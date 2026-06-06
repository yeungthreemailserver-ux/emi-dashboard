"""Provider-agnostic LLM guidance extraction (OpenAI-compatible chat endpoint).

Works with any OpenAI-compatible API — set three env vars:

  Gemini (free):  EMI_LLM_BASE=https://generativelanguage.googleapis.com/v1beta/openai
                  EMI_LLM_MODEL=gemini-2.0-flash      EMI_LLM_KEY=<AI Studio key>
  Groq (free):    EMI_LLM_BASE=https://api.groq.com/openai/v1
                  EMI_LLM_MODEL=llama-3.3-70b-versatile   EMI_LLM_KEY=<groq key>
  Ollama (local): EMI_LLM_BASE=http://localhost:11434/v1
                  EMI_LLM_MODEL=qwen2.5                (no key needed)

Used only on the names the rule-based parser misses, on a short outlook snippet, so it
stays well within free-tier limits.
"""
from __future__ import annotations

import json
import os
import re

import requests

PROMPT = (
    "You extract forward GUIDANCE that the company itself issued in its earnings press release.\n"
    "Return ONLY minified JSON of this exact shape (no prose, no markdown):\n"
    '{"period":"e.g. Q2 FY2027 or null","currency":"USD","revenue":{"mid":<USD number or null>,'
    '"low":<USD or null>,"high":<USD or null>},"gross_margin":{"mid":<fraction 0..1 or null>}}\n'
    "Rules: '$91.0 billion' -> 91000000000. '$X billion, plus or minus N%' -> mid=X*1e9, "
    "low=mid*(1-N/100), high=mid*(1+N/100). 'between $X and $Y billion' -> low=X*1e9, high=Y*1e9, "
    "mid=midpoint. Gross margin '74.9%' -> 0.749. Use null where the company gave no guidance for "
    "that item. Only the company's own guidance — not analyst estimates. Output JSON only.\nTEXT:\n"
)


def _cfg():
    return (os.environ.get("EMI_LLM_BASE", "").rstrip("/"),
            os.environ.get("EMI_LLM_KEY", ""),
            os.environ.get("EMI_LLM_MODEL", ""))


def configured() -> bool:
    base, _, model = _cfg()
    return bool(base and model)


def _parse(content: str) -> dict | None:
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def llm_extract(text: str) -> dict | None:
    base, key, model = _cfg()
    if not (base and model):
        raise RuntimeError("LLM not configured — set EMI_LLM_BASE, EMI_LLM_MODEL (+ EMI_LLM_KEY for cloud).")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "user", "content": PROMPT + text[:6000]}]}
    r = requests.post(f"{base}/chat/completions", headers=headers, json=body, timeout=90)
    r.raise_for_status()
    return _parse(r.json()["choices"][0]["message"]["content"])
