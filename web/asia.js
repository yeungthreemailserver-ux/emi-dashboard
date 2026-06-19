// Asia overview — level-1 of the drill-down (Asia → country → city → cluster).
// Filled-country choropleth (vendored Natural-Earth geo, ECharts) on the left + a ranked
// country panel on the right (mirrors the China map+dossier layout). Colour-switchable by
// chip supply-chain weight ↔ GDP growth. Click a LIVE country (map or panel) → animated zoom-drill.
const ASIA = window.ASIA;
const STATE = { layer: "chip" };
const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const byName = {}, byCode = {}; ASIA.countries.forEach((c) => { byName[c.name] = c; byCode[c.code] = c; });
const reduceMotion = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

const RAMP = {
  chip: { stops: ["#eff6ff", "#bfdbfe", "#60a5fa", "#2563eb", "#1e3a8a"], min: 0, max: 100, label: "chip supply-chain weight", disp: (c) => c.chip + "/100", pct: (c) => c.chip, metric: (c) => c.chip },
  gdp: { stops: ["#f0fdf4", "#bbf7d0", "#4ade80", "#16a34a", "#14532d"], min: 0, max: 7, label: "GDP growth", disp: (c) => "+" + c.gdp + "%", pct: (c) => (c.gdp / 7) * 100, metric: (c) => c.gdp },
};
function rampColor(layer, value) {
  const r = RAMP[layer], t = Math.max(0, Math.min(1, (value - r.min) / (r.max - r.min)));
  const n = r.stops.length - 1, seg = Math.min(n - 1, Math.floor(t * n)), lt = t * n - seg;
  const h = (x) => [parseInt(x.slice(1, 3), 16), parseInt(x.slice(3, 5), 16), parseInt(x.slice(5, 7), 16)];
  const [r1, g1, b1] = h(r.stops[seg]), [r2, g2, b2] = h(r.stops[seg + 1]);
  const m = (u, v) => Math.round(u + (v - u) * lt);
  return `rgb(${m(r1, r2)},${m(g1, g2)},${m(b1, b2)})`;
}

// fixed label anchors for the three live countries so they never collide
const LPOS = { cn: "top", my: "left", sg: "bottom" };
let CHART = null;
function buildOption() {
  const r = RAMP[STATE.layer];
  const mapData = ASIA.countries.map((c) => ({ name: c.name, value: r.metric(c) }));
  const markers = ASIA.countries.map((c) => {
    const live = c.status === "live";
    return {
      name: c.name, value: [c.lon, c.lat], code: c.code,
      symbol: "circle", symbolSize: live ? 12 : 6,
      itemStyle: { color: live ? "#fff" : "#94a3b8", borderColor: live ? "#0f172a" : "#cbd5e1", borderWidth: live ? 2.5 : 1, opacity: live ? 1 : 0.9, shadowBlur: live ? 6 : 0, shadowColor: "rgba(15,23,42,.3)" },
      label: { show: live, position: LPOS[c.code] || "right", distance: 7, formatter: c.name + " ↗", fontSize: 12.5, fontWeight: 700, color: "#0f172a", textShadowColor: "#fff", textShadowBlur: 4 },
      emphasis: { label: { show: true, formatter: c.name + (live ? " ↗" : ""), fontSize: 12, fontWeight: live ? 700 : 600, color: live ? "#0f172a" : "#475569", textShadowColor: "#fff", textShadowBlur: 4 } },
    };
  });
  return {
    animationDurationUpdate: 480, animationEasingUpdate: "cubicOut",
    tooltip: {
      trigger: "item", confine: true, backgroundColor: "#fff", borderColor: "rgba(148,163,184,.5)", borderWidth: 0.5, padding: [8, 11], textStyle: { color: "#1e293b", fontSize: 12 },
      formatter: (p) => { const c = byName[p.name]; if (!c) return ""; return `<b>${esc(c.name)}</b> · <span style="color:${c.status === "live" ? "#2563eb" : "#94a3b8"}">${c.status === "live" ? "live ↗ click to drill" : "planned"}</span><br>chip weight <b>${c.chip}</b>/100 · GDP <b>${c.gdp}%</b><br><span style="color:#475569;white-space:normal;display:inline-block;max-width:250px">${esc(c.headline)}</span>`; },
    },
    visualMap: { type: "continuous", min: r.min, max: r.max, calculable: true, left: 16, bottom: 18, itemHeight: 110, itemWidth: 12, text: ["high", "low"], textStyle: { color: "#64748b", fontSize: 11 }, inRange: { color: r.stops }, seriesIndex: 0 },
    geo: {
      map: "asia", roam: true, zoom: 1.45, center: [100, 22], scaleLimit: { min: 1, max: 12 },
      itemStyle: { areaColor: "#f1f5f9", borderColor: "#fff", borderWidth: 0.8 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: "#cdd9e8", borderColor: "#0f172a", borderWidth: 1.2 } },
      select: { disabled: true },
    },
    series: [
      { type: "map", geoIndex: 0, data: mapData, itemStyle: { areaColor: "#f1f5f9" } },
      { type: "scatter", coordinateSystem: "geo", geoIndex: 0, data: markers, z: 6, cursor: "pointer", emphasis: { scale: 1.18 }, labelLayout: { hideOverlap: true, moveOverlap: "shiftY" } },
    ],
  };
}

