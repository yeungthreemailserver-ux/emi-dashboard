r"""TOKEN-FREE topic-mention counter for earnings-call transcripts.

The expensive way is to have an LLM read every transcript and count. This does it for FREE:
  1. fetch the transcript HTML with urllib (no tokens)
  2. strip boilerplate to the transcript body
  3. count each topic with a tuned keyword/regex lexicon (no tokens)

The LLM is only used ONCE to draft/expand TOPIC_LEXICON below and to spot-audit a few calls.
This scales to hundreds of companies at ~zero marginal token cost.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\count_topics.py --validate
    ...\python.exe scripts\count_topics.py --url <transcript_url> --ticker MU --period 2026Q1
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

from emi.config import ROOT

CACHE = ROOT / "data" / "transcripts"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# Per-topic patterns (case-insensitive). Each topic's count = total regex hits in the transcript body.
# Order/keys MUST match the TOPICS ids in load_transcripts.py.
TOPIC_LEXICON = {
    "ai_demand":     [r"\bA\.?I\b", r"artificial intelligence", r"data ?cent(?:er|re)", r"accelerat", r"\bGPU\b", r"hyperscal"],
    "agentic_ai":    [r"agentic", r"\binference\b", r"reasoning model", r"\btraining\b"],
    "sovereign_ai":  [r"sovereign"],
    "auto":          [r"automotive", r"\bauto\b", r"\bvehicle"],
    "industrial":    [r"industrial", r"broad[- ]based", r"mass[- ]market", r"broad[- ]market"],
    "consumer":      [r"smartphone", r"\bPC\b", r"personal computer", r"handset", r"consumer"],  # dropped client/mobile (ambiguous)
    "hbm":           [r"\bHBM", r"high[- ]bandwidth"],  # \bHBM also matches HBM3/HBM4/HBM3E/HBMs
    "mem_pricing":   [r"\bpricing\b", r"\bprice", r"\bASP\b", r"average selling price", r"blended"],
    "mem_strategic": [r"long[- ]term agreement", r"\bLTA\b", r"\bSCA\b", r"strategic", r"multi[- ]?year", r"long[- ]term supply"],
    "capex":         [r"\bcapex\b", r"capital expenditure", r"capital spending", r"\bWFE\b", r"capital investment"],
    "capacity":      [r"capacity", r"sold[- ]out", r"supply constrain", r"\bconstrain", r"\btight"],
    "leadtimes":     [r"lead[- ]time"],
    "cowos":         [r"CoWoS", r"advanced packaging", r"\bpackaging\b", r"assembly and test"],
    "nodes":         [r"1[- ]?gamma", r"1[- ]?beta", r"1[- ]?alpha", r"\bnode\b", r"\bnanometer", r"\bnm\b"],
    "highna":        [r"high[- ]?NA", r"\bEUV\b", r"lithograph"],
    "hbm4":          [r"\bHBM4\b", r"HBM4E"],
    "nand_qlc":      [r"\bNAND\b", r"\bQLC\b", r"\bTLC\b", r"solid[- ]state drive"],  # dropped bare SSD (noisy)
    "china":         [r"\bChina\b", r"export control", r"geopolit"],
    "tariffs":       [r"\btariff", r"trade policy", r"trade war"],
    "inventory":     [r"inventor", r"channel invent", r"days of supply", r"weeks of supply"],
    # ── expanded topics for the multi-dimension tree (Subject × Dimension) ──
    # Memory · Demand / Supply (proximity co-occurrence within a sentence)
    "mem_demand":    [r"bit demand", r"(?:memory|DRAM|HBM|NAND)[^.]{0,28}demand", r"demand[^.]{0,28}(?:memory|DRAM|HBM|NAND)"],
    "mem_supply":    [r"bit supply", r"undersupply", r"(?:memory|DRAM|HBM|NAND|bit)[^.]{0,28}(?:supply|shortage|constrain|sold[- ]out)"],
    # Memory · Capability (product family beyond HBM/NAND)
    "dram":          [r"\bDRAM\b", r"\bDDR[0-9]", r"LPDDR", r"GDDR", r"LPCAMM", r"\bDIMM\b"],
    # Processor · Capability + Demand
    "gpu":           [r"\bGPU\b", r"\baccelerator", r"Blackwell", r"\bRubin\b", r"Hopper", r"GB200", r"\bH100\b", r"\bH200\b", r"\bMI3\d0"],
    "cpu":           [r"\bCPU\b", r"\bXeon\b", r"\bEPYC\b", r"server processor", r"central processing"],
    "custom_asic":   [r"custom silicon", r"\bASIC\b", r"\bTPU\b", r"custom accelerator", r"custom chip", r"in[- ]house chip"],
    "compute_demand":[r"(?:GPU|accelerator|compute|silicon)[^.]{0,28}demand", r"demand[^.]{0,28}(?:GPU|accelerator|compute)", r"compute demand"],
    # Process Technology · Capability (transistor architecture)
    "gaa":           [r"\bGAA\b", r"gate[- ]all[- ]around", r"nanosheet", r"backside power", r"back[- ]side power", r"super power rail"],
}
_COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in pats] for k, pats in TOPIC_LEXICON.items()}

# end-of-transcript boilerplate markers — cut everything after the first one we find
_END_MARKERS = ["This article is a transcript", "All earnings call transcripts", "Premium Investing Services",
                "More From The Motley Fool", "Motley Fool Transcribing"]


def fetch(url: str, key: str | None = None) -> str:
    """Download transcript HTML, caching to data/transcripts/<key>.html so we never re-fetch."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / (f"{key}.html" if key else re.sub(r"[^a-z0-9]+", "_", url.lower())[-80:] + ".html")
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8", errors="ignore")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    cache_file.write_text(html, encoding="utf-8")
    return html


