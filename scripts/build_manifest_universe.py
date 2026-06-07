r"""Expand data/manifest.json from the company universe via TOKEN-FREE MarketBeat discovery.

Keeps the existing (hand-curated) manifest entries and ADDS US-listed L0-L3 chip-chain companies
whose transcripts MarketBeat exposes. No LLM, no agents -> 0 tokens. Non-US (TW/JP/CN/KR) have no
free transcript source and are skipped.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\build_manifest_universe.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT, iter_universe
import discover_urls as D

EXCHS = ["NASDAQ", "NYSE", "NYSEAMERICAN"]
LAYERS = {"L0", "L1", "L2", "L3"}   # core chip chain (skip L4 EMS / L5 OEM — different topic universe)
MIN_URLS = 3

mf = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
have = {c["ticker"] for c in mf["companies"]}
cands = [r for r in iter_universe() if r["region"] == "US" and r["layer"] in LAYERS and r["ticker"] not in have]

added, skipped = [], []
for r in cands:
    tk = r["ticker"]
    urls, ex = [], None
    for e in EXCHS:
        u = D.discover(tk, e, 5)
        if u:
            urls, ex = u, e
            break
    if len(urls) < MIN_URLS:
        skipped.append(tk)
        continue
    mf["companies"].append({"ticker": tk, "name": r["name"], "layer": r["layer"],
                            "sublayer": r.get("sublayer") or r["layer"][1:], "core": False,
                            "source": "marketbeat", "mb": f"{ex}/{tk}", "urls": urls})
    added.append(tk)

(ROOT / "data" / "manifest.json").write_text(json.dumps(mf, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"candidates(US L0-L3, new)={len(cands)}  added={len(added)}  skipped(no MB transcripts)={len(skipped)}  manifest_total={len(mf['companies'])}")
print("added:", " ".join(added))
