// EMI Asia Atlas — single-page D3 continuous-zoom drill-down (Asia → country → city).
// No navigation: clicking zooms the map in/out and swaps the side panel. Data is loaded in-page
// from window.ASIA (registry + Asia geo), window.CHINA (provinces geo + cities + macro + leverage),
// window.APAC.{sg,my} (country bundles). Reuses china.css.
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
  const m = (u, v2) => Math.round(u + (v2 - u) * lt);
  return `rgb(${m(a1, a2)},${m(b1, b2)},${m(c1, c2)})`;
}
const gdpScale = (g) => ramp("chip", Math.max(8, Math.min(100, (g / 14) * 100)));  // province GDP (¥T) → blue scale

const STATE = { level: "asia", layer: "chip", country: null, city: null };
let svg, g, gBase, gDetail, gLab, projection, path, zoom, W, H, K = 1;

// ---- tooltips ----
let tip;
function initTip() { tip = document.getElementById("ctip") || document.body.appendChild(Object.assign(document.createElement("div"), { id: "ctip" }));
  document.addEventListener("mousemove", (e) => { if (tip.style.display === "block") { tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; } }); }
const showTip = (html, e) => { tip.innerHTML = html; tip.style.display = "block"; tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; };
const hideTip = () => { tip.style.display = "none"; };

// ---- map ----
function fitProjection() {
  const el = document.getElementById("map"); W = el.clientWidth; H = el.clientHeight || 560;
  projection = d3.geoMercator(); path = d3.geoPath(projection);
  projection.fitExtent([[14, 14], [W - 14, H - 14]], ASIA.geo);
}
function initMap() {
  const el = document.getElementById("map"); el.innerHTML = "";
  fitProjection();
  svg = d3.select(el).append("svg").attr("width", "100%").attr("height", "100%").attr("viewBox", `0 0 ${W} ${H}`).style("display", "block");
  g = svg.append("g");
  gBase = g.append("g").attr("class", "base");
  gDetail = g.append("g").attr("class", "detail");
  gLab = g.append("g").attr("class", "labs");
  zoom = d3.zoom().scaleExtent([1, 60]).on("zoom", zoomed);
  svg.call(zoom).on("dblclick.zoom", null);
  svg.on("dblclick", () => up());
  drawAsia();
}
function zoomed(ev) {
  K = ev.transform.k; g.attr("transform", ev.transform);
  gBase.selectAll("path").attr("stroke-width", 0.8 / K);
  gDetail.selectAll("path.prov").attr("stroke-width", 0.5 / K);
  gDetail.selectAll("circle.city").attr("r", 5 / K).attr("stroke-width", 1.6 / K);
  gLab.selectAll("text").attr("font-size", (d) => (d.fs || 12) / K).attr("stroke-width", 3 / K);
}
function drawAsia() {
  const r = RAMP[STATE.layer];
  gBase.selectAll("path").data(ASIA.geo.features, (d) => d.properties.name).join("path")
    .attr("d", path).attr("class", "cgeo")
    .attr("fill", (d) => { const c = byName[d.properties.name]; return c ? ramp(STATE.layer, r.val(c)) : "#eef2f6"; })
    .attr("stroke", "#fff").attr("stroke-width", 0.8).attr("opacity", 1)
    .style("cursor", (d) => { const c = byName[d.properties.name]; return c && c.status === "live" ? "pointer" : "default"; })
    .on("mousemove", function (e, d) { const c = byName[d.properties.name]; if (!c) return hideTip(); showTip(`<b>${esc(c.name)}</b> · <span style="color:${c.status === "live" ? "#2563eb" : "#94a3b8"}">${c.status === "live" ? "live ↗ click to drill" : "planned"}</span><br>chip weight <b>${c.chip}</b>/100 · GDP <b>${c.gdp}%</b><br><span style="color:#475569;white-space:normal;display:inline-block;max-width:250px">${esc(c.headline)}</span>`, e); if (c.status !== "live") return; d3.select(this).attr("stroke", "#0f172a").attr("stroke-width", 1.6 / K); })
    .on("mouseout", function () { hideTip(); d3.select(this).attr("stroke", "#fff").attr("stroke-width", 0.8 / K); })
    .on("click", (e, d) => { const c = byName[d.properties.name]; if (c && c.status === "live") drillCountry(c.code); });
  drawLabels();
}
function drawLabels() {
  const live = CO.filter((c) => c.status === "live").map((c) => ({ name: c.name, p: projection([c.lon, c.lat]), fs: 13 }));
  gLab.selectAll("text").data(live, (d) => d.name).join("text").attr("class", "lab")
    .attr("x", (d) => d.p[0] + 9).attr("y", (d) => d.p[1] + 4).text((d) => d.name + " ↗")
    .attr("font-size", (d) => d.fs / K).attr("font-weight", 700).attr("fill", "#0f172a")
    .attr("stroke", "#fff").attr("stroke-width", 3 / K).attr("paint-order", "stroke").style("pointer-events", "none");
}
function zoomToFeature(feature, dur) {
  const b = path.bounds(feature), dx = b[1][0] - b[0][0], dy = b[1][1] - b[0][1], cx = (b[0][0] + b[1][0]) / 2, cy = (b[0][1] + b[1][1]) / 2;
  const scale = Math.max(1, Math.min(40, 0.82 / Math.max(dx / W, dy / H)));
  const t = d3.zoomIdentity.translate(W / 2 - scale * cx, H / 2 - scale * cy).scale(scale);
  svg.transition().duration(reduce() ? 0 : (dur || 820)).ease(d3.easeCubicInOut).call(zoom.transform, t);
}
function zoomToPoint(lonlat, scale, dur) {
  const p = projection(lonlat), s = scale || 14;
  const t = d3.zoomIdentity.translate(W / 2 - s * p[0], H / 2 - s * p[1]).scale(s);
  svg.transition().duration(reduce() ? 0 : (dur || 760)).ease(d3.easeCubicInOut).call(zoom.transform, t);
}