def to_body(html: str) -> str:
    """Strip scripts/styles/tags and trim trailing site boilerplate -> plain transcript text."""
    html = re.sub(r"(?is)<(script|style|nav|header|footer)\b.*?</\1>", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", " ", html)
    txt = re.sub(r"&[a-z]+;", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    cut = len(txt)
    for m in _END_MARKERS:
        i = txt.find(m)
        if 0 < i < cut:
            cut = i
    return txt[:cut]


_SENT = re.compile(r"(?<=[.!?])\s+")


def count_topics(text: str) -> dict[str, int]:
    """Sentence-level count: how many SENTENCES mention the topic (any keyword) — de-duped per
    sentence, so synonyms in one breath count once and repeated name-drops don't inflate."""
    sents = _SENT.split(text)
    return {k: sum(1 for s in sents if any(rx.search(s) for rx in rxs)) for k, rxs in _COMPILED.items()}


# directional sentiment cues (earnings-call tuned). Used only on the sentences that mention a topic.
POS = [r"strong", r"robust", r"record", r"\bgrow", r"growth", r"improv", r"recover", r"accelerat", r"momentum",
       r"healthy", r"solid", r"tailwind", r"\brais(e|ed|ing)", r"\bbeat\b", r"outperform", r"expand", r"\bramp",
       r"upside", r"optimis", r"confiden", r"bullish", r"resilien", r"stabiliz", r"stabilis", r"exceed", r"better"]
NEG = [r"\bsoft", r"\bweak", r"declin", r"headwind", r"cautio", r"pressure", r"\bslow", r"trough", r"\bbottom",
       r"challeng", r"muted", r"sluggish", r"correction", r"\bdigest", r"oversupply", r"\bglut", r"destock",
       r"deteriorat", r"\bmiss\b", r"\bbelow\b", r"concern", r"uncertain", r"soften", r"\bcut\b", r"push[- ]?out"]
_POS = [re.compile(p, re.I) for p in POS]
_NEG = [re.compile(p, re.I) for p in NEG]


def topic_sentiment(text: str):
    """For each topic, average directional sentiment (-1..+1) over the sentences that mention it.
    None when the topic isn't mentioned. Crude (no negation handling) but directional & free."""
    sents = _SENT.split(text)
    pn = [(sum(len(rx.findall(s)) for rx in _POS), sum(len(rx.findall(s)) for rx in _NEG)) for s in sents]
    out = {}
    for tid, rxs in _COMPILED.items():
        sc = []
        for i, s in enumerate(sents):
            if any(rx.search(s) for rx in rxs):
                p, n = pn[i]
                sc.append((p - n) / (p + n) if (p + n) else 0.0)
        out[tid] = round(sum(sc) / len(sc), 2) if sc else None
    return out


def count_url(url: str, key: str | None = None) -> dict:
    body = to_body(fetch(url, key))
    counts = count_topics(body)
    return {"counts": counts, "total": sum(counts.values()), "words": len(body.split())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--ticker")
    ap.add_argument("--period")
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()

    if a.validate:
        url = "https://www.fool.com/earnings/call-transcripts/2026/03/18/micron-mu-q2-2026-earnings-call-transcript/"
        r = count_url(url, key="MU_2026Q2_validate")
        # LLM pilot (Sonnet) on the SAME call, for comparison:
        llm = {"ai_demand": 47, "hbm": 31, "capacity": 28, "capex": 22, "nodes": 19, "mem_pricing": 18,
               "mem_strategic": 14, "auto": 12, "nand_qlc": 10, "consumer": 9, "agentic_ai": 8, "hbm4": 8,
               "industrial": 5, "inventory": 4, "leadtimes": 3, "cowos": 2, "china": 2, "highna": 1, "tariffs": 1, "sovereign_ai": 0}
        print(f"Micron FQ2'26 — body {r['words']} words, keyword total {r['total']}")
        print(f"{'topic':<14}{'keyword':>9}{'LLM':>6}")
        order = sorted(r["counts"], key=lambda k: -r["counts"][k])
        for k in order:
            print(f"{k:<14}{r['counts'][k]:>9}{llm.get(k, '-'):>6}")
        kw_top3 = order[:3]
        llm_top3 = sorted(llm, key=lambda k: -llm[k])[:3]
        print(f"\nkeyword top-3: {kw_top3}\nLLM     top-3: {llm_top3}")
        return

    if a.url:
        r = count_url(a.url, key=f"{a.ticker}_{a.period}" if a.ticker and a.period else None)
        print(json.dumps({"ticker": a.ticker, "period": a.period, **r}, ensure_ascii=False))


if __name__ == "__main__":
    main()
