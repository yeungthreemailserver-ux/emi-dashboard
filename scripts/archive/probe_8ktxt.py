r"""Check whether the EX-99.1 earnings press release (with guidance) is embedded in the
full-submission .txt of NVDA's earnings 8-K. If so, guidance is extractable."""
import re

import requests
from bs4 import BeautifulSoup

from emi.config import SEC_USER_AGENT

H = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
URL = "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000051/0001045810-26-000051.txt"

r = requests.get(URL, headers=H, timeout=60)
print("full submission .txt:", r.status_code, f"{len(r.text)} chars")
if r.status_code != 200:
    raise SystemExit("full .txt unavailable")

# count embedded documents and their types
types = re.findall(r"<TYPE>([^\n<]+)", r.text)
print("embedded document <TYPE> tags:", types)

text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
print(f"\nstripped text length: {len(text)} chars")
for kw in ["outlook", "guidance", "we expect", "expected to be", "revenue is expected",
           "second quarter", "gross margin", "billion, plus or minus", "plus or minus"]:
    m = re.search(r".{0,60}" + re.escape(kw) + r".{0,200}", text, re.I)
    print(f"  [{kw}]: " + (("…" + m.group(0).strip() + "…") if m else "NOT FOUND"))
