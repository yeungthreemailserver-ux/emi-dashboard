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
// ---- i18n (简体中文 toggle; China content has zh data, others fall back to English) ----
const Z = () => STATE.lang === "zh";
const READ_ZH = { cooling: "放缓", accelerating: "加速", flat: "持平", positive: "正增长", negative: "负增长", expansion: "扩张", contraction: "收缩", healthy: "健康", "deflation risk": "通缩风险", "too hot": "过热", contained: "受控", elevated: "偏高", rising: "上升", easing: "回落" };
const COUNTRY_ZH = { cn: "中国", sg: "新加坡", my: "马来西亚", tw: "台湾", kr: "韩国", jp: "日本", vn: "越南", ph: "菲律宾", th: "泰国", in: "印度" };
const TT = {
  sub_head: ["one map · zoom in & out by click — Asia → country → city", "一张地图 · 点击放大缩小 — 亚洲 → 国家 → 城市"],
  colourby: ["Colour by", "着色依据"], chip: ["Chip supply-chain weight", "芯片供应链权重"], gdp: ["GDP growth", "GDP 增速"], zoomout: ["⤢ Zoom out", "⤢ 缩小"], pan: ["scroll = zoom · drag = pan", "滚轮缩放 · 拖动平移"],
  macrosnap: ["macro snapshot", "宏观快照"], prints: ["latest official prints", "最新官方数据"], more_ind: ["More indicators", "更多指标"], more_sub: ["trade · money · labour", "贸易 · 货币 · 就业"],
  leverage: ["Supply-chain leverage", "供应链杠杆"], role: ["Supply-chain role", "供应链角色"], leads: ["Where it leads", "领先环节"], lags: ["Where it lags / depends", "受制 / 依赖环节"], t_str: ["· strengths", "· 优势"], t_gap: ["· gaps", "· 短板"],
  cities: ["Cities", "城市"], clickdrill: ["click to drill", "点击进入"], keyclusters: ["Key clusters", "核心集群"],
  sig: ["Signature strengths", "核心强项"], subd: ["Sub-district clusters", "次级区域集群"], vc: ["Value-chain role", "价值链定位"], dist: ["For an electronics distributor", "对电子分销商而言"], buy: ["Source here", "可在此采购"], sell: ["Sell into here", "可向此销售"], mfg: ["Manufacturing-type strength", "制造类型强度"],
  lg_local: ["Local", "本土"], lg_for: ["Foreign HQ", "境外总部"], lg_sanc: ["US-restricted", "美国管制"], lg_hint: ["· hover a company for HQ", "· 悬停查看公司总部"],
  rankby: ["ranked by", "排名依据"], chipw: ["chip supply-chain weight", "芯片供应链权重"], gdpg: ["GDP growth", "GDP 增速"], live: ["live", "在营"], soon: ["soon", "即将"], clickzoom: ["Click a live country on the map or list to zoom in.", "点击地图或列表中在营的国家放大查看。"], mapdots: ["Map dots —", "地图圆点 —"],
  switch_hint: ["live ↗ click to switch", "在营 ↗ 点击切换"], planned_hint: ["planned · not yet mapped", "规划中 · 暂未收录"],
  role_l: ["Manufacturing profile", "制造画像"], vc_sub: ["the electronics demand map · by industry", "电子需求地图 · 按行业"],
  drivers: ["Demand drivers — fastest-rising end-markets", "需求驱动 — 增长最快的终端市场"], explore: ["Explore a live country", "进入在营国家"],
  vc_title: ["Where each industry manufactures", "各行业的制造分布"], vc_titlesub: ["electronics-consuming manufacturing across Asia · shade = scale of presence", "亚洲电子制造分布 · 深浅 = 规模"],
  maprole: ["Map colour = manufacturing profile —", "地图颜色 = 制造画像 —"], vc_foot: ["Scale of each industry's electronics manufacturing · hover a cell for OEMs & the components it pulls", "各行业电子制造规模 · 悬停看 OEM 与所需元件"],
};
const tt = (k) => { const e = TT[k]; return e ? (Z() ? e[1] : e[0]) : k; };
const domName = (d) => (CHINA && CHINA.domains && CHINA.domains[d]) ? (Z() ? (CHINA.domains[d][2] || CHINA.domains[d][0]) : CHINA.domains[d][0]) : d;
const cityName = (c) => (Z() && c.name_zh) ? c.name_zh : c.name;
const countryName = (code) => (Z() && COUNTRY_ZH[code]) ? COUNTRY_ZH[code] : (byCode[code] ? byCode[code].name : code);
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
// Frame the *cities* (where the content is), not the whole country polygon — so drilling into
// China centres on the populated east instead of leaving it stranded above empty Xinjiang/Tibet.
function cityBounds(code) {
  const cities = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const pts = (cities || []).filter((c) => c.lon != null && c.lat != null);
  if (pts.length < 2) return null;
  let mnx = 180, mny = 90, mxx = -180, mxy = -90;
  pts.forEach((c) => { mnx = Math.min(mnx, c.lon); mxx = Math.max(mxx, c.lon); mny = Math.min(mny, c.lat); mxy = Math.max(mxy, c.lat); });
  return [[mnx, mny], [mxx, mxy]];
}

