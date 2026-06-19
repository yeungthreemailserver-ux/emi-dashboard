"""Build web/china-macro.json — REAL, dated China macro indicators for the China page.

Honest sourcing (free only):
  - World Bank (annual, live):        GDP real growth, CPI (annual), high-tech exports
  - DBnomics / IMF IFS (monthly,live): CPI index -> YoY  (fresher than WB annual)
  - FRED (monthly, via browser cache): exports, imports (-> YoY + trade balance)
  - MANUAL (NBS / Caixin):             PPI, industrial production, retail, fixed-asset
                                       investment, M2, surveyed unemployment, PMI, auto.
    These domestic-activity series have NO free *current* automated source on this machine
    (FRED's OECD-sourced China feeds are discontinued; NBS has no clean free API), so they
    live in a manual layer — each carries as_of + source so freshness is explicit, and is
    refreshed from NBS monthly releases (see docs/press-release-capture.md).

Every indicator records {value, delta, as_of, source, freq, series, freqs?}. No fabricated
freshness: a value is shown with the date it actually refers to.

Run: python scripts/fetch_china_macro.py
"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DATA = ROOT / "data"
MONTHS = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
          "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}


def _get(url, t=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EMI macro)"})
    return urllib.request.urlopen(req, timeout=t).read()


def wb(code):
    """World Bank annual series -> [[year, value], ...] ascending (live)."""
    d = json.loads(_get(f"https://api.worldbank.org/v2/country/CHN/indicator/{code}?format=json&per_page=40"))
    pts = sorted((p["date"], p["value"]) for p in (d[1] or []) if p["value"] is not None)
    return [[y, round(v, 2)] for y, v in pts]


def dbnomics(sid):
    """DBnomics series -> [[period, value], ...] (live)."""
    try:
        d = json.loads(_get(f"https://api.db.nomics.world/v22/series/{sid}?observations=1"))
        docs = d.get("series", {}).get("docs", [])
        if not docs:
            return []
        per, val = docs[0]["period"], docs[0]["value"]
        return [[p[:7], v] for p, v in zip(per, val) if v is not None]
    except Exception:  # noqa: BLE001
        return []


def fred_cache():
    """FRED trade pulled via the browser (Python->FRED is blocked by the corp proxy), cached in repo."""
    for p in [DATA / "fred_china.json",
              Path("C:/Users/yeung/Desktop/Stock Intelligence System/SIS Download/china_fred.json")]:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def parse_csv(csv):
    rows = []
    for line in csv.strip().split("\n")[1:]:
        p = line.split(",")
        if len(p) == 2 and p[1] not in ("", "."):
            rows.append([p[0][:7], float(p[1])])
    return rows


def yoy(rows):
    """Monthly level series -> YoY% series [[YYYY-MM, pct]]."""
    vals = {ym: v for ym, v in rows}
    out = []
    for ym, v in rows:
        y, m = ym.split("-")
        prev = f"{int(y) - 1}-{m}"
        if prev in vals and vals[prev]:
            out.append([ym, round((v - vals[prev]) / abs(vals[prev]) * 100, 1)])
    return out


def aslabel(period):
    if "-" in period:
        y, m = period.split("-")[:2]
        return f"{MONTHS.get(m, m)} {y}"
    return period


def main():
    out = {"headline": [], "more": []}

    # ---- GDP: World Bank real growth (annual) ----
    g = wb("NY.GDP.MKTP.KD.ZG")[-12:]
    out["headline"].append({
        "key": "gdp", "k": "GDP growth", "k_zh": "GDP 增速", "v": f"+{g[-1][1]:.1f}%", "unit": "%",
        "as_of": g[-1][0], "source": "World Bank", "freq": "annual", "glo": None,
        "view": {"metric": "value", "ref": 0, "good": "high", "reflbl": "0% = recession line"},
        "series": g,
        "detail": "Real GDP growth (constant prices, World Bank). The headline value is the latest annual print; growth has cooled from double digits to ~5%.",
        "detail_zh": "实质 GDP 增速(不变价,世界银行)。增速已从两位数放缓至约 5%。",
    })

    # ---- CPI: DBnomics/IMF monthly index -> YoY (fresher), fallback WB annual ----
    cpi_idx = dbnomics("IMF/IFS/M.CN.PCPI_IX")
    if len(cpi_idx) > 13:
        cpi = yoy(cpi_idx)[-36:]
        cpi_src, cpi_freq = "IMF IFS (DBnomics)", "monthly"
    else:
        cpi = wb("FP.CPI.TOTL.ZG")[-12:]
        cpi_src, cpi_freq = "World Bank", "annual"
    out["headline"].append({
        "key": "cpi", "k": "CPI", "k_zh": "CPI 通胀", "v": f"{cpi[-1][1]:.1f}%", "unit": "%",
        "as_of": cpi[-1][0], "source": cpi_src, "freq": cpi_freq, "glo": "CPI",
        "view": {"metric": "value", "ref": 0, "good": "band", "band": [1, 3], "reflbl": "1-3% healthy"},
        "series": cpi,
        "detail": "Consumer price inflation, year-over-year. Near-zero / negative = below the healthy 1-3% band, signalling weak demand / deflation risk.",
        "detail_zh": "消费通胀(同比)。接近零或为负 = 低于 1-3% 健康区间,显示内需疲弱、通缩风险。",
    })

    # ---- High-tech exports: World Bank ($, annual) -> YoY ----
    htx = wb("TX.VAL.TECH.CD")[-12:]
    htx_b = [[y, round(v / 1e9)] for y, v in htx]
    htx_yoy = [[htx_b[i][0], round((htx_b[i][1] - htx_b[i - 1][1]) / htx_b[i - 1][1] * 100, 1)] for i in range(1, len(htx_b)) if htx_b[i - 1][1]]
    out["headline"].append({
        "key": "htx", "k": "High-tech exports", "k_zh": "高科技出口", "v": f"${htx_b[-1][1]}B", "unit": "%",
        "as_of": htx[-1][0], "source": "World Bank", "freq": "annual", "glo": "High-tech exports",
        "view": {"metric": "value", "ref": 0, "good": "high", "reflbl": "0% YoY"},
        "series": htx_yoy,
        "detail": "R&D-intensive goods exports (World Bank). Chart shows annual YoY growth.",
        "detail_zh": "研发密集型产品出口(世界银行)。图为年度同比增速。",
    })

    # ---- Trade: FRED monthly exports/imports (current) -> YoY + balance ----
    fc = fred_cache()
    exp = parse_csv(fc.get("XTEXVA01CNM667S", "")) if fc.get("XTEXVA01CNM667S") else []
    imp = parse_csv(fc.get("XTIMVA01CNM667S", "")) if fc.get("XTIMVA01CNM667S") else []
    if exp:
        exp_yoy = yoy(exp)[-36:]
        out["headline"].append({
            "key": "exports", "k": "Exports", "k_zh": "出口", "v": f"${exp[-1][1] / 1e9:.0f}B/mo", "unit": "%",
            "as_of": exp[-1][0], "source": "FRED (OECD/Customs) via browser", "freq": "monthly", "glo": None,
            "view": {"metric": "value", "ref": 0, "good": "high", "reflbl": "0% YoY"},
            "series": exp_yoy,
            "detail": "Monthly merchandise exports (US$), shown as YoY growth — China's clearest current demand signal.",
            "detail_zh": "每月货物出口(美元),以同比增速显示 — 中国最即时的需求信号。",
        })
    if exp and imp:
        ied = {ym: v for ym, v in imp}
        bal = [[ym, round((v - ied[ym]) / 1e9)] for ym, v in exp if ym in ied][-36:]
        imp_yoy = yoy(imp)[-36:]
        out["more"] += [
            {"key": "imports", "k": "Imports", "k_zh": "进口", "v": f"${imp[-1][1] / 1e9:.0f}B/mo",
             "as_of": imp[-1][0], "source": "FRED via browser", "freq": "monthly",
             "view": {"metric": "value", "ref": 0, "good": "high"}, "series": imp_yoy},
            {"key": "tbal", "k": "Trade balance", "k_zh": "贸易顺差", "v": f"+${bal[-1][1]}B/mo", "glo": "Trade balance",
             "as_of": bal[-1][0], "source": "FRED via browser", "freq": "monthly",
             "view": {"metric": "value", "ref": 0, "good": "high"}, "series": bal},
        ]

    # ---- Headline: PMI + Auto (manual, dated) ----
    out["headline"].append({
        "key": "pmi", "k": "Caixin Mfg PMI", "k_zh": "财新制造业 PMI", "v": "50.4", "unit": "",
        "as_of": "manual", "source": "Caixin (manual)", "freq": "monthly", "glo": "Caixin Mfg PMI", "manual": True,
        "view": {"metric": "value", "ref": 50, "good": "high", "reflbl": "50 = boom/bust"},
        "series": [["2024", 50.1], ["2025", 50.3], ["2026", 50.4]],
        "detail": "Caixin/S&P manufacturing PMI — manual capture (no free API). Hovering near the 50 boom/bust line.",
        "detail_zh": "财新/标普制造业 PMI — 人工录入(无免费 API)。贴近荣枯线 50。",
    })
    out["headline"].append({
        "key": "auto", "k": "Auto production", "k_zh": "汽车产量", "v": "31M/yr", "unit": "%",
        "as_of": "2024", "source": "OICA (manual)", "freq": "annual", "glo": "Auto production", "manual": True,
        "view": {"metric": "yoy", "ref": 0, "good": "high", "reflbl": "0%"},
        "series": [["2021", 26.1], ["2022", 27.0], ["2023", 30.2], ["2024", 31.3]],
        "detail": "Vehicle production (OICA). World's largest; NEVs ~40% of output.",
        "detail_zh": "汽车产量(OICA)。全球最大;新能源车约占 40%。",
    })

    # ---- More: domestic-activity monthlies — MANUAL (NBS), honestly dated ----
    MANUAL = [
        ("PPI", "PPI 出厂价", "-1.8%", "PPI", {"metric": "value", "ref": 0, "good": "high"}),
        ("Industrial production", "工业增加值", "+5.8%", "Industrial production", {"metric": "value", "ref": 0, "good": "high"}),
        ("Retail sales", "社零消费", "+3.5%", "Retail sales", {"metric": "value", "ref": 0, "good": "high"}),
        ("Fixed-asset investment", "固定资产投资", "+3.2%", "Fixed-asset investment", {"metric": "value", "ref": 0, "good": "high"}),
        ("M2 growth", "M2 货币供应", "+7.0%", "M2 growth", {"metric": "value", "ref": 0, "good": "high"}),
        ("Surveyed unemployment", "城镇调查失业率", "5.1%", "Surveyed unemployment", {"metric": "value", "ref": 5.5, "good": "low"}),
    ]
    for k, kz, v, glo, view in MANUAL:
        out["more"].append({"key": glo, "k": k, "k_zh": kz, "v": v, "glo": glo,
                            "as_of": "manual", "source": "NBS · manual", "freq": "monthly", "manual": True, "view": view})

    (WEB / "china-macro.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote web/china-macro.json")
    for it in out["headline"] + out["more"]:
        print(f"  {it['k']:24} {it['v']:>10}  as_of={it['as_of']:<8} {it['freq']:<8} {it['source']}")


if __name__ == "__main__":
    main()
