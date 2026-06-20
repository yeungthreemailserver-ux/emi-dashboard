r"""Probe: does yfinance deliver global financials + forward consensus across regions?

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\test_yf.py
"""
import pandas as pd
import yfinance as yf

pd.set_option("display.width", 220)

# US, ADR, Taiwan-local, Korea, Japan, Europe — one per region pattern.
TICKERS = ["NVDA", "TSM", "2330.TW", "005930.KS", "8035.T", "ASML.AS"]
ROWS = ["Total Revenue", "Gross Profit", "Operating Income", "Net Income"]


def b(x):
    try:
        return f"{x / 1e9:,.2f}B"
    except Exception:
        return str(x)


for tk in TICKERS:
    print("=" * 72)
    print(tk)
    try:
        t = yf.Ticker(tk)
        info = t.info or {}
        print(f"  name={info.get('shortName')}  currency={info.get('financialCurrency')}")

        qi = t.quarterly_income_stmt
        if qi is not None and not qi.empty:
            cols = list(qi.columns[:3])
            print(f"  quarters: {[str(c.date()) for c in cols]}")
            for r in ROWS:
                if r in qi.index:
                    print(f"    {r:18s}: " + " | ".join(b(qi.loc[r, c]) for c in cols))
        else:
            print("  (no quarterly income stmt)")

        qb = t.quarterly_balance_sheet
        if qb is not None and not qb.empty and "Inventory" in qb.index:
            c = qb.columns[0]
            print(f"  Inventory  {c.date()} = {b(qb.loc['Inventory', c])}")

        qc = t.quarterly_cashflow
        if qc is not None and not qc.empty:
            for key in ("Capital Expenditure", "Capital Expenditures"):
                if key in qc.index:
                    c = qc.columns[0]
                    print(f"  Capex      {c.date()} = {b(qc.loc[key, c])}")
                    break

        try:
            re = t.revenue_estimate
            if re is not None and not re.empty:
                print("  revenue_estimate (forward consensus):")
                print("    " + re.to_string().replace("\n", "\n    "))
        except Exception as e:
            print(f"  revenue_estimate unavailable: {e!r}")
    except Exception as e:
        print(f"  ERROR: {e!r}")
