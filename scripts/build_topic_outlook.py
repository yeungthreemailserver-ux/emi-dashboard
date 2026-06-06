r"""Merge a Haiku outlook synthesis (topic_outlook/<t>.synth.json) with the extracted evidence
sentences and per-segment sentiment matrix (data/_topic_<t>.json) into the final consumable
data/topic_outlook/<t>.json that load_transcripts.py bundles into the dashboard.

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\build_topic_outlook.py auto
"""
import json
import sys

sys.path.insert(0, "scripts")
from emi.config import ROOT

topic = sys.argv[1]
OUT = ROOT / "data" / "topic_outlook"
synth = json.loads((OUT / f"{topic}.synth.json").read_text(encoding="utf-8"))
ext = json.loads((ROOT / "data" / f"_topic_{topic}.json").read_text(encoding="utf-8"))

# management speech first (it is the company's stance); analyst questions last
PRIO = {"ceo": 0, "cfo": 1, "a": 2, "all": 3, "q": 9}
# only carry companies the LLM judged to have SUBSTANTIVE exposure (drops keyword false-positives / list-only mentions)
keep = set(synth.get("companies", {}).keys())
evidence, matrix = {}, {}
for tk, c in ext["companies"].items():
    if tk not in keep:
        continue
    ss = sorted(c["sents"], key=lambda s: PRIO.get(s["seg"], 5))
    evidence[tk] = [{"seg": s["seg"], "t": s["t"]} for s in ss[:3]]
    matrix[tk] = {"traj": c.get("traj"), "sent": c.get("sent", {})}

synth["evidence"] = evidence
synth["matrix"] = {"periods": ext["periods"], "companies": matrix}
(OUT / f"{topic}.json").write_text(json.dumps(synth, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote data/topic_outlook/{topic}.json  ({len(evidence)} companies, evidence + matrix merged)")
