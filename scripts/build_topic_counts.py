r"""Build REAL topic-mention counts from actual transcripts (token-free) -> data/topic_counts.json.

For each company we hold the URLs of its last 5 earnings calls, mapped newest->oldest onto the
5 period slots. We fetch each (urllib; PDFs via pypdf), strip to the transcript body, and count the
20 topics with the keyword lexicon in count_topics.py. Then per company we nearest-fill any quarter
we couldn't fetch (e.g. investing.com 403 / paywall), and sum across companies per quarter.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\build_topic_counts.py
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT
from count_topics import _COMPILED, _SENT, count_topics, to_body
from count_topics import topic_sentiment
from parse_transcript import segments
from lang import cached_en, html_to_text, looks_like_transcript

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
CACHE = ROOT / "data" / "transcripts"

# Single source of truth: data/manifest.json (ticker/name/layer/sublayer/core/source/urls).
# Add a company there (one entry) + rerun -> it flows through. urls are NEWEST-FIRST, one per period.
_MF = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
PERIODS = _MF["periods"]                                          # oldest -> newest
MANIFEST = {c["ticker"]: c["urls"] for c in _MF["companies"]}     # ticker -> URLs (newest-first)
TOPIC_IDS = list(_COMPILED.keys())


def fetch_text(url: str, key: str) -> str | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    is_pdf = url.lower().endswith(".pdf") or "/document/ppt/" in url
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]  # URL in the key → changed URL auto-refetches
    cache = CACHE / f"{key}_{h}.{'pdf' if is_pdf else 'html'}"
    raw = None
    if cache.exists():
        raw = cache.read_bytes()
    else:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                raw = urllib.request.urlopen(req, timeout=45).read()
                cache.write_bytes(raw)
                break
            except Exception as e:  # noqa: BLE001
                print(f"    fetch attempt {attempt + 1} failed: {type(e).__name__}")
                time.sleep(2)
    if raw is None:
        return (None, None)
    if is_pdf:
        try:
            import pypdf
            rd = pypdf.PdfReader(io.BytesIO(raw))
            return (re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in rd.pages)), "pdf")
        except Exception as e:  # noqa: BLE001
            print(f"    pdf parse failed: {type(e).__name__}")
            return (None, None)
    return (raw.decode("utf-8", "ignore"), "html")


def clean_text(raw, kind):
    """Return only management+analyst speech. HTML -> parse verbatim transcript -> analysis_text
    (reject non-verbatim pages); PDF -> official IR text as-is."""
    if kind == "pdf":
        return raw
    if kind == "html":
        seg = segments(raw)
        if seg.get("ok"):
            return seg["analysis_text"]
        gen = html_to_text(raw)                       # generic source (IR / Investing.com): use if it's really a transcript
        return gen if looks_like_transcript(gen) else None
    return None


def nearest_fill(vals: list[int | None]) -> list[int]:
    """Fill None slots from the nearest non-None slot (ties -> earlier)."""
    n = len(vals)
    out = list(vals)
    for i in range(n):
        if out[i] is None:
            best, bestd = None, 99
            for j in range(n):
                if vals[j] is not None and abs(j - i) < bestd:
                    best, bestd = vals[j], abs(j - i)
            out[i] = best if best is not None else 0
    return out


SEGS = ["all", "prepared", "ceo", "cfo", "q", "a"]  # speech segments (ceo/cfo = prepared split; q = analyst, a = mgmt)


def main() -> None:
    per_company = {}   # ticker -> {topic: {seg: [5 raw counts]}}
    per_sent = {}      # ticker -> {topic: {seg: [5 net sentiment -1..1 / null]}}
    quotes = {}        # ticker -> {topic: "representative management sentence"} (latest call)
    coverage = {}
    NP = len(PERIODS)
    for tk, urls in MANIFEST.items():
        slots = [None] * NP  # align newest-first urls to the NEWEST period slots (a partial history fills recent quarters, not oldest)
        for _i, _u in enumerate(urls[:NP]):
            slots[NP - 1 - _i] = _u
        got, segmentable = [], False
        raw = {tid: {sg: [None] * NP for sg in SEGS} for tid in TOPIC_IDS}
        sent = {tid: {sg: [None] * NP for sg in SEGS} for tid in TOPIC_IDS}
        for si, url in enumerate(slots):
            if not url:
                continue
            key = f"{tk}_{PERIODS[si]}"
            en = cached_en(key)   # translated non-English call -> use English body (whole-call 'all' segment only)
            if en is not None:
                print(f"  {tk} {PERIODS[si]} <- [translated EN]")
                texts = {sg: "" for sg in SEGS}; texts["all"] = en
            else:
                print(f"  {tk} {PERIODS[si]} <- {url[:70]}")
                doc, kind = fetch_text(url, key=key)
                if kind == "html":
                    seg = segments(doc)
                    if seg.get("ok"):
                        texts = {"all": seg["analysis_text"], "prepared": seg["prepared"], "ceo": seg["ceo"], "cfo": seg["cfo"], "q": seg["q"], "a": seg["a"]}
                        segmentable = True
                    else:   # non-MarketBeat source (IR site / Investing.com): generic extraction if it really is a transcript
                        gen = html_to_text(doc)
                        if looks_like_transcript(gen):
                            texts = {sg: "" for sg in SEGS}; texts["all"] = gen
                            print("    (generic transcript extraction)")
                        else:
                            print("    SKIP (not a verbatim transcript)")
                            continue
                elif kind == "pdf":
                    texts = {sg: "" for sg in SEGS}; texts["all"] = doc   # PDFs can't be segmented
                else:
                    continue
            if not texts["all"] or len(texts["all"].split()) < 600:
                print(f"    SKIP ({len(texts['all'].split()) if texts['all'] else 0} words)")
                continue
            got.append(PERIODS[si])
            for sg in SEGS:
                has = bool(texts[sg].strip())
                c = count_topics(texts[sg]) if has else None
                sc = topic_sentiment(texts[sg]) if has else None
                for tid in TOPIC_IDS:
                    raw[tid][sg][si] = c[tid] if c else 0
                    sent[tid][sg][si] = sc[tid] if sc else None
            # representative MANAGEMENT quote per topic (prepared + answers; PDF -> all). Latest processed quarter wins.
            mgmt = (texts["ceo"] + " " + texts["cfo"] + " " + texts["a"]).strip() or texts["all"]
            msents = _SENT.split(mgmt)
            for tid in TOPIC_IDS:
                hits = [s.strip() for s in msents if any(rx.search(s) for rx in _COMPILED[tid])]
                if hits:
                    quotes.setdefault(tk, {})[tid] = max(hits, key=len)[:220]
        keep = SEGS if segmentable else ["all"]   # PDF companies expose only 'all'
        per_company[tk] = {tid: {sg: nearest_fill(raw[tid][sg]) for sg in keep} for tid in TOPIC_IDS}
        per_sent[tk] = {tid: {sg: sent[tid][sg] for sg in keep} for tid in TOPIC_IDS}  # keep nulls (no fill)
        coverage[tk] = got
        print(f"  -> {tk}: real quarters {got}")

    n = len(per_company)
    # aggregate (default 'all' segment) = AVERAGE MENTIONS PER COMPANY
    agg = {tid: [round(sum(per_company[tk][tid]["all"][si] for tk in per_company) / n, 1) for si in range(len(PERIODS))] for tid in TOPIC_IDS}
    breadth = {tid: [sum(1 for tk in per_company if per_company[tk][tid]["all"][si] >= 1) for si in range(len(PERIODS))] for tid in TOPIC_IDS}
    out = {"periods": PERIODS, "unit": "percompany", "segments": SEGS, "series": agg, "breadth": breadth,
           "per_company": per_company, "sentiment": per_sent, "quotes": quotes, "coverage": coverage}
    (ROOT / "data" / "topic_counts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nwrote data/topic_counts.json  (avg mentions/company, segmented all/prepared/q/a)")
    for t in sorted(agg, key=lambda t: -agg[t][-1])[:6]:
        print(f"  {t:<14} now={agg[t][-1]:<6} series={agg[t]}")


if __name__ == "__main__":
    main()
