"""Auto-album creation — organizes photos into Flickr photosets.

Clusters Venice-analyzed photos by location, scene type, and date
to create meaningful albums automatically.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import structlog

from flickr_autotagger.db import StateDB

logger = structlog.get_logger()


def _normalize_location(location: str | None) -> str | None:
    """Normalize a location string for grouping.

    Strips qualifiers, extracts the core city/region name.
    """
    if not location or location.lower() in ("unknown", "unknown location", ""):
        return None

    cleaned = location.strip()

    # Remove hedging
    for prefix in (
        "likely ", "possibly ", "probably ", "appears to be ",
        "somewhere in ", "best guess: ", "near ", "downtown ",
    ):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]

    # Remove trailing qualifiers
    for suffix in (
        ", exact location unknown", ", unknown city",
        ", unknown country", " (unconfirmed)",
    ):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]

    # Take just the first major part (city name usually)
    # "Downtown Los Angeles, California, USA" -> "Los Angeles, California"
    parts = [p.strip() for p in cleaned.split(",")]
    if len(parts) >= 2:
        # Return city + region/country
        return ", ".join(parts[:2]).strip()
    return cleaned.strip()


def _normalize_scene(scene: str | None) -> str | None:
    """Normalize scene type for grouping."""
    if not scene:
        return None

    scene = scene.lower().strip()

    # Map to broad categories
    mappings = {
        "portrait": ["portrait", "headshot", "selfie", "face", "person"],
        "landscape": ["landscape", "nature", "scenic", "mountain", "forest", "lake", "ocean", "beach"],
        "architecture": ["architecture", "building", "structure", "cathedral", "church", "temple", "bridge"],
        "street": ["street", "urban street", "city street", "road"],
        "night": ["night", "nighttime", "evening", "dark", "neon"],
        "food & drink": ["food", "restaurant", "bar", "cafe", "coffee", "drink", "dining", "pub"],
        "urban": ["urban", "city", "cityscape", "skyline", "downtown"],
        "still life": ["still life", "object", "product", "flat lay"],
        "macro": ["macro", "close-up", "closeup", "detail"],
        "wildlife": ["wildlife", "animal", "bird", "insect", "pet", "dog", "cat"],
        "abstract": ["abstract", "pattern", "texture", "geometric"],
        "event": ["event", "concert", "festival", "wedding", "celebration", "party"],
        "travel": ["travel", "landmark", "monument", "tourist"],
        "art": ["art", "mural", "graffiti", "sculpture", "gallery", "museum", "installation"],
    }

    for category, keywords in mappings.items():
        for keyword in keywords:
            if keyword in scene:
                return category

    return scene  # Return original if no mapping found


def build_album_plan(db: StateDB, *, min_photos: int = 3) -> list[dict[str, Any]]:
    """Analyze Venice-analyzed photos and propose album groupings.

    Groups photos by:
    1. Location (city/region)
    2. Scene type (portrait, landscape, street, etc.)

    Args:
        db: StateDB instance.
        min_photos: Minimum photos per album (skip smaller groups).

    Returns:
        List of album dicts: {'name': str, 'description': str, 'type': str,
                               'photo_ids': list[str], 'count': int}
    """
    conn = db.connect()
    rows = conn.execute(
        "SELECT id, flickr_id, location_guess, scene_type, mood, ai_title "
        "FROM photos WHERE venice_status = 'done' ORDER BY id"
    ).fetchall()

    # Group by location
    location_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scene_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        photo = dict(row)

        # Location grouping
        loc = _normalize_location(photo.get("location_guess"))
        if loc and len(loc) > 2:
            location_groups[loc].append(photo)

        # Scene grouping
        scene = _normalize_scene(photo.get("scene_type"))
        if scene:
            scene_groups[scene].append(photo)

    albums: list[dict[str, Any]] = []

    # Location-based albums
    for location, photos in sorted(location_groups.items(), key=lambda x: -len(x[1])):
        if len(photos) < min_photos:
            continue
        albums.append({
            "name": f"📍 {location}",
            "description": f"Photos taken in or near {location}. Auto-organized by AI analysis.",
            "type": "location",
            "key": location,
            "photo_ids": [p["flickr_id"] for p in photos],
            "count": len(photos),
        })

    # Scene-based albums
    for scene, photos in sorted(scene_groups.items(), key=lambda x: -len(x[1])):
        if len(photos) < min_photos:
            continue
        albums.append({
            "name": f"🎨 {scene.title()}",
            "description": f"Photos categorized as '{scene}' by AI scene analysis.",
            "type": "scene",
            "key": scene,
            "photo_ids": [p["flickr_id"] for p in photos],
            "count": len(photos),
        })

    return albums


def create_albums_on_flickr(
    flickr: Any,
    albums: list[dict[str, Any]],
    *,
    dry_run: bool = False,
    max_albums: int = 50,
) -> dict[str, int]:
    """Create Flickr photosets from album plan.

    Args:
        flickr: Authenticated FlickrAPI client.
        albums: Album plan from build_album_plan().
        dry_run: If True, just log what would be created.
        max_albums: Maximum number of albums to create.

    Returns:
        Dict with counts: {'created': N, 'skipped': N, 'failed': N, 'photos_added': N}.
    """
    import time

    stats = {"created": 0, "skipped": 0, "failed": 0, "photos_added": 0}

    # Get existing photosets to avoid duplicates
    existing_sets: set[str] = set()
    try:
        sets_resp = flickr.photosets.getList(per_page=500)
        if sets_resp and "photosets" in sets_resp:
            for s in sets_resp["photosets"].get("photoset", []):
                existing_sets.add(s["title"]["_content"].lower())
    except Exception as exc:
        logger.warning("could_not_fetch_existing_sets", error=str(exc))

    albums_to_create = albums[:max_albums]

    for album in albums_to_create:
        name = album["name"]
        photo_ids = album["photo_ids"]

        if name.lower() in existing_sets:
            logger.info("album_exists_skipping", name=name)
            stats["skipped"] += 1
            continue

        if not photo_ids:
            stats["skipped"] += 1
            continue

        if dry_run:
            logger.info(
                "album_dry_run",
                name=name,
                type=album["type"],
                count=album["count"],
                sample_ids=photo_ids[:3],
            )
            stats["created"] += 1
            stats["photos_added"] += len(photo_ids)
            continue

        try:
            # Create the photoset with the first photo as the primary
            primary_id = photo_ids[0]
            result = flickr.photosets.create(
                title=name,
                description=album["description"],
                primary_photo_id=primary_id,
            )
            photoset_id = result["photoset"]["id"]

            logger.info(
                "album_created",
                name=name,
                photoset_id=photoset_id,
                primary=primary_id,
            )
            stats["created"] += 1
            stats["photos_added"] += 1  # primary already added

            # Add remaining photos to the set
            for photo_id in photo_ids[1:]:
                try:
                    flickr.photosets.addPhoto(
                        photoset_id=photoset_id,
                        photo_id=photo_id,
                    )
                    stats["photos_added"] += 1
                except Exception as add_exc:
                    error_str = str(add_exc)
                    if "429" in error_str:
                        time.sleep(60)
                    elif "Photo already in set" in error_str or "3" in str(getattr(add_exc, 'code', '')):
                        pass  # Already in set, skip
                    else:
                        logger.warning(
                            "album_add_photo_failed",
                            photoset_id=photoset_id,
                            photo_id=photo_id,
                            error=error_str,
                        )

                # Rate limit
                time.sleep(0.5)

            time.sleep(2)  # Pause between album creations

        except Exception as exc:
            error_str = str(exc)
            if "429" in error_str:
                logger.warning("album_create_rate_limited", name=name)
                time.sleep(60)
            logger.error("album_create_failed", name=name, error=error_str)
            stats["failed"] += 1

    logger.info("albums_complete", **stats)
    return stats
