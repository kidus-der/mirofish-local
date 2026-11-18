#!/usr/bin/env python
"""Score a graph backend on eval/seed.md against the hand-written answers in eval/gold.json.

    cd backend && uv run python ../eval/run_graph_eval.py --backend sqlite --label v1-keyword --no-embed
    cd backend && uv run python ../eval/run_graph_eval.py --backend graphiti --label graphiti

Runs the app's real GraphBuilderService and search client, then writes eval/results/<label>.json.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import netguard  # noqa: E402

netguard.install()

from app.config import Config  # noqa: E402,F401  (loads .env)
from app.local_graph import engine as eng  # noqa: E402
from app.services.graph_builder import GraphBuilderService  # noqa: E402
from app.services.text_processor import TextProcessor  # noqa: E402
from app.utils.zep import get_zep_client  # noqa: E402

sys.path.insert(0, str(ROOT / "eval"))
from score import score  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="sqlite", choices=["sqlite", "graphiti"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--chunk-size", type=int, default=500)
    ap.add_argument("--timeout", type=int, default=14400)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    gold = json.loads((ROOT / "eval/gold.json").read_text())
    text = (ROOT / "eval/seed.md").read_text()

    # Count every LLM and embedding call, whichever client makes it.
    from openai.resources.chat.completions import AsyncCompletions, Completions
    from openai.resources.embeddings import AsyncEmbeddings, Embeddings

    stats = {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "embed_calls": 0}

    def note(r):
        stats["llm_calls"] += 1
        if getattr(r, "usage", None):
            stats["prompt_tokens"] += r.usage.prompt_tokens or 0
            stats["completion_tokens"] += r.usage.completion_tokens or 0
        return r

    sync_c, async_c, sync_e, async_e = Completions.create, AsyncCompletions.create, Embeddings.create, AsyncEmbeddings.create
    Completions.create = lambda s, *x, **k: note(sync_c(s, *x, **k))

    async def ac(s, *x, **k):
        return note(await async_c(s, *x, **k))

    AsyncCompletions.create = ac

    def se(s, *x, **k):
        stats["embed_calls"] += 1
        return sync_e(s, *x, **k)

    async def ae(s, *x, **k):
        stats["embed_calls"] += 1
        return await async_e(s, *x, **k)

    Embeddings.create, AsyncEmbeddings.create = se, ae

    tmp = tempfile.mkdtemp(prefix="mf-eval-")
    no_embed = (lambda t: None) if a.no_embed else None
    if a.backend == "sqlite":
        cls = getattr(eng, "SqliteEngine", eng.Engine)
        e = cls(db_path=f"{tmp}/g.sqlite", embedder=no_embed)
    else:
        from app.local_graph.graphiti_engine import GraphitiEngine
        e = GraphitiEngine(db_path=f"{tmp}/g.sqlite", graph_path=f"{tmp}/falkor.rdb")
    eng.set_engine(e)

    b = GraphBuilderService()
    chunks = TextProcessor.split_text(text, a.chunk_size, 50)
    print(f"{len(chunks)} chunks", flush=True)
    t0 = time.time()
    gid = b.create_graph(a.label)
    b.set_ontology(gid, gold["ontology"])
    sub = b.add_text_batches(gid, chunks)
    last = [0.0]

    def progress(msg, frac):
        if frac - last[0] >= 0.1 or frac >= 1:
            last[0] = frac
            print(f"  {frac:.0%} {time.time()-t0:.0f}s", flush=True)

    error = None
    try:
        b._wait_for_batch(sub, progress_callback=progress, timeout=a.timeout)
    except Exception as ex:  # a partial graph is still worth scoring
        error = str(ex)[:400]
        print("BUILD ERROR:", error, flush=True)
    build_s = time.time() - t0
    data = b.get_graph_data(gid)

    c = get_zep_client()
    rows, t1 = [], time.time()
    for q in gold["queries"]:
        res = c.graph.search(graph_id=gid, query=q["q"], limit=10, scope="edges", reranker="cross_encoder")
        facts = [x.fact for x in res.edges]
        rank = next((i + 1 for i, f in enumerate(facts) if any(k.lower() in f.lower() for k in q["expect"])), None)
        rows.append({"q": q["q"], "rank": rank, "top": facts[:3]})
    search_s = (time.time() - t1) / len(rows)

    m = score(gold, data, rows)
    m.update(label=a.label, note=a.note, chunk_size=a.chunk_size, backend=a.backend, chunks=len(chunks), build_seconds=round(build_s, 1),
             search_seconds_each=round(search_s, 2), build_error=error, model=os.environ.get("LLM_MODEL_NAME"), **stats)
    out = ROOT / "eval/results"
    out.mkdir(exist_ok=True)
    (out / f"{a.label}.json").write_text(json.dumps({"metrics": m, "searches": rows, "graph": data}, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: v for k, v in m.items() if k not in ("extra_nodes", "facts", "temporal")}, indent=1, ensure_ascii=False))
    print("missing facts:", [k for k, v in m["facts"].items() if not v])
    print("extras:", m["extra_nodes"][:30])
    sys.stdout.flush()
    if hasattr(e, "close"):
        e.close()
    os._exit(0)  # daemon workers and embedded servers should not delay exit


if __name__ == "__main__":
    main()
