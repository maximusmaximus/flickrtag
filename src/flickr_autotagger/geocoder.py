"""Geocoding service — converts Venice.ai location guesses to lat/long.

Uses OpenStreetMap Nominatim (free, no API key required).
Rate limited to 1 request/second per Nominatim usage policy.
"""

from __future__ import annotations

import time
from typing import Any

import requests
import structlog

from flickr_autotagger.db import StateDB

logger = structlog.get_logger()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "flickr-autotagger/0.1.0 (https://github.com/maximusmaximus/flickrtag)"


import re

# Non-geographic descriptors that shouldn't be sent to Nominatim
NON_PLACE_TERMS = (
    "unknown", "kitchen", "bedroom", "living room", "bathroom", "dining room",
    "garage", "hallway", "basement", "attic", "backyard", "front yard",
    "patio", "balcony", "porch", "studio", "office", "restaurant",
    "bar", "cafe", "unspecified", "n/a", "none", "neighborhood",
    "residential", "diner", "street", "sidewalk", "alley", "garden", "park",
    "parking lot", "indoor", "interior", "exterior", "countryside", "rural",
    "suburban", "commercial", "industrial", "store", "shop", "hotel",
    "classroom", "gym", "rooftop", "urban", "gallery", "museum", "venue",
    "market", "booth", "house", "apartment", "table", "desk", "room",
)


def clean_location_query(location_text: str | None) -> str | None:
    """Clean location string and verify it is a genuine geographical place."""
    if not location_text:
        return None

    # Strip parentheticals like (Burning Man), (unconfirmed), (based on license plate)
    cleaned = re.sub(r"\(.*?\)", "", location_text).strip()

    # Strip 'or similar...' clauses (e.g. 'Nevada or similar desert location')
    if " or " in cleaned:
        cleaned = re.split(r"\s+or\s+", cleaned)[0].strip()

    loc_lower = cleaned.lower()
    for term in NON_PLACE_TERMS:
        if term in loc_lower:
            # Allow famous parks even if they contain 'park'
            if "national park" in loc_lower or "state park" in loc_lower:
                continue
            return None

    # Remove hedging phrases
    for prefix in (
        "likely ", "possibly ", "probably ", "appears to be ",
        "somewhere in ", "best guess: ", "near ", "downtown ",
    ):
        if loc_lower.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            loc_lower = cleaned.lower()

    # Remove trailing qualifiers
    for suffix in (
        ", exact location unknown", ", unknown city",
        ", unknown country", " (unconfirmed)",
    ):
        if loc_lower.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            loc_lower = cleaned.lower()

    if len(cleaned) < 3:
        return None

    # Must be geographically specific: have a comma (City, State) or contain known entity
    known_geo_indicators = (
        ",", "usa", "united states", "california", "nevada", "oregon", "mexico",
        "canada", "japan", "uk", "france", "italy", "spain", "germany",
        "national park", "state park", "county", "district", "desert", "san francisco",
        "los angeles", "portland", "chico", "ojai", "pasadena", "burning man",
    )
    if not any(k in loc_lower for k in known_geo_indicators):
        return None

    return cleaned


def geocode_location(location_text: str) -> dict[str, Any] | None:
    """Geocode a location string to lat/long using OpenStreetMap Nominatim.

    Args:
        location_text: Free-text location description (e.g., "Downtown Los Angeles, California").

    Returns:
        Dict with 'lat', 'lon', 'display_name' or None if geocoding fails.
    """
    cleaned = clean_location_query(location_text)
    if not cleaned:
        return None

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "q": cleaned,
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()

        if not results:
            logger.debug("geocode_no_results", query=cleaned)
            return None

        best = results[0]
        return {
            "lat": float(best["lat"]),
            "lon": float(best["lon"]),
            "display_name": best.get("display_name", ""),
            "type": best.get("type", ""),
            "importance": float(best.get("importance", 0)),
        }

    except Exception as exc:
        logger.warning("geocode_error", query=cleaned, error=str(exc))
        return None


