r"""Pilot C — manually backfill 2023Q1–2024Q4 quarterly revenue for key NON-US semiconductor
companies that yfinance only gives ~5 quarters for. These are REPORTED figures compiled from
company quarterly earnings releases, in native currency (source='manual'). They merge UNDER
yfinance (which wins for 2025Q1+), filling only the older quarters — extending the matched-panel
exclusion windows (esp. Memory & Foundry) from ~5q to ~13q.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\load_history.py
"""
from __future__ import annotations

from emi import db

PERIODS = ["2023-03-31", "2023-06-30", "2023-09-30", "2023-12-31",
           "2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]

# ticker -> (unit, [revenue per quarter in native units, same order as PERIODS])
# SK hynix: KRW trillion; TSMC & MediaTek: TWD billion  (reported quarterly net revenue)
HISTORY = {
    "000660.KS": ("KRW", [5.09e12, 7.31e12, 9.07e12, 11.31e12, 12.43e12, 16.42e12, 17.57e12, 19.77e12]),
    "2330.TW":   ("TWD", [508.6e9, 480.8e9, 546.7e9, 625.5e9, 592.6e9, 673.5e9, 759.7e9, 868.5e9]),
    "2454.TW":   ("TWD", [95.7e9, 112.5e9, 124.0e9, 101.2e9, 132.1e9, 127.3e9, 131.6e9, 139.6e9]),
}


def main() -> None:
    db.init_db()
    rows = []
    for tk, (unit, vals) in HISTORY.items():
        for period, v in zip(PERIODS, vals):
            rows.append({
                "ticker": tk, "cik": None, "metric": "revenue",
                "period_end": period, "fy": int(period[:4]),
                "fp": f"Q{(int(period[5:7]) - 1) // 3 + 1}", "frame": "quarterly",
                "value": v, "unit": unit, "form": "MANUAL", "filed": None, "source": "manual",
            })
    db.upsert_financials(rows)
    print(f"backfilled {len(rows)} quarterly revenue rows for {len(HISTORY)} companies "
          f"({', '.join(HISTORY)}) across {PERIODS[0]}..{PERIODS[-1]}")
    print("Next: rebuild data.json  ->  python -m emi.report.build")


if __name__ == "__main__":
    main()
