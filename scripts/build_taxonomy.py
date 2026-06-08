r"""HIERARCHICAL TAXONOMY INDUCTION from the discovered themes (serious, comprehensive, properly nested).

Pass-1 discovery (discover_topics.py) extracted 800+ specific themes across the corpus, but Pass-2 collapsed
them into ~40 flat clusters and the promoted ones were appended directly under root nodes. This rebuilds the
taxonomy PROPERLY: gpt-5.4 organises ALL discovered themes into a deep, legible Subject -> family -> topic tree,
PRESERVING the existing hand-tuned demand/supply/pricing backbone and ids, adding the missing subject branches
(Interconnect/Optical, Power, Networking, Storage, Analog & Sensors, RF/Connectivity, Design/EDA, Packaging, ...),
re-parenting the flat emergent leaves under their real subject, and emitting a keyword lexicon for each new leaf.

Writes a PROPOSAL (review before committing), not the live tree:
  data/topic_tree.proposed.json   (full merged tree)
  data/proposed_lexicon.json      (keywords for new leaves; merged into emergent_lexicon.json on approval)

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\build_taxonomy.py [--model gpt-5.4] [--max-phrases 900]
Then review, and: .\.venv\Scripts\python.exe scripts\build_taxonomy.py --commit
"""
from __future__ import annotations
import argparse, json, re, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT

KEY = (ROOT / "openai_key.txt").read_text(encoding="utf-8").strip()
_API = "https://api.openai.com/v1/chat/completions"


def _stream(payload, timeout=300, retries=4):
    """POST a streaming chat-completion and return the parsed JSON content, retrying transient network errors.
    A reasoning model thinks fully before the first token, so the first-byte wait must cover reasoning; once
    generation starts, SSE lines arrive continuously and keep the socket alive."""
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(_API, data=body,
                                         headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            buf, ticks = [], 0
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", "ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                    except Exception:
                        continue
                    if delta:
                        buf.append(delta); ticks += 1
                        if ticks % 200 == 0:
                            print(f"  …streaming ({sum(len(b) for b in buf)} chars)", flush=True)
            return json.loads("".join(buf))
        except (urllib.error.URLError, TimeoutError, ConnectionResetError, ValueError) as e:
            if attempt < retries - 1:
                print(f"  retry {attempt + 1}/{retries - 1} after {type(e).__name__}", flush=True)
                time.sleep(5 * (attempt + 1)); continue
            raise
TREE_PATH = ROOT / "data" / "topic_tree.json"
RAW_PATH = ROOT / "data" / "emergent_raw.json"
PROP_TREE = ROOT / "data" / "topic_tree.proposed.json"
PROP_LEX = ROOT / "data" / "proposed_lexicon.json"
LEX_PATH = ROOT / "data" / "emergent_lexicon.json"

SYS = (
    "You are a semiconductor-industry equity analyst building a COMPREHENSIVE, HIERARCHICAL topic taxonomy for "
    "earnings-call intelligence across ~72 chip/semicap/component companies. You are given (a) the EXISTING taxonomy "
    "backbone and (b) 800+ specific themes analysts actually raised. Your job: organise EVERY distinct theme into a "
    "deep, legible tree.\n\n"
    "HARD RULES:\n"
    "1. PRESERVE the existing nodes and leaves and their ids exactly — never rename or drop them. You only ADD.\n"
    "2. Build real HIERARCHY with VARIABLE DEPTH: Subject -> family -> (generation). Add the missing SUBJECT branches "
    "under 'products' that the existing tree lacks, e.g.: Interconnect & Optical (silicon photonics/CPO, 800G/1.6T optics, "
    "retimers/SerDes, AECs), Power (data-center 800V/HVDC, 48V, power management/PMIC), Power semiconductors (SiC, GaN), "
    "Networking (Ethernet/switching, fabric, 5G/6G/RAN), Storage (HDD/EPMR, SSD/enterprise NAND), Analog & Sensors "
    "(MCU, analog, sensors, radar/imaging), Connectivity & RF (RF front-end, Wi-Fi, timing/clocks), Design & IP "
    "(EDA, IP, chiplet/3D-IC design). Add families/dimensions as nodes where it aids legibility. Use the SAME "
    "Demand/Supply/Pricing/Capability dimension pattern the Memory/Processor branches use, where it fits.\n"
    "3. NEUTRAL labels only — the subject, never a judgement (no 'tight', 'strong', 'soft', 'sold-out').\n"
    "4. MERGE near-duplicate phrases into ONE leaf (e.g. '2nm ramp', 'A14 nanosheet', 'advanced logic nodes' -> an "
    "'Advanced nodes' leaf if not already present). Keep genuinely DISTINCT technologies as separate leaves "
    "(e.g. SiC vs GaN may be one 'SiC/GaN' leaf; 800G vs 1.6T optics is one 'Optical interconnect' leaf with generations only if material).\n"
    "5. RE-PARENT the existing emergent leaves (listed) from their temporary root parent to their REAL subject node.\n"
    "6. Each NEW leaf needs: stable snake_case id (<=24 chars, unique, not colliding with existing ids); neutral label; "
    "parent (an existing node id OR one of YOUR new_nodes ids); kind (product = has demand&supply, e.g. a chip/technology; "
    "demand = an end-market/demand driver; supply = capacity/ops/equipment; price; macro = geopolitics/regulation); and "
    "4-8 case-insensitive keyword regex terms that a regex counter can match in transcripts (specific multi-word phrases "
    "and acronyms, avoid over-broad single words).\n"
    "7. Aim for COMPREHENSIVE coverage — a final tree of roughly 90-140 leaves. Do not leave whole theme areas uncovered.\n"
    "Return ONLY the JSON for what to ADD/CHANGE (new_nodes, reparent, new_leaves)."
)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "new_nodes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"id": {"type": "string"}, "label": {"type": "string"}, "parent": {"type": "string"},
                           "facet": {"type": "string", "enum": ["product", "demand", "supply", "price", "risk", "commercial"]}},
            "required": ["id", "label", "parent", "facet"]}},
        "reparent": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"id": {"type": "string"}, "new_parent": {"type": "string"}},
            "required": ["id", "new_parent"]}},
        "new_leaves": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"id": {"type": "string"}, "label": {"type": "string"}, "parent": {"type": "string"},
                           "kind": {"type": "string", "enum": ["product", "demand", "supply", "price", "macro"]},
                           "keywords": {"type": "array", "items": {"type": "string"}}},
            "required": ["id", "label", "parent", "kind", "keywords"]}},
    },
    "required": ["new_nodes", "reparent", "new_leaves"],
}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:24]


