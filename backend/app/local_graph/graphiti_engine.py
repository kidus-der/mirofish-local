"""Graphiti (the open-source engine behind Zep) on embedded FalkorDB, with local models only.

Inherits job tracking (graphs, batches, episodes, worker) from Engine and replaces extraction,
storage and search. All Graphiti work runs on one private asyncio loop.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import os
import re
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional

import redis
from pydantic import Field, create_model

from ..config import Config
from ..utils.logger import get_logger
from .engine import Engine, NotFound

os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")
os.environ.setdefault("SEMAPHORE_LIMIT", os.environ.get("OLLAMA_NUM_PARALLEL", "2"))

from graphiti_core import Graphiti  # noqa: E402
from graphiti_core.cross_encoder.client import CrossEncoderClient  # noqa: E402
from graphiti_core.driver.falkordb_driver import FalkorDriver  # noqa: E402
from graphiti_core.edges import EntityEdge  # noqa: E402
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig  # noqa: E402
from graphiti_core.errors import NodeNotFoundError  # noqa: E402
from graphiti_core.llm_client.config import LLMConfig  # noqa: E402
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient  # noqa: E402
from graphiti_core.nodes import EntityNode, EpisodeType  # noqa: E402
from graphiti_core.search.search_config_recipes import (  # noqa: E402
    EDGE_HYBRID_SEARCH_CROSS_ENCODER,
    EDGE_HYBRID_SEARCH_RRF,
    NODE_HYBRID_SEARCH_CROSS_ENCODER,
    NODE_HYBRID_SEARCH_RRF,
)
from openai import AsyncOpenAI  # noqa: E402
from redislite.async_falkordb_client import AsyncFalkorDB  # noqa: E402

logger = get_logger("mirofish.graphiti")

EPISODE_TIMEOUT_S = int(os.environ.get("GRAPH_EPISODE_TIMEOUT_SECONDS", "1800"))
RERANK_MODEL = os.environ.get("RERANK_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
# Small models need this spelled out: short names and acronyms otherwise become separate entities.
EXTRACTION_HINT = os.environ.get("GRAPH_EXTRACTION_HINT", (
    "Always name an entity by its fullest proper name found in the current or previous text "
    "(for example the full personal name instead of a surname, and the full organization name instead of an acronym). "
    "Never create a separate entity for a short name, title or acronym of an entity already known. "
    "State each fact exactly as the text supports it; do not attribute a statement or action to anyone the text does not."))

# Field names Graphiti keeps for itself on nodes and edges.
_RESERVED = {"uuid", "name", "group_id", "labels", "created_at", "summary", "attributes", "name_embedding",
             "fact", "fact_embedding", "episodes", "expired_at", "valid_at", "invalid_at",
             "source_node_uuid", "target_node_uuid"}


class _NoThinkChat:
    """Adds reasoning_effort to every completion: Graphiti has no setting for it."""

    def __init__(self, client: AsyncOpenAI, effort: str):
        async def create(**kw: Any):
            if effort:
                kw.setdefault("reasoning_effort", effort)
            return await client.chat.completions.create(**kw)

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class LocalReranker(CrossEncoderClient):
    """BGE cross-encoder, loaded on first use so graph building does not pay its memory."""

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    def _predict(self, pairs: list[list[str]]):
        with self._lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(RERANK_MODEL, max_length=512)
            return self._model.predict(pairs, batch_size=16, show_progress_bar=False)

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        if not passages:
            return []
        scores = await asyncio.get_running_loop().run_in_executor(None, self._predict, [[query, p] for p in passages])
        return sorted(zip(passages, map(float, scores)), key=lambda x: -x[1])


def _model(name: str, spec: dict):
    fields = {("attr_" + k if k in _RESERVED else k): (Optional[str], Field(default=None, description=d or k))
              for k, d in (spec.get("attributes") or {}).items()}
    return create_model(name, __doc__=spec.get("description") or name, **fields)


_TITLE = re.compile(r"^(the|mr|mrs|ms|dr|mayor|president|ceo|chair|council member|councillor|senator|minister)\.?\s+", re.I)


def _plain(name: str) -> str:
    n = (name or "").strip()
    while True:
        m = _TITLE.sub("", n)
        if m == n:
            return n.lower()
        n = m


def alias_merges(nodes: list[dict]) -> dict[str, str]:
    """Map duplicate node uuid -> canonical uuid, using only unambiguous name evidence.

    Graphiti's LLM dedupe misses these on a small model: "HVWA" for "Harbor Vale Water Authority",
    "Okafor" for "Nadia Okafor", "The Courier" for "Harbor Vale Courier". A short name matching two
    candidates ("Reyes" with Tomas and Marco) is left alone.
    """
    def types(n):
        return {x for x in n["labels"] if x not in ("Entity", "Node")}

    def compatible(a, b):
        return not types(a) or not types(b) or bool(types(a) & types(b))

    out: dict[str, str] = {}
    by_len = sorted(nodes, key=lambda n: -len(_plain(n["name"])))
    for short in nodes:
        s = _plain(short["name"])
        words = s.split()
        if not s:
            continue
        hits = []
        for long in by_len:
            if long["uuid"] == short["uuid"] or long["uuid"] in out or not compatible(short, long):
                continue
            lw = _plain(long["name"]).split()
            same = lw == words and len(short["name"]) > len(long["name"])  # "The X" -> "X"
            acronym = len(words) == 1 and short["name"].isupper() and len(s) >= 3 and s == "".join(w[0] for w in lw if w not in ("of", "and", "for"))
            part = bool(types(short) & types(long)) and len(lw) > len(words) \
                and (lw[-len(words):] == words or lw[:len(words)] == words)
            if same or acronym or part:
                hits.append(long)
        if len(hits) == 1 and short["uuid"] not in {out.get(hits[0]["uuid"])}:
            out[short["uuid"]] = hits[0]["uuid"]
    return out


def _iso(v: Any) -> Optional[str]:
    return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v else None)


class GraphitiEngine(Engine):
    def __init__(self, db_path: Optional[str] = None, graph_path: Optional[str] = None):
        self.graph_path = graph_path or os.path.join(Config.UPLOAD_FOLDER, "local_graph.rdb")
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, name="graphiti-loop", daemon=True).start()
        self._graphs: dict[str, Graphiti] = {}
        self._node_graph: dict[str, str] = {}
        self._falkor = None
        self._init_lock: Optional[asyncio.Lock] = None
        base = os.environ.get("EMBED_BASE_URL") or Config.LLM_BASE_URL
        client = AsyncOpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL, timeout=900, max_retries=1)
        self._llm = OpenAIGenericClient(
            config=LLMConfig(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL, model=Config.LLM_MODEL_NAME,
                             small_model=Config.LLM_MODEL_NAME, temperature=0.1),
            client=_NoThinkChat(client, os.environ.get("LLM_REASONING_EFFORT", "none")),
            max_tokens=4096, structured_output_mode=os.environ.get("GRAPH_STRUCTURED_MODE", "json_schema"),
        )
        self._g_embedder = OpenAIEmbedder(OpenAIEmbedderConfig(
            api_key=Config.LLM_API_KEY, base_url=base,
            embedding_model=os.environ.get("EMBED_MODEL_NAME", "qwen3-embedding:0.6b"),
            embedding_dim=int(os.environ.get("EMBED_DIM", "1024"))))
        self._reranker = LocalReranker()
        super().__init__(db_path=db_path)  # last: resuming queued episodes needs everything above

    # ---------- plumbing ----------
    def _call(self, coro, timeout: float = 300):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _graph(self, graph_id: str) -> Graphiti:
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()
        async with self._init_lock:
            if self._falkor is None:
                os.makedirs(os.path.dirname(os.path.abspath(self.graph_path)), exist_ok=True)
                # Append-only log: a crash loses at most about a second of graph writes.
                self._falkor = AsyncFalkorDB(dbfilename=self.graph_path, serverconfig={"appendonly": "yes"})
                atexit.register(self.close)
            g = self._graphs.get(graph_id)
            if g is None:  # one Graphiti per graph: it would otherwise switch databases mid-await
                g = Graphiti(graph_driver=FalkorDriver(falkor_db=self._falkor, database=graph_id),
                             llm_client=self._llm, embedder=self._g_embedder, cross_encoder=self._reranker)
                await g.build_indices_and_constraints()
                self._graphs[graph_id] = g
            return g

    def close(self) -> None:
        """Save and stop the embedded server; redislite's own async close leaves it running."""
        falkor, self._falkor = self._falkor, None
        if falkor is None or self._loop.is_closed():
            return

        async def stop():
            try:
                await falkor.client.execute_command("SHUTDOWN", "SAVE")
            except (ConnectionError, OSError, redis.RedisError):
                pass  # the server drops the connection as it exits
        try:
            self._call(stop(), 30)
        except Exception as e:
            logger.warning("embedded FalkorDB did not stop cleanly: %s", e)
        self._graphs.clear()

    # ---------- ingestion ----------
    def _ingest(self, ep, ontology: dict) -> None:
        self._call(self._add(ep, ontology), EPISODE_TIMEOUT_S)

    async def _add(self, ep, ontology: dict) -> None:
        g = await self._graph(ep["graph_id"])
        ents = {n: _model(n, s) for n, s in (ontology.get("entities") or {}).items()}
        edges = {n: _model(n, s) for n, s in (ontology.get("edges") or {}).items()}
        emap: dict[tuple[str, str], list[str]] = {}
        for n, s in (ontology.get("edges") or {}).items():
            for st in s.get("source_targets") or []:
                emap.setdefault((st["source"], st["target"]), []).append(n)
        when = datetime.fromisoformat(ep["created_at"].replace("Z", "+00:00"))
        source = json.loads(ep["metadata"] or "{}").get("source", "document")
        res = await g.add_episode(
            name=f"episode-{ep['uuid'][:8]}", episode_body=ep["data"],
            source_description=source,
            reference_time=when if when.tzinfo else when.replace(tzinfo=timezone.utc),
            source=EpisodeType.text, group_id=ep["graph_id"],
            entity_types=ents or None, edge_types=edges or None, edge_type_map=emap or None,
            custom_extraction_instructions=EXTRACTION_HINT,
        )
        for n in res.nodes:
            self._node_graph[n.uuid] = ep["graph_id"]
        await self._merge_aliases(g, ep["graph_id"])

    async def _merge_aliases(self, g: Graphiti, graph_id: str) -> None:
        found = await EntityNode.get_by_group_ids(g.driver, [graph_id])
        by_id = {n.uuid: n for n in found}
        for dup_id, keep_id in alias_merges([self._node_dict(n) for n in found]).items():
            dup, keep = by_id[dup_id], by_id[keep_id]
            for e in await EntityEdge.get_by_node_uuid(g.driver, dup_id):
                await e.delete(g.driver)
                e.source_node_uuid = keep_id if e.source_node_uuid == dup_id else e.source_node_uuid
                e.target_node_uuid = keep_id if e.target_node_uuid == dup_id else e.target_node_uuid
                if e.source_node_uuid != e.target_node_uuid:  # a merge can turn an edge into a self-loop
                    await e.generate_embedding(self._g_embedder)
                    await e.save(g.driver)
            if dup.summary and dup.summary not in (keep.summary or ""):
                keep.summary = f"{keep.summary or ''} {dup.summary}".strip()
            keep.labels = list(dict.fromkeys([*keep.labels, *dup.labels]))
            keep.attributes = {**dup.attributes, **keep.attributes}
            if keep.name_embedding is None:
                await keep.generate_name_embedding(self._g_embedder)
            await keep.save(g.driver)
            await dup.delete(g.driver)
            self._node_graph.pop(dup_id, None)
            logger.info("merged alias %r into %r", dup.name, keep.name)

    # ---------- reads ----------
    @staticmethod
    def _node_dict(n: EntityNode) -> dict:
        return {"uuid": n.uuid, "name": n.name, "labels": list(n.labels or []), "summary": n.summary or "",
                "attributes": dict(n.attributes or {}), "created_at": _iso(n.created_at)}

    @staticmethod
    def _edge_dict(e: EntityEdge) -> dict:
        return {"uuid": e.uuid, "name": e.name, "fact": e.fact, "source_node_uuid": e.source_node_uuid,
                "target_node_uuid": e.target_node_uuid, "attributes": dict(e.attributes or {}),
                "created_at": _iso(e.created_at), "valid_at": _iso(e.valid_at), "invalid_at": _iso(e.invalid_at),
                "expired_at": _iso(e.expired_at), "episodes": list(e.episodes or [])}

    def nodes(self, graph_id: str) -> list[dict]:
        async def go():
            g = await self._graph(graph_id)
            return await EntityNode.get_by_group_ids(g.driver, [graph_id])
        out = self._call(go())
        self._node_graph.update({n.uuid: graph_id for n in out})
        return [self._node_dict(n) for n in out]

    def edges(self, graph_id: str) -> list[dict]:
        async def go():
            g = await self._graph(graph_id)
            return await EntityEdge.get_by_group_ids(g.driver, [graph_id])
        try:
            return [self._edge_dict(e) for e in self._call(go())]
        except Exception as e:
            if type(e).__name__ == "GroupsEdgesNotFoundError":  # Graphiti raises this for "no edges yet"
                return []
            raise

    def _locate(self, node_uuid: str):
        known = self._node_graph.get(node_uuid)
        ids = [known] if known else [r["graph_id"] for r in self._exec("SELECT graph_id FROM graphs")]

        async def go():
            for gid in ids:
                g = await self._graph(gid)
                try:
                    return gid, await EntityNode.get_by_uuid(g.driver, node_uuid)
                except NodeNotFoundError:
                    continue
            raise NotFound(f"node {node_uuid}")
        return self._call(go())

    def get_node(self, node_uuid: str) -> dict:
        gid, n = self._locate(node_uuid)
        self._node_graph[node_uuid] = gid
        return self._node_dict(n)

    def node_edges(self, node_uuid: str) -> list[dict]:
        gid, _ = self._locate(node_uuid)

        async def go():
            g = await self._graph(gid)
            return await EntityEdge.get_by_node_uuid(g.driver, node_uuid)
        return [self._edge_dict(e) for e in self._call(go())]

    def search(self, graph_id: str, query: str, scope: str, limit: int, reranker: Optional[str] = None) -> list[dict]:
        if not self.graph_exists(graph_id):
            raise NotFound(f"graph {graph_id}")
        cross = reranker != "rrf"
        cfg = (EDGE_HYBRID_SEARCH_CROSS_ENCODER if cross else EDGE_HYBRID_SEARCH_RRF) if scope == "edges" \
            else (NODE_HYBRID_SEARCH_CROSS_ENCODER if cross else NODE_HYBRID_SEARCH_RRF)
        cfg = cfg.model_copy(deep=True)
        cfg.limit = limit

        async def go():
            g = await self._graph(graph_id)
            return await g.search_(query, config=cfg, group_ids=[graph_id])
        res = self._call(go())
        return [self._edge_dict(e) for e in res.edges] if scope == "edges" else [self._node_dict(n) for n in res.nodes]

    def delete_graph(self, graph_id: str) -> None:
        async def go():
            await self._graph(graph_id)
            self._graphs.pop(graph_id, None)
            try:
                await self._falkor.select_graph(graph_id).delete()
            except Exception as e:  # an empty graph has nothing to delete
                logger.info("graph %s delete: %s", graph_id, e)
        self._call(go())
        self._node_graph = {k: v for k, v in self._node_graph.items() if v != graph_id}
        super().delete_graph(graph_id)
