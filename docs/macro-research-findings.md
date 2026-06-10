# Macro + Semiconductor Market Dashboard — Research Findings

> Deep-research synthesis (2026-06-09). 23 verified claims, 2 refuted. Goal: a decision-grade
> macro + semiconductor/electronics market-environment dashboard, APAC-first, extensible to
> EMEA/AMER, with an executive-summary tier + a detailed tier. Build target: static HTML/JS +
> ECharts + free/FMP data (same stack as the EMI project).

## 1. Presentation best-practices (named examples to learn from)

| Pattern | Model after | Copy this |
|---|---|---|
| Regional-selector layout | **OECD Short-Term Indicators Dashboard** | Country/region selector + time slider over G20 (China/Japan/Korea/Indonesia) + aggregates → one layout serves APAC→EMEA→AMER by swapping the economy set |
| Exec→detail architecture | **Shneiderman's mantra** ("Overview first, zoom & filter, details-on-demand") | = the two-tier requirement: exec = overview, detail = drill |
| Three design rules | **Schwabish, *Economist's Guide to Visualizing Data* (JEP 2014)** | (1) show the data, (2) reduce clutter, (3) integrate text + graph (annotate turning points) |
| Bars | Schwabish | Zero-baseline ALWAYS for YoY%/contribution bars |
| Many series | Schwabish | Small multiples / sparkline tables, not spaghetti; end-of-line direct labels |

## 2. Indicator shortlist — macro → industry → end-market chain

Read-through: macro demand & trade → semiconductor billings & equipment orders → end-market pull (AI/datacenter dominant).

- **Macro (context):** GDP, CPI, PPI, Industrial Production, Manufacturing PMI (leading), Exports — overall + electronics/ICT-specific (key APAC leading signal), FX/rates.
- **Industry (anchor):** WSTS semiconductor billings by region (incl. Asia Pacific); SEMI equipment billings + book-to-bill (leading capex signal — see caveat); inventory.
- **End-markets:** AI/datacenter = dominant (verified: ~50% of 2026 revenue at <0.2% of units; data-center semis >$250B; accelerators >50% of DC silicon) → hyperscaler capex + accelerator demand; then automotive (production/sales), PC/smartphone shipments.
- **Leading:** PMI, equipment book-to-bill, ICT exports, hyperscaler capex. **Lagging/coincident:** GDP, billings, vehicle production.

## 3. Data sources — free or FMP

| Indicator | Source | Access | Notes |
|---|---|---|---|
| GDP/CPI/PPI/IP/rates/FX (US + intl) | FRED API | free key (32-char), REST JSON | redistribution licensing caveat; **needs a free key (user does not have one yet)** |
| Cross-country macro | World Bank WDI | free SDMX/REST, **no key** | broad APAC/EMEA/AMER; mostly annual |
| Semi billings by region (incl. APAC) | WSTS Historical Billings ("Blue Book") | **free, no login**, XLSX, 4 decades, monthly + 3mo-MA, 4 regions | aggregate regional totals only (per-product gated) |
| Equipment billings / book-to-bill | SEMI | page | ⚠️ free NA book-to-bill press release discontinued (2016/2022) → treat as historical/reconstruct |
| Hyperscaler capex; TSMC/Samsung financials | SEC EDGAR `data.sec.gov` | **free, NO key** (User-Agent header + ~10 req/s), JSON XBRL | foreign filers (TSMC/Samsung) = annual 20-F + 6-K → lower frequency |
| US macro + treasury + commodities + company financials | FMP (user's key) | confirmed working | **US-centric economic data** — not for APAC country macro |
| APAC country ICT-export / IP detail | National stats (Taiwan DGBAS/MOEA, Korea KOSIS, Japan METI/e-Stat, China NBS, SingStat, Malaysia DOSM) | mostly HTML/Excel, some APIs | per-economy sourcing work |

**APAC economies that matter** (CSIS / BCG-SIA): Taiwan (leading-edge foundry), South Korea (memory), Japan (materials/equipment), China (largest market + mature capacity), Singapore/Malaysia (assembly-test, equipment).

## 4. APAC dashboard blueprint

**EXEC tier (overview first):** region selector (APAC▸EMEA▸AMER) + as-of date; KPI strip (semi billings APAC YoY% + sparkline · Mfg PMI · ICT exports TW/KR · GDP · CPI/PPI · hyperscaler capex, each value+▲▼+turning dot); 3-column status board (Macro/Industry/End-market traffic lights); hero chart = WSTS Asia-Pacific billings (3-mo MA + YoY%).

**DETAIL tier (zoom/filter/details-on-demand):** Macro small-multiples (GDP/CPI/PPI/IP/PMI/Exports across CN·TW·KR·JP·SG·MY, zero-baseline YoY + indexed lines); Trade (electronics/ICT exports by economy); Industry (WSTS billings small multiples, equipment billings + book-to-bill with 1.0 ref line, inventory); End-market (AI/datacenter hyperscaler capex from EDGAR, auto production, PC/smartphone); Forecast-comparison panel (Deloitte/PwC/IDC/WSTS/Gartner side-by-side, labeled & dated).

Extends to EMEA/AMER by swapping the economy set behind the same selector.

## 5. Caveats (verified)

- **Do NOT cite (refuted):** WSTS "$700.9B/$760.7B"; hyperscaler "$600B 2026 / $100B Q3'25."
- Industry forecasts (Deloitte ~$975B 2026; PwC 8.6% CAGR to >$1T by 2030; IDC $1.29T 2026) use different bases → show side-by-side, labeled/dated, never one headline number.
- End-market shipment data (IDC/Gartner/Canalys) largely paywalled → need free proxies (press-release cadence, national stats, OICA auto data).
- FMP economic data is US-only in practice → APAC macro from FRED/World Bank/national stats.
- FRED & World Bank Terms constrain redistribution (licensing caveat for a public dashboard).

## Sources (primary)
- OECD Short-Term Indicators Dashboard · Schwabish JEP 2014 (UIC PDF) · Shneiderman 1996
- WSTS Historical Billings Report · SEMI Billings Report · Deloitte / PwC / IDC 2026 outlooks
- FRED API docs · World Bank SDMX API · SEC EDGAR APIs · FMP stable economic-indicators
- CSIS Indo-Pacific supply chain · BCG-SIA value-chain report
