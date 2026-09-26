#!/usr/bin/env python3
"""Post-sync pipeline orchestrator:
1. Waits for geocoding to complete (if running) or runs it
2. Pushes geocoded coordinates to Flickr map (1.5s delay, 429 backoff)
3. Creates smart thematic & location albums on Flickr (0.8s delay, 429 backoff)
"""

import sys
import time
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flickr_autotagger.config import get_settings
from flickr_autotagger.db import StateDB
from flickr_autotagger.auth import authenticate
from flickr_autotagger.geocoder import geocode_all_pending, push_geo_to_flickr
from flickr_autotagger.albums import build_album_plan, create_albums_on_flickr

def wait_for_geocoding_or_run(db: StateDB) -> None:
    """Ensure all geocoding is finished before moving to geo-push."""
    conn = db.connect()
    while True:
        cur = conn.cursor()
        pending = cur.execute(
            "SELECT COUNT(*) FROM photos WHERE venice_status = 'done' AND (geo_status IS NULL OR geo_status = 'pending')"
        ).fetchone()[0]
        if pending == 0:
            print("✅ Geocoding is 100% complete!", flush=True)
            break
        print(f"⏳ Waiting for geocoding... {pending} photos pending", flush=True)
        time.sleep(15)

def main() -> None:
    settings = get_settings()
    db = StateDB(Path("/root/.flickr-autotagger/state.db"))
    flickr = authenticate(settings)

    print("============================================================", flush=True)
    print("🚀 POST-SYNC PIPELINE: GEO-PUSH & AUTO-ALBUMS", flush=True)
    print("============================================================", flush=True)

    # 1. Ensure Geocoding is complete
    wait_for_geocoding_or_run(db)

    # 2. Push Geolocation to Flickr Map
    print("\n📍 STEP 2: Pushing Geolocation Coordinates to Flickr Map...", flush=True)
    print("   Pacing: 1.5s per photo | 60s backoff on 429", flush=True)
    geo_stats = push_geo_to_flickr(flickr, db)
    print(f"✅ Geolocation push complete: {geo_stats}", flush=True)

    # 3. Create Smart Auto-Albums on Flickr
    print("\n📁 STEP 3: Building Smart Curated Auto-Albums...", flush=True)
    albums = build_album_plan(db, min_photos=5)
    print(f"   Found {len(albums)} high-quality album candidates.", flush=True)

    print("\n🚀 Creating albums on Flickr...", flush=True)
    print("   Pacing: 0.8s per photo addition | 2.5s between albums", flush=True)
    album_stats = create_albums_on_flickr(
        flickr,
        albums,
        max_albums=40,
        max_photos_per_album=100,
    )
    print(f"🎉 Auto-albums complete: {album_stats}", flush=True)
    print("\n============================================================", flush=True)
    print("🏁 ALL POST-SYNC TASKS COMPLETED SUCCESSFULLY!", flush=True)
    print("============================================================", flush=True)

if __name__ == "__main__":
    main()
