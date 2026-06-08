r"""TRANSLATE-AT-INGEST — make the pipeline language-agnostic.

For every transcript in the manifest, fetch it, and if it is NOT English (e.g. Japanese 決算説明会, Korean,
Chinese A-share disclosures, Taiwan 法說會), translate the call to English once and cache it to
data/transcripts_en/{ticker}_{period}.txt. build_topic_counts / llm_dimension_reads then pick up the English
text automatically (the non-English call maps to the 'all' speech segment — we don't split CEO/CFO/Q&A for it).

Idempotent + concurrent. English transcripts are skipped (no cost). Key from openai_key.txt.

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\translate_transcripts.py [--workers 6]
"""
from __future__ import annotations
import argparse, re, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT
from build_topic_counts import fetch_text, MANIFEST, PERIODS
from parse_transcript import segments
import lang

_TAG = re.compile(r"(?is)<(script|style)\b.*?</\1>")
_TAGS = re.compile(r"(?s)<[^>]+>")


def html_to_text(doc):
    seg = segments(doc)
    if seg.get("ok") and seg.get("analysis_text"):
        return seg["analysis_text"]          # clean verbatim body when the parser succeeds
    t = _TAG.sub(" ", doc or "")             # else crude strip (non-English pages the parser can't segment)
    t = _TAGS.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def body_for(tk, period, url):
    doc, kind = fetch_text(url, key=f"{tk}_{period}")
    if not doc:
        return None
    return doc if kind == "pdf" else html_to_text(doc)


def work(tk, period, url):
    key = f"{tk}_{period}"
    if lang.cached_en(key) is not None:
        return tk, period, "cached"
    body = body_for(tk, period, url)
    if not body or len(body.split()) < 300:
        return tk, period, "no-text"
    if lang.looks_english(body):
        return tk, period, "english"
    lang.translate(body, key)                # translate + cache
    return tk, period, "TRANSLATED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--ticker", help="limit to one ticker")
    a = ap.parse_args()
    jobs = []
    for tk, urls in MANIFEST.items():
        if a.ticker and tk != a.ticker:
            continue
        slots = (urls[::-1] + [None] * len(PERIODS))[:len(PERIODS)]
        for si, url in enumerate(slots):
            if url:
                jobs.append((tk, PERIODS[si], url))
    print(f"scanning {len(jobs)} transcripts for non-English (translate -> English) · {a.workers} workers")
    done = {"cached": 0, "english": 0, "no-text": 0, "TRANSLATED": 0}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, *j) for j in jobs]
        for f in as_completed(futs):
            tk, period, status = f.result()
            done[status] = done.get(status, 0) + 1
            if status == "TRANSLATED":
                print(f"  {tk} {period}: TRANSLATED -> data/transcripts_en/{tk}_{period}.txt", flush=True)
    print(f"done: {done['TRANSLATED']} translated · {done['english']} already English · {done['cached']} cached · {done['no-text']} no-text")


if __name__ == "__main__":
    main()
