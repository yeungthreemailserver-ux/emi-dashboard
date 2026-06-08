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
from build_topic_counts import fetch_text, PERIODS
from parse_transcript import segments
import lang
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
    ap.add_argument("--textfile", help="pasted transcript file(s): 'path' (latest quarter) or 'PERIOD=path,PERIOD=path' (any language; auto-translated)")
    ap.add_argument("--period", default=PERIODS[-1], help="quarter for a single --textfile (default = latest)")
    a = ap.parse_args()
    mf = json.loads(MANIFEST.read_text(encoding="utf-8"))

    # --- manual paste: read local transcript file(s), cache as English (translate if needed), no URL needed ---
    if a.textfile:
        entries = []
        for part in a.textfile.split(","):
            part = part.strip()
            if not part:
                continue
            per, path = part.split("=", 1) if "=" in part else (a.period, part)
            entries.append((per.strip(), path.strip()))
        wrote = []
        for per, path in entries:
            p = Path(path)
            if not p.exists():
                print(f"  {per}: FILE NOT FOUND: {path}"); continue
            txt = p.read_text(encoding="utf-8", errors="ignore").strip()
            if len(txt.split()) < 200:
                print(f"  {per}: SKIP (only {len(txt.split())} words — paste the full call)"); continue
            key = f"{a.ticker}_{per}"
            if lang.looks_english(txt):
                lang.EN_DIR.mkdir(parents=True, exist_ok=True)
                lang.en_file(key).write_text(txt, encoding="utf-8")
                note = f"english {len(txt.split())}w"
            else:
                lang.translate(txt, key)          # translate -> cache English
                note = f"translated {len(txt.split())}w"
            wrote.append((per, note))
        if not wrote:
            print("no usable transcript files — nothing added"); return
        if not any(c["ticker"] == a.ticker for c in mf["companies"]):
            mf["companies"].append({"ticker": a.ticker, "name": a.name, "layer": a.layer,
                                    "sublayer": a.sub, "core": False, "source": "manual_text", "urls": []})
            MANIFEST.write_text(json.dumps(mf, ensure_ascii=False, indent=1), encoding="utf-8")
        for per, note in wrote:
            print(f"  cached {a.ticker} {per}: {note}")
        print(f"  added/updated {a.name} ({a.ticker}) L{a.layer}/{a.sub} · {len(wrote)} quarter(s) · run: refresh.py update")
        return

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
