# Electronic Market Intelligence (EMI)

A market-intelligence engine for the **global electronics & semiconductor supply chain**.
It ingests free/public data, builds leading indicators and cycle analytics, and produces
dashboards and briefings to support **corporate-strategy** decisions. The data model is
deliberately source-agnostic and tidy/long so **investment** and **supply-chain/procurement**
lenses can plug in later without re-architecting.

## Status
**v2 research terminal live.** Layered global universe (263 names, L0–L5) → Yahoo Finance ingestion (financials + forward analyst consensus) → SQLite → `web/data.json` → static HTML/ECharts dark "analyst terminal" in `web/`. 258/263 tickers resolved. Next: expand the universe toward 500, clean ticker misses, refine the layer-level consensus aggregate, add company guidance + cycle/news layers.

---

## How the pros do it (and what we replicate)
The engine triangulates the same signals professional electronics analysts use:

| Source / org | What they provide | Role in the cycle | Our analog |
|---|---|---|---|
| **WSTS** | Bottoms-up monthly semiconductor billings by product & region; spring/fall forecast | Ground-truth demand & consensus | `market_series` (wsts) |
| **SIA** | US repackaging of WSTS + policy/CHIPS context | Free monthly headline | `market_series` (sia) |
| **ECIA** | Distributor book-to-bill + ESI sentiment | **Leading** channel indicator | `market_series` (ecia) |
| **DigiTimes / TrendForce / Counterpoint** | Asia supply-chain checks: foundry utilization, memory/panel pricing, builds | Qualitative leading checks | `news`, `events` |
| **IDC / Gartner / Omdia / Yole** | Top-down end-market unit forecasts & capex | Demand sizing | `market_series`, `events` |
| **Company financials + earnings calls** | Revenue, margin, inventory, capex, guidance language | Confirmation + forward read | `financials`, `transcripts`, `call_signals` |

The analytical edge comes from **(a)** leading-indicator construction (book-to-bill, inventory
days, lead times, capex cycles), **(b)** earnings-call NLP (tone / guidance direction), and
**(c)** cycle-phase classification (recovery / expansion / correction / trough).

---

## Architecture
```
Sources (free)        Ingestion          SQLite (tidy/long)      Analytics            Outputs
------------------    --------------     -------------------     ---------------      ----------------------
SEC EDGAR (XBRL)  ->  ingest/edgar.py -> companies          ->   indicators.py   ->  Streamlit dashboard
WSTS/SIA/ECIA     ->  ingest/wsts.py     financials (long)       cycle.py             scheduled briefings
FRED macro        ->  ingest/fred.py     market_series           nlp_calls.py         (md -> docx/pdf/pptx)
transcripts       ->  ingest/...         transcripts             demand_matrix
news RSS          ->  ingest/news.py     call_signals / news
```

## Data model (SQLite — `data/emi.db`)
All metrics are stored **long/tidy and source-tagged** so any new metric or lens is just new rows.

- `companies(ticker, cik, name, tier, region, listing, end_markets)`
- `financials(ticker, cik, metric, period_end, fy, fp, frame, value, unit, form, filed, source)`
- `market_series(source, series, period, value, unit)`
- `transcripts(ticker, period, call_date, url, raw_text, source)`
- `call_signals(ticker, period, signal, value, label, evidence)`
- `news(id, published, source, title, url, summary, entities, tags)`
- `events(id, event_date, type, ticker, title, notes)`

`frame` ∈ {`quarterly`, `annual`, `instant`}. `metric` is a **canonical** name
(`revenue`, `gross_profit`, `operating_income`, `net_income`, `cost_of_revenue`,
`inventory`, `capex`, `rd_expense`, `total_assets`, `accounts_receivable`, `cash`).

## Analytics (planned, building on financials first)
- **Per-company:** revenue YoY/QoQ, gross & operating margin trend, **inventory days**
  (`inventory / cost_of_revenue × days`), DSO, R&D intensity, capex YoY.
- **Tier roll-ups:** equipment capex cycle, foundry/IDM margin pressure, distributor book-to-bill.
- **Cycle-phase classifier:** WSTS YoY growth × book-to-bill × inventory direction → phase label.
- **End-market demand matrix:** map company commentary & revenue to end-markets
  (AI/datacenter, mobile, auto, industrial, consumer, comms, storage).
- **Earnings-call NLP:** guidance direction, demand sentiment by end-market, mentions of
  inventory / lead-times / pricing / AI capex.

## Outputs
- **Streamlit dashboard:** cycle gauge, WSTS billings, book-to-bill, company financial heatmap,
  end-market demand matrix, call-sentiment tracker.
- **Scheduled briefings:** weekly channel-check + quarterly cycle report (Markdown → docx/pdf/pptx).

---

## Roadmap
- **Phase 0 — Foundation** ✅ structure, universe taxonomy, DB schema, config.
- **Phase 1 — Financial spine** ✅ EDGAR ingestion → financial indicators → Streamlit dashboard.
- **Phase 2 — Market series** WSTS/SIA/ECIA/FRED → cycle classifier.
- **Phase 3 — Voice of the market** transcripts + earnings-call NLP + end-market matrix.
- **Phase 4 — Platform** news/events ingestion, report generation, scheduling, refresh jobs.

## Setup (Windows / PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run ingestion
SEC asks for a descriptive User-Agent with contact info. Override the default if you like:
```powershell
$env:EMI_SEC_USER_AGENT = "Your Name your@email.com"
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\run_ingest.py
```

## Run the research terminal (v2)
```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\run_ingest_v2.py    # Yahoo financials + consensus -> SQLite (disk-cached)
.\.venv\Scripts\python.exe -m emi.report.build         # FX -> USD, rollups, QoQ/YoY, consensus -> web/data.json
.\.venv\Scripts\python.exe -m http.server 8765 --directory web
```
Then open **http://localhost:8765** — supply-chain layer navigation (L0→L5), metric switcher
(Revenue / Margin / Inventory / Op income / Capex / Earnings), heat-colored comparison tables,
and company drill-down with forward consensus. ECharts + Fira fonts are vendored under `web/vendor/`
(fully offline). Sanity-check the data with `scripts\check_data.py`. *(The v1 Streamlit `app.py` is superseded.)*

## Known gaps (free-only) & how we patch them
- **Non-US filers** (Samsung, SK Hynix, TSMC detail, Murata, Foxconn, Infineon) don't file
  full XBRL with SEC → captured later via IR-page ingestion / manual CSV drops (Phase 3+).
- **ADRs** (ASML, ARM, TSM, STM, NXP) file 20-F → **annual-only** financials via EDGAR.
- **WSTS detailed dataset** is paid → we use the free monthly headline + 3-month moving avg.
- **Q4 standalone** isn't always filed in XBRL → derive `Q4 = annual − (Q1+Q2+Q3)` (Phase 2).
