"""Drop-in, fully local replacement for the zep_cloud client surface MiroFish uses.

Same method names and result attributes as the Zep SDK calls in services/*, so
those services need no logic changes. Storage and extraction live in engine.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Optional

from .engine import Engine, NotFound, get_engine


class ApiError(Exception):
    def __init__(self, status_code: Optional[int] = None, headers: Optional[dict] = None, body: Any = None):
        super().__init__(f"status_code: {status_code}, body: {body}")
        self.status_code, self.headers, self.body = status_code, headers or {}, body


class NotFoundError(ApiError):
    def __init__(self, body: Any = None):
        super().__init__(404, None, body)


@dataclass
class BatchAddItem:
    type: str = "graph_episode"
    graph_id: str = ""
    data: str = ""
    data_type: str = "text"
    source_description: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EntityEdgeSourceTarget:
    source: str = "Entity"
    target: str = "Entity"


def _obj(d: dict) -> SimpleNamespace:
    o = SimpleNamespace(**d)
    o.uuid_ = d.get("uuid")  # Zep objects expose both spellings
    return o


def _guard(fn):
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except NotFound as e:
            raise NotFoundError(str(e)) from e
    return wrapper


class _Raw:
    """Mimics `.with_raw_response.get_by_graph_id`: a page with .data and .headers (no next cursor)."""

    def __init__(self, listing):
        self._listing = listing

    @_guard
    def get_by_graph_id(self, graph_id: str, limit: int = 100, cursor: Optional[str] = None, **_):
        return SimpleNamespace(data=[_obj(d) for d in self._listing(graph_id)], headers={})


class _Node:
    def __init__(self, e: Engine):
        self._e = e
        self.with_raw_response = _Raw(e.nodes)

    @_guard
    def get(self, uuid_: str):
        return _obj(self._e.get_node(uuid_))

    @_guard
    def get_edges(self, node_uuid: str):
        return [_obj(d) for d in self._e.node_edges(node_uuid)]


class _Edge:
    def __init__(self, e: Engine):
        self.with_raw_response = _Raw(e.edges)


class _Episode:
    def __init__(self, e: Engine):
        self._e = e

    @_guard
    def get(self, uuid_: str):
        return _obj(self._e.get_episode(uuid_))


class _Graph:
    def __init__(self, e: Engine):
        self._e = e
        self.node, self.edge, self.episode = _Node(e), _Edge(e), _Episode(e)

    def create(self, graph_id: str, name: Optional[str] = None, description: Optional[str] = None, **_):
        self._e.create_graph(graph_id, name, description)
        return _obj({"graph_id": graph_id, "uuid": graph_id})

    @_guard
    def get(self, graph_id: str):
        if not self._e.graph_exists(graph_id):
            raise NotFound(f"graph {graph_id}")
        return _obj({"graph_id": graph_id, "uuid": graph_id})

    def delete(self, graph_id: str):
        self._e.delete_graph(graph_id)

    def set_ontology(self, graph_ids=None, entities=None, edges=None, **_):
        self._e.set_ontology(graph_ids or [], entities or {}, edges)

    @_guard
    def add(self, graph_id: str, type: str = "text", data: str = "", created_at: Optional[str] = None,
            source_description: Optional[str] = None, metadata: Optional[dict] = None, **_):
        ep = self._e.add_episode(graph_id, data, created_at, metadata)
        return _obj({"uuid": ep, "processed": False})

    @_guard
    def search(self, graph_id: str, query: str, limit: int = 10, scope: str = "edges",
               reranker: Optional[str] = None, **_):
        hits = [_obj(d) for d in self._e.search(graph_id, query, scope, limit, reranker)]
        return SimpleNamespace(edges=hits if scope == "edges" else [], nodes=hits if scope == "nodes" else [])


class _Batch:
    def __init__(self, e: Engine):
        self._e = e

    def create(self, metadata: Optional[dict] = None, **_):
        return SimpleNamespace(batch_id=self._e.create_batch(metadata))

    @_guard
    def add(self, batch_id: str, items: list, **_):
        return [_obj({"uuid": d["episode_uuid"], **d}) for d in self._e.add_batch_items(batch_id, items)]

    @_guard
    def process(self, batch_id: str, **_):
        self._e.process_batch(batch_id)

    @_guard
    def get(self, batch_id: str):
        s = self._e.batch_summary(batch_id)
        return SimpleNamespace(
            batch_id=batch_id, status=s["status"], metadata=s["metadata"],
            progress=SimpleNamespace(percent_complete=s["percent_complete"], succeeded_items=s["succeeded_items"]),
        )

    def list(self, limit: int = 100, cursor: Optional[int] = None, **_):
        return SimpleNamespace(batches=[SimpleNamespace(**b) for b in self._e.list_batches()], next_cursor=None)

    @_guard
    def list_items(self, batch_id: str, limit: int = 100, cursor: Optional[int] = None, **_):
        return SimpleNamespace(items=[SimpleNamespace(**i) for i in self._e.batch_items(batch_id)], next_cursor=None)


class Zep:
    """Local stand-in for zep_cloud.client.Zep; no API key, no network."""

    def __init__(self, engine: Optional[Engine] = None, **_):
        e = engine or get_engine()
        self.graph, self.batch = _Graph(e), _Batch(e)
