#!/bin/bash
set -euo pipefail

REPO_DIR="/home/droid/handover"
cd "$REPO_DIR"

log() { echo "[$(date +'%Y-%m-%dT%H:%M:%S')] $*"; }

log "Starting Handover Seal Process..."

# Generate SHA-256 seal including everything in scripts/tooling/
log "Generating HANDOVER.sha256..."
# Find all files in tooling and the core scripts to include in the checksum
FILES_TO_SEAL=$(find scripts/tooling -type f | sort)
sha256sum HANDOVER.json manifest.json scripts/repo-ctl sync_and_monitor.sh monitor_remote.sh remote_check.sh $FILES_TO_SEAL > HANDOVER.sha256

log "Synchronizing Git index..."
git add HANDOVER.sha256 sync_and_monitor.sh monitor_remote.sh remote_check.sh .gitignore scripts/tooling/
git add -u

if ! git diff --cached --quiet; then
    log "Committing state and expanded tooling seal..."
    git commit -m "chore(handover): formalize shadow tooling and update seal"
else
    log "No index changes detected."
fi

log "Pushing to origin/main..."
git push origin main
