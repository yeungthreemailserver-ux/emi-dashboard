r"""DATA-READINESS / COVERAGE report for the whole universe (US + non-US) -> data/readiness.json.

For every company in config/universe/*.yaml it joins:
  - transcript readiness : how many of the last 5 quarters we actually have cached + when last pulled
  - financial readiness  : Yahoo fundamentals present? (market cap, quarterly revenue) + SEC/EDGAR present?
  - size for screening   : latest market cap (USD) and latest-quarter revenue (USD), via a stamped FX table
  - freshness            : newest file mtime per source (so the dashboard can show staleness)
It SCREENS OUT companies below a market-cap floor (default $2B) — too small to track — but still lists them
(included=false) so the screen is auditable. Writes data/readiness.json (generated_at stamped) + a layer summary.

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\build_readiness.py [--min-mcap 2.0]
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import iter_universe, ROOT

YAHOO = ROOT / "data" / "raw" / "yahoo"
EDGAR = ROOT / "data" / "raw" / "edgar"
TRANSCRIPTS = ROOT / "data" / "transcripts"
# tickers never surfaced in the dashboard (project policy)
EXCLUDE = {"AVT"}
MF = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
MF_TK = {c["ticker"] for c in MF["companies"]}
PERIODS = MF.get("periods", [])

# FX -> USD, stamped. Rough mid-rates; only used to bucket size for screening, not for precise valuation.
FX_AS_OF = "2026-06-01"
FX = {"USD": 1.0, "TWD": 0.031, "KRW": 0.00073, "JPY": 0.0064, "EUR": 1.08, "CNY": 0.138, "HKD": 0.128,
      "GBP": 1.27, "GBp": 0.0127, "CHF": 1.12, "ILS": 0.27, "ILA": 0.0027, "CAD": 0.73, "NOK": 0.092,
      "SGD": 0.74, "SEK": 0.095, "DKK": 0.145}


def mtime(p):
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


def yahoo_for(tk):
    p = YAHOO / (tk.replace(".", "_") + ".json")
    return (json.loads(p.read_text(encoding="utf-8")), p) if p.exists() else (None, None)


def latest_rev(iq):
    if not iq:
        return None, None
    q = sorted(iq)[-1]
    row = iq[q] or {}
    rev = row.get("Total Revenue") or row.get("Operating Revenue")
    return (rev, q) if rev else (None, q)


def transcript_quarters(tk):
    files = list(TRANSCRIPTS.glob(f"{tk}_*.html")) + list(TRANSCRIPTS.glob(f"{tk}_*.pdf")) + list(TRANSCRIPTS.glob(f"{tk}_*.txt"))
    # unique by quarter token (e.g. 2025Q3)
    qs = set()
    for f in files:
        for part in f.stem.split("_"):
            if len(part) == 6 and part[:4].isdigit() and part[4] == "Q":
                qs.add(part)
    last = max((mtime(f) for f in files), default=None) if files else None
    return sorted(qs), last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-mcap", type=float, default=2.0, help="market-cap floor in US$ billions (below = screened out)")
    a = ap.parse_args()
    floor = a.min_mcap * 1e9
    rows = []
    for c in iter_universe():
        tk = c["ticker"]
        if tk in EXCLUDE:
            continue
        y, yp = yahoo_for(tk)
        cur = (y or {}).get("currency") or "USD"
        fx = FX.get(cur, FX.get(cur.upper(), None))
        mcap_loc = (y or {}).get("market_cap")
        mcap_usd = round(mcap_loc * fx) if (mcap_loc and fx) else None
        rev_loc, rev_q = latest_rev((y or {}).get("income_q")) if y else (None, None)
        rev_usd = round(rev_loc * fx) if (rev_loc and fx) else None
        tq, tq_last = transcript_quarters(tk)
        region = c.get("region") or "?"
        is_us = region in ("US", "United States", "USA", "U.S.")
        edgar_files = list(EDGAR.glob("*")) if is_us else []
        has_fin = bool(y)
        included = (mcap_usd is None and is_us) or (mcap_usd is not None and mcap_usd >= floor)
        reason = ""
        if mcap_usd is not None and mcap_usd < floor:
            reason = f"below ${a.min_mcap}B"
        elif mcap_usd is None and not is_us:
            included = False; reason = "no market cap"
        rows.append({
            "ticker": tk, "name": c.get("name") or tk, "layer": c.get("layer"), "sublayer": c.get("sublayer"),
            "layer_name": c.get("layer_name"), "region": region, "us": is_us,
            "mcap_usd": mcap_usd, "rev_usd": rev_usd, "rev_q": rev_q, "currency": cur,
            "transcript_q": len(tq), "transcript_latest": (tq[-1] if tq else None), "transcript_pulled": tq_last,
            "in_pipeline": tk in MF_TK, "has_financials": has_fin, "fin_pulled": mtime(yp) if yp else None,
            "included": included, "screen": reason,
        })
    # summary by layer
    bylayer = {}
    for r in rows:
        L = r["layer"] or "?"
        s = bylayer.setdefault(L, {"layer_name": r.get("layer_name"), "companies": 0, "included": 0,
                                   "with_transcripts": 0, "with_financials": 0, "us": 0, "non_us": 0})
        s["companies"] += 1
        s["included"] += 1 if r["included"] else 0
        s["with_transcripts"] += 1 if r["transcript_q"] else 0
        s["with_financials"] += 1 if r["has_financials"] else 0
        s["us"] += 1 if r["us"] else 0
        s["non_us"] += 0 if r["us"] else 1
    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "fx_as_of": FX_AS_OF, "min_mcap_usd_b": a.min_mcap,
        "periods": PERIODS, "n_companies": len(rows),
        "n_included": sum(1 for r in rows if r["included"]),
        "n_with_transcripts": sum(1 for r in rows if r["transcript_q"]),
        "by_layer": bylayer, "companies": rows,
    }
    (ROOT / "data" / "readiness.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"readiness: {len(rows)} companies · {out['n_included']} pass ${a.min_mcap}B screen · {out['n_with_transcripts']} have transcripts · FX {FX_AS_OF}")
    for L in sorted(bylayer):
        s = bylayer[L]
        print(f"  {L:<4} {str(s['layer_name'])[:22]:<22} {s['companies']:>3} cos · {s['included']:>3} incl · {s['with_transcripts']:>3} transcript · {s['with_financials']:>3} fin · US {s['us']}/non-US {s['non_us']}")


if __name__ == "__main__":
    main()
