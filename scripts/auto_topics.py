r"""AUTO-PROMOTE hot emergent topics into the taxonomy (data-driven, idempotent).

Reads data/emergent_topics.json (clusters from discover_topics.py), keeps the ones flagged is_new and
raised by >= MIN_COS companies (the "hot & latest" filter), then asks gpt-5.4 to assign each a stable id,
neutral label, best-fit tree parent node, kind, and keyword lexicon. Writes:
  - data/emergent_lexicon.json : {id: [keyword regexes]}   (count_topics merges these -> token-free counting)
  - appends leaves to data/topic_tree.json                  (so the tree/bubbles/inspector pick them up)
Idempotent: ids/labels already in the taxonomy are skipped. Key from openai_key.txt; never printed.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\auto_topics.py [--min-cos 6] [--max-new 12]
"""
from __future__ import annotations
import argparse, json, re, sys, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT

KEY = (ROOT / "openai_key.txt").read_text(encoding="utf-8").strip()
TREE_PATH = ROOT / "data" / "topic_tree.json"
LEX_PATH = ROOT / "data" / "emergent_lexicon.json"
TREE = json.loads(TREE_PATH.read_text(encoding="utf-8"))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:24]


SYS = (
    "You curate a semiconductor-supply-chain topic taxonomy. For each emergent topic, assign: a stable snake_case "
    "id; a NEUTRAL label (the subject only — NO judgement words like tight/strong/soft); the best-fit PARENT node "
    "id from the provided tree nodes; a kind (product = has both demand & supply, e.g. a chip/tech; demand = an "
    "end-market/demand driver; supply = capacity/inventory/ops; price; macro = geopolitics/regulation); and 4-7 "
    "keyword regex terms (case-insensitive, specific, that a regex counter can match in transcripts). "
    "Pick parent so kind matches the parent's facet where possible (products->a product subject/dimension; demand->ai_dc or endmkt; supply->ops; price->mem_pri; macro->macro)."
)
SCHEMA = {"type": "object", "additionalProperties": False, "properties": {"topics": {"type": "array", "items": {
    "type": "object", "additionalProperties": False,
    "properties": {"cluster": {"type": "string"}, "id": {"type": "string"}, "label": {"type": "string"},
                   "parent": {"type": "string"}, "kind": {"type": "string", "enum": ["product", "demand", "supply", "price", "macro"]},
                   "keywords": {"type": "array", "items": {"type": "string"}}},
    "required": ["cluster", "id", "label", "parent", "kind", "keywords"]}}}, "required": ["topics"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-cos", type=int, default=6)
    ap.add_argument("--max-new", type=int, default=12)
    a = ap.parse_args()
    em = json.loads((ROOT / "data" / "emergent_topics.json").read_text(encoding="utf-8"))
    have_labels = {lf["label"].lower() for lf in TREE["leaves"].values()} | {n["label"].lower() for n in TREE["nodes"].values()}
    have_ids = set(TREE["leaves"]) | set(TREE["nodes"])
    hot = [c for c in em["clusters"] if c.get("is_new") and c.get("companies", 0) >= a.min_cos
           and c["name"].lower() not in have_labels][:a.max_new]
    if not hot:
        print("no new hot emergent topics over threshold"); return
    nodes_desc = "\n".join(f"- {nid} = {n['label']} (facet {n.get('facet')})" for nid, n in TREE["nodes"].items())
    user = ("Tree parent nodes you may assign to:\n" + nodes_desc + "\n\nExisting leaf labels (do not duplicate):\n"
            + ", ".join(sorted(lf["label"] for lf in TREE["leaves"].values())) + "\n\nEmergent topics to add (name · #companies · examples):\n"
            + "\n".join(f"- {c['name']} · {c['companies']} · {', '.join(c.get('examples', [])[:3])}" for c in hot))
    payload = {"model": "gpt-5.4", "reasoning_effort": "medium",
               "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
               "response_format": {"type": "json_schema", "json_schema": {"name": "promote", "strict": True, "schema": SCHEMA}}}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    out = json.loads(json.loads(urllib.request.urlopen(req, timeout=240).read())["choices"][0]["message"]["content"])["topics"]
    lex = json.loads(LEX_PATH.read_text(encoding="utf-8")) if LEX_PATH.exists() else {}
    added = []
    for t in out:
        tid = slug(t["id"] or t["label"])
        if not tid or tid in have_ids or t["parent"] not in TREE["nodes"] or not t.get("keywords"):
            continue
        TREE["leaves"][tid] = {"label": t["label"], "parent": t["parent"], "kind": t["kind"],
                               "reads": (["demand", "supply"] if t["kind"] == "product" else [t["kind"] if t["kind"] in ("demand", "supply") else "demand"]),
                               "emergent": True}
        lex[tid] = t["keywords"]
        have_ids.add(tid); added.append((tid, t["label"], t["parent"], t["kind"], len(t["keywords"])))
    if added:
        TREE_PATH.write_text(json.dumps(TREE, ensure_ascii=False, indent=1), encoding="utf-8")
        LEX_PATH.write_text(json.dumps(lex, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"promoted {len(added)} emergent topics (>= {a.min_cos} cos):")
    for tid, lab, par, kind, nk in added:
        print(f"  + {tid:<22} '{lab}' -> {par} [{kind}] {nk} kw")


if __name__ == "__main__":
    main()
