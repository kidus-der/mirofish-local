#!/usr/bin/env python
"""Scoring rules for the graph evaluation. Run directly to re-score every saved result."""

import json
import re
from pathlib import Path


def norm(s: str) -> str:
    s = re.sub(r"[^\w\s.]", " ", (s or "").lower())
    s = re.sub(r"^(the|mayor|council member|ceo)\s+", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


def resolver(gold):
    table = {}
    for e in gold["entities"]:
        for n in [e["name"], *e["aliases"]]:
            table[norm(n)] = e["name"]
    canon = [(norm(e["name"]), e["name"]) for e in gold["entities"]]

    def resolve(name):
        n = norm(name)
        if n in table:
            return table[n]
        return next((c for k, c in canon if k in n), None)

    return resolve


def score(gold, data, search_rows):
    resolve = resolver(gold)
    by_gold, extras = {}, []
    for n in data["nodes"]:
        g = resolve(n["name"])
        if g:
            by_gold.setdefault(g, []).append(n["name"])
        else:
            extras.append(n["name"])
    ent_total = len(gold["entities"])
    dup = {k: v for k, v in by_gold.items() if len(v) > 1}

    names = {n["uuid"]: resolve(n["name"]) for n in data["nodes"]}
    edges = [{**e, "_s": names.get(e["source_node_uuid"]), "_o": names.get(e["target_node_uuid"]),
              "_t": f"{e['name']} {e['fact']}".lower().replace("_", " ")} for e in data["edges"]]

    def match(f):
        return [e for e in edges if {e["_s"], e["_o"]} == {f["s"], f["o"]} and any(k in e["_t"] for k in f["keywords"])]

    facts = {f["id"]: bool(match(f)) for f in gold["facts"]}

    # Looser rule: the fact text names the subject and carries the keyword, whatever node it hangs off
    # (a fact linked to "the plan" instead of the organization still counts).
    aliases = {e["name"]: [norm(x) for x in [e["name"], *e["aliases"]]] for e in gold["entities"]}

    def loose(f):
        for e in edges:
            words = f" {norm(e['fact'])} "
            named = e["_s"] == f["s"] or e["_o"] == f["s"] or any(f" {a} " in words for a in aliases[f["s"]])
            if named and any(k in e["_t"] for k in f["keywords"]):
                return True
        return False

    loose_facts = {f["id"]: loose(f) for f in gold["facts"]}
    temporal = {t["id"]: any(e.get("invalid_at") or e.get("expired_at") for e in match(t["old"])) for t in gold["temporal"]}
    hit5 = sum(r["rank"] is not None and r["rank"] <= 5 for r in search_rows)
    mrr = sum(1 / r["rank"] for r in search_rows if r["rank"]) / len(search_rows)
    return {
        "entity_recall": len(by_gold) / ent_total, "entities_found": len(by_gold), "entities_total": ent_total,
        "duplicate_entities": dup, "extra_nodes": extras, "node_count": len(data["nodes"]),
        "edge_count": len(data["edges"]), "fact_recall": sum(facts.values()) / len(facts), "facts": facts,
        "fact_recall_loose": sum(loose_facts.values()) / len(loose_facts), "facts_loose": loose_facts,
        "temporal_recall": sum(temporal.values()) / len(temporal), "temporal": temporal,
        "search_hit_at_5": hit5 / len(search_rows), "search_mrr": mrr,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    gold = json.loads((root / "gold.json").read_text())
    for p in sorted((root / "results").glob("*.json")):
        d = json.loads(p.read_text())
        d["metrics"].update(score(gold, d["graph"], d["searches"]))
        p.write_text(json.dumps(d, indent=1, ensure_ascii=False, default=str))
        m = d["metrics"]
        print(f"{p.stem:14} ent {m['entity_recall']:.0%} dup {len(m['duplicate_entities'])} fact {m['fact_recall']:.0%}/{m['fact_recall_loose']:.0%} "
              f"temporal {m['temporal_recall']:.0%} hit5 {m['search_hit_at_5']:.0%} mrr {m['search_mrr']:.2f} build {m['build_seconds']:.0f}s calls {m['llm_calls']}")
