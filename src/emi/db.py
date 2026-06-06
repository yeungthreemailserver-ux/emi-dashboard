"""SQLite schema and write helpers. Data model is tidy/long and source-tagged.

v2 (layered universe + Yahoo Finance): `companies` carries supply-chain layer context;
`estimates` holds forward analyst consensus (0q/+1q/0y/+1y). Financial values store their
reporting currency in `unit` (FX-normalized to USD at analytics time).
"""
from __future__ import annotations

import sqlite3
from typing import Iterable, Mapping

from .config import DATA_DIR, DB_PATH

TABLES = ["companies", "financials", "estimates", "fx_rates", "guidance",
          "market_series", "transcripts", "call_signals", "news", "events"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
  ticker        TEXT PRIMARY KEY,
  name          TEXT,
  layer         TEXT,   -- L0..L5
  layer_name    TEXT,
  sublayer      TEXT,   -- e.g. 3.2
  sublayer_name TEXT,
  region        TEXT,
  end_market    TEXT,   -- L5 only (auto/datacenter/industrial/consumer/comms/drone)
  currency      TEXT,   -- reporting currency (financialCurrency)
  market_cap    REAL,
  cik           TEXT
);

CREATE TABLE IF NOT EXISTS financials (
  ticker     TEXT NOT NULL,
  cik        TEXT,
  metric     TEXT NOT NULL,   -- revenue, gross_profit, operating_income, net_income, cost_of_revenue, rd_expense, inventory, capex, total_assets
  period_end TEXT NOT NULL,   -- YYYY-MM-DD
  fy         INTEGER,
  fp         TEXT,
  frame      TEXT NOT NULL,   -- quarterly | annual | instant
  value      REAL,
  unit       TEXT,            -- reporting currency
  form       TEXT,
  filed      TEXT,
  source     TEXT,            -- yahoo | edgar
  PRIMARY KEY (ticker, metric, period_end, frame, source)
);
CREATE INDEX IF NOT EXISTS idx_fin_lookup ON financials(ticker, metric, period_end);

CREATE TABLE IF NOT EXISTS estimates (
  ticker       TEXT NOT NULL,
  metric       TEXT NOT NULL,   -- revenue | earnings
  period       TEXT NOT NULL,   -- 0q | +1q | 0y | +1y
  avg          REAL,
  low          REAL,
  high         REAL,
  num_analysts INTEGER,
  year_ago     REAL,
  growth       REAL,            -- implied YoY growth from Yahoo
  currency     TEXT,
  source       TEXT,
  PRIMARY KEY (ticker, metric, period)
);

CREATE TABLE IF NOT EXISTS fx_rates (
  currency TEXT PRIMARY KEY,    -- e.g. TWD, KRW, JPY, EUR
  to_usd   REAL,                -- 1 unit of currency = to_usd USD
  asof     TEXT
);

CREATE TABLE IF NOT EXISTS market_series (
  source TEXT NOT NULL, series TEXT NOT NULL, period TEXT NOT NULL,
  value REAL, unit TEXT, PRIMARY KEY (source, series, period)
);
CREATE TABLE IF NOT EXISTS transcripts (
  ticker TEXT NOT NULL, period TEXT NOT NULL, call_date TEXT, url TEXT,
  raw_text TEXT, source TEXT, PRIMARY KEY (ticker, period)
);
CREATE TABLE IF NOT EXISTS call_signals (
  ticker TEXT NOT NULL, period TEXT NOT NULL, signal TEXT NOT NULL,
  value REAL, label TEXT, evidence TEXT, PRIMARY KEY (ticker, period, signal)
);
CREATE TABLE IF NOT EXISTS news (
  id TEXT PRIMARY KEY, published TEXT, source TEXT, title TEXT, url TEXT,
  summary TEXT, entities TEXT, tags TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY, event_date TEXT, type TEXT, ticker TEXT, title TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS guidance (
  ticker      TEXT NOT NULL,
  metric      TEXT NOT NULL,   -- revenue | gross_margin
  period_text TEXT,            -- e.g. "Second quarter FY2027"
  mid         REAL, low REAL, high REAL,
  filed       TEXT, accn TEXT, raw TEXT, source TEXT,
  PRIMARY KEY (ticker, metric)
);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> str:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return str(DB_PATH)


def reset_db() -> str:
    """Drop all tables and recreate (schema migration without file locks on Windows)."""
    conn = connect()
    try:
        for t in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.commit()
    finally:
        conn.close()
    return init_db()


def _executemany(sql: str, rows: Iterable[Mapping]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    conn = connect()
    try:
        conn.executemany(sql, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def upsert_companies(rows: Iterable[Mapping]) -> int:
    return _executemany(
        """INSERT OR REPLACE INTO companies
           (ticker, name, layer, layer_name, sublayer, sublayer_name, region, end_market, currency, market_cap, cik)
           VALUES (:ticker, :name, :layer, :layer_name, :sublayer, :sublayer_name, :region, :end_market, :currency, :market_cap, :cik)""",
        rows,
    )


def upsert_financials(rows: Iterable[Mapping]) -> int:
    return _executemany(
        """INSERT OR REPLACE INTO financials
           (ticker, cik, metric, period_end, fy, fp, frame, value, unit, form, filed, source)
           VALUES (:ticker, :cik, :metric, :period_end, :fy, :fp, :frame, :value, :unit, :form, :filed, :source)""",
        rows,
    )


def upsert_estimates(rows: Iterable[Mapping]) -> int:
    return _executemany(
        """INSERT OR REPLACE INTO estimates
           (ticker, metric, period, avg, low, high, num_analysts, year_ago, growth, currency, source)
           VALUES (:ticker, :metric, :period, :avg, :low, :high, :num_analysts, :year_ago, :growth, :currency, :source)""",
        rows,
    )


def upsert_guidance(rows: Iterable[Mapping]) -> int:
    return _executemany(
        """INSERT OR REPLACE INTO guidance
           (ticker, metric, period_text, mid, low, high, filed, accn, raw, source)
           VALUES (:ticker, :metric, :period_text, :mid, :low, :high, :filed, :accn, :raw, :source)""",
        rows,
    )


def upsert_fx(rows: Iterable[Mapping]) -> int:
    return _executemany(
        "INSERT OR REPLACE INTO fx_rates (currency, to_usd, asof) VALUES (:currency, :to_usd, :asof)",
        rows,
    )


def upsert_market_series(rows: Iterable[Mapping]) -> int:
    return _executemany(
        """INSERT OR REPLACE INTO market_series (source, series, period, value, unit)
           VALUES (:source, :series, :period, :value, :unit)""",
        rows,
    )


def upsert_transcripts(rows: Iterable[Mapping]) -> int:
    return _executemany(
        """INSERT OR REPLACE INTO transcripts (ticker, period, call_date, url, raw_text, source)
           VALUES (:ticker, :period, :call_date, :url, :raw_text, :source)""",
        rows,
    )


def upsert_call_signals(rows: Iterable[Mapping]) -> int:
    return _executemany(
        """INSERT OR REPLACE INTO call_signals (ticker, period, signal, value, label, evidence)
           VALUES (:ticker, :period, :signal, :value, :label, :evidence)""",
        rows,
    )
