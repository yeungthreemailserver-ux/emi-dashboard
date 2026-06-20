# EMI scripts

Active pipeline scripts live at the root of `scripts/`. One-off diagnostics, probes, and tests
have been moved to [`archive/`](archive/) (they are parked, not part of any build).

> Run scripts from the repo root with the project venv, e.g. `python scripts/build_china_bundle.py`.
> Paths here are stable on purpose — automation and docs reference them.

## Shared libraries (imported by other scripts — do not move)
- `lang.py` · `parse_transcript.py` · `count_topics.py` · `build_topic_counts.py` · `discover_urls.py`

## Ingest — pull raw data in
- Market / macro: `fetch_macro.py`, `fetch_china_macro.py`, `run_wsts.py`, `run_market_seed.py`, `build_market.py`
- Company financials / filings: `run_ingest.py`, `run_ingest_v2.py`, `run_edgar_us.py`
- Guidance: `run_guidance.py`, `run_guidance_llm.py`, `add_manual_guidance.py`
- Transcripts & universe: `load_transcripts.py`, `translate_transcripts.py`, `load_history.py`,
  `load_memory_market.py`, `load_samsung_memory.py`, `load_private.py`,
  `add_company.py`, `add_companies.py`, `discover_urls.py`, `discover_topics.py`, `backfill_mb.py`
- Orchestration: `refresh.py`

## Build / analyze — compute → JSON & web bundles
- Topic/earnings analysis: `build_topic_counts.py`, `build_topic_outlook.py`, `auto_topics.py`,
  `build_taxonomy.py`, `extract_stance_input.py`, `extract_topic_paragraphs.py`,
  `llm_synthesis.py`, `llm_dimension_reads.py`, `audit_lexicon.py`
- Universe / readiness: `build_manifest_universe.py`, `build_readiness.py`, `validate_data.py`
- Web bundles (→ `web/*-bundle.js`): `build_china_bundle.py`, `build_apac_bundles.py`, `bundle.py`

## News module — `news/` (daily, analysis-first)
- `news/fetch_news.py` → `data/news_raw.json` (curated free sources: RSS, GDELT, Google News, Federal Register)
- `news/build_news.py` → `web/news-bundle.js` (tag vs `data/ontology.json` → cluster → momentum →
  Sonnet synthesis into themes + brief; hot-concept treemap + themeriver data)
- `news/run_news.py` — fetch → build orchestrator (run by the "EMI News Daily" Windows task)

## archive/
22 diagnostics / probes / tests / one-off fixes (`probe_*`, `test_*`, `diag*`, `check_*`,
`inspect_*`, `debug_*`, etc.). Kept for reference; safe to delete. They import nothing the
active pipeline depends on.
