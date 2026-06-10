# Macro Market Intelligence (MMI)

A decision-grade **macro + semiconductor/electronics market-environment** dashboard — APAC-first,
extensible to EMEA / AMER — with an **executive-summary tier** and a **detail tier**. Static
HTML/JS + ECharts + free/FMP data (same build philosophy as the sibling EMI project).

See [`docs/research-findings.md`](docs/research-findings.md) for the researched best-practice
patterns, indicator shortlist, and data-source map.

## Architecture
- `scripts/fetch_macro.py` — pulls free/FMP sources into `web/data.json` (token-free; just HTTP)
- `web/` — static dashboard (`index.html`, `app.js`, `styles.css`, vendored ECharts), reads `data.json`
- Region tiers via an OECD-style selector (APAC ▸ EMEA ▸ AMER) over one layout

## Data sources (all free or via FMP)
| Layer | Source | Key? |
|---|---|---|
| APAC macro (GDP/CPI/exports) — CN/KR/JP/SG/MY | World Bank WDI REST | none |
| US macro + treasury + commodities | FMP `economic-indicators` / `treasury-rates` | `fmp_key.txt` |
| Hyperscaler capex (AI/datacenter) | SEC EDGAR `data.sec.gov` XBRL | none (User-Agent only) |
| Semiconductor billings by region (incl. Asia Pacific) | WSTS Historical Billings "Blue Book" XLSX | none |
| PPI / Industrial Production / Taiwan series (next) | FRED API | free key (TODO) |

**Gaps flagged by research:** Taiwan is absent from World Bank (use FRED/DGBAS); end-market
shipment data (IDC/Gartner/Canalys) is paywalled (use proxies); FMP economic data is US-only.

## Run
```
python scripts/fetch_macro.py     # writes web/data.json
# open web/index.html (static)
```
`fmp_key.txt` (gitignored) holds the FMP key; FMP steps are skipped if absent.
