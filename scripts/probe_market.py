r"""Feasibility probe: which industry-level market-data sources are reachable here, and do
their pages actually contain the numbers we'd parse?

    .\.venv\Scripts\python.exe scripts\probe_market.py
"""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

URLS = {
    "SIA_home":  "https://www.semiconductors.org/",
    "SIA_news":  "https://www.semiconductors.org/category/latest-news/",
    "WSTS_home": "https://www.wsts.org/",
    "WSTS_news": "https://www.wsts.org/67/Recent-News-Release",
    "ECIA_home": "https://www.ecianow.org/",
    "SEMI_news": "https://www.semi.org/en/news-media-press-releases",
    "FRED_INDPRO":  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=INDPRO",
    "FRED_semi_IP": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=IPG3344S",
}

PAT = re.compile(r".{0,30}(billion|book-to-bill|sales of \$|\$[\d,.]+\s*billion|moving average).{0,70}", re.I)

for name, url in URLS.items():
    try:
        r = requests.get(url, headers=UA, timeout=20)
        body = r.text or ""
        info = f"{r.status_code}  {len(body):>7} chars"
        if name.startswith("FRED"):
            head = body.splitlines()[:3]
            info += "  | csv head: " + " / ".join(head)
        else:
            m = PAT.search(re.sub(r"<[^>]+>", " ", body))
            info += "  | numeric hit: " + (m.group(0).strip()[:90] if m else "none found")
        print(f"{name:14s} {info}")
    except Exception as e:
        print(f"{name:14s} ERROR: {repr(e)[:110]}")
