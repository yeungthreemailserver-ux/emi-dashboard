r"""Land earnings-call SIGNALS as a TIDY FACT TABLE (the cube in long form) into the DB
(call_signals + transcripts) and emit web/transcripts.json for the dashboard "Signals" tab.

Fact grain: (ticker, period, signal, [segment]) -> value/label/dir/evidence.
  signal = sentiment | demand | supply | pricing | inventory | capex   (cyclical/structural)
  segment-tagged signals use "demand@<end-market>" (e.g. demand@ai_dc, demand@auto)
This long form lets the front-end pivot into any lens: Journey (now), Cycle heatmap (time),
Divergence/Inflection radar (alpha). Values are model-extracted from free transcripts (Sonnet).

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\load_transcripts.py
"""
from __future__ import annotations

import json

from emi import db
from emi.config import ROOT

LVL = {"strong": 2, "moderate": 1, "stable": 1, "tight": -1, "soft": -1, "negative": -2, "na": None}

# Single source of truth: data/manifest.json. COMPANIES = the "core" roster (other Signals lenses,
# which also need QHIST/CARDS below); TOPIC_COMPANIES = everyone (the topic bubble). Add a company
# in manifest.json and it flows into the roster automatically.
_MF = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
PERIODS = _MF["periods"]
_ROW = lambda c: {"ticker": c["ticker"], "name": c["name"], "layer": c["layer"], "sublayer": c["sublayer"]}
COMPANIES = [_ROW(c) for c in _MF["companies"] if c.get("core")]
TOPIC_COMPANIES = [_ROW(c) for c in _MF["companies"]]

# Per-quarter scalar signals: ticker -> { period: [sent, demand, supply, pricing, inventory, capex] }
SIG_ORDER = ["sentiment", "demand", "supply", "pricing", "inventory", "capex"]
QHIST = {
    "2330.TW": {
        "2025Q1": [1, "strong", "tight", "moderate", "moderate", "strong"],
        "2025Q2": [2, "strong", "tight", "moderate", "moderate", "strong"],
        "2025Q3": [2, "strong", "tight", "moderate", "moderate", "strong"],
        "2025Q4": [2, "strong", "tight", "moderate", "moderate", "strong"],
        "2026Q1": [2, "strong", "tight", "moderate", "moderate", "strong"]},
    "MU": {
        "2025Q1": [1, "strong", "moderate", "soft", "soft", "moderate"],
        "2025Q2": [1, "strong", "moderate", "negative", "moderate", "strong"],
        "2025Q3": [1, "strong", "tight", "moderate", "moderate", "strong"],
        "2025Q4": [2, "strong", "tight", "strong", "moderate", "strong"],
        "2026Q1": [2, "strong", "tight", "strong", "strong", "strong"]},
    "ASML.AS": {
        "2025Q3": [1, "moderate", "moderate", "moderate", "na", "strong"],
        "2025Q4": [2, "strong", "strong", "moderate", "na", "strong"],
        "2026Q1": [1, "strong", "strong", "moderate", "na", "strong"]},
    "AMAT": {
        "2025Q2": [1, "strong", "moderate", "strong", "moderate", "strong"],
        "2025Q4": [1, "moderate", "moderate", "strong", "moderate", "strong"],
        "2026Q1": [2, "strong", "strong", "strong", "moderate", "strong"]},
    "LRCX": {
        "2025Q3": [1, "moderate", "moderate", "na", "moderate", "moderate"],
        "2025Q4": [2, "strong", "moderate", "na", "strong", "strong"],
        "2026Q1": [2, "strong", "strong", "na", "strong", "strong"]},
    "6723.T": {
        "2025Q3": [0, "soft", "soft", "na", "negative", "na"],
        "2025Q4": [1, "moderate", "soft", "moderate", "soft", "na"],
        "2026Q1": [2, "strong", "tight", "moderate", "soft", "strong"]},
    "NVDA": {
        "2025Q4": [2, "strong", "tight", "moderate", "moderate", "na"]},
    "AVT": {
        "2025Q1": [-1, "soft", "soft", "soft", "soft", "na"],
        "2025Q2": [0, "moderate", "soft", "negative", "moderate", "na"],
        "2025Q3": [1, "moderate", "moderate", "moderate", "moderate", "na"],
        "2025Q4": [1, "strong", "moderate", "moderate", "moderate", "na"],
        "2026Q1": [2, "strong", "moderate", "moderate", "moderate", "na"]},
    "ARW": {
        "2025Q1": [0, "soft", "soft", "soft", "soft", "na"],
        "2025Q2": [1, "moderate", "soft", "soft", "moderate", "na"],
        "2025Q3": [1, "moderate", "soft", "soft", "moderate", "na"],
        "2025Q4": [1, "moderate", "moderate", "na", "moderate", "na"],
        "2026Q1": [2, "strong", "moderate", "soft", "moderate", "na"]},
}

