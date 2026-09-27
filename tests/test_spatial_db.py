"""Unit tests for spatial NFT database layer."""

import pytest
from flickr_autotagger.spatial_nft.backend.database import (
    init_aether_db,
    get_pools,
    create_or_update_pool,
    save_composition,
    mint_nft,
    get_recent_mints,
    get_archive_stats,
    get_spatial_photos,
    search_photos,
    get_photo_detail,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_aether_db()


def test_pools_initialization():
    """Verify that default pool categories are created."""
    pools = get_pools()
    assert len(pools) >= 5
    categories = [p["category"] for p in pools]
    assert "Geospatial" in categories
    assert "Atmosphere" in categories
    assert "Genesis" in categories


def test_create_and_update_pool():
    """Verify admin can create and update a custom pool category."""
    new_pool = {
        "title": "Neon Horizons Series",
        "slug": "neon-horizons",
        "category": "Futuristic",
        "price_eth": 0.025,
        "max_supply": 25,
        "max_per_mint": 2,
        "description": "Cyberpunk night compositions",
        "is_active": True,
    }
    created = create_or_update_pool(new_pool)
    assert created["id"] > 0
    assert created["slug"] == "neon-horizons"

    # Update pool price
    created["price_eth"] = 0.03
    updated = create_or_update_pool(created)
    assert updated["price_eth"] == 0.03


def test_save_and_mint_composition():
    """Verify full composition save and NFT minting transaction."""
    comp = {
        "title": "Test Composition #1",
        "description": "Test dual-asset composition",
        "creator_wallet": "0x1111222233334444555566667777888899990000",
        "contributing_photos": [
            {"flickr_id": "999001", "title": "Photo A", "thumb_url": "http://img.jpg"}
        ],
        "stitch_mode": "voronoi",
        "image_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
        "video_url": "http://video.mp4",
        "tags_cocktail": ["street", "night", "neon"],
    }
    saved_comp = save_composition(comp)
    assert saved_comp["id"].startswith("comp_")

    pools = get_pools()
    target_pool = pools[0]
    initial_minted = target_pool["minted_count"]

    mint_result = mint_nft({
        "composition_id": saved_comp["id"],
        "pool_id": target_pool["id"],
        "minter_wallet": "0x1111222233334444555566667777888899990000",
    })

    assert mint_result["token_id"] >= 1000
    assert mint_result["tx_hash"].startswith("0x")
    assert mint_result["metadata"]["name"] == f"{comp['title']} #{mint_result['token_id']}"

    # Verify pool supply decremented
    updated_pools = get_pools()
    updated_target = next(p for p in updated_pools if p["id"] == target_pool["id"])
    assert updated_target["minted_count"] == initial_minted + 1


def test_get_recent_mints():
    """Verify recent mints query returns public feed entries."""
    recent = get_recent_mints(limit=10)
    assert len(recent) >= 1
    assert "token_id" in recent[0]
    assert "contributing_photos" in recent[0]


def test_archive_stats():
    """Verify aggregated platform statistics."""
    stats = get_archive_stats()
    assert stats["total_photos"] >= 1000
    assert stats["venice_analyzed"] >= 1000
    assert stats["active_pools"] >= 5


def test_get_spatial_photos():
    """Verify spatial photos retrieval across different modes."""
    for mode in ["globe", "cosmos", "torus", "helix"]:
        photos = get_spatial_photos(mode=mode, limit=10)
        assert len(photos) > 0
        assert "x" in photos[0]
        assert "y" in photos[0]
        assert "z" in photos[0]
        assert "thumb_url" in photos[0]


def test_search_photos():
    """Verify faceted search on photos."""
    results = search_photos(query="view", limit=5)
    assert isinstance(results, list)
