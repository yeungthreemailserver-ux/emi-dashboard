r"""Feasibility probe: can we get company guidance from EDGAR 8-K earnings press releases?

Checks (for NVDA): submissions API -> recent 8-K filings -> fetch the press-release
exhibit document -> search for guidance language. Also reports EDGAR quarterly-history depth.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\probe_edgar8k.py
"""
import re

import requests

from emi.config import SEC_USER_AGENT
from emi.ingest.edgar import fetch_company_facts, load_cik_map

H = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
TICK = "NVDA"

cik = load_cik_map()[TICK]
cikint = int(cik)
print(f"{TICK} CIK={cikint}")

# --- EDGAR quarterly-history depth (for the 'longer history' question) ---
facts = fetch_company_facts(cik)
try:
    pts = facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    q = [p for p in pts if p.get("start") and 80 <= (
        __import__("datetime").date.fromisoformat(p["end"]) - __import__("datetime").date.fromisoformat(p["start"])).days <= 100]
    ends = sorted({p["end"] for p in q})
    print(f"EDGAR quarterly Revenue points: {len(q)} spanning {ends[0]}..{ends[-1]}")
except Exception as e:
    print("history check error:", e)

# --- submissions -> recent 8-K ---
r = requests.get(f"https://data.sec.gov/submissions/CIK{cikint:010d}.json", headers=H, timeout=30)
print("submissions API:", r.status_code)
if r.status_code != 200:
    raise SystemExit("submissions API unavailable in this environment")
rec = r.json()["filings"]["recent"]
eight = [i for i, f in enumerate(rec["form"]) if f == "8-K"][:3]
print(f"recent 8-K count (shown {len(eight)}):")
for i in eight:
    print(f"  {rec['filingDate'][i]}  accn={rec['accessionNumber'][i]}  doc={rec['primaryDocument'][i]}  desc={rec.get('primaryDocDescription', ['']*len(rec['form']))[i]}")

if not eight:
    raise SystemExit("no 8-K filings listed")

# --- fetch the filing directory + an exhibit, search for guidance ---
i = eight[0]
accn = rec["accessionNumber"][i].replace("-", "")
base = f"https://www.sec.gov/Archives/edgar/data/{cikint}/{accn}"
idx = requests.get(base + "/index.json", headers=H, timeout=30)
print(f"\nfiling index.json: {idx.status_code}  ({base})")
if idx.status_code == 200:
    items = idx.json().get("directory", {}).get("item", [])
    print("  documents:", [it["name"] for it in items][:12])
    cand = [it["name"] for it in items if re.search(r"(ex.?99|press|earnings|ex99)", it["name"], re.I) or it["name"].endswith(".htm")]
    target = cand[0] if cand else (items[0]["name"] if items else None)
    if target:
        doc = requests.get(f"{base}/{target}", headers=H, timeout=30)
        print(f"\nfetched exhibit '{target}': {doc.status_code}, {len(doc.text)} chars")
        from bs4 import BeautifulSoup
        text = BeautifulSoup(doc.text, "html.parser").get_text(" ", strip=True)
        for kw in ["outlook", "guidance", "we expect", "first quarter", "second quarter", "revenue is expected", "expected to be"]:
            m = re.search(r".{0,80}" + re.escape(kw) + r".{0,160}", text, re.I)
            if m:
                print(f"  [{kw}] …{m.group(0).strip()}…")