// ---- drill ----
function clearDetail() { gDetail.selectAll("*").remove(); }
function fadeOthers(focusName) {
  gBase.selectAll("path").transition().duration(reduce() ? 0 : 500).attr("opacity", (d) => d.properties.name === focusName ? 1 : 0.25);
  gLab.selectAll("text").style("display", "none");
}
function restoreAll() { gBase.selectAll("path").transition().duration(reduce() ? 0 : 500).attr("opacity", 1); gLab.selectAll("text").style("display", null); }

function drillCountry(code) {
  const c = byCode[code]; if (!c || c.status !== "live") return;
  STATE.level = "country"; STATE.country = code; STATE.city = null;
  hideTip(); clearDetail();
  const feat = ASIA.geo.features.find((f) => f.properties.name === c.name);
  if (feat) { zoomToFeature(feat); fadeOthers(c.name); }
  // China: provinces + city dots; Malaysia: city dots; Singapore: single marker
  if (code === "cn" && CHINA && CHINA.geo) drawProvinces();
  drawCityDots(code);
  renderPanel(); renderCrumb();
}
function drawProvinces() {
  gDetail.append("g").selectAll("path.prov").data(CHINA.geo.features).join("path").attr("class", "prov")
    .attr("d", path).attr("fill", (d) => { const pr = (CHINA.provinces || {})[d.properties.name]; return pr ? gdpScale(pr.gdp || 0) : "#dbe4ef"; })
    .attr("stroke", "#fff").attr("stroke-width", 0.5 / K).attr("opacity", 0).style("pointer-events", "none")
    .transition().duration(reduce() ? 0 : 500).attr("opacity", 0.95);
}
function drawCityDots(code) {
  const cities = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  if (code === "sg") { const sg = byCode.sg; cities.length || drawDot({ name: "Singapore", lon: sg.lon, lat: sg.lat, _sg: true }, code); }
  cities.forEach((ct) => drawDot(ct, code));
}
function drawDot(ct, code) {
  if (ct.lon == null || ct.lat == null) return;
  const p = projection([ct.lon, ct.lat]);
  gDetail.append("circle").attr("class", "city").attr("cx", p[0]).attr("cy", p[1]).attr("r", 5 / K)
    .attr("fill", "#fff").attr("stroke", "#1d4ed8").attr("stroke-width", 1.6 / K).style("cursor", "pointer")
    .on("mousemove", (e) => showTip(`<b>${esc(ct.name)}</b>${ct.area ? " · " + esc(ct.area) : ""}<br><span style="color:#64748b">click to open dossier</span>`, e))
    .on("mouseout", hideTip)
    .on("click", () => drillCity(code, ct.name));
  gDetail.append("text").attr("class", "clab").attr("x", p[0] + 8 / K).attr("y", p[1] + 4 / K).text(ct.name)
    .attr("font-size", 11 / K).attr("font-weight", 600).attr("fill", "#0f172a").attr("stroke", "#fff").attr("stroke-width", 2.5 / K).attr("paint-order", "stroke").style("pointer-events", "none");
}
function drillCity(code, cityName) {
  const list = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const ct = list.find((x) => x.name === cityName); if (!ct) return;
  STATE.level = "city"; STATE.city = cityName; hideTip();
  if (ct.lon != null) zoomToPoint([ct.lon, ct.lat], code === "cn" ? 18 : 22);
  renderPanel(); renderCrumb();
}
function up() {
  if (STATE.level === "city") { STATE.level = "country"; STATE.city = null; const c = byCode[STATE.country]; const f = ASIA.geo.features.find((x) => x.properties.name === c.name); if (f) zoomToFeature(f); }
  else if (STATE.level === "country") { STATE.level = "asia"; STATE.country = null; clearDetail(); restoreAll(); svg.transition().duration(reduce() ? 0 : 700).call(zoom.transform, d3.zoomIdentity); }
  renderPanel(); renderCrumb();
}
function goAsia() { STATE.level = "asia"; STATE.country = null; STATE.city = null; clearDetail(); restoreAll(); svg.transition().duration(reduce() ? 0 : 700).call(zoom.transform, d3.zoomIdentity); renderPanel(); renderCrumb(); }

