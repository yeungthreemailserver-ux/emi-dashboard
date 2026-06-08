r"""Language helpers for ingesting NON-ENGLISH transcripts.

The LLM judging layers read any language, but the retrieval+counting layer (count_topics.py) is English
regex. So we translate non-English call text to English ONCE at ingest and cache it; everything downstream
(counts, keyword sentence-retrieval, favorability, synthesis) then runs unchanged on the English text.

  cached_en(key)         -> English body if we already translated this transcript, else None
  looks_english(text)    -> heuristic; True = leave as-is, False = translate
  translate(text, key)   -> translate to English (chunked, gpt-5.4-mini), cache to data/transcripts_en/{key}.txt
"""
from __future__ import annotations
import json, re, urllib.request, urllib.error, time
from pathlib import Path

from emi.config import ROOT

EN_DIR = ROOT / "data" / "transcripts_en"
_KEYFILE = ROOT / "openai_key.txt"
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯ｦ-ﾟ]")  # hiragana/katakana/CJK/hangul
_EN_STOP = re.compile(r"\b(the|and|of|to|in|that|we|our|for|is|are|on|with|as|will)\b", re.I)


def en_file(key: str) -> Path:
    return EN_DIR / f"{key}.txt"


def cached_en(key: str):
    p = en_file(key)
    return p.read_text(encoding="utf-8") if p.exists() else None


def looks_english(text: str) -> bool:
    """True if the text is already English enough to skip translation."""
    if not text:
        return True
    sample = text[:6000]
    letters = sum(c.isalpha() for c in sample) or 1
    cjk = len(_CJK.findall(sample))
    if cjk / letters > 0.06:          # meaningful CJK presence -> not English
        return False
    words = max(1, len(sample.split()))
    stop = len(_EN_STOP.findall(sample))
    return stop / words > 0.04         # Latin script but almost no English function words -> translate


_SYS = ("Translate the following earnings-call transcript text to natural English. Translate FAITHFULLY and "
        "completely — do not summarize, omit, or add. Preserve any speaker labels (e.g. 'CEO:', 'Analyst:'). "
        "Keep company/product names and figures as-is. Output ONLY the English translation.")


def _chunks(text: str, words_per: int = 2600):
    w = text.split()
    for i in range(0, len(w), words_per):
        yield " ".join(w[i:i + words_per])


def _call(chunk: str, key: str, model: str) -> str:
    payload = {"model": model, "reasoning_effort": "low",
               "messages": [{"role": "system", "content": _SYS}, {"role": "user", "content": chunk}]}
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(3):
        try:
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body,
                                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=180).read())
            return r["choices"][0]["message"]["content"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt < 2:
                time.sleep(4 * (attempt + 1)); continue
            raise


def translate(text: str, key: str, model: str = "gpt-5.4-mini") -> str:
    """Translate to English (chunked) and cache. Returns the English text."""
    okey = _KEYFILE.read_text(encoding="utf-8").strip()
    out = []
    for ch in _chunks(text):
        if ch.strip():
            out.append(_call(ch, okey, model))
    en = "\n".join(out)
    EN_DIR.mkdir(parents=True, exist_ok=True)
    en_file(key).write_text(en, encoding="utf-8")
    return en
