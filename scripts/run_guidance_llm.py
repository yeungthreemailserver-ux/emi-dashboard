r"""LLM guidance recovery — runs only on US filers the rule-based parser MISSED.

Set a free OpenAI-compatible endpoint first (see emi.ingest.guidance_llm docstring), e.g.:
    $env:EMI_LLM_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
    $env:EMI_LLM_MODEL = "gemini-2.0-flash"
    $env:EMI_LLM_KEY = "<your free AI Studio key>"
    $env:PYTHONPATH = "src"
    .\.venv\Scripts\python.exe scripts\run_guidance_llm.py
"""
from __future__ import annotations

import sqlite3

from emi import db
from emi.config import DB_PATH, iter_universe
from emi.ingest import guidance_llm
from emi.ingest.edgar import load_cik_map
from emi.ingest.guidance import get_outlook_text


def _covered() -> set:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        return {r[0] for r in conn.execute("SELECT DISTINCT ticker FROM guidance").fetchall()}
    except sqlite3.Error:
        return set()
    finally:
        conn.close()


def main() -> None:
    if not guidance_llm.configured():
        print("LLM not configured. Pick a FREE provider and set 3 env vars:\n"
              "  Gemini (free):  EMI_LLM_BASE=https://generativelanguage.googleapis.com/v1beta/openai  "
              "EMI_LLM_MODEL=gemini-2.0-flash  EMI_LLM_KEY=<AI Studio key>\n"
              "  Groq (free):    EMI_LLM_BASE=https://api.groq.com/openai/v1  "
              "EMI_LLM_MODEL=llama-3.3-70b-versatile  EMI_LLM_KEY=<groq key>\n"
              "  Ollama (local): EMI_LLM_BASE=http://localhost:11434/v1  EMI_LLM_MODEL=qwen2.5  (no key)")
        return

    db.init_db()
    cikmap = load_cik_map()
    have = _covered()
    todo = [r for r in iter_universe() if r.get("region") == "US" and r["ticker"] not in have]
    print(f"US filers missed by rule-based parser: {len(todo)} — recovering via LLM…")

    rows, got = [], 0
    for i, r in enumerate(todo, 1):
        tk, cik = r["ticker"], cikmap.get(r["ticker"])
        if not cik:
            continue
        ot = get_outlook_text(tk, cik)
        if not ot:
            continue
        try:
            g = guidance_llm.llm_extract(ot["text"])
        except Exception as e:
            print(f"  err {tk}: {e}")
            continue
        if not g:
            continue
        added = False
        rev = g.get("revenue") or {}
        if rev.get("mid"):
            rows.append({"ticker": tk, "metric": "revenue", "period_text": g.get("period"),
                         "mid": rev.get("mid"), "low": rev.get("low"), "high": rev.get("high"),
                         "filed": ot["filed"], "accn": ot["accn"], "raw": "LLM", "source": "edgar_8k_llm"})
            added = True
        gm = g.get("gross_margin") or {}
        if gm.get("mid") is not None:
            rows.append({"ticker": tk, "metric": "gross_margin", "period_text": g.get("period"),
                         "mid": gm.get("mid"), "low": None, "high": None,
                         "filed": ot["filed"], "accn": ot["accn"], "raw": "LLM", "source": "edgar_8k_llm"})
            added = True
        if added:
            got += 1
        if i % 10 == 0:
            print(f"  [{i}/{len(todo)}] recovered={got}", flush=True)

    db.upsert_guidance(rows)
    print(f"\nMissed: {len(todo)} | LLM-recovered companies: {got} | rows: {len(rows)}")
    print("Now rebuild: .\\.venv\\Scripts\\python.exe -m emi.report.build")


if __name__ == "__main__":
    main()
