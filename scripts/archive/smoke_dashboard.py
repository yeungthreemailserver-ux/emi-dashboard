r"""Exercise every dashboard view's data + chart logic without a Streamlit runtime.

Catches KeyErrors, pandas/plotly issues, and empty frames before launch.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\smoke_dashboard.py
"""
import plotly.express as px
import plotly.graph_objects as go

from emi.analytics import indicators

snap = indicators.latest_snapshot()
panel = indicators.build_quarterly_panel()
assert not snap.empty, "snapshot empty — run run_ingest.py"
assert not panel.empty, "panel empty"

# Cycle pulse
ts = indicators.tier_summary(snap)
px.bar(ts, x="median_rev_yoy", y="tier", orientation="h", color="median_rev_yoy")
px.bar(ts, x="median_inv_days", y="tier", orientation="h", color="median_inv_days")

# End-market demand
em = indicators.end_market_matrix(snap)
px.bar(em, x="wtd_yoy", y="end_market", orientation="h", color="wtd_yoy", text="companies")

# Company drill-down (test the headline name + a thin-data name)
for t in ["NVDA", "MU", "AAPL", "WOLF"]:
    cs = panel[panel["ticker"] == t]
    fig = go.Figure()
    fig.add_bar(x=cs["period_end"], y=cs["revenue"] / 1e9, name="Revenue $B")
    fig.add_scatter(x=cs["period_end"], y=cs["gross_margin"] * 100, name="Gross %", yaxis="y2")
    px.line(cs, x="period_end", y="inventory_days")
    px.bar(cs, x="period_end", y="revenue_yoy")

print("SMOKE OK")
print(f"  snapshot rows   : {len(snap)}")
print(f"  panel rows      : {len(panel)}  ({panel['ticker'].nunique()} tickers)")
print(f"  tiers           : {len(ts)}")
print(f"  end-markets     : {len(em)}")
print("  top end-markets by rev-wtd YoY:")
for _, r in em.head(5).iterrows():
    print(f"    {r['end_market']:16s} {r['wtd_yoy'] * 100:6.1f}%  ({int(r['companies'])} cos)")