# Per-quarter management Q&A confidence (0-1) — "reading between the lines" over time.
CONF_HIST = {
    "2330.TW": {"2025Q1": 0.80, "2025Q2": 0.85, "2025Q3": 0.88, "2025Q4": 0.90, "2026Q1": 0.92},
    "MU": {"2025Q1": 0.80, "2025Q2": 0.85, "2025Q3": 0.87, "2025Q4": 0.92, "2026Q1": 0.97},
    "ASML.AS": {"2025Q3": 0.70, "2025Q4": 0.85, "2026Q1": 0.75},
    "AMAT": {"2025Q2": 0.65, "2025Q4": 0.75, "2026Q1": 0.88},
    "LRCX": {"2025Q3": 0.78, "2025Q4": 0.85, "2026Q1": 0.92},
    "6723.T": {"2025Q3": 0.50, "2025Q4": 0.65, "2026Q1": 0.75},
    "NVDA": {"2025Q4": 0.90},
    "AVT": {"2025Q1": 0.80, "2025Q2": 0.74, "2025Q3": 0.75, "2025Q4": 0.72, "2026Q1": 0.78},
    "ARW": {"2025Q1": 0.68, "2025Q2": 0.73, "2025Q3": 0.70, "2025Q4": 0.72, "2026Q1": 0.78},
}
# latest-quarter Review/Outlook per signal for the distributors (richer extraction).
SIGDETAIL = {
    "AVT": {"demand": ["strong", "strong"], "supply": ["moderate", "moderate"], "pricing": ["moderate", "moderate"], "inventory": ["moderate", "strong"], "capex": ["na", "na"]},
    "ARW": {"demand": ["strong", "strong"], "supply": ["moderate", "moderate"], "pricing": ["soft", "soft"], "inventory": ["moderate", "moderate"], "capex": ["na", "na"]},
}

# Latest-quarter DEMAND by end-market (segment dimension). end-market keys are shared across the chain.
SEG_DEMAND = {
    "2330.TW": {"period": "2026Q1", "ai_dc": "strong", "smartphone": "soft", "automotive": "soft", "industrial": "moderate"},
    "MU": {"period": "2026Q1", "ai_dc": "strong", "smartphone": "soft", "pc": "soft", "automotive": "moderate"},
    "NVDA": {"period": "2025Q4", "ai_dc": "strong"},
    "6723.T": {"period": "2026Q1", "ai_dc": "strong", "automotive": "strong", "industrial": "soft"},
    "AVT": {"period": "2026Q1", "ai_dc": "strong", "automotive": "moderate", "industrial": "strong"},
    "ARW": {"period": "2026Q1", "ai_dc": "strong", "automotive": "strong", "industrial": "strong"},
    "AMAT": {"period": "2026Q1", "ai_dc": "strong", "automotive": "soft"},
    "ASML.AS": {"period": "2026Q1", "ai_dc": "strong"},
    "LRCX": {"period": "2026Q1", "ai_dc": "strong"},
}

