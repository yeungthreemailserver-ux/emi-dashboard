r"""Backfill quarterly financials from SEC EDGAR for US filers (source='edgar'), to extend
history well beyond Yahoo's ~5-quarter window (esp. fiscal-offset names like NVDA/MRVL).
CUTOFF sets how many years of history to keep (EDGAR carries up to ~18 years).
Non-US names (TSMC, SK hynix, MediaTek, Infineon...) have no SEC filings, so they stay
limited to Yahoo's recent quarters — a hard limit of free data.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\run_edgar_us.py
"""
from __future__ import annotations

import sqlite3

from emi import db
from emi.config import DB_PATH, iter_universe
from emi.ingest import edgar

CUTOFF = "2019-01-01"  # ~7 years of history for US filers


def main() -> None:
    db.init_db()
    cikmap = edgar.load_cik_map()
    us = [r for r in iter_universe() if r.get("region") == "US"]
    rows, resolved, missing = [], [], []
    for i, r in enumerate(us, 1):
        tk = r["ticker"]
        cik = cikmap.get(tk)
        if not cik:
            missing.append(tk)
            continue
        facts = edgar.fetch_company_facts(cik)
        if not facts:
            missing.append(f"{tk}(no facts)")
            continue
        recent = [x for x in edgar.extract_metrics(tk, str(cik), facts) if x["period_end"] >= CUTOFF]
        rows.extend(recent)
        resolved.append(tk)
        if i % 20 == 0:
            print(f"  [{i}/{len(us)}] rows={len(rows)}", flush=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM financials WHERE source='edgar'")
    conn.commit()
    conn.close()
    db.upsert_financials(rows)
    print(f"\nUS resolved: {len(resolved)} | EDGAR rows (>= {CUTOFF}): {len(rows)} | missing: {len(missing)}")
    if missing:
        print("missing:", ", ".join(missing))


if __name__ == "__main__":
    main()
