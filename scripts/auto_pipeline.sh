#!/bin/bash
# Auto-pipeline: download → tag → approve → push
# Runs as a scheduled job, picks up where it left off each time.
# Uses a lockfile to prevent concurrent runs.

set -euo pipefail
cd /mnt/d/flickrtag

LOCKFILE="/tmp/flickrtag-pipeline.lock"
VENV=".venv/bin"
mkdir -p /mnt/d/flickrtag/logs
LOG="/mnt/d/flickrtag/logs/pipeline_$(date +%Y%m%d_%H%M%S).log"

# Prevent concurrent runs
if [ -f "$LOCKFILE" ]; then
    LOCK_PID=$(cat "$LOCKFILE" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "Pipeline already running (PID $LOCK_PID), skipping." | tee -a "$LOG"
        exit 0
    else
        echo "Stale lockfile found, removing." | tee -a "$LOG"
        rm -f "$LOCKFILE"
    fi
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

echo "=== Pipeline run: $(date) ===" | tee -a "$LOG"

# Step 1: Download (will skip already-downloaded, retry errors)
echo "[1/4] Downloading..." | tee -a "$LOG"
$VENV/flickr-autotagger download --concurrency 1 2>&1 | tee -a "$LOG" || true

# Step 2: Tag any newly downloaded photos
echo "[2/4] Tagging..." | tee -a "$LOG"
$VENV/flickr-autotagger tag --threshold 0.15 --max-tags 10 2>&1 | tee -a "$LOG" || true

# Step 3: Auto-approve all new tags
echo "[3/4] Auto-approving..." | tee -a "$LOG"
$VENV/flickr-autotagger review --auto-approve 2>&1 | tee -a "$LOG" || true

# Step 4: Push to Flickr
echo "[4/4] Pushing to Flickr..." | tee -a "$LOG"
$VENV/flickr-autotagger push 2>&1 | tee -a "$LOG" || true

# Status
echo "=== Status ===" | tee -a "$LOG"
$VENV/flickr-autotagger status 2>&1 | tee -a "$LOG" || true
echo "=== Done: $(date) ===" | tee -a "$LOG"
