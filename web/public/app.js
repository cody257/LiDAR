/* lidar-arch — Milestone A front-end.
   Draw/type a bbox -> find covering 3DEP collections -> emit the CLI command.
   Front-end only: this NEVER runs a pipeline, it just builds the command string. */

"use strict";

// ---- density color ramp (sequential: sparse=pale -> dense=saturated) ----
// Domain chosen to spread the real data (0.2..91); 8 = "good for earthworks" sits mid-ramp.
const DENSITY_STOPS = [
  [0.2, "#f3f7e8"],
  [2,   "#cfe6b8"],
  [4,   "#94d27f"],
  [8,   "#3fae4a"],
  [16,  "#1a8a4a"],
  [40,  "#0d5a3c"],
];
const GOOD_DENSITY = 8;          // "good for subtle earthworks" threshold
const LEGEND_MIN = 0.2, LEGEND_MAX = 40; // legend axis (data goes higher but flattens visually)

const EMPTY = { type: "FeatureCollection", features: [] };
const state = { bbox: null, matches: [], best: null };

// computed once coverage loads: per-feature [minx,miny,maxx,maxy] aligned with features array
let coverage = null;        // the loaded FeatureCollection
let featureBboxes = [];     // parallel array of bboxes

// ---------------- map ----------------
const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [-98.5, 39.5], // continental US
  zoom: 3.4,
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

// `mapReady` = the basemap style has painted and the draw layers exist.
// `dataReady` = coverage.json is fetched + bboxes precomputed (lookup works).
// These are DECOUPLED on purpose: the bbox->coverage lookup and command output
// must work even if the basemap tiles are slow or blocked.
let mapReady = false;
let dataReady = false;

map.on("load", onStyleLoad);
function onStyleLoad() {
  if (mapReady) return;
  // draw layer (the user's box), on top of coverage
  map.addSource("draw", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "draw-fill", type: "fill", source: "draw",
    paint: { "fill-color": "#b8552e", "fill-opacity": 0.12 } });
  map.addLayer({ id: "draw-line", type: "line", source: "draw",
    paint: { "line-color": "#b8552e", "line-width": 2.5 } });

  mapReady = true;
  addCoverageLayers();         // add coverage layers if data already arrived
  if (state.bbox) redrawBox(state.bbox); // restore box drawn before the map was ready
}

// Kick off data loading immediately — do NOT wait for the basemap.
prepareData();

// ---------------- coverage data (map-independent) ----------------
async function prepareData() {
  try {
    const res = await fetch("coverage.json");
    if (!res.ok) throw new Error("HTTP " + res.status);
    coverage = await res.json();
  } catch (err) {
    console.error("Failed to load coverage.json", err);
    document.getElementById("cov-count").textContent = "Coverage failed to load.";
    return;
  }

  // precompute each feature's bbox once (used for the fast pre-filter)
  featureBboxes = coverage.features.map((f) => geomBbox(f.geometry));
  dataReady = true;

  const n = coverage.features.length.toLocaleString();
  document.getElementById("cov-count").textContent = `${n} USGS 3DEP collections loaded.`;
  console.log(`coverage.json loaded: ${coverage.features.length} features`);

  addCoverageLayers();              // draw on the map if the style is ready
  if (state.bbox) setBbox(state.bbox); // re-run a lookup the user requested before data arrived
}

// Add the coverage fill/line layers. Safe to call before either side is ready;
// runs only when BOTH the style has loaded and the data is parsed, and only once.
function addCoverageLayers() {
  if (!mapReady || !dataReady) return;
  if (map.getSource("coverage")) return;

  map.addSource("coverage", { type: "geojson", data: coverage });
  map.addLayer({
    id: "cov-fill", type: "fill", source: "coverage",
    paint: { "fill-color": densityColorExpr(), "fill-opacity": 0.55 },
  }, "draw-fill"); // keep coverage UNDER the draw box
  map.addLayer({
    id: "cov-line", type: "line", source: "coverage",
    paint: { "line-color": "#3a4a63", "line-width": 0.5, "line-opacity": 0.35 },
  }, "draw-fill");

  wireHoverPopup();
}

