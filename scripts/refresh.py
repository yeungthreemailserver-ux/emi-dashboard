r"""EMI incremental refresh orchestrator — one idempotent command to bring the dashboard up to date.

Pipeline (free unless noted):
  detect    poll each company's earnings page for a newer report      (network; via discover_urls)
  counts    re-fetch transcripts (cached by URL-hash) + recount topics (FREE, Python regex)
  outlooks  re-extract topic paragraphs + rebuild outlook JSONs        (FREE merge; LLM only if changed)
  bundle    load_transcripts.py + bundle.py                            (FREE)
  all       counts -> outlooks -> bundle

The LLM "substantive vs tangential" VALIDATION (the strict synthesis that powers each outlook)
runs ONLY for topics whose extracted input changed since the last run (content-hash cache in
topic_outlook/.cache.json), and ONLY if EMI_ANTHROPIC_KEY is set — so a cron uses the cheap Haiku
API and NEVER your interactive Max quota. With no key, existing *.synth.json are kept and only the
free layers refresh. This makes "add a company / new quarter" cost ~one Haiku call per changed topic.

Usage (PowerShell):
  $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\refresh.py all
  $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\refresh.py outlooks --topics auto,hbm
  $env:EMI_ANTHROPIC_KEY="sk-..."; .\.venv\Scripts\python.exe scripts\refresh.py all   # also re-validates changed topics
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

from emi.config import ROOT

MANIFEST = ROOT / "data" / "manifest.json"
STAMP = ROOT / "data" / "last_refresh.json"


def _stamp(step, ok=True):
    """Housekeeping: record when each pipeline step last ran (surfaced in the Data-coverage lens)."""
    s = json.loads(STAMP.read_text(encoding="utf-8")) if STAMP.exists() else {"steps": {}}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    s.setdefault("steps", {})[step] = {"at": now, "ok": ok}
    s["last_run"] = now
    STAMP.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")

PY = sys.executable
PERIOD = "2026Q1"                      # latest 'as of' quarter (detect hook can advance this)
OUT = ROOT / "data" / "topic_outlook"
CACHE = OUT / ".cache.json"

STRICT_PROMPT = """You are a rigorous semiconductor supply-chain analyst. Below is JSON: for the "{topic}" topic, each company's keyword-matched sentences from its latest earnings call (2026Q1), tagged by speaker segment, with a 5-quarter sentiment trajectory ("traj").

CRITICAL: the sentences came from a keyword match and SOME ARE NOT substantive. Judge EACH company:
- SUBSTANTIVE = real commentary on this topic (demand/supply/pricing/strategy/roadmap that genuinely concerns it).
- TANGENTIAL/FALSE = the keyword only appears inside a list of many items, an analyst question the company doesn't substantively answer, or a homonym/unrelated use of the word.
Build the outlook ONLY from substantive companies. A driver's "companies" may ONLY list companies that substantively made that point.

Return ONLY this JSON (no prose):
{{"topic":"{topic}","as_of":"2026Q1","outlook":{{"direction":"improving|stabilizing|deteriorating|mixed","confidence":"high|medium|low","headline":"<=18 words","summary":"2-3 sentences"}},"drivers":[{{"label":"...","polarity":"pos|neg|mixed","detail":"<=18 words","companies":["TICKER"]}}],"risks":["<=15 words"],"companies":{{"TICKER":{{"stance":"positive|neutral|negative","trend":"improving|flat|worsening","point":"<=18 words"}}}},"consensus":"aligned|split|mixed","consensus_note":"<=22 words","excluded":[{{"ticker":"...","reason":"..."}}]}}

