// EMI Asia Atlas — single-page MapLibre GL drill-down (Asia → country → city).
// WebGL vector rendering of our vendored GeoJSON (no external tiles/keys). Click zooms in/out
// in-place and swaps the side panel. Data in-page: window.ASIA (registry+geo), window.CHINA
// (provinces geo + cities + macro + leverage), window.APAC.{sg,my}. Reuses china.css.
const ASIA = window.ASIA, CHINA = window.CHINA || null, APAC = window.APAC || {};
const CO = ASIA.countries, byName = {}, byCode = {};
CO.forEach((c) => { byName[c.name] = c; byCode[c.code] = c; });
const ORIGIN = { US: "USA", DE: "Germany", JP: "Japan", TW: "Taiwan", KR: "South Korea", NL: "Netherlands", FR: "France", EU: "Europe", CH: "Switzerland", AT: "Austria", CN: "China", AU: "Australia", IN: "India" };
// industry-domain colours + taxonomy shading (matches china.html)
const TAXFILL = ["", "#E1F5EE", "#5DCAA5", "#0F6E56"], TAXFG = ["", "#0F6E56", "#04342C", "#fff"], LVLW = { 1: "present", 2: "strong", 3: "leading" };
const domColor = (d) => (CHINA && CHINA.domains && CHINA.domains[d]) ? CHINA.domains[d][1] : "#1d4ed8";
const domName = (d) => (CHINA && CHINA.domains && CHINA.domains[d]) ? CHINA.domains[d][0] : d;
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
let map, hovered = null, countryMarkers = [], detailMarkers = [], MAP_READY = false, drilledName = null;
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
// hide city labels that would overlap (greedy by insertion order); re-runs on every map move/idle.
let declutterRAF = null;
function declutterCityLabels() {
  const els = detailMarkers.map((m) => m.getElement()).filter((el) => el && el.classList.contains("mk-city"));
  els.forEach((el) => { const lab = el.querySelector(".clab"); if (lab) lab.style.display = "inline-block"; });
  const placed = [];
  els.forEach((el) => {
    const lab = el.querySelector(".clab"); if (!lab) return;
    const r = lab.getBoundingClientRect(); if (!r.width) return;
    const hit = placed.some((p) => !(r.right < p.left - 4 || r.left > p.right + 4 || r.bottom < p.top - 2 || r.top > p.bottom + 2));
    if (hit) lab.style.display = "none"; else placed.push(r);
  });
}
const scheduleDeclutter = () => { if (!declutterRAF) declutterRAF = requestAnimationFrame(() => { declutterRAF = null; declutterCityLabels(); }); };

