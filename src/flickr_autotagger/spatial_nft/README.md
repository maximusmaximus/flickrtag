# 🌐 AETHER // FLICKR 3D

> **Spatial Photogrammetry, Multi-Exposure Composition Studio & Generative Minting Engine**  
> Built upon the **15,769 Flickr Photographs**, **314,294 Venice AI Vision Tags**, and **902 GPS Geocoded Records** from `state.db`.

---

## ⚡ Quick Start

### 1. Launch the Server
The application is pre-configured and can be launched on **`http://localhost:8000`**:

- **Windows**: Double click [`start_server.bat`](file:///C:/Users/maxin/.gemini/antigravity/scratch/aether-flickr/start_server.bat) or run:
  ```powershell
  wsl -u root /mnt/d/flickrtag/.venv/bin/python /mnt/c/Users/maxin/.gemini/antigravity/scratch/aether-flickr/run_server.py
  ```
- **WSL / Linux**: Run [`start_server.sh`](file:///C:/Users/maxin/.gemini/antigravity/scratch/aether-flickr/start_server.sh):
  ```bash
  ./start_server.sh
  ```

Visit **[http://localhost:8000](http://localhost:8000)** in any browser.

---

## 🚀 Key Features

### 1. 3D Spatial Exploration (`Three.js` / WebGL)
- **Terra-Globe**: 3D interactive Earth globe pinning 902+ exact GPS coordinates across Portland, Seattle, San Francisco, Los Angeles, and the California Sierra Foothills.
- **Semantic Cosmos**: 3D starfield cluster space positioned by AI tags, scene types, and Venice moods.
- **Chromatic Torus**: RGB/HSV color spectrum donut wheel sorted by dominant color hex.
- **Chronos Helix**: Ascending time spiral winding through photo capture dates from 2016 to 2026.
- **Interactive Raycasting**: Hover any photo to reveal Venice descriptions and tags; click to pin to the **Curator Tray**.

### 2. Multi-Photo Stitching & Composition Studio
- **4 Stitching Algorithms**:
  - *Poisson Gradient Blend* (Seamless soft transitions)
  - *Voronoi Mosaic* (Algorithmic cellular puzzle)
  - *Depth Multi-Exposure* (Screen / Overlay / Color Dodge layering)
  - *Algorithmic Weave* (Interlocking horizontal/vertical photo strips)
- **Creative Controls**: Seam feathering, chromatic vignette, and real-time film grain noise.
- **10-Second Cinematic Video Generator**: Generates an animated Ken Burns zoom loop with ambient floating particles using client-side canvas capture.

### 3. Base L2 ERC-721 Smart Contract & Minting Pools
- **Pool Categories**:
  - *Pacific Northwest & West Coast Odyssey* (Geospatial, 50 supply, 0.02 ETH, max 2)
  - *Urban Noir & Kinetic Motion* (Atmosphere, 100 supply, 0.015 ETH, max 3)
  - *Chromatic Etherea & Lucid Dreams* (Aesthetics, 75 supply, 0.01 ETH, max 5)
  - *VIP Genesis 1-of-1 Masterworks* (Genesis, 10 supply, 0.08 ETH, max 1)
  - *Public Infinite Mosaic* (Community, 1000 supply, 0.005 ETH, max 10)
- **Dual-Asset NFT Standards**: Every token includes a 4K master composite image, a 10s looping MP4/WebM video, OpenSea/Blur compliant attributes, and deep parent photo provenance.

### 4. Public Live Mints Feed & Lineage Tree
- Real-time gallery of newly minted compositions.
- Mouse-over video loop auto-playback.
- Interactive **Lineage Tree** revealing contributing Flickr photo IDs, original capture dates, Venice AI prompts, and GPS coordinates.
- Social sharing with Twitter/X and Telegram cards.

### 5. Operator Admin Console
- Create new custom pool categories with custom pricing, max supply, and per-wallet limits.
- Pause or activate pools in real time.
- Watchdog telemetry connected directly to `state.db` and Venice Vision pipeline.
- Treasury revenue tracking and withdrawal simulation.

---

## 📁 Project Structure

```
aether-flickr/
├── backend/
│   ├── database.py       # Reads state.db (15,769 photos) & manages aether.db (pools/mints)
│   ├── spatial_math.py   # 3D math for Globe, Cosmos, Torus, and Helix projections
│   ├── main.py           # FastAPI REST API & static asset server
│   └── seed_demo_mint.py # Genesis demo mint seeder
├── static/
│   ├── index.html        # Complete UI (3D Explore, Studio, Mints, Admin)
│   ├── app.js            # Three.js scene, Canvas compositor, video gen, API calls
│   └── style.css         # Cyber-luxe dark glassmorphic styling
├── data/
│   └── aether.db         # Persistent SQLite database for pools, compositions, and mints
├── run_server.py         # Entrypoint script
├── start_server.bat      # Windows one-click launcher
└── start_server.sh       # Linux/WSL launcher
```
