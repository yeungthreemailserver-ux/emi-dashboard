r"""Ingest company-issued guidance from EDGAR 8-K press releases for US filers.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\run_guidance.py
"""
from __future__ import annotations

from emi import db
from emi.config import iter_universe
from emi.ingest.edgar import load_cik_map
from emi.ingest.guidance import get_guidance


def main() -> None:
    db.init_db()  # ensures the guidance table exists (CREATE IF NOT EXISTS), drops nothing
    cikmap = load_cik_map()
    us = [r for r in iter_universe() if r.get("region") == "US"]
    rows, got = [], 0
    for i, r in enumerate(us, 1):
        tk = r["ticker"]
        cik = cikmap.get(tk)
        if not cik:
            continue
        g = get_guidance(tk, cik)
        if not g:
            continue
        got += 1
        for metric in ("revenue", "gross_margin"):
            if metric in g:
                d = g[metric]
                rows.append({"ticker": tk, "metric": metric, "period_text": g.get("period_text"),
                             "mid": d.get("mid"), "low": d.get("low"), "high": d.get("high"),
                             "filed": g.get("filed"), "accn": g.get("accn"), "raw": d.get("raw"),
                             "source": "edgar_8k"})
        if i % 15 == 0:
            print(f"  [{i}/{len(us)}] companies with guidance: {got}", flush=True)
    db.upsert_guidance(rows)
    print(f"\nUS companies scanned : {len(us)}")
    print(f"With guidance        : {got}")
    print(f"Guidance rows        : {len(rows)}")


if __name__ == "__main__":
    main()