DATA:
{data}
"""


def run(*args):
    env = {**os.environ, "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"}
    print(f"  $ {' '.join(args)}")
    subprocess.run([PY, *args], check=True, env=env, cwd=str(ROOT))


def _cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def synth_topics() -> list[str]:
    return sorted(p.name[: -len(".synth.json")] for p in OUT.glob("*.synth.json"))


def llm_validate(topic: str, inp) -> bool:
    """(Re)write {topic}.synth.json via the Anthropic API (Haiku). Returns True if it ran."""
    key = os.environ.get("EMI_ANTHROPIC_KEY")
    if not key:
        return False
    import urllib.request
    prompt = STRICT_PROMPT.format(topic=topic, data=inp.read_text(encoding="utf-8"))
    body = json.dumps({"model": os.environ.get("EMI_LLM_MODEL", "claude-haiku-4-5"),
                       "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    txt = json.loads(urllib.request.urlopen(req, timeout=60).read())["content"][0]["text"]
    txt = txt[txt.find("{"): txt.rfind("}") + 1]
    json.loads(txt)                                            # validate before writing
    (OUT / f"{topic}.synth.json").write_text(txt, encoding="utf-8")
    print(f"    LLM re-validated {topic}")
    return True


def cmd_counts():
    run("scripts/build_topic_counts.py")                       # cache-hit fetch by URL hash; recount is free


def cmd_outlooks(topics: list[str]):
    cache = _cache()
    for t in topics:
        run("scripts/extract_topic_paragraphs.py", t, PERIOD)  # free
        inp = ROOT / "data" / f"_topic_{t}.json"
        h = hashlib.md5(inp.read_bytes()).hexdigest()
        if cache.get(t) != h:                                  # input changed -> re-validate (only if key)
            if llm_validate(t, inp):
                cache[t] = h
            else:
                print(f"    {t}: input changed but no EMI_ANTHROPIC_KEY -> kept existing synth")
        else:
            print(f"    {t}: unchanged -> skip LLM")
        if (OUT / f"{t}.synth.json").exists():
            run("scripts/build_topic_outlook.py", t)           # free merge
    CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")


def cmd_bundle():
    run("scripts/load_transcripts.py")
    run("scripts/bundle.py")


# --- current-gen pipeline steps (gpt-5.4 reads/synth + self-calibrating lexicon + readiness) ---
def cmd_discover():   run("scripts/discover_topics.py")            # LLM: extract+cluster emergent themes
def cmd_promote():    run("scripts/auto_topics.py")                # LLM: promote new hot themes into the tree
def cmd_expand():     run("scripts/build_taxonomy.py", "--expand") # LLM: widen UNDER-matching keywords vs discovery
def cmd_tighten():    run("scripts/build_taxonomy.py", "--tighten")# LLM: kill keyword false positives
def cmd_reads(fresh): run("scripts/llm_dimension_reads.py", *(["--fresh"] if fresh else []))  # LLM: per-company favorability
def cmd_synth():      run("scripts/llm_synthesis.py", "--model", "gpt-5.4-mini")              # LLM: forward outlooks
def cmd_readiness():  run("scripts/build_readiness.py")            # FREE: data-coverage report
def cmd_translate():  run("scripts/translate_transcripts.py")      # LLM: non-English calls -> English (cached)


def _url_date(u):
    m = re.search(r"/reports/(\d{4})-(\d{1,2})-(\d{1,2})", u or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def cmd_detect(bump=None):
    """Poll each MarketBeat company for a newer report than the manifest; --bump <PERIOD> advances
    the quarter (prepends the new url per company, appends the period label, saves manifest)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from discover_urls import discover
    mf = json.loads(MANIFEST.read_text(encoding="utf-8"))
    new = 0
    for c in mf["companies"]:
        if c.get("source") != "marketbeat" or not c.get("mb"):
            print(f"  {c['ticker']:9} {c.get('source','?'):10} — no MarketBeat detect (manual)")
            if bump:
                c["urls"] = [None] + c["urls"]
            continue
        exch, tk = c["mb"].split("/")
        found = discover(tk, exch, n=1)
        curd = _url_date(c["urls"][0] if c["urls"] else None)
        newd = _url_date(found[0]) if found else (0, 0, 0)
        is_new = bool(found) and newd > curd
        new += is_new
        cur_s = "%04d-%02d-%02d" % curd if curd != (0, 0, 0) else "—"
        new_s = "%04d-%02d-%02d" % newd if found else "ERR/none"
        print(f"  {c['ticker']:9} manifest={cur_s}  latest={new_s}  {'NEW ***' if is_new else 'up-to-date'}")
        if bump:
            c["urls"] = [found[0] if is_new else None] + c["urls"]
    if bump:
        mf["periods"] = mf["periods"] + [bump]
        MANIFEST.write_text(json.dumps(mf, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  bumped periods -> {mf['periods']}; fill any manual (ir_pdf) urls, then: refresh.py all")
    print(f"detect: {new} companies have a newer report than the manifest")


# named multi-step plans (current-gen). 'quick' = free rebuild; 'calibrate' = cheap keyword self-tuning;
# 'update' = full quarterly refresh. Legacy 'all'/'outlooks' (the old .synth path) are kept for back-compat.
PLANS = {
    "quick": ["counts", "readiness", "bundle"],
    "calibrate": ["expand", "tighten", "counts", "readiness", "bundle"],
    "update": ["translate", "discover", "promote", "expand", "tighten", "counts", "reads", "synth", "readiness", "bundle"],
}


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "quick"
    fresh = "--fresh" in sys.argv
    topics = synth_topics()
    if "--topics" in sys.argv:
        topics = sys.argv[sys.argv.index("--topics") + 1].split(",")
    STEP = {
        "counts": cmd_counts, "bundle": cmd_bundle, "readiness": cmd_readiness, "translate": cmd_translate,
        "discover": cmd_discover, "promote": cmd_promote, "expand": cmd_expand, "tighten": cmd_tighten,
        "reads": lambda: cmd_reads(fresh), "synth": cmd_synth, "outlooks": lambda: cmd_outlooks(topics),
    }
    if arg == "detect":
        bump = sys.argv[sys.argv.index("--bump") + 1] if "--bump" in sys.argv else None
        cmd_detect(bump); return
    if arg == "all":   # legacy path (old .synth outlooks)
        plan = ["counts", "outlooks", "bundle"]
    elif arg in PLANS:
        plan = PLANS[arg]
    elif arg in STEP:
        plan = [arg]
    else:
        print(f"unknown command '{arg}'. Use one of: {', '.join(list(PLANS) + list(STEP) + ['detect','all'])}"); sys.exit(2)
    print(f"refresh plan: {' -> '.join(plan)}" + (" (--fresh)" if fresh else ""))
    for step in plan:
        try:
            STEP[step]()
            _stamp(step, True)
        except Exception as e:  # noqa: BLE001
            _stamp(step, False)
            print(f"!! step '{step}' FAILED: {type(e).__name__} — stopping"); sys.exit(1)
    print(f"\n✓ refresh '{arg}' done: {', '.join(plan)} · stamped {STAMP.name}")


if __name__ == "__main__":
    main()
