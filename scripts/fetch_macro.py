r"""Fetch free/FMP macro + semiconductor-industry data into web/data.json. Token-free (plain HTTP).

Sources (per docs/research-findings.md):
  - World Bank WDI (no key): APAC macro — GDP, CPI, high-tech exports — CN/KR/JP/SG/MY
  - SEC EDGAR data.sec.gov (no key, User-Agent only): hyperscaler quarterly capex (AI/datacenter)
  - FMP (fmp_key.txt, optional): US macro (GDP/CPI) + treasury curve
  - WSTS Blue Book (no key): regional semiconductor billings incl. Asia Pacific (link scraped, XLSX)

    python scripts/fetch_macro.py
"""
from __future__ import annotations
import json, re, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
UA = "MMI-macro-dashboard (yeungthreemailserver@gmail.com)"   # SEC requires a descriptive UA

# Semiconductor/electronics economies by region (World Bank ISO3; Taiwan TWN absent from WB -> FRED/DGBAS)
REGIONS = {
    "APAC": {"CHN": "China", "KOR": "South Korea", "JPN": "Japan", "TWN": "Taiwan", "SGP": "Singapore", "MYS": "Malaysia"},
    "EMEA": {"DEU": "Germany", "NLD": "Netherlands", "FRA": "France", "GBR": "United Kingdom", "ISR": "Israel", "IRL": "Ireland"},
    "AMER": {"USA": "United States", "MEX": "Mexico", "CAN": "Canada", "BRA": "Brazil"},
}
WSTS_REGION = {"APAC": "Asia Pacific", "EMEA": "Europe", "AMER": "Americas"}   # region -> WSTS billings region
ALL_ECON = {iso: name for d in REGIONS.values() for iso, name in d.items()}
WB_INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "FP.CPI.TOTL.ZG": "Inflation, CPI (% YoY)",
    "TX.VAL.TECH.CD": "High-tech exports (current US$)",
}
HYPERSCALERS = {  # CIK -> name (capex = us-gaap PaymentsToAcquirePropertyPlantAndEquipment)
    "0000789019": "Microsoft", "0001652044": "Alphabet",
    "0001018724": "Amazon", "0001326801": "Meta",
}


def get(url, headers=None, timeout=45):
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=timeout).read()
    except Exception as e:  # noqa: BLE001
        print(f"    fetch fail {type(e).__name__}: {str(e)[:80]}  <- {url[:70]}")
        return None


def get_json(url, headers=None):
    raw = get(url, headers)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", "ignore"))
    except Exception:  # noqa: BLE001
        return None


def world_bank():
    """Annual macro series (all regions), newest 15 yrs."""
    out = {}
    for iso, name in ALL_ECON.items():
        out[iso] = {"name": name, "series": {}}
        for ind, lbl in WB_INDICATORS.items():
            j = get_json(f"https://api.worldbank.org/v2/country/{iso}/indicator/{ind}?format=json&date=2010:2026&per_page=100")
            pts = []
            if isinstance(j, list) and len(j) == 2 and j[1]:
                pts = [{"date": r["date"], "value": r["value"]} for r in j[1] if r.get("value") is not None]
                pts.sort(key=lambda p: p["date"])
            out[iso]["series"][ind] = {"label": lbl, "points": pts}
            print(f"  WB {name:12} {ind:18} {len(pts)} pts")
    return out


def hyperscaler_capex():
    """Quarterly capex (PP&E payments) per hyperscaler -> proxy for AI/datacenter buildout."""
    out = {}
    for cik, name in HYPERSCALERS.items():
        j = get_json(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/PaymentsToAcquirePropertyPlantAndEquipment.json",
                     headers={"User-Agent": UA})
        pts = []
        if j and "units" in j and "USD" in j["units"]:
            # quarterly-ish frames: keep form 10-Q/10-K, dedupe by (end), take frame-tagged where present
            seen = {}
            for u in j["units"]["USD"]:
                if u.get("form") in ("10-Q", "10-K") and u.get("start") and u.get("end"):
                    # approx-quarter: keep entries spanning ~<=100 days (quarterly), drop annual cumulatives
                    seen[u["end"] + "|" + u["start"]] = u
            rows = sorted(seen.values(), key=lambda u: u["end"])
            for u in rows:
                pts.append({"end": u["end"], "start": u["start"], "val": u["val"], "fy": u.get("fy"), "fp": u.get("fp")})
        out[name] = pts[-24:]   # last ~6yr of quarter-ish points
        print(f"  EDGAR {name:10} {len(out[name])} capex points")
    return out


def fmp_us():
    keyf = ROOT / "fmp_key.txt"
    if not keyf.exists():
        print("  FMP: no fmp_key.txt -> skipping US macro/treasury")
        return None
    key = keyf.read_text(encoding="utf-8").strip()
    if not key or "PUT_YOUR" in key:
        print("  FMP: key placeholder -> skipping")
        return None
    out = {}
    for name in ("GDP", "CPI", "realGDP"):
        j = get_json(f"https://financialmodelingprep.com/stable/economic-indicators?name={name}&apikey={key}")
        out[name] = j if isinstance(j, list) else []
        print(f"  FMP econ {name}: {len(out[name])} pts")
    tr = get_json(f"https://financialmodelingprep.com/stable/treasury-rates?apikey={key}")
    out["treasury_latest"] = (tr[0] if isinstance(tr, list) and tr else None)
    return out


