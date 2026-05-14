# Deploy Handoff — Control Panel → GitHub Pages

**Operator:** Hermes Agent (for Ricky West / Turnkey Services)
**Date:** 2026-05-14
**Status:** Ready for Claude Code to execute

---

## What's been done

- Audited repo: `web/` is the real frontend, `app/` is FastAPI backend, `docs/` is a contaminated copy
- Built deploy-ready static files in `/tmp/cp-deploy-89x1ho0e/` with three fixes:
  - All `/static/` paths → `./` (GitHub Pages compatibility)
  - Added `CONTROL_PANEL_API_BASE` config variable in `app.js`
  - Added API connectivity status indicator in the UI
- Created GitHub Actions deploy workflow (below)

## What you need to do (Claude Code — run these in order)

### Step 1: Create the GitHub Actions workflow

Create `.github/workflows/deploy.yml` in the repo root:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Pages
        uses: actions/configure-pages@v4

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: './web'

      - name: Deploy to GitHub Pages
        uses: actions/deploy-pages@v4
```

### Step 2: Push the deploy branch

```bash
# From the repo root (C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\control-panel)

# Make sure everything is committed on main
git add -A
git commit -m "chore: deploy control panel to GitHub Pages

- Fix static asset paths for GitHub Pages compatibility
- Add CONTROL_PANEL_API_BASE config variable
- Add API connectivity indicator to UI
- Add GitHub Actions deploy workflow"

git push origin main
```

### Step 3: Enable GitHub Pages

1. Go to repo Settings → Pages
2. Source: **GitHub Actions**
3. Save

### Step 4: Verify

After push, GitHub Actions runs automatically. When the `gh-pages` branch is created, the site goes live at:
`https://turnkeycfo.github.io/control-panel/` (or your custom domain)

### Optional: API connectivity

The deployed UI works standalone. To hit live APIs from the browser, open the page console and set:
```javascript
window.CONTROL_PANEL_API_BASE = "https://your-tunnel-url.ngrok-free.app"
```
Or set it as a constant in `web/app.js` before building.

---

## Files that were modified/created

| File | Action |
|---|---|
| `.github/workflows/deploy.yml` | **Created** — GitHub Actions workflow |
| `web/index.html` | Fixed static paths (`/static/` → `./`) |
| `web/app.js` | Added `CONTROL_PANEL_API_BASE` config, API status indicator |
| `web/style.css` | No changes (just confirming it's deploy-ready) |
| `docs/` | **Left as-is** — dirty planning docs are Ricky's, not touched |

## Notes

- `docs/` directory still has the old copies — deliberately untouched
- The `web/` folder is the source of truth for the frontend
- This deploys `web/` directly via GitHub Actions, **not** the `docs/` folder