// MapLibre paint expression mirroring DENSITY_STOPS. Null density -> grey.
function densityColorExpr() {
  const expr = ["interpolate", ["linear"], ["coalesce", ["get", "density"], -1]];
  expr.push(-1, "#c3cbd6"); // unknown density
  for (const [v, c] of DENSITY_STOPS) expr.push(v, c);
  return expr;
}

// ---------------- geometry helpers ----------------
function geomBbox(geom) {
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  const polys = geom.type === "MultiPolygon" ? geom.coordinates : [geom.coordinates];
  for (const poly of polys) {
    for (const ring of poly) {
      for (let i = 0; i < ring.length; i++) {
        const x = ring[i][0], y = ring[i][1];
        if (x < minx) minx = x;
        if (y < miny) miny = y;
        if (x > maxx) maxx = x;
        if (y > maxy) maxy = y;
      }
    }
  }
  return [minx, miny, maxx, maxy];
}

function pointInBbox(lon, lat, b) {
  return lon >= b[0] && lon <= b[2] && lat >= b[1] && lat <= b[3];
}

// ray-casting; ring is array of [lon,lat]. Returns true if point strictly/­boundary inside.
function pointInRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    const intersect =
      (yi > lat) !== (yj > lat) &&
      lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

// point-in-polygon for one Polygon coordinate set: [outer, hole1, hole2, ...]
function pointInPolygon(lon, lat, rings) {
  if (!rings.length || !pointInRing(lon, lat, rings[0])) return false; // outside outer ring
  for (let h = 1; h < rings.length; h++) {
    if (pointInRing(lon, lat, rings[h])) return false; // inside a hole
  }
  return true;
}

function pointInGeometry(lon, lat, geom) {
  if (geom.type === "MultiPolygon") {
    for (const poly of geom.coordinates) {
      if (pointInPolygon(lon, lat, poly)) return true;
    }
    return false;
  }
  return pointInPolygon(lon, lat, geom.coordinates); // Polygon
}

// ---------------- lookup ----------------
function findMatches(bbox) {
  if (!coverage) return [];
  const cLon = (bbox[0] + bbox[2]) / 2;
  const cLat = (bbox[1] + bbox[3]) / 2;
  const out = [];
  for (let i = 0; i < coverage.features.length; i++) {
    if (!pointInBbox(cLon, cLat, featureBboxes[i])) continue;      // fast reject
    if (!pointInGeometry(cLon, cLat, coverage.features[i].geometry)) continue; // exact
    out.push(coverage.features[i].properties);
  }
  // density desc, then year desc (nulls last)
  out.sort((a, b) => {
    const da = a.density == null ? -Infinity : a.density;
    const db = b.density == null ? -Infinity : b.density;
    if (db !== da) return db - da;
    const ya = a.year == null ? -Infinity : a.year;
    const yb = b.year == null ? -Infinity : b.year;
    return yb - ya;
  });
  return out;
}

// ---------------- UTM ----------------
function utmZone(centerLon) {
  return Math.floor((centerLon + 180) / 6) + 1;
}
function utmLabel(bbox) {
  const cLon = (bbox[0] + bbox[2]) / 2;
  const z = utmZone(cLon);
  return { zone: z, epsg: 26900 + z, label: `UTM ${z}N / EPSG:${26900 + z}` };
}

// ---------------- quality hint ----------------
function qualityHint(density) {
  if (density == null) return { cls: "sparse", text: "density unknown" };
  if (density >= 8) return { cls: "good", text: "good for subtle earthworks" };
  if (density >= 4) return { cls: "marginal", text: "marginal — large features only" };
  return { cls: "sparse", text: "too sparse for subtle features" };
}

