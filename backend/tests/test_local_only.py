"""Proof the fork is local: the guard blocks outbound traffic, and the real GraphBuilder
pipeline runs end to end on the local engine with no network and no LLM server."""

import os
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

_REAL_SLEEP = time.sleep  # graph_builder.time is the same module, so keep the original
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(code: str, **env):
    e = {**os.environ, "PYTHONPATH": BACKEND, **env}
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=e, timeout=30)


def test_guard_autoloads_and_blocks_external_ip():
    # No explicit import of netguard: sitecustomize on PYTHONPATH must load it (this is how
    # the simulation subprocesses are covered).
    r = _run("import socket; socket.create_connection(('93.184.216.34', 80), timeout=2)")
    assert r.returncode != 0 and "netguard" in r.stderr


def test_guard_blocks_dns_for_external_names():
    r = _run("import socket; socket.getaddrinfo('example.com', 443)")
    assert r.returncode != 0 and "netguard" in r.stderr


def test_guard_blocks_https_client_libraries():
    r = _run("import httpx; httpx.get('https://example.com', timeout=3)")
    assert r.returncode != 0 and "netguard" in (r.stderr + r.stdout)


def test_guard_allows_loopback():
    code = (
        "import socket\n"
        "s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(1)\n"
        "c = socket.create_connection(s.getsockname(), timeout=2); print('ok')\n"
    )
    r = _run(code)
    assert r.returncode == 0 and "ok" in r.stdout


def test_guard_allowlist_is_explicit_only():
    r = _run("import socket; socket.getaddrinfo('gpu-box.lan', 11434)", NETGUARD_ALLOW="gpu-box.lan")
    assert "blocked" not in r.stderr  # allowed through the guard (may still fail to resolve)


@pytest.mark.parametrize("call", [
    "socket.gethostbyname('example.com')",
    "socket.gethostbyname_ex('example.com')",
    "socket.gethostbyaddr('93.184.216.34')",
    "socket.getnameinfo(('93.184.216.34', 80), 0)",
    "socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendmsg([b'x'], [], 0, ('93.184.216.34', 53))",
])
def test_guard_blocks_other_resolver_and_send_paths(call):
    r = _run(f"import socket; {call}")
    assert r.returncode != 0 and "netguard" in r.stderr


def test_guard_no_localhost_suffix_allowance():
    import netguard

    assert netguard.host_allowed("localhost") and not netguard.host_allowed("evil.localhost")


def test_guard_off_warns_loudly():
    r = _run("pass", NETGUARD="off")
    assert "NETGUARD=off" in r.stderr and r.stderr.count("DISABLED") == 1


def test_untrusted_host_rejected():
    from app import create_app

    client = create_app().test_client()
    assert client.get("/health", headers={"Host": "evil.com"}).status_code == 400
    assert client.get("/health", headers={"Host": "localhost.evil.com:5001"}).status_code == 400
    for host in ("localhost:5001", "127.0.0.1:5001", "[::1]:5001"):
        assert client.get("/health", headers={"Host": host}).status_code == 200


def test_foreign_origin_post_rejected_and_allowed_origin_passes():
    from app import create_app

    client = create_app().test_client()
    # Simple cross-site multipart POST: no CORS preflight, so the server itself must refuse it.
    r = client.post("/api/graph/ontology/generate", data={"a": "b"}, headers={"Origin": "https://evil.com"})
    assert r.status_code == 403
    assert client.get("/health", headers={"Origin": "null"}).status_code == 403
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        assert client.get("/health", headers={"Origin": origin}).status_code == 200
        r = client.post("/api/graph/ontology/generate", data={"a": "b"}, headers={"Origin": origin})
        assert r.status_code != 403  # reaches the handler (which rejects the missing files itself)


def test_config_rejects_non_local_llm_url(monkeypatch):
    from app.config import Config

    monkeypatch.setattr(Config, "LLM_BASE_URL", "https://api.openai.com/v1")
    assert any("LLM_BASE_URL" in e for e in Config.validate())
    monkeypatch.setattr(Config, "LLM_BASE_URL", "http://localhost:11434/v1")
    assert Config.validate() == []


