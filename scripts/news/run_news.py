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


def git_publish():
    """Commit the day's regenerated bundle + cache-stamped pages and push, so the live
    Cloudflare Pages site auto-redeploys. No-ops gracefully if there's no remote / auth /
    git — the local build still succeeds. Local secrets (Claude token, raw fetch, store)
    are git-ignored and never leave the machine."""
    try:
        g = ["git", "-C", ROOT]
        if not subprocess.run(g + ["remote"], capture_output=True, text=True).stdout.strip():
            print("git: no remote — skipping push (configure one to go live; see DEPLOY.md)")
            return
        subprocess.run(g + ["add", "web", "data/news_history.json"], check=False)
        msg = "News: daily auto-build " + dt.datetime.now().strftime("%Y-%m-%d")
        c = subprocess.run(g + ["commit", "-m", msg], capture_output=True, text=True)
        if c.returncode != 0 and "nothing to commit" in (c.stdout + c.stderr):
            print("git: nothing changed today — no push")
            return
        p = subprocess.run(g + ["push"], capture_output=True, text=True)
        print("git push: " + ("ok — Cloudflare will redeploy" if p.returncode == 0 else "FAILED — " + p.stderr.strip()[:160]))
    except Exception as e:
        print(f"git publish skipped ({type(e).__name__}: {str(e)[:120]})")


def cloudflare_deploy():
    """Publish the freshly built site to Cloudflare PAGES via wrangler, so the live
    https://emi-dashboard.pages.dev updates daily. Auth = CLOUDFLARE_API_TOKEN env var
    (set as a Windows user variable; the scheduled task inherits it). No-ops gracefully
    if wrangler/auth is missing — the local build still succeeds."""
    try:
        win = (os.name == "nt")
        cmd = ("npx --yes wrangler@latest pages deploy web --project-name=emi-dashboard "
               "--branch=main --commit-dirty=true")
        if not win:
            cmd = cmd.split()
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600, shell=win)
        ok = r.returncode == 0
        print("cloudflare deploy: " + ("ok — emi-dashboard.pages.dev updated" if ok else "FAILED — " + ((r.stderr or r.stdout).strip()[-200:])))
    except Exception as e:
        print(f"cloudflare deploy skipped ({type(e).__name__}: {str(e)[:120]})")


def main():
    start = dt.datetime.now()
    print(f"EMI News daily run @ {start.isoformat(timespec='seconds')}")
    rc = step("fetch_news.py")
    if rc != 0:
        print("fetch failed but continuing to build with whatever is cached")
    rc = step("build_news.py")
    if rc == 0:
        stamp_cache()
        cloudflare_deploy()   # publish the updated site to Cloudflare
        git_publish()         # also push to GitHub as a version backup
    status = "OK" if rc == 0 else f"FAIL(build rc={rc})"
    log = os.path.join(ROOT, "data", "news_last_run.txt")
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{start.isoformat(timespec='seconds')}  {status}  ({(dt.datetime.now()-start).seconds}s)\n")
    print(f"\nDone: {status}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
