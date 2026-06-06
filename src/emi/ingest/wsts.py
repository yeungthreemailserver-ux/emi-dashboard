"""WSTS Historical Billings Report ingestion (free Excel from wsts.org).

Two sheets — 'Monthly Data' (raw) and '3MMA' (3-month moving average). Each is year-blocked:
a row with the year, then 5 region rows (Americas/Europe/Japan/Asia Pacific/Worldwide) with
12 monthly columns. Values are in thousands of USD → stored in USD. Region-level only;
WSTS by-product-category is a separate paid report (not here).
"""
from __future__ import annotations

import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from ..config import RAW_DIR

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
HBR_PAGE = "https://www.wsts.org/67/Historical-Billings-Report"
WSTS_RAW = RAW_DIR / "wsts"
REGIONS = {"Americas": "americas", "Europe": "europe", "Japan": "japan",
           "Asia Pacific": "asiapacific", "Worldwide": "worldwide"}


def download_hbr(refresh: bool = False):
    WSTS_RAW.mkdir(parents=True, exist_ok=True)
    cache = WSTS_RAW / "hbr.xlsx"
    if cache.exists() and not refresh:
        return cache
    page = requests.get(HBR_PAGE, headers=UA, timeout=30).text
    links = [a["href"] for a in BeautifulSoup(page, "html.parser").find_all("a", href=True)]
    xls = [l for l in links if re.search(r"\.xlsx(\?|$)", l, re.I)]
    if not xls:
        raise RuntimeError("WSTS HBR .xlsx link not found on page")
    url = xls[0] if xls[0].startswith("http") else "https://www.wsts.org" + xls[0]
    cache.write_bytes(requests.get(url, headers=UA, timeout=60).content)
    return cache


def _parse_sheet(df: pd.DataFrame, suffix: str, quarters: bool = False) -> list[dict]:
    rows, year = [], None
    for _, r in df.iterrows():
        c0 = r.iloc[0]
        ys = None
        if isinstance(c0, (int, float)) and pd.notna(c0) and 1980 < float(c0) < 2100:
            ys = int(c0)
        elif isinstance(c0, str) and re.fullmatch(r"\d{4}", c0.strip()):
            ys = int(c0.strip())
        if ys:
            year = ys
            continue
        label = str(c0).strip() if pd.notna(c0) else ""
        if label not in REGIONS or not year:
            continue
        reg = REGIONS[label]
        for mi in range(1, 13):  # cols 1..12 = Jan..Dec
            if mi >= len(r):
                break
            v = r.iloc[mi]
            if pd.notna(v) and isinstance(v, (int, float)) and v > 0:  # skip 0-padded future months
                rows.append({"source": "wsts", "series": f"billings_{reg}{suffix}",
                             "period": f"{year}-{mi:02d}", "value": round(float(v) * 1000.0), "unit": "USD"})
        if quarters and len(r) >= 18:  # cols 14..17 = Q1..Q4
            for q in range(1, 5):
                v = r.iloc[13 + q]
                if pd.notna(v) and isinstance(v, (int, float)) and v > 0:
                    rows.append({"source": "wsts", "series": f"billings_{reg}_q",
                                 "period": f"{year}Q{q}", "value": round(float(v) * 1000.0), "unit": "USD"})
    return rows


def parse_hbr(path) -> list[dict]:
    rows = _parse_sheet(pd.read_excel(path, sheet_name="Monthly Data", header=None), "", quarters=True)
    rows += _parse_sheet(pd.read_excel(path, sheet_name="3MMA", header=None), "_3mma")
    return rows
