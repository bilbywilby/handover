#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/droid/handover"
MANIFEST="$REPO_DIR/manifest.json"

echo "[INFO] Commencing State Synchronization..." 
cd "$REPO_DIR"

# Stage manifest and operational tooling
git add "$MANIFEST" scripts/

# Commit changes if staging area contains modifications
if ! git diff --cached --quiet; then
    git commit -m "OPSEC: Sync manifest and harden operational tooling"
fi

# Push to origin if remote exists
if git remote get-url origin >/dev/null 2>&1; then
    git push -u origin "$(git rev-parse --abbrev-ref HEAD)"
else
    echo "[WARN] Remote 'origin' is not set. Skipping git push."
fi
