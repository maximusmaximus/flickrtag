#!/usr/bin/env python3
"""Pipeline status and watchdog monitor for flickrtag.

Reports:
1. Venice Vision analysis progress & process health (restarts if dead)
2. Live Flickr push progress & process health (restarts if dead)
"""

import subprocess
import sqlite3
from pathlib import Path

DB_PATH = Path("/root/.flickr-autotagger/state.db")
TAGGER_LOG = Path("/mnt/d/flickrtag/logs/venice_full_run.log")
PUSHER_LOG = Path("/mnt/d/flickrtag/logs/venice_push.log")


def is_running(process_name: str) -> tuple[bool, str]:
    try:
        res = subprocess.run(
            ["pgrep", "-f", process_name],
            capture_output=True,
            text=True,
            check=False,
        )
        pids = res.stdout.strip().split()
        if pids and pids[0]:
            return True, pids[0]
        return False, ""
    except Exception:
        return False, ""


def check_and_restart():
    # Check DB stats
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM photos")
    total_photos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM photos WHERE venice_status = 'done'")
    venice_done = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM photos WHERE venice_pushed = 1")
    pushed_done = cur.fetchone()[0]

    # Process 1: Venice Tagger
    tagger_alive, tagger_pid = is_running("venice-tag")
    if not tagger_alive and venice_done < total_photos:
        print("⚠️ Venice tagger was down! Auto-restarting...", flush=True)
        subprocess.Popen(
            "nohup /mnt/d/flickrtag/.venv/bin/flickr-autotagger venice-tag --auto-approve >> /mnt/d/flickrtag/logs/venice_full_run.log 2>&1 &",
            shell=True,
            cwd="/mnt/d/flickrtag",
        )
        tagger_status = "🔄 Auto-restarted"
    else:
        tagger_status = f"🟢 Running (PID {tagger_pid})" if tagger_alive else "✅ Complete"

    # Process 2: Flickr Pusher
    pusher_alive, pusher_pid = is_running("continuous_push.py")
    if not pusher_alive and pushed_done < venice_done:
        print("⚠️ Flickr pusher was down! Auto-restarting...", flush=True)
        subprocess.Popen(
            "nohup /mnt/d/flickrtag/.venv/bin/python3 -u /mnt/d/flickrtag/scripts/continuous_push.py >> /mnt/d/flickrtag/logs/venice_push.log 2>&1 &",
            shell=True,
            cwd="/mnt/d/flickrtag",
        )
        pusher_status = "🔄 Auto-restarted"
    else:
        pusher_status = f"🟢 Running (PID {pusher_pid})" if pusher_alive else "⏸️ Caught up"

    # Print summary
    venice_pct = (venice_done / total_photos * 100) if total_photos else 0
    pushed_pct = (pushed_done / total_photos * 100) if total_photos else 0

    print("=" * 60)
    print("📊 FLICKRTAG PIPELINE STATUS")
    print("=" * 60)
    print(f"🔬 Venice Vision Tagger:  {venice_done:,} / {total_photos:,} ({venice_pct:.1f}%) | {tagger_status}")
    print(f"🚀 Live Flickr Pusher:   {pushed_done:,} / {total_photos:,} ({pushed_pct:.1f}%) | {pusher_status}")
    print("-" * 60)

    # Recent Venice tagger logs
    if TAGGER_LOG.exists():
        print("Recent Vision Analyses:")
        lines = [line.strip() for line in TAGGER_LOG.read_text().splitlines() if "✅" in line]
        for l in lines[-3:]:
            print(f"   {l}")

    print("-" * 60)

    # Recent Pusher logs
    if PUSHER_LOG.exists():
        print("Recent Live Flickr Pushes:")
        lines = [line.strip() for line in PUSHER_LOG.read_text().splitlines() if "✅" in line]
        for l in lines[-3:]:
            print(f"   {l}")

    print("=" * 60)


if __name__ == "__main__":
    check_and_restart()
