"""Build web/china-macro.json — CURRENT, dated China macro for the China page.

Senior-exec requirement: latest published prints, each with as_of + source + frequency.

CURRENT values are the latest official releases (NBS — National Bureau of Statistics —
released monthly/quarterly), read via the browser from Trading Economics' China page
(which republishes NBS) on the date in READ_DATE. These are point-in-time reads, recorded
here explicitly so the snapshot is auditable; refresh by re-reading the source.

Sparkline HISTORY comes from free live APIs where available:
  - World Bank (annual): GDP real growth, high-tech exports
  - DBnomics / IMF IFS (monthly): CPI index -> YoY
  - FRED (monthly, via browser cache, data/fred_china.json): exports, imports
Series we can't get free history for show a single current reading vs the reference line.

Run: python scripts/fetch_china_macro.py
"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DATA = ROOT / "data"

READ_DATE = "2026-06"
SRC_NBS = "NBS (via Trading Economics), read Jun 2026"
SRC_FRED = "FRED (OECD/Customs) via browser"

# --- Latest official prints (NBS), read READ_DATE -------------------------
CURRENT = {
    "gdp":    {"v": "+5.0%", "val": 5.0,  "as_of": "2026-Q1", "freq": "quarterly"},  # real GDP YoY
    "cpi":    {"v": "+1.2%", "val": 1.2,  "as_of": "2026-05", "freq": "monthly"},     # CPI YoY
    "ppi":    {"v": "+3.9%", "val": 3.9,  "as_of": "2026-05", "freq": "monthly"},     # PPI YoY
    "ind":    {"v": "+4.5%", "val": 4.5,  "as_of": "2026-05", "freq": "monthly"},     # industrial production YoY
    "retail": {"v": "-0.6%", "val": -0.6, "as_of": "2026-05", "freq": "monthly"},     # retail sales YoY
    "pmi":    {"v": "51.8",  "val": 51.8, "as_of": "2026-05", "freq": "monthly"},     # NBS manufacturing PMI
    "m2":     {"v": "+8.6%", "val": 8.6,  "as_of": "2026-05", "freq": "monthly"},     # M2 YoY
    "unemp":  {"v": "5.1%",  "val": 5.1,  "as_of": "2026-05", "freq": "monthly"},     # surveyed urban unemployment
    "tbal":   {"v": "+$105B/mo", "val": 105, "as_of": "2026-05", "freq": "monthly"},  # trade balance
}


def _get(url, t=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EMI macro)"})
    return urllib.request.urlopen(req, timeout=t).read()


def wb(code):
    d = json.loads(_get(f"https://api.worldbank.org/v2/country/CHN/indicator/{code}?format=json&per_page=40"))
    pts = sorted((p["date"], p["value"]) for p in (d[1] or []) if p["value"] is not None)
    return [[y, round(v, 2)] for y, v in pts]


def dbnomics(sid):
    try:
        d = json.loads(_get(f"https://api.db.nomics.world/v22/series/{sid}?observations=1"))
        docs = d.get("series", {}).get("docs", [])
        return [[p[:7], v] for p, v in zip(docs[0]["period"], docs[0]["value"]) if v is not None] if docs else []
    except Exception:  # noqa: BLE001
        return []


def fred_cache():
    for p in [DATA / "fred_china.json", Path("C:/Users/yeung/Desktop/Stock Intelligence System/SIS Download/china_fred.json")]:
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
    vals = {ym: v for ym, v in rows}
    out = []
    for ym, v in rows:
        y, m = ym.split("-")
        prev = f"{int(y) - 1}-{m}"
        if prev in vals and vals[prev]:
            out.append([ym, round((v - vals[prev]) / abs(vals[prev]) * 100, 1)])
    return out


def tile(key, k, kz, cur_key, view, glo=None, source=SRC_NBS, series=None, detail="", detail_zh=""):
    c = CURRENT[cur_key]
    # default series = single current reading vs reference (when no free history)
    s = series if series else [[c["as_of"], c["val"]]]
    return {"key": key, "k": k, "k_zh": kz, "v": c["v"], "as_of": c["as_of"], "source": source,
            "freq": c["freq"], "glo": glo, "view": view, "series": s, "detail": detail, "detail_zh": detail_zh}


def main():
    out = {"read_date": READ_DATE, "headline": [], "more": []}

    # GDP sparkline history (WB annual real growth) + current quarterly point
    gdp_hist = wb("NY.GDP.MKTP.KD.ZG")[-10:] + [["2026-Q1", CURRENT["gdp"]["val"]]]
    # CPI sparkline history (IMF monthly index -> YoY) + current point
    cpi_idx = dbnomics("IMF/IFS/M.CN.PCPI_IX")
    cpi_hist = (yoy(cpi_idx)[-18:] if len(cpi_idx) > 13 else []) + [["2026-05", CURRENT["cpi"]["val"]]]

    out["headline"] = [
        tile("gdp", "GDP growth", "GDP 增速", "gdp", {"metric": "value", "ref": 0, "good": "high", "reflbl": "0% = recession"},
             series=gdp_hist,
             detail="Real GDP growth, year-over-year (NBS, quarterly). Holding ~5% but cooling from the 2010s.",
             detail_zh="实质 GDP 同比增速(国家统计局,季度)。维持约 5%,较 2010 年代放缓。"),
        tile("cpi", "CPI", "CPI 通胀", "cpi", {"metric": "value", "ref": 0, "good": "band", "band": [0, 3], "reflbl": "0-3% healthy"},
             glo="CPI", series=cpi_hist,
             detail="Consumer inflation, YoY (NBS, monthly). Recovered from 2025 deflation back into a low-but-positive range.",
             detail_zh="消费通胀,同比(国家统计局,月度)。已自 2025 年通缩回升至偏低正区间。"),
        tile("ppi", "PPI", "PPI 出厂价", "ppi", {"metric": "value", "ref": 0, "good": "high", "reflbl": "0%"},
             glo="PPI",
             detail="Producer (factory-gate) prices, YoY (NBS, monthly). Turned positive after a long deflationary run.",
             detail_zh="工业生产者出厂价,同比(国家统计局,月度)。在长期通缩后转正。"),
        tile("ind", "Industrial production", "工业增加值", "ind", {"metric": "value", "ref": 0, "good": "high", "reflbl": "0%"},
             glo="Industrial production",
             detail="Above-scale industrial value-added, YoY (NBS, monthly).",
             detail_zh="规模以上工业增加值,同比(国家统计局,月度)。"),
        tile("retail", "Retail sales", "社零消费", "retail", {"metric": "value", "ref": 0, "good": "high", "reflbl": "0%"},
             glo="Retail sales",
             detail="Retail sales of consumer goods, YoY (NBS, monthly). Negative = consumption contracting — a key weak spot.",
             detail_zh="社会消费品零售总额,同比(国家统计局,月度)。为负 = 消费收缩,是关键弱点。"),
        tile("pmi", "Mfg PMI", "制造业 PMI", "pmi", {"metric": "value", "ref": 50, "good": "high", "reflbl": "50 = boom/bust"},
             glo="Caixin Mfg PMI",
             detail="Official NBS manufacturing PMI (monthly). Above 50 = expansion.",
             detail_zh="官方制造业 PMI(国家统计局,月度)。高于 50 = 扩张。"),
    ]

    # ---- more ----
    fc = fred_cache()
    exp = parse_csv(fc.get("XTEXVA01CNM667S", "")) if fc.get("XTEXVA01CNM667S") else []
    imp = parse_csv(fc.get("XTIMVA01CNM667S", "")) if fc.get("XTIMVA01CNM667S") else []
    if exp:
        out["more"].append({"key": "exports", "k": "Exports", "k_zh": "出口", "v": f"${exp[-1][1] / 1e9:.0f}B/mo",
                            "as_of": exp[-1][0][:7], "source": SRC_FRED, "freq": "monthly",
                            "view": {"metric": "value", "ref": 0, "good": "high"}, "series": yoy(exp)[-24:]})
    if imp:
        out["more"].append({"key": "imports", "k": "Imports", "k_zh": "进口", "v": f"${imp[-1][1] / 1e9:.0f}B/mo",
                            "as_of": imp[-1][0][:7], "source": SRC_FRED, "freq": "monthly",
                            "view": {"metric": "value", "ref": 0, "good": "high"}, "series": yoy(imp)[-24:]})
    out["more"] += [
        {"key": "tbal", "k": "Trade balance", "k_zh": "贸易顺差", "v": CURRENT["tbal"]["v"], "glo": "Trade balance",
         "as_of": CURRENT["tbal"]["as_of"], "source": SRC_NBS, "freq": "monthly",
         "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [[CURRENT["tbal"]["as_of"], CURRENT["tbal"]["val"]]]},
        {"key": "m2", "k": "M2 growth", "k_zh": "M2 货币供应", "v": CURRENT["m2"]["v"], "glo": "M2 growth",
         "as_of": CURRENT["m2"]["as_of"], "source": SRC_NBS, "freq": "monthly",
         "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [[CURRENT["m2"]["as_of"], CURRENT["m2"]["val"]]]},
        {"key": "unemp", "k": "Surveyed unemployment", "k_zh": "城镇调查失业率", "v": CURRENT["unemp"]["v"], "glo": "Surveyed unemployment",
         "as_of": CURRENT["unemp"]["as_of"], "source": SRC_NBS, "freq": "monthly",
         "view": {"metric": "value", "ref": 5.5, "good": "low"}, "series": [[CURRENT["unemp"]["as_of"], CURRENT["unemp"]["val"]]]},
    ]
    # High-tech exports (WB annual) + Auto (OICA, manual)
    htx = wb("TX.VAL.TECH.CD")[-10:]
    htx_yoy = [[htx[i][0], round((htx[i][1] - htx[i - 1][1]) / htx[i - 1][1] * 100, 1)] for i in range(1, len(htx)) if htx[i - 1][1]]
    out["more"].append({"key": "htx", "k": "High-tech exports", "k_zh": "高科技出口", "v": f"${round(htx[-1][1] / 1e9)}B",
                        "as_of": htx[-1][0], "source": "World Bank", "freq": "annual", "glo": "High-tech exports",
                        "view": {"metric": "value", "ref": 0, "good": "high"}, "series": htx_yoy})
    out["more"].append({"key": "auto", "k": "Auto production", "k_zh": "汽车产量", "v": "31M/yr",
                        "as_of": "2024", "source": "OICA (manual)", "freq": "annual", "glo": "Auto production", "manual": True,
                        "view": {"metric": "yoy", "ref": 0, "good": "high"}, "series": [["2021", 26.1], ["2022", 27.0], ["2023", 30.2], ["2024", 31.3]]})

    (WEB / "china-macro.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote web/china-macro.json (read {READ_DATE})")
    for it in out["headline"] + out["more"]:
        print(f"  {it['k']:24} {it['v']:>10}  as_of={it['as_of']:<8} {it['freq']:<9} {it['source']}")


if __name__ == "__main__":
    main()
