r"""TOKEN-FREE transcript-URL discovery. Scrapes each company's MarketBeat earnings page
(urllib + regex) and prints the 5 most-recent transcript URLs, newest-first — ready to paste
into MANIFEST in build_topic_counts.py. No LLM, no agents → 0 tokens per company.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\discover_urls.py AMD:NASDAQ AVGO:NASDAQ ...
"""
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def get(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        return "ERR:" + type(e).__name__


def discover(ticker, exch, n=5):
    html = get(f"https://www.marketbeat.com/stocks/{exch}/{ticker}/earnings/")
    if html.startswith("ERR"):
        return []
    links = re.findall(r"/earnings/reports/\d{4}-\d{1,2}-\d{1,2}-[a-z0-9-]+-stock/", html)
    seen = list(dict.fromkeys(links))  # dedupe, keep order

    def dkey(l):
        m = re.search(r"reports/(\d{4})-(\d{1,2})-(\d{1,2})", l)
        return tuple(int(x) for x in m.groups())
    seen.sort(key=dkey, reverse=True)  # newest first
    return ["https://www.marketbeat.com" + l for l in seen[:n]]


def main():
    args = sys.argv[1:] or ["AMD:NASDAQ", "AVGO:NASDAQ", "TXN:NASDAQ", "ADI:NASDAQ", "KLAC:NASDAQ"]
    for a in args:
        tk, exch = (a.split(":") + ["NASDAQ"])[:2]
        urls = discover(tk, exch)
        print(f'    "{tk}": [')
        for x in urls:
            print(f'        "{x}",')
        print(f'    ],   # {len(urls)} found')


if __name__ == "__main__":
    main()
