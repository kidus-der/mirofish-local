"""Local replacement for the Zep Cloud graph engine: SQLite store + LLM extraction.

Everything runs in-process. The only network calls are to the endpoints the user
configured for the LLM (LLM_BASE_URL) and embeddings (EMBED_BASE_URL), which the
network guard requires to be loopback. Without EMBED_MODEL_NAME, search is
lexical only.
"""

from __future__ import annotations

import json
import math
import os
import queue
import re
import sqlite3
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.local_graph")

MAX_EPISODE_CHARS = 6000  # longer episodes are extracted in several calls
EPISODE_ATTEMPTS = 3
SUMMARY_CAP = 800

_SCHEMA = """
CREATE TABLE IF NOT EXISTS graphs(graph_id TEXT PRIMARY KEY, name TEXT, description TEXT,
  ontology TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS batches(batch_id TEXT PRIMARY KEY, metadata TEXT, processing INTEGER DEFAULT 0,
  created_at TEXT, seq INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS episodes(uuid TEXT PRIMARY KEY, graph_id TEXT, data TEXT, created_at TEXT,
  metadata TEXT, batch_id TEXT, sequence_index INTEGER, state TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS nodes(uuid TEXT PRIMARY KEY, graph_id TEXT, name TEXT, name_key TEXT,
  labels TEXT, summary TEXT, attributes TEXT, created_at TEXT, embedding TEXT,
  UNIQUE(graph_id, name_key));
CREATE TABLE IF NOT EXISTS edges(uuid TEXT PRIMARY KEY, graph_id TEXT, name TEXT, fact TEXT,
  source_uuid TEXT, target_uuid TEXT, attributes TEXT, created_at TEXT, valid_at TEXT,
  episodes TEXT, embedding TEXT);
CREATE INDEX IF NOT EXISTS ix_nodes_g ON nodes(graph_id);
CREATE INDEX IF NOT EXISTS ix_edges_g ON edges(graph_id);
CREATE INDEX IF NOT EXISTS ix_eps_b ON episodes(batch_id);
"""

