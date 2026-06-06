r"""Bundle the web JSON data into a single web/bundle.js that defines window.EMI, so the
dashboard works by just DOUBLE-CLICKING web/index.html (file://) — no server needed.
(Browsers block fetch() of local files over file://, but allow <script src>.)

Run this AFTER any rebuild (build.py / build_market.py / load_transcripts.py):
    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\bundle.py
"""
import json

from emi.config import ROOT

WEB = ROOT / "web"


def _load(name):
    p = WEB / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main() -> None:
    payload = {"data": _load("data.json"), "market": _load("market.json"), "signals": _load("transcripts.json")}
    js = "window.EMI = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    out = WEB / "bundle.js"
    out.write_text(js, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB) — open web/index.html directly, no server needed")


if __name__ == "__main__":
    main()
