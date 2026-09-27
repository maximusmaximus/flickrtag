"""Spatial mathematics and 3D coordinate transformations for photo exploration.

Projections supported:
1. Terra-Globe: Spherical GPS projection (lat/lng to 3D Cartesian coords)
2. Semantic Cosmos: Embedding/tag-based dimensional projection (cluster by mood, scene, tags)
3. Chromatic Torus: RGB/HSV color space mapped to a 3D donut ring
4. Chronos Helix: Ascending vertical time spiral (2016 - 2026)
"""

import math
import hashlib
from typing import Dict, Any, Tuple, List

# Primary geographic anchor centroids for photos with location guesses
GEO_ANCHORS = {
    "portland": (45.5152, -122.6784),
    "seattle": (47.6062, -122.3321),
    "san francisco": (37.7749, -122.4194),
    "los angeles": (34.0522, -118.2437),
    "chico": (39.7285, -121.8375),
    "oroville": (39.5138, -121.5564),
    "san jose": (37.3382, -121.8863),
    "sacramento": (38.5816, -121.4944),
    "oregon": (44.0000, -120.5000),
    "california": (36.7783, -119.4179),
}

# Semantic clusters for mood and scene vectors
SEMANTIC_CLUSTERS = {
    "street": (60.0, -20.0, 10.0),
    "noir": (80.0, -40.0, -30.0),
    "urban": (45.0, 15.0, 40.0),
    "architecture": (30.0, 50.0, -10.0),
    "nature": (-60.0, 30.0, 20.0),
    "landscape": (-80.0, 10.0, -40.0),
    "portrait": (10.0, 70.0, 30.0),
    "abstract": (-20.0, -60.0, 50.0),
    "motion": (50.0, -50.0, 30.0),
    "night": (70.0, -30.0, -50.0),
    "dreamy": (-40.0, -40.0, 60.0),
    "ethereal": (-30.0, -30.0, 80.0),
}


def _pseudo_hash(s: str) -> float:
    """Return a deterministic float in range [-1.0, 1.0] from a string."""
    h = int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)
    return (h / 0xFFFFFFFF) * 2.0 - 1.0


def to_globe_coords(lat: float | None, lng: float | None, loc_guess: str | None, photo_id: str, radius: float = 100.0) -> Tuple[float, float, float]:
    """Convert Latitude and Longitude to 3D Cartesian coordinates (X, Y, Z) on a sphere."""
    if lat is None or lng is None:
        # Check if location_guess matches any anchor
        assigned = False
        if loc_guess:
            lg_lower = loc_guess.lower()
            for city, (a_lat, a_lng) in GEO_ANCHORS.items():
                if city in lg_lower:
                    # Add pseudo jitter around anchor
                    lat = a_lat + _pseudo_hash(f"{photo_id}_lat") * 0.8
                    lng = a_lng + _pseudo_hash(f"{photo_id}_lng") * 0.8
                    assigned = True
                    break
        if not assigned:
            # Distribute across West Coast / global latitude belt
            lat = 35.0 + _pseudo_hash(f"{photo_id}_glat") * 15.0
            lng = -120.0 + _pseudo_hash(f"{photo_id}_glng") * 15.0

    phi = (90.0 - lat) * (math.pi / 180.0)
    theta = (lng + 180.0) * (math.pi / 180.0)

    # Elevation jitter
    r = radius + (_pseudo_hash(f"{photo_id}_alt") * 2.5)
    x = -(r * math.sin(phi) * math.cos(theta))
    z = r * math.sin(phi) * math.sin(theta)
    y = r * math.cos(phi)
    return round(x, 2), round(y, 2), round(z, 2)


def to_semantic_cosmos_coords(photo_id: str, scene: str | None, mood: str | None, tags_count: int, radius: float = 140.0) -> Tuple[float, float, float]:
    """Compute 3D position in the Semantic Cosmos by clustering moods and scene genres."""
    cx, cy, cz = 0.0, 0.0, 0.0
    weight = 0

    text_combo = f"{scene or ''} {mood or ''}".lower()
    for key, (kx, ky, kz) in SEMANTIC_CLUSTERS.items():
        if key in text_combo:
            cx += kx
            cy += ky
            cz += kz
            weight += 1

    if weight > 0:
        base_x = cx / weight
        base_y = cy / weight
        base_z = cz / weight
    else:
        # Generic cosmic scatter
        angle = _pseudo_hash(f"{photo_id}_c1") * math.pi
        pitch = _pseudo_hash(f"{photo_id}_c2") * math.pi * 0.5
        dist = 40.0 + abs(_pseudo_hash(f"{photo_id}_c3")) * 60.0
        base_x = dist * math.cos(pitch) * math.cos(angle)
        base_y = dist * math.sin(pitch)
        base_z = dist * math.cos(pitch) * math.sin(angle)

    # Add localized dispersion
    jx = _pseudo_hash(f"{photo_id}_jx") * 18.0
    jy = _pseudo_hash(f"{photo_id}_jy") * 18.0
    jz = _pseudo_hash(f"{photo_id}_jz") * 18.0

    return round(base_x + jx, 2), round(base_y + jy, 2), round(base_z + jz, 2)


def to_color_torus_coords(colors_list: List[str], photo_id: str, major_r: float = 90.0, minor_r: float = 30.0) -> Tuple[float, float, float]:
    """Map photo to a 3D Torus (donut ring) based on dominant color hue and saturation."""
    COLOR_HUES = {
        "red": 0.0,
        "orange": 30.0,
        "yellow": 60.0,
        "green": 120.0,
        "cyan": 180.0,
        "blue": 220.0,
        "purple": 280.0,
        "magenta": 310.0,
        "pink": 330.0,
        "white": 180.0,
        "black": 0.0,
        "gray": 90.0,
        "brown": 25.0,
    }

    hue_deg = 0.0
    match_count = 0
    if colors_list:
        for c in colors_list:
            c_clean = c.lower().strip()
            for cname, deg in COLOR_HUES.items():
                if cname in c_clean:
                    hue_deg += deg
                    match_count += 1
                    break

    if match_count > 0:
        hue_deg /= match_count
    else:
        hue_deg = abs(_pseudo_hash(f"{photo_id}_hue")) * 360.0

    theta = (hue_deg * math.pi) / 180.0
    phi = _pseudo_hash(f"{photo_id}_phi") * math.pi

    x = (major_r + minor_r * math.cos(phi)) * math.cos(theta)
    z = (major_r + minor_r * math.cos(phi)) * math.sin(theta)
    y = minor_r * math.sin(phi)

    return round(x, 2), round(y, 2), round(z, 2)


def to_chronos_helix_coords(date_taken: str | None, index: int, total: int = 1500, radius: float = 75.0, height: float = 240.0) -> Tuple[float, float, float]:
    """Map photo along an ascending vertical time spiral."""
    # Approximate year extraction
    year = 2020.0
    if date_taken and len(date_taken) >= 4:
        try:
            year = float(date_taken[:4])
        except ValueError:
            pass

    # Normalized progress between 2016 and 2026
    norm_t = min(max((year - 2016.0) / 10.0, 0.0), 1.0)
    # Add index fine-grain progression
    sub_t = norm_t + ((index % 100) / 100.0) * 0.08

    spiral_turns = 6.0
    angle = sub_t * spiral_turns * 2.0 * math.pi
    y = (sub_t - 0.5) * height
    x = radius * math.cos(angle) + _pseudo_hash(f"{index}_hx") * 6.0
    z = radius * math.sin(angle) + _pseudo_hash(f"{index}_hz") * 6.0

    return round(x, 2), round(y, 2), round(z, 2)