# Latest-quarter card (Journey view) — verdict-level detail per company
CARDS = {
    "2330.TW": {"period": "2026Q1", "sent": 2, "gtone": "bullish", "conf": 0.92,
        "quote": "Capacity is expected to stay tight into 2027... AI accelerator CAGR raised to mid-to-high 50s%.",
        "themes": [["AI CAGR raised to mid-high 50s%", "up"], ["CoWoS / advanced packaging tight", "up"], ["agentic AI demand step-up", "new"], ["smartphone & auto soft", "down"]],
        "evasion": ["AI-CAGR update deferred to next quarter", "exact CoWoS capacity numbers", "specific wafer ASP increase %"]},
    "ASML.AS": {"period": "2026Q1", "sent": 1, "gtone": "bullish (Q2 margin caution)", "conf": 0.75,
        "quote": "Memory 51% of new tool sales — first time memory exceeded logic; customers sold out beyond 2026.",
        "themes": [["memory > logic in tool sales (first ever)", "new"], ["AI demand outpacing supply", "up"], ["China revenue down to 19%", "down"]],
        "evasion": ["STOPPED disclosing quarterly bookings (first time ever)", "individual customer commitments", "High-NA insertion timing"]},
    "AMAT": {"period": "2026Q1", "sent": 2, "gtone": "bullish", "conf": 0.88,
        "quote": ">20% semi equipment growth this year; record DRAM revenue; leading-edge capacity full, prices up.",
        "themes": [["AI giga-cycle / WFE >20%", "up"], ["record DRAM / HBM WFE intensity", "up"], ["China & ICAPS soft", "down"]],
        "evasion": ["bookings / backlog $ not disclosed", "advanced-packaging revenue size", "no customer-capex cross-check"]},
    "LRCX": {"period": "2026Q1", "sent": 2, "gtone": "bullish", "conf": 0.92,
        "quote": "WFE raised to $140B with a bias to the upside; record DRAM; NAND $40B conversion pulled forward.",
        "themes": [["WFE 2026 raised to $140B+", "up"], ["DRAM all-time high", "up"], ["NAND $40B pulled forward", "up"], ["adv. packaging >50% (HBM4)", "up"]],
        "evasion": ["customer names", "exact lead-time stretch", "down-payment decline framed as strength"]},
    "NVDA": {"period": "2025Q4", "sent": 2, "gtone": "bullish", "conf": 0.9,
        "quote": "Completely sold out... severely capacity constrained; 'Compute equals revenues'.",
        "themes": [["agentic AI inflection", "new"], ["sovereign AI >$30B", "up"], ["Blackwell / Rubin ramp", "up"], ["China assumed $0", "down"]],
        "evasion": ["Rubin ramp specifics ('too early')", "China revenue timing", "standalone CPU traction ('tell you at GTC')"]},
    "MU": {"period": "2026Q1", "sent": 2, "gtone": "extremely bullish", "conf": 0.97,
        "quote": "We fulfill only 50% to two-thirds of key-customer demand; DRAM pricing +65-67% QoQ, NAND +75-79%.",
        "themes": [["memory recast as strategic AI asset", "up"], ["HBM4 for NVIDIA Vera Rubin", "up"], ["supply tight beyond 2026", "up"], ["5-yr supply agreements (SCA)", "new"]],
        "evasion": ["specific 5-yr SCA customer name", "exact HBM ASP", "per-customer allocations"]},
    "6723.T": {"period": "2026Q1", "sent": 2, "gtone": "cautiously optimistic", "conf": 0.75,
        "quote": "Automotive much stronger than expected... but tester capacity is the bottleneck. Auto +10.6% YoY off a deep trough.",
        "themes": [["automotive recovery off trough", "up"], ["AI / data-center digital power", "up"], ["tester-capacity bottleneck", "new"], ["traditional industrial soft", "down"]],
        "evasion": ["book-to-bill not disclosed", "exact ASP change %", "China client slowdown not quantified"]},
    "AVT": {"period": "2026Q1", "sent": 2, "gtone": "bullish (up-cycle beginning)", "conf": 0.78,
        "quote": "This quarter's results and our June-quarter guidance demonstrate we're positioned well coming into the beginning of the up cycle.",
        "themes": [["up-cycle confirmed — EC +34% YoY", "up"], ["lead times extending >50% of categories", "up"], ["memory/storage pricing inflation", "up"], ["data-center/AI exposure rising", "up"], ["Asia mix diluting gross margin", "down"]],
        "evasion": ["no numeric book-to-bill ('above parity')", "double-ordering risk not quantified", "Asia margin drivers deflected as 'mix'"]},
    "ARW": {"period": "2026Q1", "sent": 2, "gtone": "bullish", "conf": 0.78,
        "quote": "The growth we experienced was driven by unit-volume growth — not pricing.",
        "themes": [["broad demand recovery (volume-led)", "up"], ["lead times gradually extending", "up"], ["IP&E components >$1B", "new"], ["data-center / AI driving ECS", "up"], ["mass-market backlog normalizing", "up"]],
        "evasion": ["exact book-to-bill withheld", "double-ordering dismissed without data", "tariff pass-through mechanics vague"]},
}

