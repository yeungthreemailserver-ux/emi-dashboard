r"""Print the latest-quarter financial snapshot across the universe (Phase 1 verification).

    $env:PYTHONPATH = "src"
    .\.venv\Scripts\python.exe scripts\show_snapshot.py
"""
from __future__ import annotations

import pandas as pd

from emi.analytics import indicators


def main() -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 300)

    snap = indicators.latest_snapshot()
    if snap.empty:
        print("No data — run scripts/run_ingest.py first.")
        return

    show = pd.DataFrame({
        "tier": snap["tier"],
        "ticker": snap["ticker"],
        "name": snap["name"].str.slice(0, 22),
        "quarter": pd.to_datetime(snap["period_end"]).dt.date,
        "rev_$B": (snap["revenue"] / 1e9).round(2),
        "yoy_%": (snap["revenue_yoy"] * 100).round(1),
        "gm_%": (snap["gross_margin"] * 100).round(1),
        "om_%": (snap["operating_margin"] * 100).round(1),
        "inv_days": snap["inventory_days"].round(0),
    })
    print(show.to_string(index=False))
    print(f"\n{len(show)} companies with quarterly financials.")


if __name__ == "__main__":
    main()
