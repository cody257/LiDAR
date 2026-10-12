/* lidar-arch — terrain prototype.
   Box -> USGS TNM lookup of 1 m DEM tiles -> range-read just the needed blocks of
   each Cloud-Optimized GeoTIFF from USGS S3 -> compute products in the browser ->
   overlay pinned to the raster's own UTM corners. No server work at all. */

"use strict";

const TNM = "https://tnmaccess.nationalmap.gov/api/v1/products";
const DATASET = "Digital Elevation Model (DEM) 1 meter";
const MAX_CELLS = 4e6;     // output grid budget; bigger boxes use a coarser overview
const FETCH_CONCURRENCY = 4; // COG windows decoded at once (bounds peak memory)
const MAX_SIDE = 4096;     // stay under common WebGL texture limits
const LRM_RADIUS_M = 15;   // matches viz.lrm kernel_radius_m

const PRODUCTS = [
  { key: "lrm", label: "LRM" },
  { key: "hillshade", label: "Hillshade" },
  { key: "slope", label: "Slope" },
];
const EMPTY = { type: "FeatureCollection", features: [] };

// `grid` holds the last loaded DEM; products are recomputed from it on toggle.
const state = { bbox: null, loading: false, grid: null, product: "lrm", opacity: 0.85,
                timings: null, sources: [], error: null, imageUrl: null, lrmStretch: null };

// ---------------- map ----------------
const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [-98.5, 39.5],
  zoom: 3.4,
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

let mapReady = false;
map.on("load", () => {
  map.addSource("draw", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "draw-line", type: "line", source: "draw",
    paint: { "line-color": "#b8552e", "line-width": 2 } });
  mapReady = true;
  if (state.bbox) redrawBox(state.bbox);
  if (state.grid) showImage(buildProduct(state.product));
});

// ---------------- draw + inputs ----------------
let drawing = false, start = null;
const drawBtn = document.getElementById("draw-btn");
drawBtn.addEventListener("click", () => (drawing ? exitDraw() : enterDraw()));

function enterDraw() {
  if (!mapReady) return;
  drawing = true;
  drawBtn.classList.add("active");
  drawBtn.textContent = "Drag on the map…";
  map.dragPan.disable();
  map.getCanvas().style.cursor = "crosshair";
}
function exitDraw() {
  drawing = false; start = null;
  drawBtn.classList.remove("active");
  drawBtn.textContent = "Draw box on map";
  map.dragPan.enable();
  map.getCanvas().style.cursor = "";
}
function boxFrom(a, b) {
  return [Math.min(a.lng, b.lng), Math.min(a.lat, b.lat), Math.max(a.lng, b.lng), Math.max(a.lat, b.lat)];
}
function boxGeoJSON(b) {
  const [w, s, e, n] = b;
  return { type: "Feature", geometry: { type: "Polygon",
    coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } };
}
function redrawBox(b) {
  if (mapReady) map.getSource("draw").setData(boxGeoJSON(b));
}
map.on("mousedown", (e) => { if (drawing) start = e.lngLat; });
map.on("mousemove", (e) => { if (drawing && start) redrawBox(boxFrom(start, e.lngLat)); });
map.on("mouseup", (e) => {
  if (!drawing || !start) return;
  const b = boxFrom(start, e.lngLat);
  exitDraw();
  setBbox(b);
});

const inIds = ["in-w", "in-s", "in-e", "in-n"];
inIds.forEach((id) => document.getElementById(id).addEventListener("change", () => {
  const v = inIds.map((i) => parseFloat(document.getElementById(i).value));
  if (v.some(Number.isNaN)) return;
  setBbox([Math.min(v[0], v[2]), Math.min(v[1], v[3]), Math.max(v[0], v[2]), Math.max(v[1], v[3])]);
}));

function setBbox(b) {
  state.bbox = b;
  b.forEach((x, i) => { document.getElementById(inIds[i]).value = x.toFixed(4); });
  redrawBox(b);
  history.replaceState(null, "", `?bbox=${b.map((x) => x.toFixed(5)).join(",")}`);
  render();
}

// ---------------- load pipeline ----------------
function utmDef(zone) {
  return `+proj=utm +zone=${zone} +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs`;
}

