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
const flowLayer   = L.layerGroup().addTo(map);
const jitterLayer = L.layerGroup().addTo(map); // connector legs for co-located markers
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
  decorLayer.clearLayers();
  _flows = [];
  LOC_MARKERS = {};

  // Group entities by coordinate; co-located ones get a small circular offset
  // so each marker is individually clickable. LOCATIONS keeps true coords.
  const _coordGroups = {};
  [...DATA.sources, ...DATA.processes, ...DATA.products].forEach(e => {
    const key = `${(+e.lat).toFixed(5)},${(+e.lon).toFixed(5)}`;
    (_coordGroups[key] = _coordGroups[key] || []).push(e.id);
  });
  function _jittered(e) {
    const key = `${(+e.lat).toFixed(5)},${(+e.lon).toFixed(5)}`;
    const group = _coordGroups[key];
    if (group.length === 1) return [e.lat, e.lon];
    const idx   = group.indexOf(e.id);
    const angle = (2 * Math.PI * idx) / group.length - Math.PI / 2;
    const r     = 0.0018; // ~200 m at mid-latitudes
    const jll   = [e.lat + r * Math.cos(angle), e.lon + r * Math.sin(angle)];
    L.polyline([[e.lat, e.lon], jll], {
      color: "#888", weight: 1, opacity: 0.55, dashArray: "3 4", pane: "flowPane",
      interactive: false,
    }).addTo(jitterLayer);
    LOCATIONS[e.id] = jll; // flow lines follow the marker, not the true centre
    return jll;
  }

  const bounds = [];

  DATA.sources.forEach(s => {
    const ll = _jittered(s);
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
    const ll = _jittered(t);
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
    const ll = _jittered(p);
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

function makeTable(rows, entityType, columns) {
  if (!rows.length) return "<p class='text-muted'>No data</p>";
  let h = "<table class='table table-sm table-striped table-bordered mb-0'><thead><tr>";
  columns.forEach(c => { h += `<th>${c.label}</th>`; });
  h += "</tr></thead><tbody>";
  rows.forEach(r => {
    const id = String(r.id || "");
    const safeId = id.replace(/['\\]/g, "\\$&");
    const safeIdAttr = id.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    h += `<tr onclick="focusOn('${safeId}')" style="cursor:pointer">`;
    columns.forEach(c => {
      let v = c.get(r);
      if (v === null || v === undefined) v = "";
      if (c.qualityKey) {
        // Discrete class dropdown — short label in select, full label as tooltip.
        const opts = QUALITY[c.qualityKey] || {};
        const shortLabel = lbl => lbl.split(" (")[0];
        let sel = `<select class="tbl-quality-select" ` +
                  `data-entity-type="${entityType}" data-id="${safeIdAttr}" data-field="quality.${c.qualityKey}" ` +
                  `onclick="event.stopPropagation()">` +
                  `<option value="">—</option>`;
        Object.entries(opts).forEach(([k, label]) => {
          sel += `<option value="${k}" title="${label}"${String(v) === k ? " selected" : ""}>${shortLabel(label)}</option>`;
        });
        sel += `</select>`;
        h += `<td style="padding:1px 2px">${sel}</td>`;
      } else if (c.editable) {
        const safeVal = String(v)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/\"/g, "&quot;");
        h += `<td class="tbl-edit" contenteditable="true" ` +
             `data-entity-type="${entityType}" data-id="${safeIdAttr}" data-field="${c.field}" ` +
             `onclick="event.stopPropagation()" ` +
             `onkeydown="if(event.key==='Enter'){event.preventDefault();this.blur()}` +
                        `if(event.key==='Escape'){this.textContent=this.dataset.orig;this.blur()}" ` +
             `onfocus="this.dataset.orig=this.textContent.trim()">${safeVal}</td>`;
      } else {
        const safeText = String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        h += `<td>${safeText}</td>`;
      }
    });
    h += "</tr>";
  });
  h += "</tbody></table>";
  return h;
}

async function patchEntity(type, id, field, value) {
  const res = await fetch("/api/entity", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, id, field, value }),
  });
  const j = await res.json();
  if (!res.ok) throw new Error(j.error || `Save failed (${res.status})`);
  // Keep local DATA in sync so optimizer uses updated values.
  const lists = { source: DATA.sources, process: DATA.processes, product: DATA.products };
  const entity = (lists[type] || []).find(e => e.id === id);
  if (entity) {
    if (field.startsWith("quality.")) {
      const sub = field.split(".")[1];
      entity.quality = entity.quality || {};
      entity.quality[sub] = value === "" ? null : parseInt(value, 10);
      return;
    }
    const parsed = parseFloat(value);
    entity[field] = Number.isFinite(parsed) ? parsed : value;
    // If lat/lon changed, redraw markers and decorations.
    if (field === "lat" || field === "lon") {
      LOCATIONS[id] = [
        field === "lat" ? parsed : entity.lat,
        field === "lon" ? parsed : entity.lon,
      ];
      drawMarkers();
      _renderDecorations();
    }
  }
}

// Delegated change handler for quality class dropdowns.
document.addEventListener("change", async (e) => {
  const sel = e.target;
  if (!sel.classList.contains("tbl-quality-select")) return;
  const { entityType, id, field } = sel.dataset;
  const td = sel.closest("td");
  try {
    await patchEntity(entityType, id, field, sel.value);
    if (td) { td.classList.add("tbl-edit-saved"); setTimeout(() => td.classList.remove("tbl-edit-saved"), 900); }
    // Local DATA state is updated inside patchEntity().
  } catch (err) {
    if (td) { td.classList.add("tbl-edit-error"); setTimeout(() => td.classList.remove("tbl-edit-error"), 1800); }
    showToast(err.message, "Save error", "danger");
  }
});

// Delegated focusout handler for all editable table cells.
document.addEventListener("focusout", async (e) => {
  const td = e.target;
  if (!td.classList.contains("tbl-edit")) return;

  const newVal = td.textContent.trim();
  const origVal = td.dataset.orig ?? newVal;
  if (newVal === origVal) return; // unchanged

  const { entityType, id, field } = td.dataset;
  try {
    await patchEntity(entityType, id, field, newVal);
    td.classList.add("tbl-edit-saved");
    setTimeout(() => td.classList.remove("tbl-edit-saved"), 900);
  } catch (err) {
    td.textContent = origVal; // revert
    td.classList.add("tbl-edit-error");
    setTimeout(() => td.classList.remove("tbl-edit-error"), 1800);
    showToast(err.message, "Save error", "danger");
  }
});

// Delegated hover + click handlers for flow table rows.
document.addEventListener("mouseover", (e) => {
  const row = e.target.closest(".flow-row");
  if (!row) return;
  const idx = parseInt(row.dataset.idx, 10);
  _highlightFlow(idx, true);
});
document.addEventListener("mouseout", (e) => {
  const row = e.target.closest(".flow-row");
  if (!row) return;
  _highlightFlow(parseInt(row.dataset.idx, 10), false);
});
document.addEventListener("click", (e) => {
  const row = e.target.closest(".flow-row");
  if (!row) return;
  const idx = parseInt(row.dataset.idx, 10);
  const f   = _flows[idx];
  const pl  = _flowLines[idx];
  if (!f || !pl) return;
  const from = LOCATIONS[f.from_id];
  const to   = LOCATIONS[f.to_id];
  if (from && to) map.fitBounds([from, to], { padding: [60, 60] });
  pl.openPopup();
});

function drawTables() {
  document.getElementById("tbl-sources").innerHTML = makeTable(DATA.sources, "source", [
    { label: "ID",      get: r => r.id },
    { label: "Name",    get: r => r.name,          editable: true, field: "name" },
    { label: "Qty (kg)",get: r => r.quantity_kg,   editable: true, field: "quantity_kg" },
    { label: "€/kg",   get: r => r.cost_per_kg,   editable: true, field: "cost_per_kg" },
    { label: "Impact",  get: r => r.impact_per_kg, editable: true, field: "impact_per_kg" },
    { label: "Fine.",   get: r => r.quality?.fineness ?? "",       qualityKey: "fineness" },
    { label: "Col.",    get: r => r.quality?.color ?? "",           qualityKey: "color" },
    { label: "Staple",  get: r => r.quality?.staple_length ?? "",   qualityKey: "staple_length" },
    { label: "Scour",   get: r => r.quality?.scouring_yield ?? "",  qualityKey: "scouring_yield" },
  ]);
  document.getElementById("tbl-processes").innerHTML = makeTable(DATA.processes, "process", [
    { label: "ID",    get: r => r.id },
    { label: "Name",  get: r => r.name,          editable: true, field: "name" },
    { label: "Stage", get: r => r.stage },
    { label: "Chain", get: r => r.chain },
    { label: "Conv%", get: r => r.conversion_pct,   editable: true, field: "conversion_pct" },
    { label: "Cap",   get: r => r.max_capacity_kg >= 1e8 ? "∞" : r.max_capacity_kg,
                      editable: true, field: "max_capacity_kg" },
    { label: "€/kg",  get: r => r.cost_per_kg,      editable: true, field: "cost_per_kg" },
    { label: "Imp",   get: r => r.impact_per_kg,    editable: true, field: "impact_per_kg" },
  ]);
  document.getElementById("tbl-products").innerHTML = makeTable(DATA.products, "product", [
    { label: "ID",     get: r => r.id },
    { label: "Name",   get: r => r.name,          editable: true, field: "name" },
    { label: "Min kg", get: r => r.demand_min_kg, editable: true, field: "demand_min_kg" },
    { label: "Max kg", get: r => r.demand_max_kg >= 1e8 ? "∞" : r.demand_max_kg,
                       editable: true, field: "demand_max_kg" },
    { label: "€/kg",  get: r => r.price_per_kg,  editable: true, field: "price_per_kg" },
  ]);
}

// Flow lines.

let _flows = [];
let _flowLines = []; // parallel array of Leaflet polylines
const decorLayer = L.layerGroup().addTo(map);

function escHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function _entityName(id) {
  return (
    DATA.sources.find(e => e.id === id) ||
    DATA.processes.find(e => e.id === id) ||
    DATA.products.find(e => e.id === id)
  )?.name || id;
}

function _highlightFlow(idx, on) {
  _flowLines.forEach((pl, i) => {
    if (!pl) return;
    if (i === idx) pl.setStyle({ color: on ? "#ff6f00" : "#e53935", weight: on ? pl._woolWeight + 2 : pl._woolWeight, opacity: 0.9 });
    else pl.setStyle({ opacity: on ? 0.3 : 0.75, color: "#e53935", weight: pl._woolWeight });
  });
  const row = document.querySelector(`.flow-row[data-idx="${idx}"]`);
  if (row) row.classList.toggle("flow-highlight", on);
}

function drawFlows(flows) {
  _flows = flows || [];
  _flowLines = [];
  flowLayer.clearLayers();
  decorLayer.clearLayers();

  const ftEl = document.getElementById("flow-table");
  const rtEl = document.getElementById("results-text");

  if (!_flows.length) {
    if (ftEl) ftEl.innerHTML = "";
    return;
  }

  const maxMass = Math.max(..._flows.map(f => f.mass_kg), 1);
  const totalMass = _flows.reduce((s, f) => s + f.mass_kg, 0);

  _flows.forEach((f, idx) => {
    const from = LOCATIONS[f.from_id];
    const to   = LOCATIONS[f.to_id];
    if (!from || !to) { _flowLines.push(null); return; }
    const weight = Math.max(2, Math.min(10, (f.mass_kg / maxMass) * 10));
    const fromName = _entityName(f.from_id);
    const toName   = _entityName(f.to_id);
    const pl = L.polyline([from, to], {
      color: "#e53935", weight, opacity: 0.75, pane: 'flowPane',
    }).bindPopup(
      `<b>${fromName}</b><br>↓ ${f.mass_kg.toFixed(1)} kg<br><b>${toName}</b>`
    ).addTo(flowLayer);
    pl._woolWeight = weight;
    pl._woolIdx   = idx;
    pl.on("mouseover", () => _highlightFlow(idx, true));
    pl.on("mouseout",  () => _highlightFlow(idx, false));
    _flowLines.push(pl);
  });

  // Build flow table in Results tab.
  if (ftEl) {
    let h = `<div class="flow-table-scroll"><table class="table table-sm table-hover table-bordered mb-0">
      <thead><tr>
        <th>From</th><th>To</th><th class="text-end">kg</th><th class="text-end">%</th>
      </tr></thead><tbody>`;
    _flows.forEach((f, idx) => {
      const pct = totalMass ? (f.mass_kg / totalMass * 100).toFixed(1) : "0.0";
      const fromName = escHtml(_entityName(f.from_id));
      const toName   = escHtml(_entityName(f.to_id));
      h += `<tr class="flow-row" data-idx="${idx}" style="cursor:pointer">
        <td title="${fromName}">${fromName}</td>
        <td title="${toName}">${toName}</td>
        <td class="text-end">${f.mass_kg.toFixed(0)}</td>
        <td class="text-end">${pct}%</td>
      </tr>`;
    });
    h += "</tbody></table></div>";
    ftEl.innerHTML = h;
  }
  _renderDecorations();
}

// Redrawn on zoomend so pixel-derived positions stay snapped to the line.
function _renderDecorations() {
  decorLayer.clearLayers();
  if (!_flows.length) return;

  _flows.forEach(f => {
    const from = LOCATIONS[f.from_id];
    const to   = LOCATIONS[f.to_id];
    if (!from || !to) return;

    const fromPx = map.latLngToContainerPoint(L.latLng(from[0], from[1]));
    const toPx   = map.latLngToContainerPoint(L.latLng(to[0],   to[1]));
    const angle  = Math.atan2(toPx.x - fromPx.x, fromPx.y - toPx.y) * 180 / Math.PI;

    const dx = toPx.x - fromPx.x;
    const dy = toPx.y - fromPx.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;

    // Unit perpendicular — always left of travel direction.
    // Each flow from a different direction gets a different perpendicular,
    // so labels naturally spread around convergence nodes.
    const perpX = -dy / len;
    const perpY =  dx / len;
    const labelOffset = 22;

    const arrowLL = map.containerPointToLatLng(L.point(
      fromPx.x + dx * 0.5,
      fromPx.y + dy * 0.5
    ));
    L.marker(arrowLL, {
      icon: L.divIcon({
        className: "",
        html: `<svg width="16" height="16" style="transform:rotate(${angle}deg)">` +
              `<polygon points="8,0 16,16 0,16" fill="#e53935" opacity="0.85"/></svg>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      }),
      pane: 'flowPane',
    }).addTo(decorLayer);
  });

  try {
    sourceLayer.bringToFront();
    techLayer.bringToFront();
    productLayer.bringToFront();
  } catch (e) {}
}

map.on('zoomend', _renderDecorations);

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

// Sidebar resize and collapse.
(function () {
  const sidebarEl  = document.getElementById("sidebar");
  const edgeEl     = document.getElementById("sidebar-edge");
  const toggleBtn  = document.getElementById("sidebar-toggle-btn");
  const mobilBtn   = document.getElementById("mobile-panel-btn");
  const backdrop   = document.getElementById("sidebar-backdrop");
  const mobileQ    = window.matchMedia("(max-width: 767.98px)");

  let _width     = sidebarEl.offsetWidth || 500;
  let _resizing  = false;
  let _collapsed = false;

  function isMobile() { return mobileQ.matches; }

  // Desktop collapse/expand.
  function desktopCollapse(on) {
    _collapsed = on;
    if (on) {
      sidebarEl.style.width    = "0";
      sidebarEl.style.padding  = "0";
      sidebarEl.style.overflow = "hidden";
      toggleBtn.textContent    = "›";
      toggleBtn.title          = "Show panel";
    } else {
      sidebarEl.style.width    = _width + "px";
      sidebarEl.style.padding  = "";
      sidebarEl.style.overflow = "";
      toggleBtn.textContent    = "‹";
      toggleBtn.title          = "Hide panel";
    }
    map.invalidateSize();
  }

  // Mobile overlay open/close.
  function mobileOpen(on) {
    sidebarEl.classList.toggle("sidebar-open", on);
    backdrop.classList.toggle("active", on);
    mobilBtn.style.display = on ? "none" : "";
  }

  // Adapt when breakpoint changes (e.g. window resize / rotation).
  function onBreakpointChange() {
    if (isMobile()) {
      // Reset any desktop inline styles so CSS takes over.
      sidebarEl.style.width    = "";
      sidebarEl.style.padding  = "";
      sidebarEl.style.overflow = "";
      mobileOpen(false);
    } else {
      sidebarEl.classList.remove("sidebar-open");
      backdrop.classList.remove("active");
      mobilBtn.style.display = "";
      // Restore desktop width.
      if (!_collapsed) sidebarEl.style.width = _width + "px";
    }
    map.invalidateSize();
  }
  mobileQ.addEventListener("change", onBreakpointChange);

  // Desktop drag resize.
  edgeEl.addEventListener("mousedown", (e) => {
    if (e.target === toggleBtn) return;
    if (isMobile()) return;
    _resizing = true;
    document.body.style.cursor     = "col-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e) => {
    if (!_resizing) return;
    const left = edgeEl.parentElement.getBoundingClientRect().left;
    const w = Math.max(500, Math.min(650, e.clientX - left));
    sidebarEl.style.width = w + "px";
    _width = w;
    map.invalidateSize();
  });
  document.addEventListener("mouseup", () => {
    if (!_resizing) return;
    _resizing = false;
    document.body.style.cursor     = "";
    document.body.style.userSelect = "";
  });

  // Desktop toggle button.
  toggleBtn.addEventListener("click", () => {
    if (isMobile()) return;
    desktopCollapse(!_collapsed);
  });

  // Mobile open button (on map).
  mobilBtn.addEventListener("click", () => mobileOpen(true));

  // Backdrop closes sidebar on mobile.
  backdrop.addEventListener("click", () => mobileOpen(false));
}());

// Start the app.

// Load quality labels first so the first popups have readable text.
// If that fails, the UI falls back to raw class numbers.
loadQualityClasses().catch(() => {}).then(loadData);
