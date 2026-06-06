r"""Pre-filter step for the Haiku stance pass: for a company's latest call, pull the sentences
that mention each topic, grouped by speaker segment (ceo/cfo). This tiny JSON (a few hundred
tokens) is what Haiku judges — NOT the whole transcript. Token-cheap by construction.

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\extract_stance_input.py TXN 2026Q1
"""
import glob
import json
import sys

sys.path.insert(0, "scripts")
from count_topics import _COMPILED, _SENT
from emi.config import ROOT
from parse_transcript import segments

tk, period = sys.argv[1], sys.argv[2]
files = glob.glob(str(ROOT / "data" / "transcripts" / f"{tk}_{period}_*.html"))
html = open(files[0], encoding="utf-8", errors="ignore").read()
S = segments(html)
out = {}
for seg in ("ceo", "cfo"):
    text = S.get(seg, "") or ""
    sents = _SENT.split(text)
    by_topic = {}
    for tid, rxs in _COMPILED.items():
        ms = [s.strip() for s in sents if any(rx.search(s) for rx in rxs)]
        if ms:
            by_topic[tid] = ms[:6]
    out[seg] = by_topic
(ROOT / "data" / "_stance_input.json").write_text(json.dumps({"ticker": tk, "period": period, "segments": out}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote data/_stance_input.json — CEO topics: {list(out['ceo'])}\n  CFO topics: {list(out['cfo'])}")
