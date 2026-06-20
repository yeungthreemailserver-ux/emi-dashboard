r"""Dump recent raw financial rows for one ticker to debug extraction quality.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\diag.py NVDA
"""
import sqlite3
import sys

import pandas as pd

from emi.config import DB_PATH

ticker = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()
conn = sqlite3.connect(str(DB_PATH))
df = pd.read_sql_query(
    "SELECT metric, period_end, frame, value, fy, fp, form, filed "
    "FROM financials WHERE ticker = ? ORDER BY metric, period_end",
    conn, params=[ticker],
)
conn.close()

pd.set_option("display.max_rows", 400)
pd.set_option("display.width", 200)
print(f"### {ticker} — {len(df)} rows")
for m in ["revenue", "cost_of_revenue", "gross_profit", "operating_income", "inventory"]:
    sub = df[df["metric"] == m].tail(6)
    print(f"\n== {m} ==")
    print(sub.to_string(index=False) if not sub.empty else "  (none)")
