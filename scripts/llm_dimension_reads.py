r"""LLM demand/supply dimension reads (hybrid: keyword retrieves, LLM judges).

For each company's latest earnings call, gather the sentences that mention each PRODUCT topic
(keyword-matched, token-free), then ask one cheap LLM call per company to judge — from the
COMPANY'S perspective — the demand state and supply state (+ favorability) per product.

Key is read from openai_key.txt (gitignored); never printed. Output -> data/dimension_reads.json.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\llm_dimension_reads.py --ticker MU
    ...\python.exe scripts\llm_dimension_reads.py            # all companies
"""
from __future__ import annotations
import argparse, json, re, sys, time, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT
from count_topics import _COMPILED, _SENT
from build_topic_counts import fetch_text, clean_text, MANIFEST, PERIODS

MODEL = "gpt-5.4-mini"
PRICE = {"gpt-5.4-mini": (0.75, 4.50), "gpt-5.4-nano": (0.20, 1.25), "gpt-4.1-mini": (0.40, 1.60)}  # $/1M (in,out)
KEY = (ROOT / "openai_key.txt").read_text(encoding="utf-8").strip()
TREE = json.loads((ROOT / "data" / "topic_tree.json").read_text(encoding="utf-8"))
# judge node-parented topics (generation children like HBM4/DDR5/QLC inherit the family), FURTHER scoped to
# topics with real mention support (raised by >= MIN_COS companies) so we never pay to judge niche single-SKU
# topics nobody discusses. products get demand+supply; every topic gets a company-relative favorability.
MIN_COS = int(__import__("os").environ.get("EMI_MIN_COS", "4"))
try:
    _CNT = json.loads((ROOT / "data" / "topic_counts.json").read_text(encoding="utf-8")).get("breadth", {})
    _SUPPORTED = {tid for tid, b in _CNT.items() if b and max(b) >= MIN_COS}
except Exception:
    _SUPPORTED = None
LEAVES = {tid: lf["label"] for tid, lf in TREE["leaves"].items()
          if lf["parent"] in TREE["nodes"] and (_SUPPORTED is None or tid in _SUPPORTED)}
KIND = {tid: TREE["leaves"][tid].get("kind", "topic") for tid in LEAVES}
LABEL2ID = {label: tid for tid, label in LEAVES.items()}
_LOWER2ID = {l.lower(): i for l, i in LABEL2ID.items()}
_SEP = re.compile(r"\s*(?:[·•|(]|�).*$")   # strip any echoed suffix like " · product" / " (type …)"


def to_id(s):
    """Map an LLM-echoed topic name back to its stable id, tolerating appended type/separators."""
    s = (s or "").strip()
    if s in LABEL2ID:
        return LABEL2ID[s]
    base = _SEP.sub("", s).strip()
    return LABEL2ID.get(base) or _LOWER2ID.get(base.lower()) or base
_MF = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
NAMES = {c["ticker"]: c["name"] for c in _MF["companies"]}
PERIOD = PERIODS[-1]

SYS = (
    "You are a sell-side semiconductor analyst. For each TOPIC a company discusses, read the quoted sentences "
    "and judge — FROM THE COMPANY'S OWN PERSPECTIVE — whether it is favorable (bullish), neutral, or unfavorable "
    "(bearish), with one terse 'why'. Favorability rules by topic type:\n"
    "- demand (end-markets, AI, compute): bullish if demand strong/accelerating, bearish if weak/declining.\n"
    "- supply / capacity / inventory / capex: bullish when tight BECAUSE demand outruns supply (pricing power / "
    "sold out) or lean/healthy; bearish on oversupply/glut/destocking, or being supply-constrained and losing "
    "sales. capex: for equipment vendors, customers raising capex = bullish.\n"
    "- price (memory pricing, long-term agreements): bullish if prices rising / contracts locking in seller "
    "power, bearish if falling.\n"
    "- macro (China, tariffs): bullish if the headwind is easing, bearish if worsening.\n"
    "- product (HBM, GPU, nodes…): ALSO set demand_state and supply_state (bullish supply = tight-by-demand).\n"
    "Decouple tone from meaning: 'constrained / sold out' for a supplier is BULLISH (demand>supply), not bearish. "
    "Set demand_state/supply_state to 'na' on NON-product topics or when not addressed. One read per topic; only the topics provided."
)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"reads": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "topic": {"type": "string"},
            "favorable": {"type": "string", "enum": ["bullish", "neutral", "bearish"]},
            "demand_state": {"type": "string", "enum": ["hot", "solid", "soft", "weak", "na"]},
            "demand_favorable": {"type": "string", "enum": ["bullish", "neutral", "bearish", "na"]},
            "supply_state": {"type": "string", "enum": ["tight", "balanced", "ample", "oversupply", "na"]},
            "supply_favorable": {"type": "string", "enum": ["bullish", "neutral", "bearish", "na"]},
            "why": {"type": "string"},
        },
        "required": ["topic", "favorable", "demand_state", "demand_favorable", "supply_state", "supply_favorable", "why"],
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
    for tid, label in LEAVES.items():
        hits = [s for s in sents if any(rx.search(s) for rx in _COMPILED[tid])]
        if hits:
            out[tid] = sorted(hits, key=len, reverse=True)[:6]
    return out, None


