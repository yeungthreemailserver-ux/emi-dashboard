r"""Targeted probe: can we locate + parse SIA's monthly global semiconductor sales release?"""
import re

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

home = requests.get("https://www.semiconductors.org/", headers=UA, timeout=25).text
links = sorted({a.get("href") for a in BeautifulSoup(home, "html.parser").find_all("a", href=True)
                if a.get("href") and re.search(r"semiconductor-sales|global-semiconductor|sales-(increase|grow|decline)", a["href"], re.I)})
print(f"candidate sales links: {len(links)}")
for u in links[:8]:
    print("  ", u)

if links:
    url = links[0] if links[0].startswith("http") else "https://www.semiconductors.org" + links[0]
    print(f"\nfetching: {url}")
    art = requests.get(url, headers=UA, timeout=25).text
    text = re.sub(r"\s+", " ", BeautifulSoup(art, "html.parser").get_text(" ", strip=True))
    for kw in ["sales", "billion", "percent", "month", "moving average", "Americas", "Europe", "Japan", "Asia"]:
        m = re.search(r".{0,50}\b" + kw + r"\b.{0,120}", text)
        if m:
            print(f"  [{kw}] …{m.group(0).strip()[:170]}…")
