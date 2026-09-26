#!/usr/bin/env python3
"""Run geocoding on all pending photos with clean caching and logging."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flickr_autotagger.db import StateDB
from flickr_autotagger.geocoder import geocode_all_pending

def main() -> None:
    db = StateDB(Path("/root/.flickr-autotagger/state.db"))
    print("🌍 Starting geocoding runner...", flush=True)
    stats = geocode_all_pending(db)
    print(f"\n🎉 Geocoding complete: {stats}", flush=True)

if __name__ == "__main__":
    main()