def call_llm(name, tk, topics, model):
    blocks = "\n\n".join(f"[TOPIC: {LEAVES[t]}]  (type: {KIND.get(t, 'topic')})\n" + "\n".join("- " + s[:280] for s in topics[t]) for t in topics)
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
    ap.add_argument("--fresh", action="store_true", help="ignore prior cache (re-judge every company against the current topic set)")
    ap.add_argument("--workers", type=int, default=12, help="concurrent OpenAI calls (uses only the OpenAI key, $0 Max)")
    a = ap.parse_args()
    model = a.model
    tickers = [a.ticker] if a.ticker else list(MANIFEST.keys())
    outpath = ROOT / "data" / "dimension_reads.json"
    out, tot_in, tot_out = {}, 0, 0
    if not a.ticker and not a.fresh and outpath.exists():   # resume: keep already-done companies for this period
        prev = json.loads(outpath.read_text(encoding="utf-8"))
        if prev.get("period") == PERIOD and prev.get("model") == model:
            out = prev.get("companies", {})
    todo = [tk for tk in tickers if a.ticker or tk not in out]
    workers = 1 if a.ticker else max(1, a.workers)
    print(f"model = {model} · judging {len(LEAVES)} topics (>= {MIN_COS} cos) · {len(todo)} companies to do · {workers} workers" + (" · FRESH" if a.fresh else ""))
    lock = threading.Lock()
    save = lambda: outpath.write_text(json.dumps({"model": model, "period": PERIOD, "companies": out}, ensure_ascii=False, indent=1), encoding="utf-8")

    def work(tk):
        topics, err = sentences_for(tk)
        if err:
            return tk, None, None, err
        if not topics:
            return tk, None, None, "no topics raised"
        try:
            reads, usage = call_llm(NAMES.get(tk, tk), tk, topics, model)
        except Exception as e:   # noqa: BLE001 — never let one company abort the batch
            msg = e.read().decode("utf-8", "ignore")[:160] if isinstance(e, urllib.error.HTTPError) else str(e)[:160]
            return tk, None, None, f"{type(e).__name__} {msg}"
        return tk, {to_id(t["topic"]): t for t in reads}, usage, None

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(work, tk): tk for tk in todo}
        for fut in as_completed(futs):
            tk, reads, usage, err = fut.result()
            done += 1
            if err or not reads:
                print(f"  [{done}/{len(todo)}] {tk}: SKIP ({err})"); continue
            with lock:
                out[tk] = reads
                save()   # persist as each finishes — a crash never loses progress
            pin, pout = (usage or {}).get("prompt_tokens", 0), (usage or {}).get("completion_tokens", 0)
            tot_in += pin; tot_out += pout
            print(f"  [{done}/{len(todo)}] {tk}: {len(reads)} reads · {pin}+{pout} tok", flush=True)
    pin, pout = PRICE.get(model, (0.75, 4.50))
    cost = tot_in / 1e6 * pin + tot_out / 1e6 * pout
    print(f"\nTOTAL {tot_in}+{tot_out} tok  (~${cost:.3f} at {model})  · {len(out)} companies · wrote data/dimension_reads.json" if out else "\nno output")


if __name__ == "__main__":
    main()