def call(model, phrases, tree, effort="medium"):
    nodes_desc = "\n".join(f"- {nid} = {n['label']} (parent {n.get('parent')}, facet {n.get('facet')})"
                           for nid, n in tree["nodes"].items())
    leaves_desc = "\n".join(f"- {lid} = {lf['label']} (parent {lf['parent']}, kind {lf['kind']}"
                            + (", EMERGENT-flat" if lf.get("emergent") else "") + ")" for lid, lf in tree["leaves"].items())
    emergent_ids = [lid for lid, lf in tree["leaves"].items() if lf.get("emergent")]
    user = (
        "EXISTING NODES (preserve all; you may add children to any):\n" + nodes_desc
        + "\n\nEXISTING LEAVES (preserve all ids; RE-PARENT the EMERGENT-flat ones under their real subject):\n" + leaves_desc
        + "\n\nEmergent leaves to re-parent: " + ", ".join(emergent_ids)
        + "\n\nDISCOVERED THEMES (deduped, organise ALL of these):\n" + "\n".join(f"- {p}" for p in phrases)
    )
    payload = {"model": model, "reasoning_effort": effort, "stream": True,
               "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
               "response_format": {"type": "json_schema", "json_schema": {"name": "taxonomy", "strict": True, "schema": SCHEMA}}}
    return _stream(payload)


