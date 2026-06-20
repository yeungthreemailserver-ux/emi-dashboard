r"""Dump the 'Outlook' snippet of US filers the rule-based parser missed, so Claude can
extract guidance directly (no external LLM API needed).

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\dump_missed_outlooks.py
"""
import sqlite3

from emi.config import DB_PATH, iter_universe
from emi.ingest.edgar import load_cik_map
from emi.ingest.guidance import get_outlook_text

conn = sqlite3.connect(str(DB_PATH))
try:
    have = {r[0] for r in conn.execute("SELECT DISTINCT ticker FROM guidance").fetchall()}
finally:
    conn.close()

cikmap = load_cik_map()
todo = [r for r in iter_universe() if r.get("region") == "US" and r["ticker"] not in have]
print(f"# missed US filers: {len(todo)}\n")

found = 0
for r in todo:
    tk = r["ticker"]
    cik = cikmap.get(tk)
    if not cik:
        continue
    ot = get_outlook_text(tk, cik)
    if not ot:
        continue
    found += 1
    snip = " ".join(ot["text"].split())[:650]
    print(f"### {tk} | filed {ot['filed']} | accn {ot['accn']}")
    print(snip)
    print()
print(f"# companies with an outlook snippet: {found}")
