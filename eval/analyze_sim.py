#!/usr/bin/env python
"""Metrics for one simulation run directory written by run_e2e.py (or any dir holding the same files).

    cd backend && uv run python ../eval/analyze_sim.py ../eval/results/e2e-t1
    cd backend && uv run python ../eval/analyze_sim.py ../eval/results/e2e-t1 --stance --target "the transit levy"
    cd backend && uv run python ../eval/analyze_sim.py --self-test

Reads, per platform p in {twitter, reddit}:
  <p>_simulation.db   OASIS SQLite. Tables used: user, post, comment, trace, like, dislike, follow
                      (schema: backend/.venv/.../oasis/social_platform/schema/*.sql)
  <p>_actions.jsonl   MiroFish log (backend/scripts/action_logger.py): lines with `event_type`
                      (round_start/round_end/simulation_*) or actions {round, agent_id, action_type, action_args}.
                      Only used for round numbers (the DB has none) and as a cross-check of the action mix.
Writes <out>/metrics.json. Every metric carries its n and tolerates empty data.
--stance is the only thing that touches the network (the LLM at LLM_BASE_URL, loopback only).
"""

import argparse
import hashlib
import json
import math
import random
import re
import sqlite3
import statistics
import sys
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("twitter", "reddit")
IGNORED = {"sign_up", "interview", "update_rec_table", "exit"}  # bookkeeping, not agent behaviour
PASSIVE = {"do_nothing", "refresh"}  # excluded from "activity" (Gini), kept in the mix
LABELS = ("support", "oppose", "neutral")
MAX_PAIR_ITEMS = 4000  # shortcut: above this, pairwise Jaccard runs on a seeded sample; raise if you have the minutes


# ------------------------------------------------------------------ small pure helpers
def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def dist(vals):
    v = sorted(vals)
    if not v:
        return {"n": 0, "mean": None, "median": None, "p10": None, "p90": None, "min": None, "max": None, "std": None}
    return {"n": len(v), "mean": statistics.fmean(v), "median": pct(v, 0.5), "p10": pct(v, 0.1), "p90": pct(v, 0.9),
            "min": v[0], "max": v[-1], "std": statistics.pstdev(v)}


def gini(vals):
    v = sorted(vals)
    n, s = len(v), sum(v)
    if n == 0 or s == 0:
        return None
    return 2 * sum(i * x for i, x in enumerate(v, 1)) / (n * s) - (n + 1) / n


def entropy(labels):
    c, n = Counter(labels), len(labels)
    return -sum(k / n * math.log2(k / n) for k in c.values()) if n else None


def tokens(text):
    return re.findall(r"\w+", (text or "").lower())


def jaccard(a, b):
    u = len(a | b)
    return len(a & b) / u if u else None


def share(k, n):
    return k / n if n else None


# ------------------------------------------------------------------ loading
def q(conn, sql, args=()):
    try:
        return conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError:  # table missing (e.g. a DB that never got past setup)
        return []


def load_platform(out, p):
    """Raw rows for one platform. Missing files give empty lists, never an exception."""
    d = {"platform": p, "db": False, "users": [], "posts": [], "comments": [], "trace": [], "likes": [],
         "dislikes": [], "follows": [], "log": []}
    db = Path(out) / f"{p}_simulation.db"
    if db.exists():
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        d["db"] = True
        d["users"] = q(c, "SELECT user_id, agent_id, user_name, name FROM user")
        d["posts"] = q(c, "SELECT post_id, user_id, original_post_id, content, quote_content FROM post ORDER BY post_id")
        d["comments"] = q(c, "SELECT comment_id, post_id, user_id, content FROM comment ORDER BY comment_id")
        d["trace"] = q(c, "SELECT user_id, action, info FROM trace ORDER BY rowid")
        d["likes"] = q(c, "SELECT user_id, post_id FROM like")
        d["dislikes"] = q(c, "SELECT user_id, post_id FROM dislike")
        d["follows"] = q(c, "SELECT follower_id, followee_id FROM follow")
        c.close()
    for cand in (Path(out) / f"{p}_actions.jsonl", Path(out) / p / "actions.jsonl"):
        if cand.exists():
            for line in cand.read_text(encoding="utf-8").splitlines():
                try:
                    d["log"].append(json.loads(line))
                except ValueError:
                    pass  # a line cut short by a crash
            break
    return d


