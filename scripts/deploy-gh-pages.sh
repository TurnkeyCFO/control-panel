#!/bin/bash
# deploy-gh-pages.sh — Run from repo root on Windows (Git Bash / WSL)
# Deploys web/ to gh-pages branch and pushes to GitHub

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Deploy Control Panel to GitHub Pages ==="

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $CURRENT_BRANCH"

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  Uncommitted changes detected. Committing..."
    git add -A
    git commit -m "chore: deploy control panel to GitHub Pages

- Fix static asset paths for GitHub Pages compatibility
- Add CONTROL_PANEL_API_BASE config variable
- Add API connectivity indicator to UI
- Add GitHub Actions deploy workflow"
    git push origin "$CURRENT_BRANCH"
    echo "✅ Committed and pushed changes to $CURRENT_BRANCH"
else
    echo "✅ No uncommitted changes"
fi

# Create orphan gh-pages branch
echo "Creating gh-pages branch..."

# Delete gh-pages if it exists remotely
if git ls-remote --exit-code origin gh-pages >/dev/null 2>&1; then
    git push origin --delete gh-pages || true
fi

# Switch to orphan branch
git checkout --orphan gh-pages
git rm -rf . 2>/dev/null || true

# Copy web contents
echo "Copying web/ contents..."
cp -r web/* .
cp -r web/.github .github 2>/dev/null || true

# Clean up any non-web files that got copied
rm -rf app docs scripts artifacts .gitignore 2>/dev/null || true

# Remove vendor sourcemaps/duplicates if any
rm -rf vendor/*.map 2>/dev/null || true

# Commit and push
git add -A
git commit -m "Deploy control panel to GitHub Pages

Built from main branch web/ directory.
Static assets path-fixed for GitHub Pages hosting."

git push origin gh-pages --force

echo ""
echo "=========================================="
echo "✅ Deployed to gh-pages branch!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Go to repo Settings → Pages"
echo "2. Set source to 'gh-pages' branch (or GitHub Actions)"
echo "3. Site will be live at: https://turnkeycfo.github.io/control-panel/"
echo ""
echo "To switch back to main: git checkout main"