THEMES = [
    {"theme": "Capex super-cycle (WFE ↑)", "dir": "up", "tickers": ["2330.TW", "MU", "ASML.AS", "AMAT", "LRCX"]},
    {"theme": "HBM / memory super-cycle (sold out)", "dir": "up", "tickers": ["MU", "ASML.AS", "LRCX", "2330.TW", "NVDA"]},
    {"theme": "Advanced packaging / CoWoS ↑", "dir": "up", "tickers": ["2330.TW", "AMAT", "LRCX"]},
    {"theme": "Agentic AI (new demand vector)", "dir": "new", "tickers": ["NVDA", "2330.TW"]},
    {"theme": "China headwind (equipment)", "dir": "down", "tickers": ["ASML.AS", "AMAT", "LRCX"]},
    {"theme": "Automotive / industrial weak → bottoming", "dir": "down", "tickers": ["2330.TW", "6723.T"]},
]
# Capability / technology roadmap (structural signal that LEADS capex). Curated from the calls.
# status: hvm (high-volume) · ramp · dev · planned. quarters on a 2024Q1–2028Q4 axis.
CAPABILITY = [
    {"layer": "L1", "name": "N3 (3nm)", "start": "2023Q3", "end": "2028Q4", "status": "hvm", "note": "mature; AI + mobile"},
    {"layer": "L1", "name": "N2 (2nm, GAA)", "start": "2025Q4", "end": "2028Q4", "status": "ramp", "note": "HVM Q4'25; smartphone + HPC"},
    {"layer": "L1", "name": "A16 (1.6nm)", "start": "2026Q3", "end": "2028Q4", "status": "planned", "note": "Super Power Rail; H2'26"},
    {"layer": "L1", "name": "CoWoS capacity 2×", "start": "2024Q1", "end": "2027Q4", "status": "ramp", "note": "sold out into 2027"},
    {"layer": "L2", "name": "High-NA EUV", "start": "2026Q1", "end": "2028Q4", "status": "ramp", "note": "Intel HVM; SK Hynix / Samsung"},
    {"layer": "L2", "name": "GAA / backside-power tools", "start": "2025Q1", "end": "2028Q4", "status": "ramp", "note": "+30% WFE per fab vs FinFET"},
    {"layer": "L3", "name": "HBM3E (12-Hi)", "start": "2024Q1", "end": "2026Q1", "status": "hvm", "note": "Blackwell"},
    {"layer": "L3", "name": "1γ DRAM (first EUV node)", "start": "2025Q2", "end": "2028Q4", "status": "ramp", "note": "majority of bits by mid-2026"},
    {"layer": "L3", "name": "HBM4", "start": "2026Q1", "end": "2028Q4", "status": "ramp", "note": "for NVIDIA Vera Rubin"},
    {"layer": "L3", "name": "HBM4E", "start": "2027Q1", "end": "2028Q4", "status": "dev", "note": "CY2027 ramp"},
    {"layer": "L3", "name": "G9 NAND / QLC", "start": "2025Q1", "end": "2028Q4", "status": "ramp", "note": "data-center SSD"},
    {"layer": "L3", "name": "Blackwell", "start": "2025Q1", "end": "2026Q2", "status": "hvm", "note": "NVIDIA"},
    {"layer": "L3", "name": "Blackwell Ultra (B300)", "start": "2026Q1", "end": "2026Q4", "status": "ramp", "note": "NVIDIA"},
    {"layer": "L3", "name": "Rubin (Vera Rubin)", "start": "2026Q3", "end": "2028Q4", "status": "planned", "note": "10× lower inference cost"},
]
CALLOUTS = [
    "AI super-cycle confirmed across 3 independent layers — NVIDIA (demand 'sold out') ↔ TSMC (CoWoS tight to 2027) ↔ Micron (HBM only 50-67% of demand met). Three layers, one signal = high confidence.",
    "Capex super-cycle confirmed by the equipment layer — ASML Q4'25 bookings €13.2B (2× est., named Micron + SK Hynix) + AMAT record DRAM + Lam WFE $140B → validates TSMC $52-56B and Micron $25B+ capex.",
    "The bottleneck is PACKAGING + MEMORY, not logic — CoWoS (TSMC) and HBM (Micron) are both 'sold out' into 2027.",
    "Automotive is bottoming, not booming — Renesas auto recovering off a -14% trough, but TSMC and Infineon still sequentially soft → real but fragile.",
    "China is the soft spot in equipment — ASML, AMAT and Lam all flag China revenue declining (export controls).",
]

