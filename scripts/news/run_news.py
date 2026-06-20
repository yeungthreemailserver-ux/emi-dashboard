#!/usr/bin/env python3
"""EMI News — daily orchestrator: fetch -> build, with a timestamped log line.

This is what the Windows scheduled task runs once a day. Uses the same Python
interpreter that launched it (sys.executable) so the venv is honoured.
"""
import os, re, sys, glob, subprocess, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable


def step(name):
    print(f"\n=== {name} ===")
    r = subprocess.run([PY, os.path.join(HERE, name)])
    return r.returncode


def stamp_cache():
    """The bundle filename is stable but its content changes daily — rewrite the ?v= token on
    every page that loads it to the build date so browsers fetch the fresh bundle, not a stale cache."""
    ver = dt.datetime.now().strftime("%Y%m%d")
    rx = re.compile(r"news-bundle\.js\?v=[0-9a-z]+")
    n = 0
    for f in glob.glob(os.path.join(ROOT, "web", "*.html")):
        txt = open(f, encoding="utf-8").read()
        new = rx.sub("news-bundle.js?v=" + ver, txt)
        if new != txt:
            open(f, "w", encoding="utf-8").write(new); n += 1
    print(f"Cache-stamped news-bundle -> v={ver} on {n} page(s)")


def main():
    start = dt.datetime.now()
    print(f"EMI News daily run @ {start.isoformat(timespec='seconds')}")
    rc = step("fetch_news.py")
    if rc != 0:
        print("fetch failed but continuing to build with whatever is cached")
    rc = step("build_news.py")
    if rc == 0:
        stamp_cache()
    status = "OK" if rc == 0 else f"FAIL(build rc={rc})"
    log = os.path.join(ROOT, "data", "news_last_run.txt")
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{start.isoformat(timespec='seconds')}  {status}  ({(dt.datetime.now()-start).seconds}s)\n")
    print(f"\nDone: {status}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
