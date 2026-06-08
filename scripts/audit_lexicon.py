r"""LEXICON QA — spot-check keyword PRECISION (and surface RECALL gaps), token-free.

For each topic it scans the cached transcripts, collects the sentences its keyword regexes matched, and
samples them so you can eyeball whether the matches are really on-topic (precision). It also prints the
keyword breadth (how many companies) next to the discovery prevalence (how many companies raised the theme
in data/emergent_raw.json) — a big gap = the keywords are UNDER-matching (recall miss) and should be widened.

This is the manual half of the self-calibrating loop; --flag prints only the suspect topics.

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\audit_lexicon.py --topics cpo_npo,hvdc_800v,ethernet_switch
    ...\python.exe scripts\audit_lexicon.py --emergent --sample 4          # all auto-added topics
    ...\python.exe scripts\audit_lexicon.py --flag                          # only topics that look mis-tuned
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT
from count_topics import _COMPILED, _SENT
from build_topic_counts import fetch_text, clean_text, MANIFEST, PERIODS

TREE = json.loads((ROOT / "data" / "topic_tree.json").read_text(encoding="utf-8"))
LEAVES = TREE["leaves"]
LEX = json.loads((ROOT / "data" / "emergent_lexicon.json").read_text(encoding="utf-8"))
CNT = json.loads((ROOT / "data" / "topic_counts.json").read_text(encoding="utf-8"))
BRD = CNT.get("breadth", {})
RAW = json.loads((ROOT / "data" / "emergent_raw.json").read_text(encoding="utf-8")) if (ROOT / "data" / "emergent_raw.json").exists() else {}
PERIOD = PERIODS[-1]


def discovery_prevalence(tid):
    """Rough recall ground-truth: how many companies' discovered themes look related to this topic's keywords."""
    kws = [re.sub(r"\\b|\\.|[()?]", "", k).lower() for k in LEX.get(tid, [])]
    kws = [k for k in kws if len(k) >= 3]
    if not kws:
        return None
    n = 0
    for tk, themes in RAW.items():
        blob = " ".join(themes).lower()
        if any(k in blob for k in kws):
            n += 1
    return n


def body_sentences(tk):
    url = MANIFEST.get(tk, [None])[0]
    if not url:
        return []
    doc, kind = fetch_text(url, key=f"{tk}_{PERIOD}")
    text = clean_text(doc, kind) if doc else None
    if not text or len(text.split()) < 400:
        return []
    return [s.strip() for s in _SENT.split(text) if len(s.strip()) > 25]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", help="comma-separated topic ids")
    ap.add_argument("--emergent", action="store_true", help="audit every emergent (auto-added) topic")
    ap.add_argument("--flag", action="store_true", help="print only mis-tuned topics (precision or recall suspect)")
    ap.add_argument("--sample", type=int, default=5, help="matched sentences to show per topic")
    ap.add_argument("--cos", type=int, default=24, help="how many companies to scan (latest call)")
    a = ap.parse_args()
    if a.topics:
        tids = [t.strip() for t in a.topics.split(",") if t.strip()]
    elif a.emergent or a.flag:
        tids = [t for t in LEX if t in LEAVES]
    else:
        tids = [t for t in LEX if t in LEAVES][:12]

    tickers = list(MANIFEST.keys())[: a.cos]
    # gather matched sentences per topic across the scanned companies
    hits = {t: [] for t in tids}
    cos_hit = {t: set() for t in tids}
    for tk in tickers:
        sents = body_sentences(tk)
        if not sents:
            continue
        for t in tids:
            rxs = _COMPILED.get(t, [])
            if not rxs:
                continue
            m = [s for s in sents if any(rx.search(s) for rx in rxs)]
            if m:
                cos_hit[t].add(tk)
                for s in m[:3]:
                    hits[t].append((tk, s))

    for t in tids:
        kb = (BRD.get(t) or [0])
        kb = max(kb) if kb else 0
        dp = discovery_prevalence(t)
        label = LEAVES.get(t, {}).get("label", t)
        sample = hits[t][: a.sample]
        prec_suspect = len(sample) and False  # eyeball; keep all unless --flag heuristic below
        recall_suspect = (dp is not None and dp >= 8 and kb < max(2, dp * 0.25))
        if a.flag and not recall_suspect:
            continue
        flagbits = []
        if recall_suspect:
            flagbits.append(f"RECALL-GAP (kw {kb}cos vs discovery {dp}cos)")
        print(f"\n=== {label}  ({t}) — kw breadth {kb}cos · discovery {dp}cos · scanned-hits {len(cos_hit[t])}cos {' · '.join(flagbits)}")
        print("  keywords: " + " | ".join(LEX.get(t, [])))
        for tk, s in sample:
            print(f"  [{tk}] {s[:200]}")
        if not sample:
            print("  (no matches in scanned sample)")


if __name__ == "__main__":
    main()