async function loadTerrain() {
  if (state.loading || !state.bbox) return;
  state.loading = true; state.error = null; render();
  const t = {};
  const t0 = performance.now();
  try {
    const bbox = state.bbox;
    const zone = Math.floor(((bbox[0] + bbox[2]) / 2 + 180) / 6) + 1;
    const def = utmDef(zone);

    // 1) which 1 m DEM tiles cover the box (newest publication first)
    const q = new URLSearchParams({ bbox: bbox.join(","), datasets: DATASET,
      prodFormats: "GeoTIFF", max: "200", outputFormat: "JSON" });
    const res = await fetch(`${TNM}?${q}`);
    if (!res.ok) throw new Error(`USGS lookup failed (HTTP ${res.status}).`);
    const items = ((await res.json()).items || [])
      .map((it) => ({ it, m: it.downloadURL.match(/USGS_1M_(\d+)_x\d+y\d+_/) }))
      .filter((x) => x.m && +x.m[1] === zone)   // prototype: centre zone only
      .map((x) => x.it)
      .sort((a, b) => (b.publicationDate || "").localeCompare(a.publicationDate || ""));
    t.lookup = performance.now() - t0;
    if (!items.length) throw new Error("No USGS 1 m bare-earth DEM covers this box (in its centre UTM zone).");

    // 2) output grid in UTM: the box's projected extent at a power-of-two resolution
    const xs = [], ys = [];
    for (let i = 0; i <= 20; i++) {
      const lon = bbox[0] + (bbox[2] - bbox[0]) * i / 20, lat = bbox[1] + (bbox[3] - bbox[1]) * i / 20;
      for (const p of [[lon, bbox[1]], [lon, bbox[3]], [bbox[0], lat], [bbox[2], lat]]) {
        const [x, y] = proj4("EPSG:4326", def, p); xs.push(x); ys.push(y);
      }
    }
    const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
    let res_m = 1;
    while ((maxx - minx) * (maxy - miny) / (res_m * res_m) > MAX_CELLS ||
           Math.max(maxx - minx, maxy - miny) / res_m > MAX_SIDE) res_m *= 2;
    const W = Math.ceil((maxx - minx) / res_m), H = Math.ceil((maxy - miny) / res_m);
    const x0 = minx, top = maxy;
    const dem = new Float32Array(W * H).fill(NaN);

    // 3) read tile windows newest-first, a few at a time, filling as each batch lands;
    //    stop as soon as every cell has data so older overlapping projects aren't fetched.
    const t1 = performance.now();
    const used = new Map();
    let filled = 0, decoded = 0, tilesRead = 0;
    for (let k = 0; k < items.length && filled < W * H; k += FETCH_CONCURRENCY) {
      const batch = items.slice(k, k + FETCH_CONCURRENCY);
      const wins = await Promise.all(batch.map((it) => readWindow(it.downloadURL, x0, top, W, H, res_m)));
      wins.forEach((win, j) => {
        if (!win) return;
        tilesRead++;
        decoded += win.data.byteLength;
        const n = fillFrom(dem, W, H, x0, top, res_m, win);
        if (n) {
          filled += n;
          const p = batch[j].downloadURL.split("/Projects/")[1].split("/")[0];
          used.set(p, (used.get(p) || 0) + n);
        }
      });
    }
    t.fetch = performance.now() - t1;
    if (!filled) throw new Error("USGS tiles were found but hold no data inside this box.");

    state.grid = { dem, W, H, res: res_m, zone, def, x0, top, coverage: filled / (W * H),
                   tilesRead, decodedMB: decoded / 1e6 };
    state.sources = [...used.entries()].map(([name, n]) => ({ name, share: n / filled }));
    const tc = performance.now();
    const rgba = buildProduct(state.product);
    t.compute = performance.now() - tc;
    t.render = await showImage(rgba);
    t.total = performance.now() - t0;
    state.timings = t;
  } catch (err) {
    console.error(err);
    state.error = err.message || String(err);
  }
  state.loading = false;
  render();
}

