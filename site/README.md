# RAKSHAK site

3-page site: `/` (overview), `/demo` (real captured run, an interactive scoring sandbox,
and a live "run it yourself" call to the real backend), `/docs` (architecture,
requirements, API). Static HTML/CSS/JS, no build step - the one exception is
`/api/score`, a serverless function that runs actual `backend/engine/insider` code
against whatever batch of events a visitor generates or pastes in. See the "run it live"
section on the demo page for why that's scoped to one request instead of a fully
persistent deployment.

## Deploy

**Vercel** - this repo now ships both the static site and a Python serverless function
(`api/score.py`), wired together by `vercel.json` at the repo root:

1. Import the repo.
2. Project Settings → **Root Directory**: leave blank (repo root), not `site`. This is a
   change from the site-only setup - `vercel.json`'s `outputDirectory` now points at
   `site` for you, and the function needs the repo root in scope to import
   `backend/engine/insider` directly (no code duplicated into the site).
3. Leave build command and framework preset alone (none needed).
4. Deploy. `/`, `/demo`, `/docs` resolve as before; `/api/score` is the new live endpoint.

**Render** - the static-only path still works if you don't want the live endpoint: New →
Static Site, publish directory `site`. Render's free tier doesn't run the Python
function, so `/demo`'s "run it live" panel would just show a request-failed state there,
gracefully, without breaking the rest of the page.
