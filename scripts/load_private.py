r"""Load strategic PRIVATE champions that have no public listing (so yfinance/EDGAR can't
reach them) but are too important to omit — e.g. China's memory leaders CXMT & YMTC and
Huawei's HiSilicon. Quarterly revenue here is a PUBLIC INDUSTRY ESTIMATE (TrendForce /
Omdia / DigiTimes / Reuters reporting), NOT reported financials — flagged as such in the UI.

Idempotent and NON-destructive (upsert only; never resets the DB, so WSTS survives).

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\load_private.py
"""
from __future__ import annotations

from emi import db

# period_end for each calendar quarter we estimate
PERIODS = ["2023-03-31", "2023-06-30", "2023-09-30", "2023-12-31",
           "2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
           "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"]

# company meta + quarterly revenue ESTIMATE in USD billions (public-report based)
PRIVATE = [
    {"ticker": "CXMT", "name": "ChangXin Memory (CXMT) [est.]", "sublayer": "3.4",
     "sublayer_name": "Memory & Storage",
     # 2023 ramping; 2025 full-year ~CNY 55-58B (~$8B); 2026 surging on the memory up-cycle
     "rev": [0.4, 0.5, 0.6, 0.7, 0.7, 0.8, 1.0, 1.3, 1.1, 1.4, 2.0, 3.4, 7.0]},
    {"ticker": "YMTC", "name": "Yangtze Memory (YMTC) [est.]", "sublayer": "3.4",
     "sublayer_name": "Memory & Storage",
     # NAND share 4% -> 8%+; revenue ~$1.6B rising
     "rev": [0.3, 0.3, 0.4, 0.4, 0.4, 0.5, 0.5, 0.6, 0.7, 0.9, 1.1, 1.3, 1.5]},
    {"ticker": "HISILICON", "name": "HiSilicon (Huawei) [est.]", "sublayer": "3.2",
     "sublayer_name": "Core Compute & Logic",
     # ~$11B FY2024 on Kirin + Ascend AI ramp
     "rev": [1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 3.5, 3.5, 4.0, 4.5, 5.0, 5.5]},
]


def main() -> None:
    db.init_db()
    comp_rows, fin_rows = [], []
    for p in PRIVATE:
        comp_rows.append({
            "ticker": p["ticker"], "name": p["name"],
            "layer": "L3", "layer_name": "Component Manufacturers",
            "sublayer": p["sublayer"], "sublayer_name": p["sublayer_name"],
            "region": "CN", "end_market": None,
            "currency": "USD", "market_cap": None, "cik": None,
        })
        for period, rev_b in zip(PERIODS, p["rev"]):
            fin_rows.append({
                "ticker": p["ticker"], "cik": None, "metric": "revenue",
                "period_end": period, "fy": int(period[:4]),
                "fp": f"Q{(int(period[5:7]) - 1) // 3 + 1}", "frame": "quarterly",
                "value": rev_b * 1e9, "unit": "USD", "form": "ESTIMATE",
                "filed": None, "source": "estimate",
            })
    db.upsert_companies(comp_rows)
    db.upsert_financials(fin_rows)
    print(f"loaded {len(comp_rows)} private champions ({', '.join(p['ticker'] for p in PRIVATE)}) "
          f"with {len(fin_rows)} estimated quarterly revenue rows")
    print("Next: rebuild data.json  ->  python -m emi.report.build")


if __name__ == "__main__":
    main()