TIGHTEN_SYS = (
    "You tune keyword REGEX terms for a token-free counter that scans earnings-call transcripts. For each topic "
    "(id + label + current keywords) return a TIGHT list of 4-8 regex terms that match the topic WITHOUT false positives.\n"
    "HARD RULES:\n"
    "1. NEVER output a bare common English word — e.g. timing, clock, clocks, roadmap, sensing, ramp, demand, supply, "
    "capacity, services, spares, upgrades, scale up, scale-up, power density, voltage, allocation, expansion, content, "
    "roadmap, platform — they match unrelated speech. Drop them.\n"
    "2. Short acronyms MUST be word-boundaried: 'GaN' -> '\\\\bGaN\\\\b', 'PON' -> '\\\\bPON\\\\b', 'XPU' -> '\\\\bXPU\\\\b', "
    "'AEC' -> '\\\\bAEC\\\\b'. NEVER output bare 'IP' or 'PIC' (they match 'equ-IP-ment', 'to-PIC'); drop them entirely.\n"
    "3. Prefer SPECIFIC multi-word phrases and concrete product/standard names (e.g. 'co-packaged optics', 'silicon photonics', "
    "'1\\\\.6T', 'HAMR', 'XGS-PON', 'NVLink', '800V', 'EUV pellicle'). Acronyms only with \\\\b boundaries.\n"
    "4. Every regex must be case-insensitively matchable in prose. Keep each topic's terms specific to THAT topic (avoid "
    "terms that also fire for sibling topics). Return tightened keywords for EVERY id you are given."
)
TIGHTEN_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {"topics": {"type": "array", "items": {
    "type": "object", "additionalProperties": False,
    "properties": {"id": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}}},
    "required": ["id", "keywords"]}}}, "required": ["topics"]}


def tighten(model, lex, tree, effort="medium"):
    leaves = tree["leaves"]
    items = [{"id": tid, "label": leaves.get(tid, {}).get("label", tid), "keywords": kw} for tid, kw in lex.items()]
    user = "Tighten keywords for these topics (return all):\n" + json.dumps(items, ensure_ascii=False)
    payload = {"model": model, "reasoning_effort": effort, "stream": True,
               "messages": [{"role": "system", "content": TIGHTEN_SYS}, {"role": "user", "content": user}],
               "response_format": {"type": "json_schema", "json_schema": {"name": "tight", "strict": True, "schema": TIGHTEN_SCHEMA}}}
    out = _stream(payload)["topics"]
    return {t["id"]: t["keywords"] for t in out if t.get("keywords")}


EXPAND_SYS = (
    "You widen keyword REGEX coverage for a token-free transcript counter. A topic is UNDER-matching: its keywords "
    "miss companies that (per semantic discovery) clearly discuss it. Given the topic label, its CURRENT keywords, and "
    "example phrases analysts actually used, propose 3-6 ADDITIONAL regex terms that capture the missed phrasings.\n"
    "HARD RULES (same as before): NO bare generic English words (test, timing, power, demand, supply, capacity, content, "
    "platform…); short acronyms MUST be \\\\b-boundaried; never bare 'IP'/'PIC'/'ATE'-style 2-letter strings without \\\\b; "
    "prefer specific multi-word phrases. Do NOT repeat the current keywords. Stay specific to THIS topic (don't bleed into "
    "siblings). Return additions for every id."
)


