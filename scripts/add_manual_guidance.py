r"""Guidance extracted directly by Claude from EDGAR 8-K outlook snippets that the
rule-based parser missed (table / bulleted formats). source = edgar_8k_claude.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\add_manual_guidance.py
"""
from emi import db

ROWS = [
    {"ticker": "AVT", "metric": "revenue", "period_text": "Q4 FY2026", "mid": 7.45e9, "low": 7.30e9, "high": 7.60e9,
     "filed": "2026-04-29", "accn": "0000008858-26-000040", "raw": "Outlook Q4 FY2026 Sales $7.30B-$7.60B, midpoint $7.45B", "source": "edgar_8k_claude"},
    {"ticker": "AMKR", "metric": "revenue", "period_text": "Q2 2026", "mid": 1.80e9, "low": 1.75e9, "high": 1.85e9,
     "filed": "2026-04-27", "accn": "0001047127-26-000017", "raw": "Business Outlook Q2 2026 net sales $1.75B-$1.85B", "source": "edgar_8k_claude"},
    {"ticker": "AMKR", "metric": "gross_margin", "period_text": "Q2 2026", "mid": 0.15, "low": None, "high": None,
     "filed": "2026-04-27", "accn": "0001047127-26-000017", "raw": "gross margin 14.5%-15.5%", "source": "edgar_8k_claude"},
    {"ticker": "AMAT", "metric": "revenue", "period_text": "Q3 FY2026", "mid": 8.95e9, "low": 8.45e9, "high": 9.45e9,
     "filed": "2026-05-14", "accn": "0001628280-26-035071", "raw": "Business Outlook Q3 FY2026 total revenue $8,950M +/- $500M", "source": "edgar_8k_claude"},
    {"ticker": "GRMN", "metric": "revenue", "period_text": "FY2026", "mid": 7.9e9, "low": None, "high": None,
     "filed": "2026-04-29", "accn": "0001193125-26-188907", "raw": "FY2026 guidance approximately $7.9 billion revenue", "source": "edgar_8k_claude"},
]

if __name__ == "__main__":
    db.init_db()
    n = db.upsert_guidance(ROWS)
    print(f"inserted/updated {n} Claude-extracted guidance rows")
