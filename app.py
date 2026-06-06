r"""Electronic Market Intelligence — Streamlit dashboard (Phase 1: financial spine).

Launch:
    $env:PYTHONPATH = "src"   # optional; app.py also injects src/ onto sys.path
    .\.venv\Scripts\python.exe -m streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from emi.analytics import indicators

st.set_page_config(page_title="Electronic Market Intelligence", layout="wide", page_icon="📡")

GREEN_RED = "RdYlGn"


@st.cache_data(show_spinner=False)
def get_snapshot():
    return indicators.latest_snapshot()


@st.cache_data(show_spinner=False)
def get_panel():
    return indicators.build_quarterly_panel()


@st.cache_data(show_spinner=False)
def get_companies():
    return indicators.load_companies()


snap = get_snapshot()
panel = get_panel()

st.title("📡 Electronic Market Intelligence")
st.caption("Free/public data (SEC EDGAR) · corporate-strategy lens · Phase 1 — financial spine")

if snap.empty:
    st.warning("No data yet. Run `scripts/run_ingest.py` first.")
    st.stop()

as_of = panel["period_end"].max()
st.sidebar.markdown(f"**Latest quarter in data:** {as_of:%Y-%m-%d}")
section = st.sidebar.radio(
    "View",
    ["Cycle pulse", "Competitive scorecard", "End-market demand", "Company drill-down"],
)
st.sidebar.caption("Financials are as-reported (SEC XBRL). Margins shown only where the "
                   "company tags the line item.")


def pct(series):
    return series * 100


# ----------------------------------------------------------------------------- Cycle pulse
if section == "Cycle pulse":
    st.subheader("Cycle pulse — breadth of growth and inventory pressure")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Median revenue YoY", f"{snap['revenue_yoy'].median() * 100:.1f}%")
    c2.metric("% companies growing", f"{(snap['revenue_yoy'] > 0).mean() * 100:.0f}%")
    c3.metric("Median inventory-days", f"{snap['inventory_days'].median():.0f}")
    c4.metric("Companies covered", f"{snap['ticker'].nunique()}")

    ts = indicators.tier_summary(snap)

    fig = px.bar(ts.sort_values("median_rev_yoy"), x="median_rev_yoy", y="tier",
                 orientation="h", color="median_rev_yoy", color_continuous_scale=GREEN_RED,
                 title="Median revenue YoY by tier")
    fig.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig, width="stretch")

    fig2 = px.bar(ts.sort_values("median_inv_days"), x="median_inv_days", y="tier",
                  orientation="h", color="median_inv_days", color_continuous_scale="Reds",
                  title="Median inventory-days by tier (higher = more destocking risk)")
    st.plotly_chart(fig2, width="stretch")

    disp = ts.assign(
        median_rev_yoy=pct(ts["median_rev_yoy"]),
        median_op_margin=pct(ts["median_op_margin"]),
        pct_growing=pct(ts["pct_growing"]),
    )
    st.dataframe(disp, width="stretch", hide_index=True, column_config={
        "median_rev_yoy": st.column_config.NumberColumn("Median Rev YoY %", format="%.1f"),
        "median_op_margin": st.column_config.NumberColumn("Median Op %", format="%.1f"),
        "median_inv_days": st.column_config.NumberColumn("Median Inv days", format="%.0f"),
        "pct_growing": st.column_config.NumberColumn("% growing", format="%.0f"),
    })

# ------------------------------------------------------------------- Competitive scorecard
elif section == "Competitive scorecard":
    st.subheader("Competitive scorecard — latest reported quarter")
    tiers = sorted(snap["tier"].unique())
    chosen = st.sidebar.multiselect("Tiers", tiers, default=tiers)
    df = snap[snap["tier"].isin(chosen)].copy()

    show = df[["tier", "ticker", "name"]].copy()
    show["quarter"] = df["period_end"].dt.date
    show["Rev $B"] = df["revenue"] / 1e9
    show["Rev YoY %"] = pct(df["revenue_yoy"])
    show["Gross %"] = pct(df["gross_margin"])
    show["Op %"] = pct(df["operating_margin"])
    show["Net %"] = pct(df["net_margin"])
    show["Inv days"] = df["inventory_days"]
    show["end-markets"] = df["end_markets"]

    st.dataframe(show, width="stretch", hide_index=True, column_config={
        "Rev $B": st.column_config.NumberColumn(format="%.2f"),
        "Rev YoY %": st.column_config.NumberColumn(format="%.1f"),
        "Gross %": st.column_config.NumberColumn(format="%.1f"),
        "Op %": st.column_config.NumberColumn(format="%.1f"),
        "Net %": st.column_config.NumberColumn(format="%.1f"),
        "Inv days": st.column_config.NumberColumn(format="%.0f"),
    })
    st.caption("Tip: click a column header to sort (e.g. by Rev YoY % or Inv days).")

# -------------------------------------------------------------------- End-market demand
elif section == "End-market demand":
    st.subheader("End-market demand — revenue-weighted YoY across tagged companies")
    em = indicators.end_market_matrix(snap)

    fig = px.bar(em.sort_values("wtd_yoy"), x="wtd_yoy", y="end_market", orientation="h",
                 color="wtd_yoy", color_continuous_scale=GREEN_RED, text="companies",
                 title="Revenue-weighted revenue YoY by end-market (bar label = # companies)")
    fig.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig, width="stretch")

    disp = em.assign(median_yoy=pct(em["median_yoy"]), wtd_yoy=pct(em["wtd_yoy"]),
                     median_op_margin=pct(em["median_op_margin"]))
    st.dataframe(disp, width="stretch", hide_index=True, column_config={
        "median_yoy": st.column_config.NumberColumn("Median YoY %", format="%.1f"),
        "wtd_yoy": st.column_config.NumberColumn("Rev-wtd YoY %", format="%.1f"),
        "median_op_margin": st.column_config.NumberColumn("Median Op %", format="%.1f"),
    })

# --------------------------------------------------------------------- Company drill-down
elif section == "Company drill-down":
    tickers = sorted(panel["ticker"].unique())
    default_ix = tickers.index("NVDA") if "NVDA" in tickers else 0
    ticker = st.sidebar.selectbox("Company", tickers, index=default_ix)

    meta = get_companies()
    row = meta[meta["ticker"] == ticker]
    if not row.empty:
        r = row.iloc[0]
        st.subheader(f"{r['name']} ({ticker}) — {r['tier']} · {r['region']}")
        st.caption(f"End-markets: {r['end_markets']}")

    cs = panel[panel["ticker"] == ticker].sort_values("period_end")

    fig = go.Figure()
    fig.add_bar(x=cs["period_end"], y=cs["revenue"] / 1e9, name="Revenue $B",
                marker_color="#4C78A8")
    fig.add_scatter(x=cs["period_end"], y=pct(cs["gross_margin"]), name="Gross %",
                    yaxis="y2", mode="lines+markers")
    fig.add_scatter(x=cs["period_end"], y=pct(cs["operating_margin"]), name="Op %",
                    yaxis="y2", mode="lines+markers")
    fig.update_layout(
        title=f"{ticker} — quarterly revenue & margins",
        yaxis=dict(title="Revenue $B"),
        yaxis2=dict(title="Margin %", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, width="stretch")

    col1, col2 = st.columns(2)
    f2 = px.line(cs, x="period_end", y="inventory_days", markers=True,
                 title="Inventory-days")
    col1.plotly_chart(f2, width="stretch")
    f3 = px.bar(cs, x="period_end", y="revenue_yoy", title="Revenue YoY")
    f3.update_yaxes(tickformat=".0%")
    col2.plotly_chart(f3, width="stretch")