# ------------------------------------------------------------------ metrics
def action_mix(actions):
    c = Counter(a for a in actions if a not in IGNORED)
    n = sum(c.values())
    return {"n": n, "counts": dict(c), "shares": {k: v / n for k, v in c.items()} if n else {},
            "do_nothing_share": share(c.get("do_nothing", 0), n)}


def log_action_mix(entries):
    """Same mix from actions.jsonl (upper-case names, no refresh/sign_up: the logger filters them)."""
    return action_mix(e["action_type"].lower() for e in entries if "action_type" in e)


def authored(P):
    """Content-bearing items: original posts, quote posts (quote_content) -> (agent, text, kind, key)."""
    out = []
    for pid, uid, orig, content, quote in P["posts"]:
        if orig is None and content:
            out.append((uid, content, "post", f"post:{pid}"))
        elif orig is not None and quote:
            out.append((uid, quote, "quote", f"post:{pid}"))
    return out


def activity(P):
    acts = Counter(uid for uid, a, _ in P["trace"] if a not in IGNORED and a not in PASSIVE)
    ids = sorted({u[0] for u in P["users"]})
    per = [acts.get(i, 0) for i in ids]
    posts = Counter(a for a, _, _, _ in authored(P))
    pp = [posts.get(i, 0) for i in ids]
    return {"n_agents": len(ids),
            "activity": {"definition": "per agent: actions other than do_nothing/refresh (incl. likes, follows)",
                         "n": len(per), "gini": gini(per), "dist": dist(per)},
            "posts_per_agent": {"definition": "original posts + quote posts (reposts carry no text)", "n": len(pp),
                                "gini": gini(pp), "zero_share": share(sum(1 for x in pp if x == 0), len(pp)), "dist": dist(pp)}}


def repetition(items, thr=0.6):
    """items: [(agent, text)]. Jaccard on lower-cased word sets."""
    items = [(a, t) for a, t in items if tokens(t)]
    n_all = len(items)
    sampled = n_all > MAX_PAIR_ITEMS
    work = random.Random(0).sample(items, MAX_PAIR_ITEMS) if sampled else items
    sets = [frozenset(tokens(t)) for _, t in work]
    w_n = w_hit = x_n = x_hit = 0
    for i, j in combinations(range(len(work)), 2):
        s = jaccard(sets[i], sets[j])
        if work[i][0] == work[j][0]:
            w_n += 1
            w_hit += s >= thr
        else:
            x_n += 1
            x_hit += s >= thr
    norm = Counter(" ".join(tokens(t)) for _, t in items)
    extra = sum(v - 1 for v in norm.values())
    toks = [w for _, t in items for w in tokens(t)]
    return {"n": n_all, "threshold": thr, "pairs_sampled": sampled, "pairs_items": len(work),
            "within_agent": {"n_pairs": w_n, "similar_pairs": w_hit, "share": share(w_hit, w_n)},
            "across_agents": {"n_pairs": x_n, "similar_pairs": x_hit, "share": share(x_hit, x_n)},
            "exact_duplicates": {"extra_copies": extra, "share": share(extra, n_all),
                                 "groups": sum(1 for v in norm.values() if v > 1)},
            "distinct_unigram_ratio": {"n_tokens": len(toks), "value": share(len(set(toks)), len(toks))}}


def lengths(texts):
    return {"chars": dist([len(t) for t in texts]), "words": dist([len(tokens(t)) for t in texts])}