// color swatch matching the map ramp, for a given density
function densityColor(density) {
  if (density == null) return "#c3cbd6";
  const stops = DENSITY_STOPS;
  if (density <= stops[0][0]) return stops[0][1];
  if (density >= stops[stops.length - 1][0]) return stops[stops.length - 1][1];
  for (let i = 1; i < stops.length; i++) {
    if (density <= stops[i][0]) {
      const [v0, c0] = stops[i - 1], [v1, c1] = stops[i];
      return lerpColor(c0, c1, (density - v0) / (v1 - v0));
    }
  }
  return stops[stops.length - 1][1];
}
function lerpColor(a, b, t) {
  const pa = hex2rgb(a), pb = hex2rgb(b);
  const r = Math.round(pa[0] + (pb[0] - pa[0]) * t);
  const g = Math.round(pa[1] + (pb[1] - pa[1]) * t);
  const bl = Math.round(pa[2] + (pb[2] - pa[2]) * t);
  return `rgb(${r},${g},${bl})`;
}
function hex2rgb(h) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

// ---------------- command ----------------
function fmt(bbox) { return bbox.map((x) => Number(x).toFixed(4)); }
function buildCommand() {
  if (!state.bbox || !state.best) return "";
  const [w, s, e, n] = fmt(state.bbox);
  return `lidar-arch run --bbox ${w} ${s} ${e} ${n} --resource ${state.best.name} --out out/site`;
}

// ---------------- draw interaction ----------------
let drawing = false, start = null;
const drawBtn = document.getElementById("draw-btn");

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
drawBtn.addEventListener("click", () => (drawing ? exitDraw() : enterDraw()));

function boxToGeoJSON(a, b) {
  const w = Math.min(a.lng, b.lng), e = Math.max(a.lng, b.lng);
  const s = Math.min(a.lat, b.lat), n = Math.max(a.lat, b.lat);
  return {
    bbox: [w, s, e, n],
    gj: { type: "Feature", geometry: { type: "Polygon",
      coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } },
  };
}
// Paint the rectangle for a [w,s,e,n] bbox onto the draw layer (no-op until the map is ready).
function redrawBox(bbox) {
  if (!mapReady) return;
  const src = map.getSource("draw");
  if (src) src.setData(
    boxToGeoJSON({ lng: bbox[0], lat: bbox[1] }, { lng: bbox[2], lat: bbox[3] }).gj
  );
}
map.on("mousedown", (e) => { if (drawing) start = e.lngLat; });
map.on("mousemove", (e) => {
  if (!drawing || !start) return;
  map.getSource("draw").setData(boxToGeoJSON(start, e.lngLat).gj);
});
map.on("mouseup", (e) => {
  if (!drawing || !start) return;
  const { bbox, gj } = boxToGeoJSON(start, e.lngLat);
  map.getSource("draw").setData(gj);
  setBbox(bbox);
  exitDraw();
});

// ---------------- inputs <-> box ----------------
const inIds = ["in-w", "in-s", "in-e", "in-n"];
function setInputs(bbox) {
  const [w, s, e, n] = bbox;
  setVal("in-w", w); setVal("in-s", s); setVal("in-e", e); setVal("in-n", n);
}
function setVal(id, v) {
  const el = document.getElementById(id);
  if (el && v != null && !Number.isNaN(v)) el.value = Number(v).toFixed(4);
}
function readInputs() {
  const g = (id) => parseFloat(document.getElementById(id).value);
  const w = g("in-w"), s = g("in-s"), e = g("in-e"), n = g("in-n");
  if ([w, s, e, n].some(Number.isNaN)) return;
  const bbox = [Math.min(w, e), Math.min(s, n), Math.max(w, e), Math.max(s, n)];
  redrawBox(bbox);
  setBbox(bbox);
}
inIds.forEach((id) =>
  document.getElementById(id).addEventListener("change", readInputs)
);

// ---------------- state + render ----------------
function setBbox(bbox) {
  state.bbox = bbox;
  state.matches = findMatches(bbox);
  state.best = state.matches[0] || null;
  setInputs(bbox);
  render();
}

