# RAKSHAK site

Static, zero-build, 3-page site: `/` (overview), `/demo` (interactive replay of a real
captured run, not a live backend), `/docs` (architecture, requirements, API). No server,
no build step, no external calls except the GitHub link.

## Deploy

**Vercel**: import the repo, set the project root directory to `site`, leave build command
and output directory empty (static).

**Render**: New → Static Site, set the publish directory to `site`. No build command
needed.

Either way the three routes resolve at `/`, `/demo`, `/docs` since each is its own
`index.html` in a matching folder.