def like_dislike(actions):
    c = Counter(actions)
    out = {}
    for what, l, d in (("posts", "like_post", "dislike_post"), ("comments", "like_comment", "dislike_comment")):
        out[what] = {"likes": c[l], "dislikes": c[d], "n": c[l] + c[d], "like_to_dislike": share(c[l], c[d])}
    both = {"likes": c["like_post"] + c["like_comment"], "dislikes": c["dislike_post"] + c["dislike_comment"]}
    out["all"] = {**both, "n": both["likes"] + both["dislikes"], "like_to_dislike": share(both["likes"], both["dislikes"])}
    return out


def cascades(P):
    """Roots = posts that are not reposts/quotes. Children of a node = reposts/quotes of it + comments on it
    (OASIS comments are flat: no comment-on-comment, so a comment is always a leaf one level down)."""
    ids = {r[0] for r in P["posts"]}
    kids, roots = defaultdict(list), []
    for pid, _, orig, _, _ in P["posts"]:
        if orig is None or orig not in ids:
            roots.append(pid)
        else:
            kids[orig].append(("post", pid))
    for cid, pid, _, _ in P["comments"]:
        kids[pid].append(("comment", cid))
    stats = []
    for r in roots:
        level, seen, depth, size, width = [("post", r)], {("post", r)}, 0, 0, 0
        while True:
            nxt = []
            for kind, i in level:
                if kind == "post":
                    nxt += [k for k in kids.get(i, []) if k not in seen]
            seen.update(nxt)
            if not nxt:
                break
            depth, size, width = depth + 1, size + len(nxt), max(width, len(nxt))
            level = nxt
        stats.append({"root": r, "size": size, "depth": depth, "breadth": width,
                      "direct": len(kids.get(r, []))})
    eng = [s for s in stats if s["size"] > 0]
    return {"n_roots": len(stats), "n_engaged": len(eng), "engaged_share": share(len(eng), len(stats)),
            "size": dist([s["size"] for s in eng]), "depth": dist([s["depth"] for s in eng]),
            "breadth": dist([s["breadth"] for s in eng]), "direct_children": dist([s["direct"] for s in eng]),
            "depth_hist": dict(Counter(s["depth"] for s in eng)),
            "top": sorted(eng, key=lambda s: -s["size"])[:5],
            "note": "breadth = widest level of the cascade; depth counts repost/quote chains, comments are depth+1 leaves"}


# ------------------------------------------------------------------ stance
def round_maps(entries):
    """actions.jsonl -> where each DB row came from. Posts/comments carry ids in action_args except the
    seed posts (round 0), which only carry content, hence the (agent, content) fallback."""
    by_post, by_comment, by_content = {}, {}, {}
    for e in entries:
        t, a, r = e.get("action_type"), e.get("action_args") or {}, e.get("round")
        if t is None or r is None:
            continue
        if t == "CREATE_POST":
            if a.get("post_id") is not None:
                by_post[a["post_id"]] = r
            by_content.setdefault((e.get("agent_id"), a.get("content")), r)
        elif t in ("REPOST", "QUOTE_POST") and a.get("new_post_id") is not None:
            by_post[a["new_post_id"]] = r
        elif t == "CREATE_COMMENT" and a.get("comment_id") is not None:
            by_comment[a["comment_id"]] = r
    return by_post, by_comment, by_content


