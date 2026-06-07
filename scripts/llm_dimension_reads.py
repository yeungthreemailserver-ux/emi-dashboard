r"""LLM demand/supply dimension reads (hybrid: keyword retrieves, LLM judges).

For each company's latest earnings call, gather the sentences that mention each PRODUCT topic
(keyword-matched, token-free), then ask one cheap LLM call per company to judge — from the
COMPANY'S perspective — the demand state and supply state (+ favorability) per product.

Key is read from openai_key.txt (gitignored); never printed. Output -> data/dimension_reads.json.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\llm_dimension_reads.py --ticker MU
    ...\python.exe scripts\llm_dimension_reads.py            # all companies
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT
from count_topics import _COMPILED, _SENT
from build_topic_counts import fetch_text, clean_text, MANIFEST, PERIODS

MODEL = "gpt-5.4-mini"
PRICE = {"gpt-5.4-mini": (0.75, 4.50), "gpt-5.4-nano": (0.20, 1.25), "gpt-4.1-mini": (0.40, 1.60)}  # $/1M (in,out)
KEY = (ROOT / "openai_key.txt").read_text(encoding="utf-8").strip()
TREE = json.loads((ROOT / "data" / "topic_tree.json").read_text(encoding="utf-8"))
# judge demand/supply only at FAMILY level (parent is an internal node, e.g. HBM/DRAM/NAND/GPU) —
# generation children (HBM4, DDR5, QLC …) are Capability detail and inherit the family's market read.
PRODUCT_LEAVES = {tid: lf["label"] for tid, lf in TREE["leaves"].items()
                  if lf.get("kind") == "product" and lf["parent"] in TREE["nodes"]}
LABEL2ID = {label: tid for tid, label in PRODUCT_LEAVES.items()}
_MF = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
NAMES = {c["ticker"]: c["name"] for c in _MF["companies"]}
PERIOD = PERIODS[-1]

SYS = (
    "You are a sell-side semiconductor analyst. For each PRODUCT a company discusses, read the quoted "
    "sentences and judge two dimensions FROM THE COMPANY'S OWN PERSPECTIVE.\n"
    "DEMAND — how strong is end-demand for this product? state: hot/solid/soft/weak/na. "
    "favorable: bullish if strong/accelerating, bearish if weak/declining.\n"
    "SUPPLY — how tight is supply? state: tight/balanced/ample/oversupply/na. "
    "favorable: bullish when tight BECAUSE demand outruns supply (pricing power / sold out for a supplier); "
    "bearish on oversupply/glut, OR when the company itself is the bottleneck and loses sales.\n"
    "Decouple tone from meaning: 'constrained / sold out / can't make enough' for a supplier is BULLISH "
    "(demand > supply), not bearish. Use 'na' for a dimension the sentences do not address. "
    "'why' = one terse sentence citing the evidence. Judge ONLY the topics provided; return one read per topic."
)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"reads": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "topic": {"type": "string"},
            "demand_state": {"type": "string", "enum": ["hot", "solid", "soft", "weak", "na"]},
            "demand_favorable": {"type": "string", "enum": ["bullish", "neutral", "bearish"]},
            "supply_state": {"type": "string", "enum": ["tight", "balanced", "ample", "oversupply", "na"]},
            "supply_favorable": {"type": "string", "enum": ["bullish", "neutral", "bearish"]},
            "why": {"type": "string"},
        },
        "required": ["topic", "demand_state", "demand_favorable", "supply_state", "supply_favorable", "why"],
    }}},
    "required": ["reads"],
}


def sentences_for(tk):
    """Latest-call sentences per product topic the company raises (keyword-matched)."""
    url = MANIFEST.get(tk, [None])[0]
    if not url:
        return None, "no url"
    doc, kind = fetch_text(url, key=f"{tk}_{PERIOD}")
    text = clean_text(doc, kind) if doc else None
    if not text or len(text.split()) < 600:
        return None, "no transcript"
    sents = [s.strip() for s in _SENT.split(text) if len(s.strip()) > 25]
    out = {}
    for tid, label in PRODUCT_LEAVES.items():
        hits = [s for s in sents if any(rx.search(s) for rx in _COMPILED[tid])]
        if hits:
            out[tid] = sorted(hits, key=len, reverse=True)[:6]
    return out, None


def call_llm(name, tk, topics, model):
    blocks = "\n\n".join(f"[TOPIC: {PRODUCT_LEAVES[t]}]\n" + "\n".join("- " + s[:280] for s in topics[t]) for t in topics)
    user = f"Company: {name} ({tk}), {PERIOD} earnings call. Judge demand & supply for each topic.\n\n{blocks}"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "dimension_reads", "strict": True, "schema": SCHEMA}},
    }
    if model.startswith(("gpt-5", "o3", "o4")):
        payload["reasoning_effort"] = "low"   # reasoning models — keep it shallow for cheap extraction
    else:
        payload["temperature"] = 0
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(3):   # retry transient timeouts / rate-limits / 5xx
        try:
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body,
                                         headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=120).read())
            reads = json.loads(r["choices"][0]["message"]["content"])["reads"]
            return reads, r.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(4 * (attempt + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 2:
                time.sleep(4 * (attempt + 1)); continue
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", help="run a single company")
    ap.add_argument("--model", default=MODEL, help="override model id (e.g. gpt-5.4-nano)")
    a = ap.parse_args()
    model = a.model
    tickers = [a.ticker] if a.ticker else list(MANIFEST.keys())
    print(f"model = {model}")
    outpath = ROOT / "data" / "dimension_reads.json"
    out, tot_in, tot_out = {}, 0, 0
    if not a.ticker and outpath.exists():   # resume: keep already-done companies for this period
        prev = json.loads(outpath.read_text(encoding="utf-8"))
        if prev.get("period") == PERIOD and prev.get("model") == model:
            out = prev.get("companies", {})
    save = lambda: outpath.write_text(json.dumps({"model": model, "period": PERIOD, "companies": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    for tk in tickers:
        if tk in out and not a.ticker:
            print(f"  {tk}: cached ({len(out[tk])} reads)"); continue
        topics, err = sentences_for(tk)
        if err:
            print(f"  {tk}: SKIP ({err})"); continue
        if not topics:
            print(f"  {tk}: no product topics raised"); continue
        try:
            reads, usage = call_llm(NAMES.get(tk, tk), tk, topics, model)
        except Exception as e:   # noqa: BLE001 — never let one company abort the batch
            msg = e.read().decode("utf-8", "ignore")[:160] if isinstance(e, urllib.error.HTTPError) else str(e)[:160]
            print(f"  {tk}: FAILED ({type(e).__name__}) {msg}"); continue
        out[tk] = {LABEL2ID.get(t["topic"], t["topic"]): t for t in reads}   # key by stable topic id
        save()   # persist after every company so a crash never loses progress
        pin, pout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        tot_in += pin; tot_out += pout
        print(f"  {tk}: {len(reads)} reads · {pin}+{pout} tok")
        for t in reads:
            print(f"      {t['topic']:<22} D:{t['demand_state']}/{t['demand_favorable']:<7} S:{t['supply_state']}/{t['supply_favorable']:<7} — {t['why'][:90]}")
    pin, pout = PRICE.get(model, (0.75, 4.50))
    cost = tot_in / 1e6 * pin + tot_out / 1e6 * pout
    print(f"\nTOTAL {tot_in}+{tot_out} tok  (~${cost:.3f} at {model})  · wrote data/dimension_reads.json" if out else "\nno output")


if __name__ == "__main__":
    main()
