// Asia overview — level-1 of the drill-down (Asia → country → city → cluster).
// Real filled-country choropleth (vendored Natural-Earth geo, ECharts), colour-switchable by
// chip supply-chain weight ↔ GDP growth. Click a LIVE country → animated zoom-drill into its page.
const ASIA = window.ASIA;
const STATE = { layer: "chip" };
const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const byName = {}; ASIA.countries.forEach((c) => { byName[c.name] = c; });
const reduceMotion = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

const RAMP = {
  chip: { colors: ["#eff6ff", "#bfdbfe", "#60a5fa", "#2563eb", "#1e3a8a"], min: 0, max: 100, label: "Chip supply-chain weight" },
  gdp: { colors: ["#f0fdf4", "#bbf7d0", "#4ade80", "#16a34a", "#14532d"], min: 0, max: 7, label: "GDP growth (%)" },
};

let CHART = null;
function buildOption() {
  const r = RAMP[STATE.layer];
  const mapData = ASIA.countries.map((c) => ({ name: c.name, value: STATE.layer === "chip" ? c.chip : c.gdp }));
  const markers = ASIA.countries.map((c) => {
    const live = c.status === "live";
    return {
      name: c.name, value: [c.lon, c.lat],
      symbol: "circle", symbolSize: live ? 13 : 7,
      itemStyle: { color: live ? "#fff" : "#94a3b8", borderColor: live ? "#0f172a" : "#cbd5e1", borderWidth: live ? 2.5 : 1, opacity: live ? 1 : 0.85, shadowBlur: live ? 6 : 0, shadowColor: "rgba(15,23,42,.25)" },
      label: { show: true, position: "right", distance: live ? 8 : 6, formatter: c.name + (live ? "  ↗" : "  ·soon"), fontSize: live ? 12.5 : 10.5, fontWeight: live ? 700 : 400, color: live ? "#0f172a" : "#64748b", textShadowColor: "#fff", textShadowBlur: 3 },
    };
  });
  return {
    animationDurationUpdate: 480, animationEasingUpdate: "cubicOut",
    tooltip: {
      trigger: "item", confine: true, backgroundColor: "#fff", borderColor: "rgba(148,163,184,.5)", borderWidth: 0.5, padding: [8, 11], textStyle: { color: "#1e293b", fontSize: 12 },
      formatter: (p) => { const c = byName[p.name]; if (!c) return `<b>${esc(p.name)}</b>`; return `<b>${esc(c.name)}</b> · <span style="color:${c.status === "live" ? "#2563eb" : "#94a3b8"}">${c.status === "live" ? "live ↗ click to drill" : "planned"}</span><br>chip weight <b>${c.chip}</b>/100 · GDP <b>${c.gdp}%</b><br><span style="color:#475569;white-space:normal;display:inline-block;max-width:250px">${esc(c.headline)}</span>`; },
    },
    visualMap: {
      type: "continuous", min: r.min, max: r.max, calculable: true, left: 14, bottom: 16, itemHeight: 120,
      text: ["high", "low"], textStyle: { color: "#64748b", fontSize: 11 },
      inRange: { color: r.colors }, seriesIndex: 0,
    },
    geo: {
      map: "asia", roam: true, zoom: 1.35, center: [104, 24], scaleLimit: { min: 1, max: 12 },
      itemStyle: { areaColor: "#eef2f6", borderColor: "#fff", borderWidth: 0.6 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: "#cdd9e8", borderColor: "#0f172a", borderWidth: 1.2 } },
      select: { disabled: true },
    },
    series: [
      { type: "map", geoIndex: 0, data: mapData, itemStyle: { areaColor: "#eef2f6" }, emphasis: { disabled: false } },
      { type: "scatter", coordinateSystem: "geo", geoIndex: 0, data: markers, z: 5, cursor: "pointer", emphasis: { scale: 1.15 } },
    ],
  };
}

function drillTo(c) {
  if (!c || c.status !== "live" || !c.href) return;
  if (reduceMotion()) { location.href = c.href; return; }
  const el = document.getElementById("asiamap");
  CHART.setOption({ geo: { zoom: 6, center: [c.lon, c.lat] } });   // animated zoom-in (spatial continuity)
  if (el) { el.style.transition = "opacity .42s ease"; el.style.opacity = "0.5"; }
  setTimeout(() => { location.href = c.href; }, 460);
}

function initMap() {
  const el = document.getElementById("asiamap"); if (!el || !window.echarts) return;
  if (!echarts.getMap || !echarts.getMap("asia")) echarts.registerMap("asia", ASIA.geo);
  CHART = echarts.init(el);
  CHART.setOption(buildOption());
  CHART.on("click", (p) => { const c = byName[p.name]; if (c) drillTo(c); });
  window.addEventListener("resize", () => CHART && CHART.resize());
}

function render() {
  const live = ASIA.countries.filter((c) => c.status === "live");
  const cards = live.map((c) => `<a class="morec asia-card" href="${esc(c.href)}"><div class="mk">${esc(c.name)} ↗</div><div class="md">${esc(c.headline)}</div></a>`).join("");
  const planned = ASIA.countries.filter((c) => c.status === "planned").map((c) => esc(c.name)).join(" · ");
  document.getElementById("main").innerHTML = `
    <div class="cty-head"><h1>Asia <span style="font-size:12px;color:var(--muted);font-weight:400">electronics supply-chain map · drill into any country</span></h1>
      <div class="sub">Colour = the selected layer · click a <b>live</b> country to drill into it. Scroll to zoom, drag to pan.</div></div>
    <div class="maptools"><span class="mt-label">Colour by</span>
      <button class="mapbtn${STATE.layer === "chip" ? " active" : ""}" data-layer="chip">Chip supply-chain weight</button>
      <button class="mapbtn${STATE.layer === "gdp" ? " active" : ""}" data-layer="gdp">GDP growth</button>
      <span class="mt-sep"></span><button class="mapbtn" id="resetbtn">⤢ Reset view</button></div>
    <div class="asiamap" id="asiamap"></div>
    <div class="legend"><span><i style="color:#0f172a">◉</i> live — click to drill</span><span><i style="color:#94a3b8">○</i> planned</span><span class="dim">fill colour = ${STATE.layer === "chip" ? "chip supply-chain weight" : "GDP growth"}</span></div>
    <div class="sech">Live countries <span class="dim">${live.length} of ${ASIA.countries.length} · planned: ${planned}</span></div>
    <div class="more-grid">${cards}</div>`;
  initMap();
  document.querySelectorAll(".mapbtn[data-layer]").forEach((b) => b.addEventListener("click", () => { STATE.layer = b.dataset.layer; CHART && CHART.setOption(buildOption()); document.querySelectorAll(".mapbtn[data-layer]").forEach((x) => x.classList.toggle("active", x === b)); document.querySelector(".legend .dim").textContent = "fill colour = " + (STATE.layer === "chip" ? "chip supply-chain weight" : "GDP growth"); }));
  const rb = document.getElementById("resetbtn"); if (rb) rb.addEventListener("click", () => { const el = document.getElementById("asiamap"); if (el) el.style.opacity = "1"; CHART && CHART.setOption({ geo: { zoom: 1.35, center: [104, 24] } }); });
}

render();
