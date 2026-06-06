r"""Topic deep-dive extractor. For ONE topic, sweep every company's latest call and pull the
sentences that mention it, tagged by speaker segment, plus the 5-quarter sentiment trajectory
from topic_counts.json. This compact JSON is the input to the Haiku outlook synthesis.

    $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\extract_topic_paragraphs.py auto 2026Q1
"""
import glob
import json
import sys

sys.path.insert(0, "scripts")
from count_topics import _COMPILED, _SENT
from emi.config import ROOT
from parse_transcript import segments

topic, period = sys.argv[1], sys.argv[2]
rx = _COMPILED[topic]
TR = ROOT / "data" / "transcripts"


def pdf_text(path):
    try:
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
    except Exception:
        return ""


def topic_sents_from(text, seg):
    out = []
    for s in _SENT.split(text or ""):
        s = s.strip()
        if s and any(r.search(s) for r in rx):
            out.append({"seg": seg, "t": s})
    return out


# 5-quarter sentiment trajectory (lexicon) for the matrix
tc = json.loads((ROOT / "data" / "topic_counts.json").read_text(encoding="utf-8"))
periods = tc["periods"]
sent_all = tc.get("sentiment", {})

companies = {}
for f in sorted(glob.glob(str(TR / f"*_{period}_*.html"))) + sorted(glob.glob(str(TR / f"*_{period}_*.pdf"))):
    name = f.replace("\\", "/").split("/")[-1]
    tk = name.split(f"_{period}_")[0]
    sents = []
    if name.endswith(".html"):
        S = segments(open(f, encoding="utf-8", errors="ignore").read())
        if S.get("ok"):
            for seg in ("ceo", "cfo", "q", "a"):
                sents += topic_sents_from(S.get(seg, ""), seg)
        else:
            sents += topic_sents_from(S.get("analysis_text", ""), "all")
    else:
        sents += topic_sents_from(pdf_text(f), "all")
    if not sents:
        continue
    # per-segment lexicon sentiment trajectory (each value is a 5-quarter list)
    st = sent_all.get(tk, {}).get(topic, {}) or {}
    traj = st.get("all") if isinstance(st.get("all"), list) else [None] * len(periods)
    companies[tk] = {"sents": sents[:12], "traj": traj, "sent": st, "n": len(sents)}

out = {"topic": topic, "period": period, "periods": periods, "companies": companies}
(ROOT / "data" / f"_topic_{topic}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote data/_topic_{topic}.json")
for tk, c in companies.items():
    segs = {}
    for s in c["sents"]:
        segs[s["seg"]] = segs.get(s["seg"], 0) + 1
    print(f"  {tk:9} {c['n']:2} sents  {segs}  traj={c['traj']}")