def collect(P):
    """Text items to label and the interactions between agents. Keys: 'post:<id>' / 'comment:<id>'."""
    by_post, by_comment, by_content = round_maps(P["log"])
    items, inter = {}, []
    pid_author = {r[0]: r[1] for r in P["posts"]}
    for uid, text, kind, key in authored(P):
        pid = int(key.split(":")[1])
        rnd = by_post.get(pid, by_content.get((uid, text)))
        items[key] = {"key": key, "kind": kind, "agent": uid, "text": text, "round": rnd}
    for pid, uid, orig, content, quote in P["posts"]:
        if orig is None:
            continue
        kind = "quote" if quote else "repost"
        inter.append({"kind": kind, "actor": uid, "target": f"post:{orig}", "actor_key": f"post:{pid}" if quote else None})
    for cid, pid, uid, content in P["comments"]:
        if content:
            key = f"comment:{cid}"
            items[key] = {"key": key, "kind": "comment", "agent": uid, "text": content, "round": by_comment.get(cid)}
            inter.append({"kind": "comment", "actor": uid, "target": f"post:{pid}", "actor_key": key})
    inter += [{"kind": "like", "actor": u, "target": f"post:{p}", "actor_key": None} for u, p in P["likes"]]
    inter += [{"kind": "dislike", "actor": u, "target": f"post:{p}", "actor_key": None} for u, p in P["dislikes"]]
    for it in inter:  # target author, to drop self-interactions
        it["target_author"] = pid_author.get(int(it["target"].split(":")[1]))
    return items, inter


def stance_metrics(items, inter, labels):
    """labels: {item_key: support|oppose|neutral|None}."""
    lab = {k: labels.get(k) for k in items}
    ok = {k: v for k, v in lab.items() if v in LABELS}
    # per round entropy
    rounds = defaultdict(list)
    for k, v in ok.items():
        rounds[items[k]["round"]].append(v)
    per_round = [{"round": r, "n": len(v), "entropy_bits": entropy(v), "shares": {s: v.count(s) / len(v) for s in LABELS}}
                 for r, v in sorted(rounds.items(), key=lambda kv: (kv[0] is None, kv[0]))]
    ents = [r["entropy_bits"] for r in per_round if r["round"] is not None]
    # flips: first vs last labelled item per agent, in round order
    by_agent = defaultdict(list)
    for k, v in ok.items():
        it = items[k]
        by_agent[it["agent"]].append(((it["round"] if it["round"] is not None else 10**9, int(k.split(":")[1])), v))
    seq = {a: [v for _, v in sorted(x)] for a, x in by_agent.items()}
    elig = {a: s for a, s in seq.items() if len(s) >= 2}
    flipped = sum(s[0] != s[-1] for s in elig.values())
    reversed_ = sum({s[0], s[-1]} == {"support", "oppose"} for s in elig.values())
    # same-stance interactions; non-text interactions use the actor's modal stance (ties: most recent)
    modal = {}
    for a, s in seq.items():
        c = Counter(s)
        top = max(c.values())
        modal[a] = next(v for v in reversed(s) if c[v] == top)
    kinds = defaultdict(lambda: [0, 0, 0, 0])  # n, same, n_nonneutral, same_nonneutral
    skipped = 0
    for it in inter:
        if it["actor"] == it["target_author"]:
            continue
        a = ok.get(it["actor_key"]) if it["actor_key"] else modal.get(it["actor"])
        t = ok.get(it["target"])
        if a is None or t is None:
            skipped += 1
            continue
        for key in (it["kind"], "all"):
            r = kinds[key]
            r[0] += 1
            r[1] += a == t
            if a != "neutral" and t != "neutral":
                r[2] += 1
                r[3] += a == t
    inter_out = {k: {"n": r[0], "same_stance_share": share(r[1], r[0]), "n_nonneutral": r[2],
                     "same_stance_share_nonneutral": share(r[3], r[2])} for k, r in kinds.items()}
    if "all" not in inter_out:
        inter_out["all"] = {"n": 0, "same_stance_share": None, "n_nonneutral": 0, "same_stance_share_nonneutral": None}
    return {"n_items": len(items), "n_labelled": len(ok), "n_unlabelled": len(items) - len(ok),
            "n_without_round": sum(1 for k in ok if items[k]["round"] is None),
            "overall_shares": {s: share(list(ok.values()).count(s), len(ok)) for s in LABELS},
            "entropy_per_round": per_round, "mean_entropy_bits": statistics.fmean(ents) if ents else None,
            "flips": {"n_agents_eligible": len(elig), "definition": "agents with >=2 labelled items; first vs last in round order",
                      "flipped_share": share(flipped, len(elig)), "polarity_reversal_share": share(reversed_, len(elig))},
            "same_stance_interactions": {"n_skipped_unlabelled": skipped, **inter_out}}


