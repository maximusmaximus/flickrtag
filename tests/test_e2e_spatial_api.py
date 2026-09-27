"""End-to-End (E2E) integration tests for the AETHER // Robinhood Chain web platform."""

import pytest
from fastapi.testclient import TestClient
from flickr_autotagger.spatial_nft.backend.main import app

client = TestClient(app)


def test_e2e_platform_stats():
    """E2E Test: GET /api/stats returns complete archive and Robinhood Chain stats."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()

    assert data["total_photos"] >= 1000
    assert data["active_pools"] >= 5
    assert data["blockchain"]["network"] == "Robinhood Chain"
    assert data["blockchain"]["chain_id"] == 4663


def test_e2e_spatial_photos_all_modes():
    """E2E Test: GET /api/photos/spatial for Globe, Cosmos, Torus, and Helix."""
    for mode in ["globe", "cosmos", "torus", "helix"]:
        response = client.get(f"/api/photos/spatial?mode={mode}&limit=20")
        assert response.status_code == 200
        photos = response.json()
        assert len(photos) > 0
        first = photos[0]
        assert "x" in first and "y" in first and "z" in first
        assert "flickr_id" in first
        assert "thumb_url" in first


def test_e2e_photo_search():
    """E2E Test: GET /api/photos/search with various facets."""
    response = client.get("/api/photos/search?q=gothic&limit=10")
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)


def test_e2e_photo_detail():
    """E2E Test: GET /api/photos/{photo_id}."""
    # Fetch first photo ID
    list_res = client.get("/api/photos/spatial?limit=1")
    first_id = list_res.json()[0]["id"]

    detail_res = client.get(f"/api/photos/{first_id}")
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["id"] == first_id
    assert "existing_tags" in data
    assert "predicted_tags" in data


def test_e2e_pools_crud():
    """E2E Test: GET /api/pools and POST /api/pools."""
    # List pools
    list_res = client.get("/api/pools")
    assert list_res.status_code == 200
    pools = list_res.json()
    assert len(pools) >= 5

    # Create new pool
    new_pool_payload = {
        "title": "E2E Test Pool",
        "slug": "e2e-test-pool",
        "category": "Testing",
        "price_eth": 0.012,
        "max_supply": 40,
        "max_per_mint": 2,
        "description": "E2E verification pool",
        "is_active": True,
    }
    create_res = client.post("/api/pools", json=new_pool_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["slug"] == "e2e-test-pool"


def test_e2e_composition_and_mint_pipeline():
    """E2E Test: Save composition -> Mint on Robinhood Chain -> Verify in Recent Mints."""
    # 1. Save Composition
    comp_payload = {
        "title": "E2E Spatial Masterpiece",
        "description": "Full E2E test composition",
        "creator_wallet": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "contributing_photos": [
            {
                "flickr_id": "30291798331",
                "title": "Gothic Window",
                "location_name": "Portland, OR",
                "thumb_url": "https://live.staticflickr.com/5499/30291798331_a79484073d_q.jpg",
            }
        ],
        "stitch_mode": "poisson",
        "image_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
        "video_url": "https://video.mp4",
        "tags_cocktail": ["gothic", "architecture", "ethereal"],
    }
    comp_res = client.post("/api/compositions", json=comp_payload)
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert "id" in comp_data

    # 2. Mint on Robinhood Chain
    mint_payload = {
        "composition_id": comp_data["id"],
        "pool_id": 1,
        "minter_wallet": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    }
    mint_res = client.post("/api/mint", json=mint_payload)
    assert mint_res.status_code == 200
    mint_data = mint_res.json()

    assert mint_data["token_id"] >= 1000
    assert mint_data["network"] == "Robinhood Chain"
    assert mint_data["chain_id"] == 4663
    assert "explorer.chain.robinhood.com" in mint_data["explorer_url"]

    # 3. Verify in Recent Mints Feed
    recent_res = client.get("/api/mints/recent?limit=10")
    assert recent_res.status_code == 200
    recent = recent_res.json()
    minted_token = next((m for m in recent if m["token_id"] == mint_data["token_id"]), None)
    assert minted_token is not None
    assert minted_token["title"] == "E2E Spatial Masterpiece"
    assert minted_token["network"] == "Robinhood Chain"

    # 4. Verify Social Sharing Endpoint
    share_res = client.get(f"/api/share/{mint_data['token_id']}")
    assert share_res.status_code == 200
    share_data = share_res.json()
    assert share_data["token_id"] == mint_data["token_id"]
    assert "Robinhood" in share_data["x_share_text"]


def test_e2e_robinhood_endpoints():
    """E2E Test: Robinhood Chain network info, contract details, and tx verification."""
    # Network status
    net_res = client.get("/api/robinhood/network")
    assert net_res.status_code == 200
    net_data = net_res.json()
    assert net_data["chain_id"] == 4663
    assert net_data["is_online"] is True

    # Contract metadata
    contract_res = client.get("/api/robinhood/contract")
    assert contract_res.status_code == 200
    contract_data = contract_res.json()
    assert contract_data["network"]["chain_id"] == 4663
    assert len(contract_data["abi"]) > 0

    # Tx verification
    tx_res = client.post(
        "/api/robinhood/verify-tx",
        json={"tx_hash": "0x1237a7b819f2c38d21c33a4ba99d04a999b81f24"}
    )
    assert tx_res.status_code == 200
    tx_data = tx_res.json()
    assert tx_data["verified"] is True


def test_e2e_static_assets():
    """E2E Test: Verify index.html, style.css, and app.js serve with 200 OK."""
    index_res = client.get("/")
    assert index_res.status_code == 200
    assert "AETHER // FLICKR 3D" in index_res.text
    assert "Robinhood Chain (ID: 4663)" in index_res.text

    css_res = client.get("/style.css")
    assert css_res.status_code == 200

    js_res = client.get("/app.js")
    assert js_res.status_code == 200
    assert "ROBINHOOD_CHAIN" in js_res.text
