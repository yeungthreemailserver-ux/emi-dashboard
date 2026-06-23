# Deploying EMI to Cloudflare Pages (free)

EMI is a **static site** (`web/`) plus a **local daily build** (`scripts/news/run_news.py`).
Plan: Cloudflare Pages serves the static site; your PC's daily 07:00 task rebuilds the news
bundle and `git push`es it — Cloudflare auto-redeploys. No server, no API key, no cost.

Your Claude Code token, the raw fetch, and the rolling store are git-ignored and **never leave
your machine** — only the finished `web/` bundle is published.

---

## One-time setup

### 1. Create a GitHub repo
- Sign in at github.com → **New repository** (e.g. `emi-dashboard`). Private is fine — Cloudflare
  can deploy from a private repo. Don't add a README/.gitignore (the repo already has them).

### 2. Push this project to it
From the project root (`Electronic Market Intelligence/`), in a terminal:

```bash
git remote add origin https://github.com/<your-username>/emi-dashboard.git
git push -u origin main
```

The first push will prompt you to log in (browser or token). Windows then **stores the
credential**, so the daily scheduled task can push silently afterwards.

### 3. Connect Cloudflare Pages
- Sign in at dash.cloudflare.com → **Workers & Pages** → **Create** → **Pages** →
  **Connect to Git** → pick the `emi-dashboard` repo.
- Build settings:
  - **Framework preset:** `None`
  - **Build command:** *(leave empty — it's already static)*
  - **Build output directory:** `web`
- **Save and Deploy.** In ~1 min you get a public URL like `https://emi-dashboard.pages.dev`.
  - Root `/` lands on the EMI hub (via `web/_redirects`); Earnings is at `/index.html`,
    News at `/news.html`, Atlas at `/atlas.html`, Macro at `/macro.html`.

That's it — the site is live.

---

## Daily updates (automatic)
`run_news.py` now ends with a `git push` step (`git_publish`). So each morning:
**fetch → build → cache-stamp → commit → push → Cloudflare redeploys.** The live site updates
itself, as long as your PC is on at 07:00 (same as today's scheduled task).

- If there's no remote yet, the push step just prints a note and the local build still works.
- To verify a run: `data/news_last_run.txt` (status) and `git log` (the daily commits).

## Notes
- **Repo growth:** the bundle changes daily (~1 MB), so the repo grows ~1 MB/day. Fine for a
  year+; later you can squash history if needed.
- **Change the landing page:** edit `web/_redirects` (e.g. point `/` to `index.html`).
- **Custom domain:** Cloudflare Pages → your project → *Custom domains* (optional, free).
- **What's NOT published** (git-ignored): `.venv/`, `data/news_raw.json`, `data/news_store.json`,
  `data/news_last_run.txt`. Your Claude Code login stays local.
