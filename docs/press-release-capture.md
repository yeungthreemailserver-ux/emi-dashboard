# Press-Release Capture — Manual Indicator Playbook

> Two indicators — Manufacturing PMI and PC/Smartphone Shipments — have no reliable free structured API.
> This document explains why, lists exact sources, and prescribes a lightweight recurring workflow
> for keeping `web/manual-macro.json` current so the dashboard stays accurate.

---

## 1. Why these are manual

| Indicator | API situation |
|---|---|
| **Manufacturing PMI** | S&P Global and ISM release headline numbers as HTML/PDF press releases, not structured endpoints. DBnomics previously mirrored the ISM feed but the series is corrupted post-August 2025 and must not be used. OECD/MEI has a REST API but its PMI data is frozen at 2023 and is no longer updated. No free, reliable machine-readable PMI feed exists as of mid-2026. |
| **PC shipments** | IDC and Gartner publish quarterly vendor tables in press releases. IDC's data.idc.com API is commercial ($$$). Gartner's newsroom is WAF-protected (bot-blocked on automated fetch). Canalys returns 403 to non-browser clients. |
| **Smartphone shipments** | IDC maintains one free HTML hub page (no API). Counterpoint and Omdia are gated beyond headline YoY%. |

**Bottom line:** these indicators require a human to open a URL, read the press release, and paste the headline numbers into `web/manual-macro.json` once per release cycle. The effort is ~5 minutes per release.

---

## 2. Source table

### 2a. Manufacturing PMI

| Source | URL | Cadence | Free fields | Gated fields |
|---|---|---|---|---|
| **S&P Global PMI hub** | `https://www.pmi.spglobal.com/` | ~1st business day of month | Composite/Manufacturing PMI index, new orders, output, employment sub-indices (headline + brief commentary) | Full report PDF with all sub-indices requires registration |
| S&P Global press release (direct) | `https://www.pmi.spglobal.com/Public/Home/PressRelease/{GUID}` — GUID rotates each month; crawl the hub homepage to find the current link | Same | Same headline fields | — |
| **ISM US Manufacturing PMI** | `https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/manufacturing/` (also mirrored on PR Newswire) | 1st business day of month | Headline index, new orders, production, employment, prices | Detailed commodity responses gated |
| **Coverage via S&P Global** | — | — | US, Japan (au Jibun Bank), South Korea, Taiwan, ASEAN, Caixin China, JPMorgan Global composite | — |

**Fields to capture per PMI release:**

```
period        YYYY-MM  (report month, not release date)
value         float    Manufacturing PMI index (50 = neutral)
source        "ISM" | "S&P Global"
asof          YYYY-MM-DD  (date you captured it)
```

---

### 2b. PC Shipments

| Source | URL | Cadence | Free fields | Gated fields |
|---|---|---|---|---|
| **IDC press releases** | `https://www.idc.com/resource-center/press-releases/` — quarterly PC slug e.g. `/1q26-pc-top5/` | ~4–6 weeks after quarter-end | Total market units (millions), top-5 vendor units + YoY%, overall market YoY% | ASP, segment split, regional detail |
| **Gartner newsroom** | `https://www.gartner.com/en/newsroom/archive` — search "PC shipments" | ~4–6 weeks after quarter-end | Top-6 vendor table, total market units + YoY% | Segment breakdown, forecasts |
| **Canalys / Omdia** | `omdia.tech.informa.com/pr/…` | ~3–4 weeks after quarter-end | Headline market YoY% only | All vendor detail |

**Fields to capture per PC release:**

```
period        YYYYQn   e.g. "2026Q1"
total_m       float    total market units (millions)
yoy_pct       float    YoY% change
source        "IDC" | "Gartner"
asof          YYYY-MM-DD
vendors[]     name, units_m (top 5–6 per source)
```

---

### 2c. Smartphone Shipments

| Source | URL | Cadence | Free fields | Gated fields |
|---|---|---|---|---|
| **IDC smartphone hub** | `https://www.idc.com/promo/smartphone-market-share/market-share/` | ~4–6 weeks after quarter-end | Total market units (millions) + YoY%, top-5 vendor units + market share | Regional breakdown, ASP, OS split |
| **Counterpoint** | Counterpoint press releases | Same | Headline market YoY% only | All vendor detail |

**Fields to capture per smartphone release:**

```
period        YYYYQn
total_m       float
yoy_pct       float
source        "IDC"
asof          YYYY-MM-DD
vendors[]     name, units_m
```

---

## 3. Recurring workflow

### When to check

| Indicator | Check date |
|---|---|
| Manufacturing PMI (all geographies) | 1st and 2nd business day of each month |
| PC shipments | 4–6 weeks after each quarter-end (i.e. early May, early August, early November, early February) |
| Smartphone shipments | Same as PC shipments |

### What to do each cycle

1. Open the source URL in a browser (see table above).
2. Locate the latest press release and note the headline numbers.
3. Open `web/manual-macro.json`.
4. Append a new entry to the relevant array (e.g. `pmi.US`, `pc_shipments`, `smartphone_shipments`) following the schema already in the file — one JSON object per period.
5. For PMI, add an entry for **each geography** covered in that release cycle (US, China_Caixin, Japan, SouthKorea, Taiwan, ASEAN, Global).
6. Save the file. The dashboard's macro page will pick up the new values on next load (once `fetch_macro.py` is wired up — see §4 below).

> **Tip for S&P Global PMI:** The press-release GUID changes every month. Go to `https://www.pmi.spglobal.com/` directly; the "Latest Press Releases" section on the homepage links to the current month's reports for each geography.

---

## 4. How it feeds the dashboard

`web/manual-macro.json` is the **staging file** for indicators that cannot be fetched automatically.

The planned `fetch_macro.py` merge step will:

1. Load the auto-fetched `macro-data.json` (FRED, World Bank, WSTS, EDGAR, etc.).
2. Load `web/manual-macro.json`.
3. Merge manual entries under a `"manual"` top-level key in `macro-data.json`, or inject them directly into the relevant indicator arrays depending on the dashboard's data-binding model.
4. Write the merged output back to `macro-data.json` (or a `macro-data-merged.json` staging file).

Until `fetch_macro.py` is built, the dashboard's macro page can read `manual-macro.json` directly via a second `fetch()` call in the JS layer, keyed off the `"manual"` namespace, so manual data is never confused with auto-fetched data.

---

*Last updated: 2026-06-10*
