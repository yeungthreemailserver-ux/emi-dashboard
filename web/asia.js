// Asia overview — level-1 of the drill-down (Asia → country → city → cluster).
// Geographic bubble map (countries positioned by lon/lat, sized by chip-weight, coloured by the
// toggled layer); click a LIVE country to drill into its page. Upgrades to a filled choropleth
// once an Asia GeoJSON is vendored. Reuses china.css + vendored ECharts.
const ASIA = window.ASIA;
const STATE = { layer: "chip" };
const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

function lerp(a, b, t) {
  const h = (x) => [parseInt(x.slice(1, 3), 16), parseInt(x.slice(3, 5), 16), parseInt(x.slice(5, 7), 16)];
  const [r1, g1, b1] = h(a), [r2, g2, b2] = h(b); t = Math.max(0, Math.min(1, t));
  const m = (u, v) => Math.round(u + (v - u) * t);
  return `rgb(${m(r1, r2)},${m(g1, g2)},${m(b1, b2)})`;
}
const chipColor = (v) => lerp("#dbeafe", "#1e3a8a", v / 100);
const gdpColor = (v) => lerp("#dcfce7", "#15803d", v / 7);

let CHART = null;
function buildOption() {
  const data = ASIA.countries.map((c) => {
    const live = c.status === "live";
    // every country coloured by the selected layer (so the whole Asia chip landscape shows);
    // live vs planned distinguished by border / opacity / clickability instead.
    const color = STATE.layer === "chip" ? chipColor(c.chip) : gdpColor(c.gdp);
    return {
      name: c.name, value: [c.lon, c.lat], symbolSize: 16 + c.chip * 0.5,
      href: c.href, chip: c.chip, gdp: c.gdp, status: c.status, headline: c.headline,
      itemStyle: { color, opacity: live ? 0.95 : 0.55, borderColor: live ? "#0f172a" : "#94a3b8", borderWidth: live ? 2 : 1, borderType: live ? "solid" : "dashed", shadowBlur: live ? 7 : 0, shadowColor: "rgba(15,23,42,.2)" },
      label: { show: true, position: "right", formatter: c.name + (live ? "" : " ·soon"), fontSize: live ? 12.5 : 10.5, fontWeight: live ? 700 : 400, color: live ? "#0f172a" : "#64748b" },
    };
  });
  return {
    grid: { left: 8, right: 8, top: 8, bottom: 8 },
    xAxis: { type: "value", min: 70, max: 150, show: false },
    yAxis: { type: "value", min: -10, max: 50, show: false },
    tooltip: {
      trigger: "item", confine: true,
      backgroundColor: "#fff", borderColor: "rgba(148,163,184,.5)", borderWidth: 0.5, textStyle: { color: "#1e293b", fontSize: 12 },
      formatter: (p) => { const d = p.data; return `<b>${esc(d.name)}</b> · <span style="color:#64748b">${d.status === "live" ? "live ↗ click to drill" : "planned"}</span><br>chip weight <b>${d.chip}</b>/100 · GDP <b>${d.gdp}%</b><br><span style="color:#475569;max-width:240px;display:inline-block;white-space:normal">${esc(d.headline)}</span>`; },
    },
    series: [{ type: "scatter", coordinateSystem: "cartesian2d", data, emphasis: { scale: 1.12 }, cursor: "pointer", z: 3 }],
  };
}
function initMap() {
  const el = document.getElementById("asiamap"); if (!el || !window.echarts) return;
  CHART = echarts.init(el);
  CHART.setOption(buildOption());
  CHART.on("click", (p) => { if (p.data && p.data.href) location.href = p.data.href; });
  window.addEventListener("resize", () => CHART && CHART.resize());
}

function render() {
  const live = ASIA.countries.filter((c) => c.status === "live");
  const cards = live.map((c) => `<a class="morec asia-card" href="${esc(c.href)}"><div class="mk">${esc(c.name)} ↗</div><div class="md">${esc(c.headline)}</div></a>`).join("");
  const planned = ASIA.countries.filter((c) => c.status === "planned").map((c) => esc(c.name)).join(" · ");
  document.getElementById("main").innerHTML = `
    <div class="cty-head"><h1>Asia <span style="font-size:12px;color:var(--muted);font-weight:400">electronics supply-chain map · drill into any country</span></h1>
      <div class="sub">Bubble size = chip supply-chain weight · click a <b>live</b> country to drill in.
        <span class="dim">Filled-country choropleth lands once an Asia map file is vendored.</span></div></div>
    <div class="maptools"><span class="mt-label">Colour by</span>
      <button class="mapbtn${STATE.layer === "chip" ? " active" : ""}" data-layer="chip">Chip supply-chain weight</button>
      <button class="mapbtn${STATE.layer === "gdp" ? " active" : ""}" data-layer="gdp">GDP growth</button></div>
    <div class="asiamap" id="asiamap"></div>
    <div class="legend"><span><i style="color:#0f172a">●</i> solid = live, click to drill</span><span><i style="color:#94a3b8">◌</i> dashed = planned</span><span class="dim">colour = ${STATE.layer === "chip" ? "chip weight" : "GDP growth"} · size = chip weight</span></div>
    <div class="sech">Live countries <span class="dim">${live.length} of ${ASIA.countries.length} · planned: ${planned}</span></div>
    <div class="more-grid">${cards}</div>`;
  initMap();
  document.querySelectorAll(".mapbtn[data-layer]").forEach((b) => b.addEventListener("click", () => { STATE.layer = b.dataset.layer; render(); }));
}

render();
