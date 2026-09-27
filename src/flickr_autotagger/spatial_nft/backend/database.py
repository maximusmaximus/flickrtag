"""Database layer for AETHER-FLICKR.

Provides read-only queries against the 15,769 Flickr photo dataset in state.db,
and read/write persistence for pools, compositions, and mints in local aether.db.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.spatial_math import (
    to_globe_coords,
    to_semantic_cosmos_coords,
    to_color_torus_coords,
    to_chronos_helix_coords,
)

# Resolve state.db path dynamically for both WSL and native Windows
WSL_STATE_DB = Path("/root/.flickr-autotagger/state.db")
WIN_STATE_DB = Path(r"\\wsl.localhost\Ubuntu\root\.flickr-autotagger\state.db")

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
AETHER_DB_PATH = DATA_DIR / "aether.db"


def get_state_db_path() -> Path:
    """Return the accessible state.db path."""
    if WSL_STATE_DB.exists():
        return WSL_STATE_DB
    if WIN_STATE_DB.exists():
        return WIN_STATE_DB
    # Fallback to local copy if available
    local_state = DATA_DIR / "state.db"
    return local_state


def get_state_db_conn() -> sqlite3.Connection:
    """Open read-only connection to Flickr state database."""
    db_path = get_state_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Flickr state database not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_aether_db_conn() -> sqlite3.Connection:
    """Open read/write connection to Aether platform database."""
    conn = sqlite3.connect(str(AETHER_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_aether_db():
    """Initialize Aether application schema and default pools."""
    conn = get_aether_db_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS pools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        price_eth REAL NOT NULL,
        max_supply INTEGER NOT NULL,
        minted_count INTEGER DEFAULT 0,
        max_per_mint INTEGER DEFAULT 3,
        is_active INTEGER DEFAULT 1,
        created_at REAL NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS compositions (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        creator_wallet TEXT NOT NULL,
        contributing_photos TEXT NOT NULL,
        stitch_mode TEXT NOT NULL,
        blend_settings TEXT,
        image_url TEXT,
        video_url TEXT,
        tags_cocktail TEXT,
        geo_centroid TEXT,
        created_at REAL NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_id INTEGER UNIQUE NOT NULL,
        composition_id TEXT NOT NULL REFERENCES compositions(id),
        pool_id INTEGER NOT NULL REFERENCES pools(id),
        minter_wallet TEXT NOT NULL,
        price_paid_eth REAL NOT NULL,
        tx_hash TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        image_url TEXT NOT NULL,
        video_url TEXT NOT NULL,
        title TEXT NOT NULL,
        contributing_count INTEGER NOT NULL,
        minted_at REAL NOT NULL
    );
    """)

    # Check if default pools exist
    cur.execute("SELECT COUNT(*) FROM pools;")
    if cur.fetchone()[0] == 0:
        now = time.time()
        default_pools = [
            (
                "pacific-odyssey",
                "Pacific Northwest & West Coast Odyssey",
                "Curated from geocoded captures across Portland, Seattle, San Francisco, and the California Sierra Foothills.",
                "Geospatial",
                0.02,
                50,
                0,
                2,
                1,
                now,
            ),
            (
                "urban-noir",
                "Urban Noir & Kinetic Motion",
                "Atmospheric night photography, intentional motion blur, neon accents, and gritty street textures.",
                "Atmosphere",
                0.015,
                100,
                0,
                3,
                1,
                now,
            ),
            (
                "chromatic-etherea",
                "Chromatic Etherea & Lucid Dreams",
                "Dreamy, high-key overexposure, pastel hues, and abstract architectural geometry.",
                "Aesthetics",
                0.01,
                75,
                0,
                5,
                1,
                now,
            ),
            (
                "vip-genesis",
                "VIP Genesis 1-of-1 Masterworks",
                "Ultra-rare 1/1 bespoke compositions with verified provenance across historical photo collections.",
                "Genesis",
                0.08,
                10,
                0,
                1,
                1,
                now,
            ),
            (
                "open-mosaic",
                "Public Infinite Mosaic (Community Edition)",
                "Open access community minting pool with low gas barriers and unlimited creative remixing.",
                "Community",
                0.005,
                1000,
                0,
                10,
                1,
                now,
            ),
        ]
        cur.executemany(
            """
            INSERT INTO pools (slug, title, description, category, price_eth, max_supply, minted_count, max_per_mint, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            default_pools,
        )

    conn.commit()
    conn.close()


def get_archive_stats() -> Dict[str, Any]:
    """Return aggregated platform statistics from both databases."""
    state_conn = get_state_db_conn()
    cur = state_conn.cursor()

    cur.execute("SELECT COUNT(*) FROM photos;")
    total_photos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM photos WHERE venice_status = 'done';")
    venice_done = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM predicted_tags;")
    total_ai_tags = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT tag) FROM predicted_tags;")
    unique_tags = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM photos WHERE latitude IS NOT NULL AND latitude != '';")
    photos_with_gps = cur.fetchone()[0]

    state_conn.close()

    # Aether DB stats
    aether_conn = get_aether_db_conn()
    acur = aether_conn.cursor()

    acur.execute("SELECT COUNT(*) FROM pools WHERE is_active = 1;")
    active_pools = acur.fetchone()[0]

    acur.execute("SELECT COUNT(*) FROM mints;")
    total_mints = acur.fetchone()[0]

    acur.execute("SELECT COALESCE(SUM(price_paid_eth), 0.0) FROM mints;")
    total_volume_eth = acur.fetchone()[0]

    acur.execute("SELECT COUNT(*) FROM compositions;")
    total_compositions = acur.fetchone()[0]

    aether_conn.close()

    return {
        "total_photos": total_photos,
        "venice_analyzed": venice_done,
        "total_ai_tags": total_ai_tags,
        "unique_ai_tags": unique_tags,
        "photos_with_gps": photos_with_gps,
        "active_pools": active_pools,
        "total_mints": total_mints,
        "total_volume_eth": round(total_volume_eth, 4),
        "total_compositions": total_compositions,
    }


def get_spatial_photos(mode: str = "globe", limit: int = 1500, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return photos with pre-calculated 3D positions according to spatial projection mode."""
    conn = get_state_db_conn()
    cur = conn.cursor()

    query = """
    SELECT id, flickr_id, title, description, original_url, farm, server, secret,
           date_taken, ai_title, ai_description, scene_type, mood, technique, colors,
           location_guess, time_of_day, season_guess, objects, latitude, longitude,
           geo_display_name
    FROM photos
    WHERE original_url IS NOT NULL
    """
    params: List[Any] = []

    if category:
        c_lower = f"%{category.lower()}%"
        query += " AND (LOWER(scene_type) LIKE ? OR LOWER(mood) LIKE ? OR LOWER(geo_display_name) LIKE ?)"
        params.extend([c_lower, c_lower, c_lower])

    query += " ORDER BY id ASC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()

    results: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        photo_id = str(row["flickr_id"])
        lat = float(row["latitude"]) if row["latitude"] is not None else None
        lng = float(row["longitude"]) if row["longitude"] is not None else None
        loc_guess = row["location_guess"] or row["geo_display_name"]
        scene = row["scene_type"]
        mood = row["mood"]
        date_taken = row["date_taken"]

        # Parse colors array safely
        colors: List[str] = []
        if row["colors"]:
            try:
                colors = json.loads(row["colors"])
            except Exception:
                colors = [c.strip() for c in str(row["colors"]).split(",") if c.strip()]

        # Compute 3D position based on selected mode
        if mode == "globe":
            x, y, z = to_globe_coords(lat, lng, loc_guess, photo_id)
        elif mode == "cosmos":
            x, y, z = to_semantic_cosmos_coords(photo_id, scene, mood, len(colors))
        elif mode == "torus":
            x, y, z = to_color_torus_coords(colors, photo_id)
        elif mode == "helix":
            x, y, z = to_chronos_helix_coords(date_taken, idx, len(rows))
        else:
            x, y, z = to_globe_coords(lat, lng, loc_guess, photo_id)

        # Standard Flickr CDN resolution ladder
        server = row["server"] or "5499"
        secret = row["secret"] or ""
        fid = row["flickr_id"]
        # _q = 150px square thumbnail (blazing fast for 3D billboards)
        # _z = 640px medium
        # _b = 1024px large
        thumb_q = f"https://live.staticflickr.com/{server}/{fid}_{secret}_q.jpg"
        img_z = f"https://live.staticflickr.com/{server}/{fid}_{secret}_z.jpg"
        img_b = f"https://live.staticflickr.com/{server}/{fid}_{secret}_b.jpg"
        img_orig = row["original_url"] or img_b

        results.append({
            "id": row["id"],
            "flickr_id": fid,
            "title": row["ai_title"] or row["title"] or f"Capture #{fid}",
            "raw_title": row["title"],
            "ai_description": row["ai_description"],
            "scene_type": scene or "general",
            "mood": mood or "ambient",
            "technique": row["technique"],
            "colors": colors[:4],
            "location_name": row["geo_display_name"] or loc_guess or "Unmapped",
            "has_gps": lat is not None and lng is not None,
            "latitude": lat,
            "longitude": lng,
            "date_taken": date_taken,
            "thumb_url": thumb_q,
            "preview_url": img_z,
            "highres_url": img_b,
            "original_url": img_orig,
            "x": x,
            "y": y,
            "z": z,
        })

    conn.close()
    return results


def search_photos(query: str = "", tag: str = "", mood: str = "", scene: str = "", city: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Perform multi-facet search across titles, descriptions, Venice tags, moods, and locations."""
    conn = get_state_db_conn()
    cur = conn.cursor()

    conditions: List[str] = ["1=1"]
    params: List[Any] = []

    if query:
        q_wild = f"%{query.lower()}%"
        conditions.append("(LOWER(title) LIKE ? OR LOWER(ai_title) LIKE ? OR LOWER(ai_description) LIKE ? OR LOWER(objects) LIKE ?)")
        params.extend([q_wild, q_wild, q_wild, q_wild])

    if mood:
        conditions.append("LOWER(mood) LIKE ?")
        params.append(f"%{mood.lower()}%")

    if scene:
        conditions.append("LOWER(scene_type) LIKE ?")
        params.append(f"%{scene.lower()}%")

    if city:
        conditions.append("(LOWER(geo_display_name) LIKE ? OR LOWER(location_guess) LIKE ?)")
        params.extend([f"%{city.lower()}%", f"%{city.lower()}%"])

    sql = f"""
    SELECT id, flickr_id, title, ai_title, ai_description, scene_type, mood, technique,
           colors, server, secret, original_url, geo_display_name, location_guess,
           latitude, longitude, date_taken
    FROM photos
    WHERE {' AND '.join(conditions)}
    LIMIT ?
    """
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()

    results: List[Dict[str, Any]] = []
    for r in rows:
        fid = r["flickr_id"]
        server = r["server"] or "5499"
        secret = r["secret"] or ""
        results.append({
            "id": r["id"],
            "flickr_id": fid,
            "title": r["ai_title"] or r["title"] or f"Photo #{fid}",
            "ai_description": r["ai_description"],
            "scene_type": r["scene_type"],
            "mood": r["mood"],
            "technique": r["technique"],
            "location_name": r["geo_display_name"] or r["location_guess"] or "Unmapped",
            "has_gps": r["latitude"] is not None,
            "thumb_url": f"https://live.staticflickr.com/{server}/{fid}_{secret}_q.jpg",
            "preview_url": f"https://live.staticflickr.com/{server}/{fid}_{secret}_z.jpg",
            "highres_url": f"https://live.staticflickr.com/{server}/{fid}_{secret}_b.jpg",
            "date_taken": r["date_taken"],
        })

    conn.close()
    return results


def get_photo_detail(photo_id: str) -> Optional[Dict[str, Any]]:
    """Return full details including all Venice vision prompts and associated tags."""
    conn = get_state_db_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT * FROM photos WHERE flickr_id = ? OR id = ?;
        """,
        (photo_id, photo_id),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    db_id = row["id"]
    # Fetch existing and predicted tags
    cur.execute("SELECT tag FROM existing_tags WHERE photo_id = ?;", (db_id,))
    existing_tags = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT tag, confidence FROM predicted_tags WHERE photo_id = ? ORDER BY confidence DESC LIMIT 25;", (db_id,))
    predicted_tags = [{"tag": r[0], "confidence": round(r[1], 2)} for r in cur.fetchall()]

    conn.close()

    server = row["server"] or "5499"
    secret = row["secret"] or ""
    fid = row["flickr_id"]

    return {
        "id": row["id"],
        "flickr_id": fid,
        "title": row["title"],
        "ai_title": row["ai_title"],
        "ai_description": row["ai_description"],
        "scene_type": row["scene_type"],
        "mood": row["mood"],
        "technique": row["technique"],
        "colors": json.loads(row["colors"]) if row["colors"] and row["colors"].startswith("[") else [],
        "objects": json.loads(row["objects"]) if row["objects"] and row["objects"].startswith("[") else [],
        "location_guess": row["location_guess"],
        "geo_display_name": row["geo_display_name"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "time_of_day": row["time_of_day"],
        "season_guess": row["season_guess"],
        "date_taken": row["date_taken"],
        "thumb_url": f"https://live.staticflickr.com/{server}/{fid}_{secret}_q.jpg",
        "preview_url": f"https://live.staticflickr.com/{server}/{fid}_{secret}_z.jpg",
        "highres_url": f"https://live.staticflickr.com/{server}/{fid}_{secret}_b.jpg",
        "original_url": row["original_url"],
        "existing_tags": existing_tags,
        "predicted_tags": predicted_tags,
    }


def get_pools() -> List[Dict[str, Any]]:
    """Return all active and inactive pools with mint statistics."""
    conn = get_aether_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pools ORDER BY id ASC;")
    rows = cur.fetchall()
    pools = [dict(r) for r in rows]
    conn.close()
    return pools


def create_or_update_pool(pool_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update a pool category."""
    conn = get_aether_db_conn()
    cur = conn.cursor()

    pool_id = pool_data.get("id")
    slug = pool_data.get("slug")
    title = pool_data.get("title")
    desc = pool_data.get("description", "")
    category = pool_data.get("category", "General")
    price = float(pool_data.get("price_eth", 0.01))
    max_supply = int(pool_data.get("max_supply", 100))
    max_per_mint = int(pool_data.get("max_per_mint", 3))
    is_active = 1 if pool_data.get("is_active", True) else 0

    if pool_id:
        cur.execute(
            """
            UPDATE pools
            SET title = ?, description = ?, category = ?, price_eth = ?,
                max_supply = ?, max_per_mint = ?, is_active = ?
            WHERE id = ?;
            """,
            (title, desc, category, price, max_supply, max_per_mint, is_active, pool_id),
        )
    else:
        now = time.time()
        cur.execute(
            """
            INSERT INTO pools (slug, title, description, category, price_eth, max_supply, minted_count, max_per_mint, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?);
            """,
            (slug, title, desc, category, price, max_supply, max_per_mint, is_active, now),
        )
        pool_id = cur.lastrowid

    conn.commit()
    cur.execute("SELECT * FROM pools WHERE id = ?;", (pool_id,))
    row = dict(cur.fetchone())
    conn.close()
    return row


def save_composition(comp: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a new user composition recipe."""
    conn = get_aether_db_conn()
    cur = conn.cursor()

    cid = comp.get("id") or f"comp_{int(time.time() * 1000)}"
    title = comp.get("title", "Untitled Spatial Synthesis")
    desc = comp.get("description", "")
    creator = comp.get("creator_wallet", "0x0000000000000000000000000000000000000000")
    photos_json = json.dumps(comp.get("contributing_photos", []))
    stitch_mode = comp.get("stitch_mode", "poisson")
    blend_json = json.dumps(comp.get("blend_settings", {}))
    img_url = comp.get("image_url", "")
    vid_url = comp.get("video_url", "")
    tags_json = json.dumps(comp.get("tags_cocktail", []))
    geo_json = json.dumps(comp.get("geo_centroid", {}))
    now = time.time()

    cur.execute(
        """
        INSERT OR REPLACE INTO compositions
        (id, title, description, creator_wallet, contributing_photos, stitch_mode, blend_settings, image_url, video_url, tags_cocktail, geo_centroid, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (cid, title, desc, creator, photos_json, stitch_mode, blend_json, img_url, vid_url, tags_json, geo_json, now),
    )
    conn.commit()
    conn.close()

    comp["id"] = cid
    return comp


def mint_nft(mint_data: Dict[str, Any]) -> Dict[str, Any]:
    """Mint a composition into an active pool, decrementing supply and creating the NFT record."""
    conn = get_aether_db_conn()
    cur = conn.cursor()

    pool_id = int(mint_data["pool_id"])
    comp_id = mint_data["composition_id"]
    wallet = mint_data.get("minter_wallet", "0x9a3B...81F2")

    # Verify pool supply
    cur.execute("SELECT * FROM pools WHERE id = ? AND is_active = 1;", (pool_id,))
    pool = cur.fetchone()
    if not pool:
        conn.close()
        raise ValueError("Selected pool is inactive or does not exist.")

    if pool["minted_count"] >= pool["max_supply"]:
        conn.close()
        raise ValueError(f"Pool '{pool['title']}' is completely minted out ({pool['max_supply']}/{pool['max_supply']}).")

    # Generate next sequential token ID
    cur.execute("SELECT COALESCE(MAX(token_id), 1000) + 1 FROM mints;")
    token_id = cur.fetchone()[0]

    # Fetch composition
    cur.execute("SELECT * FROM compositions WHERE id = ?;", (comp_id,))
    comp_row = cur.fetchone()
    if not comp_row:
        conn.close()
        raise ValueError("Composition not found.")

    comp = dict(comp_row)
    contributing_photos = json.loads(comp["contributing_photos"])
    tags_cocktail = json.loads(comp["tags_cocktail"]) if comp["tags_cocktail"] else []
    geo_centroid = json.loads(comp["geo_centroid"]) if comp["geo_centroid"] else {}

    now = time.time()
    tx_hash = f"0x{int(now * 1000):x}{token_id:04x}c4b88144d50893a2"

    # Assemble ERC-721 OpenSea compliant metadata
    metadata = {
        "name": f"{comp['title']} #{token_id}",
        "description": f"{comp.get('description', '')}\n\nMinted via AETHER-FLICKR on Base L2. Blended from {len(contributing_photos)} historical photographs.",
        "image": comp["image_url"],
        "animation_url": comp["video_url"],
        "external_url": f"https://aether.voidride.art/mint/{token_id}",
        "attributes": [
            {"trait_type": "Pool Category", "value": pool["category"]},
            {"trait_type": "Pool Title", "value": pool["title"]},
            {"trait_type": "Contributing Photos", "value": len(contributing_photos)},
            {"trait_type": "Stitch Algorithm", "value": comp["stitch_mode"].capitalize()},
            {"trait_type": "Centroid Latitude", "value": geo_centroid.get("lat")},
            {"trait_type": "Centroid Longitude", "value": geo_centroid.get("lng")},
            {"trait_type": "Primary Tags", "value": ", ".join(tags_cocktail[:5])},
        ],
        "provenance": {
            "token_id": token_id,
            "composition_id": comp_id,
            "contributing_photos": contributing_photos,
        },
    }

    # Increment pool minted_count
    cur.execute("UPDATE pools SET minted_count = minted_count + 1 WHERE id = ?;", (pool_id,))

    # Insert mint record
    cur.execute(
        """
        INSERT INTO mints
        (token_id, composition_id, pool_id, minter_wallet, price_paid_eth, tx_hash, metadata_json, image_url, video_url, title, contributing_count, minted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            token_id,
            comp_id,
            pool_id,
            wallet,
            pool["price_eth"],
            tx_hash,
            json.dumps(metadata),
            comp["image_url"],
            comp["video_url"],
            comp["title"],
            len(contributing_photos),
            now,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "token_id": token_id,
        "pool_id": pool_id,
        "pool_title": pool["title"],
        "tx_hash": tx_hash,
        "price_eth": pool["price_eth"],
        "minter_wallet": wallet,
        "metadata": metadata,
        "image_url": comp["image_url"],
        "video_url": comp["video_url"],
    }


def get_recent_mints(limit: int = 24) -> List[Dict[str, Any]]:
    """Return latest minted NFTs for the public showcase gallery."""
    conn = get_aether_db_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT m.*, p.title as pool_title, p.category as pool_category, c.contributing_photos
        FROM mints m
        JOIN pools p ON m.pool_id = p.id
        JOIN compositions c ON m.composition_id = c.id
        ORDER BY m.minted_at DESC
        LIMIT ?;
        """,
        (limit,),
    )
    rows = cur.fetchall()

    results: List[Dict[str, Any]] = []
    for r in rows:
        results.append({
            "token_id": r["token_id"],
            "title": r["title"],
            "pool_title": r["pool_title"],
            "pool_category": r["pool_category"],
            "minter_wallet": r["minter_wallet"],
            "price_paid_eth": r["price_paid_eth"],
            "tx_hash": r["tx_hash"],
            "image_url": r["image_url"],
            "video_url": r["video_url"],
            "contributing_count": r["contributing_count"],
            "contributing_photos": json.loads(r["contributing_photos"]) if r["contributing_photos"] else [],
            "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
            "minted_at": r["minted_at"],
        })

    conn.close()
    return results
