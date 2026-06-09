r"""Gap-safe MarketBeat backfill for companies missing historical quarters.

For each TICKER:EXCH/MBTICKER, discovers MarketBeat transcript URLs, maps each call's
REPORT DATE to the calendar quarter it reports (not naive right-align, so sparse coverage
doesn't mislabel), and for any quarter in PERIODS the company is still MISSING, fetches +
cleans + VERIFIES it's a real transcript, then writes it to the per-period cached_en slot
(data/transcripts_en/{TICKER}_{PERIOD}.txt) — which build_topic_counts reads first.

Stubs (e.g. foreign-ADR earnings-report pages with no call text) fail the transcript guard
and are skipped, so we never silently ingest junk.

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\backfill_mb.py NXPI:NASDAQ/NXPI UMC:NYSE/UMC ...
"""
from __future__ import annotations
import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT
from build_topic_counts import fetch_text, PERIODS, clean_text
from discover_urls import discover
import lang
from parse_transcript import segments

import json
COV = json.loads((ROOT / "data" / "topic_counts.json").read_text(encoding="utf-8")).get("coverage", {})


def period_of(y: int, m: int) -> str:
    """Calendar quarter a call reported in month m/year y is reporting ON (call ~1mo after q-end)."""
    if m in (4, 5, 6):   return f"{y}Q1"
    if m in (7, 8, 9):   return f"{y}Q2"
    if m in (10, 11, 12):return f"{y}Q3"
    return f"{y-1}Q4"    # Jan-Mar -> prior Q4


def clean_for_cache(html: str) -> str | None:
    """Same extraction build_topic_counts uses: MarketBeat segments -> analysis_text, else generic."""
    seg = segments(html)
    if seg.get("ok") and seg.get("analysis_text"):
        return seg["analysis_text"]
    gen = lang.html_to_text(html)
    return gen if lang.looks_like_transcript(gen) else None


def main():
    pairs = sys.argv[1:]
    if not pairs:
        print("usage: backfill_mb.py TICKER:EXCH/MBTICKER ..."); return
    total_filled = 0
    for spec in pairs:
        tk, rest = spec.split(":", 1)
        exch, mbt = rest.split("/", 1)
        have = set(COV.get(tk, []))
        urls = discover(mbt, exch, n=8)
        # newest-first: first url to claim a period wins (dedup spurious extra calls)
        by_period: dict[str, str] = {}
        for u in urls:
            m = re.search(r"reports/(\d{4})-(\d{1,2})-(\d{1,2})", u)
            if not m: continue
            per = period_of(int(m.group(1)), int(m.group(2)))
            if per in PERIODS and per not in have and per not in by_period:
                by_period[per] = u
        if not by_period:
            print(f"{tk:6} ({mbt}): nothing missing/available to fill (have {sorted(have)})"); continue
        filled = []
        for per, u in sorted(by_period.items()):
            key = f"{tk}_{per}"
            doc, kind = fetch_text(u, key=key + "_bf")
            if kind != "html" or not doc:
                print(f"  {tk} {per}: FETCH FAIL"); continue
            txt = clean_for_cache(doc)
            if not txt or not lang.looks_like_transcript(txt):
                print(f"  {tk} {per}: NOT A TRANSCRIPT (stub) -> skip"); continue
            out = lang.en_file(key)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(txt, encoding="utf-8")
            filled.append(per); total_filled += 1
        print(f"{tk:6} ({mbt}): filled {filled or '—'}")
    print(f"\nTOTAL filled {total_filled} (ticker,quarter) cached_en slots -> re-run build_topic_counts")


if __name__ == "__main__":
    main()
