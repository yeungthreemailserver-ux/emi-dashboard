r"""Test guidance extraction across several US filers.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\test_guidance.py
"""
from emi.ingest.edgar import load_cik_map
from emi.ingest.guidance import get_guidance

cikmap = load_cik_map()
for tk in ["NVDA", "AMD", "INTC", "MU", "AVGO", "TXN", "QCOM", "MCHP", "AMAT", "DELL", "ARW"]:
    cik = cikmap.get(tk)
    if not cik:
        print(f"{tk}: no CIK"); continue
    g = get_guidance(tk, cik)
    if not g:
        print(f"{tk}: no guidance found"); continue
    rev, gm = g.get("revenue"), g.get("gross_margin")
    print(f"{tk}  [{g.get('period_text', '?')}]  filed {g.get('filed')}")
    if rev:
        rng = f"  (${rev['low']/1e9:.2f}–{rev['high']/1e9:.2f}B)" if rev.get('low') and rev.get('high') else "  (point estimate)"
        print(f"    revenue: mid ${rev['mid']/1e9:.2f}B{rng}")
    if gm:
        print(f"    gross margin: {gm['mid']*100:.1f}%")
