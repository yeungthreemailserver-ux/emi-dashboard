"""Build web/china-macro.json — CURRENT, dated China macro WITH real trend history.

Senior-exec requirement: latest published prints + a real trend, each tagged as_of + source + freq.

Sources (free):
  - NBS (National Bureau of Statistics), read via the browser from Trading Economics, which
    republishes NBS and exposes the full Highcharts history. Monthly/quarterly series + the
    latest value are cached in data/te_china.json (read date in READ_DATE). Refresh = re-read.
  - FRED (via browser cache data/fred_china.json): exports, imports (monthly) + trade balance.
  - World Bank (annual, live): high-tech exports.
  - OICA (manual, annual): auto production.

Every indicator records {value, as_of, source, freq, series}. The series is the real recent
history so the sparkline + expand-modal show an actual trend, not a single block.

Run: python scripts/fetch_china_macro.py
"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DATA = ROOT / "data"

READ_DATE = "2026-06"
# Cite the authoritative source only — not the aggregator/mirror we happened to read it from
# (Trading Economics / FRED) nor the fetch mechanism. Those are internal plumbing, off the page.
SRC_NBS = "NBS"
SRC_FRED = "OECD / China Customs"
SRC_CAIXIN = "Caixin / RatingDog (S&P Global)"
SRC_NBSPMI = "NBS / CFLP (official)"

# Latest official prints (NBS), read READ_DATE — the headline value + its reference date.
CURRENT = {
    "gdp":    {"v": "+5.0%", "as_of": "2026-Q1", "freq": "quarterly"},
    "cpi":    {"v": "+1.2%", "as_of": "2026-05", "freq": "monthly"},
    "ppi":    {"v": "+3.9%", "as_of": "2026-05", "freq": "monthly"},
    "ind":    {"v": "+4.5%", "as_of": "2026-05", "freq": "monthly"},
    "retail": {"v": "-0.6%", "as_of": "2026-05", "freq": "monthly"},
    "pmi":     {"v": "51.8", "as_of": "2026-05", "freq": "monthly"},   # Caixin / RatingDog (S&P) manufacturing
    "pmi_nbs": {"v": "50.5", "as_of": "2026-05", "freq": "monthly"},   # NBS / CFLP official
    "m2":     {"v": "+8.6%", "as_of": "2026-05", "freq": "monthly"},
    "unemp":  {"v": "5.1%",  "as_of": "2026-05", "freq": "monthly"},
}


def _get(url, t=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EMI)"}), timeout=t).read()


def wb(code):
    d = json.loads(_get(f"https://api.worldbank.org/v2/country/CHN/indicator/{code}?format=json&per_page=40"))
    return [[y, round(v, 2)] for y, v in sorted((p["date"], p["value"]) for p in (d[1] or []) if p["value"] is not None)]


def fred_cache():
    for p in [DATA / "fred_china.json", Path("C:/Users/yeung/Desktop/Stock Intelligence System/SIS Download/china_fred.json")]:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def parse_csv(csv):
    out = []
    for line in csv.strip().split("\n")[1:]:
        p = line.split(",")
        if len(p) == 2 and p[1] not in ("", "."):
            out.append([p[0][:7], float(p[1])])
    return out


def yoy(rows):
    vals = {ym: v for ym, v in rows}
    out = []
    for ym, v in rows:
        y, m = ym.split("-")
        prev = f"{int(y) - 1}-{m}"
        if prev in vals and vals[prev]:
            out.append([ym, round((v - vals[prev]) / abs(vals[prev]) * 100, 1)])
    return out


def tile(key, k, kz, cur, view, series, glo=None, source=SRC_NBS, detail="", detail_zh=""):
    c = CURRENT[cur]
    return {"key": key, "k": k, "k_zh": kz, "v": c["v"], "as_of": c["as_of"], "source": source,
            "freq": c["freq"], "glo": glo, "view": view, "series": series, "detail": detail, "detail_zh": detail_zh}


def main():
    te = json.loads((DATA / "te_china.json").read_text(encoding="utf-8"))
    out = {"read_date": READ_DATE, "headline": [], "more": []}

    out["headline"] = [
        tile("gdp", "GDP growth", "GDP 增速", "gdp", {"metric": "value", "ref": 0, "good": "high", "reflbl": "0% = recession"}, te["gdp"],
             detail="Real GDP growth, YoY (NBS, quarterly). The trend shows the cooling wave settling around ~5%.",
             detail_zh="实质 GDP 同比增速(国家统计局,季度)。趋势显示增速回落、企稳于约 5%。"),
        tile("cpi", "CPI", "CPI 通胀", "cpi", {"metric": "value", "ref": 0, "good": "band", "band": [0, 3], "reflbl": "0-3% healthy"}, te["cpi"], glo="CPI",
             detail="Consumer inflation, YoY (NBS, monthly). Climbed out of 2025 deflation back into a low-positive range.",
             detail_zh="消费通胀,同比(国家统计局,月度)。已自 2025 年通缩回升至偏低正区间。"),
        tile("ppi", "PPI", "PPI 出厂价", "ppi", {"metric": "value", "ref": 0, "good": "high", "reflbl": "0%"}, te["ppi"], glo="PPI",
             detail="Producer (factory-gate) prices, YoY (NBS, monthly). A clear recovery from deep deflation (-3.6%) to positive (+3.9%).",
             detail_zh="工业生产者出厂价,同比(国家统计局,月度)。从深度通缩(-3.6%)明显回升至正值(+3.9%)。"),
        tile("ind", "Industrial production", "工业增加值", "ind", {"metric": "value", "ref": 0, "good": "high", "reflbl": "0%"}, te["ind"], glo="Industrial production",
             detail="Above-scale industrial value-added, YoY (NBS, monthly). Steady ~5% (Jan combined with Feb for Lunar New Year).",
             detail_zh="规模以上工业增加值,同比(国家统计局,月度)。维持约 5%(1 月与 2 月合并发布)。"),
        tile("retail", "Retail sales", "社零消费", "retail", {"metric": "value", "ref": 0, "good": "high", "reflbl": "0%"}, te["retail"], glo="Retail sales",
             detail="Retail sales, YoY (NBS, monthly). A persistent slowdown from 6.4% to -0.6% — consumption turning negative is the key weak spot.",
             detail_zh="社会消费品零售总额,同比(国家统计局,月度)。从 6.4% 持续放缓至 -0.6% — 消费转负是关键弱点。"),
        tile("pmi_nbs", "NBS PMI", "官方 PMI", "pmi_nbs", {"metric": "value", "ref": 50, "good": "high", "reflbl": "50 = boom/bust"}, te["pmi_nbs"], glo="NBS PMI", source=SRC_NBSPMI,
             detail="Official NBS / CFLP PMI — surveys ~3,200 mostly large & state-owned firms; the most policy-watched gauge. Barely above 50 = activity essentially flat.",
             detail_zh="官方 NBS(中物联)PMI — 调查约 3,200 家多为大型/国企,最受政策关注。刚过 50 = 活动基本持平。"),
        tile("caixin", "Caixin Mfg PMI", "财新制造业 PMI", "pmi", {"metric": "value", "ref": 50, "good": "high", "reflbl": "50 = boom/bust"}, te["pmi"], glo="Caixin Mfg PMI", source=SRC_CAIXIN,
             detail="Caixin China Manufacturing PMI — compiled by S&P Global from ~500 smaller, private, export-oriented manufacturers (rebranded 'RatingDog' in 2025 after Caixin's sponsorship ended). Running above the official NBS gauge — private / export manufacturers are outperforming.",
             detail_zh="财新中国制造业 PMI — 由标普全球 S&P Global 编制、调查约 500 家中小型民营出口制造商(2025 年财新冠名结束后更名为「RatingDog」)。高于官方 NBS — 民营/出口制造商表现更强。"),
    ]

    # ---- more ----
    fc = fred_cache()
    exp = parse_csv(fc.get("XTEXVA01CNM667S", "")) if fc.get("XTEXVA01CNM667S") else []
    imp = parse_csv(fc.get("XTIMVA01CNM667S", "")) if fc.get("XTIMVA01CNM667S") else []
    if exp:
        out["more"].append({"key": "exports", "k": "Exports", "k_zh": "出口", "v": f"${exp[-1][1] / 1e9:.0f}B/mo",
                            "as_of": exp[-1][0][:7], "source": SRC_FRED, "freq": "monthly",
                            "view": {"metric": "value", "ref": 0, "good": "high"}, "series": yoy(exp)[-18:]})
    if imp:
        out["more"].append({"key": "imports", "k": "Imports", "k_zh": "进口", "v": f"${imp[-1][1] / 1e9:.0f}B/mo",
                            "as_of": imp[-1][0][:7], "source": SRC_FRED, "freq": "monthly",
                            "view": {"metric": "value", "ref": 0, "good": "high"}, "series": yoy(imp)[-18:]})
    if exp and imp:
        ied = {ym: v for ym, v in imp}
        bal = [[ym, round((v - ied[ym]) / 1e9)] for ym, v in exp if ym in ied][-18:]
        out["more"].append({"key": "tbal", "k": "Trade balance", "k_zh": "贸易顺差", "v": f"+${bal[-1][1]}B/mo", "glo": "Trade balance",
                            "as_of": exp[-1][0][:7], "source": SRC_FRED, "freq": "monthly",
                            "view": {"metric": "value", "ref": 0, "good": "high"}, "series": bal})

    # M2 — chart is a level (CNY bn); show month-over-month momentum as the trend, YoY as headline.
    m2 = te.get("m2_level", [])
    m2mom = [[m2[i][0], round((m2[i][1] - m2[i - 1][1]) / m2[i - 1][1] * 100, 2)] for i in range(1, len(m2)) if m2[i - 1][1]]
    out["more"].append({"key": "m2", "k": "M2 growth", "k_zh": "M2 货币供应", "v": CURRENT["m2"]["v"], "glo": "M2 growth",
                        "as_of": CURRENT["m2"]["as_of"], "source": SRC_NBS, "freq": "monthly",
                        "view": {"metric": "value", "ref": 0, "good": "high", "reflbl": "MoM %"}, "series": m2mom,
                        "detail": "Broad money M2, YoY +8.6% (headline). Trend = month-over-month growth, consistently positive (steady monetary expansion).",
                        "detail_zh": "广义货币 M2,同比 +8.6%(头条)。趋势为环比增速,持续为正(货币稳步扩张)。"})
    out["more"].append({"key": "unemp", "k": "Surveyed unemployment", "k_zh": "城镇调查失业率", "v": CURRENT["unemp"]["v"], "glo": "Surveyed unemployment",
                        "as_of": CURRENT["unemp"]["as_of"], "source": SRC_NBS, "freq": "monthly",
                        "view": {"metric": "value", "ref": 5.5, "good": "low", "reflbl": "5.5% threshold"}, "series": te["unemp"]})

    # High-tech exports + Auto production (both annual, manually maintained from the authoritative
    # China source — GACC Customs / CAAM — which is more current than the World Bank / OICA mirrors,
    # whose latest releases lag by 2-3 years). Refresh once a year from the official full-year release.
    # GACC 2025: high-tech product exports ¥5.25T (+13.2% YoY) ≈ $735B at ~7.15 CNY/USD.
    # Single source only: GACC's own current print. We deliberately do NOT splice the World Bank
    # "high-technology exports" historical series onto it (different definition + USD methodology,
    # and WB only runs to 2023) — one indicator, one source. Hence just the current point, no
    # multi-year sparkline until a clean GACC YoY history is available.
    out["more"].append({"key": "htx", "k": "High-tech exports", "k_zh": "高科技出口", "v": "$735B", "as_of": "2025",
                        "source": "China Customs (GACC)", "freq": "annual", "glo": "High-tech exports", "manual": True,
                        "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [["2025", 13.2]]})
    # CAAM 2025: vehicle production 34.53M units (+10.4% YoY).
    out["more"].append({"key": "auto", "k": "Auto production", "k_zh": "汽车产量", "v": "34.5M/yr", "as_of": "2025",
                        "source": "CAAM", "freq": "annual", "glo": "Auto production", "manual": True,
                        "view": {"metric": "yoy", "ref": 0, "good": "high"}, "series": [["2021", 26.1], ["2022", 27.0], ["2023", 30.2], ["2024", 31.3], ["2025", 34.5]]})

    (WEB / "china-macro.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote web/china-macro.json (read {READ_DATE})")
    for it in out["headline"] + out["more"]:
        print(f"  {it['k']:24} {it['v']:>10}  as_of={it['as_of']:<8} {it['freq']:<9} series_n={len(it['series']):<3} {it['source']}")


if __name__ == "__main__":
    main()
