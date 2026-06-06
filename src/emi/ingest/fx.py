"""FX rates to USD via Yahoo (<CUR>USD=X). Used to normalize layer aggregates.

Growth %, margins, and inventory-days are currency-neutral and need no conversion;
only absolute sums (layer revenue, capex) are converted to USD.
"""
from __future__ import annotations

import time

import yfinance as yf


def fetch_fx(currencies, base: str = "USD") -> dict[str, float]:
    """Return {currency: units_of_USD_per_1_unit}. USD -> 1.0; unknown -> omitted."""
    out = {"USD": 1.0}
    for cur in sorted({c for c in currencies if c and c != "USD"}):
        rate = None
        try:
            hist = yf.Ticker(f"{cur}{base}=X").history(period="5d")
            if hist is not None and not hist.empty:
                close = hist["Close"].dropna()
                if not close.empty:
                    rate = float(close.iloc[-1])
        except Exception:
            rate = None
        if rate:
            out[cur] = rate
        time.sleep(0.2)
    return out