def test_unsafe_ids_rejected():
    from app import create_app

    client = create_app().test_client()
    r = client.delete("/api/graph/project/%2e%2e")
    assert r.status_code == 400


# ---- the real GraphBuilderService on the local engine, fake extractor, no network ----

def fake_extractor(messages):
    text = messages[-1]["content"]
    ents, rels = [], []
    for line in text.split("."):
        if " mentors " in line:
            a, b = [p.strip() for p in line.split(" mentors ")]
            ents += [{"name": a, "type": "Person", "summary": f"{a} is a mentor"},
                     {"name": b, "type": "Person", "summary": f"{b} is mentored"}]
            rels.append({"source": a, "target": b, "type": "MENTORS", "fact": f"{a} mentors {b}"})
    return {"entities": ents, "relations": rels}


@pytest.fixture
def engine(tmp_path):
    from app.local_graph import engine as eng

    e = eng.Engine(db_path=str(tmp_path / "g.sqlite"), extractor=fake_extractor, embedder=lambda t: None)
    eng.set_engine(e)
    yield e
    eng.set_engine(None)


ONTOLOGY = {
    "entity_types": [{"name": "Person", "description": "A person.", "attributes": []}],
    "edge_types": [{"name": "MENTORS", "description": "Mentors someone.", "attributes": [],
                    "source_targets": [{"source": "Person", "target": "Person"}]}],
}


def test_graph_pipeline_end_to_end(engine, monkeypatch):
    from app.services import graph_builder
    from app.services.graph_builder import GraphBuilderService

    monkeypatch.setattr(graph_builder.time, "sleep", lambda s: _REAL_SLEEP(0.05))
    b = GraphBuilderService()
    gid = b.create_graph("t")
    b.set_ontology(gid, ONTOLOGY)
    sub = b.add_text_batches(gid, ["Ada mentors Grace.", "Grace mentors Linus.", "Ada mentors Grace."])
    eps = b._wait_for_batch(sub, timeout=30)
    assert len(eps) == 3

    data = b.get_graph_data(gid)
    names = {n["name"] for n in data["nodes"]}
    assert names == {"Ada", "Grace", "Linus"}            # deduped across chunks
    assert data["edge_count"] == 2                        # duplicate fact not re-added
    assert all("Person" in n["labels"] for n in data["nodes"])
    assert {e["name"] for e in data["edges"]} == {"MENTORS"}

    # keyword search (no embedding model configured)
    from app.utils.zep import get_zep_client
    c = get_zep_client()
    res = c.graph.search(graph_id=gid, query="who mentors Linus", scope="edges", limit=5)
    assert any("Linus" in e.fact for e in res.edges)
    nres = c.graph.search(graph_id=gid, query="Ada", scope="nodes", limit=5)
    assert nres.nodes and nres.nodes[0].name == "Ada"

    # simulation memory write-back path: graph.add + episode polling
    ep = c.graph.add(graph_id=gid, type="text", data="Linus mentors Ada.", metadata={})
    for _ in range(100):
        if c.graph.episode.get(uuid_=ep.uuid_).processed:
            break
        time.sleep(0.05)
    assert c.graph.episode.get(uuid_=ep.uuid_).processed
    assert b.get_graph_data(gid)["edge_count"] == 3

    # delete
    b.delete_graph(gid)
    from app.local_graph import NotFoundError
    with pytest.raises(NotFoundError):
        c.graph.get(gid)


def test_failed_extraction_surfaces_as_failed_batch(tmp_path, monkeypatch):
    from app.local_graph import engine as eng
    from app.services import graph_builder
    from app.services.graph_builder import GraphBuilderService

    def boom(_):
        raise RuntimeError("model returned garbage")

    e = eng.Engine(db_path=str(tmp_path / "g.sqlite"), extractor=boom, embedder=lambda t: None)
    eng.set_engine(e)
    try:
        monkeypatch.setattr(graph_builder.time, "sleep", lambda s: _REAL_SLEEP(0.05))
        b = GraphBuilderService()
        gid = b.create_graph("t")
        sub = b.add_text_batches(gid, ["x"])
        with pytest.raises(RuntimeError, match="model returned garbage"):
            b._wait_for_batch(sub, timeout=30)
    finally:
        eng.set_engine(None)


