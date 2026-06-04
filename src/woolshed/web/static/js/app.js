/**
 * WoolShed front-end app.
 *
 * Handles map markers, workbook upload, sample loading, optimisation and flow rendering.
 */

"use strict";

// Map setup.

const map = L.map("map", { zoomControl: true }).setView([46.2, 12.0], 7);

// Use OpenStreetMap tiles by default.
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

// Keep flow lines below markers.
try {
  map.createPane('flowPane');
  map.getPane('flowPane').style.zIndex = 200; // Below the default marker pane.
} catch (e) {
  // Older Leaflet builds may not expose createPane.
}

// Layer groups.
const sourceLayer = L.layerGroup().addTo(map);
const techLayer = L.layerGroup().addTo(map);
const productLayer = L.layerGroup().addTo(map);
const flowLayer = L.layerGroup().addTo(map);
// Marker lookup for table clicks.
let LOC_MARKERS = {};

// Marker colour helpers.

function circleIcon(colour) {
  return L.divIcon({
    className: "",
    html: `<svg width="20" height="20"><circle cx="10" cy="10" r="8"
             fill="${colour}" stroke="#fff" stroke-width="2" opacity="0.9"/></svg>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -12],
  });
}

const ICONS = {
  source: circleIcon("#2196F3"),
  proc: circleIcon("#FF9800"),
  product: circleIcon("#4CAF50"),
};
// Process colours by stage.
const STAGE_COLOURS = [
  "#FF9800", "#FB8C00", "#F57C00", "#EF6C00", "#E65100",
  "#D84315", "#BF360C", "#A1887F", "#8D6E63",
];

function techIcon(stage) {
  const c = STAGE_COLOURS[(stage - 1) % STAGE_COLOURS.length];
  return circleIcon(c);
}

// Quality class labels.
// The backend owns these labels; the frontend loads them at startup.

let QUALITY = { fineness: {}, color: {}, staple_length: {}, scouring_yield: {} };

async function loadQualityClasses() {
  const res = await fetch("/api/quality-classes");
  QUALITY = await res.json();
}

function qualityLabel(q) {
  if (!q) return "—";
  const parts = [];
  if (q.fineness) parts.push("Fineness: " + (QUALITY.fineness[q.fineness] || q.fineness));
  if (q.color) parts.push("Colour: " + (QUALITY.color[q.color] || q.color));
  if (q.staple_length) parts.push("Staple: " + (QUALITY.staple_length[q.staple_length] || q.staple_length));
  if (q.scouring_yield) parts.push("Scour yield: " + (QUALITY.scouring_yield[q.scouring_yield] || q.scouring_yield));
  return parts.length ? parts.join("<br>") : "—";
}

// State.

let DATA = { sources: [], processes: [], products: [], params: {} };
let LOCATIONS = {};  // ID to [lat, lon].

// Data loading helpers.

function showSpinner() {
  if (!document.getElementById("spinner-ov")) {
    const d = document.createElement("div");
    d.id = "spinner-ov";
    d.className = "spinner-overlay";
    d.innerHTML = '<div class="spinner-border text-light" role="status"></div>';
    document.body.appendChild(d);
  }
}
function hideSpinner() {
  const el = document.getElementById("spinner-ov");
  if (el) el.remove();
}

// Show a toast, or fall back to alert if the toast container is missing.
function showToast(message, title = "Notice", variant = "danger") {
  const wrap = document.getElementById("toast-wrap");
  if (!wrap) {
    alert(title + ": " + message);
    return;
  }
  const toast = document.createElement("div");
  toast.className = `toast align-items-center text-bg-${variant} border-0`;
  toast.setAttribute("role", "alert");
  toast.setAttribute("aria-live", "assertive");
  toast.setAttribute("aria-atomic", "true");
  toast.innerHTML = `<div class="d-flex"><div class="toast-body"><strong>${title}:</strong> ${message}</div>` +
                    `<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>`;
  wrap.appendChild(toast);
  const bsToast = new bootstrap.Toast(toast, { delay: 6000 });
  bsToast.show();
  toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

async function loadData() {
  const res = await fetch("/api/data");
  DATA = await res.json();
  LOCATIONS = {};
  DATA.sources.forEach(s => { LOCATIONS[s.id] = [s.lat, s.lon]; });
  DATA.processes.forEach(t => { LOCATIONS[t.id] = [t.lat, t.lon]; });
  DATA.products.forEach(p => { LOCATIONS[p.id] = [p.lat, p.lon]; });
  drawMarkers();
  drawTables();
  document.getElementById("opt-status").textContent =
    `${DATA.sources.length} sources, ${DATA.processes.length} processes, ${DATA.products.length} products loaded.`;
}

// Marker rendering.

function drawMarkers() {
  sourceLayer.clearLayers();
  techLayer.clearLayers();
  productLayer.clearLayers();
  flowLayer.clearLayers();
  LOC_MARKERS = {};

  const bounds = [];

  DATA.sources.forEach(s => {
    const ll = [s.lat, s.lon];
    bounds.push(ll);
    const m = L.marker(ll, { icon: ICONS.source })
      .bindPopup(
        `<b>🐑 ${s.name}</b> <small>(${s.id})</small><br>` +
        `Quantity: ${s.quantity_kg} kg<br>` +
        `Cost: €${s.cost_per_kg}/kg &nbsp; Impact: ${s.impact_per_kg}/kg<br>` +
        `<hr class="my-1"><small>${qualityLabel(s.quality)}</small>`
      )
      .addTo(sourceLayer);
    LOC_MARKERS[s.id] = m;
  });

  DATA.processes.forEach(t => {
    const ll = [t.lat, t.lon];
    bounds.push(ll);
    const m = L.marker(ll, { icon: techIcon(t.stage) })
      .bindPopup(
        `<b>⚙️ ${t.name}</b> <small>(${t.id})</small><br>` +
        `Stage ${t.stage} · Chain: ${t.chain}<br>` +
        `Conversion: ${t.conversion_pct}% · Capacity: ${t.max_capacity_kg} kg<br>` +
        `Cost: €${t.cost_per_kg}/kg &nbsp; Impact: ${t.impact_per_kg}/kg`
      )
      .addTo(techLayer);
    LOC_MARKERS[t.id] = m;
  });

  DATA.products.forEach(p => {
    const ll = [p.lat, p.lon];
    bounds.push(ll);
    const m = L.marker(ll, { icon: ICONS.product })
      .bindPopup(
        `<b>📦 ${p.name}</b> <small>(${p.id})</small><br>` +
        `Demand: ${p.demand_min_kg}–${p.demand_max_kg} kg<br>` +
        `Price: €${p.price_per_kg}/kg`
      )
      .addTo(productLayer);
    LOC_MARKERS[p.id] = m;
  });

  if (bounds.length) {
    map.fitBounds(bounds, { padding: [40, 40] });
  }
}

// Focus the map on an entity and open its popup.
function focusOn(id) {
  const ll = LOCATIONS[id];
  if (!ll) return;
  try {
    map.setView(ll, Math.max(map.getZoom(), 10));
  } catch (e) {
    map.panTo(ll);
  }
  const m = LOC_MARKERS[id];
  if (m && m.openPopup) m.openPopup();
}

// Data tables.

function makeTable(rows, columns) {
  if (!rows.length) return "<p class='text-muted'>No data</p>";
  let h = "<table class='table table-sm table-striped table-bordered mb-0'><thead><tr>";
  columns.forEach(c => { h += `<th>${c.label}</th>`; });
  h += "</tr></thead><tbody>";
  rows.forEach(r => {
    h += "<tr onclick=\"focusOn('" + r.id + "')\" style=\"cursor:pointer\">";
    columns.forEach(c => {
      let v = c.get(r);
      if (v === null || v === undefined) v = "";
      h += `<td>${v}</td>`;
    });
    h += "</tr>";
  });
  h += "</tbody></table>";
  return h;
}

function drawTables() {
  document.getElementById("tbl-sources").innerHTML = makeTable(DATA.sources, [
    { label: "ID", get: r => r.id },
    { label: "Name", get: r => r.name },
    { label: "Qty (kg)", get: r => r.quantity_kg },
    { label: "€/kg", get: r => r.cost_per_kg },
    { label: "Impact", get: r => r.impact_per_kg },
    { label: "Fine.", get: r => r.quality?.fineness ?? "" },
    { label: "Col.", get: r => r.quality?.color ?? "" },
    { label: "Staple", get: r => r.quality?.staple_length ?? "" },
    { label: "Scour", get: r => r.quality?.scouring_yield ?? "" },
  ]);
  document.getElementById("tbl-processes").innerHTML = makeTable(DATA.processes, [
    { label: "ID", get: r => r.id },
    { label: "Name", get: r => r.name },
    { label: "Stage", get: r => r.stage },
    { label: "Chain", get: r => r.chain },
    { label: "Conv%", get: r => r.conversion_pct },
    { label: "Cap", get: r => r.max_capacity_kg >= 1e8 ? "∞" : r.max_capacity_kg },
    { label: "€/kg", get: r => r.cost_per_kg },
    { label: "Imp", get: r => r.impact_per_kg },
  ]);
  document.getElementById("tbl-products").innerHTML = makeTable(DATA.products, [
    { label: "ID", get: r => r.id },
    { label: "Name", get: r => r.name },
    { label: "Min kg", get: r => r.demand_min_kg },
    { label: "Max kg", get: r => r.demand_max_kg >= 1e8 ? "∞" : r.demand_max_kg },
    { label: "€/kg", get: r => r.price_per_kg },
  ]);
}

// Flow lines.

function drawFlows(flows) {
  flowLayer.clearLayers();
  if (!flows || !flows.length) return;

  // Scale line width against the largest flow.
  const maxMass = Math.max(...flows.map(f => f.mass_kg), 1);

  flows.forEach(f => {
    const from = LOCATIONS[f.from_id];
    const to = LOCATIONS[f.to_id];
    if (!from || !to) return;

    const weight = Math.max(2, Math.min(10, (f.mass_kg / maxMass) * 10));

    const line = L.polyline([from, to], {
      color: "#e53935",
      weight: weight,
      opacity: 0.75,
      dashArray: null,
      pane: 'flowPane',
    }).addTo(flowLayer);

    // Label the midpoint.
    const mid = [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2];
    L.marker(mid, {
      icon: L.divIcon({
        className: "",
        html: `<span style="background:rgba(255,255,255,0.85);padding:1px 5px;border-radius:3px;
               font-size:11px;font-weight:600;color:#c62828;white-space:nowrap;
               border:1px solid #ef9a9a">${f.mass_kg.toFixed(0)} kg</span>`,
        iconSize: [60, 18],
        iconAnchor: [30, 9],
      }),
      pane: 'flowPane',
    }).addTo(flowLayer);

    // Put a small arrow near the destination.
    const ratio = 0.85;
    const arrowLat = from[0] + (to[0] - from[0]) * ratio;
    const arrowLon = from[1] + (to[1] - from[1]) * ratio;
    L.marker([arrowLat, arrowLon], {
      icon: L.divIcon({
        className: "",
        html: `<svg width="16" height="16" style="transform:rotate(${
          Math.atan2(to[1]-from[1], to[0]-from[0]) * 180/Math.PI - 90
        }deg)"><polygon points="8,0 16,16 0,16" fill="#e53935" opacity="0.8"/></svg>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      }),
      pane: 'flowPane',
    }).addTo(flowLayer);

    line.bindPopup(`<b>${f.from_id} → ${f.to_id}</b><br>${f.mass_kg.toFixed(1)} kg`);
  });
    // Keep markers visible above flow lines.
    try {
      sourceLayer.bringToFront();
      techLayer.bringToFront();
      productLayer.bringToFront();
    } catch (e) {
      // Some Leaflet builds may not support bringToFront.
    }
}

// Event handlers.

// Upload Excel.
document.getElementById("file-upload").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  showSpinner();
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    let j = null;
    try {
      j = await res.json();
    } catch (e) {
      // Show the raw response if the server returned an HTML error page.
      try {
        const txt = await res.text();
        showToast(txt || String(e), "Upload error", "danger");
      } catch (_) {
        showToast(String(e), "Upload error", "danger");
      }
      return;
    }
    if (!res.ok) {
      const msg = j && (j.error || j.message) ? (j.error || j.message) : JSON.stringify(j);
      showToast(msg || `Upload failed (status ${res.status})`, "Upload error", "danger");
      return;
    }
    if (j.error) { showToast(j.error, "Upload error", "danger"); return; }
    await loadData();
  } catch (err) {
    showToast(String(err), "Upload failed", "danger");
  } finally {
    hideSpinner();
    e.target.value = "";
  }
});

// Load sample data.
document.getElementById("btn-sample").addEventListener("click", async () => {
  showSpinner();
  try {
    await fetch("/api/generate-sample", { method: "POST" });
    await loadData();
  } finally {
    hideSpinner();
  }
});

// Download the template workbook.
document.getElementById("btn-download-sample").addEventListener("click", () => {
  window.location.href = "/api/download-sample";
});

// Run the optimiser.
document.getElementById("btn-optimize").addEventListener("click", async () => {
  const objective = document.getElementById("sel-objective").value;
  showSpinner();
  document.getElementById("opt-status").textContent = "Running optimiser…";
  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective }),
    });
    const j = await res.json();
    if (j.error) {
      document.getElementById("opt-status").textContent = "Error: " + j.error;
      document.getElementById("results-text").textContent = j.error;
      return;
    }
    document.getElementById("opt-status").textContent =
      `${j.status} — Objective: ${j.objective_value}`;
    document.getElementById("results-text").textContent = (j.summary || []).join("\n");
    drawFlows(j.flows || []);
    // Switch to the results tab.
    const tab = document.getElementById("tab-results");
    if (tab) new bootstrap.Tab(tab).show();
  } catch (err) {
    document.getElementById("opt-status").textContent = "Error: " + err;
  } finally {
    hideSpinner();
  }
});

// Start the app.

// Load quality labels first so the first popups have readable text.
// If that fails, the UI falls back to raw class numbers.
loadQualityClasses().catch(() => {}).then(loadData);
