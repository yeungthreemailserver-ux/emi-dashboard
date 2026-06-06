r"""v2 ingestion: layered universe -> companies + Yahoo financials + consensus -> SQLite.

    $env:PYTHONPATH = "src"
    .\.venv\Scripts\python.exe scripts\run_ingest_v2.py                 # all companies
    .\.venv\Scripts\python.exe scripts\run_ingest_v2.py --limit 10      # first 10
    .\.venv\Scripts\python.exe scripts\run_ingest_v2.py NVDA 2330.TW    # specific tickers
"""
from __future__ import annotations

import sys

from emi import db
from emi.config import iter_universe
from emi.ingest import yahoo


def select_rows(rows, args):
    if not args:
        return rows
    if args[0] == "--limit":
        return rows[: int(args[1])]
    want = {a.upper() for a in args}
    return [r for r in rows if r["ticker"].upper() in want]


def main() -> None:
    rows = select_rows(list(iter_universe()), sys.argv[1:])
    db.reset_db()

    comp_rows, fin_all, est_all, resolved, missing = [], [], [], [], []
    n = len(rows)
    for i, r in enumerate(rows, 1):
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
        if i % 20 == 0 or i == n:
            print(f"  [{i}/{n}] {sym:10s} fin={len(fin_all)} est={len(est_all)}", flush=True)

    db.upsert_companies(comp_rows)
    db.upsert_financials(fin_all)
    db.upsert_estimates(est_all)

    print(f"\nCompanies        : {len(comp_rows)}")
    print(f"With financials  : {len(resolved)}")
    print(f"Empty (no data)  : {len(missing)}" + (f"  -> {missing}" if missing else ""))
    print(f"Financial rows   : {len(fin_all)}")
    print(f"Estimate rows    : {len(est_all)}")


if __name__ == "__main__":
    main()