# ── TOPIC TREND CUBE ──────────────────────────────────────────────────────────
# "What is the chain most concerned / excited about, and is that topic heating up?"
# Per topic we hold an EMPHASIS series (0-10) across quarters. On emit we convert it to a
# TOTAL MENTION COUNT = roughly the sum over companies of how many times each says it that quarter
# (count = round(11*e + 0.7*e²) → 0..~180). So X is a real frequency tally, not a company head-count.
# Grounded in the per-company themes above + the well-documented AI/HBM super-cycle narrative arc of
# these names. Indicative — replace with true per-call counts from a Sonnet pass when available.
# The bubble chart reads X = total mentions (how hot) · Y = momentum vs trailing-4Q average.
TOPIC_PERIODS = ["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1"]
TOPIC_PLOT_FROM = 2  # first index plotted as bubbles (earlier quarters are baseline-only for the 4Q trail)
TOPIC_CATS = [  # Tableau 10 — the dataviz-standard professional palette (muted, harmonious, reads on white)
    {"id": "ai", "label": "AI & data-center demand", "color": "#4e79a7"},      # blue (the hero)
    {"id": "endmkt", "label": "End-markets (auto / industrial / consumer)", "color": "#f28e2b"},  # orange
    {"id": "mem", "label": "Memory · HBM · pricing", "color": "#b07aa1"},      # mauve
    {"id": "cap", "label": "Capacity · capex · lead-times", "color": "#76b7b2"},  # teal
    {"id": "tech", "label": "Technology roadmap", "color": "#59a14f"},         # green
    {"id": "macro", "label": "Macro & geopolitics", "color": "#e15759"},       # red (risk)
]
# series order = TOPIC_PERIODS
TOPICS = [
    {"id": "ai_demand", "label": "AI / data-center demand", "cat": "ai", "stance": "excited",
     "series": [6, 7, 7, 8, 8, 9, 10], "who": "NVDA · TSMC · MU · all equipment", "note": "the through-line of every call"},
    {"id": "agentic_ai", "label": "Agentic & inference AI", "cat": "ai", "stance": "excited",
     "series": [0, 1, 1, 2, 3, 5, 7], "who": "NVDA · TSMC", "note": "new demand vector — inference as the next leg"},
    {"id": "sovereign_ai", "label": "Sovereign AI", "cat": "ai", "stance": "excited",
     "series": [0, 1, 2, 2, 3, 4, 5], "who": "NVDA", "note": "national build-outs >$30B pipeline"},
    {"id": "auto", "label": "Automotive recovery", "cat": "endmkt", "stance": "mixed",
     "series": [3, 3, 2, 2, 3, 5, 7], "who": "Renesas · TSMC · Arrow · Avnet", "note": "bottoming off a deep trough, now recovering"},
    {"id": "industrial", "label": "Industrial / broad-market", "cat": "endmkt", "stance": "mixed",
     "series": [2, 2, 2, 3, 4, 5, 6], "who": "Avnet · Arrow · Renesas", "note": "broad demand turning up off the bottom"},
    {"id": "consumer", "label": "Smartphone / PC softness", "cat": "endmkt", "stance": "concern",
     "series": [4, 4, 5, 5, 4, 4, 3], "who": "TSMC · Micron", "note": "persistent soft spot, slowly fading as a worry"},
    {"id": "hbm", "label": "HBM (high-bandwidth memory)", "cat": "mem", "stance": "excited",
     "series": [4, 5, 6, 6, 7, 9, 10], "who": "Micron · ASML · Lam · TSMC · NVDA", "note": "sold out; the AI memory engine"},
    {"id": "mem_pricing", "label": "Memory pricing inflection", "cat": "mem", "stance": "excited",
     "series": [2, 2, 2, 1, 4, 7, 10], "who": "Micron · Avnet · ASML", "note": "trough in mid-2025 → +65-79% QoQ by 2026Q1"},
    {"id": "mem_strategic", "label": "Memory as strategic asset / LTAs", "cat": "mem", "stance": "excited",
     "series": [0, 0, 0, 1, 2, 4, 7], "who": "Micron", "note": "5-year supply agreements — a structural shift"},
    {"id": "capex", "label": "Capex / WFE super-cycle", "cat": "cap", "stance": "excited",
     "series": [4, 5, 5, 5, 6, 8, 9], "who": "ASML · AMAT · Lam · TSMC · Micron", "note": "WFE raised to $140B+ with upside bias"},
    {"id": "capacity", "label": "Capacity tight / sold out", "cat": "cap", "stance": "excited",
     "series": [3, 4, 4, 5, 6, 8, 9], "who": "TSMC · NVDA · Micron", "note": "tight into 2027 across packaging + memory"},
    {"id": "leadtimes", "label": "Lead times extending", "cat": "cap", "stance": "mixed",
     "series": [1, 1, 1, 1, 2, 4, 7], "who": "Avnet · Arrow", "note": "extending across >50% of categories — up-cycle marker"},
    {"id": "cowos", "label": "CoWoS / advanced packaging", "cat": "cap", "stance": "excited",
     "series": [3, 4, 5, 5, 6, 7, 8], "who": "TSMC · AMAT · Lam", "note": "the real bottleneck; capacity 2×"},
    {"id": "nodes", "label": "Advanced nodes (N2 / A16)", "cat": "tech", "stance": "excited",
     "series": [3, 3, 4, 4, 5, 6, 7], "who": "TSMC", "note": "N2 HVM Q4'25; A16 H2'26"},
    {"id": "highna", "label": "High-NA EUV", "cat": "tech", "stance": "excited",
     "series": [2, 3, 3, 3, 4, 5, 5], "who": "ASML · Lam", "note": "Intel HVM; SK Hynix / Samsung adopting"},
    {"id": "hbm4", "label": "HBM4 / next-gen memory", "cat": "tech", "stance": "excited",
     "series": [0, 0, 1, 1, 2, 4, 6], "who": "Micron · Lam", "note": "for NVIDIA Vera Rubin"},
    {"id": "nand_qlc", "label": "NAND / QLC for AI storage", "cat": "tech", "stance": "excited",
     "series": [1, 1, 1, 2, 2, 4, 6], "who": "Micron · Lam", "note": "$40B NAND conversion pulled forward"},
    {"id": "china", "label": "China / export controls", "cat": "macro", "stance": "concern",
     "series": [5, 6, 6, 6, 5, 5, 4], "who": "ASML · AMAT · Lam · NVDA", "note": "still a drag, but increasingly assumed at zero"},
    {"id": "tariffs", "label": "Tariffs / trade policy", "cat": "macro", "stance": "concern",
     "series": [1, 1, 3, 5, 4, 3, 3], "who": "Avnet · Arrow", "note": "spiked in 2025; pass-through mechanics still vague"},
    {"id": "inventory", "label": "Inventory correction / double-ordering", "cat": "macro", "stance": "concern",
     "series": [6, 6, 5, 4, 4, 3, 3], "who": "Avnet · Arrow · Renesas", "note": "channel normalizing; double-ordering the new watch-item"},
    # ── expanded topics for the multi-dimension tree (real counts from topic_counts.json override series) ──
    {"id": "mem_demand", "label": "Memory demand", "cat": "mem", "stance": "excited",
     "series": [0, 0, 0, 0, 0, 0, 0], "who": "Micron", "note": "AI-driven bit demand"},
    {"id": "mem_supply", "label": "Memory supply", "cat": "mem", "stance": "excited",
     "series": [0, 0, 0, 0, 0, 0, 0], "who": "Micron", "note": "bit supply constrained vs demand"},
    {"id": "dram", "label": "DRAM / DDR", "cat": "mem", "stance": "excited",
     "series": [0, 0, 0, 0, 0, 0, 0], "who": "Micron", "note": "DDR5 / LPDDR / GDDR family"},
    {"id": "compute_demand", "label": "Compute demand", "cat": "ai", "stance": "excited",
     "series": [0, 0, 0, 0, 0, 0, 0], "who": "NVDA · TSMC", "note": "GPU / accelerator compute demand"},
    {"id": "gpu", "label": "GPU / accelerators", "cat": "tech", "stance": "excited",
     "series": [0, 0, 0, 0, 0, 0, 0], "who": "NVDA", "note": "Blackwell / Rubin / accelerators"},
    {"id": "cpu", "label": "CPU", "cat": "tech", "stance": "mixed",
     "series": [0, 0, 0, 0, 0, 0, 0], "who": "NVDA", "note": "server / client CPU"},
    {"id": "custom_asic", "label": "Custom silicon / ASIC", "cat": "tech", "stance": "excited",
     "series": [0, 0, 0, 0, 0, 0, 0], "who": "TSMC · NVDA", "note": "hyperscaler custom accelerators"},
    {"id": "gaa", "label": "GAA / backside power", "cat": "tech", "stance": "excited",
     "series": [0, 0, 0, 0, 0, 0, 0], "who": "TSMC · ASML", "note": "gate-all-around + backside power"},
]