// Read the part of one COG that overlaps the output grid, from the coarsest
// overview that is still at least as fine as the output resolution.
async function readWindow(url, x0, top, W, H, res_m) {
  const tiff = await GeoTIFF.fromUrl(url);
  const img0 = await tiff.getImage(0);
  const [ox, oy] = img0.getOrigin();
  const [rx0, ry0] = img0.getResolution();
  const W0 = img0.getWidth(), H0 = img0.getHeight();
  const extX = W0 * rx0, extY = H0 * Math.abs(ry0);
  const nodata = img0.getGDALNoData();

  let img = img0;
  const count = await tiff.getImageCount();
  for (let i = 1; i < count; i++) {
    const cand = await tiff.getImage(i);
    if (extX / cand.getWidth() > res_m) break;
    img = cand;
  }
  const iw = img.getWidth(), ih = img.getHeight();
  const resX = extX / iw, resY = extY / ih;
  const c0 = Math.max(0, Math.floor((x0 - ox) / resX));
  const c1 = Math.min(iw, Math.ceil((x0 + W * res_m - ox) / resX));
  const r0 = Math.max(0, Math.floor((oy - top) / resY));
  const r1 = Math.min(ih, Math.ceil((oy - (top - H * res_m)) / resY));
  if (c1 <= c0 || r1 <= r0) return null;
  const data = await img.readRasters({ window: [c0, r0, c1, r1], samples: [0], interleave: true });
  return { data, ox, oy, resX, resY, c0, r0, w: c1 - c0, h: r1 - r0, nodata };
}

// Nearest-neighbour sample a tile window into the still-empty output cells.
function fillFrom(dem, W, H, x0, top, res_m, win) {
  let n = 0;
  for (let r = 0; r < H; r++) {
    const y = top - (r + 0.5) * res_m;
    const wr = Math.floor((win.oy - y) / win.resY) - win.r0;
    if (wr < 0 || wr >= win.h) continue;
    for (let c = 0; c < W; c++) {
      const i = r * W + c;
      if (!Number.isNaN(dem[i])) continue;
      const wc = Math.floor((x0 + (c + 0.5) * res_m - win.ox) / win.resX) - win.c0;
      if (wc < 0 || wc >= win.w) continue;
      const v = win.data[wr * win.w + wc];
      if (v === win.nodata || !Number.isFinite(v) || v < -1e5) continue;
      dem[i] = v; n++;
    }
  }
  return n;
}

// ---------------- products (computed on the UTM grid, in metres) ----------------
function gradients(g) {
  const { dem, W, H, res } = g;
  const gx = new Float32Array(W * H).fill(NaN), gy = new Float32Array(W * H).fill(NaN);
  for (let r = 1; r < H - 1; r++) {
    for (let c = 1; c < W - 1; c++) {
      const i = r * W + c;
      if (Number.isNaN(dem[i])) continue;              // a hole stays a hole; NaN neighbours propagate
      gx[i] = (dem[i + 1] - dem[i - 1]) / (2 * res);   // dz/dx, east
      gy[i] = (dem[i - W] - dem[i + W]) / (2 * res);   // dz/dy, north
    }
  }
  return { gx, gy };
}

// Kernel half-width in cells. Coarse grids can't hold the 15 m radius, so the
// radius actually used (R * res) is reported in the sidebar.
function lrmRadiusPx(res) {
  return Math.max(2, Math.round(LRM_RADIUS_M / res));
}

// LRM = elevation minus its mean over a (2R+1)^2 square of valid cells.
// Separable running sums keep memory at ~10 bytes/cell; values are offset by a
// reference elevation so the float32 row sums stay precise.
function lrmArray(g) {
  const { dem, W, H, res } = g;
  const R = lrmRadiusPx(res);
  let ref = 0;
  for (let i = 0; i < dem.length; i++) if (!Number.isNaN(dem[i])) { ref = dem[i]; break; }

  const hs = new Float32Array(W * H), hn = new Uint16Array(W * H);
  for (let r = 0; r < H; r++) {
    const o = r * W;
    let s = 0, n = 0;
    for (let c = 0; c < Math.min(R, W); c++) {
      const v = dem[o + c];
      if (!Number.isNaN(v)) { s += v - ref; n++; }
    }
    for (let c = 0; c < W; c++) {
      if (c + R < W) { const v = dem[o + c + R]; if (!Number.isNaN(v)) { s += v - ref; n++; } }
      if (c - R - 1 >= 0) { const v = dem[o + c - R - 1]; if (!Number.isNaN(v)) { s -= v - ref; n--; } }
      hs[o + c] = s; hn[o + c] = n;
    }
  }

  const out = new Float32Array(W * H).fill(NaN);
  const cs = new Float64Array(W), cn = new Int32Array(W);
  const addRow = (r, sign) => {
    const o = r * W;
    for (let c = 0; c < W; c++) { cs[c] += sign * hs[o + c]; cn[c] += sign * hn[o + c]; }
  };
  for (let r = 0; r < Math.min(R, H); r++) addRow(r, 1);
  for (let r = 0; r < H; r++) {
    if (r + R < H) addRow(r + R, 1);
    if (r - R - 1 >= 0) addRow(r - R - 1, -1);
    const o = r * W;
    for (let c = 0; c < W; c++) {
      const v = dem[o + c];
      if (Number.isNaN(v) || !cn[c]) continue;
      out[o + c] = v - ref - cs[c] / cn[c];
    }
  }
  return out;
}

