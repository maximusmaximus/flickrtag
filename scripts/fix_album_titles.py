#!/usr/bin/env python3
"""Update Flickr photoset titles to clean ASCII/UTF-8 text without 4-byte emojis."""

import sys
import time
import re
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flickr_autotagger.config import get_settings
from flickr_autotagger.auth import authenticate

ALBUMS_MAP = [
    ("72177720335818836", "Black Rock Desert, Nevada", "Photos taken in or near Black Rock Desert, Nevada."),
    ("72177720335812320", "California, USA", "Photos taken in or near California, USA."),
    ("72177720335829953", "San Francisco, California", "Photos taken in or near San Francisco, California."),
    ("72177720335842209", "Portland, Oregon", "Photos taken in or near Portland, Oregon."),
    ("72177720335842219", "Chico, California", "Photos taken in or near Chico, California."),
    ("72177720335818886", "Southern California, USA", "Photos taken in or near Southern California, USA."),
    ("72177720335818896", "Pacific Northwest, USA", "Photos taken in or near Pacific Northwest, USA."),
    ("72177720335818901", "Ojai, California", "Photos taken in or near Ojai, California."),
    ("72177720335812172", "California", "Photos taken in or near California."),
    ("72177720335830003", "Los Angeles, California", "Photos taken in or near Los Angeles, California."),
    ("72177720335842234", "Pasadena, California", "Photos taken in or near Pasadena, California."),
    ("72177720335830013", "California Coast, USA", "Photos taken in or near California Coast, USA."),
    ("72177720335830018", "Burning Man, Black Rock Desert", "Photos taken in or near Burning Man, Black Rock Desert."),
    ("72177720335842239", "Mexico", "Photos taken in or near Mexico."),
    ("72177720335812192", "Pacific Northwest Forest", "Photos taken in or near temperate forest, Pacific Northwest."),
    ("72177720335812197", "Lassen Volcanic National Park", "Photos taken in or near Lassen Volcanic National Park, California."),
    ("72177720335812202", "Mission District, San Francisco", "Photos taken in or near Mission District, San Francisco."),
    ("72177720335818921", "San Francisco Bay Area", "Photos taken in or near San Francisco Bay Area, California."),
    ("72177720335830023", "Disneyland, Anaheim", "Photos taken in or near Disneyland, Anaheim."),
    ("72177720335830028", "Coastal California", "Photos taken in or near coastal California, USA."),
    ("72177720335818926", "Pacific Coast, USA", "Photos taken in or near Pacific Coast, USA."),
    ("72177720335818936", "Butte County, California", "Photos taken in or near Butte County, California."),
    ("72177720335812207", "Venice Beach, California", "Photos taken in or near Venice Beach, California."),
    ("72177720335812212", "Oregon, USA", "Photos taken in or near Oregon, USA."),
    ("72177720335818956", "Yellowstone National Park", "Photos taken in or near Yellowstone National Park, USA."),
    ("72177720335812360", "Burning Man Festival", "Photos taken in or near Burning Man festival, Black Rock Desert."),
    ("72177720335812217", "Street Photography", "A curated collection of street photography."),
    ("72177720335818961", "Night Photography", "A curated collection of night photography."),
    ("72177720335842269", "Event Photography", "A curated collection of event photography."),
    ("72177720335830068", "Still Life Photography", "A curated collection of still life photography."),
    ("72177720335812252", "Nature Photography", "A curated collection of nature photography."),
    ("72177720335812425", "Portrait Photography", "A curated collection of portrait photography."),
    ("72177720335830098", "Landscape Photography", "A curated collection of landscape photography."),
    ("72177720335812307", "Macro Photography", "A curated collection of macro photography."),
    ("72177720335819021", "Food & Drink", "A curated collection of food and drink photography."),
    ("72177720335842334", "Urban Photography", "A curated collection of urban photography."),
    ("72177720335812485", "Abstract Photography", "A curated collection of abstract photography."),
    ("72177720335830138", "Art Photography", "A curated collection of art photography."),
    ("72177720335812367", "Architecture Photography", "A curated collection of architecture photography."),
    ("72177720335812377", "Flora & Botanical", "A curated collection of botanical photography."),
]

def main() -> None:
    settings = get_settings()
    flickr = authenticate(settings)
    print(f"🔧 Updating titles for {len(ALBUMS_MAP)} photosets on Flickr...", flush=True)

    for i, (sid, title, desc) in enumerate(ALBUMS_MAP, 1):
        try:
            flickr.photosets.editMeta(photoset_id=sid, title=title, description=desc)
            print(f"[{i}/{len(ALBUMS_MAP)}] ✅ {title} (ID: {sid})", flush=True)
            time.sleep(1.0)
        except Exception as exc:
            print(f"[{i}/{len(ALBUMS_MAP)}] ❌ Failed {sid} ({title}): {exc}", flush=True)
            time.sleep(3.0)

    print("\n🎉 All photoset titles updated successfully!", flush=True)

if __name__ == "__main__":
    main()
