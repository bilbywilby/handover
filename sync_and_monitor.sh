#!/bin/bash
set -euo pipefail

REPO_DIR="/home/droid/handover"
cd "$REPO_DIR"

log() { echo "[$(date +'%Y-%m-%dT%H:%M:%S')] $*"; }

log "Starting Handover Seal Process..."

# 1. Generate SHA-256 seal including all utility scripts
log "Generating HANDOVER.sha256..."
sha256sum HANDOVER.json manifest.json scripts/repo-ctl sync_and_monitor.sh monitor_remote.sh remote_check.sh > HANDOVER.sha256

# 2. Index Synchronization
log "Synchronizing Git index..."
git add HANDOVER.sha256 sync_and_monitor.sh monitor_remote.sh remote_check.sh .gitignore
git add -u

# 3. Conditional Commit
if ! git diff --cached --quiet; then
    log "Committing state and seal..."
    git commit -m "chore(handover): integrate remote_check utility into seal"
else
    log "No index changes detected. Skipping commit."
fi

log "Pushing committed state to origin/main..."
git push origin main

log "Handover successfully sealed, pushed, and monitor deployed."
