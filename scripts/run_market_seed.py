r"""Load config/market_seed.csv (ECIA book-to-bill, SEMI billings — SEED values to be
replaced with official figures) into market_series.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\run_market_seed.py
"""
import csv
import sqlite3

from emi import db
from emi.config import CONFIG_DIR, DB_PATH


def main() -> None:
    db.init_db()
    rows = []
    with open(CONFIG_DIR / "market_seed.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"source": r["source"], "series": r["series"], "period": r["period"],
                         "value": float(r["value"]), "unit": r["unit"]})
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM market_series WHERE source IN ('ecia','semi')")
    conn.commit()
    conn.close()
    db.upsert_market_series(rows)
    print(f"seeded market rows: {len(rows)} (ecia + semi)")


if __name__ == "__main__":
    main()