function percentileAbs(arr, p) {
  const s = [];
  const step = Math.max(1, Math.floor(arr.length / 200000));
  for (let i = 0; i < arr.length; i += step) if (Number.isFinite(arr[i])) s.push(Math.abs(arr[i]));
  if (!s.length) return 1;
  s.sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(s.length * p))] || 1;
}

function ramp(stops, t) {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [t0, a] = stops[i - 1], [t1, b] = stops[i];
      const f = (t - t0) / (t1 - t0);
      return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
    }
  }
  return stops[stops.length - 1][1];
}
const DIVERGING = [[0, [33, 102, 172]], [0.5, [247, 247, 247]], [1, [178, 24, 43]]];
const SLOPE = [[0, [252, 253, 191]], [0.35, [252, 137, 97]], [0.7, [183, 55, 121]], [1, [0, 0, 4]]];

// RGBA buffer for one product; NaN cells stay transparent (no invented ground).
// Only the shown product is kept, so switching recomputes rather than caching all three.
function buildProduct(key) {
  const g = state.grid;
  const { W, H } = g;
  const rgba = new Uint8ClampedArray(W * H * 4);
  if (key === "lrm") {
    const l = lrmArray(g);
    const v = percentileAbs(l, 0.98);
    state.lrmStretch = v;
    for (let i = 0; i < l.length; i++) {
      if (Number.isNaN(l[i])) continue;
      const c = ramp(DIVERGING, 0.5 + l[i] / (2 * v));
      rgba[i * 4] = c[0]; rgba[i * 4 + 1] = c[1]; rgba[i * 4 + 2] = c[2]; rgba[i * 4 + 3] = 255;
    }
  } else {
    const { gx, gy } = gradients(g);
    const az = 315 * Math.PI / 180, zen = (90 - 45) * Math.PI / 180;
    const Lx = Math.sin(zen) * Math.sin(az), Ly = Math.sin(zen) * Math.cos(az), Lz = Math.cos(zen);
    for (let i = 0; i < gx.length; i++) {
      if (Number.isNaN(gx[i]) || Number.isNaN(gy[i])) continue;
      if (key === "slope") {
        const s = Math.atan(Math.hypot(gx[i], gy[i])) * 180 / Math.PI;
        const c = ramp(SLOPE, s / 45);
        rgba[i * 4] = c[0]; rgba[i * 4 + 1] = c[1]; rgba[i * 4 + 2] = c[2]; rgba[i * 4 + 3] = 255;
      } else {
        const nlen = Math.hypot(gx[i], gy[i], 1);
        const hs = Math.max(0, (-gx[i] * Lx - gy[i] * Ly + Lz) / nlen) * 255;
        rgba[i * 4] = rgba[i * 4 + 1] = rgba[i * 4 + 2] = hs; rgba[i * 4 + 3] = 255;
      }
    }
  }
  return rgba;
}

// ---------------- overlay ----------------
async function showImage(rgba) {
  const g = state.grid;
  if (!mapReady || !g) return 0;
  const t0 = performance.now();
  const canvas = document.createElement("canvas");
  canvas.width = g.W; canvas.height = g.H;
  canvas.getContext("2d").putImageData(new ImageData(rgba, g.W, g.H), 0, 0);
  const blob = await new Promise((ok) => canvas.toBlob(ok));
  const url = URL.createObjectURL(blob);

  // Pin the image to the raster's own corners (UTM -> lon/lat), not to the request box.
  const x1 = g.x0 + g.W * g.res, bottom = g.top - g.H * g.res;
  const inv = (x, y) => proj4(g.def, "EPSG:4326", [x, y]);
  const coordinates = [inv(g.x0, g.top), inv(x1, g.top), inv(x1, bottom), inv(g.x0, bottom)];

  const src = map.getSource("dem");
  if (src) src.updateImage({ url, coordinates });
  else {
    map.addSource("dem", { type: "image", url, coordinates });
    map.addLayer({ id: "dem-layer", type: "raster", source: "dem",
      paint: { "raster-opacity": state.opacity, "raster-fade-duration": 0 } }, "draw-line");
  }
  if (state.imageUrl) URL.revokeObjectURL(state.imageUrl);
  state.imageUrl = url;
  return performance.now() - t0;
}