const STATE = { level: "asia", layer: "role", country: null, city: null, lang: "en" };
let map, hovered = null, countryMarkers = [], detailMarkers = [], MAP_READY = false, drilledName = null;
const mapDo = (fn) => { if (MAP_READY && map) { try { fn(); } catch (e) {} } };  // run map ops only once GL is ready

// ---- tooltip (#ctip) ----
let tip;
function initTip() {
  tip = document.getElementById("ctip") || document.body.appendChild(Object.assign(document.createElement("div"), { id: "ctip" }));
  document.addEventListener("mousemove", (e) => { if (tip.style.display === "block") { tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; } });
  // delegated [data-tip] tooltips for panel/matrix DOM (the map sets its own tips directly)
  document.addEventListener("mouseover", (e) => { const t = e.target.closest ? e.target.closest("[data-tip]") : null; if (t && t.getAttribute("data-tip")) { tip.textContent = t.getAttribute("data-tip"); tip.style.display = "block"; tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; } });
  document.addEventListener("mouseout", (e) => { if (e.target.closest && e.target.closest("[data-tip]")) hideTip(); });
}
const showTip = (html, e) => { tip.innerHTML = html; tip.style.display = "block"; tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; };
const hideTip = () => { if (tip) tip.style.display = "none"; };

function colorAsia() {
  ASIA.geo.features.forEach((f) => { const c = byName[f.properties.name];
    f.properties.color = c ? (c.rc || "#cbd5e1") : "#ece7dc";   // covered → manufacturing-profile colour; other land → neutral (matches world land)
    f.properties.tracked = c ? 1 : 0; });
}
function colorProvinces() {
  if (CHINA && CHINA.geo) CHINA.geo.features.forEach((f) => { const pr = (CHINA.provinces || {})[f.properties.name]; f.properties.color = pr ? gdpScale(pr.gdp || 0) : "#cfe0f0"; });
}
const ASIA_BOUNDS = [[66, -48], [179, 54]];   // Asia-Pacific incl. Australia & New Zealand

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
    const html = `<span class="dot" style="background:${live ? "var(--blue)" : "#94a3b8"}"></span>${esc(countryName(c.code))}${live ? " ↗" : ""}`;
    const mk = marker(html, "mk-country" + (live ? " live" : " plan"), [c.lon, c.lat], "left", live ? () => drillCountry(c.code) : null);
    countryMarkers.push(mk);
  });
  scheduleDeclutter();
}
function setMarkersVisible(show) { countryMarkers.forEach((m) => { m.getElement().style.display = show ? "" : "none"; }); }
// hide city labels that would overlap (greedy by insertion order); re-runs on every map move/idle.
let declutterRAF = null;
function declutterCityLabels() {
  const els = detailMarkers.map((m) => m.getElement()).filter((el) => el && el.classList.contains("mk-city"));
  els.forEach((el) => { const lab = el.querySelector(".clab"); if (lab) { lab.style.display = ""; lab.classList.remove("clab-right", "clab-bottom", "clab-left"); } });
  // obstacles: seed with every city dot so a label never lands on another city's dot
  const placed = [];
  els.forEach((el) => { const dot = el.querySelector(".cdot"); if (dot) { const dr = dot.getBoundingClientRect(); if (dr.width) placed.push(dr); } });
  const clear = (r, p) => (r.right < p.left - 3 || r.left > p.right + 3 || r.bottom < p.top - 2 || r.top > p.bottom + 2);
  els.forEach((el) => {
    const lab = el.querySelector(".clab"); if (!lab) return;
    let ok = false;
    for (const pos of ["top", "right", "bottom", "left"]) {   // try each side; use the first that fits the empty space before giving up
      lab.classList.remove("clab-right", "clab-bottom", "clab-left");
      if (pos !== "top") lab.classList.add("clab-" + pos);
      const r = lab.getBoundingClientRect();
      if (!r.width) { ok = true; break; }   // unmeasurable (headless preview) — leave the default position visible
      if (placed.every((p) => clear(r, p))) { placed.push(r); ok = true; break; }
    }
    if (!ok) { lab.classList.remove("clab-right", "clab-bottom", "clab-left"); lab.style.display = "none"; }
  });
}
// same idea for the country pills at the Asia level — hide labels that overlap (greedy by importance);
// the coloured country shape stays clickable, and hidden labels reappear as you zoom in.
function declutterCountryLabels() {
  const els = countryMarkers.map((m) => m.getElement()).filter(Boolean);
  els.forEach((el) => { el.style.visibility = ""; });
  const placed = [], clear = (r, p) => (r.right < p.left - 2 || r.left > p.right + 2 || r.bottom < p.top - 2 || r.top > p.bottom + 2);
  els.forEach((el) => { if (el.style.display === "none") return; const r = el.getBoundingClientRect(); if (!r.width) return; if (placed.every((p) => clear(r, p))) placed.push(r); else el.style.visibility = "hidden"; });
}
function declutterMarkers() { if (STATE.level === "asia") declutterCountryLabels(); else declutterCityLabels(); }
const scheduleDeclutter = () => { if (!declutterRAF) declutterRAF = requestAnimationFrame(() => { declutterRAF = null; declutterMarkers(); }); };