function drillTo(c) {
  if (!c || c.status !== "live" || !c.href) return;
  if (reduceMotion() || !CHART) { location.href = c.href; return; }
  const el = document.getElementById("asiamap");
  CHART.setOption({ geo: { zoom: 6, center: [c.lon, c.lat] } });
  if (el) { el.style.transition = "opacity .42s ease"; el.style.opacity = "0.5"; }
  setTimeout(() => { location.href = c.href; }, 460);
}

function panelHTML() {
  const r = RAMP[STATE.layer];
  const sorted = ASIA.countries.slice().sort((a, b) => r.metric(b) - r.metric(a));
  const rows = sorted.map((c) => {
    const live = c.status === "live", col = rampColor(STATE.layer, r.metric(c));
    return `<div class="lev-row arow ${live ? "live" : "planned"}"${live ? ` data-code="${c.code}"` : ""}>
      <div class="lev-top"><span class="lev-term">${esc(c.name)}${live ? " ↗" : ""}</span><span class="lev-scope"><span class="stat-badge ${live ? "live" : "plan"}">${live ? "live" : "soon"}</span></span><span class="lev-val" style="color:${live ? col : "#94a3b8"}">${r.disp(c)}</span></div>
      <div class="lev-bar"><div class="lev-fill" style="width:${Math.max(2, r.pct(c)).toFixed(0)}%;background:${col};opacity:${live ? 1 : 0.5}"></div></div>
      <div class="lev-src">${esc(c.headline)}</div></div>`;
  }).join("");
  return `<div class="dos-h"><span class="dos-name">Countries</span><span class="dos-area">ranked by ${r.label}</span></div>
    <div class="arows">${rows}</div>
    <div class="dos-note">${ASIA.countries.filter((c) => c.status === "live").length} live · click to drill · rest planned</div>`;
}

function initMap() {
  const el = document.getElementById("asiamap"); if (!el || !window.echarts) return;
  if (!echarts.getMap || !echarts.getMap("asia")) echarts.registerMap("asia", ASIA.geo);
  CHART = echarts.init(el);
  CHART.setOption(buildOption());
  CHART.on("click", (p) => { const c = byName[p.name]; if (c) drillTo(c); });
  window.addEventListener("resize", () => CHART && CHART.resize());
}
function wirePanel() {
  document.querySelectorAll(".arow.live[data-code]").forEach((el) => el.addEventListener("click", () => drillTo(byCode[el.dataset.code])));
}
function refresh() {  // on layer toggle: recolour map + rebuild panel (no full re-init)
  CHART && CHART.setOption(buildOption());
  document.getElementById("asiapanel").innerHTML = panelHTML(); wirePanel();
  const lbl = STATE.layer === "chip" ? "chip supply-chain weight" : "GDP growth";
  const d = document.querySelector(".legend .dim"); if (d) d.textContent = "fill colour = " + lbl;
}

function render() {
  document.getElementById("main").innerHTML = `
    <div class="cty-head"><h1>Asia <span style="font-size:12px;color:var(--muted);font-weight:400">electronics supply-chain map · drill into any country</span></h1>
      <div class="sub">Colour = the selected layer · click a <b>live</b> country (map or list) to drill into it. Scroll to zoom, drag to pan.</div></div>
    <div class="maptools"><span class="mt-label">Colour by</span>
      <button class="mapbtn${STATE.layer === "chip" ? " active" : ""}" data-layer="chip">Chip supply-chain weight</button>
      <button class="mapbtn${STATE.layer === "gdp" ? " active" : ""}" data-layer="gdp">GDP growth</button>
      <span class="mt-sep"></span><button class="mapbtn" id="resetbtn">⤢ Reset view</button></div>
    <div class="legend"><span><i style="color:#0f172a">◉</i> live — click to drill</span><span><i style="color:#94a3b8">○</i> planned</span><span class="dim">fill colour = chip supply-chain weight</span></div>
    <div class="citywrap">
      <div class="citymap" id="asiamap"></div>
      <div class="dossier" id="asiapanel">${panelHTML()}</div>
    </div>`;
  initMap(); wirePanel();
  document.querySelectorAll(".mapbtn[data-layer]").forEach((b) => b.addEventListener("click", () => { STATE.layer = b.dataset.layer; document.querySelectorAll(".mapbtn[data-layer]").forEach((x) => x.classList.toggle("active", x === b)); refresh(); }));
  const rb = document.getElementById("resetbtn"); if (rb) rb.addEventListener("click", () => { const el = document.getElementById("asiamap"); if (el) el.style.opacity = "1"; CHART && CHART.setOption({ geo: { zoom: 1.45, center: [100, 22] } }); });
}

render();
