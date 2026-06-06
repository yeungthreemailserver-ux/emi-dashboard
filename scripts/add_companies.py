r"""Incrementally ingest specific tickers WITHOUT resetting the DB.

Unlike run_ingest_v2.py (which calls reset_db() and wipes everything, including the
WSTS / ECIA / SEMI market_series), this only UPSERTS the requested tickers, so existing
companies and all market data are preserved. Tickers must already exist in the universe
YAML (config/universe/*.yaml).

    $env:PYTHONPATH = "src"
    .\.venv\Scripts\python.exe scripts\add_companies.py SWKS QRVO HIMX
    .\.venv\Scripts\python.exe scripts\add_companies.py --new      # any universe ticker not yet in DB
"""
from __future__ import annotations

import sqlite3
import sys

from emi import db
from emi.config import DB_PATH, iter_universe
from emi.ingest import yahoo


def existing_tickers() -> set[str]:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        return {r[0] for r in conn.execute("SELECT ticker FROM companies").fetchall()}
    finally:
        conn.close()


def main() -> None:
    args = sys.argv[1:]
    universe = list(iter_universe())
    if args == ["--new"]:
        have = existing_tickers()
        want = [r for r in universe if r["ticker"] not in have]
    else:
        wanted = {a.upper() for a in args}
        want = [r for r in universe if r["ticker"].upper() in wanted]
    if not want:
        print("Nothing to add (no matching universe tickers).")
        return

    db.init_db()
    comp_rows, fin_all, est_all, resolved, missing = [], [], [], [], []
    for i, r in enumerate(want, 1):
        sym = r["ticker"]
        blob = yahoo.fetch_ticker(sym)
        fr = yahoo.extract_financials(sym, blob)
        er = yahoo.extract_estimates(sym, blob)
        comp_rows.append({
            "ticker": sym, "name": blob.get("name") or r["name"],
            "layer": r["layer"], "layer_name": r["layer_name"],
            "sublayer": r["sublayer"], "sublayer_name": r["sublayer_name"],
            "region": r["region"], "end_market": r["end_market"],
            "currency": blob.get("currency"), "market_cap": blob.get("market_cap"), "cik": None,
        })
        fin_all += fr
        est_all += er
        (resolved if fr else missing).append(sym)
        print(f"  [{i}/{len(want)}] {sym:10s} fin={len(fr)} est={len(er)}", flush=True)

    db.upsert_companies(comp_rows)
    db.upsert_financials(fin_all)
    db.upsert_estimates(est_all)
    print(f"\nAdded/updated {len(comp_rows)} companies | with financials {len(resolved)} | "
          f"empty {len(missing)}{(' -> ' + str(missing)) if missing else ''}")
    print("Next: rebuild data.json  ->  python -m emi.report.build")


if __name__ == "__main__":
    main()
