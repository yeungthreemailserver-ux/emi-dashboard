r"""Find + download the WSTS Historical Billings Report Excel, then inspect its structure."""
import re

import requests
from bs4 import BeautifulSoup

from emi.config import RAW_DIR

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PAGE = "https://www.wsts.org/67/Historical-Billings-Report"

r = requests.get(PAGE, headers=UA, timeout=30)
print(f"HBR page: {r.status_code}  {len(r.text)} chars")
soup = BeautifulSoup(r.text, "html.parser")
links = [a.get("href") for a in soup.find_all("a", href=True)]
cand = sorted({l for l in links if re.search(r"\.(xlsx|xls|csv)(\?|$)", l, re.I)
               or re.search(r"download|billing|hbr|histor|/secure", l, re.I)})
print(f"candidate download links: {len(cand)}")
for l in cand:
    print("  ", l)

# try downloading the first spreadsheet-looking link
xls = [l for l in cand if re.search(r"\.(xlsx|xls|csv)(\?|$)", l, re.I)]
if xls:
    u = xls[0] if xls[0].startswith("http") else "https://www.wsts.org" + xls[0]
    print(f"\ndownloading: {u}")
    dr = requests.get(u, headers=UA, timeout=60)
    print("  status", dr.status_code, "bytes", len(dr.content), "ctype", dr.headers.get("Content-Type"))
    out = RAW_DIR / "wsts"
    out.mkdir(parents=True, exist_ok=True)
    ext = ".xlsx" if "xlsx" in u.lower() else ".xls" if ".xls" in u.lower() else ".csv"
    fp = out / ("hbr" + ext)
    fp.write_bytes(dr.content)
    print("  saved", fp)
else:
    print("\nno direct spreadsheet link found in page anchors (may be JS / behind a button).")