def test_graphiti_store_survives_restart(tmp_path):
    """Graph data must outlive the backend process (embedded FalkorDB persists to one file)."""
    from graphiti_core.nodes import EntityNode

    from app.local_graph.graphiti_engine import GraphitiEngine

    paths = dict(db_path=str(tmp_path / "g.sqlite"), graph_path=str(tmp_path / "f.rdb"))
    e = GraphitiEngine(**paths)
    e.create_graph("g1", "n", "d")

    async def put():
        g = await e._graph("g1")
        await EntityNode(name="Ada", group_id="g1", labels=["Entity", "Person"], summary="s",
                         name_embedding=[0.1] * 1024).save(g.driver)
    e._call(put(), 60)
    assert [n["name"] for n in e.nodes("g1")] == ["Ada"]
    pid = e._falkor.client.pid
    e.close()
    with pytest.raises(ProcessLookupError):  # really stopped, so the reopen below reads from disk
        for _ in range(100):
            os.kill(pid, 0)
            time.sleep(0.05)

    e2 = GraphitiEngine(**paths)
    try:
        nodes = e2.nodes("g1")
        assert [n["name"] for n in nodes] == ["Ada"] and "Person" in nodes[0]["labels"]
        assert e2.get_node(nodes[0]["uuid"])["name"] == "Ada"
        assert e2.edges("g1") == []
        e2.delete_graph("g1")
        assert not e2.graph_exists("g1")
    finally:
        e2.close()


def test_graphiti_store_survives_server_crash(tmp_path):
    import signal

    from graphiti_core.nodes import EntityNode

    from app.local_graph.graphiti_engine import GraphitiEngine

    paths = dict(db_path=str(tmp_path / "g.sqlite"), graph_path=str(tmp_path / "f.rdb"))
    e = GraphitiEngine(**paths)
    e.create_graph("g1", "n", "d")

    async def put():
        g = await e._graph("g1")
        await EntityNode(name="Ada", group_id="g1", labels=["Entity"], summary="s",
                         name_embedding=[0.1] * 1024).save(g.driver)
    e._call(put(), 60)
    time.sleep(1.5)  # appendfsync everysec
    os.kill(e._falkor.client.pid, signal.SIGKILL)
    time.sleep(0.2)
    e._falkor = None

    e2 = GraphitiEngine(**paths)
    try:
        assert [n["name"] for n in e2.nodes("g1")] == ["Ada"]
    finally:
        e2.close()


def test_alias_merges_only_unambiguous_names():
    from app.local_graph.graphiti_engine import alias_merges

    def n(u, name, *t):
        return {"uuid": u, "name": name, "labels": ["Entity", *t]}

    nodes = [n("1", "Harbor Vale Water Authority", "Organization"), n("2", "HVWA", "Organization"),
             n("3", "Nadia Okafor", "Person"), n("4", "Okafor", "Person"),
             n("5", "Tomas Reyes", "Person"), n("6", "Marco Reyes", "Person"), n("7", "Reyes", "Person"),
             n("8", "Harbor Vale Courier", "Organization"), n("9", "The Harbor Vale Courier", "Organization"),
             n("10", "Mayor Ilse Varga", "Person"), n("11", "Ilse Varga", "Person"),
             n("12", "Harbor Vale"), n("13", "Okafor Holdings", "Organization")]
    m = alias_merges(nodes)
    assert m["2"] == "1" and m["4"] == "3"          # acronym, surname
    assert "7" not in m                              # ambiguous between two people
    assert m["9"] == "8"                             # leading "The"
    assert {m.get("10"), m.get("11")} & {"10", "11"}  # title variant merges one way
    assert "13" not in m and "1" not in m and "3" not in m