# ── TOPIC TAXONOMY TREE (data/topic_tree.json) ───────────────────────────────
# Variable-depth tree: nodes (internal groupings, parent pointer) + leaves (the 20 topics, with
# kind/reads/favorable). We merge each leaf's path/kind/reads onto its topic item so the front-end
# can roll up (leaf -> ... -> L1) and drill down, and ship nodes+rules in the bundle.
_TREE = json.loads((ROOT / "data" / "topic_tree.json").read_text(encoding="utf-8"))


def _node_path(nid):
    """root -> node chain of ids for an internal node id."""
    chain, nodes = [], _TREE["nodes"]
    while nid:
        chain.append(nid)
        nid = nodes.get(nid, {}).get("parent")
    return list(reversed(chain))


def _leaf_meta(tid):
    """tree metadata for a leaf topic id: parent chain + kind + reads + facet + labels."""
    lf = _TREE["leaves"].get(tid)
    if not lf:
        return {}
    path = _node_path(lf["parent"]) + [tid]
    labels = [_TREE["nodes"][n]["label"] for n in path[:-1]] + [lf["label"]]
    # NEUTRAL topic name: the tree label has no judgement words ("Capacity", not "Capacity tight / sold
    # out"). Override the verbose TOPICS label so every lens shows the neutral subject.
    out = {"label": lf["label"], "parent": lf["parent"], "kind": lf.get("kind"), "reads": lf.get("reads", []),
           "facet": _TREE["nodes"].get(lf["parent"], {}).get("facet"),
           "tlabel": lf["label"], "path": path, "path_labels": labels}
    if lf.get("role_flip"):
        out["role_flip"] = lf["role_flip"]
    return out


