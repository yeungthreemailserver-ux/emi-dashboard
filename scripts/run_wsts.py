r"""Ingest WSTS Historical Billings Report into market_series.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\run_wsts.py
"""
from __future__ import annotations

import sqlite3

from emi import db
from emi.config import DB_PATH
from emi.ingest import wsts


def main() -> None:
    db.init_db()
    path = wsts.download_hbr(refresh=True)
    rows = wsts.parse_hbr(path)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM market_series WHERE source='wsts'")
    conn.commit()
    conn.close()
    db.upsert_market_series(rows)

    # summary
    conn = sqlite3.connect(str(DB_PATH))
    n = conn.execute("SELECT COUNT(*) FROM market_series WHERE source='wsts'").fetchone()[0]
    last = conn.execute("SELECT period, value FROM market_series WHERE series='billings_worldwide' ORDER BY period DESC LIMIT 1").fetchone()
    last3 = conn.execute("SELECT period, value FROM market_series WHERE series='billings_worldwide_3mma' ORDER BY period DESC LIMIT 1").fetchone()
    yago = None
    if last:
        ym = last[0]
        prevy = f"{int(ym[:4])-1}{ym[4:]}"
        row = conn.execute("SELECT value FROM market_series WHERE series='billings_worldwide' AND period=?", (prevy,)).fetchone()
        yago = row[0] if row else None
    conn.close()

    print(f"WSTS rows ingested: {n}")
    if last:
        print(f"latest worldwide ({last[0]}): ${last[1]/1e9:.1f}B/month")
    if last3:
        print(f"latest worldwide 3MMA ({last3[0]}): ${last3[1]/1e9:.1f}B")
    if last and yago:
        print(f"YoY: {(last[1]/yago-1)*100:+.1f}%  (vs {prevy} ${yago/1e9:.1f}B)")


if __name__ == "__main__":
    main()
