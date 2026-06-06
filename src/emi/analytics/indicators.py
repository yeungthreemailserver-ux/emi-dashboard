"""Phase 1 financial indicators built from the long-format `financials` table.

Quarterly XBRL from US filers typically carries Q1/Q2/Q3 standalone (Q4 is reported only
inside the annual 10-K), so year-over-year is computed by matching the closest quarter
~one year earlier rather than a fixed row shift (the Q3->Q1 gap is six months).
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from ..config import DB_PATH

DAYS_PER_QUARTER = 365.25 / 4

_FLOW_COLS = ["revenue", "cost_of_revenue", "gross_profit", "operating_income",
              "net_income", "rd_expense", "sga_expense"]
_INSTANT_COLS = ["inventory", "accounts_receivable", "total_assets", "cash"]


def _read(sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def load_financials() -> pd.DataFrame:
    df = _read("SELECT * FROM financials")
    if not df.empty:
        df["period_end"] = pd.to_datetime(df["period_end"])
    return df


def load_companies() -> pd.DataFrame:
    return _read("SELECT * FROM companies")


def _pivot(df: pd.DataFrame, frame: str) -> pd.DataFrame:
    sub = df[df["frame"] == frame]
    if sub.empty:
        return pd.DataFrame(columns=["ticker", "period_end"])
    return (sub.pivot_table(index=["ticker", "period_end"], columns="metric",
                            values="value", aggfunc="last")
               .reset_index())


def build_quarterly_panel() -> pd.DataFrame:
    """One row per (ticker, quarter-end) with derived margins, inventory days, and revenue YoY."""
    df = load_financials()
    if df.empty:
        return df
    flows = _pivot(df, "quarterly")
    insts = _pivot(df, "instant")
    if flows.empty:
        return flows
    panel = flows.merge(insts, on=["ticker", "period_end"], how="left")

    for col in _FLOW_COLS + _INSTANT_COLS:
        if col not in panel:
            panel[col] = pd.NA
        panel[col] = pd.to_numeric(panel[col], errors="coerce")

    # Fill gross profit when the company didn't tag GrossProfit directly.
    panel["gross_profit"] = panel["gross_profit"].where(
        panel["gross_profit"].notna(), panel["revenue"] - panel["cost_of_revenue"])

    panel["gross_margin"] = panel["gross_profit"] / panel["revenue"]
    panel["operating_margin"] = panel["operating_income"] / panel["revenue"]
    panel["net_margin"] = panel["net_income"] / panel["revenue"]
    panel["rd_intensity"] = panel["rd_expense"] / panel["revenue"]
    panel["inventory_days"] = panel["inventory"] / panel["cost_of_revenue"] * DAYS_PER_QUARTER

    # Revenue YoY: match the closest quarter ~one year earlier (±25 days).
    prev = (panel[["ticker", "period_end", "revenue"]]
            .rename(columns={"revenue": "revenue_prev_yr"}))
    prev["period_end"] = prev["period_end"] + pd.DateOffset(years=1)
    panel = pd.merge_asof(
        panel.sort_values("period_end"),
        prev.sort_values("period_end"),
        on="period_end", by="ticker", direction="nearest",
        tolerance=pd.Timedelta(days=25),
    )
    panel["revenue_yoy"] = panel["revenue"] / panel["revenue_prev_yr"] - 1
    return panel.sort_values(["ticker", "period_end"]).reset_index(drop=True)


def latest_snapshot() -> pd.DataFrame:
    """Latest reported quarter per company, joined to tier/name/end-market metadata."""
    panel = build_quarterly_panel()
    if panel.empty:
        return panel
    latest = panel.groupby("ticker", as_index=False).tail(1)
    out = load_companies().merge(latest, on="ticker", how="inner")
    cols = ["tier", "ticker", "name", "region", "period_end", "revenue", "revenue_yoy",
            "gross_margin", "operating_margin", "net_margin", "inventory_days",
            "rd_intensity", "end_markets"]
    return out[[c for c in cols if c in out.columns]].sort_values(["tier", "ticker"])


def company_series(ticker: str) -> pd.DataFrame:
    panel = build_quarterly_panel()
    if panel.empty:
        return panel
    return panel[panel["ticker"] == ticker.upper()].sort_values("period_end")


def tier_summary(snap: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-tier roll-up of the latest snapshot: breadth of growth, margin, inventory."""
    snap = latest_snapshot() if snap is None else snap
    if snap.empty:
        return snap
    g = snap.groupby("tier")
    out = pd.DataFrame({
        "companies": g["ticker"].nunique(),
        "median_rev_yoy": g["revenue_yoy"].median(),
        "median_op_margin": g["operating_margin"].median(),
        "median_inv_days": g["inventory_days"].median(),
        "pct_growing": g["revenue_yoy"].apply(lambda s: (s > 0).mean()),
    })
    return out.reset_index().sort_values("median_rev_yoy", ascending=False)


def end_market_matrix(snap: pd.DataFrame | None = None) -> pd.DataFrame:
    """Demand read by end-market: revenue-weighted and median YoY across tagged companies."""
    snap = latest_snapshot() if snap is None else snap
    if snap.empty:
        return pd.DataFrame()
    ex = snap.assign(end_market=snap["end_markets"].fillna("").str.split(",")).explode("end_market")
    ex["end_market"] = ex["end_market"].str.strip()
    ex = ex[ex["end_market"] != ""]
    g = ex.groupby("end_market")
    out = pd.DataFrame({
        "companies": g["ticker"].nunique(),
        "median_yoy": g["revenue_yoy"].median(),
        "median_op_margin": g["operating_margin"].median(),
    })
    m = ex[["end_market", "revenue", "revenue_yoy"]].dropna()
    num = (m["revenue"] * m["revenue_yoy"]).groupby(m["end_market"]).sum()
    den = m["revenue"].groupby(m["end_market"]).sum()
    out["wtd_yoy"] = num / den
    return out.reset_index().sort_values("wtd_yoy", ascending=False)
