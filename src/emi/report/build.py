r"""Compute per-company quarterly metrics + consensus and export web/data.json.

The terminal aggregates layers CLIENT-SIDE from per-company quarterly arrays, so it can
filter by country / consensus-availability on the fly. Each company carries, per quarter,
{value, yoy, qoq} for every metric (growth computed on the company's OWN fiscal sequence,
so calendar-bucketing never distorts it). Absolute values are FX-normalized to USD.

Run:  $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m emi.report.build
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .. import db
from ..config import DB_PATH, ROOT
from ..ingest.fx import fetch_fx

WEB_DIR = ROOT / "web"
DATA_JSON = WEB_DIR / "data.json"
FLAGS_YAML = ROOT / "config" / "flags.yaml"
SEGMENTS_YAML = ROOT / "config" / "segments.yaml"


def load_flags() -> tuple[dict, dict]:
    """Return (conglomerate_notes, private_estimate_notes), each ticker -> note."""
    if not FLAGS_YAML.exists():
        return {}, {}
    import yaml
    doc = yaml.safe_load(FLAGS_YAML.read_text(encoding="utf-8")) or {}
    conglo = {str(tk): note for tk, note in (doc.get("conglomerate") or {}).items()}
    est = {str(tk): note for tk, note in (doc.get("private_estimate") or {}).items()}
    return conglo, est


def load_segments() -> dict:
    """ticker -> {share?: float, note: str} — narrow consolidated revenue to the layer-relevant segment."""
    if not SEGMENTS_YAML.exists():
        return {}
    import yaml
    doc = yaml.safe_load(SEGMENTS_YAML.read_text(encoding="utf-8")) or {}
    return {str(tk): v for tk, v in (doc.get("segment_share") or {}).items()}


def apply_segments(companies: list, segments: dict) -> int:
    """Scale a company's revenue (and its analyst consensus) to the layer-relevant segment share;
    blank other (consolidated) metrics. cons_share scales only consensus (when actual is overridden
    elsewhere, e.g. Samsung memory) so the forecast columns stay apple-to-apple with the actuals."""
    n = 0
    for c in companies:
        seg = segments.get(c["ticker"])
        if not seg:
            continue
        c["seg_note"] = seg.get("note")
        sh = seg.get("share")
        if sh is not None:
            n += 1
            rev = c["metrics"]["revenue"]
            if rev.get("usd") is not None:
                rev["usd"] = round(rev["usd"] * sh, 1)
            rv = c["q"]["revenue"]
            rv["v"] = [round(v * sh, 1) if v is not None else None for v in rv["v"]]  # yoy/qoq ratios unchanged
            for m in ("operating_income", "net_income", "gross_margin", "inventory_days", "capex"):
                c["metrics"][m] = {k: None for k in c["metrics"][m]}
                qm = c["q"].get(m)
                if qm:
                    for k in qm:
                        qm[k] = [None] * len(qm[k])
        # scale the (consolidated) consensus to the same segment, then recompute this-Q QoQ off the
        # segment actual; drop EPS consensus (consolidated, not comparable).
        cs = seg.get("cons_share", sh)
        if cs is not None:
            crev = (c.get("consensus") or {}).get("revenue")
            if crev:
                for k in ("this_q_usd", "next_q_usd"):
                    if crev.get(k) is not None:
                        crev[k] = round(crev[k] * cs, 1)
                base = c["metrics"]["revenue"].get("usd")
                crev["this_q_qoq"] = round(crev["this_q_usd"] / base - 1, 4) if (crev.get("this_q_usd") and base) else None
            if c.get("consensus"):
                c["consensus"].pop("earnings", None)
    return n
DAYS_Q = 365.25 / 4
QH = 28  # quarters of history emitted per company (~7y where EDGAR backfill reaches)
LAYER_ORDER = ["L1", "L2", "L3", "L0", "L4", "L5"]  # Distribution (L0) after Components (L3)
METRICS = ["revenue", "gross_margin", "operating_income", "net_income", "inventory_days", "capex"]


def _f(x, nd=4):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if np.isnan(x) or np.isinf(x):
        return None
    return round(x, nd)


def _i(x):
    v = _f(x)
    return int(v) if v is not None else None


def _s(x):
    try:
        return None if pd.isna(x) else x
    except (TypeError, ValueError):
        return x


def _q_to_int(p):
    y, q = p.split("Q")
    return int(y) * 4 + (int(q) - 1)


def _int_to_q(v):
    y, q = divmod(v, 4)
    return f"{y}Q{q + 1}"


def _read():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        comp = pd.read_sql_query("SELECT * FROM companies", conn)
        fin = pd.read_sql_query("SELECT * FROM financials", conn, parse_dates=["period_end"])
        est = pd.read_sql_query("SELECT * FROM estimates", conn)
        fx = pd.read_sql_query("SELECT * FROM fx_rates", conn)
        try:
            guid = pd.read_sql_query("SELECT * FROM guidance", conn)
        except Exception:
            guid = pd.DataFrame()
    finally:
        conn.close()
    return comp, fin, est, fx, guid


def guidance_map(guid: pd.DataFrame) -> dict:
    """ticker -> {revenue:{mid,low,high}, gross_margin:{mid}, period, filed} (company-issued, USD)."""
    out: dict = {}
    if guid is None or guid.empty:
        return out
    for _, r in guid.iterrows():
        g = out.setdefault(r["ticker"], {})
        if r["metric"] == "revenue":
            g["revenue"] = {"mid": _f(r["mid"], 1), "low": _f(r["low"], 1), "high": _f(r["high"], 1)}
        elif r["metric"] == "gross_margin":
            g["gross_margin"] = {"mid": _f(r["mid"])}
        g["period"] = _s(r["period_text"])
        g["filed"] = _s(r["filed"])
    return out


def ensure_fx(comp) -> dict:
    rates = fetch_fx(comp["currency"].dropna().unique().tolist())
    asof = datetime.now(timezone.utc).date().isoformat()
    db.upsert_fx([{"currency": c, "to_usd": r, "asof": asof} for c, r in rates.items()])
    return rates


def build_panels(fin: pd.DataFrame, rate: dict) -> pd.DataFrame:
    fin = fin.copy()
    fin["to_usd"] = fin["unit"].map(rate).fillna(1.0)
    fin["usd"] = fin["value"] * fin["to_usd"]
    fin["period_end"] = pd.to_datetime(fin["period_end"])
    fin["calq"] = fin["period_end"].dt.to_period("Q").astype(str)
    fin = fin[fin["frame"].isin(["quarterly", "instant"])].copy()
    # Merge sources by calendar quarter: prefer Yahoo, fall back to EDGAR (fills NVDA/MRVL gaps).
    fin["src_rank"] = fin["source"].map({"yahoo": 0, "edgar": 1}).fillna(2)
    fin = (fin.sort_values(["ticker", "metric", "calq", "src_rank", "period_end"])
              .drop_duplicates(["ticker", "metric", "calq"], keep="first"))

    val = fin.pivot_table(index=["ticker", "calq"], columns="metric", values="value", aggfunc="last")
    usd = fin.pivot_table(index=["ticker", "calq"], columns="metric", values="usd", aggfunc="last")
    pe = fin.groupby(["ticker", "calq"])["period_end"].max()
    for c in ["revenue", "cost_of_revenue", "gross_profit", "operating_income", "net_income", "capex", "inventory"]:
        if c not in val:
            val[c] = np.nan
        if c not in usd:
            usd[c] = np.nan

    gp_n = val["gross_profit"].where(val["gross_profit"].notna(), val["revenue"] - val["cost_of_revenue"])
    df = pd.DataFrame(index=val.index)
    df["revenue_usd"] = usd["revenue"]
    df["operating_income_usd"] = usd["operating_income"]
    df["net_income_usd"] = usd["net_income"]
    df["capex_usd"] = usd["capex"]
    df["gross_margin"] = gp_n / val["revenue"]
    df["operating_margin"] = val["operating_income"] / val["revenue"]
    df["net_margin"] = val["net_income"] / val["revenue"]
    df["inventory_days"] = val["inventory"] / val["cost_of_revenue"] * DAYS_Q
    df["period_end"] = pe
    df = df.reset_index().sort_values(["ticker", "calq"])

    def _shift(q, k):  # calendar-quarter arithmetic on 'YYYYQn'
        v = int(q[:4]) * 4 + (int(q[5]) - 1) - k
        y, n = divmod(v, 4)
        return f"{y}Q{n + 1}"

    def _ok(x):
        return x is not None and pd.notna(x)

    USD_COLS = ["revenue_usd", "operating_income_usd", "net_income_usd", "capex_usd"]
    DIFF_COLS = ["gross_margin", "operating_margin", "net_margin", "inventory_days"]
    parts = []
    for _, g in df.groupby("ticker"):
        g = g.sort_values("calq").copy()
        for col in USD_COLS + DIFF_COLS:
            m = dict(zip(g["calq"], g[col]))
            usd = col in USD_COLS
            yoy, qoq = [], []
            for q in g["calq"]:
                cur, p4, p1 = m.get(q), m.get(_shift(q, 4)), m.get(_shift(q, 1))
                if usd:  # calendar-aligned growth; None when the comparison quarter is missing
                    yoy.append(cur / p4 - 1 if (_ok(cur) and _ok(p4) and p4 != 0) else None)
                    qoq.append(cur / p1 - 1 if (_ok(cur) and _ok(p1) and p1 != 0) else None)
                else:
                    yoy.append(cur - p4 if (_ok(cur) and _ok(p4)) else None)
                    qoq.append(cur - p1 if (_ok(cur) and _ok(p1)) else None)
            g[col + "_yoy"] = yoy
            g[col + "_qoq"] = qoq
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def consensus_by_ticker(est: pd.DataFrame, rate: dict, last_rev_usd: dict) -> dict:
    out: dict[str, dict] = {}
    for tk, g in est.groupby("ticker"):
        g = g.set_index(["metric", "period"])
        r, cur_rate = {}, (rate.get(g["currency"].iloc[0], 1.0) if "currency" in g else 1.0)
        for metric in ["revenue", "earnings"]:
            def cell(period, field):
                try:
                    return g.loc[(metric, period), field]
                except KeyError:
                    return None
            entry = {"this_q_yoy": _f(cell("0q", "growth")), "next_q_yoy": _f(cell("+1q", "growth")),
                     "num_analysts": _i(cell("0q", "num_analysts"))}
            if metric == "revenue":
                this_avg, next_avg = cell("0q", "avg"), cell("+1q", "avg")
                entry["this_q_usd"] = _f((this_avg or np.nan) * cur_rate, 1)
                entry["next_q_usd"] = _f((next_avg or np.nan) * cur_rate, 1)
                base = last_rev_usd.get(tk)
                entry["this_q_qoq"] = _f(((this_avg * cur_rate) / base - 1) if (this_avg and base) else None)
            r[metric] = entry
        out[tk] = r
    return out


# canonical metric -> (value col, yoy col, qoq col, decimals)
QMAP = {
    "revenue": ("revenue_usd", "revenue_usd_yoy", "revenue_usd_qoq", 1),
    "gross_margin": ("gross_margin", "gross_margin_yoy", "gross_margin_qoq", 4),
    "operating_income": ("operating_income_usd", "operating_income_usd_yoy", "operating_income_usd_qoq", 1),
    "net_income": ("net_income_usd", "net_income_usd_yoy", "net_income_usd_qoq", 1),
    "inventory_days": ("inventory_days", "inventory_days_yoy", "inventory_days_qoq", 1),
    "capex": ("capex_usd", "capex_usd_yoy", "capex_usd_qoq", 1),
}


def main() -> None:
    comp, fin, est, fx, guid = _read()
    if comp.empty or fin.empty:
        raise SystemExit("No data — run scripts/run_ingest_v2.py first.")
    gmap = guidance_map(guid)
    rate = dict(zip(fx["currency"], fx["to_usd"])) if not fx.empty else {}
    if not rate or set(comp["currency"].dropna()) - set(rate):
        rate = ensure_fx(comp)

    panel = build_panels(fin, rate)
    latest = panel.groupby("ticker", as_index=False).tail(1).set_index("ticker")
    cons = consensus_by_ticker(est, rate, latest["revenue_usd"].to_dict())
    cmeta = comp.set_index("ticker")
    flags, est_notes = load_flags()
    segments = load_segments()

    companies, all_calq = [], set()
    for tk, row in latest.iterrows():
        meta = cmeta.loc[tk] if tk in cmeta.index else None
        hist = panel[panel["ticker"] == tk].tail(QH)
        calq = list(hist["calq"])
        all_calq.update(calq)
        q = {"calq": calq}
        for m, (vc, yc, qc, nd) in QMAP.items():
            q[m] = {"v": [_f(v, nd) for v in hist[vc]],
                    "yoy": [_f(v, nd if m in ("inventory_days",) else 4) for v in hist[yc]],
                    "qoq": [_f(v, nd if m in ("inventory_days",) else 4) for v in hist[qc]]}
        companies.append({
            "ticker": tk,
            "name": (_s(meta["name"]) or tk) if meta is not None else tk,
            "layer": _s(meta["layer"]) if meta is not None else None,
            "sublayer": _s(meta["sublayer"]) if meta is not None else None,
            "sublayer_name": _s(meta["sublayer_name"]) if meta is not None else None,
            "region": _s(meta["region"]) if meta is not None else None,
            "end_market": _s(meta["end_market"]) if meta is not None else None,
            "currency": _s(meta["currency"]) if meta is not None else None,
            "market_cap_usd": _f((meta["market_cap"] * rate.get(meta["currency"], 1.0))
                                 if (meta is not None and pd.notna(meta["market_cap"])) else None, 0),
            "latest_period": row["period_end"].date().isoformat(),
            "metrics": {
                "revenue": {"usd": _f(row["revenue_usd"], 1), "qoq": _f(row["revenue_usd_qoq"]), "yoy": _f(row["revenue_usd_yoy"])},
                "operating_income": {"usd": _f(row["operating_income_usd"], 1), "margin": _f(row["operating_margin"])},
                "net_income": {"usd": _f(row["net_income_usd"], 1), "margin": _f(row["net_margin"])},
                "gross_margin": {"value": _f(row["gross_margin"])},
                "inventory_days": {"value": _f(row["inventory_days"], 1)},
                "capex": {"usd": _f(row["capex_usd"], 1)},
            },
            "consensus": cons.get(tk, {}),
            "guidance": gmap.get(tk),
            "flag": flags.get(tk),
            "estimate_note": est_notes.get(tk),
            "q": q,
        })

    n_seg = apply_segments(companies, segments)

    # layer structure in supply-chain order (Distribution after Components)
    lmeta = {}
    for c in companies:
        L = lmeta.setdefault(c["layer"], {"layer": c["layer"], "layer_name": None, "subs": {}})
        cm = cmeta.loc[c["ticker"]] if c["ticker"] in cmeta.index else None
        L["layer_name"] = _s(cm["layer_name"]) if cm is not None else c["layer"]
        s = L["subs"].setdefault(c["sublayer"], {"sublayer": c["sublayer"], "sublayer_name": c["sublayer_name"], "n": 0})
        s["n"] += 1
    layers = []
    for lid in [x for x in LAYER_ORDER if x in lmeta] + [x for x in lmeta if x not in LAYER_ORDER]:
        L = lmeta[lid]
        subs = [L["subs"][s] for s in sorted(L["subs"])]
        layers.append({"layer": lid, "layer_name": L["layer_name"],
                       "n_companies": sum(s["n"] for s in subs), "sublayers": subs})

    latest_q = max((_q_to_int(c["q"]["calq"][-1]) for c in companies if c["q"]["calq"]), default=0)
    forward = [_int_to_q(latest_q + 1), _int_to_q(latest_q + 2)]
    regions = sorted({c["region"] for c in companies if c["region"]})

    out = {
        "as_of": max((c["latest_period"] for c in companies), default=None),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fx": {k: _f(v, 6) for k, v in rate.items()},
        "metrics": METRICS,
        "n_companies": len(companies),
        "regions": regions,
        "forward": forward,
        "layers": layers,
        "companies": companies,
    }
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    DATA_JSON.write_text(json.dumps(out, allow_nan=False), encoding="utf-8")
    print(f"Wrote {DATA_JSON}  ({DATA_JSON.stat().st_size/1024:.0f} KB)")
    print(f"  companies={len(companies)} layers={[l['layer'] for l in layers]} regions={len(regions)} forward={forward} segment-adjusted={n_seg}")


if __name__ == "__main__":
    main()
