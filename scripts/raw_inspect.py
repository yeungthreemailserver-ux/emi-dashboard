r"""Inspect raw cached EDGAR companyfacts for a ticker — concept coverage + durations.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\raw_inspect.py MU list
    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\raw_inspect.py MU RevenueFromContractWithCustomerExcludingAssessedTax
"""
import json
import sys
from datetime import date

from emi.config import RAW_DIR
from emi.ingest.edgar import load_cik_map

ticker = (sys.argv[1] if len(sys.argv) > 1 else "MU").upper()
mode = sys.argv[2] if len(sys.argv) > 2 else "list"

cik = load_cik_map()[ticker]
facts = json.loads((RAW_DIR / "edgar" / f"CIK{int(cik):010d}.json").read_text(encoding="utf-8"))
usgaap = facts["facts"]["us-gaap"]


def points(concept):
    units = usgaap[concept]["units"]
    return units.get("USD") or next(iter(units.values()))


if mode == "list":
    print(f"### {ticker} — concepts containing Revenue / Sales / GrossProfit")
    for c in sorted(usgaap):
        if any(k in c for k in ("Revenue", "Sales", "GrossProfit")):
            pts = points(c)
            ends = [p["end"] for p in pts]
            print(f"  {c:60s} n={len(pts):4d}  {min(ends)}..{max(ends)}")
else:
    print(f"### {ticker} — {mode} (points ending >= 2025-06-01)")
    for pt in points(mode):
        start, end = pt.get("start"), pt.get("end")
        if end < "2025-06-01":
            continue
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days if start else None
        print(f"  {str(start):10} -> {end}  days={str(days):>4}  "
              f"val={pt['val'] / 1e9:8.3f}B  fp={pt.get('fp')} form={pt.get('form')} filed={pt.get('filed')}")
