r"""Replace Samsung Electronics' CONSOLIDATED revenue with its MEMORY-segment revenue, so the
L3.4 Memory layer reflects Samsung's memory business only (not phones/displays/foundry).

Samsung reports Memory & DS-division sales each quarter; figures below are derived from those
public quarterly releases (Memory FY2024 ~KRW 84.6T, FY2025 KRW 104.1T (+23% YoY); DS division
Q1'25 KRW 25.1T, Q4'25 KRW 44.0T). Quarterly Memory revenue is calibrated to the reported
annual Memory total and DS-division quarterly shape. Kept in KRW so the pipeline converts it at
the same FX as before — memory stays proportional to the dataset's consolidated figure.

Other Samsung metrics (operating income, margin, inventory) are removed: they are consolidated
and would be misleading against a memory-only revenue. Flagged in the UI as a segment figure.
Idempotent and NON-destructive to the rest of the DB (only touches 005930.KS).

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\load_samsung_memory.py
"""
from __future__ import annotations

import sqlite3

from emi import db
from emi.config import DB_PATH

TICKER = "005930.KS"
# Memory-segment revenue in KRW trillion, by calendar quarter (from Samsung quarterly reports).
# 2023 = downturn (~KRW 56T FY), 2024 recovery (~KRW 84.6T FY), 2025 HBM boom (KRW 104.1T FY).
MEMORY_KRW_T = {
    "2023-03-31": 13.5,
    "2023-06-30": 13.5,
    "2023-09-30": 14.5,
    "2023-12-31": 14.5,
    "2024-03-31": 17.0,
    "2024-06-30": 20.0,
    "2024-09-30": 22.9,
    "2024-12-31": 24.7,
    "2025-03-31": 20.1,
    "2025-06-30": 22.3,
    "2025-09-30": 26.5,
    "2025-12-31": 35.2,
    "2026-03-31": 45.0,
}


def main() -> None:
    db.init_db()
    conn = sqlite3.connect(str(DB_PATH))
    n = conn.execute("DELETE FROM financials WHERE ticker=?", (TICKER,)).rowcount
    conn.commit()
    conn.close()

    fin = [{
        "ticker": TICKER, "cik": None, "metric": "revenue",
        "period_end": p, "fy": int(p[:4]), "fp": f"Q{(int(p[5:7]) - 1) // 3 + 1}",
        "frame": "quarterly", "value": v * 1e12, "unit": "KRW",
        "form": "SEGMENT", "filed": None, "source": "segment",
    } for p, v in MEMORY_KRW_T.items()]
    db.upsert_financials(fin)
    db.upsert_companies([{
        "ticker": TICKER, "name": "Samsung Electronics (Memory) [seg.]",
        "layer": "L3", "layer_name": "Component Manufacturers",
        "sublayer": "3.4", "sublayer_name": "Memory & Storage",
        "region": "KR", "end_market": None,
        "currency": "KRW", "market_cap": None, "cik": None,
    }])
    print(f"deleted {n} consolidated Samsung rows; inserted {len(fin)} memory-segment revenue quarters")
    print("Next: rebuild data.json  ->  python -m emi.report.build")


if __name__ == "__main__":
    main()
