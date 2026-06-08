r"""ADD A COMPANY to the transcript roster (data/manifest.json) — the clean way to expand coverage.

Two sources:
  - MarketBeat (US + some ADRs): auto-discovers the last 5 verbatim transcript URLs and VERIFIES the latest
    actually parses as a transcript before adding.
  - Manual URLs (IR pages / PDFs, any language): pass --urls u1,u2,... newest-first (PDFs are most reliable).

After adding, run:  refresh.py update   (counts -> reads -> synth -> readiness -> bundle; translates non-English).

    # MarketBeat ADR:
    .\.venv\Scripts\python.exe scripts\add_company.py --ticker STM --name STMicroelectronics --layer L3 --sub 3.1 --mb NYSE/STM
    # Manual IR PDFs (e.g. a Japanese/Korean transcript):
    .\.venv\Scripts\python.exe scripts\add_company.py --ticker 6857.T --name Advantest --layer L2 --sub 2.1 --urls "https://.../q1.pdf,https://.../q4.pdf"
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT
from build_topic_counts import fetch_text
from parse_transcript import segments
from lang import html_to_text, looks_like_transcript

MANIFEST = ROOT / "data" / "manifest.json"


def verify(url, key):
    doc, kind = fetch_text(url, key=key)
    if not doc:
        return False, "fetch failed"
    if kind == "pdf":
        return (len(doc.split()) > 300), f"pdf {len(doc.split())} words"
    seg = segments(doc)
    if seg.get("ok"):
        return True, f"verbatim transcript {len(seg['analysis_text'].split())} words"
    gen = html_to_text(doc)
    if looks_like_transcript(gen):
        return True, f"generic transcript {len(gen.split())} words"
    return False, f"not a transcript ({len(gen.split())} words)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--layer", required=True)
    ap.add_argument("--sub", required=True)
    ap.add_argument("--mb", help="MarketBeat EXCH/TICKER (auto-discover)")
    ap.add_argument("--urls", help="comma-separated transcript URLs, newest-first (manual)")
    a = ap.parse_args()
    mf = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if any(c["ticker"] == a.ticker for c in mf["companies"]):
        print(f"{a.ticker} already in manifest"); return
    if a.mb:
        sys.path.insert(0, str(ROOT / "scripts"))
        from discover_urls import discover
        exch, tk = a.mb.split("/")
        urls = discover(tk, exch, n=5)
        source = "marketbeat"
    elif a.urls:
        urls = [u.strip() for u in a.urls.split(",") if u.strip()]
        source = "ir_manual"
    else:
        print("need --mb or --urls"); return
    if not urls:
        print("no URLs found"); return
    ok, msg = verify(urls[0], f"{a.ticker}_verify")
    print(f"{a.ticker}: {len(urls)} urls · latest verify: {msg}")
    if ok is False:
        print("  latest URL did not yield usable text — NOT added (check the source)"); return
    entry = {"ticker": a.ticker, "name": a.name, "layer": a.layer, "sublayer": a.sub,
             "core": False, "source": source, "urls": urls}
    if a.mb:
        entry["mb"] = a.mb
    mf["companies"].append(entry)
    MANIFEST.write_text(json.dumps(mf, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  added {a.name} ({a.ticker}) L{a.layer}/{a.sub} · {len(urls)} urls · run: refresh.py update")


if __name__ == "__main__":
    main()
