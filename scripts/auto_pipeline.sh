#!/bin/bash
# Auto-pipeline: download → tag → approve → push
# Runs as a scheduled job, picks up where it left off each time.

set -euo pipefail
cd /mnt/d/flickrtag

VENV=".venv/bin"
LOG="/mnt/d/flickrtag/logs/pipeline_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

echo "=== Pipeline run: $(date) ===" | tee -a "$LOG"

# Step 1: Download (will skip already-downloaded, retry errors)
echo "[1/4] Downloading..." | tee -a "$LOG"
$VENV/flickr-autotagger download --concurrency 1 2>&1 | tee -a "$LOG"

# Step 2: Tag any newly downloaded photos
echo "[2/4] Tagging..." | tee -a "$LOG"
$VENV/flickr-autotagger tag --threshold 0.15 --max-tags 10 2>&1 | tee -a "$LOG"

# Step 3: Auto-approve all new tags
echo "[3/4] Auto-approving..." | tee -a "$LOG"
$VENV/flickr-autotagger review --auto-approve 2>&1 | tee -a "$LOG"

# Step 4: Push to Flickr
echo "[4/4] Pushing to Flickr..." | tee -a "$LOG"
$VENV/flickr-autotagger push 2>&1 | tee -a "$LOG"

# Status
echo "=== Status ===" | tee -a "$LOG"
$VENV/flickr-autotagger status 2>&1 | tee -a "$LOG"
echo "=== Done: $(date) ===" | tee -a "$LOG"
