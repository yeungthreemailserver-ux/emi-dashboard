r"""Verify Yahoo+EDGAR merge filled the recent window (esp. 2025Q1) for fiscal-offset names."""
import json

from emi.config import ROOT

d = json.load(open(ROOT / "web" / "data.json", encoding="utf-8"))
print(f"companies: {d['n_companies']}")
for tk in ["NVDA", "MRVL", "AVGO", "AMD", "TXN", "2330.TW"]:
    c = next((x for x in d["companies"] if x["ticker"] == tk), None)
    if not c:
        print(f"{tk}: missing")
        continue
    cq = c["q"]["calq"]
    rv = c["q"]["revenue"]["v"]
    pairs = " ".join(f"{q}={round(v/1e9,1) if v else '—'}" for q, v in zip(cq, rv))
    print(f"{tk:9s} {pairs}")