def main() -> None:
    db.init_db()
    sig_rows, tr_rows, facts = [], [], []
    cmap = {c["ticker"]: c for c in COMPANIES}

    # per-quarter scalar signals -> facts + call_signals
    for tk, byq in QHIST.items():
        lyr = cmap[tk]["layer"]
        for period, vals in byq.items():
            for sig, lv in zip(SIG_ORDER, vals):
                val = lv if sig == "sentiment" else LVL.get(lv)
                lab = str(lv)
                sig_rows.append({"ticker": tk, "period": period, "signal": sig, "value": val, "label": lab, "evidence": None})
                facts.append({"ticker": tk, "layer": lyr, "period": period, "signal": sig, "segment": "overall", "value": val, "label": lab})

    # segment demand (end-market) for the latest quarter -> facts + call_signals
    for tk, d in SEG_DEMAND.items():
        lyr, period = cmap[tk]["layer"], d["period"]
        for seg, lv in d.items():
            if seg == "period":
                continue
            sig_rows.append({"ticker": tk, "period": period, "signal": f"demand@{seg}", "value": LVL.get(lv), "label": lv, "evidence": None})
            facts.append({"ticker": tk, "layer": lyr, "period": period, "signal": "demand", "segment": seg, "value": LVL.get(lv), "label": lv})

    # per-quarter management confidence -> facts + call_signals
    for tk, byq in CONF_HIST.items():
        lyr = cmap[tk]["layer"]
        for period, cf in byq.items():
            sig_rows.append({"ticker": tk, "period": period, "signal": "confidence", "value": cf, "label": f"{int(cf*100)}%", "evidence": None})
            facts.append({"ticker": tk, "layer": lyr, "period": period, "signal": "confidence", "segment": "overall", "value": cf, "label": f"{int(cf*100)}%"})

    # journey cards -> transcripts
    for tk, card in CARDS.items():
        full = {**cmap[tk], **card}
        tr_rows.append({"ticker": tk, "period": card["period"], "call_date": None, "url": None,
                        "raw_text": json.dumps(full, ensure_ascii=False), "source": "sonnet-extract"})

    db.upsert_call_signals(sig_rows)
    db.upsert_transcripts(tr_rows)

    calls = [{"ticker": tk, "name": cmap[tk]["name"], "layer": cmap[tk]["layer"], "sublayer": cmap[tk]["sublayer"],
              "period": c["period"], "sentiment": c["sent"], "confidence": c["conf"], "gtone": c["gtone"],
              "quote": c["quote"], "themes": c["themes"], "evasion": c.get("evasion", []),
              "signals": dict(zip(SIG_ORDER[1:], QHIST[tk][c["period"]][1:])),
              "trend": [[p, QHIST[tk][p][0]] for p in PERIODS if p in QHIST[tk]],
              "conftrend": [[p, CONF_HIST[tk][p]] for p in PERIODS if tk in CONF_HIST and p in CONF_HIST[tk]]}
             for tk, c in CARDS.items()]

    # sigmatrix: latest-quarter Review/Outlook per signal (distributors from SIGDETAIL; others = level from QHIST)
    SIG5 = SIG_ORDER[1:]
    sigmatrix = {}
    for c in COMPANIES:
        tk = c["ticker"]
        if tk in SIGDETAIL:
            sigmatrix[tk] = {s: {"review": SIGDETAIL[tk][s][0], "outlook": SIGDETAIL[tk][s][1]} for s in SIG5}
            continue
        qs = QHIST.get(tk, {})
        want = CARDS[tk]["period"]
        key = want if want in qs else (sorted(qs)[-1] if qs else None)
        vals = dict(zip(SIG5, qs[key][1:])) if key else {}
        sigmatrix[tk] = {s: {"review": vals.get(s, "na"), "outlook": vals.get(s, "na")} for s in SIG5}

    def _count(e):  # emphasis (0-10) -> total mention-count tally across companies
        return round(11 * e + 0.7 * e * e)
    who_layer = {"TSMC": "L1", "ASML": "L2", "AMAT": "L2", "Applied Materials": "L2", "Lam": "L2", "Lam Research": "L2",
                 "NVDA": "L3", "NVIDIA": "L3", "Micron": "L3", "MU": "L3", "Renesas": "L3", "Avnet": "L0", "Arrow": "L0"}

    def _layers(who):  # which supply-chain layers raise this topic (from the company list)
        out = set()
        for tok in who.split("·"):
            t = tok.strip()
            if t in who_layer:
                out.add(who_layer[t])
            elif "equipment" in t.lower():
                out.add("L2")
            elif "foundry" in t.lower():
                out.add("L1")
            elif "distribut" in t.lower():
                out.add("L0")
        return sorted(out)
    real_path = ROOT / "data" / "topic_counts.json"
    real = json.loads(real_path.read_text(encoding="utf-8")) if real_path.exists() else None
    if real:
        t_periods, t_plotfrom, t_series, t_breadth = real["periods"], 1, real["series"], real.get("breadth")
    else:
        t_periods, t_plotfrom, t_series, t_breadth = TOPIC_PERIODS, TOPIC_PLOT_FROM, None, None

    def _series(it):  # real measured counts when we have them, else the estimate
        if t_series and it["id"] in t_series:
            return t_series[it["id"]]
        return [_count(e) for e in it["series"]]
    topic_items = [{**it, **_leaf_meta(it["id"]), "series": _series(it), "breadth": (t_breadth or {}).get(it["id"]), "emphasis": it["series"], "layers": _layers(it["who"])} for it in TOPICS]
    topics = {"periods": t_periods, "plot_from": t_plotfrom, "categories": TOPIC_CATS, "items": topic_items,
              "source": "real" if real else "estimated", "coverage": (real or {}).get("coverage"),
              "per_company": (real or {}).get("per_company"), "companies": TOPIC_COMPANIES,
              "sentiment": (real or {}).get("sentiment"), "quotes": (real or {}).get("quotes"),
              "segments": (real or {}).get("segments", ["all"]),
              "tree": {"nodes": _TREE["nodes"], "rules": _TREE["rules"]},
              "unit": (real or {}).get("unit", "count"), "mom_smooth": 4 if real else 20}

    # topic OUTLOOK syntheses (Haiku-judged forward call + drivers + per-segment matrix + evidence)
    outdir = ROOT / "data" / "topic_outlook"
    outlook = {}
    if outdir.exists():
        for f in sorted(outdir.glob("*.json")):
            if f.name.endswith(".synth.json") or f.name.startswith("."):   # skip synth inputs + .cache.json
                continue
            try:
                o = json.loads(f.read_text(encoding="utf-8"))
                outlook[o.get("topic", f.stem)] = o
            except Exception:
                pass
    topics["outlook"] = outlook

    # PROPAGATE the LLM's "excluded" verdicts (keyword false-positives / tangential list mentions):
    # drop those (company, topic) cells from counts + sentiment, and recompute the topic's series/breadth,
    # so the bubble size, distribution and layer-groups all match the validated set — not just the headline.
    pc, sent = topics.get("per_company") or {}, topics.get("sentiment") or {}
    by_id = {it["id"]: it for it in topic_items}
    for tid, o in outlook.items():
        ex = [e.get("ticker") for e in (o.get("excluded") or []) if e.get("ticker")]
        if not ex:
            continue
        for tk in ex:
            if tk in pc and tid in pc[tk]:
                del pc[tk][tid]
            if tk in sent and tid in sent[tk]:
                del sent[tk][tid]
        it = by_id.get(tid)
        if it and topics.get("unit") == "percompany":
            n = len(t_periods)
            ser, brd = [], []
            for i in range(n):
                vals = [pc[tk][tid]["all"][i] for tk in pc if tid in pc[tk] and "all" in pc[tk][tid] and pc[tk][tid]["all"][i] is not None]
                ser.append(round(sum(vals) / len(vals), 1) if vals else 0)
                brd.append(sum(1 for v in vals if v >= 1))
            it["series"], it["breadth"] = ser, brd

    out = {"as_of": "2026Q1", "periods": PERIODS,
           "companies": COMPANIES, "calls": calls, "facts": facts, "sigmatrix": sigmatrix,
           "themes": THEMES, "callouts": CALLOUTS, "capability": CAPABILITY, "topics": topics}
    (ROOT / "web" / "transcripts.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"landed {len(sig_rows)} call_signals + {len(tr_rows)} transcripts | facts={len(facts)} | wrote web/transcripts.json")


if __name__ == "__main__":
    main()