def _norm(s):
    return set(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def reconcile(tree):
    """Compare keyword breadth (topic_counts) vs reliable discovery prevalence (emergent_topics clusters)."""
    cnt = json.loads((ROOT / "data" / "topic_counts.json").read_text(encoding="utf-8")).get("breadth", {})
    em = json.loads((ROOT / "data" / "emergent_topics.json").read_text(encoding="utf-8")).get("clusters", [])
    lex = json.loads(LEX_PATH.read_text(encoding="utf-8")) if LEX_PATH.exists() else {}
    leaves = tree["leaves"]
    gaps = []
    for tid in lex:
        lf = leaves.get(tid)
        if not lf:
            continue
        kb = cnt.get(tid) or [0]
        kb = max(kb) if kb else 0
        toks = _norm(lf["label"])
        best, bestov = None, 0.0
        for c in em:
            ov = len(toks & _norm(c["name"])) / max(1, len(toks | _norm(c["name"])))
            if ov > bestov:
                best, bestov = c, ov
        if best and bestov >= 0.3:
            disc = best.get("companies", 0)
            if disc >= 8 and kb < disc * 0.4:
                gaps.append({"id": tid, "label": lf["label"], "kw_cos": kb, "disc_cos": disc,
                             "current": lex.get(tid, []), "examples": best.get("examples", [])[:6]})
    return gaps, lex


def expand(model, gaps, effort="medium"):
    items = [{"id": g["id"], "label": g["label"], "current_keywords": g["current"], "example_phrases": g["examples"]} for g in gaps]
    user = "Widen keyword coverage for these under-matching topics (return additions for all):\n" + json.dumps(items, ensure_ascii=False)
    payload = {"model": model, "reasoning_effort": effort, "stream": True,
               "messages": [{"role": "system", "content": EXPAND_SYS}, {"role": "user", "content": user}],
               "response_format": {"type": "json_schema", "json_schema": {"name": "expand", "strict": True, "schema": TIGHTEN_SCHEMA}}}
    return {t["id"]: t["keywords"] for t in _stream(payload)["topics"] if t.get("keywords")}


def merge(tree, out):
    tree = json.loads(json.dumps(tree))  # deep copy
    nodes, leaves = tree["nodes"], tree["leaves"]
    added_nodes, added_leaves, reparented = [], [], []
    for n in out.get("new_nodes", []):
        nid = slug(n["id"])
        if not nid or nid in nodes or nid in leaves:
            continue
        nodes[nid] = {"label": n["label"], "parent": n["parent"], "facet": n["facet"]}
        added_nodes.append(nid)
    valid = set(nodes)
    for rp in out.get("reparent", []):
        lid, np = rp["id"], rp["new_parent"]
        if lid in leaves and np in valid:
            leaves[lid]["parent"] = np
            leaves[lid].pop("emergent", None)
            reparented.append((lid, np))
    lex = {}
    for lf in out.get("new_leaves", []):
        lid = slug(lf["id"])
        if not lid or lid in leaves or lid in nodes or lf["parent"] not in valid or not lf.get("keywords"):
            continue
        kind = lf["kind"]
        reads = ["demand", "supply"] if kind == "product" else ([kind] if kind in ("demand", "supply") else ["demand"])
        leaves[lid] = {"label": lf["label"], "parent": lf["parent"], "kind": kind, "reads": reads, "emergent": True}
        lex[lid] = lf["keywords"]
        added_leaves.append((lid, lf["label"], lf["parent"], kind))
    return tree, lex, added_nodes, added_leaves, reparented


def print_tree(tree):
    nodes, leaves = tree["nodes"], tree["leaves"]
    children = {}
    for nid, n in nodes.items():
        children.setdefault(n.get("parent"), []).append(("node", nid))
    for lid, lf in leaves.items():
        children.setdefault(lf.get("parent"), []).append(("leaf", lid))

    def walk(pid, depth):
        for kind, cid in sorted(children.get(pid, []), key=lambda x: (x[0] == "leaf", (nodes.get(x[1]) or leaves.get(x[1]))["label"].lower())):
            obj = nodes.get(cid) or leaves.get(cid)
            tag = "" if kind == "node" else f"  [{leaves[cid]['kind']}]" + ("  *NEW*" if leaves[cid].get("emergent") else "")
            print("  " * depth + ("• " if kind == "leaf" else "▸ ") + obj["label"] + (f"  ({cid})" if kind == "leaf" else "") + tag)
            if kind == "node":
                walk(cid, depth + 1)
    for kind, cid in [c for c in children.get(None, [])]:
        obj = nodes.get(cid) or leaves.get(cid)
        print("\n### " + obj["label"] + f"  ({cid})")
        walk(cid, 1)
    print(f"\nTOTAL: {len(nodes)} nodes, {len(leaves)} leaves")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.4-mini")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--max-phrases", type=int, default=900)
    ap.add_argument("--commit", action="store_true", help="merge the proposal into the LIVE tree + lexicon")
    ap.add_argument("--show", action="store_true", help="re-render the saved proposal tree (no LLM call)")
    ap.add_argument("--prune", action="store_true", help="clean the proposal: drop dup-label leaves + empty nodes")
    ap.add_argument("--tighten", action="store_true", help="LLM-tighten the LIVE emergent lexicon to kill false positives")
    ap.add_argument("--expand", action="store_true", help="reconcile keyword breadth vs discovery prevalence; widen UNDER-matching topics")
    a = ap.parse_args()

    if a.show:
        print_tree(json.loads(PROP_TREE.read_text(encoding="utf-8"))); return

    if a.expand:
        tree = json.loads(TREE_PATH.read_text(encoding="utf-8"))
        gaps, lex = reconcile(tree)
        if not gaps:
            print("no under-matching topics — keyword coverage looks aligned with discovery"); return
        print(f"{len(gaps)} under-matching topics (keyword breadth << discovery prevalence):")
        for g in gaps:
            print(f"  {g['id']:<24} kw {g['kw_cos']}cos vs discovery {g['disc_cos']}cos")
        adds = expand(a.model, gaps, a.effort)
        n = 0
        for tid, kw in adds.items():
            if tid in lex and kw:
                have = set(lex[tid]); new = [k for k in kw if k not in have]
                if new:
                    lex[tid] = lex[tid] + new; n += 1
        LEX_PATH.write_text(json.dumps(lex, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"expanded {n} keyword sets -> {LEX_PATH.name}  (re-run build_topic_counts to apply)")
        return

    if a.tighten:
        tree = json.loads(TREE_PATH.read_text(encoding="utf-8"))
        lex = json.loads(LEX_PATH.read_text(encoding="utf-8"))
        print(f"tightening {len(lex)} keyword sets with {a.model} ({a.effort})…", flush=True)
        tight = tighten(a.model, lex, tree, a.effort)
        n = 0
        for tid, kw in tight.items():
            if tid in lex and kw:
                lex[tid] = kw; n += 1
        LEX_PATH.write_text(json.dumps(lex, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"tightened {n}/{len(lex)} keyword sets -> {LEX_PATH.name}")
        return

    if a.prune:
        tree = json.loads(PROP_TREE.read_text(encoding="utf-8"))
        nodes, leaves = tree["nodes"], tree["leaves"]
        lex = json.loads(PROP_LEX.read_text(encoding="utf-8")) if PROP_LEX.exists() else {}
        norm = lambda s: re.sub(r"[^a-z0-9]+", "", (s or "").lower())
        # 1) drop NEW leaves whose normalised label duplicates an existing/curated leaf (keep the non-emergent one)
        by_norm = {}
        for lid, lf in leaves.items():
            by_norm.setdefault(norm(lf["label"]), []).append(lid)
        dropped_dup = []
        for nlabel, ids in by_norm.items():
            if len(ids) < 2:
                continue
            ids.sort(key=lambda i: (1 if leaves[i].get("emergent") else 0))  # prefer keeping non-emergent
            for lid in ids[1:]:
                leaves.pop(lid, None); lex.pop(lid, None); dropped_dup.append(lid)
        # 2) iteratively prune nodes that have no leaf among their descendants
        def has_leaf(nid):
            if any(lf["parent"] == nid for lf in leaves.values()):
                return True
            return any((cn["parent"] == nid and has_leaf(cnid)) for cnid, cn in nodes.items())
        pruned_nodes = []
        changed = True
        while changed:
            changed = False
            for nid in list(nodes):
                if nid in ("products", "endmkt", "ops", "macro"):
                    continue
                if not has_leaf(nid):
                    nodes.pop(nid); pruned_nodes.append(nid); changed = True
        PROP_TREE.write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
        PROP_LEX.write_text(json.dumps(lex, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"pruned {len(dropped_dup)} duplicate leaves: {', '.join(dropped_dup) or '—'}")
        print(f"pruned {len(pruned_nodes)} empty nodes: {', '.join(pruned_nodes) or '—'}")
        print(f"now: {len(nodes)} nodes, {len(leaves)} leaves")
        return

    if a.commit:
        if not PROP_TREE.exists():
            print("no proposal to commit — run without --commit first"); return
        prop = json.loads(PROP_TREE.read_text(encoding="utf-8"))
        TREE_PATH.write_text(json.dumps(prop, ensure_ascii=False, indent=1), encoding="utf-8")
        lex = json.loads(LEX_PATH.read_text(encoding="utf-8")) if LEX_PATH.exists() else {}
        plex = json.loads(PROP_LEX.read_text(encoding="utf-8")) if PROP_LEX.exists() else {}
        lex.update(plex)
        LEX_PATH.write_text(json.dumps(lex, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"committed: tree -> {TREE_PATH.name} ({len(prop['leaves'])} leaves), lexicon += {len(plex)} new leaves")
        return

    tree = json.loads(TREE_PATH.read_text(encoding="utf-8"))
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    seen, phrases = set(), []
    for tk, lst in raw.items():
        for p in (lst or []):
            k = (p or "").lower().strip()
            if k and k not in seen:
                seen.add(k); phrases.append(p.strip())
    phrases = phrases[:a.max_phrases]
    print(f"organising {len(phrases)} unique themes with {a.model} ({a.effort} reasoning, streaming)…", flush=True)
    out = call(a.model, phrases, tree, a.effort)
    merged, lex, an, al, rp = merge(tree, out)
    PROP_TREE.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    PROP_LEX.write_text(json.dumps(lex, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n+{len(an)} new nodes, +{len(al)} new leaves, {len(rp)} re-parented\n")
    print_tree(merged)
    print("\nwrote PROPOSAL:", PROP_TREE.name, "+", PROP_LEX.name, "— review, then run with --commit")


if __name__ == "__main__":
    main()
