"""AETHER-FLICKR FastAPI Web Server.

Serves 3D spatial photo coordinates, composition stitching endpoints,
Robinhood Chain (Chain ID: 4663) ERC-721 minting, admin pool management,
and public mint showcase.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.database import (
    init_aether_db,
    get_archive_stats,
    get_spatial_photos,
    search_photos,
    get_photo_detail,
    get_pools,
    create_or_update_pool,
    save_composition,
    mint_nft,
    get_recent_mints,
)
from backend.robinhood_chain import (
    ROBINHOOD_MAINNET,
    CONTRACT_CONFIG,
    COMPOSITE_NFT_ABI,
    robinhood_client,
)

app = FastAPI(
    title="AETHER-FLICKR // Robinhood Chain Spatial Minting Engine",
    description="3D Photogrammetry & Dual-Asset Generative NFT Platform on Robinhood Chain (Arbitrum Orbit L2, Chain ID: 4663)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# --- Pydantic Request Models ---
class PoolCreateUpdate(BaseModel):
    id: Optional[int] = None
    slug: str
    title: str
    description: str = ""
    category: str = "General"
    price_eth: float = 0.01
    max_supply: int = 100
    max_per_mint: int = 3
    is_active: bool = True


class CompositionPayload(BaseModel):
    id: Optional[str] = None
    title: str
    description: str = ""
    creator_wallet: str = "0x9a3B4...81F2"
    contributing_photos: List[Dict[str, Any]]
    stitch_mode: str = "poisson"
    blend_settings: Dict[str, Any] = Field(default_factory=dict)
    image_url: str
    video_url: str = ""
    tags_cocktail: List[str] = Field(default_factory=list)
    geo_centroid: Dict[str, Any] = Field(default_factory=dict)


class MintPayload(BaseModel):
    composition_id: str
    pool_id: int
    minter_wallet: str = "0x9a3B4...81F2"
    tx_hash: Optional[str] = None


class VerifyTxPayload(BaseModel):
    tx_hash: str


@app.on_event("startup")
def startup_event():
    """Ensure database and default pools are ready on launch."""
    init_aether_db()


# --- Robinhood Chain Endpoints ---
@app.get("/api/robinhood/network")
def api_robinhood_network():
    """Return live Robinhood Chain L2 status, block number, and gas price."""
    return robinhood_client.get_status()


@app.get("/api/robinhood/contract")
def api_robinhood_contract():
    """Return smart contract configuration and ABI for Robinhood Chain."""
    return {
        "network": ROBINHOOD_MAINNET,
        "contract": CONTRACT_CONFIG,
        "abi": COMPOSITE_NFT_ABI,
    }


@app.post("/api/robinhood/verify-tx")
def api_robinhood_verify_tx(payload: VerifyTxPayload):
    """Verify transaction status on Robinhood Chain."""
    return robinhood_client.verify_tx(payload.tx_hash)


# --- Platform Routes ---
@app.get("/api/stats")
def api_stats():
    """Return aggregated platform statistics and Robinhood Chain details."""
    try:
        stats = get_archive_stats()
        stats["blockchain"] = {
            "network": ROBINHOOD_MAINNET["name"],
            "chain_id": ROBINHOOD_MAINNET["chain_id"],
            "settlement": "Ethereum Mainnet via Arbitrum Orbit",
            "explorer_url": ROBINHOOD_MAINNET["explorer_url"],
        }
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/photos/spatial")
def api_spatial(
    mode: str = Query("globe", pattern="^(globe|cosmos|torus|helix)$"),
    limit: int = Query(1200, ge=50, le=4000),
    category: Optional[str] = Query(None),
):
    """Retrieve photos with calculated 3D coordinates for the chosen projection."""
    try:
        return get_spatial_photos(mode=mode, limit=limit, category=category)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/photos/search")
def api_search(
    q: str = Query(""),
    tag: str = Query(""),
    mood: str = Query(""),
    scene: str = Query(""),
    city: str = Query(""),
    limit: int = Query(60, ge=1, le=200),
):
    """Faceted search across photo titles, Venice prompts, moods, and locations."""
    try:
        return search_photos(query=q, tag=tag, mood=mood, scene=scene, city=city, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/photos/{photo_id}")
def api_photo_detail(photo_id: str):
    """Fetch complete metadata for a single photo including all Venice AI prompts."""
    photo = get_photo_detail(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


@app.get("/api/pools")
def api_get_pools():
    """Retrieve all minting pool categories and current supply stats."""
    return get_pools()


@app.post("/api/pools")
def api_save_pool(payload: PoolCreateUpdate):
    """Create or update a pool category (Admin)."""
    try:
        return create_or_update_pool(payload.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/compositions")
def api_save_composition(payload: CompositionPayload):
    """Save a user composition recipe."""
    try:
        return save_composition(payload.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/mint")
def api_mint(payload: MintPayload):
    """Mint a composition into a pool category and generate the Robinhood Chain NFT."""
    try:
        mint_result = mint_nft(payload.dict())
        mint_result["network"] = ROBINHOOD_MAINNET["name"]
        mint_result["chain_id"] = ROBINHOOD_MAINNET["chain_id"]
        mint_result["explorer_url"] = f"{ROBINHOOD_MAINNET['explorer_url']}/tx/{mint_result['tx_hash']}"
        return mint_result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mints/recent")
def api_recent_mints(limit: int = Query(24, ge=1, le=100)):
    """Return latest minted NFTs for the public showcase."""
    try:
        mints = get_recent_mints(limit=limit)
        for m in mints:
            m["network"] = ROBINHOOD_MAINNET["name"]
            m["chain_id"] = ROBINHOOD_MAINNET["chain_id"]
            m["explorer_url"] = f"{ROBINHOOD_MAINNET['explorer_url']}/tx/{m['tx_hash']}"
        return mints
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/share/{token_id}")
def api_share_token(token_id: int):
    """Return social sharing payload with OpenGraph card parameters."""
    mints = get_recent_mints(limit=100)
    matched = next((m for m in mints if m["token_id"] == token_id), None)
    if not matched:
        raise HTTPException(status_code=404, detail="Minted NFT not found")
    return {
        "title": matched["title"],
        "token_id": matched["token_id"],
        "pool_category": matched["pool_category"],
        "image_url": matched["image_url"],
        "video_url": matched["video_url"],
        "minter_wallet": matched["minter_wallet"],
        "network": ROBINHOOD_MAINNET["name"],
        "chain_id": ROBINHOOD_MAINNET["chain_id"],
        "share_url": f"https://aether.voidride.art/mint/{token_id}",
        "x_share_text": f"Just minted '{matched['title']}' on @RobinhoodApp Chain (Arbitrum Orbit L2)! 15k photo spatial synthesis: https://aether.voidride.art/mint/{token_id}",
    }


# Mount static assets
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