def parse_label(raw):
    try:
        v = json.loads(raw)["label"]
    except (ValueError, KeyError, TypeError):
        return None
    v = str(v).strip().lower()
    return v if v in LABELS else None


def read_env(path):
    env = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*)", line)
            if m and not line.lstrip().startswith("#"):
                env[m[1]] = re.sub(r"\s+#.*$", "", m[2]).strip().strip("\"'")
    return env


def llm_labeler(env, target):
    base, model = env.get("LLM_BASE_URL"), env.get("LLM_MODEL_NAME")
    if not base or not model:
        sys.exit("LLM_BASE_URL / LLM_MODEL_NAME not found in .env")
    if urlparse(base).hostname not in ("127.0.0.1", "localhost", "::1"):
        sys.exit(f"refusing non-loopback LLM_BASE_URL {base}")
    system = ("You label the stance of a social media message toward a target. Reply with ONLY a JSON object "
              '{"label": "support" | "oppose" | "neutral"}. support = agrees with, favours or defends the target; '
              "oppose = disagrees with, criticises or rejects it; neutral = no discernible stance, unrelated, or purely informational.")

    def label(text):
        body = {"model": model, "temperature": 0, "max_tokens": 40, "reasoning_effort": "none",
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": f"Target: {target}\nMessage: {text}"}]}
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "Authorization": f"Bearer {env.get('LLM_API_KEY', 'x')}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return parse_label(json.load(r)["choices"][0]["message"]["content"])

    return label, model


def label_items(items, target, cache_path, labeler, model):
    """Cached by sha1(model, target, text); saved every 20 new labels so an interrupted run resumes."""
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    keyof = lambda t: hashlib.sha1(f"{model}\x00{target}\x00{t}".encode()).hexdigest()
    todo = sorted({it["text"] for it in items.values() if keyof(it["text"]) not in cache})
    t0 = last = time.time()
    fails = 0
    for n, text in enumerate(todo, 1):
        try:
            cache[keyof(text)] = {"label": labeler(text), "target": target, "model": model}
            fails = 0
        except Exception as e:  # noqa: BLE001 - network/parse; do not cache failures
            fails += 1
            if fails >= 3:
                cache_path.write_text(json.dumps(cache))
                sys.exit(f"stance: 3 LLM failures in a row ({e}); {len(cache)} labels cached, rerun to resume")
        if n % 20 == 0:
            cache_path.write_text(json.dumps(cache))
        if time.time() - last >= 30:
            print(f"[stance] {n}/{len(todo)} labelled, {int(time.time() - t0)}s", flush=True)
            last = time.time()
    cache_path.write_text(json.dumps(cache))
    return {k: (cache.get(keyof(it["text"])) or {}).get("label") for k, it in items.items()}, len(todo)


# ------------------------------------------------------------------ driver
def analyze(out, stance=None):
    """stance: None, or (target, labeler, model) to enable the LLM-backed metrics."""
    out = Path(out)
    res = {"meta": {"out_dir": str(out), "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "similarity_threshold": 0.6, "ignored_actions": sorted(IGNORED)}, "platforms": {}}
    for p in PLATFORMS:
        P = load_platform(out, p)
        if not P["db"] and not P["log"]:
            continue
        acts = [a for _, a, _ in P["trace"]]
        texts = authored(P)
        comments = [(u, c) for _, _, u, c in P["comments"] if c]
        m = {"has_db": P["db"], "has_actions_log": bool(P["log"]), "action_mix": action_mix(acts),
             "action_mix_from_actions_jsonl": log_action_mix(P["log"]), **activity(P),
             "repetition": {"posts": repetition([(a, t) for a, t, _, _ in texts]), "comments": repetition(comments)},
             "length": {"posts": lengths([t for _, t, _, _ in texts]), "comments": lengths([c for _, c in comments])},
             "like_to_dislike": like_dislike(acts), "cascades": cascades(P),
             "follows": {"n": len(P["follows"])}}
        if stance:
            target, labeler, model = stance
            items, inter = collect(P)
            labels, n_new = label_items(items, target, out / "stance_labels.json", labeler, model)
            m["stance"] = {"target": target, "model": model, "new_llm_calls": n_new, **stance_metrics(items, inter, labels)}
        res["platforms"][p] = m
    if not res["platforms"]:
        res["meta"]["warning"] = "no <platform>_simulation.db or <platform>_actions.jsonl found"
    (out / "metrics.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


# ------------------------------------------------------------------ self-test
def find_schema():
    import importlib.util
    spec = importlib.util.find_spec("oasis")
    d = Path(spec.submodule_search_locations[0]) / "social_platform" / "schema" if spec else None
    return d if d and d.is_dir() else None


def build_fixture(out):
    """A 4-agent reddit-shaped run created from OASIS's real schema files (so table/column names are proven)."""
    schema = find_schema()
    if not schema:
        sys.exit("self-test needs the oasis package (run from backend/ with `uv run`)")
    c = sqlite3.connect(Path(out) / "reddit_simulation.db")
    for f in sorted(schema.glob("*.sql")):
        c.executescript(f.read_text())
    c.executemany("INSERT INTO user (user_id, agent_id, user_name, name) VALUES (?,?,?,?)", [(i, i, f"u{i}", f"U{i}") for i in range(4)])
    A, B, C = "The levy is a great idea for transit funding", "I think the levy is terrible and costly", "totally agree it is terrible"
    c.executemany("INSERT INTO post (post_id, user_id, original_post_id, content, quote_content) VALUES (?,?,?,?,?)", [
        (1, 0, None, A, None), (2, 1, None, A, None), (3, 0, None, B, None), (4, 2, 1, "", None),
        (5, 3, 3, B, C), (6, 1, 5, "", None)])
    c.executemany("INSERT INTO comment (comment_id, post_id, user_id, content) VALUES (?,?,?,?)", [(1, 1, 2, "support this"), (2, 1, 3, "no way")])
    c.executemany("INSERT INTO like (user_id, post_id) VALUES (?,?)", [(2, 1), (3, 1), (1, 3)])
    c.executemany("INSERT INTO dislike (user_id, post_id) VALUES (?,?)", [(0, 5)])
    tr = [(i, "sign_up") for i in range(4)] + [(0, "create_post"), (0, "create_post"), (1, "create_post"), (1, "repost"),
          (2, "repost"), (2, "create_comment"), (2, "like_post"), (3, "quote_post"), (3, "create_comment"), (3, "like_post"),
          (1, "like_post"), (0, "dislike_post"), (0, "do_nothing"), (3, "do_nothing"), (0, "refresh"), (1, "refresh"), (0, "interview")]
    c.executemany("INSERT INTO trace (user_id, created_at, action, info) VALUES (?,?,?,?)", [(u, i, a, "{}") for i, (u, a) in enumerate(tr)])
    c.commit()
    c.close()
    ev = lambda r, aid, t, **a: {"round": r, "agent_id": aid, "agent_name": f"U{aid}", "action_type": t, "action_args": a}
    log = [{"event_type": "simulation_start"}, ev(0, 0, "CREATE_POST", content=A), {"event_type": "round_start", "round": 1},
           ev(1, 1, "CREATE_POST", content=A, post_id=2), ev(1, 0, "CREATE_POST", content=B, post_id=3), ev(1, 1, "DO_NOTHING"),
           ev(2, 3, "QUOTE_POST", quoted_id=3, new_post_id=5), ev(2, 2, "CREATE_COMMENT", content="support this", comment_id=1),
           ev(3, 3, "CREATE_COMMENT", content="no way", comment_id=2), ev(3, 0, "INTERVIEW", prompt="x"),
           {"event_type": "simulation_end"}]
    (Path(out) / "reddit_actions.jsonl").write_text("\n".join(json.dumps(x) for x in log) + "\n")
    return {A: "support", B: "oppose", C: "oppose", "support this": "support", "no way": "oppose"}


def self_test():
    ap = lambda a, b, tol=1e-9: abs(a - b) <= tol
    assert gini([1, 1, 1, 5]) == 0.375 and gini([]) is None and gini([0, 0]) is None and ap(gini([2, 2, 2]), 0)
    assert ap(entropy(["a", "b"]), 1.0) and entropy([]) is None
    assert parse_label('{"label": " Support "}') == "support" and parse_label("nope") is None and parse_label('{"label":"maybe"}') is None
    assert read_env_text("LLM_BASE_URL=http://127.0.0.1:11435/v1   # inline\n# X=1\nLLM_MODEL_NAME='m'\n") == {
        "LLM_BASE_URL": "http://127.0.0.1:11435/v1", "LLM_MODEL_NAME": "m"}

    with tempfile.TemporaryDirectory() as td:
        empty = Path(td) / "empty"
        empty.mkdir()
        assert analyze(empty)["meta"]["warning"]  # nothing there: no crash
        (empty / "twitter_actions.jsonl").write_text('garbage\n{"event_type": "simulation_end"}\n')  # torn line is skipped
        assert analyze(empty)["platforms"]["twitter"]["action_mix"]["n"] == 0

        out = Path(td) / "run"
        out.mkdir()
        gold = build_fixture(out)
        calls = []
        res = analyze(out, stance=("the transit levy", lambda t: calls.append(t) or gold[t], "fake-model"))
        m = res["platforms"]["reddit"]
        assert "twitter" not in res["platforms"]

        mix = m["action_mix"]  # 16 behaviour rows; sign_up x4 and interview ignored
        assert mix["n"] == 16 and mix["counts"]["create_post"] == 3 and mix["counts"]["like_post"] == 3
        assert ap(mix["do_nothing_share"], 2 / 16)
        jm = m["action_mix_from_actions_jsonl"]  # event lines skipped, INTERVIEW ignored
        assert jm["n"] == 7 and jm["counts"]["do_nothing"] == 1

        assert m["n_agents"] == 4 and ap(m["activity"]["gini"], 0.0) and m["activity"]["dist"]["mean"] == 3
        pp = m["posts_per_agent"]
        assert pp["dist"]["max"] == 2 and ap(pp["dist"]["mean"], 1.0) and ap(pp["zero_share"], 0.25) and ap(pp["gini"], 0.375)

        r = m["repetition"]["posts"]
        assert r["n"] == 4 and r["within_agent"]["n_pairs"] == 1 and r["within_agent"]["similar_pairs"] == 0
        assert r["across_agents"]["n_pairs"] == 5 and ap(r["across_agents"]["share"], 0.2)
        assert r["exact_duplicates"]["extra_copies"] == 1 and ap(r["exact_duplicates"]["share"], 0.25)
        assert r["exact_duplicates"]["groups"] == 1
        assert r["distinct_unigram_ratio"]["n_tokens"] == 31 and ap(r["distinct_unigram_ratio"]["value"], 17 / 31)
        assert m["length"]["posts"]["words"]["median"] == 8.5 and ap(m["length"]["posts"]["words"]["mean"], 7.75)
        assert m["repetition"]["comments"]["n"] == 2 and m["length"]["comments"]["chars"]["n"] == 2

        ld = m["like_to_dislike"]["posts"]
        assert ld["likes"] == 3 and ld["dislikes"] == 1 and ld["like_to_dislike"] == 3.0
        assert m["like_to_dislike"]["comments"]["like_to_dislike"] is None and m["like_to_dislike"]["comments"]["n"] == 0

        c = m["cascades"]  # roots 1,2,3: sizes 3 (repost+2 comments), 0, 2 (quote -> repost of quote)
        assert c["n_roots"] == 3 and c["n_engaged"] == 2 and c["size"]["max"] == 3 and ap(c["size"]["mean"], 2.5)
        assert c["depth"]["max"] == 2 and c["breadth"]["max"] == 3 and c["depth_hist"] == {1: 1, 2: 1}

        s = m["stance"]
        assert len(calls) == 5 and s["new_llm_calls"] == 5  # duplicate text A labelled once
        assert s["n_items"] == 6 and s["n_labelled"] == 6 and s["n_without_round"] == 0
        er = {x["round"]: x for x in s["entropy_per_round"]}
        assert [er[i]["n"] for i in range(4)] == [1, 2, 2, 1]
        assert ap(er[0]["entropy_bits"], 0) and ap(er[1]["entropy_bits"], 1) and ap(er[2]["entropy_bits"], 1) and ap(er[3]["entropy_bits"], 0)
        assert s["flips"]["n_agents_eligible"] == 2 and ap(s["flips"]["flipped_share"], 0.5) and ap(s["flips"]["polarity_reversal_share"], 0.5)
        si = s["same_stance_interactions"]
        assert si["all"]["n"] == 9 and ap(si["all"]["same_stance_share"], 5 / 9)
        assert si["comment"]["n"] == 2 and ap(si["comment"]["same_stance_share"], 0.5)
        assert si["like"]["n"] == 3 and si["repost"]["n"] == 2 and si["quote"]["n"] == 1 and si["dislike"]["n"] == 1

        calls.clear()  # rerun: everything comes from stance_labels.json, zero LLM calls
        again = analyze(out, stance=("the transit levy", lambda t: calls.append(t) or gold[t], "fake-model"))
        assert calls == [] and again["platforms"]["reddit"]["stance"]["new_llm_calls"] == 0
        assert json.loads((out / "metrics.json").read_text())["platforms"]["reddit"]["stance"]["n_labelled"] == 6

        # empty OASIS DB (schema only, nothing happened): every metric present, none crash
        e2 = Path(td) / "e2"
        e2.mkdir()
        build_empty = sqlite3.connect(e2 / "twitter_simulation.db")
        for f in sorted(find_schema().glob("*.sql")):
            build_empty.executescript(f.read_text())
        build_empty.commit()
        build_empty.close()
        t = analyze(e2, stance=("x", lambda t: "neutral", "fake"))["platforms"]["twitter"]
        assert t["action_mix"]["n"] == 0 and t["activity"]["gini"] is None and t["cascades"]["n_roots"] == 0
        assert t["stance"]["n_labelled"] == 0 and t["stance"]["same_stance_interactions"]["all"]["n"] == 0
    print("self-test OK")


def read_env_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
        f.write(text)
    try:
        return read_env(f.name)
    finally:
        Path(f.name).unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", nargs="?", help="run directory (e.g. eval/results/e2e-<label>)")
    ap.add_argument("--self-test", action="store_true", help="synthetic fixture with asserted values; no network")
    ap.add_argument("--stance", action="store_true", help="classify each post/comment with the local LLM (needs --target)")
    ap.add_argument("--target", help='what stance is measured toward, e.g. "the proposed transit levy"')
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.out_dir or not Path(a.out_dir).is_dir():
        ap.error("out_dir missing or not a directory")
    if a.stance and not a.target:
        ap.error("--stance needs --target")
    stance = None
    if a.stance:
        labeler, model = llm_labeler(read_env(ROOT / ".env"), a.target)
        stance = (a.target, labeler, model)
    res = analyze(a.out_dir, stance)
    for p, m in res["platforms"].items():
        print(p, "actions:", m["action_mix"]["n"], "do_nothing:", m["action_mix"]["do_nothing_share"],
              "gini:", m["activity"]["gini"], "dup_posts:", m["repetition"]["posts"]["exact_duplicates"]["share"])
    print("wrote", Path(a.out_dir) / "metrics.json")


if __name__ == "__main__":
    main()
