r"""Dump one ticker's stored companies row + financials + consensus (v2 sanity check).

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\diag_v2.py NVDA
"""
import sqlite3
import sys

import pandas as pd

from emi.config import DB_PATH

tk = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()
conn = sqlite3.connect(str(DB_PATH))
comp = pd.read_sql_query("SELECT * FROM companies WHERE ticker=?", conn, params=[tk])
fin = pd.read_sql_query(
    "SELECT metric,period_end,frame,value,unit FROM financials WHERE ticker=? ORDER BY metric,period_end",
    conn, params=[tk])
est = pd.read_sql_query(
    "SELECT metric,period,avg,low,high,num_analysts,growth,currency FROM estimates WHERE ticker=? ORDER BY metric,period",
    conn, params=[tk])
conn.close()

if comp.empty:
    print(f"{tk}: not in DB")
    raise SystemExit

print(comp.T.to_string())
print("\nFinancials (last 3 per metric):")
for m, g in fin.groupby("metric"):
    cur = g["unit"].iloc[0]
    print(f"  {m:16s}: " + " | ".join(f"{r.period_end}={r.value/1e9:.2f}B {cur}" for r in g.tail(3).itertuples()))
print("\nConsensus estimates:")
print(est.to_string(index=False) if not est.empty else "  (none)")
