# EMI deployment (Cloudflare, free)

**Live site:** https://emi-dashboard.yeungthreemailserver.workers.dev
- Root `/` → EMI hub (`home.html`); News `/news`, Atlas `/atlas`, Earnings `/earnings`, Macro `/macro`.
  (Cloudflare auto-normalises `.html` to clean paths; `web/_redirects` sends the root to the hub.)

## How it's hosted
EMI is a **static site** (`web/`) published to **Cloudflare Workers Static Assets** via `wrangler`.
Config is `wrangler.toml` at the project root (`[assets] directory = "./web"`, `name = "emi-dashboard"`).
GitHub (`emi-dashboard` repo) is kept as a version backup; the live site is served by Cloudflare.

## Daily updates (automatic)
The Windows scheduled task **"EMI News Daily"** (07:00) runs `scripts/news/run_news.py`:
**fetch → build → cache-stamp → `wrangler deploy` (live) → `git push` (backup).**
So the live site refreshes every morning as long as the PC is on at 07:00. One-time auth
(`npx wrangler login`) is already done; the task deploys non-interactively from the stored login.

- Verify a run: `data/news_last_run.txt`, and the deploy line in the task output.
- Manual deploy anytime: from the project root, `npx wrangler deploy`.

## Housekeeping
- **Delete the leftover worker:** the first upload created a random `super-king-a2ab` worker —
  Cloudflare → Workers & Pages → `super-king-a2ab` → Settings → Delete (optional cleanup).
- **Custom domain:** Workers & Pages → emi-dashboard → Settings → Domains & Routes (free).
- **Rename:** change `name` in `wrangler.toml`, `wrangler deploy`, delete the old one.

## What is NOT published (git-ignored, stays local)
`.venv/`, `data/news_raw.json`, `data/news_store.json`, `data/news_last_run.txt`,
and your Claude Code / wrangler logins. Only the finished `web/` assets go live.
