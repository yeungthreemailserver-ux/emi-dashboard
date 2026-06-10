/* MMI — macro + semiconductor market environment. Region-aware (APAC/EMEA/AMER). ECharts. Reads data.json. */
const charts = [];
let DATA = null;
const STATE = { region: "APAC" };

const PALETTE = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#64748b"];
const fmtUSD = v => {
  if (v == null || isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(0) + "M";
  return "$" + (+v).toFixed(0);
};
const pct = v => v == null ? "" : (v >= 0 ? "+" : "") + v.toFixed(1) + "%";
const qOf = end => { const [y, m] = end.split("-").map(Number); return `${y}Q${Math.ceil(m / 3)}`; };
const axis = () => ({ axisLine: { lineStyle: { color: "#cbd5e1" } }, axisLabel: { color: "#64748b", fontSize: 10 },
  splitLine: { lineStyle: { color: "#eef2f6" } }, nameTextStyle: { color: "#94a3b8", fontSize: 10 } });
const mk = (id, opt) => { const el = document.getElementById(id); if (!el) return; const c = echarts.init(el); c.setOption(opt); charts.push(c); };
const disposeAll = () => { charts.forEach(c => { try { c.dispose(); } catch (e) {} }); charts.length = 0; };

/* ---- WSTS regional billings (the industry anchor) ---- */
const wstsName = S => (S.wsts_region || {})[STATE.region];
const wstsSeries = (S, sheet) => { const w = (S.wsts || {})[sheet] || {}; return w[wstsName(S)] || []; };
const yoyLast = pts => {
  if (!pts || pts.length < 13) return null;
  const a = pts[pts.length - 1].val, b = pts[pts.length - 13].val;
  return b ? (a - b) / b * 100 : null;
};

/* ---- combined hyperscaler capex per calendar quarter (global AI/datacenter signal) ---- */
function capexCombined(hs) {
  const byQ = {};
  Object.values(hs || {}).forEach(pts => (pts || []).forEach(p => { const q = qOf(p.end); (byQ[q] = byQ[q] || { sum: 0, n: 0 }); byQ[q].sum += p.val; byQ[q].n++; }));
  return Object.keys(byQ).sort().map(q => ({ q, sum: byQ[q].sum, n: byQ[q].n }));
}

function renderKPIs(S) {
  const mma = wstsSeries(S, "mma3");
  const billLast = mma.length ? mma[mma.length - 1] : null, billYoY = yoyLast(mma);
  const econ = (S.regions || {})[STATE.region] || [];
  const wb = S.worldbank || {};
  const gdp = iso => { const p = ((wb[iso] || {}).series || {})["NY.GDP.MKTP.CD"]; return p && p.points.length ? p.points[p.points.length - 1] : null; };
  const leader = econ.map(iso => ({ iso, g: gdp(iso) })).filter(x => x.g).sort((a, b) => b.g.value - a.g.value)[0];
  const expSum = econ.reduce((a, iso) => { const p = ((wb[iso] || {}).series || {})["TX.VAL.TECH.CD"]; return a + (p && p.points.length ? (p.points[p.points.length - 1].value || 0) : 0); }, 0);
  const comb = capexCombined(S.hyperscaler_capex).filter(r => r.n >= 3);
  const cl = comb[comb.length - 1], cy = comb[comb.length - 5];
  const capYoY = cl && cy ? (cl.sum - cy.sum) / cy.sum * 100 : null;
  const dcls = v => v == null ? "flat" : v >= 1 ? "up" : v <= -1 ? "down" : "flat";
  const arr = v => v == null ? "" : v >= 1 ? "▲" : v <= -1 ? "▼" : "→";
  const cards = [
    { lbl: `${STATE.region} semi billings`, val: billLast ? fmtUSD(billLast.val) : "—", d: billYoY, dt: billYoY != null ? `${arr(billYoY)} ${pct(billYoY)} YoY` : "", ctx: billLast ? `${billLast.ym} · WSTS 3MMA/mo` : "WSTS" },
    { lbl: leader ? `${(S.region_names || {})[STATE.region]?.[leader.iso] || leader.iso} GDP` : "Largest GDP", val: leader ? fmtUSD(leader.g.value) : "—", d: null, dt: "", ctx: leader ? `${leader.g.date} · World Bank` : "" },
    { lbl: `${STATE.region} high-tech exports`, val: expSum ? fmtUSD(expSum) : "—", d: null, dt: "", ctx: "World Bank · latest yr" },
    { lbl: "Hyperscaler capex / Q (global)", val: cl ? fmtUSD(cl.sum) : "—", d: capYoY, dt: capYoY != null ? `${arr(capYoY)} ${pct(capYoY)} YoY` : "", ctx: cl ? `${cl.q} · AI/datacenter` : "" },
  ];
  return `<div class="kpis">${cards.map(c => `<div class="kpi"><div class="lbl">${c.lbl}</div><div class="val">${c.val}</div>${c.dt ? `<div class="delta ${dcls(c.d)}">${c.dt}</div>` : ""}<div class="ctx">${c.ctx}</div></div>`).join("")}</div>`;
}

function chartBillingsHero(S) {
  const mma = wstsSeries(S, "mma3");
  const x = mma.map(p => p.ym), y = mma.map(p => +(p.val / 1e9).toFixed(2));
  mk("ch_bill", {
    tooltip: { trigger: "axis", valueFormatter: v => "$" + v + "B" },
    grid: { left: 50, right: 16, top: 16, bottom: 40 },
    xAxis: { type: "category", data: x, ...axis(), axisLabel: { color: "#64748b", fontSize: 9, interval: Math.floor(x.length / 8) } },
    yAxis: { type: "value", name: "US$B / mo", min: 0, ...axis() },
    dataZoom: [{ type: "inside", start: 50 }, { type: "slider", height: 14, bottom: 6 }],
    series: [{ type: "line", smooth: true, symbol: "none", data: y, areaStyle: { color: "rgba(37,99,235,.10)" }, lineStyle: { color: "#2563eb", width: 2 } }],
  });
}

function chartRegionCompare(S) {
  const w = (S.wsts || {}).mma3 || {};
  const regs = ["Americas", "Europe", "Japan", "Asia Pacific"];
  const x = (w["Asia Pacific"] || w[regs[0]] || []).map(p => p.ym);
  const series = regs.map((r, i) => ({
    name: r, type: "line", smooth: true, symbol: "none",
    lineStyle: { width: r === wstsName(S) ? 3 : 1.3, color: PALETTE[i] }, emphasis: { focus: "series" },
    data: (w[r] || []).map(p => +(p.val / 1e9).toFixed(2)),
  }));
  mk("ch_cmp", {
    tooltip: { trigger: "axis", valueFormatter: v => "$" + v + "B" },
    legend: { top: 0, textStyle: { fontSize: 11, color: "#334155" } },
    grid: { left: 46, right: 14, top: 28, bottom: 28 },
    xAxis: { type: "category", data: x, ...axis(), axisLabel: { color: "#64748b", fontSize: 9, interval: Math.floor(x.length / 7) } },
    yAxis: { type: "value", name: "US$B/mo", min: 0, ...axis() },
    series,
  });
}

function chartGDP(S) {
  const wb = S.worldbank || {}, econ = (S.regions || {})[STATE.region] || [];
  const names = (S.region_names || {})[STATE.region] || {};
  const have = econ.filter(iso => (((wb[iso] || {}).series || {})["NY.GDP.MKTP.CD"] || { points: [] }).points.length);
  const yrs = [...new Set(have.flatMap(i => wb[i].series["NY.GDP.MKTP.CD"].points.map(p => p.date)))].sort();
  const series = have.map((iso, i) => {
    const pts = wb[iso].series["NY.GDP.MKTP.CD"].points, base = pts[0].value;
    return { name: names[iso] || iso, type: "line", smooth: true, symbol: "none", lineStyle: { color: PALETTE[i % PALETTE.length] },
      data: yrs.map(y => { const p = pts.find(x => x.date === y); return p && base ? +(p.value / base * 100).toFixed(1) : null; }), connectNulls: true };
  });
  mk("ch_gdp", {
    tooltip: { trigger: "axis" }, legend: { top: 0, type: "scroll", textStyle: { fontSize: 10, color: "#334155" } },
    grid: { left: 44, right: 14, top: 28, bottom: 26 },
    xAxis: { type: "category", data: yrs, ...axis() }, yAxis: { type: "value", name: `idx (${yrs[0] || ""}=100)`, ...axis() }, series,
  });
}

function chartExports(S) {
  const wb = S.worldbank || {}, econ = (S.regions || {})[STATE.region] || [];
  const names = (S.region_names || {})[STATE.region] || {};
  const rows = econ.map(iso => { const pts = (((wb[iso] || {}).series || {})["TX.VAL.TECH.CD"] || { points: [] }).points; return { name: names[iso] || iso, v: pts.length ? pts[pts.length - 1].value / 1e9 : 0 }; })
    .filter(r => r.v > 0).sort((a, b) => a.v - b.v);
  mk("ch_exp", {
    tooltip: { trigger: "axis", valueFormatter: v => "$" + (+v).toFixed(0) + "B" },
    grid: { left: 92, right: 28, top: 12, bottom: 24 },
    xAxis: { type: "value", name: "US$B", min: 0, ...axis() }, yAxis: { type: "category", data: rows.map(r => r.name), ...axis() },
    series: [{ type: "bar", data: rows.map(r => +r.v.toFixed(1)), itemStyle: { color: "#16a34a", borderRadius: [0, 3, 3, 0] }, barWidth: "55%",
      label: { show: true, position: "right", color: "#64748b", fontSize: 10, formatter: p => "$" + p.value + "B" } }],
  });
}

function chartCapex(S) {
  const hs = S.hyperscaler_capex || {};
  const allQ = [...new Set(Object.values(hs).flatMap(p => p.map(x => qOf(x.end))))].sort();
  const series = Object.keys(hs).map((name, i) => ({ name, type: "line", smooth: true, symbol: "none", lineStyle: { color: PALETTE[i % PALETTE.length] },
    data: allQ.map(q => { const p = hs[name].find(x => qOf(x.end) === q); return p ? +(p.val / 1e9).toFixed(2) : null; }), connectNulls: true }));
  mk("ch_capex", {
    tooltip: { trigger: "axis", valueFormatter: v => v == null ? "—" : "$" + v + "B" }, legend: { top: 0, textStyle: { fontSize: 11, color: "#334155" } },
    grid: { left: 44, right: 14, top: 28, bottom: 40 },
    xAxis: { type: "category", data: allQ, ...axis(), axisLabel: { color: "#64748b", fontSize: 9, interval: Math.floor(allQ.length / 8) } },
    yAxis: { type: "value", name: "US$B/Q", min: 0, ...axis() },
    dataZoom: [{ type: "inside", start: 40 }, { type: "slider", height: 14, bottom: 6 }], series,
  });
}

/* forecast-comparison panel — labeled, dated FORECASTS (different bases; never one headline number) */
function forecastPanel() {
  const f = [
    { src: "Deloitte", yr: "2026E", val: "~$975B", note: "+26% YoY" },
    { src: "IDC", yr: "2026E", val: "$1.29T", note: "+52.8% YoY" },
    { src: "PwC", yr: "2030E", val: ">$1T", note: "8.6% CAGR from ~$627B (2024)" },
    { src: "WSTS/SIA", yr: "2024A", val: "~$628B", note: "actual base" },
  ];
  return `<div class="card full"><h3>Global semiconductor revenue — forecasts <span class="pill warn">forecast</span></h3>
    <div class="csub">Different houses, different bases &amp; AI-share definitions — shown side-by-side, not as one number.</div>
    <div class="fc">${f.map(x => `<div class="fc-card"><div class="fc-src">${x.src}</div><div class="fc-val">${x.val}</div><div class="fc-yr">${x.yr}</div><div class="fc-note">${x.note}</div></div>`).join("")}</div></div>`;
}

function wireTabs() {
  document.querySelectorAll("#regionTabs .tab").forEach(b => {
    b.disabled = false; b.title = "";
    b.onclick = () => { STATE.region = b.dataset.region; render(); };
  });
}

function render() {
  const S = DATA, main = document.getElementById("main");
  if (!S) { main.innerHTML = '<div class="loading">No data — run scripts/fetch_macro.py</div>'; return; }
  document.querySelectorAll("#regionTabs .tab").forEach(b => b.classList.toggle("active", b.dataset.region === STATE.region));
  document.getElementById("asof").textContent = `${STATE.region} · latest available`;
  main.innerHTML = `
    <div class="view-head"><h1>${STATE.region} — macro &amp; semiconductor market environment</h1>
      <div class="sub">Executive summary · overview-first · macro → industry → end-market</div></div>
    ${renderKPIs(S)}
    <div class="grid">
      <div class="card full"><h3>${STATE.region} semiconductor billings — WSTS (3-month moving avg)</h3>
        <div class="csub">US$B/month · the industry revenue anchor · drag the slider to zoom</div><div class="chart" id="ch_bill"></div></div>
      <div class="card"><h3>Billings by region — WSTS</h3><div class="csub">${STATE.region} highlighted · US$B/mo (3MMA)</div><div class="chart" id="ch_cmp"></div></div>
      <div class="card"><h3>GDP — indexed</h3><div class="csub">${STATE.region} economies · World Bank (annual)</div><div class="chart" id="ch_gdp"></div></div>
      <div class="card"><h3>High-tech exports — latest year</h3><div class="csub">US$B · World Bank</div><div class="chart" id="ch_exp"></div></div>
      <div class="card"><h3>AI / datacenter — hyperscaler capex (global)</h3><div class="csub">US$B/quarter · SEC EDGAR · dominant semi end-market</div><div class="chart" id="ch_capex"></div></div>
      ${forecastPanel()}
    </div>`;
  disposeAll();
  chartBillingsHero(S); chartRegionCompare(S); chartGDP(S); chartExports(S); chartCapex(S);
  const us = S.us_macro || {}, gdp = (us.GDP || [])[0], cpi = (us.CPI || [])[0], fredN = Object.keys(S.fred || {}).length;
  document.getElementById("foot").innerHTML =
    `<b>Sources:</b> WSTS Blue Book (billings) · World Bank WDI (macro) · SEC EDGAR (capex) · FMP (US macro${gdp ? `: GDP ${fmtUSD(gdp.value * (gdp.value < 1e6 ? 1e9 : 1))}` : ""}${cpi ? `, CPI ${(+cpi.value).toFixed(1)}` : ""}). ` +
    `<span class="pill warn">gap</span> Taiwan absent from World Bank → FRED/DGBAS (FRED ${fredN ? "loaded" : "unreachable from this network"}). ` +
    `<span class="pill warn">next</span> detail tier (small-multiples macro), end-market shipments (auto/PC/smartphone), PMI.`;
}

window.addEventListener("resize", () => charts.forEach(c => { try { c.resize(); } catch (e) {} }));
(async () => {
  try { DATA = await (await fetch("macro-data.json", { cache: "no-store" })).json(); } catch (e) { DATA = null; }
  wireTabs(); render();
})();
