r"""Segment a MarketBeat verbatim earnings-call transcript into clean parts BEFORE analysis.

MarketBeat format = repeating turns of:  <Speaker + affiliation>  /  <HH:MM:SS>  /  <spoken text>
The HH:MM:SS line is a reliable delimiter; the affiliation gives the role (issuer = management,
a bank/other = analyst). We split into:
    prepared remarks  -> CEO / CFO / other management
    Q&A               -> Q (analyst) and A (management)
and DROP the financial-table header, operator boilerplate, IR logistics and safe-harbor — i.e.
exactly the non-management text that was polluting the keyword counts (Fool "Takeaways"/glossary etc.).

`segments(html)` returns {ceo, cfo, prepared, q, a, analysis_text, turns, ok}.
`analysis_text` = what management/analysts actually SAID — feed this to the topic counter.

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\parse_transcript.py   # self-test on Micron
"""
import re

TS = re.compile(r"^\d\d:\d\d:\d\d$")
QA_ANCHOR = re.compile(r"question-and-answer|question and answer|\[?Operator Instructions\]?|first question", re.I)


def to_lines(html: str):
    html = re.sub(r"(?is)<(script|style|nav|header|footer)\b.*?</\1>", " ", html)
    html = re.sub(r"(?i)</(p|div|h[1-6]|li|tr)>", "\n", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    t = re.sub(r"(?s)<[^>]+>", " ", html)
    t = re.sub(r"&[a-z]+;", " ", t)
    return [re.sub(r"[ \t]+", " ", l).strip() for l in t.split("\n") if l.strip()]


def _issuer(labels):
    # the affiliation ("... at X") shared by the exec speakers = the company being reported
    for lab in labels:
        if re.search(r"\bCEO\b|Chief Executive|\bCFO\b|Chief Financial|Investor Relations", lab):
            m = re.search(r"\bat\s+(.+)$", lab)
            if m:
                return m.group(1).strip()
    return None


def _role(label, issuer):
    L = label.strip()
    if L.lower() == "operator":
        return "operator"
    if re.search(r"Investor Relations", L):
        return "ir"
    if re.search(r"\bCEO\b|Chief Executive", L):
        return "CEO"
    if re.search(r"\bCFO\b|Chief Financial", L):
        return "CFO"
    at = re.search(r"\bat\s+(.+)$", L)
    if issuer and at and issuer.lower() in at.group(1).lower():
        return "mgmt"                                  # other management of the issuer
    if re.search(r"Analyst|Managing Director|Research|Equity|\bat\s+", L):
        return "analyst"
    return "mgmt"                                       # safe default for unlabeled exec


def parse(html: str):
    lines = to_lines(html)
    ts = [i for i, l in enumerate(lines) if TS.match(l)]
    if len(ts) < 4:
        return []                                       # not a verbatim MarketBeat transcript
    labels = [lines[i - 1] for i in ts if i > 0]
    issuer = _issuer(labels)
    turns = []
    for k, i in enumerate(ts):
        spk = lines[i - 1] if i > 0 else ""
        end = (ts[k + 1] - 1) if k + 1 < len(ts) else len(lines)
        turns.append({"speaker": spk, "text": " ".join(lines[i + 1:end]).strip(), "role": _role(spk, issuer)})
    # Q&A begins at the first analyst turn (robust; prepared remarks are everything before it)
    first_analyst = next((idx for idx, t in enumerate(turns) if t["role"] == "analyst"), len(turns))
    for idx, t in enumerate(turns):
        t["section"] = "qa" if idx >= first_analyst else "prepared"
        t["qa"] = ("A" if t["role"] in ("CEO", "CFO", "mgmt") else "Q" if t["role"] == "analyst" else None) if t["section"] == "qa" else None
    return turns


def segments(html: str):
    turns = parse(html)
    if not turns:
        return {"ok": False, "analysis_text": "", "turns": []}
    j = lambda pred: " ".join(t["text"] for t in turns if pred(t)).strip()
    ceo = j(lambda t: t["section"] == "prepared" and t["role"] == "CEO")
    cfo = j(lambda t: t["section"] == "prepared" and t["role"] == "CFO")
    prepared = j(lambda t: t["section"] == "prepared" and t["role"] in ("CEO", "CFO", "mgmt"))
    q = j(lambda t: t["qa"] == "Q")
    a = j(lambda t: t["qa"] == "A")
    analysis = " ".join(x for x in [prepared, q, a] if x)   # management + analyst speech only
    return {"ok": True, "ceo": ceo, "cfo": cfo, "prepared": prepared, "q": q, "a": a, "analysis_text": analysis, "turns": turns}


if __name__ == "__main__":
    from emi.config import ROOT
    from count_topics import count_topics, to_body
    raw = (ROOT / "data" / "transcripts" / "MU_2025Q3.html").read_text(encoding="utf-8", errors="ignore")
    seg = segments(raw)
    w = lambda s: len(s.split())
    print("ok:", seg["ok"], "| turns:", len(seg["turns"]))
    print(f"CEO {w(seg['ceo'])}w · CFO {w(seg['cfo'])}w · prepared {w(seg['prepared'])}w · Q {w(seg['q'])}w · A {w(seg['a'])}w · analysis {w(seg['analysis_text'])}w")
    print("\nNAND/QLC count — full to_body vs clean analysis_text:")
    print("  full   :", count_topics(to_body(raw))["nand_qlc"])
    print("  cleaned:", count_topics(seg["analysis_text"])["nand_qlc"])
    roles = {}
    for t in seg["turns"]:
        roles[t["role"]] = roles.get(t["role"], 0) + 1
    print("\nturn roles:", roles)