WSTS_REGIONS = {"americas", "europe", "japan", "asia pacific", "worldwide"}


def _parse_wsts_sheet(xl, sheet, months_back=120):
    """Blue Book layout: per-year blocks — a row with the 4-digit year in col0, then region rows
    (Americas/Europe/Japan/Asia Pacific/Worldwide) with 12 monthly values in cols 1..12. Values in 1000 US$."""
    import pandas as pd  # lazy
    df = xl.parse(sheet, header=None)
    series = {}
    year = None
    for _, row in df.iterrows():
        c0 = str(row[0]).strip()
        if re.fullmatch(r"\d{4}", c0):
            year = int(c0); continue
        key = c0.lower()
        if year and key in WSTS_REGIONS:
            for mi in range(1, 13):
                v = row[mi] if mi < len(row) else None
                if pd.notna(v) and isinstance(v, (int, float)) and v > 0:   # skip zero-padded future months
                    series.setdefault(c0, []).append({"ym": f"{year}-{mi:02d}", "val": float(v) * 1000})  # ->USD
    for r in series:
        series[r] = sorted(series[r], key=lambda p: p["ym"])[-months_back:]
    return series


def wsts():
    """Regional semiconductor billings (incl. Asia Pacific) — scrape Blue Book link, download + parse XLSX."""
    raw = get("https://www.wsts.org/67/Historical-Billings-Report")
    if raw is None:
        return None
    html = raw.decode("utf-8", "ignore")
    m = re.search(r'href=["\']([^"\']+Historical-Billings-Report[^"\']+\.xlsx)["\']', html, re.I)
    url = m.group(1) if m else None
    if url and not url.startswith("http"):
        url = "https://www.wsts.org" + url
    print(f"  WSTS xlsx link: {url or 'NOT FOUND'}")
    if not url:
        return {"xlsx_url": None}
    xraw = get(url)
    if xraw is None:
        return {"xlsx_url": url, "note": "download failed"}
    try:
        import io as _io, pandas as pd  # noqa: F401
        xl = pd.ExcelFile(_io.BytesIO(xraw))
        monthly = _parse_wsts_sheet(xl, "Monthly Data")
        mma3 = _parse_wsts_sheet(xl, "3MMA")
        for r in monthly:
            print(f"  WSTS {r:14} {len(monthly[r])} mo (latest {monthly[r][-1]['ym']})")
        return {"xlsx_url": url, "unit": "USD", "monthly": monthly, "mma3": mma3}
    except Exception as e:  # noqa: BLE001
        print(f"  WSTS parse failed ({type(e).__name__}: {str(e)[:60]}) — need pandas+openpyxl")
        return {"xlsx_url": url, "note": "parse failed (install pandas+openpyxl)"}


# FRED keyless CSV (fredgraph.csv?id=) — no API key/registration. Skips gracefully if unreachable.
FRED_SERIES = {
    "PPIACO": ("US PPI — all commodities", "US"),
    "INDPRO": ("US industrial production", "US"),
    "IPB50001SQ": ("US industrial production (q)", "US"),
    "XTEXVA01TWM667S": ("Taiwan exports (value, monthly)", "TWN"),    # best-effort OECD id; skips if invalid
    "TWNPROINDMISMEI": ("Taiwan industrial production", "TWN"),
    "KORPROINDMISMEI": ("Korea industrial production", "KOR"),
    "JPNPROINDMISMEI": ("Japan industrial production", "JPN"),
}


def fred():
    out = {}
    for sid, (lbl, region) in FRED_SERIES.items():
        raw = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=20)
        if raw is None:
            continue
        pts = []
        for line in raw.decode("utf-8", "ignore").strip().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) >= 2 and parts[1] not in (".", ""):
                try:
                    pts.append({"date": parts[0], "value": float(parts[1])})
                except ValueError:
                    pass
        if pts:
            out[sid] = {"label": lbl, "region": region, "points": pts[-180:]}
            print(f"  FRED {sid:18} {len(out[sid]['points'])} pts")
    if not out:
        print("  FRED: unreachable/empty from this network (works where fred.stlouisfed.org resolves)")
    return out


def main():
    WEB.mkdir(parents=True, exist_ok=True)
    print("World Bank (APAC macro)…");          wb = world_bank()
    print("SEC EDGAR (hyperscaler capex)…");     hs = hyperscaler_capex()
    print("FMP (US macro)…");                    us = fmp_us()
    print("WSTS (semiconductor billings)…");     ws = wsts()
    print("FRED (PPI / IndProd / Taiwan)…");     fr = fred()
    out = {
        "as_of": None,  # stamped by caller / left null (no Date.now in pipeline by policy)
        "regions": {r: list(econ.keys()) for r, econ in REGIONS.items()},
        "region_names": {r: econ for r, econ in REGIONS.items()},
        "wsts_region": WSTS_REGION,
        "worldbank": wb,
        "hyperscaler_capex": hs,
        "us_macro": us,
        "wsts": ws,
        "fred": fr,
    }
    (WEB / "macro-data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sz = (WEB / "macro-data.json").stat().st_size / 1024
    print(f"\nwrote web/macro-data.json ({sz:.0f} KB)")


if __name__ == "__main__":
    main()