function initMap() {
  colorAsia();
  map = new maplibregl.Map({
    container: "map", attributionControl: false, dragRotate: false, pitchWithRotate: false, maxZoom: 11, minZoom: 1.4,
    style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#eef3f8" } }] },
    bounds: ASIA_BOUNDS, fitBoundsOptions: { padding: 24 },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  const status = Object.assign(document.createElement("div"), { id: "mapstatus", className: "map-status", textContent: "Loading map…" });
  document.getElementById("map").appendChild(status);
  map.on("error", (e) => console.error("[atlas map]", (e && e.error && e.error.message) || e));
  setTimeout(() => { if (!MAP_READY) { const s = document.getElementById("mapstatus"); if (s) { s.textContent = "Map couldn't initialise — reload; if it persists, open the browser console (F12) and send the error."; s.classList.add("err"); } } }, 2800);
  const setup = () => {
    if (MAP_READY || map.getSource("asia")) return;
    map.addSource("asia", { type: "geojson", data: ASIA.geo, promoteId: "name" });
    map.addLayer({ id: "asia-fill", type: "fill", source: "asia", paint: { "fill-color": ["get", "color"], "fill-opacity": ["case", ["boolean", ["feature-state", "drilled"], false], 0, ["boolean", ["feature-state", "hover"], false], 1, 0.92] } });
    map.addLayer({ id: "asia-line", type: "line", source: "asia", paint: { "line-color": "#ffffff", "line-opacity": ["case", ["boolean", ["feature-state", "drilled"], false], 0, 1], "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 2, 0.8] } });
    map.on("mousemove", "asia-fill", (e) => {
      if (STATE.level !== "asia") return;   // once drilled in, provinces/city markers own the hover, not the country
      const f = e.features[0], c = byName[f.properties.name]; map.getCanvas().style.cursor = c && c.status === "live" ? "pointer" : "";
      if (hovered !== f.id) { if (hovered != null) map.setFeatureState({ source: "asia", id: hovered }, { hover: false }); hovered = f.id; map.setFeatureState({ source: "asia", id: hovered }, { hover: true }); }
      if (c) showTip(`<b>${esc(c.name)}</b> · <span style="color:${c.status === "live" ? "#2563eb" : "#94a3b8"}">${c.status === "live" ? "live ↗ click to drill" : "planned"}</span><br>chip weight <b>${c.chip}</b>/100 · GDP <b>${c.gdp}%</b><br><span style="color:#475569;white-space:normal;display:inline-block;max-width:250px">${esc(c.headline)}</span>`, e.originalEvent); else hideTip();
    });
    map.on("mouseleave", "asia-fill", () => { map.getCanvas().style.cursor = ""; if (hovered != null) map.setFeatureState({ source: "asia", id: hovered }, { hover: false }); hovered = null; hideTip(); });
    map.on("click", "asia-fill", (e) => { const c = byName[e.features[0].properties.name]; if (c && c.status === "live") drillCountry(c.code); });
    map.on("move", scheduleDeclutter); map.on("idle", declutterCityLabels);
    MAP_READY = true; addCountryMarkers(); map.resize();
    const s = document.getElementById("mapstatus"); if (s) s.remove();
  };
  if (map.isStyleLoaded()) setup(); else map.on("load", setup);
  [120, 450, 1000].forEach((ms) => setTimeout(() => { try { map.resize(); if (map.isStyleLoaded()) setup(); } catch (e) {} }, ms));
}

// ---- drill ----
function drillCountry(code) {
  const c = byCode[code]; if (!c || c.status !== "live") return;
  STATE.level = "country"; STATE.country = code; STATE.city = null; hideTip();
  mapDo(() => {
    clearDetailMarkers(); setMarkersVisible(false);
    if (drilledName) { map.setFeatureState({ source: "asia", id: drilledName }, { drilled: false }); drilledName = null; }
    if (code === "cn") { map.setFeatureState({ source: "asia", id: c.name }, { drilled: true }); drilledName = c.name; }  // hide China's base fill/outline so its provinces render clean
    const feat = ASIA.geo.features.find((f) => f.properties.name === c.name);
    if (feat) map.fitBounds(bbox(feat), { padding: 70, maxZoom: 7, duration: reduce() ? 0 : 1700, essential: true });
    else map.flyTo({ center: [c.lon, c.lat], zoom: 6.5, duration: reduce() ? 0 : 1700, curve: 1.3, essential: true });
    if (code === "cn" && CHINA && CHINA.geo) {
      colorProvinces();
      if (!map.getSource("prov")) {
        map.addSource("prov", { type: "geojson", data: CHINA.geo, promoteId: "name" });
        map.addLayer({ id: "prov-fill", type: "fill", source: "prov", paint: { "fill-color": ["get", "color"], "fill-opacity": 0.95 } }, "asia-line");
        map.addLayer({ id: "prov-line", type: "line", source: "prov", paint: { "line-color": "#ffffff", "line-width": 0.5 } }, "asia-line");
        map.on("mousemove", "prov-fill", (e) => { const nm = e.features[0].properties.name, pr = (CHINA.provinces || {})[nm]; map.getCanvas().style.cursor = ""; showTip(`<b>${esc(nm)}</b>${pr && pr.gdp != null ? ` · provincial GDP ¥${pr.gdp}T` : ""}`, e.originalEvent); });
        map.on("mouseleave", "prov-fill", hideTip);
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
  const col = code === "cn" ? domColor(ct.dom) : "#1d4ed8";   // colour the dot by industry domain (like china.html)
  const html = `<span class="cdot" style="background:${col};border-color:#fff"></span><span class="clab">${esc(ct.name)}</span>`;
  detailMarkers.push(marker(html, "mk-city", [ct.lon, ct.lat], "left", () => drillCity(code, ct.name)));
}
function drillCity(code, name) {
  const list = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const ct = list.find((x) => x.name === name); if (!ct) return;
  STATE.level = "city"; STATE.city = name; hideTip();
  mapDo(() => { if (ct.lon != null) map.flyTo({ center: [ct.lon, ct.lat], zoom: code === "cn" ? 7.5 : 9, duration: reduce() ? 0 : 1700, curve: 1.4, essential: true }); });
  renderPanel(); renderCrumb();
}
function up() {
  if (STATE.level === "city") { STATE.level = "country"; STATE.city = null; const c = byCode[STATE.country], f = ASIA.geo.features.find((x) => x.properties.name === c.name); mapDo(() => { if (f) map.fitBounds(bbox(f), { padding: 70, maxZoom: 7, duration: reduce() ? 0 : 1400, essential: true }); }); renderPanel(); renderCrumb(); }
  else if (STATE.level === "country") goAsia();
}
function goAsia() {
  STATE.level = "asia"; STATE.country = null; STATE.city = null; hideTip();
  mapDo(() => { clearDetailMarkers(); setProvVisible(false); setMarkersVisible(true); if (drilledName) { map.setFeatureState({ source: "asia", id: drilledName }, { drilled: false }); drilledName = null; } map.fitBounds(ASIA_BOUNDS, { padding: 24, duration: reduce() ? 0 : 1400, essential: true }); });
  renderPanel(); renderCrumb();
}

// ---- macro digest tiles + leverage (ported from the China page) ----
function viewSeries(it) {
  const v = it.view || { metric: "value", ref: 0, good: "high" }, raw = it.series || []; let s2;
  if (v.metric === "yoy") { s2 = []; for (let i = 1; i < raw.length; i++) { const p = raw[i - 1][1], c = raw[i][1]; if (p) s2.push([raw[i][0], +((c - p) / Math.abs(p) * 100).toFixed(1)]); } }
  else s2 = raw.map((r) => [r[0], r[1]]);
  const latest = s2.length ? s2[s2.length - 1][1] : null, prior = s2.length > 1 ? s2[s2.length - 2][1] : null, ref = v.ref != null ? v.ref : 0;
  const trend = (latest != null && prior != null) ? (latest > prior ? "accelerating" : latest < prior ? "cooling" : "flat") : "flat";
  return { s2, latest, prior, ref, band: v.band, good: v.good, metric: v.metric, trend };
}
function digest(vw) {
  if (vw.latest == null) return { color: "var(--muted)", read: "" };
  if (vw.good === "none") return { color: "var(--ink)", read: "" };
  const x = vw.latest, b = vw.band || [1, 3]; let read, color;
  if (vw.good === "band") { if (x < b[0]) { read = "deflation risk"; color = "var(--amber)"; } else if (x > b[1]) { read = "too hot"; color = "var(--red)"; } else { read = "healthy"; color = "var(--green)"; } }
  else if (vw.good === "low") { read = x <= vw.ref ? "contained" : "elevated"; color = x <= vw.ref ? "var(--green)" : "var(--red)"; }
  else { color = x >= vw.ref ? "var(--green)" : "var(--red)"; read = (vw.ref === 50) ? (x >= 50 ? "expansion" : "contraction") : (x < vw.ref ? "negative" : (vw.prior != null ? vw.trend : "positive")); }
  return { color, read };
}
function digestStr(it, vw) {
  const dg = digest(vw); if (vw.latest == null || (it.view && it.view.good === "none")) return { color: dg.color, txt: "" };
  const dunit = vw.ref === 50 ? "" : "%", valStr = vw.metric === "yoy" ? ((vw.latest >= 0 ? "+" : "") + vw.latest + "% YoY") : (vw.latest + dunit);
  return { color: dg.color, txt: valStr + (dg.read ? " · " + dg.read : "") };
}
function sparkBars(vw) {
  const s = vw.s2; if (!s || s.length < 2) return ""; const w = 150, h = 30;
  const vals = s.map((p) => p[1]).concat([vw.ref]), mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1;
  const y = (v) => h - 3 - ((v - mn) / rng) * (h - 6), refY = +y(vw.ref).toFixed(1), bw = (w - 2) / s.length;
  const good = (v) => vw.good === "low" ? v <= vw.ref : vw.good === "band" ? (v >= vw.band[0] && v <= vw.band[1]) : v >= vw.ref;
  let bars = ""; s.forEach((p, i) => { const x = (1 + i * bw).toFixed(1), vy = y(p[1]), top = Math.min(vy, refY).toFixed(1), ht = Math.max(1.5, Math.abs(vy - refY)).toFixed(1);
    const c = vw.good === "none" ? "#94a3b8" : (good(p[1]) ? "#16a34a" : (vw.good === "band" && p[1] < vw.band[0] ? "#d97706" : "#dc2626"));
    bars += `<rect x="${x}" y="${top}" width="${(bw - 1.3).toFixed(1)}" height="${ht}" rx="1" fill="${c}" opacity="0.82"/>`; });
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${bars}<line x1="0" y1="${refY}" x2="${w}" y2="${refY}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="3 2"/></svg>`;
}
const tileFoot = (it) => `<span class="asof">as of ${esc(it.as_of)} · ${esc(it.source || "")}</span>`;
function macroTile(it) {
  const vw = viewSeries(it), neutral = it.view && it.view.good === "none", dg = digestStr(it, vw);
  const verdict = neutral ? (it.note ? `<div class="digest" style="color:var(--muted)">${esc(it.note)}</div>` : "") : (dg.txt ? `<div class="digest" style="color:${dg.color}">${esc(dg.txt)}</div>` : "");
  const spk = (vw.s2 && vw.s2.length > 1) ? `<div class="spk">${sparkBars(vw)}</div>` : "";
  return `<div class="kpi nostatic"><div class="lbl">${esc(it.k || it.label)}</div><div class="val">${esc(it.v)}</div>${verdict}${spk}<div class="src">${tileFoot(it)}</div></div>`;
}
function leverageHTML(nodes, take) {
  const row = (n) => { const col = n.type === "hold" ? "var(--blue)" : "var(--amber)", pct = Math.max(3, Math.min(100, n.share));
    return `<div class="lev-row"><div class="lev-top"><span class="lev-term">${esc(n.node)}</span><span class="lev-scope">${esc(n.scope || "")}</span><span class="lev-val" style="color:${col}">${esc(n.disp)}</span></div><div class="lev-bar"><div class="lev-fill" style="width:${pct}%;background:${col}"></div></div></div>`; };
  const grp = (type, title, cap) => { const r = (nodes || []).filter((n) => n.type === type); return r.length ? `<div class="lev-grp"><div class="lev-h">${title} <span class="lev-cap">${cap}</span></div><div class="lev-rows">${r.map(row).join("")}</div></div>` : ""; };
  return (take ? `<div class="lev-take">${esc(take)}</div>` : "") + `<div class="levmap">${grp("hold", "Where it leads", "· strengths")}${grp("gap", "Where it lags / depends", "· gaps")}</div>`;
}
function countryTilesHTML(code) {
  if (code === "cn" && CHINA) {
    const head = (CHINA.macro && CHINA.macro.headline) || [], more = (CHINA.macro && CHINA.macro.more) || [];
    return `<div class="sech">China · macro snapshot <span class="dim">latest official prints</span></div>
      <div class="kpis">${head.map(macroTile).join("")}</div>
      ${more.length ? `<div class="sech">More indicators <span class="dim">trade · money · labour</span></div><div class="kpis">${more.map(macroTile).join("")}</div>` : ""}
      <div class="sech">Supply-chain leverage</div>${leverageHTML(CHINA.leverage, "")}`;
  }
  const d = APAC[code]; if (!d) return "";
  return `<div class="sech">${esc(d.name)} · macro snapshot <span class="dim">latest official prints</span></div>
    <div class="kpis">${(d.macro || []).map(macroTile).join("")}</div>
    <div class="sech">Supply-chain role</div>${leverageHTML(d.role, d.role_take || "")}`;
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
function cityCardsHTML(code) {
  const d = code === "cn" ? CHINA : APAC[code]; if (!d) return "";
  const cities = code === "cn" ? (CHINA.cities || []) : (d.cities || []);
  if (!cities.length && d.clusters) return `<div class="dos-h"><span class="dos-name">Key clusters</span></div>${d.clusters.map((cl) => clusterBlock(cl, code)).join("")}`;
  return `<div class="dos-h"><span class="dos-name">Cities</span><span class="dos-area">${cities.length} · click to drill</span></div>
    <div class="citycards">${cities.map((c) => `<button class="citycard" data-city="${escA(c.name)}"><b>${esc(c.name)}${c.dom ? ` <span class="cc-dom">${esc(c.dom)}</span>` : ""}</b><span>${esc((c.tagline || c.area || "").slice(0, 92))}</span></button>`).join("")}</div>`;
}
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
function panelCity(code, name) {
  const list = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const c = list.find((x) => x.name === name); if (!c) return "";
  let h = `<div class="dos-h"><span class="dos-name">${esc(c.name)}</span>${c.dom ? `<span class="dos-dom" style="background:${domColor(c.dom)}">${esc(domName(c.dom))}</span>` : ""}</div>`;
  h += `<div class="dos-tag">${esc(c.tagline || "")}</div>`;
  if (c.stats && c.stats.length) h += `<div class="dos-stats">${c.stats.map((s) => `<div class="dos-stat"><div class="k">${esc(s.k)}</div><div class="v">${esc(s.v)}</div></div>`).join("")}</div>`;
  if (c.clusters && c.clusters.length) h += `<div class="dos-sec"><h5>Signature strengths</h5>
    <div class="dos-legend"><span><i class="dot cn"></i>Local</span><span><i class="dot for"></i>Foreign HQ</span><span class="sanc-leg">⚠ US-restricted</span><span class="leg-hint">· hover a company for HQ</span></div>
    ${c.clusters.map((cl) => clusterBlock(cl, code)).join("")}</div>`;
  if (c.subdistricts && c.subdistricts.length) h += `<div class="dos-sec"><h5>Sub-district clusters</h5>${c.subdistricts.map((s) => `<div class="sub-row"><b>${esc(s.name)}</b><span>${esc(s.focus)}</span></div>`).join("")}</div>`;
  if (c.valuechain) h += `<div class="dos-sec"><h5>Value-chain role</h5><div class="vc">${esc(c.valuechain)}</div></div>`;
  if (c.sourcing) h += `<div class="dos-sec"><h5>For an electronics distributor</h5><div class="src2">
    <div><div class="lbl">Source here</div><ul>${(c.sourcing.buy || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    <div><div class="lbl">Sell into here</div><ul>${(c.sourcing.sell || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div></div></div>`;
  if (c.tags && CHINA && CHINA.taxonomy) {
    const cells = CHINA.taxonomy.map((t) => { const v = c.tags[t] || 0, bg = v ? `background:${TAXFILL[v]}` : "background:#fafbfd;border:1px solid var(--line)";
      return `<div class="taxc" style="${bg};color:${TAXFG[v] || "#cbd5e1"}" data-tip="${escA(t + ": " + (v ? LVLW[v] : "—"))}"><div class="tl">${esc(t.slice(0, 8))}</div><div class="tv">${v ? "●".repeat(v) : "·"}</div></div>`; }).join("");
    h += `<div class="dos-sec"><h5>Manufacturing-type strength</h5><div class="taxg">${cells}</div></div>`;
  }
  if (c.note) h += `<div class="dos-note">${esc(c.note)}</div>`;
  return h;
}
function renderPanel() {
  const tilesEl = document.getElementById("tiles"), el = document.getElementById("panel");
  if (STATE.level === "asia") { tilesEl.style.display = "none"; tilesEl.innerHTML = ""; el.innerHTML = panelAsia(); }
  else {
    tilesEl.style.display = ""; tilesEl.innerHTML = countryTilesHTML(STATE.country);
    el.innerHTML = STATE.level === "country" ? cityCardsHTML(STATE.country) : panelCity(STATE.country, STATE.city);
  }
  el.scrollTop = 0;
  el.querySelectorAll(".arow.live[data-code]").forEach((b) => b.addEventListener("click", () => drillCountry(b.dataset.code)));
  el.querySelectorAll("[data-city]").forEach((b) => b.addEventListener("click", () => drillCity(STATE.country, b.dataset.city)));
  const dl = document.getElementById("domlegend");
  if (dl) {
    if (STATE.level !== "asia" && STATE.country === "cn" && CHINA && CHINA.domains) {
      dl.style.display = ""; dl.innerHTML = `<span class="dim">Map dots —</span>` + Object.keys(CHINA.domains).map((d) => `<span><i style="color:${CHINA.domains[d][1]}">●</i> ${esc(CHINA.domains[d][0])}</span>`).join("");
    } else dl.style.display = "none";
  }
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
    <div class="atlas-tiles" id="tiles" style="display:none"></div>
    <div class="legend" id="domlegend" style="display:none;margin:0 0 8px"></div>
    <div class="citywrap"><div class="citymap" id="map"></div><div class="dossier" id="panel"></div></div>`;
  initTip(); renderPanel(); renderCrumb(); initMap();
  // the timed map.resize() calls inside initMap() cure any 0-size-at-init (flex not yet laid out)
  document.querySelectorAll(".mapbtn[data-layer]").forEach((b) => b.addEventListener("click", () => {
    STATE.layer = b.dataset.layer; document.querySelectorAll(".mapbtn[data-layer]").forEach((x) => x.classList.toggle("active", x === b));
    colorAsia(); mapDo(() => { if (map.getSource("asia")) map.getSource("asia").setData(ASIA.geo); });
    if (STATE.level === "asia") renderPanel();
  }));
  document.getElementById("outbtn").addEventListener("click", () => up());
}
render();
