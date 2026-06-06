r"""Phase 1 ingestion entrypoint: universe -> companies + EDGAR financials -> SQLite.

Usage (from repo root):
    $env:PYTHONPATH = "src"
    .\.venv\Scripts\python.exe scripts\run_ingest.py
"""
from __future__ import annotations

from emi import db
from emi.config import iter_companies, load_universe
from emi.ingest import edgar


def main() -> None:
    universe = load_universe()
    companies = list(iter_companies(universe))

    db.init_db()
    cik_map = edgar.load_cik_map()

    company_rows = []
    for c in companies:
        ticker = (c.get("ticker") or "").upper()
        company_rows.append({
            "ticker": ticker,
            "cik": c.get("cik") or cik_map.get(ticker),
            "name": c.get("name"),
            "tier": c.get("tier"),
            "region": c.get("region"),
            "listing": c.get("listing"),
            "end_markets": ",".join(c.get("end_markets", []) or []),
        })
    db.upsert_companies(company_rows)

    fin_rows, resolved, missing = edgar.ingest(companies)
    db.upsert_financials(fin_rows)

    print(f"Universe companies : {len(company_rows)}")
    print(f"EDGAR resolved      : {len(resolved)}")
    print(f"Financial rows      : {len(fin_rows)}")
    if missing:
        print(f"No EDGAR data ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()