async function setProduct(key) {
  if (state.product === key || !state.grid) return;
  state.product = key;
  const t0 = performance.now();
  await showImage(buildProduct(key));
  state.switchMs = performance.now() - t0;
  render();
}

// ---------------- sidebar ----------------
const fmtMs = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`);

function render() {
  const el = document.getElementById("result");
  if (!state.bbox) return;
  let html = `<div class="row"><button class="btn" id="load-btn"${state.loading ? " disabled" : ""}>
      ${state.loading ? '<span class="spinner"></span>Loading terrain…' : "Load terrain"}</button>`;
  if (state.error) html += `<div class="error">${escapeHtml(state.error)}</div>`;
  html += `</div>`;

  const g = state.grid;
  if (g) {
    const toggles = PRODUCTS.map((p) =>
      `<button class="seg${p.key === state.product ? " active" : ""}" data-product="${p.key}">${p.label}</button>`).join("");
    html += `<div class="row">
      <div class="ov-label">Product</div><div class="seg-row">${toggles}</div>
      <div class="ov-label ov-op">Opacity <span id="op-val">${Math.round(state.opacity * 100)}%</span></div>
      <input type="range" id="op-slider" min="0" max="100" value="${Math.round(state.opacity * 100)}" />
      ${state.product === "lrm" ? lrmLegendHtml(g) : ""}
    </div>`;
    html += `<div class="row"><h4>Source</h4>
      <div class="muted" style="font-size:12.5px">USGS 3DEP 1 m bare-earth DEM, shown at ${g.res} m, UTM ${g.zone}N.
      Data covers ${Math.round(g.coverage * 100)}% of the loaded rectangle (your box plus a small margin); uncovered areas stay blank.
      Read ${g.tilesRead} tile window(s), ${g.decodedMB.toFixed(1)} MB decoded.</div>
      ${state.sources.map((s) => `<div class="mono" style="font-size:12px">${escapeHtml(s.name)} · ${Math.round(s.share * 100)}%</div>`).join("")}
    </div>`;
  }
  if (state.timings) {
    const t = state.timings;
    html += `<div class="row"><h4>Timings</h4><div class="mono" style="font-size:12px">
      lookup ${fmtMs(t.lookup)} · fetch+decode ${fmtMs(t.fetch)}<br>
      compute ${fmtMs(t.compute)} · draw ${fmtMs(t.render)} · <b>total ${fmtMs(t.total)}</b>
      ${state.switchMs != null ? `<br>last product switch ${fmtMs(state.switchMs)}` : ""}</div></div>`;
  }
  el.innerHTML = html;
  document.getElementById("load-btn").addEventListener("click", loadTerrain);
  document.querySelectorAll(".seg[data-product]").forEach((b) =>
    b.addEventListener("click", () => setProduct(b.dataset.product)));
  const slider = document.getElementById("op-slider");
  if (slider) slider.addEventListener("input", () => {
    state.opacity = Number(slider.value) / 100;
    document.getElementById("op-val").textContent = `${slider.value}%`;
    if (map.getLayer("dem-layer")) map.setPaintProperty("dem-layer", "raster-opacity", state.opacity);
  });
}

// What LRM colours mean, including the radius actually used at this grid size.
function lrmLegendHtml(g) {
  const radius = lrmRadiusPx(g.res) * g.res;
  const note = radius === LRM_RADIUS_M ? "" :
    ` (${LRM_RADIUS_M} m isn't possible at ${g.res} m cells; draw a smaller box for finer relief)`;
  const span = state.lrmStretch != null ? ` Full colour = ±${state.lrmStretch.toFixed(2)} m.` : "";
  return `<div class="muted" style="font-size:12.5px;margin-top:8px">
    <b style="color:#b2182b">Red</b> = higher, <b style="color:#2166ac">blue</b> = lower than the
    average ground within ${radius} m${note}. Not height above sea level.${span}</div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ?bbox=w,s,e,n opens straight onto a box (shareable link).
(function fromUrl() {
  const p = new URLSearchParams(location.search).get("bbox");
  if (!p) return;
  const b = p.split(",").map(Number);
  if (b.length !== 4 || b.some(Number.isNaN)) return;
  setBbox(b);
  map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40, duration: 0 });
  loadTerrain();
})();
