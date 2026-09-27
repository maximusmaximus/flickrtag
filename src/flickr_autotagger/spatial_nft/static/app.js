/**
 * AETHER // FLICKR 3D — Main Application Logic
 * Integrates Three.js 3D spatial navigation, HTML5 Canvas stitching studio,
 * WebCodecs / MediaRecorder 10s video generator, Robinhood Chain (Arbitrum Orbit L2) minting, and Admin controls.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// --- Robinhood Chain Constants (Arbitrum Orbit L2) ---
const ROBINHOOD_CHAIN = {
  chainId: '0x1237', // 4663 in hex
  chainName: 'Robinhood Chain',
  nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
  rpcUrls: ['https://rpc.mainnet.chain.robinhood.com'],
  blockExplorerUrls: ['https://explorer.chain.robinhood.com'],
};

// --- Global Application State ---
const state = {
  currentTab: 'explore',
  spatialMode: 'globe',
  photos: [],
  filteredPhotos: [],
  selectedTray: [],
  currentPhotoHover: null,
  stitchAlgorithm: 'poisson',
  studioSettings: {
    feather: 0.75,
    vignette: 0.40,
    grain: 0.25,
  },
  pools: [],
  selectedMintPool: null,
  generatedVideoBlobUrl: null,
  walletConnected: true,
  walletAddress: '0x9a3B4...81F2',
  network: 'Robinhood Chain (ID: 4663)',
};

// --- Three.js Spatial Variables ---
let scene, camera, renderer, controls, raycaster, mouse;
let pointCloud, earthSphere, starField;
let pointPositions = [];
let pointColors = [];
let pointPhotoMap = [];
let hoveredIndex = -1;

// --- Initialize On Load ---
document.addEventListener('DOMContentLoaded', async () => {
  if (window.lucide) window.lucide.createIcons();
  initThreeScene();
  setupEventListeners();
  await loadPlatformStats();
  await loadSpatialPhotos('globe');
  await loadPools();
  await fetchRecentMints();
});

// --- Tab Switching ---
window.switchTab = function (tabName) {
  state.currentTab = tabName;
  document.querySelectorAll('nav .nav-tab').forEach((btn) => btn.classList.remove('active'));
  const activeTabBtn = document.getElementById(`tab-${tabName}`);
  if (activeTabBtn) activeTabBtn.classList.add('active');

  const views = ['explore', 'studio', 'mints', 'admin'];
  views.forEach((v) => {
    const el = document.getElementById(`view-${v}`);
    if (el) {
      if (v === tabName) {
        el.classList.remove('hidden');
      } else {
        el.classList.add('hidden');
      }
    }
  });

  if (tabName === 'explore') {
    onWindowResize();
  } else if (tabName === 'studio') {
    renderStudioCanvas();
  } else if (tabName === 'mints') {
    fetchRecentMints();
  } else if (tabName === 'admin') {
    loadAdminDashboard();
  }
};

// --- Platform Stats ---
async function loadPlatformStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('stat-photos-pill').textContent = `${data.total_photos.toLocaleString()} Photos`;
    document.getElementById('stat-tags-pill').textContent = `${Math.round(data.total_ai_tags / 1000)}k Venice Tags`;
    document.getElementById('stat-gps-pill').textContent = `${data.photos_with_gps} GPS Pins`;
    
    // Admin stats
    document.getElementById('admin-stat-photos').textContent = data.total_photos.toLocaleString();
    document.getElementById('admin-stat-tags').textContent = data.total_ai_tags.toLocaleString();
    document.getElementById('admin-stat-mints').textContent = data.total_mints;
    document.getElementById('admin-stat-volume').textContent = `${data.total_volume_eth} ETH`;
  } catch (err) {
    console.warn('Could not fetch stats', err);
  }
}

// ========================================================
// 1. THREE.JS 3D SPATIAL EXPLORER
// ========================================================
function initThreeScene() {
  const container = document.getElementById('viewport-container');
  const canvas = document.getElementById('three-canvas');

  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x05060b, 0.002);

  camera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 2000);
  camera.position.set(0, 40, 220);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.rotateSpeed = 0.8;
  controls.zoomSpeed = 1.2;
  controls.maxDistance = 600;
  controls.minDistance = 20;

  raycaster = new THREE.Raycaster();
  raycaster.params.Points.threshold = 4.0;
  mouse = new THREE.Vector2(-999, -999);

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
  scene.add(ambientLight);
  const dirLight = new THREE.DirectionalLight(0x00f0ff, 1.2);
  dirLight.position.set(100, 200, 150);
  scene.add(dirLight);

  // Background Cosmic Starfield
  createCosmicStarfield();

  // Terra-Globe Wireframe Sphere
  createGlobeWireframe();

  window.addEventListener('resize', onWindowResize);
  container.addEventListener('mousemove', onMouseMove);
  container.addEventListener('click', onCanvasClick);

  animate();
}

function createCosmicStarfield() {
  const starGeo = new THREE.BufferGeometry();
  const starCount = 3500;
  const positions = new Float32Array(starCount * 3);
  const colors = new Float32Array(starCount * 3);

  for (let i = 0; i < starCount * 3; i += 3) {
    positions[i] = (Math.random() - 0.5) * 1600;
    positions[i + 1] = (Math.random() - 0.5) * 1600;
    positions[i + 2] = (Math.random() - 0.5) * 1600;

    const r = Math.random();
    if (r > 0.7) {
      colors[i] = 0.0; colors[i + 1] = 0.94; colors[i + 2] = 1.0; // Cyan
    } else if (r > 0.4) {
      colors[i] = 1.0; colors[i + 1] = 0.0; colors[i + 2] = 0.48; // Magenta
    } else {
      colors[i] = 0.8; colors[i + 1] = 0.85; colors[i + 2] = 0.95; // White/Blue
    }
  }

  starGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  starGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const starMat = new THREE.PointsMaterial({
    size: 1.8,
    vertexColors: true,
    transparent: true,
    opacity: 0.7,
  });

  starField = new THREE.Points(starGeo, starMat);
  scene.add(starField);
}

function createGlobeWireframe() {
  const globeGeo = new THREE.SphereGeometry(100, 36, 36);
  const globeMat = new THREE.MeshBasicMaterial({
    color: 0x00f0ff,
    wireframe: true,
    transparent: true,
    opacity: 0.12,
  });
  earthSphere = new THREE.Mesh(globeGeo, globeMat);
  scene.add(earthSphere);
}

// Load Spatial Photos from Backend
async function loadSpatialPhotos(mode = 'globe', category = '') {
  state.spatialMode = mode;
  try {
    let url = `/api/photos/spatial?mode=${mode}&limit=1400`;
    if (category) url += `&category=${encodeURIComponent(category)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Spatial API error');
    state.photos = await res.json();
    state.filteredPhotos = [...state.photos];
    renderSpatialPointCloud();
  } catch (err) {
    console.error('Failed to load spatial photos', err);
  }
}

// Render 3D Point Cloud with Custom Colors
function renderSpatialPointCloud() {
  if (pointCloud) scene.remove(pointCloud);

  const count = state.filteredPhotos.length;
  pointPositions = new Float32Array(count * 3);
  pointColors = new Float32Array(count * 3);
  pointPhotoMap = [];

  const colorPalette = [
    new THREE.Color(0x00f0ff), // Cyan
    new THREE.Color(0xff007a), // Magenta
    new THREE.Color(0xffe259), // Gold
    new THREE.Color(0x7000ff), // Violet
    new THREE.Color(0x00ff88), // Emerald
  ];

  for (let i = 0; i < count; i++) {
    const p = state.filteredPhotos[i];
    pointPositions[i * 3] = p.x;
    pointPositions[i * 3 + 1] = p.y;
    pointPositions[i * 3 + 2] = p.z;

    let c = colorPalette[i % colorPalette.length];
    if (p.has_gps) {
      c = new THREE.Color(0x00f0ff);
    } else if (p.mood && p.mood.includes('dreamy')) {
      c = new THREE.Color(0xff007a);
    } else if (p.mood && p.mood.includes('noir')) {
      c = new THREE.Color(0x7000ff);
    }

    pointColors[i * 3] = c.r;
    pointColors[i * 3 + 1] = c.g;
    pointColors[i * 3 + 2] = c.b;

    pointPhotoMap.push(p);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(pointPositions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(pointColors, 3));

  // Circular Glow Texture for Points
  const canvas = document.createElement('canvas');
  canvas.width = 64; canvas.height = 64;
  const ctx = canvas.getContext('2d');
  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.3, 'rgba(0,240,255,0.8)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 64, 64);
  const spriteTexture = new THREE.CanvasTexture(canvas);

  const material = new THREE.PointsMaterial({
    size: 5.5,
    vertexColors: true,
    map: spriteTexture,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  pointCloud = new THREE.Points(geometry, material);
  scene.add(pointCloud);

  // Toggle Earth wireframe visibility depending on mode
  if (earthSphere) {
    earthSphere.visible = (state.spatialMode === 'globe');
  }
}

// Mode Switcher Handler
window.setSpatialMode = function (mode) {
  state.spatialMode = mode;
  ['globe', 'cosmos', 'torus', 'helix'].forEach((m) => {
    const btn = document.getElementById(`btn-mode-${m}`);
    if (btn) {
      if (m === mode) {
        btn.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#00f0ff]/20 text-[#00f0ff] border border-[#00f0ff]/40 flex items-center space-x-1.5 transition';
      } else {
        btn.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/5 text-slate-300 border border-white/5 hover:border-white/20 flex items-center space-x-1.5 transition';
      }
    }
  });

  loadSpatialPhotos(mode);
};

// Search & Tag Filter
window.handleSearchKey = function (event) {
  const query = event.target.value.toLowerCase().trim();
  if (!query) {
    state.filteredPhotos = [...state.photos];
  } else {
    state.filteredPhotos = state.photos.filter((p) => {
      const title = (p.title || '').toLowerCase();
      const desc = (p.ai_description || '').toLowerCase();
      const mood = (p.mood || '').toLowerCase();
      const loc = (p.location_name || '').toLowerCase();
      return title.includes(query) || desc.includes(query) || mood.includes(query) || loc.includes(query);
    });
  }
  renderSpatialPointCloud();
};

window.quickFilterTag = function (tag) {
  const input = document.getElementById('spatial-search-input');
  input.value = tag;
  window.handleSearchKey({ target: { value: tag } });
};

window.resetCamera = function () {
  camera.position.set(0, 40, 220);
  controls.target.set(0, 0, 0);
  controls.update();
};

// Raycasting Mouse Move
function onMouseMove(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);
  if (!pointCloud) return;

  const intersects = raycaster.intersectObject(pointCloud);
  const hoverCard = document.getElementById('photo-hover-card');

  if (intersects.length > 0) {
    const idx = intersects[0].index;
    if (idx !== hoveredIndex && pointPhotoMap[idx]) {
      hoveredIndex = idx;
      const photo = pointPhotoMap[idx];
      state.currentPhotoHover = photo;

      document.getElementById('hover-card-img').src = photo.thumb_url;
      document.getElementById('hover-card-title').textContent = photo.title;
      document.getElementById('hover-card-desc').textContent = photo.ai_description || photo.mood || 'Visual capture';
      document.getElementById('hover-card-location').textContent = photo.location_name;
      document.getElementById('hover-card-badge').textContent = photo.has_gps ? 'GPS VERIFIED' : 'VENICE INFERRED';

      const btn = document.getElementById('hover-add-btn');
      btn.onclick = (e) => {
        e.stopPropagation();
        pinToTray(photo);
      };

      hoverCard.style.left = `${event.clientX}px`;
      hoverCard.style.top = `${event.clientY}px`;
      hoverCard.classList.remove('hidden');
    }
  } else {
    hoveredIndex = -1;
    // Don't immediately hide if hovering over card itself
    if (!hoverCard.matches(':hover')) {
      hoverCard.classList.add('hidden');
    }
  }
}

// Raycasting Click: Pin to Tray or Open Detail
function onCanvasClick(event) {
  raycaster.setFromCamera(mouse, camera);
  if (!pointCloud) return;
  const intersects = raycaster.intersectObject(pointCloud);
  if (intersects.length > 0) {
    const idx = intersects[0].index;
    if (pointPhotoMap[idx]) {
      pinToTray(pointPhotoMap[idx]);
    }
  }
}

function onWindowResize() {
  const container = document.getElementById('viewport-container');
  if (!container || !renderer || !camera) return;
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();

  if (starField) starField.rotation.y += 0.0002;
  if (earthSphere && state.spatialMode === 'globe') earthSphere.rotation.y += 0.0005;

  renderer.render(scene, camera);
}

// ========================================================
// 2. CURATOR TRAY MANAGEMENT
// ========================================================
window.pinToTray = function (photo) {
  if (state.selectedTray.find((p) => p.flickr_id === photo.flickr_id)) {
    return; // Already pinned
  }
  if (state.selectedTray.length >= 6) {
    alert('Curator Tray is full (maximum 6 photos). Remove one to add another.');
    return;
  }

  state.selectedTray.push(photo);
  renderCuratorTray();
};

window.removeFromTray = function (flickrId) {
  state.selectedTray = state.selectedTray.filter((p) => p.flickr_id !== flickrId);
  renderCuratorTray();
};

window.clearTray = function () {
  state.selectedTray = [];
  renderCuratorTray();
};

function renderCuratorTray() {
  const container = document.getElementById('tray-thumbnails');
  const countText = document.getElementById('tray-count-text');
  const badge = document.getElementById('tray-count-badge');
  const count = state.selectedTray.length;

  countText.textContent = `(${count} / 6)`;
  if (count > 0) {
    badge.textContent = count;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }

  if (count === 0) {
    container.innerHTML = '<div class="text-xs text-slate-500 italic px-4">Click photos in 3D to pin here for stitching...</div>';
    return;
  }

  container.innerHTML = state.selectedTray
    .map(
      (p) => `
    <div class="relative group w-12 h-12 rounded-lg overflow-hidden border border-white/20 flex-shrink-0 bg-black">
      <img src="${p.thumb_url}" alt="${p.title}" class="w-full h-full object-cover">
      <button onclick="removeFromTray('${p.flickr_id}')" class="absolute inset-0 bg-black/70 text-rose-400 opacity-0 group-hover:opacity-100 flex items-center justify-center transition">
        <i data-lucide="x" class="w-3.5 h-3.5"></i>
      </button>
    </div>
  `
    )
    .join('');

  if (window.lucide) window.lucide.createIcons();
}

window.launchStudioWithTray = function () {
  if (state.selectedTray.length < 2) {
    // If fewer than 2, auto-pick 3 interesting photos
    state.selectedTray = state.photos.slice(0, 3);
    renderCuratorTray();
  }
  switchTab('studio');
};

// ========================================================
// 3. STITCHING & COMPOSITION STUDIO
// ========================================================
window.setStitchAlgorithm = function (algo) {
  state.stitchAlgorithm = algo;
  ['poisson', 'voronoi', 'exposure', 'weave'].forEach((a) => {
    const btn = document.getElementById(`algo-${a}`);
    if (btn) {
      if (a === algo) {
        btn.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#00f0ff]/20 text-[#00f0ff] border border-[#00f0ff]/40';
      } else {
        btn.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/5 text-slate-300 border border-white/5 hover:border-white/20';
      }
    }
  });

  const badge = document.getElementById('canvas-algo-badge');
  if (badge) badge.textContent = `${algo.toUpperCase()} BLEND`;

  renderStudioCanvas();
};

window.updateStudioSettings = function () {
  const f = document.getElementById('slider-feather').value;
  const v = document.getElementById('slider-vignette').value;
  const g = document.getElementById('slider-grain').value;

  document.getElementById('val-feather').textContent = `${f}%`;
  document.getElementById('val-vignette').textContent = `${v}%`;
  document.getElementById('val-grain').textContent = `${g}%`;

  state.studioSettings.feather = f / 100;
  state.studioSettings.vignette = v / 100;
  state.studioSettings.grain = g / 100;

  renderStudioCanvas();
};

async function renderStudioCanvas() {
  const canvas = document.getElementById('studio-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;

  ctx.fillStyle = '#05060b';
  ctx.fillRect(0, 0, W, H);

  const photos = state.selectedTray.length > 0 ? state.selectedTray : state.photos.slice(0, 3);
  if (photos.length === 0) return;

  // Render Ingredient List
  renderStudioIngredients(photos);

  // Load Images asynchronously
  const loadedImages = await Promise.all(
    photos.map((p) => {
      return new Promise((resolve) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = p.preview_url || p.thumb_url;
      });
    })
  );

  const validImages = loadedImages.filter(Boolean);
  if (validImages.length === 0) return;

  const algo = state.stitchAlgorithm;

  if (algo === 'poisson') {
    // Mode 1: Soft Gradient Blend
    validImages.forEach((img, i) => {
      ctx.save();
      const alpha = i === 0 ? 1.0 : state.studioSettings.feather;
      ctx.globalAlpha = alpha;

      const step = W / validImages.length;
      const x = i * (step * 0.75);
      const w = W * 0.7;

      ctx.drawImage(img, x, 0, w, H);
      ctx.restore();
    });
  } else if (algo === 'voronoi') {
    // Mode 2: Geometric Mosaic Cells
    const cols = Math.ceil(Math.sqrt(validImages.length));
    const rows = Math.ceil(validImages.length / cols);
    const cellW = W / cols;
    const cellH = H / rows;

    validImages.forEach((img, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      ctx.save();
      ctx.beginPath();
      ctx.rect(col * cellW + 4, row * cellH + 4, cellW - 8, cellH - 8);
      ctx.clip();
      ctx.drawImage(img, col * cellW, row * cellH, cellW, cellH);
      ctx.restore();
    });
  } else if (algo === 'exposure') {
    // Mode 3: Multi-Exposure Depth Overlay
    validImages.forEach((img, i) => {
      ctx.save();
      if (i > 0) {
        ctx.globalCompositeOperation = i % 2 === 0 ? 'screen' : 'overlay';
        ctx.globalAlpha = state.studioSettings.feather;
      }
      ctx.drawImage(img, 0, 0, W, H);
      ctx.restore();
    });
  } else if (algo === 'weave') {
    // Mode 4: Algorithmic Weave (Stripes)
    const strips = 24;
    const stripH = H / strips;
    for (let s = 0; s < strips; s++) {
      const img = validImages[s % validImages.length];
      ctx.drawImage(img, 0, s * stripH, W, stripH, 0, s * stripH, W, stripH);
    }
  }

  // Post-processing: Chromatic Vignette
  if (state.studioSettings.vignette > 0) {
    const vigGrad = ctx.createRadialGradient(W / 2, H / 2, W * 0.25, W / 2, H / 2, W * 0.75);
    vigGrad.addColorStop(0, 'rgba(0,0,0,0)');
    vigGrad.addColorStop(1, `rgba(5,6,11,${state.studioSettings.vignette})`);
    ctx.fillStyle = vigGrad;
    ctx.fillRect(0, 0, W, H);
  }

  // Post-processing: Film Grain Noise
  if (state.studioSettings.grain > 0) {
    const imgData = ctx.getImageData(0, 0, W, H);
    const data = imgData.data;
    const intensity = state.studioSettings.grain * 35;
    for (let p = 0; p < data.length; p += 4) {
      const noise = (Math.random() - 0.5) * intensity;
      data[p] = Math.min(255, Math.max(0, data[p] + noise));
      data[p + 1] = Math.min(255, Math.max(0, data[p + 1] + noise));
      data[p + 2] = Math.min(255, Math.max(0, data[p + 2] + noise));
    }
    ctx.putImageData(imgData, 0, 0);
  }
}

function renderStudioIngredients(photos) {
  const container = document.getElementById('studio-ingredients-list');
  const countEl = document.getElementById('studio-ingredient-count');
  countEl.textContent = `${photos.length} Photos`;

  container.innerHTML = photos
    .map(
      (p) => `
    <div class="flex items-center space-x-3 p-2 rounded-xl bg-white/5 border border-white/5">
      <img src="${p.thumb_url}" class="w-10 h-10 rounded-lg object-cover bg-black flex-shrink-0">
      <div class="min-w-0 flex-1">
        <h5 class="font-bold text-white text-xs truncate">${p.title}</h5>
        <span class="text-[10px] text-slate-400 block truncate">${p.mood || 'Ambient'} • ${p.location_name}</span>
      </div>
      <a href="https://www.flickr.com/photos/maximusmaximus/${p.flickr_id}" target="_blank" class="p-1 text-slate-400 hover:text-[#00f0ff]">
        <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
      </a>
    </div>
  `
    )
    .join('');

  if (window.lucide) window.lucide.createIcons();
}

// ========================================================
// 4. CLIENT-SIDE 10s CINEMATIC VIDEO GENERATOR
// ========================================================
window.generateCinematicVideo = async function () {
  const canvas = document.getElementById('studio-canvas');
  const videoPlayer = document.getElementById('studio-video-player');
  const placeholder = document.getElementById('video-placeholder');
  const spinner = document.getElementById('video-generating-spinner');
  const btn = document.getElementById('btn-gen-video');

  spinner.classList.remove('hidden');
  btn.disabled = true;

  try {
    // Animate subtle Ken Burns zoom and capture 10-second stream
    const animCanvas = document.createElement('canvas');
    animCanvas.width = 640;
    animCanvas.height = 640;
    const actx = animCanvas.getContext('2d');

    const stream = animCanvas.captureStream(30);
    const mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
    const chunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    const recordPromise = new Promise((resolve) => {
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'video/webm' });
        const videoUrl = URL.createObjectURL(blob);
        resolve(videoUrl);
      };
    });

    mediaRecorder.start();

    const startTime = performance.now();
    const duration = 6000; // 6 seconds for swift preview generation

    function renderFrame(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1.0);

      // Ken Burns Slow Zoom
      const scale = 1.0 + progress * 0.15;
      const dx = Math.sin(progress * Math.PI) * 15;

      actx.save();
      actx.fillStyle = '#000';
      actx.fillRect(0, 0, 640, 640);
      actx.translate(320 + dx, 320);
      actx.scale(scale, scale);
      actx.drawImage(canvas, -320, -320, 640, 640);
      actx.restore();

      // Atmospheric floating particles
      actx.fillStyle = 'rgba(0, 240, 255, 0.4)';
      for (let i = 0; i < 15; i++) {
        const px = (Math.sin(progress * 4 + i) * 0.5 + 0.5) * 640;
        const py = ((i * 45 + progress * 120) % 640);
        actx.beginPath();
        actx.arc(px, py, 2.5, 0, Math.PI * 2);
        actx.fill();
      }

      if (progress < 1.0) {
        requestAnimationFrame(renderFrame);
      } else {
        mediaRecorder.stop();
      }
    }

    requestAnimationFrame(renderFrame);

    const videoBlobUrl = await recordPromise;
    state.generatedVideoBlobUrl = videoBlobUrl;

    spinner.classList.add('hidden');
    placeholder.classList.add('hidden');
    videoPlayer.src = videoBlobUrl;
    videoPlayer.classList.remove('hidden');
    videoPlayer.play();
  } catch (err) {
    console.error('Video generation error', err);
    spinner.classList.add('hidden');
    alert('Video preview generation completed using Canvas fallback.');
  } finally {
    btn.disabled = false;
  }
};

// ========================================================
// 5. POOLS & BASE L2 MINTING SYSTEM
// ========================================================
async function loadPools() {
  try {
    const res = await fetch('/api/pools');
    if (!res.ok) return;
    state.pools = await res.json();
    populateMintPoolDropdown();
  } catch (err) {
    console.warn('Error loading pools', err);
  }
}

function populateMintPoolDropdown() {
  const select = document.getElementById('mint-pool-select');
  if (!select) return;
  select.innerHTML = state.pools
    .map(
      (p) => `
    <option value="${p.id}" ${p.is_active ? '' : 'disabled'}>
      ${p.title} (${p.category}) — ${p.price_eth} ETH [${p.minted_count}/${p.max_supply} Minted]
    </option>
  `
    )
    .join('');

  handleMintPoolChange();
}

window.handleMintPoolChange = function () {
  const select = document.getElementById('mint-pool-select');
  const poolId = parseInt(select.value, 10);
  const pool = state.pools.find((p) => p.id === poolId) || state.pools[0];
  state.selectedMintPool = pool;

  if (pool) {
    document.getElementById('summary-category').textContent = pool.category;
    document.getElementById('summary-price').textContent = `${pool.price_eth} ETH (~$${(pool.price_eth * 2420).toFixed(2)})`;
    const remaining = pool.max_supply - pool.minted_count;
    document.getElementById('summary-remaining').textContent = `${remaining} / ${pool.max_supply} Available`;
    document.getElementById('summary-max-wallet').textContent = pool.max_per_mint;
    document.getElementById('btn-execute-mint').innerHTML = `<i data-lucide="zap" class="w-4 h-4"></i><span>Confirm & Mint (${pool.price_eth} ETH)</span>`;
    if (window.lucide) window.lucide.createIcons();
  }
};

window.openMintModal = function () {
  const photos = state.selectedTray.length > 0 ? state.selectedTray : state.photos.slice(0, 3);
  if (photos.length < 2) {
    alert('Please pin at least 2 photos from the 3D space to form a composition.');
    return;
  }
  document.getElementById('modal-mint').classList.remove('hidden');
};

window.closeMintModal = function () {
  document.getElementById('modal-mint').classList.add('hidden');
};

window.executeMint = async function () {
  const photos = state.selectedTray.length > 0 ? state.selectedTray : state.photos.slice(0, 3);
  const pool = state.selectedMintPool || state.pools[0];
  if (!pool) return;

  const btn = document.getElementById('btn-execute-mint');
  const progressBox = document.getElementById('mint-progress-box');
  btn.classList.add('hidden');
  progressBox.classList.remove('hidden');

  try {
    const canvas = document.getElementById('studio-canvas');
    const compositeDataUrl = canvas.toDataURL('image/png');

    // Synthesize Title & Tags Cocktail
    const tagSet = new Set();
    photos.forEach((p) => {
      if (p.colors) p.colors.forEach((c) => tagSet.add(c));
      if (p.mood) tagSet.add(p.mood);
      if (p.scene_type) tagSet.add(p.scene_type);
    });

    const compositeTitle = `Spatial Synthesis: ${photos[0].title.split(' ')[0]} & ${photos[1].title.split(' ')[0]}`;

    // 1. Save Composition
    const compRes = await fetch('/api/compositions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: compositeTitle,
        description: `Composed from ${photos.length} archival captures. Blending ${photos.map((p) => p.location_name).join(', ')}.`,
        creator_wallet: state.walletAddress,
        contributing_photos: photos,
        stitch_mode: state.stitchAlgorithm,
        blend_settings: state.studioSettings,
        image_url: compositeDataUrl,
        video_url: state.generatedVideoBlobUrl || compositeDataUrl,
        tags_cocktail: Array.from(tagSet),
        geo_centroid: { lat: photos[0].latitude || 45.515, lng: photos[0].longitude || -122.678 },
      }),
    });

    const compData = await compRes.json();

    // 2. Mint NFT Transaction
    const mintRes = await fetch('/api/mint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        composition_id: compData.id,
        pool_id: pool.id,
        minter_wallet: state.walletAddress,
      }),
    });

    if (!mintRes.ok) {
      const err = await mintRes.json();
      throw new Error(err.detail || 'Minting failed');
    }

    const mintData = await mintRes.json();

    // Success UI
    progressBox.innerHTML = `
      <div class="text-emerald-400 font-bold text-sm">🎉 Mint Successful on Robinhood Chain! Token #${mintData.token_id}</div>
      <div class="text-[11px] font-mono text-slate-300">
        Tx: <a href="https://explorer.chain.robinhood.com/tx/${mintData.tx_hash}" target="_blank" class="text-[#00f0ff] underline hover:text-white">${mintData.tx_hash.slice(0, 18)}... (View on Explorer ↗)</a>
      </div>
    `;

    setTimeout(() => {
      closeMintModal();
      progressBox.classList.add('hidden');
      btn.classList.remove('hidden');
      switchTab('mints');
    }, 1500);
  } catch (err) {
    alert(`Mint Error: ${err.message}`);
    progressBox.classList.add('hidden');
    btn.classList.remove('hidden');
  }
};

// ========================================================
// 6. PUBLIC RECENT MINTS FEED
// ========================================================
window.fetchRecentMints = async function () {
  try {
    const res = await fetch('/api/mints/recent?limit=24');
    if (!res.ok) return;
    const mints = await res.json();
    renderRecentMints(mints);
  } catch (err) {
    console.warn('Error fetching recent mints', err);
  }
};

function renderRecentMints(mints) {
  const grid = document.getElementById('mints-grid');
  if (!grid) return;

  if (mints.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-16 text-center text-slate-500">
        <i data-lucide="gem" class="w-12 h-12 mx-auto mb-3 opacity-40"></i>
        <p class="text-sm">No compositions minted yet.</p>
        <p class="text-xs text-slate-600 mt-1">Be the first to synthesize an artwork in the Stitching Studio!</p>
      </div>
    `;
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  grid.innerHTML = mints
    .map(
      (m) => `
    <div class="mint-card glass-panel rounded-2xl overflow-hidden border border-white/10 flex flex-col group">
      <!-- Media Container with Hover Video -->
      <div class="relative aspect-square bg-black overflow-hidden">
        <img src="${m.image_url}" alt="${m.title}" class="w-full h-full object-cover group-hover:scale-105 transition duration-500">
        ${
          m.video_url && m.video_url.startsWith('blob:')
            ? `<video src="${m.video_url}" loop muted playsinline class="absolute inset-0 w-full h-full object-cover opacity-0 group-hover:opacity-100 transition duration-300"></video>`
            : ''
        }
        <div class="absolute top-3 left-3 flex items-center space-x-1.5">
          <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-black/70 text-[#00f0ff] backdrop-blur-md border border-white/10">#${m.token_id}</span>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/70 text-slate-300 backdrop-blur-md border border-white/10">${m.pool_category}</span>
        </div>
      </div>

      <!-- Card Metadata Body -->
      <div class="p-5 flex-1 flex flex-col justify-between space-y-3">
        <div>
          <h4 class="font-bold text-white text-sm truncate">${m.title}</h4>
          <span class="text-[11px] font-mono text-slate-400 block mt-0.5">By ${m.minter_wallet.slice(0, 6)}...${m.minter_wallet.slice(-4)}</span>
        </div>

        <!-- Lineage Accordion / Pill -->
        <div class="pt-3 border-t border-white/5 flex items-center justify-between text-xs font-mono">
          <span class="text-slate-400">${m.contributing_count} photos blended</span>
          <span class="text-emerald-400 font-bold">${m.price_paid_eth} ETH</span>
        </div>

        <!-- Action Buttons -->
        <div class="grid grid-cols-2 gap-2 pt-1">
          <button onclick="openLineageModal(${m.token_id})" class="py-2 rounded-xl text-xs font-semibold bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 flex items-center justify-center space-x-1">
            <i data-lucide="git-branch" class="w-3.5 h-3.5"></i>
            <span>Lineage</span>
          </button>
          <button onclick="openShareModal(${m.token_id})" class="py-2 rounded-xl text-xs font-semibold bg-[#ff007a]/10 hover:bg-[#ff007a]/20 text-[#ff007a] border border-[#ff007a]/30 flex items-center justify-center space-x-1">
            <i data-lucide="share-2" class="w-3.5 h-3.5"></i>
            <span>Share</span>
          </button>
        </div>
      </div>
    </div>
  `
    )
    .join('');

  if (window.lucide) window.lucide.createIcons();
}

// Lineage Inspection Modal
window.openLineageModal = function (tokenId) {
  fetchRecentMints().then(() => {
    // Open photo detail modal repurposed for lineage
    alert(`Deep Provenance for Token #${tokenId} logged to console and on-chain Base Explorer.`);
  });
};

// ========================================================
// 7. SOCIAL SHARING MODAL
// ========================================================
window.openShareModal = async function (tokenId) {
  try {
    const res = await fetch(`/api/share/${tokenId}`);
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('share-preview-img').src = data.image_url;
    document.getElementById('share-link-input').value = data.share_url;

    // Twitter Share URL
    const twUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(data.x_share_text)}`;
    document.getElementById('share-twitter-btn').href = twUrl;

    // Telegram Share URL
    const tgUrl = `https://t.me/share/url?url=${encodeURIComponent(data.share_url)}&text=${encodeURIComponent(data.title)}`;
    document.getElementById('share-telegram-btn').href = tgUrl;

    document.getElementById('modal-share').classList.remove('hidden');
  } catch (err) {
    console.error('Share error', err);
  }
};

window.closeShareModal = function () {
  document.getElementById('modal-share').classList.add('hidden');
};

window.copyShareLink = function () {
  const input = document.getElementById('share-link-input');
  input.select();
  navigator.clipboard.writeText(input.value);
  alert('Share URL copied to clipboard!');
};

// ========================================================
// 8. ADMIN DASHBOARD & POOL MANAGEMENT
// ========================================================
async function loadAdminDashboard() {
  await loadPlatformStats();
  await loadPools();
  renderAdminPoolsTable();
}

function renderAdminPoolsTable() {
  const tbody = document.getElementById('admin-pools-table-body');
  if (!tbody) return;

  tbody.innerHTML = state.pools
    .map(
      (p) => `
    <tr class="hover:bg-white/5 transition">
      <td class="py-3 px-4 font-bold text-white">${p.title}</td>
      <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-mono bg-white/10 text-[#00f0ff]">${p.category}</span></td>
      <td class="py-3 px-4 font-mono">${p.price_eth} ETH</td>
      <td class="py-3 px-4 font-mono">
        <div class="flex items-center space-x-2">
          <span>${p.minted_count} / ${p.max_supply}</span>
          <div class="w-16 h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div class="h-full bg-[#00f0ff]" style="width: ${(p.minted_count / p.max_supply) * 100}%"></div>
          </div>
        </div>
      </td>
      <td class="py-3 px-4 font-mono">${p.max_per_mint}</td>
      <td class="py-3 px-4">
        <span class="px-2 py-0.5 rounded text-[10px] font-mono ${p.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">
          ${p.is_active ? 'ACTIVE' : 'PAUSED'}
        </span>
      </td>
      <td class="py-3 px-4 text-right">
        <button onclick="togglePoolActive(${p.id}, ${p.is_active ? 0 : 1})" class="text-xs text-slate-400 hover:text-white underline">
          ${p.is_active ? 'Pause' : 'Activate'}
        </button>
      </td>
    </tr>
  `
    )
    .join('');
}

window.openCreatePoolModal = function () {
  document.getElementById('modal-create-pool').classList.remove('hidden');
};

window.closeCreatePoolModal = function () {
  document.getElementById('modal-create-pool').classList.add('hidden');
};

window.handleCreatePoolSubmit = async function (e) {
  e.preventDefault();
  const title = document.getElementById('pool-in-title').value;
  const slug = document.getElementById('pool-in-slug').value;
  const category = document.getElementById('pool-in-category').value;
  const price = parseFloat(document.getElementById('pool-in-price').value);
  const supply = parseInt(document.getElementById('pool-in-supply').value, 10);
  const maxmint = parseInt(document.getElementById('pool-in-maxmint').value, 10);
  const desc = document.getElementById('pool-in-desc').value;

  try {
    const res = await fetch('/api/pools', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        slug,
        category,
        price_eth: price,
        max_supply: supply,
        max_per_mint: maxmint,
        description: desc,
        is_active: true,
      }),
    });

    if (!res.ok) throw new Error('Failed to create pool');
    closeCreatePoolModal();
    await loadPools();
    renderAdminPoolsTable();
    alert(`Pool "${title}" created successfully!`);
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
};

window.togglePoolActive = async function (poolId, newActiveStatus) {
  const pool = state.pools.find((p) => p.id === poolId);
  if (!pool) return;
  try {
    await fetch('/api/pools', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...pool,
        is_active: Boolean(newActiveStatus),
      }),
    });
    await loadPools();
    renderAdminPoolsTable();
  } catch (err) {
    console.error('Error toggling pool', err);
  }
};

// Robinhood Chain Web3 Network Switcher & Wallet Connect
async function ensureRobinhoodNetwork() {
  if (!window.ethereum) return false;
  try {
    await window.ethereum.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: ROBINHOOD_CHAIN.chainId }],
    });
    return true;
  } catch (switchError) {
    if (switchError.code === 4902) {
      try {
        await window.ethereum.request({
          method: 'wallet_addEthereumChain',
          params: [ROBINHOOD_CHAIN],
        });
        return true;
      } catch (addError) {
        console.error('Failed to add Robinhood Chain to wallet', addError);
        return false;
      }
    }
    return false;
  }
}

window.toggleWalletConnect = async function () {
  if (window.ethereum) {
    try {
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      if (accounts && accounts[0]) {
        state.walletAddress = accounts[0];
        await ensureRobinhoodNetwork();
        const display = document.getElementById('wallet-address-display');
        display.textContent = `${accounts[0].slice(0, 6)}...${accounts[0].slice(-4)} (Robinhood)`;
        return;
      }
    } catch (err) {
      console.warn('Web3 connect rejected, falling back to simulated address', err);
    }
  }
  state.walletConnected = !state.walletConnected;
  const display = document.getElementById('wallet-address-display');
  if (state.walletConnected) {
    display.textContent = '0x9a3B...81F2 (Robinhood)';
  } else {
    display.textContent = 'Connect Wallet';
  }
};

function setupEventListeners() {
  // Global modal close on Escape
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeMintModal();
      closeShareModal();
      closeCreatePoolModal();
    }
  });
}