def geocode_all_pending(db: StateDB) -> dict[str, int]:
    """Geocode all Venice-analyzed photos that have a location_guess.

    Uses an in-memory cache to deduplicate requests and strictly adheres
    to Nominatim's 1 req/sec rate limit.
    """
    conn = db.connect()
    rows = conn.execute(
        "SELECT id, flickr_id, location_guess, venice_status "
        "FROM photos "
        "WHERE venice_status = 'done' "
        "AND (geo_status IS NULL OR geo_status = 'pending') "
        "ORDER BY id"
    ).fetchall()

    stats = {"geocoded": 0, "skipped": 0, "failed": 0, "no_location": 0}

    if not rows:
        logger.info("geocode_nothing_pending")
        return stats

    logger.info("geocode_starting", count=len(rows))

    # In-memory cache: cleaned_query -> result dict or None
    geo_cache: dict[str, dict[str, Any] | None] = {}

    for i, row in enumerate(rows):
        photo_id = row["id"]
        flickr_id = row["flickr_id"]
        location_guess = row["location_guess"]

        cleaned = clean_location_query(location_guess)
        if not cleaned:
            db.update_geo_status(photo_id, "no_location")
            stats["no_location"] += 1
            continue

        # Check cache first
        if cleaned in geo_cache:
            cached_result = geo_cache[cleaned]
            if cached_result is None:
                db.update_geo_status(photo_id, "failed")
                stats["failed"] += 1
            else:
                db.store_geocode(photo_id, cached_result["lat"], cached_result["lon"], cached_result["display_name"])
                stats["geocoded"] += 1
            continue

        # Query Nominatim with rate limiting
        result = geocode_location(cleaned)
        geo_cache[cleaned] = result

        if result is None:
            db.update_geo_status(photo_id, "failed")
            stats["failed"] += 1
        else:
            db.store_geocode(photo_id, result["lat"], result["lon"], result["display_name"])
            stats["geocoded"] += 1
            logger.info(
                "geocoded",
                flickr_id=flickr_id,
                location=cleaned[:40],
                lat=f"{result['lat']:.4f}",
                lon=f"{result['lon']:.4f}",
            )

        # Rate limit: 1.1s per remote request to respect Nominatim policy
        time.sleep(1.1)

        # Progress log every 50
        done = stats["geocoded"] + stats["failed"] + stats["skipped"] + stats["no_location"]
        if done % 50 == 0:
            logger.info("geocode_progress", **stats, cached_places=len(geo_cache), remaining=len(rows) - done)

    logger.info("geocode_complete", **stats)
    return stats


def push_geo_to_flickr(
    flickr: Any,
    db: StateDB,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Push geocoded locations to Flickr.

    Returns dict with counts: {'pushed': N, 'skipped': N, 'failed': N}.
    """
    conn = db.connect()
    rows = conn.execute(
        "SELECT id, flickr_id, latitude, longitude, scene_type "
        "FROM photos "
        "WHERE geo_status = 'done' "
        "AND (geo_pushed IS NULL OR geo_pushed = 0) "
        "ORDER BY id"
    ).fetchall()

    stats = {"pushed": 0, "skipped": 0, "failed": 0}

    if not rows:
        logger.info("geo_push_nothing_pending")
        return stats

    logger.info("geo_push_starting", count=len(rows))

    for row in rows:
        flickr_id = row["flickr_id"]
        lat = row["latitude"]
        lon = row["longitude"]
        scene_type = (row["scene_type"] or "").lower()

        # Map scene_type to Flickr geo context (1=indoors, 2=outdoors, 0=not defined)
        if any(x in scene_type for x in ("indoor", "interior", "inside", "studio")):
            context = 1
        elif any(x in scene_type for x in ("outdoor", "exterior", "street", "urban", "nature", "landscape", "park")):
            context = 2
        else:
            context = 0

        if dry_run:
            logger.info("geo_push_dry_run", flickr_id=flickr_id, lat=lat, lon=lon, context=context)
            stats["pushed"] += 1
            continue

        try:
            flickr.photos.geo.setLocation(
                photo_id=flickr_id,
                lat=str(lat),
                lon=str(lon),
                accuracy=11,  # City-level accuracy (Venice guesses aren't precise)
                context=context,
            )
            db.mark_geo_pushed(row["id"])
            stats["pushed"] += 1
            time.sleep(1.5)  # Rate limit for Flickr API

        except Exception as exc:
            error_str = str(exc)
            if "429" in error_str:
                logger.warning("geo_push_rate_limited", flickr_id=flickr_id)
                time.sleep(60)
            logger.error("geo_push_failed", flickr_id=flickr_id, error=error_str)
            stats["failed"] += 1

    logger.info("geo_push_complete", **stats)
    return stats