// ---- panels ----
function anchorChip(a, code) {
  let name, origin = null, sanc = null;
  if (a && typeof a === "object") { name = a.n; origin = a.o || null; }
  else { name = a; if (code === "cn" && CHINA) { const o = (CHINA.origins || {})[a]; if (o && o.cn === false) origin = o.code; sanc = (CHINA.sanctions || []).find((s) => s.match && a.toLowerCase().indexOf(s.match.toLowerCase()) >= 0) || null; } }
  if (sanc) return `<span class="chip sanc" data-tip="${escA("⚠ " + sanc.name + " · US " + sanc.list + " (" + sanc.date + ")")}">⚠ ${esc(name)}</span>`;
  if (origin) return `<span class="chip foreign" data-tip="${escA("HQ: " + (ORIGIN[origin] || origin))}">${esc(name)}<sup class="orig">${esc(origin)}</sup></span>`;
  return `<span class="chip">${esc(name)}</span>`;
}
function roleBars(nodes) {
  return (nodes || []).slice(0, 6).map((n) => {
    const col = n.type === "hold" ? "var(--blue)" : "var(--amber)", pct = Math.max(3, Math.min(100, n.share));
    return `<div class="lev-row"><div class="lev-top"><span class="lev-term">${esc(n.node)}</span><span class="lev-val" style="color:${col}">${esc(n.disp)}</span></div><div class="lev-bar"><div class="lev-fill" style="width:${pct}%;background:${col}"></div></div></div>`;
  }).join("");
}
function macroStrip(tiles) {
  return `<div class="amx">${(tiles || []).slice(0, 6).map((t) => `<div class="amk"><span>${esc(t.k || t.label)}</span><b>${esc(t.v)}</b></div>`).join("")}</div>`;
}
function panelAsia() {
  const r = RAMP[STATE.layer], sorted = CO.slice().sort((a, b) => r.val(b) - r.val(a));
  const rows = sorted.map((c) => { const live = c.status === "live", col = ramp(STATE.layer, r.val(c));
    return `<div class="lev-row arow ${live ? "live" : "planned"}"${live ? ` data-code="${c.code}"` : ""}><div class="lev-top"><span class="lev-term">${esc(c.name)}${live ? " ↗" : ""}</span><span class="lev-scope"><span class="stat-badge ${live ? "live" : "plan"}">${live ? "live" : "soon"}</span></span><span class="lev-val" style="color:${live ? col : "#94a3b8"}">${r.disp(c)}</span></div><div class="lev-bar"><div class="lev-fill" style="width:${Math.max(2, r.pct(c)).toFixed(0)}%;background:${col};opacity:${live ? 1 : .5}"></div></div></div>`; }).join("");
  return `<div class="dos-h"><span class="dos-name">Asia</span><span class="dos-area">ranked by ${r.label}</span></div><div class="arows">${rows}</div><div class="dos-note">Click a live country on the map or list to zoom in.</div>`;
}
function panelCountry(code) {
  if (code === "cn" && CHINA) {
    const m = CHINA.macro || {};
    return `<div class="dos-h"><span class="dos-name">China</span><span class="dos-area">macro · leverage · cities</span></div>
      ${macroStrip(m.headline)}
      <div class="dos-sec"><h5>Supply-chain leverage</h5>${roleBars(CHINA.leverage)}</div>
      <div class="dos-sec"><h5>Cities <span style="font-weight:400;color:var(--faint)">click a dot or name</span></h5><div class="citylist">${(CHINA.cities || []).map((c) => `<button class="citybtn" data-city="${escA(c.name)}">${esc(c.name)}</button>`).join("")}</div></div>`;
  }
  const d = APAC[code]; if (!d) return "";
  const citychips = (d.cities || []).map((c) => `<button class="citybtn" data-city="${escA(c.name)}">${esc(c.name)}</button>`).join("");
  return `<div class="dos-h"><span class="dos-name">${esc(d.name)}</span><span class="dos-area">macro · role${d.cities ? " · cities" : ""}</span></div>
    <div class="dos-tag">${esc(d.tagline || "")}</div>
    ${macroStrip(d.macro)}
    <div class="dos-sec"><h5>Supply-chain role</h5>${roleBars(d.role)}</div>
    ${d.cities ? `<div class="dos-sec"><h5>Cities</h5><div class="citylist">${citychips}</div></div>` : (d.clusters ? `<div class="dos-sec"><h5>Key clusters</h5>${d.clusters.map((cl) => clusterBlock(cl, code)).join("")}</div>` : "")}`;
}
function clusterBlock(cl, code) {
  const anch = (cl.anchors || []).map((a) => anchorChip(a, code)).join("");
  return `<div class="cluster l${cl.level}"><div class="cl-top"><span class="cl-seg">${esc(cl.seg)}</span><span class="cl-lvl l${cl.level}">${{ 3: "leading", 2: "strong", 1: "present" }[cl.level] || ""}</span></div><div class="cl-what">${esc(cl.what)}</div>${anch ? `<div class="cl-anch">${anch}</div>` : ""}</div>`;
}
function panelCity(code, cityName) {
  const list = code === "cn" ? (CHINA ? CHINA.cities : []) : ((APAC[code] && APAC[code].cities) || []);
  const c = list.find((x) => x.name === cityName); if (!c) return "";
  const dom = c.dom ? `<span class="dos-dom" style="background:var(--blue)">${esc(c.dom)}</span>` : "";
  return `<div class="dos-h"><span class="dos-name">${esc(c.name)}</span>${dom}</div>
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
  const bc = document.getElementById("crumb");
  bc.innerHTML = parts.join('<span class="sep">›</span>');
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
      <span class="mt-label" style="margin-left:auto">scroll = zoom · drag = pan · double-click = back</span></div>
    <div class="citywrap"><div class="citymap" id="map"></div><div class="dossier" id="panel"></div></div>`;
  initTip(); initMap(); renderPanel(); renderCrumb();
  document.querySelectorAll(".mapbtn[data-layer]").forEach((b) => b.addEventListener("click", () => { STATE.layer = b.dataset.layer; document.querySelectorAll(".mapbtn[data-layer]").forEach((x) => x.classList.toggle("active", x === b)); if (STATE.level === "asia") { drawAsia(); renderPanel(); } }));
  document.getElementById("outbtn").addEventListener("click", () => up());
  window.addEventListener("resize", () => { /* keep simple: re-fit on resize */ initMap(); if (STATE.level !== "asia" && STATE.country) { const f = ASIA.geo.features.find((x) => x.properties.name === byCode[STATE.country].name); if (f) { if (STATE.country === "cn" && CHINA) drawProvinces(); drawCityDots(STATE.country); fadeOthers(byCode[STATE.country].name); zoomToFeature(f, 0); } } });
}
render();