# Episode states: draft (batch not submitted) -> queued -> processing -> done | failed
_DONE = ("done", "failed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _tokens(text: str) -> list[str]:
    text = (text or "").lower()
    words = re.findall(r"[^\W\u4e00-\u9fff]+", text)  # any script; CJK is handled below
    for run in re.findall(r"[一-鿿]+", text):  # CJK: character bigrams
        words.extend(run[i:i + 2] for i in range(max(len(run) - 1, 1)))
    return words


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class NotFound(Exception):
    pass


class Engine:
    def __init__(
        self,
        db_path: Optional[str] = None,
        extractor: Optional[Callable[[list[dict]], dict]] = None,
        embedder: Optional[Callable[[list[str]], Optional[list[list[float]]]]] = None,
    ):
        self.db_path = db_path or os.path.join(Config.UPLOAD_FOLDER, "local_graph.sqlite")
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._extractor = extractor
        self._embedder = embedder if embedder is not None else self._default_embedder
        self._q: queue.Queue[str] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        with self._db() as c:
            c.executescript(_SCHEMA)
            c.execute("PRAGMA journal_mode=WAL")
        self._resume()

    # ---------- storage ----------
    def _db(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def _exec(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        c = self._db()
        try:
            with c:
                return c.execute(sql, args).fetchall()
        finally:
            c.close()

    def _resume(self) -> None:
        """Re-queue work that was interrupted by a restart."""
        rows = self._exec(
            "SELECT e.uuid FROM episodes e LEFT JOIN batches b ON e.batch_id=b.batch_id "
            "WHERE e.state IN ('queued','processing') OR (e.state='draft' AND b.processing=1) ORDER BY e.rowid")
        for r in rows:
            self._exec("UPDATE episodes SET state='queued' WHERE uuid=?", (r["uuid"],))
            self._enqueue(r["uuid"])

    # ---------- graphs ----------
    def create_graph(self, graph_id: str, name: str | None, description: str | None) -> None:
        self._exec(
            "INSERT OR IGNORE INTO graphs(graph_id,name,description,ontology,created_at) VALUES(?,?,?,?,?)",
            (graph_id, name, description, "{}", _now()),
        )

    def graph_exists(self, graph_id: str) -> bool:
        return bool(self._exec("SELECT 1 FROM graphs WHERE graph_id=?", (graph_id,)))

    def delete_graph(self, graph_id: str) -> None:
        for t in ("edges", "nodes", "episodes"):
            self._exec(f"DELETE FROM {t} WHERE graph_id=?", (graph_id,))
        self._exec("DELETE FROM graphs WHERE graph_id=?", (graph_id,))

    def set_ontology(self, graph_ids: list[str], entities: dict, edges: dict | None) -> None:
        ont = {"entities": {}, "edges": {}}
        for name, cls in (entities or {}).items():
            ont["entities"][name] = {
                "description": (cls.__doc__ or "").strip(),
                "attributes": {k: (f.description or "") for k, f in cls.model_fields.items()},
            }
        for name, val in (edges or {}).items():
            cls, targets = val if isinstance(val, tuple) else (val, [])
            ont["edges"][name] = {
                "description": (cls.__doc__ or "").strip(),
                "attributes": {k: (f.description or "") for k, f in cls.model_fields.items()},
                "source_targets": [{"source": t.source, "target": t.target} for t in targets or []],
            }
        for gid in graph_ids:
            self._exec("UPDATE graphs SET ontology=? WHERE graph_id=?", (json.dumps(ont, ensure_ascii=False), gid))

    # ---------- episodes / batches ----------
    def add_episode(self, graph_id: str, data: str, created_at: str | None, metadata: dict | None,
                    batch_id: str | None = None, sequence_index: int | None = None, draft: bool = False) -> str:
        if not self.graph_exists(graph_id):
            raise NotFound(f"graph {graph_id}")
        ep = str(uuid.uuid4())
        self._exec(
            "INSERT INTO episodes(uuid,graph_id,data,created_at,metadata,batch_id,sequence_index,state) VALUES(?,?,?,?,?,?,?,?)",
            (ep, graph_id, data, created_at or _now(), json.dumps(metadata or {}), batch_id,
             sequence_index, "draft" if draft else "queued"),
        )
        if not draft:
            self._enqueue(ep)
        return ep

    def create_batch(self, metadata: dict | None) -> str:
        bid = str(uuid.uuid4())
        self._exec("INSERT INTO batches(batch_id,metadata,created_at) VALUES(?,?,?)",
                   (bid, json.dumps(metadata or {}), _now()))
        return bid

    def add_batch_items(self, batch_id: str, items: list[Any]) -> list[dict]:
        rows = self._exec("SELECT seq FROM batches WHERE batch_id=?", (batch_id,))
        if not rows:
            raise NotFound(f"batch {batch_id}")
        seq = rows[0]["seq"]
        out = []
        for it in items:
            ep = self.add_episode(it.graph_id, it.data, None, getattr(it, "metadata", None),
                                  batch_id=batch_id, sequence_index=seq, draft=True)
            out.append({"episode_uuid": ep, "sequence_index": seq})
            seq += 1
        self._exec("UPDATE batches SET seq=? WHERE batch_id=?", (seq, batch_id))
        return out

    def process_batch(self, batch_id: str) -> None:
        if not self._exec("SELECT 1 FROM batches WHERE batch_id=?", (batch_id,)):
            raise NotFound(f"batch {batch_id}")
        self._exec("UPDATE batches SET processing=1 WHERE batch_id=?", (batch_id,))
        rows = self._exec("SELECT uuid FROM episodes WHERE batch_id=? AND state='draft' ORDER BY sequence_index", (batch_id,))
        for r in rows:
            self._exec("UPDATE episodes SET state='queued' WHERE uuid=?", (r["uuid"],))
            self._enqueue(r["uuid"])

    def batch_items(self, batch_id: str) -> list[dict]:
        rows = self._exec("SELECT uuid,state,error,sequence_index FROM episodes WHERE batch_id=? ORDER BY sequence_index", (batch_id,))
        return [{
            "episode_uuid": r["uuid"], "source_uuid": r["uuid"], "sequence_index": r["sequence_index"],
            "status": "succeeded" if r["state"] == "done" else "failed" if r["state"] == "failed" else "pending",
            "error": r["error"],
        } for r in rows]

    def batch_summary(self, batch_id: str) -> dict:
        rows = self._exec("SELECT * FROM batches WHERE batch_id=?", (batch_id,))
        if not rows:
            raise NotFound(f"batch {batch_id}")
        items = self.batch_items(batch_id)
        ok = sum(i["status"] == "succeeded" for i in items)
        pending = sum(i["status"] == "pending" for i in items)
        if not rows[0]["processing"]:
            status = "draft"
        elif pending:
            status = "processing"
        elif ok == len(items):
            status = "succeeded"
        else:
            status = "partial" if ok else "failed"
        return {"batch_id": batch_id, "status": status, "metadata": json.loads(rows[0]["metadata"] or "{}"),
                "succeeded_items": ok, "percent_complete": 100 * (len(items) - pending) / len(items) if items else 100}

    def list_batches(self) -> list[dict]:
        return [{"batch_id": r["batch_id"], "metadata": json.loads(r["metadata"] or "{}")}
                for r in self._exec("SELECT batch_id,metadata FROM batches ORDER BY rowid")]

    def get_episode(self, ep_uuid: str) -> dict:
        rows = self._exec("SELECT * FROM episodes WHERE uuid=?", (ep_uuid,))
        if not rows:
            raise NotFound(f"episode {ep_uuid}")
        r = rows[0]
        return {"uuid": r["uuid"], "processed": r["state"] in _DONE, "error": r["error"], "created_at": r["created_at"]}

    # ---------- worker ----------
    def _enqueue(self, ep_uuid: str) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, name="local-graph-worker", daemon=True)
                self._worker.start()
        self._q.put(ep_uuid)

    def _run(self) -> None:
        while True:
            ep = self._q.get()
            for attempt in range(1, EPISODE_ATTEMPTS + 1):
                try:
                    self._process(ep)
                    break
                except Exception as e:  # never kill the worker; the episode records the failure
                    logger.warning("episode %s attempt %d/%d failed: %s", ep, attempt, EPISODE_ATTEMPTS, e)
                    if attempt == EPISODE_ATTEMPTS:
                        logger.exception("episode %s failed permanently", ep)
                        try:
                            self._exec("UPDATE episodes SET state='failed', error=? WHERE uuid=?", (str(e)[:500], ep))
                        except sqlite3.Error:
                            logger.exception("could not record failure of episode %s", ep)
                    else:
                        time.sleep(2 ** attempt)

    def _process(self, ep_uuid: str) -> None:
        rows = self._exec("SELECT * FROM episodes WHERE uuid=?", (ep_uuid,))
        if not rows or rows[0]["state"] in _DONE:
            return
        ep = rows[0]
        self._exec("UPDATE episodes SET state='processing' WHERE uuid=?", (ep_uuid,))
        g = self._exec("SELECT ontology FROM graphs WHERE graph_id=?", (ep["graph_id"],))
        if not g:  # graph was deleted while queued
            self._exec("UPDATE episodes SET state='failed', error='graph deleted' WHERE uuid=?", (ep_uuid,))
            return
        self._ingest(ep, json.loads(g[0]["ontology"] or "{}"))
        self._exec("UPDATE episodes SET state='done' WHERE uuid=?", (ep_uuid,))

    def source_passages(self, graph_id: str, name: str, limit: int = 4) -> list[str]:
        """Uploaded document chunks mentioning `name`: full-name matches first, then its last word."""
        words = name.split()
        full = re.compile(rf"\b{re.escape(name)}\b", re.I)
        last = re.compile(rf"\b{re.escape(words[-1])}\b", re.I) if words else full
        rows = self._exec("SELECT data FROM episodes WHERE graph_id=? AND batch_id IS NOT NULL "
                          "ORDER BY sequence_index", (graph_id,))  # simulation memory has no batch
        texts = [r["data"] for r in rows]
        return ([t for t in texts if full.search(t)] + [t for t in texts if last.search(t) and not full.search(t)])[:limit]

    def _ingest(self, ep: sqlite3.Row, ontology: dict) -> None:
        text = ep["data"]
        for i in range(0, max(len(text), 1), MAX_EPISODE_CHARS):
            self._store(ep["graph_id"], ep["uuid"], ep["created_at"], ontology,
                        self._extract(ontology, text[i:i + MAX_EPISODE_CHARS]))

    # ---------- extraction ----------
    def _extract(self, ontology: dict, text: str) -> dict:
        ents = ontology.get("entities") or {}
        rels = ontology.get("edges") or {}
        ent_lines = "\n".join(f"- {n}: {d.get('description','')} (attributes: {', '.join(d.get('attributes', {})) or 'none'})"
                              for n, d in ents.items()) or "- (no declared types; use type \"Entity\")"
        rel_lines = "\n".join(f"- {n}: {d.get('description','')} "
                              f"[{'; '.join(s['source']+'->'+s['target'] for s in d.get('source_targets', []))}]"
                              for n, d in rels.items()) or "- RELATED_TO: generic relationship"
        system = (
            "You extract a knowledge graph from text. Reply with one JSON object only:\n"
            '{"entities":[{"name":str,"type":str,"summary":str,"attributes":{str:str}}],'
            '"relations":[{"source":str,"target":str,"type":str,"fact":str}]}\n'
            "Use only these entity types:\n" + ent_lines + "\nUse only these relation types:\n" + rel_lines +
            "\nNames must be the exact names used in the text. 'fact' is one self-contained sentence. "
            "Skip anything not stated in the text. If nothing qualifies return empty lists."
        )
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": text}]
        if self._extractor:
            return self._extractor(msgs)
        from ..utils.llm_client import LLMClient  # lazy: avoid import cycle at module load
        return LLMClient().chat_json(messages=msgs, temperature=0.1, max_tokens=2048, max_attempts=2)

    def _store(self, graph_id: str, ep_uuid: str, created_at: str, ontology: dict, data: dict) -> None:
        valid = {k.lower(): k for k in (ontology.get("entities") or {})}
        edge_types = set((ontology.get("edges") or {}).keys())
        now = _now()
        c = self._db()
        try:
            with c:
                if not c.execute("SELECT 1 FROM graphs WHERE graph_id=?", (graph_id,)).fetchone():
                    return  # graph deleted during the slow extraction

                def text(v: Any) -> str:
                    return v.strip() if isinstance(v, str) else ""

                def node_for(name: str, typ: Any = None, summary: str = "", attrs: dict | None = None) -> str:
                    k = _key(name)
                    row = c.execute("SELECT * FROM nodes WHERE graph_id=? AND name_key=?", (graph_id, k)).fetchone()
                    canon = valid.get(text(typ).lower())
                    labels = ["Entity"] + ([canon] if canon else [])
                    if row:
                        old = json.loads(row["labels"])
                        merged = old + [l for l in labels if l not in old]
                        s = row["summary"] or ""
                        if summary and summary not in s:
                            s = (s + " " + summary).strip()[:SUMMARY_CAP]
                        a = {**json.loads(row["attributes"] or "{}"), **(attrs or {})}
                        c.execute("UPDATE nodes SET labels=?, summary=?, attributes=?, embedding=NULL WHERE uuid=?",
                                  (json.dumps(merged), s, json.dumps(a, ensure_ascii=False), row["uuid"]))
                        return row["uuid"]
                    nid = str(uuid.uuid4())
                    c.execute("INSERT INTO nodes(uuid,graph_id,name,name_key,labels,summary,attributes,created_at) VALUES(?,?,?,?,?,?,?,?)",
                              (nid, graph_id, name, k, json.dumps(labels), summary[:SUMMARY_CAP],
                               json.dumps(attrs or {}, ensure_ascii=False), now))
                    return nid

                for e in data.get("entities") or []:
                    if isinstance(e, dict) and text(e.get("name")):
                        attrs = {str(k): str(v) for k, v in e["attributes"].items()} if isinstance(e.get("attributes"), dict) else {}
                        node_for(text(e["name"]), e.get("type"), text(e.get("summary")), attrs)
                for r in data.get("relations") or []:
                    if not isinstance(r, dict) or not text(r.get("source")) or not text(r.get("target")) or not text(r.get("fact")):
                        continue
                    src, dst = node_for(text(r["source"])), node_for(text(r["target"]))
                    fact = text(r["fact"])
                    etype = text(r.get("type")) or "RELATED_TO"
                    etype = etype if (not edge_types or etype in edge_types) else "RELATED_TO"
                    if c.execute("SELECT 1 FROM edges WHERE graph_id=? AND source_uuid=? AND target_uuid=? AND fact=?",
                                 (graph_id, src, dst, fact)).fetchone():
                        continue
                    c.execute("INSERT INTO edges(uuid,graph_id,name,fact,source_uuid,target_uuid,attributes,created_at,valid_at,episodes) VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (str(uuid.uuid4()), graph_id, etype, fact, src, dst, "{}", now, created_at, json.dumps([ep_uuid])))
        finally:
            c.close()

    # ---------- reads ----------
    def _node(self, r: sqlite3.Row) -> dict:
        return {"uuid": r["uuid"], "name": r["name"], "labels": json.loads(r["labels"]), "summary": r["summary"] or "",
                "attributes": json.loads(r["attributes"] or "{}"), "created_at": r["created_at"]}

    def _edge(self, r: sqlite3.Row) -> dict:
        return {"uuid": r["uuid"], "name": r["name"], "fact": r["fact"], "source_node_uuid": r["source_uuid"],
                "target_node_uuid": r["target_uuid"], "attributes": json.loads(r["attributes"] or "{}"),
                "created_at": r["created_at"], "valid_at": r["valid_at"], "invalid_at": None, "expired_at": None,
                "episodes": json.loads(r["episodes"] or "[]")}

    def nodes(self, graph_id: str) -> list[dict]:
        return [self._node(r) for r in self._exec("SELECT * FROM nodes WHERE graph_id=? ORDER BY rowid", (graph_id,))]

    def edges(self, graph_id: str) -> list[dict]:
        return [self._edge(r) for r in self._exec("SELECT * FROM edges WHERE graph_id=? ORDER BY rowid", (graph_id,))]

    def get_node(self, node_uuid: str) -> dict:
        rows = self._exec("SELECT * FROM nodes WHERE uuid=?", (node_uuid,))
        if not rows:
            raise NotFound(f"node {node_uuid}")
        return self._node(rows[0])

    def node_edges(self, node_uuid: str) -> list[dict]:
        return [self._edge(r) for r in self._exec("SELECT * FROM edges WHERE source_uuid=? OR target_uuid=?", (node_uuid, node_uuid))]

    # ---------- search ----------
    def _default_embedder(self, texts: list[str]) -> Optional[list[list[float]]]:
        model = os.environ.get("EMBED_MODEL_NAME")
        if not model:
            return None
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("EMBED_API_KEY") or Config.LLM_API_KEY or "local",
                        base_url=os.environ.get("EMBED_BASE_URL") or Config.LLM_BASE_URL)
        res = client.embeddings.create(model=model, input=texts)
        return [d.embedding for d in res.data]

    def _ensure_embeddings(self, table: str, rows: list[sqlite3.Row], text_of: Callable[[sqlite3.Row], str]) -> dict[str, list[float]]:
        vecs: dict[str, list[float]] = {r["uuid"]: json.loads(r["embedding"]) for r in rows if r["embedding"]}
        todo = [r for r in rows if r["uuid"] not in vecs]
        for i in range(0, len(todo), 64):
            part = todo[i:i + 64]
            try:
                out = self._embedder([text_of(r) for r in part])
            except Exception as e:
                logger.warning("embedding failed, falling back to lexical for %d items: %s", len(part), e)
                return vecs
            if not out:
                return vecs
            for r, v in zip(part, out):
                vecs[r["uuid"]] = v
                self._exec(f"UPDATE {table} SET embedding=? WHERE uuid=?", (json.dumps(v), r["uuid"]))
        return vecs

    def search(self, graph_id: str, query: str, scope: str, limit: int, reranker: Optional[str] = None) -> list[dict]:
        if not self.graph_exists(graph_id):
            raise NotFound(f"graph {graph_id}")
        table, text_of, shape = (("edges", lambda r: r["fact"], self._edge) if scope == "edges"
                                 else ("nodes", lambda r: f"{r['name']}: {r['summary'] or ''}", self._node))
        rows = self._exec(f"SELECT * FROM {table} WHERE graph_id=?", (graph_id,))
        if not rows:
            return []
        q = set(_tokens(query))
        docs = {r["uuid"]: set(_tokens(text_of(r))) for r in rows}
        df = Counter(t for d in docs.values() for t in d)
        idf = {u: sum(math.log(1 + len(rows) / df[t]) for t in q & d) for u, d in docs.items()}  # rare words count most
        ranks: list[list[str]] = [sorted((u for u, v in idf.items() if v > 0), key=lambda u: -idf[u])]
        try:
            qv = (self._embedder([query]) or [None])[0]
        except Exception as e:
            logger.warning("query embedding failed, lexical only: %s", e)
            qv = None
        if qv:
            vecs = self._ensure_embeddings(table, rows, text_of)
            ranks.append([u for u, _ in sorted(((u, _cosine(qv, v)) for u, v in vecs.items()), key=lambda x: -x[1])])
        score: dict[str, float] = {}
        for lst in ranks:
            for i, u in enumerate(lst):
                score[u] = score.get(u, 0.0) + 1.0 / (60 + i)  # reciprocal-rank fusion
        by_uuid = {r["uuid"]: r for r in rows}
        top = sorted(score, key=lambda u: -score[u])[:limit]
        return [shape(by_uuid[u]) for u in top]


_engine: Optional[Engine] = None
_engine_lock = threading.Lock()


def get_engine() -> Engine:
    global _engine
    with _engine_lock:
        if _engine is None:
            if os.environ.get("GRAPH_BACKEND", "graphiti") == "sqlite":
                _engine = Engine()
            else:
                from .graphiti_engine import GraphitiEngine
                _engine = GraphitiEngine()
        return _engine


def set_engine(engine: Optional[Engine]) -> None:
    """Swap the process-wide engine (tests)."""
    global _engine
    with _engine_lock:
        _engine = engine
