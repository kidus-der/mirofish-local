#!/usr/bin/env python
"""Drive the REAL MiroFish HTTP API end to end and record every stage.

    cd backend && uv run python ../eval/run_e2e.py --label t1 --max-rounds 3 \
        --requirement "How will residents react to the proposed transit levy?"

Flow (same order as frontend/src/api/*.js and the Step*.vue components, with one forced change):
  ontology -> graph build (poll) -> entities -> create sim -> prepare (poll) -> start -> run (poll)
  -> interviews -> close-env -> pull data/files -> report (poll) -> report chat

Interviews come BEFORE close-env because the sim process only answers IPC while it sits in
wait-for-commands mode, and /report/generate only accepts a completed/stopped run, which needs the
process to have exited. The UI hides this by making the user click through; a script cannot.

Needs a running backend (default http://127.0.0.1:5001). Only stdlib + requests (in backend/.venv).
stages.json is rewritten after every stage start/end, so a crash loses nothing.
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = {"parallel": ["twitter", "reddit"], "twitter": ["twitter"], "reddit": ["reddit"]}
TERMINAL_OK = {"completed", "stopped"}
DEFAULT_QUESTION = (
    "What is your position on the central issue in this discussion, and what has influenced it "
    "most so far? Answer in English, in three sentences or fewer."
)
DEFAULT_CHAT = (
    "In five sentences or fewer: what was the single most important dynamic in this simulation, "
    "and what evidence supports it? Answer in English."
)


def now():
    return datetime.now().isoformat(timespec="seconds")


def trim(o, s=300, n=5):
    """Shrink a payload for stages.json: long strings and long lists are cut, with a count left."""
    if isinstance(o, str):
        return o if len(o) <= s else o[:s] + f"...[+{len(o) - s} chars]"
    if isinstance(o, dict):
        return {k: trim(v, s, n) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        out = [trim(v, s, n) for v in o[:n]]
        return out + ([f"...[+{len(o) - n} items]"] if len(o) > n else [])
    return o


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def entity_type_counts(entities):
    """{custom_label: n} using the backend's own rule: labels other than Entity/Node are types."""
    counts = {}
    for e in entities:
        for lab in {l for l in e.get("labels", []) if l not in ("Entity", "Node")}:
            counts[lab] = counts.get(lab, 0) + 1
    return counts


def agents_for(entities, types):
    """How many entities /prepare would turn into agents for this entity_types filter."""
    ts = set(types)
    return sum(1 for e in entities if ts & {l for l in e.get("labels", []) if l not in ("Entity", "Node")})


def pick_types_for_cap(entities, cap):
    """The API has no agent limit; the only lever is the entity_types filter. Greedily take the
    biggest types whose union stays <= cap. Returns (types, expected_agents, exceeded)."""
    counts = entity_type_counts(entities)
    chosen = []
    for t, _ in sorted(counts.items(), key=lambda kv: -kv[1]):
        if agents_for(entities, chosen + [t]) <= cap:
            chosen.append(t)
    if chosen:
        return chosen, agents_for(entities, chosen), False
    if not counts:
        return [], 0, False
    smallest = min(counts, key=counts.get)  # even the smallest type is over the cap: take it and say so
    return [smallest], counts[smallest], True


class ApiError(Exception):
    def __init__(self, msg, body=None):
        super().__init__(msg)
        self.body = body