function render() {
  const el = document.getElementById("result");
  if (!state.bbox) {
    el.innerHTML =
      '<div class="empty muted">Draw a box on the map, or type the four corners above, to see 3DEP coverage and the command.</div>';
    return;
  }
  const [w, s, e, n] = fmt(state.bbox);
  const utm = utmLabel(state.bbox);

  let html = "";
  html += `<div class="row">
    <h4>Your box</h4>
    <div class="coords mono">${w}, ${s} → ${e}, ${n}</div>
    <div class="utm">Would grid in <b>${utm.label}</b></div>
  </div>`;

  html += `<div class="row"><h4>3DEP coverage</h4>`;
  if (!dataReady) {
    html += `<div class="muted" style="font-size:12.5px">Checking coverage…</div></div>`;
    el.innerHTML = html;
    return;
  }
  if (!state.matches.length) {
    html += `<div class="no-cov">No 3DEP coverage here — browse
      <a href="https://usgs.entwine.io" target="_blank" rel="noopener">usgs.entwine.io</a>.</div></div>`;
    el.innerHTML = html;
    return;
  }

  const SHOWN = 5;
  state.matches.slice(0, SHOWN).forEach((m, i) => {
    const q = qualityHint(m.density);
    const col = densityColor(m.density);
    const dens = m.density == null ? "—" : `~${m.density} pts/m²`;
    const yr = m.year == null ? "year n/a" : m.year;
    html += `<div class="match ${i === 0 ? "best" : ""}">
      <div class="m-top">
        <span class="m-name">${escapeHtml(m.name)}</span>
        <span class="m-year">${yr}</span>
      </div>
      <div class="m-dens"><span class="dot" style="background:${col}"></span>${dens}</div>
      <div class="hint ${q.cls}">${q.text}</div>
    </div>`;
  });
  if (state.matches.length > SHOWN) {
    html += `<p class="more">+ ${state.matches.length - SHOWN} more collection(s) cover this box.</p>`;
  }
  html += `</div>`;

  // command for the best pick
  html += `<div class="row">
    <h4>Command (best pick)</h4>
    <div class="cmd" id="cmd">${escapeHtml(buildCommand())}</div>
    <div class="copy-row">
      <button class="btn ghost" id="copy-btn" style="width:auto">Copy command</button>
      <span class="copied hidden" id="copied">Copied!</span>
    </div>
  </div>`;

  el.innerHTML = html;
  document.getElementById("copy-btn").addEventListener("click", copyCommand);
}

function copyCommand() {
  const cmd = buildCommand();
  const done = () => {
    const c = document.getElementById("copied");
    c.classList.remove("hidden");
    setTimeout(() => c.classList.add("hidden"), 1400);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(cmd).then(done).catch(fallbackCopy);
  } else {
    fallbackCopy();
  }
  function fallbackCopy() {
    const ta = document.createElement("textarea");
    ta.value = cmd; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); done(); } catch (e) {}
    document.body.removeChild(ta);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------------- hover popup ----------------
function wireHoverPopup() {
  const popup = new maplibregl.Popup({
    closeButton: false, closeOnClick: false, className: "cov-pop", maxWidth: "240px",
  });
  map.on("mousemove", "cov-fill", (e) => {
    if (drawing) { popup.remove(); return; }
    map.getCanvas().style.cursor = "pointer";
    const p = e.features[0].properties;
    const dens = p.density == null || p.density === "" ? "density n/a" : `~${p.density} pts/m²`;
    const yr = p.year == null || p.year === "" ? "year n/a" : p.year;
    popup
      .setLngLat(e.lngLat)
      .setHTML(`<div class="pop-name">${escapeHtml(p.name)}</div>
                <div class="pop-meta">${yr} · ${dens}</div>`)
      .addTo(map);
  });
  map.on("mouseleave", "cov-fill", () => {
    if (!drawing) map.getCanvas().style.cursor = "";
    popup.remove();
  });
}

// ---------------- legend ----------------
(function buildLegend() {
  const ramp = document.getElementById("legend-ramp");
  // CSS gradient across the legend axis using the same stops
  const span = LEGEND_MAX - LEGEND_MIN;
  const segs = DENSITY_STOPS
    .filter(([v]) => v <= LEGEND_MAX)
    .map(([v, c]) => `${c} ${(((v - LEGEND_MIN) / span) * 100).toFixed(1)}%`);
  ramp.style.background = `linear-gradient(to right, ${segs.join(", ")})`;
  // position the "8 · earthworks" tick
  const good = document.getElementById("legend-good");
  good.style.left = `${(((GOOD_DENSITY - LEGEND_MIN) / span) * 100).toFixed(1)}%`;
})();
