// EMI Asia Atlas — single-page MapLibre GL drill-down (Asia → country → city).
// WebGL vector rendering of our vendored GeoJSON (no external tiles/keys). Click zooms in/out
// in-place and swaps the side panel. Data in-page: window.ASIA (registry+geo), window.CHINA
// (provinces geo + cities + macro + leverage), window.APAC.{sg,my}. Reuses china.css.
const ASIA = window.ASIA, CHINA = window.CHINA || null, APAC = window.APAC || {};
const CO = ASIA.countries, byName = {}, byCode = {};
CO.forEach((c) => { byName[c.name] = c; byCode[c.code] = c; });
const ORIGIN = { US: "USA", DE: "Germany", JP: "Japan", TW: "Taiwan", KR: "South Korea", NL: "Netherlands", FR: "France", EU: "Europe", CH: "Switzerland", AT: "Austria", CN: "China", AU: "Australia", IN: "India" };
const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const escA = (s) => esc(s).replace(/"/g, "&quot;");
const reduce = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

const RAMP = {
  chip: { stops: ["#eff6ff", "#bfdbfe", "#60a5fa", "#2563eb", "#1e3a8a"], min: 0, max: 100, label: "chip supply-chain weight", val: (c) => c.chip, disp: (c) => c.chip + "/100", pct: (c) => c.chip },
  gdp: { stops: ["#f0fdf4", "#bbf7d0", "#4ade80", "#16a34a", "#14532d"], min: 0, max: 7, label: "GDP growth", val: (c) => c.gdp, disp: (c) => "+" + c.gdp + "%", pct: (c) => (c.gdp / 7) * 100 },
};
function ramp(layer, v) {
  const r = RAMP[layer], t = Math.max(0, Math.min(1, (v - r.min) / (r.max - r.min)));
  const n = r.stops.length - 1, seg = Math.min(n - 1, Math.floor(t * n)), lt = t * n - seg;
  const hx = (x) => [parseInt(x.slice(1, 3), 16), parseInt(x.slice(3, 5), 16), parseInt(x.slice(5, 7), 16)];
  const [a1, b1, c1] = hx(r.stops[seg]), [a2, b2, c2] = hx(r.stops[seg + 1]);
  const m = (u, w) => Math.round(u + (w - u) * lt);
  return `rgb(${m(a1, a2)},${m(b1, b2)},${m(c1, c2)})`;
}
const gdpScale = (g) => ramp("chip", Math.max(8, Math.min(100, (g / 14) * 100)));
function bbox(f) {
  let mnx = 180, mny = 90, mxx = -180, mxy = -90;
  (function scan(co) { if (typeof co[0] === "number") { mnx = Math.min(mnx, co[0]); mxx = Math.max(mxx, co[0]); mny = Math.min(mny, co[1]); mxy = Math.max(mxy, co[1]); } else co.forEach(scan); })(f.geometry.coordinates);
  return [[mnx, mny], [mxx, mxy]];
}

const STATE = { level: "asia", layer: "chip", country: null, city: null };
let map, hovered = null, countryMarkers = [], detailMarkers = [], MAP_READY = false;
const mapDo = (fn) => { if (MAP_READY && map) { try { fn(); } catch (e) {} } };  // run map ops only once GL is ready

// ---- tooltip (#ctip) ----
let tip;
function initTip() { tip = document.getElementById("ctip") || document.body.appendChild(Object.assign(document.createElement("div"), { id: "ctip" })); document.addEventListener("mousemove", (e) => { if (tip.style.display === "block") { tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; } }); }
const showTip = (html, e) => { tip.innerHTML = html; tip.style.display = "block"; tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; };
const hideTip = () => { if (tip) tip.style.display = "none"; };

function colorAsia() {
  ASIA.geo.features.forEach((f) => { const c = byName[f.properties.name]; f.properties.color = c ? ramp(STATE.layer, RAMP[STATE.layer].val(c)) : "#e7edf4"; f.properties.tracked = c ? 1 : 0; });
}
function colorProvinces() {
  if (CHINA && CHINA.geo) CHINA.geo.features.forEach((f) => { const pr = (CHINA.provinces || {})[f.properties.name]; f.properties.color = pr ? gdpScale(pr.gdp || 0) : "#cfe0f0"; });
}
const ASIA_BOUNDS = [[68, -11], [148, 52]];

function clearDetailMarkers() { detailMarkers.forEach((m) => m.remove()); detailMarkers = []; }
function marker(html, cls, lnglat, anchor, onClick) {
  const el = document.createElement("div"); el.className = cls; el.innerHTML = html;
  if (onClick) el.addEventListener("click", (ev) => { ev.stopPropagation(); onClick(); });
  const mk = new maplibregl.Marker({ element: el, anchor: anchor || "left" }).setLngLat(lnglat).addTo(map);
  return mk;
}
function addCountryMarkers() {
  countryMarkers.forEach((m) => m.remove()); countryMarkers = [];
  CO.forEach((c) => {
    const live = c.status === "live";
    const html = `<span class="dot" style="background:${live ? "var(--blue)" : "#94a3b8"}"></span>${esc(c.name)}${live ? " ↗" : ""}`;
    const mk = marker(html, "mk-country" + (live ? " live" : " plan"), [c.lon, c.lat], "left", live ? () => drillCountry(c.code) : null);
    countryMarkers.push(mk);
  });
}
function setMarkersVisible(show) { countryMarkers.forEach((m) => { m.getElement().style.display = show ? "" : "none"; }); }

function initMap() {
  colorAsia();
  map = new maplibregl.Map({
    container: "map", attributionControl: false, dragRotate: false, pitchWithRotate: false, maxZoom: 11, minZoom: 1.4,
    style: { version: 8, sources: {}, glyphs: undefined, layers: [{ id: "bg", type: "background", paint: { "background-color": "#eef3f8" } }] },
    bounds: ASIA_BOUNDS, fitBoundsOptions: { padding: 24 },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.on("load", () => {
    map.addSource("asia", { type: "geojson", data: ASIA.geo, promoteId: "name" });
    map.addLayer({ id: "asia-fill", type: "fill", source: "asia", paint: { "fill-color": ["get", "color"], "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 1, 0.92] } });
    map.addLayer({ id: "asia-line", type: "line", source: "asia", paint: { "line-color": "#ffffff", "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 2, 0.8] } });
    map.on("mousemove", "asia-fill", (e) => {
      const f = e.features[0], c = byName[f.properties.name]; map.getCanvas().style.cursor = c && c.status === "live" ? "pointer" : "";
      if (hovered !== f.id) { if (hovered != null) map.setFeatureState({ source: "asia", id: hovered }, { hover: false }); hovered = f.id; map.setFeatureState({ source: "asia", id: hovered }, { hover: true }); }
      if (c) showTip(`<b>${esc(c.name)}</b> · <span style="color:${c.status === "live" ? "#2563eb" : "#94a3b8"}">${c.status === "live" ? "live ↗ click to drill" : "planned"}</span><br>chip weight <b>${c.chip}</b>/100 · GDP <b>${c.gdp}%</b><br><span style="color:#475569;white-space:normal;display:inline-block;max-width:250px">${esc(c.headline)}</span>`, e.originalEvent); else hideTip();
    });
    map.on("mouseleave", "asia-fill", () => { map.getCanvas().style.cursor = ""; if (hovered != null) map.setFeatureState({ source: "asia", id: hovered }, { hover: false }); hovered = null; hideTip(); });
    map.on("click", "asia-fill", (e) => { const c = byName[e.features[0].properties.name]; if (c && c.status === "live") drillCountry(c.code); });
    MAP_READY = true; addCountryMarkers();
  });
}

// ---- drill ----
function drillCountry(code) {
  const c = byCode[code]; if (!c || c.status !== "live") return;
  STATE.level = "country"; STATE.country = code; STATE.city = null; hideTip();
  mapDo(() => {
    clearDetailMarkers(); setMarkersVisible(false);
    const feat = ASIA.geo.features.find((f) => f.properties.name === c.name);
    if (feat) map.fitBounds(bbox(feat), { padding: 60, maxZoom: 7.5, duration: reduce() ? 0 : 900 });
    else map.flyTo({ center: [c.lon, c.lat], zoom: 7, duration: reduce() ? 0 : 900 });
    if (code === "cn" && CHINA && CHINA.geo) {
      colorProvinces();
      if (!map.getSource("prov")) {
        map.addSource("prov", { type: "geojson", data: CHINA.geo, promoteId: "name" });
        map.addLayer({ id: "prov-fill", type: "fill", source: "prov", paint: { "fill-color": ["get", "color"], "fill-opacity": 0.95 } }, "asia-line");
        map.addLayer({ id: "prov-line", type: "line", source: "prov", paint: { "line-color": "#ffffff", "line-width": 0.5 } }, "asia-line");
      } else { map.getSource("prov").setData(CHINA.geo); setProvVisible(true); }
    } else { setProvVisible(false); }
    addCityDots(code);
  });
  renderPanel(); renderCrumb();
}
function setProvVisible(v) { ["prov-fill", "prov-line"].forEach((id) => { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", v ? "visible" : "none"); }); }
function addCityDots(code) {
  const cities = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  if (code === "sg" && !cities.length) { const sg = byCode.sg; cityDot({ name: "Singapore", lon: sg.lon, lat: sg.lat }, code); return; }
  cities.forEach((ct) => cityDot(ct, code));
}
function cityDot(ct, code) {
  if (ct.lon == null || ct.lat == null) return;
  const html = `<span class="cdot"></span><span class="clab">${esc(ct.name)}</span>`;
  detailMarkers.push(marker(html, "mk-city", [ct.lon, ct.lat], "left", () => drillCity(code, ct.name)));
}
function drillCity(code, name) {
  const list = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const ct = list.find((x) => x.name === name); if (!ct) return;
  STATE.level = "city"; STATE.city = name; hideTip();
  mapDo(() => { if (ct.lon != null) map.flyTo({ center: [ct.lon, ct.lat], zoom: code === "cn" ? 8 : 9.5, duration: reduce() ? 0 : 1000 }); });
  renderPanel(); renderCrumb();
}
function up() {
  if (STATE.level === "city") { STATE.level = "country"; STATE.city = null; const c = byCode[STATE.country], f = ASIA.geo.features.find((x) => x.properties.name === c.name); mapDo(() => { if (f) map.fitBounds(bbox(f), { padding: 60, maxZoom: 7.5, duration: reduce() ? 0 : 800 }); }); renderPanel(); renderCrumb(); }
  else if (STATE.level === "country") goAsia();
}
function goAsia() {
  STATE.level = "asia"; STATE.country = null; STATE.city = null; hideTip();
  mapDo(() => { clearDetailMarkers(); setProvVisible(false); setMarkersVisible(true); map.fitBounds(ASIA_BOUNDS, { padding: 24, duration: reduce() ? 0 : 800 }); });
  renderPanel(); renderCrumb();
}

// ---- panels (shared, DOM-only) ----
function anchorChip(a, code) {
  let name, origin = null, sanc = null;
  if (a && typeof a === "object") { name = a.n; origin = a.o || null; }
  else { name = a; if (code === "cn" && CHINA) { const o = (CHINA.origins || {})[a]; if (o && o.cn === false) origin = o.code; sanc = (CHINA.sanctions || []).find((s) => s.match && a.toLowerCase().indexOf(s.match.toLowerCase()) >= 0) || null; } }
  if (sanc) return `<span class="chip sanc" data-tip="${escA("⚠ " + sanc.name + " · US " + sanc.list + " (" + sanc.date + ")")}">⚠ ${esc(name)}</span>`;
  if (origin) return `<span class="chip foreign" data-tip="${escA("HQ: " + (ORIGIN[origin] || origin))}">${esc(name)}<sup class="orig">${esc(origin)}</sup></span>`;
  return `<span class="chip">${esc(name)}</span>`;
}
function roleBars(nodes) {
  return (nodes || []).slice(0, 6).map((n) => { const col = n.type === "hold" ? "var(--blue)" : "var(--amber)", pct = Math.max(3, Math.min(100, n.share));
    return `<div class="lev-row"><div class="lev-top"><span class="lev-term">${esc(n.node)}</span><span class="lev-val" style="color:${col}">${esc(n.disp)}</span></div><div class="lev-bar"><div class="lev-fill" style="width:${pct}%;background:${col}"></div></div></div>`; }).join("");
}
const macroStrip = (tiles) => `<div class="amx">${(tiles || []).slice(0, 6).map((t) => `<div class="amk"><span>${esc(t.k || t.label)}</span><b>${esc(t.v)}</b></div>`).join("")}</div>`;
function clusterBlock(cl, code) {
  const anch = (cl.anchors || []).map((a) => anchorChip(a, code)).join("");
  return `<div class="cluster l${cl.level}"><div class="cl-top"><span class="cl-seg">${esc(cl.seg)}</span><span class="cl-lvl l${cl.level}">${{ 3: "leading", 2: "strong", 1: "present" }[cl.level] || ""}</span></div><div class="cl-what">${esc(cl.what)}</div>${anch ? `<div class="cl-anch">${anch}</div>` : ""}</div>`;
}
function panelAsia() {
  const r = RAMP[STATE.layer], sorted = CO.slice().sort((a, b) => r.val(b) - r.val(a));
  const rows = sorted.map((c) => { const live = c.status === "live", col = ramp(STATE.layer, r.val(c));
    return `<div class="lev-row arow ${live ? "live" : "planned"}"${live ? ` data-code="${c.code}"` : ""}><div class="lev-top"><span class="lev-term">${esc(c.name)}${live ? " ↗" : ""}</span><span class="lev-scope"><span class="stat-badge ${live ? "live" : "plan"}">${live ? "live" : "soon"}</span></span><span class="lev-val" style="color:${live ? col : "#94a3b8"}">${r.disp(c)}</span></div><div class="lev-bar"><div class="lev-fill" style="width:${Math.max(2, r.pct(c)).toFixed(0)}%;background:${col};opacity:${live ? 1 : .5}"></div></div></div>`; }).join("");
  return `<div class="dos-h"><span class="dos-name">Asia</span><span class="dos-area">ranked by ${r.label}</span></div><div class="arows">${rows}</div><div class="dos-note">Click a live country on the map or list to zoom in.</div>`;
}
function panelCountry(code) {
  if (code === "cn" && CHINA) { const m = CHINA.macro || {};
    return `<div class="dos-h"><span class="dos-name">China</span><span class="dos-area">macro · leverage · cities</span></div>${macroStrip(m.headline)}
      <div class="dos-sec"><h5>Supply-chain leverage</h5>${roleBars(CHINA.leverage)}</div>
      <div class="dos-sec"><h5>Cities <span style="font-weight:400;color:var(--faint)">click a dot or name</span></h5><div class="citylist">${(CHINA.cities || []).map((c) => `<button class="citybtn" data-city="${escA(c.name)}">${esc(c.name)}</button>`).join("")}</div></div>`;
  }
  const d = APAC[code]; if (!d) return "";
  return `<div class="dos-h"><span class="dos-name">${esc(d.name)}</span><span class="dos-area">macro · role${d.cities ? " · cities" : ""}</span></div>
    <div class="dos-tag">${esc(d.tagline || "")}</div>${macroStrip(d.macro)}
    <div class="dos-sec"><h5>Supply-chain role</h5>${roleBars(d.role)}</div>
    ${d.cities ? `<div class="dos-sec"><h5>Cities</h5><div class="citylist">${d.cities.map((c) => `<button class="citybtn" data-city="${escA(c.name)}">${esc(c.name)}</button>`).join("")}</div></div>` : (d.clusters ? `<div class="dos-sec"><h5>Key clusters</h5>${d.clusters.map((cl) => clusterBlock(cl, code)).join("")}</div>` : "")}`;
}
function panelCity(code, name) {
  const list = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const c = list.find((x) => x.name === name); if (!c) return "";
  return `<div class="dos-h"><span class="dos-name">${esc(c.name)}</span>${c.dom ? `<span class="dos-dom" style="background:var(--blue)">${esc(c.dom)}</span>` : ""}</div>
    <div class="dos-tag">${esc(c.tagline || "")}</div>
    ${c.stats ? `<div class="dos-stats">${c.stats.map((s) => `<div class="dos-stat"><div class="k">${esc(s.k)}</div><div class="v">${esc(s.v)}</div></div>`).join("")}</div>` : ""}
    <div class="dos-sec"><h5>Signature strengths</h5>${(c.clusters || []).map((cl) => clusterBlock(cl, code)).join("")}</div>
    ${c.valuechain ? `<div class="dos-sec"><h5>Value-chain role</h5><div class="vc">${esc(c.valuechain)}</div></div>` : ""}`;
}
function renderPanel() {
  const el = document.getElementById("panel");
  el.innerHTML = STATE.level === "asia" ? panelAsia() : STATE.level === "country" ? panelCountry(STATE.country) : panelCity(STATE.country, STATE.city);
  el.scrollTop = 0;
  el.querySelectorAll(".arow.live[data-code]").forEach((b) => b.addEventListener("click", () => drillCountry(b.dataset.code)));
  el.querySelectorAll(".citybtn[data-city]").forEach((b) => b.addEventListener("click", () => drillCity(STATE.country, b.dataset.city)));
}
function renderCrumb() {
  const parts = [`<a data-go="asia">Asia</a>`];
  if (STATE.country) parts.push(`<a data-go="country">${esc(byCode[STATE.country].name)}</a>`);
  if (STATE.city) parts.push(`<span>${esc(STATE.city)}</span>`);
  const bc = document.getElementById("crumb"); bc.innerHTML = parts.join('<span class="sep">›</span>');
  bc.querySelectorAll("[data-go]").forEach((a) => a.addEventListener("click", () => { a.dataset.go === "asia" ? goAsia() : up(); }));
}

function render() {
  document.getElementById("main").innerHTML = `
    <div class="cty-head"><h1>Asia Atlas <span style="font-size:12px;color:var(--muted);font-weight:400">one map · zoom in & out by click — Asia → country → city</span></h1>
      <div class="atlas-crumb" id="crumb"></div></div>
    <div class="maptools"><span class="mt-label">Colour by</span>
      <button class="mapbtn active" data-layer="chip">Chip supply-chain weight</button>
      <button class="mapbtn" data-layer="gdp">GDP growth</button>
      <span class="mt-sep"></span><button class="mapbtn" id="outbtn">⤢ Zoom out</button>
      <span class="mt-label" style="margin-left:auto">scroll = zoom · drag = pan</span></div>
    <div class="citywrap"><div class="citymap" id="map"></div><div class="dossier" id="panel"></div></div>`;
  initTip(); initMap(); renderPanel(); renderCrumb();
  document.querySelectorAll(".mapbtn[data-layer]").forEach((b) => b.addEventListener("click", () => {
    STATE.layer = b.dataset.layer; document.querySelectorAll(".mapbtn[data-layer]").forEach((x) => x.classList.toggle("active", x === b));
    colorAsia(); mapDo(() => { if (map.getSource("asia")) map.getSource("asia").setData(ASIA.geo); });
    if (STATE.level === "asia") renderPanel();
  }));
  document.getElementById("outbtn").addEventListener("click", () => up());
}
render();