class Runner:
    def __init__(self, a):
        self.a = a
        u = urlparse(a.base_url)
        if u.hostname not in ("127.0.0.1", "localhost", "::1"):
            sys.exit(f"refusing non-loopback --base-url {a.base_url} (backend allows Host 127.0.0.1/localhost only)")
        self.base = a.base_url.rstrip("/")
        self.out = Path(a.out)
        if (self.out / "stages.json").exists():
            sys.exit(f"{self.out}/stages.json exists; pick a new --label (nothing was touched)")
        self.out.mkdir(parents=True, exist_ok=True)
        self.s = requests.Session()
        # No Origin header (backend 403s foreign ones). Host comes from the URL (127.0.0.1:5001).
        # Without Accept-Language the backend answers and prompts the LLM in Chinese.
        self.s.headers.update({"Accept-Language": "en"})
        self.plats = PLATFORMS[a.platform]
        self.doc = {"label": a.label, "started_at": now(), "base_url": self.base, "args": vars(a),
                    "ids": {}, "stages": []}
        self.cap = a.max_wait_hours * 3600 if a.max_wait_hours else None
        self.save()

    def save(self):
        write_json(self.out / "stages.json", self.doc)

    def call(self, method, path, timeout=120, **kw):
        r = self.s.request(method, self.base + path, timeout=timeout, **kw)
        try:
            body = r.json()
        except ValueError:
            body = {"success": False, "error": f"non-JSON HTTP {r.status_code}: {r.text[:300]}"}
        if r.status_code >= 400 or not body.get("success", False):
            raise ApiError(f"{method} {path} -> HTTP {r.status_code}: {body.get('error')}", body)
        return body.get("data", body)

    @contextmanager
    def stage(self, name, critical=True):
        rec = {"name": name, "started_at": now(), "status": "running"}
        self.doc["stages"].append(rec)
        self.save()
        t0 = time.time()
        print(f"[{name}] start", flush=True)
        try:
            yield rec
            rec["status"] = "ok"
        except BaseException as e:  # noqa: BLE001 - record then decide
            rec["status"] = "failed"
            rec["error"] = f"{type(e).__name__}: {e}"
            if isinstance(e, ApiError) and e.body:
                rec["error_body"] = trim(e.body)
            print(f"[{name}] FAILED: {rec['error']}", flush=True)
            if critical or not isinstance(e, Exception):
                raise
        finally:
            rec["ended_at"] = now()
            rec["seconds"] = round(time.time() - t0, 1)
            self.save()
            if rec["status"] == "ok":
                print(f"[{name}] ok in {rec['seconds']}s", flush=True)

    def poll(self, name, fn, state_of, desc, every=10):
        """Call fn() until state_of(data) is 'done' (return it) or 'failed' (raise). One progress
        line per 30 s. Transient connection errors are retried (a local backend can stall under load)."""
        t0, last, errs = time.time(), 0.0, 0
        while True:
            try:
                d = fn()
                errs = 0
            except (requests.ConnectionError, requests.Timeout) as e:
                errs += 1
                if errs > 20:
                    raise ApiError(f"[{name}] backend unreachable for 20 polls: {e}")
                time.sleep(15)
                continue
            st = state_of(d)
            if st == "failed":
                raise ApiError(f"[{name}] backend reported failure: {d.get('error') or d.get('message')}", d)
            if st == "done":
                return d
            if time.time() - last >= 30:
                print(f"[{name}] {int(time.time() - t0)}s {desc(d)}", flush=True)
                last = time.time()
            if self.cap and time.time() - t0 > self.cap:
                raise ApiError(f"[{name}] gave up after --max-wait-hours={self.a.max_wait_hours}")
            time.sleep(every)

    def save_out(self, rel, obj):
        write_json(self.out / rel, obj)

    # ------------------------------------------------------------------ stages
    def run(self):
        a, ids = self.a, self.doc["ids"]

        with self.stage("health") as r:
            r["payload"] = self.s.get(self.base + "/health", timeout=10).json()

        with self.stage("ontology") as r:
            files = [("files", (Path(p).name, open(p, "rb"), "text/markdown")) for p in a.seed]
            try:
                d = self.call("POST", "/api/graph/ontology/generate", timeout=3600, files=files,
                              data={"simulation_requirement": a.requirement, "project_name": a.label})
            finally:
                for _, (_, fh, _) in files:
                    fh.close()
            ids["project_id"] = d["project_id"]
            r["payload"] = trim(d)

        with self.stage("graph_build") as r:
            d = self.call("POST", "/api/graph/build", json={"project_id": ids["project_id"], "graph_name": a.label})
            ids["graph_task_id"] = d["task_id"]
            self.save()
            t = self.poll("graph_build", lambda: self.call("GET", f"/api/graph/task/{ids['graph_task_id']}"),
                          lambda x: {"completed": "done", "failed": "failed"}.get(x["status"]),
                          lambda x: f"{x['progress']}% {x['message']}")
            ids["graph_id"] = t["result"]["graph_id"]
            r["payload"] = trim(t)

        entity_types = a.entity_types
        with self.stage("entities") as r:
            ents = self.call("GET", f"/api/simulation/entities/{ids['graph_id']}", timeout=600,
                             params={"enrich": "false"})["entities"]
            counts = entity_type_counts(ents)
            note = None
            if a.max_agents and not entity_types:
                entity_types, expected, exceeded = pick_types_for_cap(ents, a.max_agents)
                note = f"cap {a.max_agents} -> types {entity_types} = {expected} agents" + (
                    " (EXCEEDS cap: smallest type is already bigger)" if exceeded else "")
            elif entity_types:
                expected = agents_for(ents, entity_types)
            else:
                expected = agents_for(ents, list(counts))
            r["payload"] = {"entity_type_counts": counts, "total_agents_if_unfiltered": agents_for(ents, list(counts)),
                            "chosen_entity_types": entity_types, "expected_agents": expected, "note": note}
            print(f"[entities] types={counts} expected_agents={expected} {note or ''}", flush=True)
            if expected == 0:
                raise ApiError("no entities would become agents; graph extraction produced nothing usable")

        with self.stage("create_simulation") as r:
            d = self.call("POST", "/api/simulation/create", json={
                "project_id": ids["project_id"], "graph_id": ids["graph_id"],
                "enable_twitter": "twitter" in self.plats, "enable_reddit": "reddit" in self.plats})
            ids["simulation_id"] = d["simulation_id"]
            r["payload"] = trim(d)

        sim = ids["simulation_id"]
        with self.stage("prepare") as r:
            body = {"simulation_id": sim, "use_llm_for_profiles": True, "parallel_profile_count": a.profile_parallel}
            if entity_types:
                body["entity_types"] = entity_types
            d = self.call("POST", "/api/simulation/prepare", timeout=600, json=body)
            r["payload"] = trim(d)
            if not d.get("already_prepared"):
                ids["prepare_task_id"] = d["task_id"]
                self.save()
                # task_id only: with simulation_id the backend short-circuits to "ready" as soon as files
                # exist, and for single-platform runs it can never say ready (it demands both profile files).
                t = self.poll("prepare", lambda: self.call("POST", "/api/simulation/prepare/status",
                                                           json={"task_id": ids["prepare_task_id"]}),
                              lambda x: {"completed": "done", "failed": "failed"}.get(x["status"]),
                              lambda x: f"{x['progress']}% {x['message']}")
                r["result"] = trim(t)

        with self.stage("start") as r:
            body = {"simulation_id": sim, "platform": a.platform, "force": False,
                    "enable_graph_memory_update": a.graph_memory}
            if a.max_rounds:
                body["max_rounds"] = a.max_rounds
            r["payload"] = trim(self.call("POST", "/api/simulation/start", json=body))

        def run_done(x):
            if x["runner_status"] == "failed":
                return "failed"
            if x["runner_status"] in TERMINAL_OK or all(x.get(f"{p}_completed") for p in self.plats):
                return "done"

        with self.stage("simulation_run") as r:
            d = self.poll("simulation_run", lambda: self.call("GET", f"/api/simulation/{sim}/run-status"), run_done,
                          lambda x: f"{x['runner_status']} round {x['current_round']}/{x['total_rounds']} "
                                    f"actions tw={x['twitter_actions_count']} rd={x['reddit_actions_count']}")
            r["payload"] = trim(d)

        with self.stage("interviews", critical=False) as r:
            r["payload"] = self.interviews(sim)

        with self.stage("close_env") as r:
            try:
                r["payload"] = trim(self.call("POST", "/api/simulation/close-env", timeout=120,
                                              json={"simulation_id": sim, "timeout": 60}))
            except ApiError as e:
                r["close_env_error"] = str(e)
                print("[close_env] failed, falling back to /stop", flush=True)
                r["stop_payload"] = trim(self.call("POST", "/api/simulation/stop", timeout=300,
                                                   json={"simulation_id": sim}))
            d = self.poll("close_env", lambda: self.call("GET", f"/api/simulation/{sim}/run-status"),
                          lambda x: "failed" if x["runner_status"] == "failed"
                          else "done" if x["runner_status"] in TERMINAL_OK else None,
                          lambda x: x["runner_status"])
            r["final_status"] = d["runner_status"]

        with self.stage("pull_data", critical=False) as r:
            r["payload"] = self.pull(sim, ids["graph_id"])

        with self.stage("copy_files", critical=False) as r:
            r["payload"] = self.copy_files(sim)

        with self.stage("report_generate") as r:
            d = self.call("POST", "/api/report/generate", json={"simulation_id": sim})
            r["payload"] = trim(d)
            ids["report_id"] = d.get("report_id")
            if not d.get("already_generated"):
                ids["report_task_id"] = d["task_id"]
                self.save()
                self.poll("report", lambda: self.call("POST", "/api/report/generate/status",
                                                      json={"task_id": ids["report_task_id"]}),
                          lambda x: {"completed": "done", "failed": "failed"}.get(x["status"]),
                          lambda x: f"{x['progress']}% {x['message']}", every=15)

        with self.stage("report_fetch") as r:
            rep = self.call("GET", f"/api/report/{ids['report_id']}")
            self.save_out("report.json", rep)
            (self.out / "report.md").write_text(rep.get("markdown_content") or "", encoding="utf-8")
            r["payload"] = {"status": rep.get("status"), "markdown_chars": len(rep.get("markdown_content") or "")}

        with self.stage("report_chat", critical=False) as r:
            d = self.call("POST", "/api/report/chat", timeout=3600,
                          json={"simulation_id": sim, "message": a.chat_question})
            self.save_out("report_chat.json", {"question": a.chat_question, **d})
            r["payload"] = trim(d)

        self.doc["finished_at"] = now()
        self.save()
        print(f"done. results in {self.out}", flush=True)

    def interviews(self, sim):
        a = self.a
        self.poll("env", lambda: self.call("POST", "/api/simulation/env-status", json={"simulation_id": sim}),
                  lambda x: "done" if x["env_alive"] else None, lambda x: "waiting for env to enter command mode",
                  every=5)
        cfg = self.call("GET", f"/api/simulation/{sim}/config")
        agent_ids = [c["agent_id"] for c in cfg.get("agent_configs", [])]
        picks = list(dict.fromkeys(agent_ids[:1] + agent_ids[len(agent_ids) // 2:][:1]))
        platform = self.plats[-1]  # one platform only: with none given the backend asks both = 2 LLM calls
        out = []
        for aid in picks:
            try:
                d = self.call("POST", "/api/simulation/interview", timeout=a.interview_timeout + 60,
                              json={"simulation_id": sim, "agent_id": aid, "prompt": a.interview_question,
                                    "platform": platform, "timeout": a.interview_timeout})
                rec = {"agent_id": aid, "platform": platform, "question": a.interview_question, "response": d}
            except ApiError as e:
                rec = {"agent_id": aid, "platform": platform, "error": str(e), "body": trim(e.body)}
            self.save_out(f"interview_agent_{aid}.json", rec)
            out.append(trim(rec))
        return out

    def pull(self, sim, gid):
        got = {}
        self.save_out("graph.json", self.call("GET", f"/api/graph/data/{gid}", timeout=600))
        self.save_out("simulation_config.json", self.call("GET", f"/api/simulation/{sim}/config"))
        for p in self.plats:
            prof = self.call("GET", f"/api/simulation/{sim}/profiles", params={"platform": p})
            self.save_out(f"profiles_{p}.json", prof)
            got[f"profiles_{p}"] = prof.get("count")
            got[f"actions_{p}"] = self.paged(sim, "actions", "actions", p, limit=1000)
            got[f"posts_{p}"] = self.paged(sim, "posts", "posts", p, limit=500)
            got[f"comments_{p}"] = self.paged(sim, "comments", "comments", p, limit=500)
        return got

    def paged(self, sim, endpoint, key, platform, limit):
        items, off = [], 0
        while True:
            d = self.call("GET", f"/api/simulation/{sim}/{endpoint}", timeout=300,
                          params={"platform": platform, "limit": limit, "offset": off})
            page = d.get(key, [])
            items += page
            off += limit
            if len(page) < limit:
                break
        self.save_out(f"{endpoint}_{platform}.json", items)
        return len(items)

    def copy_files(self, sim):
        src = Path(self.a.sim_root) / sim
        done = []
        for p in self.plats:
            db = src / f"{p}_simulation.db"
            if db.exists():  # backup API is safe even if something still holds the file
                s, d = sqlite3.connect(f"file:{db}?mode=ro", uri=True), sqlite3.connect(self.out / db.name)
                s.backup(d)
                s.close()
                d.close()
                done.append(db.name)
            log = src / p / "actions.jsonl"
            if log.exists():
                shutil.copy2(log, self.out / f"{p}_actions.jsonl")
                done.append(f"{p}_actions.jsonl")
        for extra in ("actions.jsonl", "simulation.log", "state.json", "run_state.json"):
            if (src / extra).exists():
                shutil.copy2(src / extra, self.out / extra)
                done.append(extra)
        if not done:
            raise FileNotFoundError(f"nothing found under {src}")
        return done


def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", nargs="+", default=[str(ROOT / "eval" / "seed.md")], help="documents to upload (pdf/md/txt)")
    ap.add_argument("--requirement", required=True, help="simulation requirement (what to predict)")
    ap.add_argument("--max-rounds", type=int, default=None, help="real cap: sent to /simulation/start, truncates the run")
    ap.add_argument("--max-agents", type=int, default=None,
                    help="NO API LIMIT EXISTS. Emulated: picks whole entity types (biggest first) whose agent "
                         "total stays <= N. Type-granular, so the result can be well under N.")
    ap.add_argument("--entity-types", nargs="+", default=None, help="explicit entity_types filter for /prepare (wins over --max-agents)")
    ap.add_argument("--platform", choices=list(PLATFORMS), default="parallel")
    ap.add_argument("--label", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--out", default=None, help="default eval/results/e2e-<label>/")
    ap.add_argument("--base-url", default="http://127.0.0.1:5001")
    ap.add_argument("--sim-root", default=str(ROOT / "backend" / "uploads" / "simulations"))
    ap.add_argument("--profile-parallel", type=int, default=2, help="parallel_profile_count for /prepare (UI uses 5)")
    ap.add_argument("--graph-memory", action="store_true", help="enable_graph_memory_update (UI turns it on; off here: extra LLM load)")
    ap.add_argument("--max-wait-hours", type=float, default=12, help="per polled stage; 0 = no limit")
    ap.add_argument("--interview-timeout", type=int, default=900)
    ap.add_argument("--interview-question", default=DEFAULT_QUESTION)
    ap.add_argument("--chat-question", default=DEFAULT_CHAT)
    a = ap.parse_args(argv)
    a.out = a.out or str(ROOT / "eval" / "results" / f"e2e-{a.label}")
    for p in a.seed:
        if not Path(p).is_file():
            ap.error(f"seed not found: {p}")
    return a


if __name__ == "__main__":
    r = Runner(parse())
    try:
        r.run()
    except (ApiError, requests.RequestException, KeyError, FileNotFoundError) as e:
        r.doc["aborted"] = f"{type(e).__name__}: {e}"
        r.save()
        sys.exit(f"STOPPED: {e}\nstages.json in {r.out} shows how far it got (ids are in 'ids').")
