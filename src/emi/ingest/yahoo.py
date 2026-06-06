"""Yahoo Finance ingestion (global financials + forward analyst consensus).

yfinance is an unofficial Yahoo scraper: tolerate gaps/throttling. Raw pulls are cached
under data/raw/yahoo/ so re-runs are instant. Values are in each company's reporting
currency (stored in `unit`); FX-normalization to USD happens in analytics.
"""
from __future__ import annotations

import json
import time

import pandas as pd
import yfinance as yf

from ..config import RAW_DIR

YH_RAW = RAW_DIR / "yahoo"

# yfinance statement row label -> canonical metric
INCOME_MAP = {
    "Total Revenue": "revenue",
    "Cost Of Revenue": "cost_of_revenue",
    "Gross Profit": "gross_profit",
    "Operating Income": "operating_income",
    "Net Income": "net_income",
    "Research And Development": "rd_expense",
}
BALANCE_MAP = {"Inventory": "inventory", "Total Assets": "total_assets"}
CASHFLOW_MAP = {"Capital Expenditure": "capex"}


def _safe(sym: str) -> str:
    return sym.replace(".", "_").replace(":", "_").replace("/", "_")


def _df_to_records(df) -> dict:
    """{period_end(YYYY-MM-DD): {row_label: value}} from a yfinance statement frame."""
    if df is None or getattr(df, "empty", True):
        return {}
    out = {}
    for col in df.columns:
        try:
            key = str(pd.Timestamp(col).date())
        except Exception:
            continue
        out[key] = {str(idx): (None if pd.isna(v) else float(v)) for idx, v in df[col].items()}
    return out


def _est_to_records(df) -> dict:
    if df is None or getattr(df, "empty", True):
        return {}
    out = {}
    for idx, row in df.iterrows():
        rec = {}
        for c, v in row.items():
            if isinstance(v, (int, float)):
                rec[str(c)] = None if pd.isna(v) else float(v)
            else:
                rec[str(c)] = v
        out[str(idx)] = rec
    return out


def fetch_ticker(sym: str, refresh: bool = False, sleep: float = 0.3) -> dict:
    """Fetch + cache one ticker's statements, currency, and consensus estimates."""
    YH_RAW.mkdir(parents=True, exist_ok=True)
    cache = YH_RAW / f"{_safe(sym)}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))

    t = yf.Ticker(sym)
    out = {"symbol": sym}
    try:
        info = t.info or {}
    except Exception:
        info = {}
    out["currency"] = info.get("financialCurrency")
    out["name"] = info.get("shortName") or info.get("longName")
    out["market_cap"] = info.get("marketCap")
    out["sector"] = info.get("sector")

    for attr, key in [("quarterly_income_stmt", "income_q"),
                      ("quarterly_balance_sheet", "balance_q"),
                      ("quarterly_cashflow", "cashflow_q"),
                      ("income_stmt", "income_a")]:
        try:
            out[key] = _df_to_records(getattr(t, attr))
        except Exception:
            out[key] = {}

    for attr, key in [("revenue_estimate", "revenue_estimate"),
                      ("earnings_estimate", "earnings_estimate")]:
        try:
            out[key] = _est_to_records(getattr(t, attr))
        except Exception:
            out[key] = {}

    cache.write_text(json.dumps(out), encoding="utf-8")
    if sleep:
        time.sleep(sleep)
    return out


def extract_financials(sym: str, blob: dict) -> list[dict]:
    cur = blob.get("currency") or "USD"
    rows: list[dict] = []

    def emit(records: dict, mapping: dict, frame: str):
        for period_end, items in (records or {}).items():
            for label, val in items.items():
                metric = mapping.get(label)
                if not metric or val is None:
                    continue
                rows.append({
                    "ticker": sym, "cik": None, "metric": metric,
                    "period_end": period_end, "fy": None, "fp": None,
                    "frame": frame,
                    "value": abs(val) if metric == "capex" else val,
                    "unit": cur, "form": None, "filed": None, "source": "yahoo",
                })

    emit(blob.get("income_q"), INCOME_MAP, "quarterly")
    emit(blob.get("balance_q"), BALANCE_MAP, "instant")
    emit(blob.get("cashflow_q"), CASHFLOW_MAP, "quarterly")
    return rows


def extract_estimates(sym: str, blob: dict) -> list[dict]:
    cur = blob.get("currency") or "USD"
    rows: list[dict] = []
    for metric, key in [("revenue", "revenue_estimate"), ("earnings", "earnings_estimate")]:
        for period, vals in (blob.get(key) or {}).items():
            rows.append({
                "ticker": sym, "metric": metric, "period": period,
                "avg": vals.get("avg"), "low": vals.get("low"), "high": vals.get("high"),
                "num_analysts": vals.get("numberOfAnalysts"),
                "year_ago": vals.get("yearAgoRevenue") or vals.get("yearAgoEps"),
                "growth": vals.get("growth"),
                "currency": cur, "source": "yahoo",
            })
    return rows
