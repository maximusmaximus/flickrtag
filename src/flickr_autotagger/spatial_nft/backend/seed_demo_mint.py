"""Seeds a demo minted composition if no mints exist yet."""

import json
import time
from backend.database import get_aether_db_conn, get_pools, save_composition, mint_nft

def seed_demo():
    conn = get_aether_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM mints;")
    count = cur.fetchone()[0]
    conn.close()

    if count == 0:
        pools = get_pools()
        geo_pool = next((p for p in pools if p["category"] == "Geospatial"), pools[0])
        
        comp = {
            "id": "comp_genesis_001",
            "title": "Pacific Drift: Gothic Windows & Motion Horizons",
            "description": "Genesis spatial composition harmonizing archival captures from Sullivan's Gulch, Portland and rural transit lines. Rendered with Poisson gradient blending.",
            "creator_wallet": "0x9a3B4...81F2",
            "contributing_photos": [
                {
                    "flickr_id": "30291798331",
                    "title": "Overexposed Window View with Gothic Architecture",
                    "location_name": "Portland, Multnomah County, Oregon",
                    "thumb_url": "https://live.staticflickr.com/5499/30291798331_a79484073d_q.jpg",
                    "preview_url": "https://live.staticflickr.com/5499/30291798331_a79484073d_z.jpg",
                    "mood": "dreamy, ethereal, abstract",
                    "latitude": 45.5231,
                    "longitude": -122.6765
                },
                {
                    "flickr_id": "29746419683",
                    "title": "Motion Blur Landscape from a Moving Vehicle",
                    "location_name": "California Sierra Foothills",
                    "thumb_url": "https://live.staticflickr.com/5493/29746419683_872925b4e0_q.jpg",
                    "preview_url": "https://live.staticflickr.com/5493/29746419683_872925b4e0_z.jpg",
                    "mood": "dynamic, serene, fleeting",
                    "latitude": 39.5138,
                    "longitude": -121.5564
                }
            ],
            "stitch_mode": "poisson",
            "blend_settings": {"feather": 0.75, "vignette": 0.4, "grain": 0.25},
            "image_url": "https://live.staticflickr.com/5499/30291798331_a79484073d_b.jpg",
            "video_url": "https://live.staticflickr.com/5499/30291798331_a79484073d_b.jpg",
            "tags_cocktail": ["gothic", "motion blur", "dreamy", "ethereal", "portland", "sierra foothills", "shallow depth of field"],
            "geo_centroid": {"lat": 42.518, "lng": -122.116}
        }
        
        save_composition(comp)
        mint_nft({
            "composition_id": "comp_genesis_001",
            "pool_id": geo_pool["id"],
            "minter_wallet": "0x9a3B4...81F2"
        })
        print("✅ Demo genesis mint seeded successfully!")

if __name__ == "__main__":
    seed_demo()
