r"""Forward-outlook SYNTHESIS per topic (gpt-5.4) from the per-company LLM reads.

Reads data/dimension_reads.json (per company × topic favorability + why) + data/topic_counts.json
(mention trend), and for each family-level topic writes data/topic_outlook/{id}.json with a structured
forward outlook (direction / headline / summary / confidence / drivers / risks) — the same shape the
dashboard inspector already consumes. Topics that already have a hand-built outlook are kept (use
--force to regenerate). Key is read from openai_key.txt (gitignored); never printed.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\llm_synthesis.py            # missing only
    ...\python.exe scripts\llm_synthesis.py --force                                          # regenerate all
    ...\python.exe scripts\llm_synthesis.py --topic capacity
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT

MODEL = "gpt-5.4"
PRICE = {"gpt-5.4": (2.50, 15.0), "gpt-5.5": (5.0, 30.0), "gpt-5.4-mini": (0.75, 4.50)}
KEY = (ROOT / "openai_key.txt").read_text(encoding="utf-8").strip()
TREE = json.loads((ROOT / "data" / "topic_tree.json").read_text(encoding="utf-8"))
LEAVES = {tid: lf["label"] for tid, lf in TREE["leaves"].items() if lf["parent"] in TREE["nodes"]}
KIND = {tid: TREE["leaves"][tid].get("kind", "topic") for tid in LEAVES}
_MF = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
NAMES = {c["ticker"]: c["name"] for c in _MF["companies"]}
READS = json.loads((ROOT / "data" / "dimension_reads.json").read_text(encoding="utf-8"))
PERIOD = READS.get("period", "")
CNT = json.loads((ROOT / "data" / "topic_counts.json").read_text(encoding="utf-8"))
OUTDIR = ROOT / "data" / "topic_outlook"

SYS = (
    "You are a sell-side semiconductor analyst writing a concise FORWARD outlook on ONE topic for the next "
    "1-2 quarters, grounded ONLY in the company-by-company reads provided (each company's favorability + "
    "reasoning this quarter) and the mention trend. Be specific and insight-driven — no generic filler.\n"
    "- direction: the topic's forward trajectory for the sector — improving (tailwinds building / bullish "
    "broadening), deteriorating (headwinds / bearish), stabilizing (steady), or mixed (diverging by company).\n"
    "- headline: <= 14 words, the single most important takeaway.\n"
    "- summary: 2-3 sentences of real insight — what's driving it, who benefits vs suffers, what to watch.\n"
    "- confidence: high / medium / low, from agreement + coverage.\n"
    "- drivers: 2-5 specific factors; polarity 'pos' (tailwind) or 'neg' (headwind); companies = the names citing it.\n"
    "- risks: 1-3 concrete watch-items.\n"
    "Favorability is company-relative (tight supply = bullish for a supplier). Ground every point in the reads."
)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "direction": {"type": "string", "enum": ["improving", "stabilizing", "deteriorating", "mixed"]},
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "drivers": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "properties": {"label": {"type": "string"}, "detail": {"type": "string"},
                           "polarity": {"type": "string", "enum": ["pos", "neg"]},
                           "companies": {"type": "array", "items": {"type": "string"}}},
            "required": ["label", "detail", "polarity", "companies"]}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["direction", "headline", "summary", "confidence", "drivers", "risks"],
}


def topic_reads(tid):
    out = []
    for tk, td in READS.get("companies", {}).items():
        r = td.get(tid)
        if r and r.get("favorable"):
            out.append((NAMES.get(tk, tk), r["favorable"], r.get("demand_state", "na"), r.get("supply_state", "na"), r.get("why", "")))
    return out


def synth(tid, model):
    rows = topic_reads(tid)
    series = (CNT.get("series", {}).get(tid) or [])
    now = series[-1] if series else 0
    mom = 0
    if len(series) >= 2:
        base = sum(series[:-1]) / (len(series) - 1) or 1
        mom = round((series[-1] - base) / (base + 1) * 100)
    reads_txt = "\n".join(f"- {n} [{f}] demand={ds} supply={ss}: {w}" for n, f, ds, ss, w in rows[:28])   # cap fed reads to bound cost
    user = (f"Topic: {LEAVES[tid]} ({KIND.get(tid)}). Period {PERIOD}. Mention trend per company (oldest->newest): "
            f"{series}; latest {now}x, momentum {mom}% vs trailing average.\n\nCompany reads this quarter:\n{reads_txt}")
    payload = {"model": model, "reasoning_effort": "medium",
               "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
               "response_format": {"type": "json_schema", "json_schema": {"name": "outlook", "strict": True, "schema": SCHEMA}}}
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(3):
        try:
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body,
                                         headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=180).read())
            o = json.loads(r["choices"][0]["message"]["content"])
            return o, r.get("usage", {}), len(rows)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic"); ap.add_argument("--force", action="store_true"); ap.add_argument("--model", default=MODEL)
    ap.add_argument("--workers", type=int, default=10, help="concurrent OpenAI calls (OpenAI key only, $0 Max)")
    a = ap.parse_args()
    model = a.model
    OUTDIR.mkdir(parents=True, exist_ok=True)
    tids = [a.topic] if a.topic else list(LEAVES.keys())
    # decide which topics to synthesize: skip existing (unless --force) and topics with < 2 reads
    todo = []
    for tid in tids:
        f = OUTDIR / f"{tid}.json"
        if f.exists() and not a.force and not a.topic:
            continue
        if len(topic_reads(tid)) < 2:
            continue
        todo.append(tid)
    workers = 1 if a.topic else max(1, a.workers)
    print(f"model = {model} · {len(todo)} topics to synthesize · {workers} workers")
    tin = tout = done = 0

    def work(tid):
        try:
            o, usage, n = synth(tid, model)
            return tid, o, usage, n, None
        except Exception as e:  # noqa: BLE001
            msg = e.read().decode("utf-8", "ignore")[:160] if isinstance(e, urllib.error.HTTPError) else str(e)[:160]
            return tid, None, None, 0, f"{type(e).__name__} {msg}"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(work, tid): tid for tid in todo}
        for fut in as_completed(futs):
            tid, o, usage, n, err = fut.result()
            done += 1
            if err or not o:
                print(f"  [{done}/{len(todo)}] {tid}: FAILED ({err})"); continue
            doc = {"topic": tid, "source": f"{model}-synth", "outlook": {"direction": o["direction"], "headline": o["headline"],
                   "summary": o["summary"], "confidence": o["confidence"]}, "drivers": o["drivers"], "risks": o["risks"]}
            (OUTDIR / f"{tid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            pin, pout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0); tin += pin; tout += pout
            print(f"  [{done}/{len(todo)}] {tid}: {o['direction']} · {n} reads — {o['headline']}", flush=True)
    p = PRICE.get(model, (2.5, 15.0))
    print(f"\nTOTAL {tin}+{tout} tok (~${tin/1e6*p[0]+tout/1e6*p[1]:.3f} at {model})")


if __name__ == "__main__":
    main()