function graticule(step) {   // lat/long grid as GeoJSON line features
  step = step || 20; const fs = [];
  for (let lng = -180; lng <= 180; lng += step) { const c = []; for (let lat = -80; lat <= 80; lat += 2) c.push([lng, lat]); fs.push({ type: "Feature", geometry: { type: "LineString", coordinates: c } }); }
  for (let lat = -80; lat <= 80; lat += step) { const c = []; for (let lng = -180; lng <= 180; lng += 4) c.push([lng, lat]); fs.push({ type: "Feature", geometry: { type: "LineString", coordinates: c } }); }
  return { type: "FeatureCollection", features: fs };
}
function initMap() {
  colorAsia();
  map = new maplibregl.Map({
    container: "map", attributionControl: false, dragRotate: false, pitchWithRotate: false, maxZoom: 11, minZoom: 1.4, preserveDrawingBuffer: true,
    style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#aecbe8" } }] },
    bounds: ASIA_BOUNDS, fitBoundsOptions: { padding: 24 },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  const status = Object.assign(document.createElement("div"), { id: "mapstatus", className: "map-status", textContent: "Loading map…" });
  document.getElementById("map").appendChild(status);
  map.on("error", (e) => console.error("[atlas map]", (e && e.error && e.error.message) || e));
  setTimeout(() => { if (!MAP_READY) { const s = document.getElementById("mapstatus"); if (s) { s.textContent = "Map couldn't initialise — reload; if it persists, open the browser console (F12) and send the error."; s.classList.add("err"); } } }, 2800);
  const setup = () => {
    if (MAP_READY || map.getSource("asia")) return;
    // graticule (faint grid, drawn over ocean — land covers it) → a subtle "atlas" feel
    map.addSource("grid", { type: "geojson", data: graticule(20) });
    map.addLayer({ id: "grid-line", type: "line", source: "grid", paint: { "line-color": "rgba(255,255,255,0.55)", "line-width": 0.6 } });
    // world land context so countries don't float on blue (Natural Earth, vendored, no key)
    map.addSource("world", { type: "geojson", data: "vendor/world-land-50m.geojson" });
    map.addLayer({ id: "world-fill", type: "fill", source: "world", paint: { "fill-color": "#ece7dc" } });
    map.addSource("asia", { type: "geojson", data: ASIA.geo, promoteId: "name" });
    map.addLayer({ id: "asia-fill", type: "fill", source: "asia", paint: { "fill-color": ["get", "color"], "fill-opacity": ["case", ["boolean", ["feature-state", "drilled"], false], 0, ["boolean", ["feature-state", "hover"], false], 1, 0.92] } });
    map.addLayer({ id: "asia-line", type: "line", source: "asia", paint: { "line-color": "#ffffff", "line-opacity": ["case", ["boolean", ["feature-state", "drilled"], false], 0, 1], "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 2, 0.8] } });
    map.on("mousemove", "asia-fill", (e) => {
      const f = e.features[0], c = byName[f.properties.name], drilledIn = STATE.level !== "asia";
      // the country you're already inside is owned by its provinces / city markers — no country tip for it
      if (drilledIn && c && c.code === STATE.country) { map.getCanvas().style.cursor = ""; if (hovered != null) { map.setFeatureState({ source: "asia", id: hovered }, { hover: false }); hovered = null; } return; }
      map.getCanvas().style.cursor = c && c.status === "live" ? "pointer" : "";
      if (hovered !== f.id) { if (hovered != null) map.setFeatureState({ source: "asia", id: hovered }, { hover: false }); hovered = f.id; map.setFeatureState({ source: "asia", id: hovered }, { hover: true }); }
      if (!c) { hideTip(); return; }
      if (drilledIn)   // drilled in: hint that the other countries on screen are switchable
        showTip(`<b>${esc(countryName(c.code))}</b> · <span style="color:${c.status === "live" ? "#2563eb" : "#94a3b8"}">${c.status === "live" ? tt("switch_hint") : tt("planned_hint")}</span>`, e.originalEvent);
      else
        showTip(`<b>${esc(c.name)}</b> · <span style="color:${c.status === "live" ? "#2563eb" : "#94a3b8"}">${c.status === "live" ? "live ↗ click to drill" : "planned"}</span><br>chip weight <b>${c.chip}</b>/100 · GDP <b>${c.gdp}%</b><br><span style="color:#475569;white-space:normal;display:inline-block;max-width:250px">${esc(c.headline)}</span>`, e.originalEvent);
    });
    map.on("mouseleave", "asia-fill", () => { map.getCanvas().style.cursor = ""; if (hovered != null) map.setFeatureState({ source: "asia", id: hovered }, { hover: false }); hovered = null; hideTip(); });
    map.on("click", "asia-fill", (e) => { const c = byName[e.features[0].properties.name]; if (c && c.status === "live" && c.code !== STATE.country) drillCountry(c.code); });
    map.on("move", scheduleDeclutter); map.on("idle", declutterMarkers);
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
    if (map.getLayer("asia-fill")) map.setPaintProperty("asia-fill", "fill-color", "#ece7dc");  // neutralise neighbours while drilled — only the drilled country is the focus
    if (drilledName) { map.setFeatureState({ source: "asia", id: drilledName }, { drilled: false }); drilledName = null; }
    if (code === "cn") { map.setFeatureState({ source: "asia", id: c.name }, { drilled: true }); drilledName = c.name; }  // hide China's base fill/outline so its provinces render clean
    const feat = ASIA.geo.features.find((f) => f.properties.name === c.name), cb = cityBounds(code);
    const pad = { top: 64, bottom: 64, left: 56, right: 56 };
    if (cb) map.fitBounds(cb, { padding: pad, maxZoom: 7, duration: reduce() ? 0 : 1700, essential: true });
    else if (feat) map.fitBounds(bbox(feat), { padding: 70, maxZoom: 7, duration: reduce() ? 0 : 1700, essential: true });
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
  const col = ct.dom ? domColor(ct.dom) : "#1d4ed8";   // colour the dot by industry domain (China + APAC cities carry .dom)
  const html = `<span class="cdot" style="background:${col};border-color:#fff"></span><span class="clab">${esc(cityName(ct))}</span>`;
  detailMarkers.push(marker(html, "mk-city", [ct.lon, ct.lat], "center", () => drillCity(code, ct.name)));  // dot on the coord, label floats centred above it
}
function drillCity(code, name) {
  const list = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const ct = list.find((x) => x.name === name); if (!ct) return;
  STATE.level = "city"; STATE.city = name; hideTip();
  mapDo(() => { if (ct.lon != null) map.flyTo({ center: [ct.lon, ct.lat], zoom: code === "cn" ? 7.5 : 9, duration: reduce() ? 0 : 1700, curve: 1.4, essential: true }); });
  renderPanel(); renderCrumb();
}
function up() {
  if (STATE.level === "city") { STATE.level = "country"; STATE.city = null; const code = STATE.country, c = byCode[code], f = ASIA.geo.features.find((x) => x.properties.name === c.name), cb = cityBounds(code); mapDo(() => { if (cb) map.fitBounds(cb, { padding: { top: 64, bottom: 64, left: 56, right: 56 }, maxZoom: 7, duration: reduce() ? 0 : 1400, essential: true }); else if (f) map.fitBounds(bbox(f), { padding: 70, maxZoom: 7, duration: reduce() ? 0 : 1400, essential: true }); }); renderPanel(); renderCrumb(); }
  else if (STATE.level === "country") goAsia();
}
function goAsia() {
  STATE.level = "asia"; STATE.country = null; STATE.city = null; hideTip();
  mapDo(() => { clearDetailMarkers(); setProvVisible(false); setMarkersVisible(true); if (map.getLayer("asia-fill")) map.setPaintProperty("asia-fill", "fill-color", ["get", "color"]); if (drilledName) { map.setFeatureState({ source: "asia", id: drilledName }, { drilled: false }); drilledName = null; } map.fitBounds(ASIA_BOUNDS, { padding: 24, duration: reduce() ? 0 : 1400, essential: true }); });
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
  return { color, read: Z() ? (READ_ZH[read] || read) : read };
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
  const lbl = Z() ? (it.k_zh || it.k || it.label) : (it.k || it.label);
  return `<div class="kpi nostatic"><div class="lbl">${esc(lbl)}</div><div class="val">${esc(it.v)}</div>${verdict}${spk}<div class="src">${tileFoot(it)}</div></div>`;
}
function leverageHTML(nodes, take) {
  const row = (n) => { const col = n.type === "hold" ? "var(--blue)" : "var(--amber)", pct = Math.max(3, Math.min(100, n.share));
    return `<div class="lev-row"><div class="lev-top"><span class="lev-term">${esc(n.node)}</span><span class="lev-scope">${esc(n.scope || "")}</span><span class="lev-val" style="color:${col}">${esc(n.disp)}</span></div><div class="lev-bar"><div class="lev-fill" style="width:${pct}%;background:${col}"></div></div></div>`; };
  const grp = (type, title, cap) => { const r = (nodes || []).filter((n) => n.type === type); return r.length ? `<div class="lev-grp"><div class="lev-h">${title} <span class="lev-cap">${cap}</span></div><div class="lev-rows">${r.map(row).join("")}</div></div>` : ""; };
  return (take ? `<div class="lev-take">${esc(take)}</div>` : "") + `<div class="levmap">${grp("hold", tt("leads"), tt("t_str"))}${grp("gap", tt("lags"), tt("t_gap"))}</div>`;
}
function countryTilesHTML(code) {
  if (code === "cn" && CHINA) {
    const head = (CHINA.macro && CHINA.macro.headline) || [], more = (CHINA.macro && CHINA.macro.more) || [];
    return `<div class="sech">${countryName("cn")} · ${tt("macrosnap")} <span class="dim">${tt("prints")}</span></div>
      <div class="kpis">${head.map(macroTile).join("")}</div>
      ${more.length ? `<div class="sech">${tt("more_ind")} <span class="dim">${tt("more_sub")}</span></div><div class="kpis">${more.map(macroTile).join("")}</div>` : ""}
      <div class="sech">${tt("leverage")}</div>${leverageHTML(CHINA.leverage, "")}`;
  }
  const d = APAC[code]; if (!d) return "";
  return `<div class="sech">${countryName(code)} · ${tt("macrosnap")} <span class="dim">${tt("prints")}</span></div>
    <div class="kpis">${(d.macro || []).map(macroTile).join("")}</div>
    <div class="sech">${tt("role")}</div>${leverageHTML(d.role, d.role_take || "")}`;
}

// ---- panels (shared, DOM-only) ----
function anchorChip(a, code) {
  const raw = (a && typeof a === "object") ? a.n : a;
  let origin = null, sanc = null;
  if (a && typeof a === "object") origin = a.o || null;
  else if (code === "cn" && CHINA) { const o = (CHINA.origins || {})[raw]; if (o && o.cn === false) origin = o.code; sanc = (CHINA.sanctions || []).find((s) => s.match && raw.toLowerCase().indexOf(s.match.toLowerCase()) >= 0) || null; }
  const name = (Z() && code === "cn" && CHINA && CHINA.company_zh && CHINA.company_zh[raw]) ? CHINA.company_zh[raw] : raw;
  if (sanc) return `<span class="chip sanc" data-tip="${escA("⚠ " + sanc.name + " · US " + sanc.list + " (" + sanc.date + ")")}">⚠ ${esc(name)}</span>`;
  if (origin) return `<span class="chip foreign" data-tip="${escA("HQ: " + (ORIGIN[origin] || origin))}">${esc(name)}<sup class="orig">${esc(origin)}</sup></span>`;
  return `<span class="chip">${esc(name)}</span>`;
}
function cityCardsHTML(code) {
  const d = code === "cn" ? CHINA : APAC[code]; if (!d) return "";
  const cities = code === "cn" ? (CHINA.cities || []) : (d.cities || []);
  if (!cities.length && (d.clusters || d.tagline)) {  // city-state (Singapore): one full country-level dossier, same sections as a city
    const h = `<div class="dos-h"><span class="dos-name">${esc(countryName(code))}</span>${d.dom ? `<span class="dos-dom" style="background:${domColor(d.dom)}">${esc(domName(d.dom))}</span>` : ""}</div>`;
    return h + dossierSections(d, code, null);
  }
  const card = (c, showDom) => { const tag = (Z() && c.zh && c.zh.tagline) ? c.zh.tagline : (c.tagline || c.area || ""); return `<button class="citycard" data-city="${escA(c.name)}"><b>${esc(cityName(c))}${showDom && c.dom ? ` <span class="cc-dom">${esc(domName(c.dom))}</span>` : ""}</b><span>${esc(tag.slice(0, 92))}</span></button>`; };
  const head = `<div class="dos-h"><span class="dos-name">${tt("cities")}</span><span class="dos-area">${cities.length} · ${tt("clickdrill")}</span></div>`;
  // Any country whose cities carry a domain: group by focus industry (biggest cluster first). The coloured
  // group header carries the label, so the per-card domain badge is dropped. Domain-less cities fall to a flat grid.
  if (cities.some((c) => c.dom) && CHINA && CHINA.domains) {
    const groups = {}; cities.forEach((c) => { const k = c.dom || "OTHER"; (groups[k] = groups[k] || []).push(c); });
    const order = Object.keys(CHINA.domains).filter((k) => groups[k]).sort((a, b) => groups[b].length - groups[a].length);
    if (groups.OTHER) order.push("OTHER");
    const blocks = order.map((k) => { const list = groups[k], col = (CHINA.domains[k] && CHINA.domains[k][1]) || "#94a3b8", nm = k === "OTHER" ? (Z() ? "其他" : "Other") : domName(k);
      return `<div class="citygrp"><div class="cg-head"><span class="cg-dot" style="background:${col}"></span><span class="cg-name">${esc(nm)}</span><span class="cg-n">${list.length}</span></div><div class="citycards">${list.map((c) => card(c, false)).join("")}</div></div>`; }).join("");
    return head + blocks;
  }
  return head + `<div class="citycards">${cities.map((c) => card(c, true)).join("")}</div>`;
}
const LVLW_ZH = { 3: "领先", 2: "较强", 1: "具备" };
function clusterBlock(cl, code, zc) {
  const seg = (Z() && zc && zc.seg) ? zc.seg : cl.seg, what = (Z() && zc && zc.what) ? zc.what : cl.what;
  const anch = (cl.anchors || []).map((a) => anchorChip(a, code)).join("");
  return `<div class="cluster l${cl.level}"><div class="cl-top"><span class="cl-seg">${esc(seg)}</span><span class="cl-lvl l${cl.level}">${(Z() ? LVLW_ZH : LVLW)[cl.level] || ""}</span></div><div class="cl-what">${esc(what)}</div>${anch ? `<div class="cl-anch">${anch}</div>` : ""}</div>`;
}
// ---- Asia landing (right panel): thesis + demand drivers + live-country drill list ----
function panelAsia() {
  const A = ASIA;
  if (!A || !A.vc) return `<div class="dos-h"><span class="dos-name">${Z() ? "亚洲" : "Asia"}</span></div><div class="dos-note">${tt("clickzoom")}</div>`;
  let h = `<div class="dos-h"><span class="dos-name">${Z() ? "亚洲" : "Asia"}</span><span class="dos-area">${tt("vc_sub")}</span></div>`;
  h += `<div class="vc-thesis">${esc(A.thesis || "")}</div>`;
  h += `<div class="sech2">${tt("drivers")}</div><div class="vc-chokes">` + (A.vc.drivers || []).map((d) =>
    `<span class="vc-dr" data-tip="${escA(d.label + " — " + d.detail + "  ·  pulls: " + d.parts + "  (source: " + d.source + ")")}"><span class="vc-dr-w">${esc(d.label)}</span><span class="vc-dr-s">${esc(d.size)}</span><span class="vc-dr-l">${esc(d.parts)}</span></span>`).join("") + `</div>`;
  h += `<div class="sech2">${tt("explore")}</div><div class="vc-jump">` + CO.filter((c) => c.status === "live").map((c) =>
    `<button class="vc-jumpbtn" data-code="${c.code}">${esc(countryName(c.code))}<span class="rolepill" style="background:${c.rc || "#888"}">${esc(c.role || "")}</span> ↗</button>`).join("") + `</div>`;
  return h;
}
// the full dossier body (tagline → stats → clusters → sub-districts → value-chain → sourcing → mfg heatmap → note).
// Shared by city dossiers (China + Malaysia cities) AND the Singapore country-level dossier, so every place reads the same.
function dossierSections(c, code, z) {
  const pick = (zv, ev) => esc((z && zv != null) ? zv : ev);
  let h = `<div class="dos-tag">${pick(z ? z.tagline : null, c.tagline || "")}</div>`;
  if (c.stats && c.stats.length) h += `<div class="dos-stats">${c.stats.map((s, i) => { const sz = (z && z.stats && z.stats[i]) ? z.stats[i] : s; return `<div class="dos-stat"><div class="k">${esc(sz.k)}</div><div class="v">${esc(sz.v)}</div></div>`; }).join("")}</div>`;
  if (c.clusters && c.clusters.length) h += `<div class="dos-sec"><h5>${tt("sig")}</h5>
    <div class="dos-legend"><span><i class="dot cn"></i>${tt("lg_local")}</span><span><i class="dot for"></i>${tt("lg_for")}</span><span class="sanc-leg">⚠ ${tt("lg_sanc")}</span><span class="leg-hint">${tt("lg_hint")}</span></div>
    ${c.clusters.map((cl, i) => clusterBlock(cl, code, z && z.clusters ? z.clusters[i] : null)).join("")}</div>`;
  if (c.subdistricts && c.subdistricts.length) h += `<div class="dos-sec"><h5>${tt("subd")}</h5>${c.subdistricts.map((s, i) => `<div class="sub-row"><b>${esc(s.name)}</b><span>${pick(z && z.subdistricts && z.subdistricts[i] ? z.subdistricts[i].focus : null, s.focus)}</span></div>`).join("")}</div>`;
  if (c.valuechain) h += `<div class="dos-sec"><h5>${tt("vc")}</h5><div class="vc">${pick(z ? z.valuechain : null, c.valuechain)}</div></div>`;
  if (c.sourcing) h += `<div class="dos-sec"><h5>${tt("dist")}</h5><div class="src2">
    <div><div class="lbl">${tt("buy")}</div><ul>${(c.sourcing.buy || []).map((x, i) => `<li>${pick(z && z.sourcing && z.sourcing.buy ? z.sourcing.buy[i] : null, x)}</li>`).join("")}</ul></div>
    <div><div class="lbl">${tt("sell")}</div><ul>${(c.sourcing.sell || []).map((x, i) => `<li>${pick(z && z.sourcing && z.sourcing.sell ? z.sourcing.sell[i] : null, x)}</li>`).join("")}</ul></div></div></div>`;
  const tax = (CHINA && CHINA.taxonomy) || (APAC[code] && APAC[code].taxonomy);
  if (c.tags && tax) {
    const cells = tax.map((t) => { const v = c.tags[t] || 0, bg = v ? `background:${TAXFILL[v]}` : "background:#fafbfd;border:1px solid var(--line)";
      return `<div class="taxc" style="${bg};color:${TAXFG[v] || "#cbd5e1"}" data-tip="${escA(t + ": " + (v ? LVLW[v] : "—"))}"><div class="tl">${esc(t.slice(0, 8))}</div><div class="tv">${v ? "●".repeat(v) : "·"}</div></div>`; }).join("");
    h += `<div class="dos-sec"><h5>${tt("mfg")}</h5><div class="taxg">${cells}</div></div>`;
  }
  if (c.note) h += `<div class="dos-note">${esc(z && z.note ? z.note : c.note)}</div>`;
  return h;
}
function panelCity(code, name) {
  const list = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const c = list.find((x) => x.name === name); if (!c) return "";
  const z = (Z() && c.zh) ? c.zh : null;
  const h = `<div class="dos-h"><span class="dos-name">${esc(cityName(c))}</span>${c.dom ? `<span class="dos-dom" style="background:${domColor(c.dom)}">${esc(domName(c.dom))}</span>` : ""}</div>`;
  return h + dossierSections(c, code, z);
}
function renderPanel() {
  const tilesEl = document.getElementById("tiles"), el = document.getElementById("panel");
  if (STATE.level === "asia") { tilesEl.style.display = "none"; tilesEl.innerHTML = ""; el.innerHTML = panelAsia(); }
  else {
    tilesEl.style.display = ""; tilesEl.innerHTML = countryTilesHTML(STATE.country);
    el.innerHTML = STATE.level === "country" ? cityCardsHTML(STATE.country) : panelCity(STATE.country, STATE.city);
  }
  el.scrollTop = 0;
  el.querySelectorAll(".vc-jumpbtn[data-code]").forEach((b) => b.addEventListener("click", () => drillCountry(b.dataset.code)));
  el.querySelectorAll("[data-city]").forEach((b) => b.addEventListener("click", () => drillCity(STATE.country, b.dataset.city)));
  const dl = document.getElementById("domlegend");
  if (dl) {
    if (STATE.level === "asia") {  // map coloured by each country's manufacturing profile
      const seen = {}, items = [];
      CO.forEach((c) => { if (c.role && !seen[c.role]) { seen[c.role] = 1; items.push(c); } });
      dl.style.display = ""; dl.innerHTML = `<span class="dim">${tt("maprole")}</span>` + items.map((c) => `<span><i style="color:${c.rc}">●</i> ${esc(c.role)}</span>`).join("");
    } else {
      const cur = STATE.country, ccs = cur === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[cur] && APAC[cur].cities) || []);
      if ((ccs || []).some((c) => c.dom) && CHINA && CHINA.domains) {  // dot legend wherever cities are colour-coded by domain
        dl.style.display = ""; dl.innerHTML = `<span class="dim">${tt("mapdots")}</span>` + Object.keys(CHINA.domains).map((d) => `<span><i style="color:${CHINA.domains[d][1]}">●</i> ${esc(domName(d))}</span>`).join("");
      } else dl.style.display = "none";
    }
  }
}
function renderCrumb() {
  const parts = [`<a data-go="asia">${Z() ? "亚洲" : "Asia"}</a>`];
  if (STATE.country) parts.push(`<a data-go="country">${esc(countryName(STATE.country))}</a>`);
  if (STATE.city) { const list = STATE.country === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[STATE.country] && APAC[STATE.country].cities) || []); const cc = list.find((x) => x.name === STATE.city); parts.push(`<span>${esc(cc ? cityName(cc) : STATE.city)}</span>`); }
  const bc = document.getElementById("crumb"); bc.innerHTML = parts.join('<span class="sep">›</span>');
  bc.querySelectorAll("[data-go]").forEach((a) => a.addEventListener("click", () => { a.dataset.go === "asia" ? goAsia() : up(); }));
}

function headHTML() {
  return `<h1>Asia Atlas <span style="font-size:12px;color:var(--muted);font-weight:400">${tt("sub_head")}</span></h1><div class="atlas-crumb" id="crumb"></div>`;
}
function toolbarHTML() {
  return `<button class="mapbtn" id="outbtn">${tt("zoomout")}</button>
    <button class="mapbtn" id="langbtn">${Z() ? "EN" : "简体中文"}</button>
    <span class="mt-label" style="margin-left:auto">${tt("pan")}</span>`;
}
function wireToolbar() {
  document.getElementById("outbtn").addEventListener("click", () => up());
  document.getElementById("langbtn").addEventListener("click", () => { STATE.lang = Z() ? "en" : "zh"; relang(); });
}
function relang() {  // re-render content + markers in the new language; don't re-init the map
  document.querySelector(".cty-head").innerHTML = headHTML();
  document.getElementById("maptools").innerHTML = toolbarHTML();
  wireToolbar(); renderPanel(); renderCrumb();
  mapDo(() => { if (STATE.level === "asia") addCountryMarkers(); else { clearDetailMarkers(); addCityDots(STATE.country); declutterCityLabels(); } });
}
function render() {
  document.getElementById("main").innerHTML = `
    <div class="cty-head">${headHTML()}</div>
    <div class="maptools" id="maptools">${toolbarHTML()}</div>
    <div class="citywrap"><div class="citymap" id="map"></div><div class="dossier" id="panel"></div></div>
    <div class="legend" id="domlegend" style="display:none;margin:12px 0 0"></div>
    <div class="atlas-tiles atlas-tiles-below" id="tiles" style="display:none"></div>`;
  initTip(); wireToolbar(); renderPanel(); renderCrumb(); initMap();
}
render();
