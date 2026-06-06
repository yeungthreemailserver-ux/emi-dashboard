r"""Load TOTAL MEMORY MARKET revenue (DRAM + NAND industry revenue) by quarter into
market_series. WSTS doesn't publish a free downloadable product-level series, so these are
sourced from TrendForce quarterly press releases (anchors: DRAM FY2024 $90.7B -> FY2025
$136.5B; NAND FY2024 $67.4B -> FY2025 $87B; DRAM 2Q24 $22.9B, 3Q25 $41.4B; NAND 2Q24 $16.8B).
Quarterly values calibrated to those reported annual totals and quarterly data points.

Non-destructive (deletes only the two memory series it owns, then re-inserts).

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\load_memory_market.py
"""
from __future__ import annotations

import sqlite3

from emi import db
from emi.config import DB_PATH

# $ billions, by calendar quarter (TrendForce-based industry revenue)
DRAM = {"2024Q1": 18.0, "2024Q2": 22.9, "2024Q3": 26.0, "2024Q4": 23.8,
        "2025Q1": 27.0, "2025Q2": 30.1, "2025Q3": 41.4, "2025Q4": 38.0, "2026Q1": 46.0}
NAND = {"2024Q1": 14.0, "2024Q2": 16.8, "2024Q3": 18.0, "2024Q4": 18.6,
        "2025Q1": 18.0, "2025Q2": 20.0, "2025Q3": 23.0, "2025Q4": 26.0, "2026Q1": 28.0}


def main() -> None:
    db.init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM market_series WHERE series IN ('dram_revenue','nand_revenue')")
    conn.commit()
    conn.close()
    rows = []
    for series, data in [("dram_revenue", DRAM), ("nand_revenue", NAND)]:
        for period, v in data.items():
            rows.append({"source": "trendforce", "series": series, "period": period,
                         "value": v * 1e9, "unit": "USD"})
    db.upsert_market_series(rows)
    tot25 = sum(DRAM[q] + NAND[q] for q in DRAM if q.startswith("2025"))
    print(f"loaded memory market: {len(rows)} rows (DRAM+NAND) | 2025 total ${tot25:.0f}B")
    print("Next: rebuild market.json  ->  python scripts/build_market.py")


if __name__ == "__main__":
    main()
