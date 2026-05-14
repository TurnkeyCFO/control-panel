#!/bin/bash
# deploy-control-panel.sh — Run from repo root
# Creates gh-pages branch, deploys web/, pushes, enables GitHub Pages
set -euo pipefail

REPO_ROOT="C:/Users/ricky_j3cdbqw/CLAUDE CODE PROJECTS/control-panel"
cd "$REPO_ROOT"

echo "=== Step 1: Ensure main is current ==="
git checkout main
git pull origin main 2>/dev/null || true

echo "=== Step 2: Delete old gh-pages (local + remote) ==="
git branch -D gh-pages 2>/dev/null || true
git push origin --delete gh-pages 2>/dev/null || true

echo "=== Step 3: Create orphan gh-pages branch ==="
git checkout --orphan gh-pages

echo "=== Step 4: Remove all tracked files from orphan ==="
git rm -rf . 2>/dev/null || true

echo "=== Step 5: Clean everything leftover in working tree ==="
# Remove visible files/dirs that aren't .git
for item in *; do
  if [ "$item" != ".git" ]; then
    rm -rf "$item" 2>/dev/null || true
  fi
done

echo "=== Step 6: Copy web/ contents into root ==="
cp -r web/* .
cp -r web/.github .github 2>/dev/null || true
# Remove the vendor sourcemaps to keep it lean
rm -rf vendor/*.map 2>/dev/null || true

echo "=== Step 7: Stage and commit ==="
git add -A
git commit -m "deploy: control panel to GitHub Pages

- Static files from web/
- Path-fixed for GitHub Pages hosting"

echo "=== Step 8: Push gh-pages branch ==="
git push origin gh-pages --force

echo ""
echo "=========================================="
echo "✅ Deployed to gh-pages branch!"
echo "=========================================="
echo ""
echo "NEXT: Go to GitHub → Settings → Pages"
echo "  Source: switch to 'Deploy from a branch'"
echo "  Branch: gh-pages / (root)"
echo "  Click Save"
echo ""
echo "Live URL: https://turnkeycfo.github.io/control-panel/"