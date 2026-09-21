#!/usr/bin/env python3
"""Continuous background pusher: syncs Venice metadata to Flickr.

- Only updates generic camera titles (e.g. PA030021, _A090086, Untitled, IMG_*)
- Strictly preserves human-given titles (e.g. Riverside Christmas, Coffee Beans)
- Updates descriptions (purged of any AI references)
- Pushes rich tags (purged of any AI references)
- Paces requests with 1.5s delay and exponential backoff on 429
- Continuously picks up newly analyzed photos from the background Venice runner
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, "/mnt/d/flickrtag/src")

from flickr_autotagger.config import get_settings
from flickr_autotagger.db import StateDB
from flickr_autotagger.auth import get_flickr_client
from flickr_autotagger.flickr_client import FlickrClient
from flickr_autotagger.cli import is_generic_title, clean_no_ai


def run():
    settings = get_settings()
    db = StateDB(settings.db_path)
    db.init_db()

    flickr = get_flickr_client(settings)
    if not flickr.token_valid(perms="write"):
        print("ERROR: Write token is not valid. Please authorize first.", flush=True)
        sys.exit(1)

    client = FlickrClient(flickr, db)
    merge_strategy = settings.TAG_MERGE_STRATEGY

    print("🚀 Continuous Flickr Pusher started.", flush=True)
    print("   Pacing: 1.5s per photo | Auto-retry on rate limit", flush=True)

    total_pushed = 0
    total_titles_updated = 0
    total_titles_kept = 0

    while True:
        rows = db.get_photos_needing_venice_push(limit=50)

        if not rows:
            # Check if all photos in total are done
            conn = db.connect()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM photos WHERE venice_status = 'pending'")
            pending_venice = cur.fetchone()[0]
            if pending_venice == 0:
                print(f"🎉 All photos processed and pushed! Total pushed this session: {total_pushed}", flush=True)
                break
            # Still waiting for more photos to be analyzed by Venice
            time.sleep(20)
            continue

        for r in rows:
            photo_id = r["id"]
            flickr_id = r["flickr_id"]
            orig_title = (r["title"] or "").strip()
            ai_title = r["ai_title"] or ""
            ai_desc = r["ai_description"] or ""

            approved = db.get_approved_tags(photo_id)
            raw_tags = [t["tag"] for t in approved] if approved else []
            clean_tags = [clean_no_ai(t) for t in raw_tags if clean_no_ai(t)]

            # Title decision
            should_update_title = is_generic_title(orig_title)
            target_title = None
            if should_update_title and ai_title:
                target_title = clean_no_ai(ai_title)

            target_desc = clean_no_ai(ai_desc)

            try:
                # 1. Push tags
                if clean_tags:
                    client.push_tags(flickr_id, clean_tags, merge_strategy)

                # 2. Update title & description
                meta_kwargs = {"photo_id": flickr_id}
                if target_title:
                    meta_kwargs["title"] = target_title
                    total_titles_updated += 1
                else:
                    total_titles_kept += 1

                if target_desc:
                    meta_kwargs["description"] = target_desc

                if len(meta_kwargs) > 1:
                    flickr.photos.setMeta(**meta_kwargs)

                db.mark_venice_pushed(photo_id)
                total_pushed += 1

                action_str = f'Title -> "{target_title}"' if target_title else f'Title: KEPT "{orig_title}"'
                print(
                    f"[{total_pushed}] ✅ {flickr_id} | {action_str} | {len(clean_tags)} tags",
                    flush=True,
                )

                time.sleep(1.5)

            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str:
                    print(f"⚠️ Rate limited on {flickr_id}, sleeping 60s...", flush=True)
                    time.sleep(60)
                    # Don't mark as pushed so it retries next loop
                else:
                    print(f"❌ Failed to push {flickr_id}: {err_str}", flush=True)
                    # Pause briefly
                    time.sleep(5)


if __name__ == "__main__":
    run()
