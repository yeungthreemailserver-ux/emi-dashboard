"""Company-issued guidance from EDGAR 8-K earnings press releases (US filers).

The earnings press release (Exhibit 99.1) is embedded in the filing's full-submission .txt.
We extract just the EX-99.1/99.2 SGML sections (avoiding the binary graphic/zip exhibits),
strip tags, find the "Outlook" section, and rule-parse guided revenue (midpoint + range) and
gross-margin guidance. US-only, and only companies that issue explicit numeric guidance.
"""
from __future__ import annotations

import html as _html
import re
import time

import requests

from ..config import RAW_DIR, SEC_USER_AGENT

GUID_RAW = RAW_DIR / "guidance"
H = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _submissions(cik: str) -> dict:
    r = requests.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", headers=H, timeout=30)
    r.raise_for_status()
    return r.json()


def _recent_8k(subs: dict, n: int = 8) -> list[dict]:
    rec = subs["filings"]["recent"]
    out = []
    for i, f in enumerate(rec["form"]):
        if f == "8-K":
            out.append({"accn": rec["accessionNumber"][i], "date": rec["filingDate"][i]})
            if len(out) >= n:
                break
    return out


def _fetch_txt(cik: str, accn: str, refresh: bool = False) -> str | None:
    GUID_RAW.mkdir(parents=True, exist_ok=True)
    cikint, nod = int(cik), accn.replace("-", "")
    cache = GUID_RAW / f"{cikint}_{nod}.txt"
    if cache.exists() and not refresh:
        return cache.read_text(encoding="utf-8", errors="ignore")
    url = f"https://www.sec.gov/Archives/edgar/data/{cikint}/{nod}/{accn}.txt"
    r = requests.get(url, headers=H, timeout=60)
    if r.status_code != 200:
        return None
    cache.write_text(r.text, encoding="utf-8", errors="ignore")
    time.sleep(0.15)
    return r.text


def _press_release_text(txt: str) -> str:
    """Return stripped text of the EX-99.1/99.2 documents only (skip binary exhibits)."""
    parts = []
    for m in re.finditer(r"<DOCUMENT>(.*?)</DOCUMENT>", txt, re.S):
        seg = m.group(1)
        tm = re.search(r"<TYPE>([^\s<]+)", seg)
        if tm and tm.group(1).upper().startswith("EX-99"):
            body = re.search(r"<TEXT>(.*?)</TEXT>", seg, re.S)
            parts.append(body.group(1) if body else seg)
    raw = " ".join(parts)
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", _html.unescape(raw)).strip()


def _to_usd(num: str, unit: str | None) -> float:
    v = float(num.replace(",", ""))
    if unit and unit.lower().startswith("b"):
        v *= 1e9
    elif unit and unit.lower().startswith("m"):
        v *= 1e6
    return v


def _rev_from(w: str) -> dict | None:
    m = re.search(r"\$?\s*([\d,.]+)\s*(billion|million)\s*,?\s*(?:plus or minus|\+/-|±)\s*([\d.]+)\s*%", w)
    if m:
        mid, pct = _to_usd(m.group(1), m.group(2)), float(m.group(3)) / 100
        return {"mid": mid, "low": mid * (1 - pct), "high": mid * (1 + pct), "raw": m.group(0).strip()}
    m = re.search(r"\$?\s*([\d,.]+)\s*(billion|million)\s*,?\s*(?:plus or minus|\+/-|±)\s*\$?\s*([\d,.]+)\s*(billion|million)", w)
    if m:
        mid, d = _to_usd(m.group(1), m.group(2)), _to_usd(m.group(3), m.group(4))
        return {"mid": mid, "low": mid - d, "high": mid + d, "raw": m.group(0).strip()}
    m = re.search(r"\$?\s*([\d,.]+)\s*(billion|million)?\s*(?:to|and|–|-)\s*\$?\s*([\d,.]+)\s*(billion|million)", w)
    if m:
        unit = m.group(4) or m.group(2)
        low, high = _to_usd(m.group(1), unit), _to_usd(m.group(3), unit)
        if high >= low > 0 and high / low < 1.5:  # reject implausibly wide (mis-matched) ranges
            return {"mid": (low + high) / 2, "low": low, "high": high, "raw": m.group(0).strip()}
    m = re.search(r"approximately\s*\$?\s*([\d,.]+)\s*(billion|million)", w)
    if m:
        return {"mid": _to_usd(m.group(1), m.group(2)), "low": None, "high": None, "raw": m.group(0).strip()}
    return None


def parse_guidance(t: str) -> dict:
    out: dict = {}
    for rm in re.finditer(r"[Rr]evenues?\b", t):
        ctx = t[max(0, rm.start() - 110): rm.start() + 170]
        if not re.search(r"(expect|outlook|guidance|range|anticipat)", ctx, re.I):
            continue
        rev = _rev_from(t[rm.start(): rm.start() + 170])
        if rev:
            out["revenue"] = rev
            break

    m = re.search(r"gross margins?\b.{0,60}?(?:expected to be|of|in the range of)\s*(?:approximately\s*)?([\d.]+)\s*%", t)
    if m:
        out["gross_margin"] = {"mid": float(m.group(1)) / 100, "raw": m.group(0).strip()}

    m = (re.search(r"outlook for the\s+(first|second|third|fourth)\s+quarter\s+of\s+(?:fiscal\s+)?(\d{4})", t, re.I)
         or re.search(r"(?:for the\s+)?(first|second|third|fourth)\s+quarter\s+(?:of\s+)?(?:fiscal\s+)?(\d{4})", t, re.I))
    if m:
        out["period_text"] = f"{m.group(1).capitalize()} quarter FY{m.group(2)}"
    return out


def get_outlook_text(ticker: str, cik: str) -> dict | None:
    """Return the outlook/guidance snippet from the latest earnings 8-K (for LLM extraction),
    even when the rule parser found nothing."""
    try:
        subs = _submissions(cik)
    except Exception:
        return None
    for flg in _recent_8k(subs, 8):
        txt = _fetch_txt(cik, flg["accn"])
        if not txt or "EX-99" not in txt:
            continue
        body = _press_release_text(txt)
        m = re.search(r"(Business Outlook|Outlook|Guidance|expected to be|we expect)", body, re.I)
        if m:
            return {"text": body[max(0, m.start() - 150): m.start() + 1500],
                    "filed": flg["date"], "accn": flg["accn"]}
    return None


def get_guidance(ticker: str, cik: str) -> dict | None:
    try:
        subs = _submissions(cik)
    except Exception:
        return None
    for flg in _recent_8k(subs, 5):
        txt = _fetch_txt(cik, flg["accn"])
        if not txt or "EX-99" not in txt:
            continue
        body = _press_release_text(txt)
        if not re.search(r"\b(Outlook|expected to be)\b", body, re.I):
            continue
        g = parse_guidance(body)
        if g.get("revenue") or g.get("gross_margin"):
            g.update({"filed": flg["date"], "accn": flg["accn"], "ticker": ticker})
            return g
    return None
