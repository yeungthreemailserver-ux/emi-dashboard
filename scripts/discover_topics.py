r"""EMERGENT topic discovery: let the LLM surface themes the companies actually discuss, beyond our
curated keyword lexicon. Two passes via the OpenAI key (gpt-5.4-mini extract -> gpt-5.4 cluster):

  1. per company (latest call): extract 8-12 specific topic phrases.
  2. once: cluster all phrases into canonical topics, flag which are NEW (not in our taxonomy), rank by
     # companies -> data/emergent_topics.json. Extraction is cached in data/emergent_raw.json (resumable).

Key from openai_key.txt (gitignored); never printed.
    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\discover_topics.py
"""
from __future__ import annotations
import json, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from emi.config import ROOT
from build_topic_counts import fetch_text, clean_text, MANIFEST, PERIODS

KEY = (ROOT / "openai_key.txt").read_text(encoding="utf-8").strip()
TREE = json.loads((ROOT / "data" / "topic_tree.json").read_text(encoding="utf-8"))
EXISTING = sorted({lf["label"] for lf in TREE["leaves"].values()})
_MF = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
NAMES = {c["ticker"]: c["name"] for c in _MF["companies"]}
PERIOD = PERIODS[-1]
RAW = ROOT / "data" / "emergent_raw.json"

EXTRACT_SYS = (
    "You are a semiconductor-supply-chain analyst. From this earnings call, list the 8-12 MOST IMPORTANT, "
    "SPECIFIC topics/themes the company discusses that matter to the chip supply chain, as short canonical "
    "noun phrases (e.g. 'HBM pricing', 'CoWoS capacity', 'inventory digestion', 'China export controls', "
    "'AI inference demand', 'silicon photonics', 'glass substrates'). Be specific — avoid bare words like "
    "'growth' or 'demand'. Prefer the company's own framing."
)
EXTRACT_SCHEMA = {"type": "object", "additionalProperties": False,
                  "properties": {"topics": {"type": "array", "items": {"type": "string"}}}, "required": ["topics"]}


def _post(model, sys_p, user, schema, name, effort=None, timeout=120):
    payload = {"model": model, "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": user}],
               "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}}
    if effort:
        payload["reasoning_effort"] = effort
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(3):
        try:
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body,
                                         headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            return json.loads(r["choices"][0]["message"]["content"]), r.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            raise


def extract_all():
    raw = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}
    tin = tout = 0
    for tk in MANIFEST:
        if tk in raw:
            continue
        url = MANIFEST[tk][0] if MANIFEST.get(tk) else None
        doc, kind = fetch_text(url, key=f"{tk}_{PERIOD}") if url else (None, None)
        text = clean_text(doc, kind) if doc else None
        if not text or len(text.split()) < 600:
            print(f"  {tk}: skip (no transcript)"); raw[tk] = []; RAW.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8"); continue
        try:
            o, u = _post("gpt-5.4-mini", EXTRACT_SYS, f"Company: {NAMES.get(tk, tk)}. Earnings call:\n\n{text[:22000]}", EXTRACT_SCHEMA, "topics")
        except Exception as e:  # noqa: BLE001
            print(f"  {tk}: FAILED {type(e).__name__}"); continue
        raw[tk] = o.get("topics", [])
        tin += u.get("prompt_tokens", 0); tout += u.get("completion_tokens", 0)
        RAW.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        print(f"  {tk}: {len(raw[tk])} themes")
    print(f"extract tokens {tin}+{tout}")
    return raw


CLUSTER_SYS = (
    "You are a semiconductor-supply-chain taxonomist. You are given raw topic phrases extracted from many "
    "earnings calls (with the count of companies that raised each), and an EXISTING topic taxonomy. Cluster "
    "the raw phrases into canonical topics. For each cluster return: name (canonical), companies (total # of "
    "companies across member phrases), examples (2-4 raw phrases), and is_new = true ONLY if the cluster is "
    "NOT already represented by the existing taxonomy. Merge synonyms. Return clusters sorted by companies desc."
)
CLUSTER_SCHEMA = {"type": "object", "additionalProperties": False,
    "properties": {"clusters": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "properties": {"name": {"type": "string"}, "companies": {"type": "integer"}, "is_new": {"type": "boolean"},
                       "examples": {"type": "array", "items": {"type": "string"}}},
        "required": ["name", "companies", "is_new", "examples"]}}}, "required": ["clusters"]}


def cluster(raw):
    from collections import Counter
    cnt = Counter()
    for tk, ts in raw.items():
        for t in set(x.strip().lower() for x in ts if x.strip()):
            cnt[t] += 1
    phrases = "\n".join(f"- {p} ({n})" for p, n in cnt.most_common())
    user = (f"EXISTING taxonomy (do NOT mark these as new):\n{', '.join(EXISTING)}\n\n"
            f"RAW phrases (phrase (company_count)):\n{phrases}")
    o, u = _post("gpt-5.4", CLUSTER_SYS, user, CLUSTER_SCHEMA, "clusters", effort="medium", timeout=240)
    (ROOT / "data" / "emergent_topics.json").write_text(json.dumps({"clusters": o["clusters"], "unique_phrases": len(cnt)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cluster tokens {u.get('prompt_tokens',0)}+{u.get('completion_tokens',0)} · {len(o['clusters'])} clusters\n")
    print("=== EMERGENT (NEW, not in taxonomy) — by #companies ===")
    for c in [c for c in o["clusters"] if c["is_new"]][:25]:
        print(f"  {c['companies']:>3}  {c['name']}   e.g. {', '.join(c['examples'][:3])}")


if __name__ == "__main__":
    cluster(extract_all())
