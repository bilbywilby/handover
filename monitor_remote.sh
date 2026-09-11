#!/bin/bash
# Deployable w3m block for GitHub repository audit
REPO_URL="https://github.com/bilbywilby/handover"
LOG_FILE="/home/droid/handover/.audit_logs/sync_drift.log"

# Invoke tac for reverse chronological log viewing and w3m for remote commit audit
tac "$LOG_FILE" | head -n 50 | w3m -T text/plain
w3m "$REPO_URL/commits/main"
