"""SEC EDGAR XBRL ingestion.

Pulls standardized company financials from data.sec.gov, maps US-GAAP concepts to a
canonical metric set, and returns tidy/long rows ready for the `financials` table.

Notes
-----
* SEC requires a descriptive User-Agent and asks for < 10 requests/second.
* Raw JSON is cached under data/raw/edgar/ so re-runs don't refetch.
* us_domestic filers give full quarterly history; ADRs (20-F) are annual-only.
"""
from __future__ import annotations

import json
import time
from datetime import date

import requests

from ..config import RAW_DIR, SEC_USER_AGENT

EDGAR_RAW = RAW_DIR / "edgar"
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}

# Canonical metric -> ordered list of candidate US-GAAP concepts.
# The first concept present in a filing wins (companies use different tags over time).
METRIC_CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "cost_of_revenue": ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "rd_expense": ["ResearchAndDevelopmentExpense"],
    "sga_expense": ["SellingGeneralAndAdministrativeExpense"],
    "inventory": ["InventoryNet"],
    "accounts_receivable": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "total_assets": ["Assets"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
}

# Flow metrics span a period (start..end); the rest are point-in-time balance-sheet items.
FLOW_METRICS = {
    "revenue", "cost_of_revenue", "gross_profit", "operating_income",
    "net_income", "rd_expense", "sga_expense", "capex",
}


def _classify_duration(start: str, end: str) -> str | None:
    """Quarterly (~90d) or annual (~365d); skip 6-/9-month YTD spans."""
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    if 80 <= days <= 100:
        return "quarterly"
    if 350 <= days <= 380:
        return "annual"
    return None


def load_cik_map(refresh: bool = False) -> dict[str, str]:
    """Return {TICKER: cik} from SEC's master ticker file (cached)."""
    EDGAR_RAW.mkdir(parents=True, exist_ok=True)
    cache = EDGAR_RAW / "company_tickers.json"
    if cache.exists() and not refresh:
        raw = json.loads(cache.read_text(encoding="utf-8"))
    else:
        resp = requests.get(TICKER_MAP_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        cache.write_text(resp.text, encoding="utf-8")
        raw = resp.json()
        time.sleep(0.2)
    return {entry["ticker"].upper(): str(entry["cik_str"]) for entry in raw.values()}


def fetch_company_facts(cik: str, refresh: bool = False) -> dict | None:
    """Return the companyfacts JSON for a CIK (cached). None if SEC has no facts (404)."""
    EDGAR_RAW.mkdir(parents=True, exist_ok=True)
    cache = EDGAR_RAW / f"CIK{int(cik):010d}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    resp = requests.get(FACTS_URL.format(cik=int(cik)), headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    cache.write_text(resp.text, encoding="utf-8")
    time.sleep(0.2)
    return resp.json()


def extract_metrics(ticker: str, cik: str, facts: dict) -> list[dict]:
    """Map US-GAAP facts to canonical tidy rows.

    Candidate concepts are *unioned* (not first-match): companies switch XBRL tags over
    time — e.g. NVIDIA moved from RevenueFromContractWithCustomerExcludingAssessedTax to
    Revenues — so taking only the first present concept would truncate the history. For
    each (metric, period_end, frame) we keep the most recently filed value; concepts
    earlier in the priority list win only on an exact filed-date tie.
    """
    usgaap = facts.get("facts", {}).get("us-gaap", {})
    rows: list[dict] = []

    def row(metric, end, frame, val, b, derived=False):
        return {"ticker": ticker, "cik": str(cik), "metric": metric, "period_end": end,
                "fy": b.get("fy"), "fp": ("Q4" if derived else b.get("fp")), "frame": frame,
                "value": float(val), "unit": "USD",
                "form": ("DERIVED" if derived else b.get("form")), "filed": b.get("filed", ""),
                "source": "edgar"}

    for metric, concepts in METRIC_CONCEPTS.items():
        present = [c for c in concepts if c in usgaap]
        if not present:
            continue
        is_flow = metric in FLOW_METRICS
        best: dict[tuple, dict] = {}  # (end, frame) -> {start, end, val, fy, fp, form, filed}
        for concept in present:  # priority order: earlier concept preferred on a filed tie
            units = usgaap[concept].get("units", {})
            data = units.get("USD") or (next(iter(units.values()), []) if units else [])
            for pt in data:
                end, val = pt.get("end"), pt.get("val")
                if end is None or val is None:
                    continue
                start = pt.get("start")
                if is_flow:
                    if not start:
                        continue
                    frame = _classify_duration(start, end)
                    if frame is None:
                        continue
                else:
                    frame = "instant"
                key = (end, frame)
                filed = pt.get("filed", "")
                ex = best.get(key)
                if ex is None or filed > ex["filed"]:
                    best[key] = {"start": start, "end": end, "val": float(val),
                                 "fy": pt.get("fy"), "fp": pt.get("fp"),
                                 "form": pt.get("form"), "filed": filed}
        for (end, frame), b in best.items():
            rows.append(row(metric, end, frame, b["val"], b))
        if is_flow:  # derive the missing fiscal-Q4 quarter = annual - (Q1 + Q2 + Q3)
            quarters = [b for (e, f), b in best.items() if f == "quarterly"]
            have_q = {e for (e, f) in best if f == "quarterly"}
            for (e, f), a in best.items():
                if f != "annual" or not a["start"] or a["end"] in have_q:
                    continue
                inside = [b for b in quarters if b["start"] and a["start"] <= b["start"] and b["end"] <= a["end"]]
                if len(inside) == 3:
                    q4 = a["val"] - sum(b["val"] for b in inside)
                    rows.append(row(metric, a["end"], "quarterly", q4, a, derived=True))
    return rows


def ingest(companies: list[dict]) -> tuple[list[dict], list[tuple], list[str]]:
    """Resolve CIKs, fetch facts, and return (financial_rows, resolved, missing)."""
    cik_map = load_cik_map()
    fin_rows: list[dict] = []
    resolved: list[tuple] = []
    missing: list[str] = []
    for c in companies:
        ticker = (c.get("ticker") or "").upper()
        cik = c.get("cik") or cik_map.get(ticker)
        if not cik:
            missing.append(ticker or c.get("name", "?"))
            continue
        facts = fetch_company_facts(cik)
        if not facts:
            missing.append(f"{ticker} (no SEC facts)")
            continue
        rows = extract_metrics(ticker, str(cik), facts)
        fin_rows.extend(rows)
        resolved.append((ticker, str(cik), len(rows)))
    return fin_rows, resolved, missing