def test_source_passages_prefer_full_name_and_skip_simulation_memory(engine):
    e = engine
    e.create_graph("g", "g", "")
    batch = e.create_batch({})
    e.add_batch_items(batch, [SimpleNamespace(graph_id="g", data="Mayor Ilse Varga backed the plan.", metadata={}),
                              SimpleNamespace(graph_id="g", data="Mayor Varga withdrew support.", metadata={}),
                              SimpleNamespace(graph_id="g", data="The harbor is calm.", metadata={})])
    e.add_episode("g", "Ilse Varga is a community organizer.", None, {"source": "mirofish_simulation"})
    assert e.source_passages("g", "Ilse Varga") == ["Mayor Ilse Varga backed the plan.", "Mayor Varga withdrew support."]


def test_simulated_facts_are_labelled_only_when_simulated():
    from app.local_graph import _edge
    assert _edge({"uuid": "1", "fact": "A", "attributes": {"origin": "simulation"}}).fact == "[SIMULATED] A"
    assert _edge({"uuid": "2", "fact": "B", "attributes": {"origin": "document"}}).fact == "B"


def test_opening_post_goes_to_named_speaker_before_type_fallback():
    from app.services.simulation_config_generator import AgentActivityConfig, EventConfig, SimulationConfigGenerator
    agents = [AgentActivityConfig(agent_id=i, entity_uuid=str(i), entity_name=n, entity_type=t, influence_weight=w)
              for i, (n, t, w) in enumerate([("Harbor Authority", "Organization", 9.0), ("Water Workers Union", "Organization", 1.0)])]
    gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
    posts = [{"content": "strike", "poster_type": "Union", "poster_name": "water workers union"},
             {"content": "x", "poster_type": "Union", "poster_name": "nobody"}]
    out = gen._assign_initial_post_agents(EventConfig(initial_posts=posts), agents).initial_posts
    assert [p["poster_agent_id"] for p in out] == [1, 0]  # unknown name keeps upstream's fallback


def test_recorded_statements_are_verbatim_and_deduplicated(tmp_path):
    import sqlite3
    from app.services.zep_tools import recorded_agent_statements
    c = sqlite3.connect(tmp_path / "reddit_simulation.db")
    c.executescript("""CREATE TABLE user(user_id INT, agent_id INT);
        CREATE TABLE post(post_id INT, user_id INT, original_post_id INT, content TEXT, quote_content TEXT);
        CREATE TABLE comment(comment_id INT, post_id INT, user_id INT, content TEXT);
        INSERT INTO user VALUES (1, 7), (2, 8);
        INSERT INTO post VALUES (1,1,NULL,'mine',NULL),(2,1,NULL,'mine',NULL),(3,1,9,'copied','my quote'),(4,1,9,'plain repost',NULL),(5,2,NULL,'other',NULL);
        INSERT INTO comment VALUES (1,5,1,'my comment');""")
    c.commit(); c.close()
    assert recorded_agent_statements(str(tmp_path), 7) == ["[reddit] mine", "[reddit] my quote", "[reddit] my comment"]


def test_origin_survives_reconfirmation_and_keeps_first_source(monkeypatch):
    import asyncio
    from app.local_graph import graphiti_engine as ge

    class Edge(SimpleNamespace):
        async def save(self, driver):
            self.saved = True

        async def generate_embedding(self, embedder):
            self.fact_embedding = [0.0]

    async def lookup(driver, uuids):
        return [SimpleNamespace(source_description={"seed": "document", "sim": "mirofish_simulation"}[uuids[0]])]

    monkeypatch.setattr(ge.EpisodicNode, "get_by_uuids", lookup)
    new = Edge(episodes=["now"], attributes={}, fact_embedding=[1.0])
    seed_fact = Edge(episodes=["seed", "now"], attributes={}, fact_embedding=None)  # wiped by re-confirmation
    sim_fact = Edge(episodes=["sim", "now"], attributes={}, fact_embedding=[1.0])
    kept = Edge(episodes=["sim"], attributes={"origin": "document"}, fact_embedding=[1.0])
    asyncio.run(ge.tag_origins(None, None, [new, seed_fact, sim_fact, kept], "now", "mirofish_simulation"))
    assert [e.attributes["origin"] for e in (new, seed_fact, sim_fact, kept)] == ["simulation", "document", "simulation", "document"]
    assert seed_fact.fact_embedding == [0.0] and not hasattr(kept, "saved")
