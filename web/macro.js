/* EMI · Macro — semiconductor market environment, organised as a 3-layer terminal:
   Layer 1  Climate board  — regime read + indicator chips grouped by category (at-a-glance)
   Layer 2  Category panels — multi-layer combo charts (level + YoY bars + reference) & comparisons
   Layer 3  Detail tier     — small-multiples, full indicator scorecards, forecast comparison
   Region-aware (APAC/EMEA/AMER). All metrics derived client-side from window.MMI. ECharts. */
const charts = [];
let DATA = null;
const STATE = { region: "APAC" };

const PALETTE = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#64748b"];
const GREEN = "#16a34a", RED = "#dc2626", GREY = "#94a3b8", LINE2 = "#cbd5e1";

/* ---- formatting ---- */
const fmtUSD = v => {
  if (v == null || isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(0) + "M";
  return "$" + (+v).toFixed(0);
};
const pct = v => v == null ? "" : (v >= 0 ? "+" : "") + v.toFixed(1) + "%";
const sign1 = v => v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(1);
const qOf = end => { const [y, m] = end.split("-").map(Number); return `${y}Q${Math.ceil(m / 3)}`; };
const axis = () => ({ axisLine: { lineStyle: { color: LINE2 } }, axisLabel: { color: "#64748b", fontSize: 10 },
  splitLine: { lineStyle: { color: "#eef2f6" } }, nameTextStyle: { color: GREY, fontSize: 10 } });
const mk = (id, opt) => { const el = document.getElementById(id); if (!el) return null; const c = echarts.init(el); c.setOption(opt); charts.push(c); return c; };
const mkEl = (el, opt) => { const c = echarts.init(el); c.setOption(opt); charts.push(c); return c; };
const disposeAll = () => { charts.forEach(c => { try { c.dispose(); } catch (e) {} }); charts.length = 0; };

/* ---- series accessors (everything normalised to [{x, v}] ascending) ---- */
const wstsName = S => (S.wsts_region || {})[STATE.region];
const wstsSeries = (S, sheet) => { const w = (S.wsts || {})[sheet] || {}; return w[wstsName(S)] || []; };
const billingsPts = S => wstsSeries(S, "mma3").map(p => ({ x: p.ym, v: p.val }));
function capexCombined(hs) {
  const byQ = {};
  Object.values(hs || {}).forEach(pts => (pts || []).forEach(p => { const q = qOf(p.end); (byQ[q] = byQ[q] || { sum: 0, n: 0 }); byQ[q].sum += p.val; byQ[q].n++; }));
  return Object.keys(byQ).sort().map(q => ({ q, sum: byQ[q].sum, n: byQ[q].n }));
}
const capexPts = S => capexCombined(S.hyperscaler_capex).filter(r => r.n >= 3).map(r => ({ x: r.q, v: r.sum }));
const fredPts = (S, id) => { const o = (S.fred || {})[id]; return o && o.points ? o.points.map(p => ({ x: p.date, v: +p.value })) : []; };
const wbPts = (S, iso, code) => { const p = (((S.worldbank || {})[iso] || {}).series || {})[code]; return p && p.points ? p.points.map(q => ({ x: q.date, v: +q.value })) : []; };
const regionEcon = S => (S.regions || {})[STATE.region] || [];
const econName = (S, iso) => ((S.region_names || {})[STATE.region] || {})[iso] || iso;
const autoPts = S => (((S.auto || {}).production_by_region || {})[STATE.region] || []).map(p => ({ x: String(p.year), v: p.units }));

function leaderGDP(S) {
  let best = null;
  regionEcon(S).forEach(iso => { const pts = wbPts(S, iso, "NY.GDP.MKTP.CD"); if (pts.length) { const last = pts[pts.length - 1]; if (!best || last.v > best.v) best = { iso, v: last.v, date: last.x, pts }; } });
  return best;
}
function exportsSumPts(S) {
  const byYear = {};
  regionEcon(S).forEach(iso => wbPts(S, iso, "TX.VAL.TECH.CD").forEach(p => { byYear[p.x] = (byYear[p.x] || 0) + p.v; }));
  return Object.keys(byYear).sort().map(y => ({ x: y, v: byYear[y] }));
}

/* ---- analytics: YoY series + vs-history metrics + verdict ---- */
function yoyArr(pts, ppy) {                                   // YoY% aligned to pts (null for first ppy)
  return pts.map((p, i) => (i >= ppy && pts[i - ppy].v) ? +(((p.v - pts[i - ppy].v) / pts[i - ppy].v) * 100).toFixed(1) : null);
}
function vsHistory(pts, ppy, mode) {
  if (!pts || !pts.length) return null;
  const v = pts.map(p => p.v), n = v.length - 1, latest = v[n];
  let dir, series;                                            // dir = the headline directional metric; series = its history
  if (mode === "rate") { series = v.slice(); dir = latest; }
  else { series = yoyArr(pts, ppy).filter(x => x != null); dir = (n >= ppy && v[n - ppy]) ? (v[n] - v[n - ppy]) / v[n - ppy] * 100 : null; }
  const mom = (n >= 1 && v[n - 1]) ? (v[n] - v[n - 1]) / v[n - 1] * 100 : null;
  let m3 = null;                                              // 3M/3M annualised (monthly level only)
  if (mode !== "rate" && ppy === 12 && n >= 5) {
    const avg = (a, b) => { let s = 0, c = 0; for (let i = Math.max(0, a); i <= b; i++) if (v[i] != null) { s += v[i]; c++; } return c ? s / c : null; };
    const a = avg(n - 2, n), b = avg(n - 5, n - 3); m3 = (a && b) ? (Math.pow(a / b, 4) - 1) * 100 : null;
  }
  const mean = series.reduce((s, x) => s + x, 0) / (series.length || 1);
  const sd = Math.sqrt(series.reduce((s, x) => s + (x - mean) ** 2, 0) / (series.length || 1));
  const pctile = (dir != null && series.length) ? Math.round(series.filter(x => x <= dir).length / series.length * 100) : null;
  const z = (dir != null && sd) ? (dir - mean) / sd : null;
  const momTrend = (mode === "rate") ? (n >= 3 ? v[n] - v[n - 3] : null)
                                     : (() => { const y = yoyArr(pts, ppy); return (y[n] != null && y[n - 3] != null) ? y[n] - y[n - 3] : null; })();
  return { latest, date: pts[n].x, dir, mom, m3, pctile, z, momTrend, yearsHist: ppy ? Math.round((mode === "rate" ? series.length : series.length) / ppy) : null, n: pts.length };
}
function verdict(kind, m) {
  if (!m || m.dir == null) return { word: "—", cls: "flat" };
  const d = m.dir, rising = (m.momTrend || 0) > 0.3, falling = (m.momTrend || 0) < -0.3;
  if (kind === "price") {
    if (d > 3) return { word: rising ? "Hot" : "Elevated", cls: "down" };      // input-cost pressure = headwind (red)
    if (d > 1) return { word: "Firm", cls: "flat" };
    if (d < -0.5) return { word: "Deflating", cls: "up" };
    return { word: falling ? "Easing" : "Stable", cls: "up" };
  }
  if (d >= 5) return { word: rising ? "Accelerating" : "Expanding", cls: "up" };
  if (d >= 0) return { word: falling ? "Softening" : "Expanding", cls: "up" };
  if (d > -5) return { word: "Cooling", cls: "down" };
  return { word: rising ? "Bottoming" : "Contracting", cls: "down" };
}

/* ====================================================================== *
 *  CHART FACTORIES (the reusable multi-layer vocabulary)
 * ====================================================================== */

/* signature combo: level line (left axis) + YoY% bars (right axis) + zero & avg reference lines */
function comboChart(elId, x, level, yoy, opts = {}) {
  const compact = opts.compact, avgVal = opts.avg ? level.filter(v => v != null).reduce((s, v) => s + v, 0) / (level.filter(v => v != null).length || 1) : null;
  const lvlName = opts.levelName || "Level", lvlFmt = opts.levelFmt || (v => v);
  const o = {
    tooltip: { trigger: "axis", valueFormatter: null },
    legend: { top: 0, right: 4, textStyle: { fontSize: 10, color: "#334155" }, data: [lvlName, "YoY %"], itemWidth: 14, itemHeight: 8 },
    grid: { left: compact ? 44 : 52, right: compact ? 40 : 46, top: 26, bottom: compact ? 26 : 40 },
    xAxis: { type: "category", data: x, ...axis(), axisLabel: { color: "#64748b", fontSize: 9, interval: Math.floor(x.length / (compact ? 6 : 9)) } },
    yAxis: [
      { type: "value", name: opts.levelUnit || "", scale: true, ...axis(), axisLabel: { color: "#64748b", fontSize: 9, formatter: lvlFmt } },
      { type: "value", name: "YoY %", ...axis(), axisLabel: { color: "#64748b", fontSize: 9, formatter: "{value}%" } },
    ],
    series: [
      { name: lvlName, type: "line", yAxisIndex: 0, data: level, smooth: true, symbol: "none", z: 3,
        lineStyle: { color: opts.levelColor || GREY, width: 1.8 }, tooltip: { valueFormatter: v => v == null ? "—" : lvlFmt(v) },
        markLine: avgVal != null ? { silent: true, symbol: "none", lineStyle: { type: "dashed", color: LINE2, width: 1 }, label: { formatter: "avg", fontSize: 9, color: GREY }, data: [{ yAxis: +avgVal.toFixed(2) }] } : undefined },
      { name: "YoY %", type: "bar", yAxisIndex: 1, barWidth: "58%", tooltip: { valueFormatter: v => v == null ? "—" : (v >= 0 ? "+" : "") + v + "%" },
        data: yoy.map(v => v == null ? null : ({ value: v, itemStyle: { color: v >= 0 ? GREEN : RED } })),
        markLine: { silent: true, symbol: "none", lineStyle: { color: LINE2, width: 1 }, label: { show: false }, data: [{ yAxis: 0 }] } },
    ],
  };
  if (!compact) o.dataZoom = [{ type: "inside", start: opts.zoomStart || 40 }, { type: "slider", height: 14, bottom: 6 }];
  return mk(elId, o);
}

/* multi-series comparison overlay; the active region/economy is bold. opts.rate adds a zero line + % */
function compareLines(elId, x, defs, active, opts = {}) {
  const series = defs.map((d, i) => ({
    name: d.name, type: "line", smooth: true, symbol: "none", connectNulls: true, emphasis: { focus: "series" },
    lineStyle: { width: d.name === active ? 3 : 1.4, color: d.color || PALETTE[i % PALETTE.length] },
    data: d.data,
    ...(i === 0 && opts.rate ? { markLine: { silent: true, symbol: "none", lineStyle: { color: LINE2 }, data: [{ yAxis: 0 }] } } : {}),
  }));
  return mk(elId, {
    tooltip: { trigger: "axis", valueFormatter: opts.fmt || (v => v) },
    legend: { top: 0, type: "scroll", textStyle: { fontSize: 10, color: "#334155" } },
    grid: { left: opts.left || 46, right: 14, top: 28, bottom: opts.zoom ? 40 : 26 },
    xAxis: { type: "category", data: x, ...axis(), axisLabel: { color: "#64748b", fontSize: 9, interval: x.length > 16 ? Math.floor(x.length / 8) : 0 } },
    yAxis: { type: "value", name: opts.unit || "", scale: !!opts.scale, ...axis() },
    ...(opts.zoom ? { dataZoom: [{ type: "inside", start: opts.zoomStart || 0 }, { type: "slider", height: 14, bottom: 6 }] } : {}),
    series,
  });
}

/* horizontal ranking bar (exports by economy) */
function rankBar(elId, rows, opts = {}) {
  return mk(elId, {
    tooltip: { trigger: "axis", valueFormatter: opts.fmt || (v => v) },
    grid: { left: 96, right: 30, top: 10, bottom: 24 },
    xAxis: { type: "value", name: opts.unit || "", min: 0, ...axis() },
    yAxis: { type: "category", data: rows.map(r => r.name), ...axis() },
    series: [{ type: "bar", data: rows.map(r => +r.v.toFixed(1)), barWidth: "58%", itemStyle: { color: opts.color || GREEN, borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: "right", color: "#64748b", fontSize: 10, formatter: p => (opts.lbl ? opts.lbl(p.value) : p.value) } }],
  });
}

/* US Treasury yield curve (snapshot, x = tenor) */
function yieldCurve(elId, t) {
  if (!t) return null;
  const tenors = [["1M", "month1"], ["3M", "month3"], ["6M", "month6"], ["1Y", "year1"], ["2Y", "year2"], ["3Y", "year3"], ["5Y", "year5"], ["7Y", "year7"], ["10Y", "year10"], ["20Y", "year20"], ["30Y", "year30"]];
  const have = tenors.filter(([, k]) => t[k] != null);
  return mk(elId, {
    tooltip: { trigger: "axis", valueFormatter: v => v + "%" },
    grid: { left: 40, right: 16, top: 16, bottom: 26 },
    xAxis: { type: "category", data: have.map(([l]) => l), boundaryGap: false, ...axis() },
    yAxis: { type: "value", name: "%", scale: true, ...axis() },
    series: [{ type: "line", smooth: true, symbol: "circle", symbolSize: 5, data: have.map(([, k]) => t[k]),
      lineStyle: { color: PALETTE[4], width: 2 }, itemStyle: { color: PALETTE[4] }, areaStyle: { color: "rgba(124,58,237,.07)" } }],
  });
}

/* chip mini-spark: directional bars (green/red), no axes */
function miniBars(el, vals) {
  mkEl(el, {
    grid: { left: 1, right: 1, top: 2, bottom: 1 },
    xAxis: { type: "category", show: false, data: vals.map((_, i) => i) },
    yAxis: { type: "value", show: false },
    tooltip: { show: false },
    series: [{ type: "bar", data: vals.map(v => ({ value: v, itemStyle: { color: v >= 0 ? GREEN : RED } })), barWidth: "70%" }],
  });
}

/* ====================================================================== *
 *  INDICATOR REGISTRY — one definition per metric, grouped by category
 * ====================================================================== */
const CATEGORIES = [
  { key: "cycle",    title: "The Cycle",                    accent: "#2563eb", blurb: "Where are we in the semiconductor cycle?" },
  { key: "demand",   title: "Demand & End-Markets",         accent: "#7c3aed", blurb: "What pulls chips — AI capex, autos, devices" },
  { key: "industry", title: "Industrial Activity",          accent: "#0891b2", blurb: "Is the manufacturing economy expanding?" },
  { key: "prices",   title: "Prices & Costs",               accent: "#d97706", blurb: "Pricing power and input-cost pressure" },
  { key: "trade",    title: "Trade & Export Engines",       accent: "#16a34a", blurb: "Who ships the electronics" },
  { key: "growth",   title: "Growth & Financial Backdrop",  accent: "#64748b", blurb: "The wider economy and the cost of money" },
];

/* build the live indicator list for the current region (each carries computed metrics) */
function buildIndicators(S) {
  const R = STATE.region, out = [];
  const add = (def) => {
    if (def.regions && def.regions.indexOf(R) < 0) return;     // not tracked for this region
    const pts = def.pts; if (!pts || pts.length < 2) return;
    out.push({ ...def, m: vsHistory(pts, def.ppy, def.mode), v: verdict(def.kind, vsHistory(pts, def.ppy, def.mode)) });
  };
  const bn = b => "$" + (b / 1e9).toFixed(0) + "B";
  // 1 — Cycle
  add({ cat: "cycle", label: `${R} semi billings`, geo: "WSTS · 3MMA/mo", mode: "level", ppy: 12, kind: "growth",
    pts: billingsPts(S), fmt: v => fmtUSD(v), levelUnit: "US$B/mo", levelFmt: v => (v / 1e9).toFixed(0) });
  // 2 — Demand
  add({ cat: "demand", label: "Hyperscaler capex", geo: "Global · /quarter", mode: "level", ppy: 4, kind: "growth",
    pts: capexPts(S), fmt: v => fmtUSD(v), levelUnit: "US$B/Q", levelFmt: v => (v / 1e9).toFixed(0) });
  add({ cat: "demand", label: `${R} auto production`, geo: "OICA · /yr · to 2022", mode: "level", ppy: 1, kind: "growth",
    pts: autoPts(S), fmt: v => (v / 1e6).toFixed(1) + "M", levelUnit: "M/yr", levelFmt: v => (v / 1e6).toFixed(0) });
  add({ cat: "demand", label: "US vehicle sales", geo: "FRED · US · SAAR", mode: "level", ppy: 12, kind: "growth",
    pts: fredPts(S, "TOTALSA"), fmt: v => v.toFixed(1) + "M", levelUnit: "M (SAAR)", levelFmt: v => v.toFixed(0) });
  // 3 — Industry (US/Korea/Japan = the global chip-making pulse; shown on every tab, geo-labelled)
  add({ cat: "industry", label: "US industrial production", geo: "FRED · US · index", mode: "level", ppy: 12, kind: "growth",
    pts: fredPts(S, "INDPRO"), fmt: v => v.toFixed(1), levelUnit: "index", levelFmt: v => v.toFixed(0) });
  add({ cat: "industry", label: "Korea industrial production", geo: "FRED · KR · YoY%", mode: "rate", ppy: 12, kind: "growth",
    pts: fredPts(S, "KORPRINTO01GYSAM"), fmt: v => v.toFixed(1) + "%" });
  add({ cat: "industry", label: "Japan industrial production", geo: "FRED · JP · YoY%", mode: "rate", ppy: 12, kind: "growth",
    pts: fredPts(S, "JPNPRINTO01GYSAM"), fmt: v => v.toFixed(1) + "%" });
  // 4 — Prices
  add({ cat: "prices", label: "US PPI — all commodities", geo: "FRED · US · index", mode: "level", ppy: 12, kind: "price",
    pts: fredPts(S, "PPIACO"), fmt: v => v.toFixed(1), levelUnit: "index", levelFmt: v => v.toFixed(0) });
  const ld = leaderGDP(S);
  if (ld) add({ cat: "prices", label: `${econName(S, ld.iso)} CPI`, geo: "World Bank · YoY%/yr", mode: "rate", ppy: 1, kind: "price",
    pts: wbPts(S, ld.iso, "FP.CPI.TOTL.ZG"), fmt: v => v.toFixed(1) + "%" });
  // 5 — Trade
  add({ cat: "trade", label: `${R} high-tech exports`, geo: "World Bank · /yr", mode: "level", ppy: 1, kind: "growth",
    pts: exportsSumPts(S), fmt: v => fmtUSD(v), levelUnit: "US$B", levelFmt: v => (v / 1e9).toFixed(0) });
  // 6 — Growth
  if (ld) add({ cat: "growth", label: `${econName(S, ld.iso)} GDP`, geo: "World Bank · /yr", mode: "level", ppy: 1, kind: "growth",
    pts: ld.pts, fmt: v => fmtUSD(v), levelUnit: "US$", levelFmt: v => (v / 1e12).toFixed(1) + "T" });
  return out;
}

/* ====================================================================== *
 *  LAYER 1 — climate board
 * ====================================================================== */
function regimeRead(S, inds) {
  const by = k => inds.filter(i => i.cat === k);
  const cyc = by("cycle")[0];
  if (!cyc || !cyc.m) return `${STATE.region} — semiconductor market environment`;
  const phase = cyc.v.word.toLowerCase();
  const bits = [`billings ${pct(cyc.m.dir)} YoY${cyc.m.pctile != null ? ` (${cyc.m.pctile}th pctile of ${cyc.m.yearsHist}y)` : ""}`];
  const cap = by("demand").find(i => i.label.indexOf("capex") >= 0);
  if (cap && cap.m) bits.push(`AI capex ${cap.v.word.toLowerCase()}`);
  const ind = by("industry")[0];
  if (ind && ind.m) bits.push(`industrial output ${ind.v.word.toLowerCase()}`);
  const pr = by("prices")[0];
  if (pr && pr.m) bits.push(`prices ${pr.v.word.toLowerCase()}`);
  return `${STATE.region} semis: ${phase} — ${bits.join(" · ")}.`;
}

function climateBoardHTML(S, inds) {
  const sparkJobs = [];
  const chip = (i) => {
    const m = i.m, big = i.mode === "rate" ? sign1(m.latest) + "%" : i.fmt(m.latest);
    const subMetric = i.mode === "rate"
      ? (m.pctile != null ? `${m.pctile}th pctile` : "")
      : `<b class="${m.dir >= 0 ? "up" : "down"}">${pct(m.dir)}</b> YoY`;
    const sparkId = "spk_" + Math.random().toString(36).slice(2, 9);
    const series = (i.mode === "rate" ? i.pts.map(p => p.v) : yoyArr(i.pts, i.ppy)).filter(v => v != null).slice(-24);
    sparkJobs.push({ id: sparkId, vals: series });
    const bar = m.pctile != null ? `<span class="sc-bar" title="${m.pctile}th percentile vs own history"><i style="width:${m.pctile}%"></i></span>` : "";
    return `<div class="chip">
      <div class="chip-top"><span class="chip-lbl">${i.label}</span><span class="verdict ${i.v.cls}">${i.v.word}</span></div>
      <div class="chip-val">${big} <span class="chip-sub">${subMetric}</span></div>
      <div class="chip-foot">${bar}<span class="chip-geo">${i.geo}</span></div>
      <div class="chip-spark" id="${sparkId}"></div></div>`;
  };
  const groups = CATEGORIES.map(c => {
    const items = inds.filter(i => i.cat === c.key);
    const body = items.length ? items.map(chip).join("")
      : `<div class="chip chip-empty">Not tracked for ${STATE.region}</div>`;
    return `<div class="cat-group"><div class="cat-group-h" style="--accent:${c.accent}">${c.title}</div><div class="chip-row">${body}</div></div>`;
  }).join("");
  return { html: `<div class="board">${groups}</div>`, sparkJobs };
}

/* ====================================================================== *
 *  LAYER 2 — category panels (rendered after innerHTML set)
 * ====================================================================== */
function catHead(c, verdictLine) {
  return `<div class="cat-head" style="--accent:${c.accent}"><h2>${c.title}</h2><span class="cat-blurb">${c.blurb}</span>
    ${verdictLine ? `<div class="cat-read">${verdictLine}</div>` : ""}</div>`;
}

function renderCycle(S, inds) {
  const b = billingsPts(S); if (!b.length) return;
  comboChart("ch_bill", b.map(p => p.x), b.map(p => +(p.v / 1e9).toFixed(2)), yoyArr(b, 12),
    { levelName: "Billings", levelUnit: "US$B/mo", levelColor: "#2563eb", levelFmt: v => v.toFixed(0), avg: false, zoomStart: 45 });
  const w = (S.wsts || {}).mma3 || {}, regs = ["Americas", "Europe", "Japan", "Asia Pacific"];
  const x = (w["Asia Pacific"] || []).map(p => p.ym);
  compareLines("ch_cmp", x, regs.map((r, i) => ({ name: r, color: PALETTE[i], data: (w[r] || []).map(p => +(p.val / 1e9).toFixed(2)) })),
    wstsName(S), { unit: "US$B/mo", fmt: v => "$" + v + "B", zoom: true, zoomStart: 45 });
}

function renderDemand(S) {
  const c = capexPts(S);
  if (c.length) comboChart("ch_capex", c.map(p => p.x), c.map(p => +(p.v / 1e9).toFixed(1)), yoyArr(c, 4),
    { levelName: "Capex", levelUnit: "US$B/Q", levelColor: PALETTE[4], levelFmt: v => v.toFixed(0) });
  const a = ((S.auto || {}).production_by_region) || {}, regs = ["APAC", "EMEA", "AMER"];
  const ax = (a.APAC || []).map(p => String(p.year));
  if (ax.length) compareLines("ch_auto", ax, regs.map((r, i) => ({ name: r, color: PALETTE[i], data: (a[r] || []).map(p => +(p.units / 1e6).toFixed(2)) })),
    STATE.region, { unit: "M units/yr", fmt: v => v + "M" });
}

function renderIndustry(S) {
  // hero comparison: industrial-production YoY across the key semiconductor-economy makers
  const us = fredPts(S, "INDPRO"), kr = fredPts(S, "KORPRINTO01GYSAM"), jp = fredPts(S, "JPNPRINTO01GYSAM");
  const months = [...new Set([...us, ...kr, ...jp].map(p => p.x))].sort();
  const align = (pts, isLevel) => { const map = Object.fromEntries((isLevel ? pts.map((p, i) => [p.x, yoyArr(pts, 12)[i]]) : pts.map(p => [p.x, p.v]))); return months.map(m => map[m] ?? null); };
  const defs = [];
  if (us.length) defs.push({ name: "US", color: PALETTE[0], data: align(us, true) });
  if (kr.length) defs.push({ name: "Korea", color: PALETTE[1], data: align(kr, false) });
  if (jp.length) defs.push({ name: "Japan", color: PALETTE[2], data: align(jp, false) });
  const active = { APAC: "Korea", AMER: "US", EMEA: "" }[STATE.region];
  if (defs.length) compareLines("ch_ind", months, defs, active, { unit: "YoY %", rate: true, fmt: v => v == null ? "—" : (v >= 0 ? "+" : "") + v + "%", zoom: true, zoomStart: 50 });
  // secondary: US INDPRO level+YoY combo
  if (us.length) comboChart("ch_indpro", us.map(p => p.x), us.map(p => +p.v.toFixed(1)), yoyArr(us, 12),
    { levelName: "IndProd", levelUnit: "index", levelColor: PALETTE[5], levelFmt: v => v.toFixed(0), zoomStart: 50 });
}

function renderPrices(S) {
  const ppi = fredPts(S, "PPIACO");
  if (ppi.length) comboChart("ch_ppi", ppi.map(p => p.x), ppi.map(p => +p.v.toFixed(1)), yoyArr(ppi, 12),
    { levelName: "PPI", levelUnit: "index", levelColor: PALETTE[3], levelFmt: v => v.toFixed(0), avg: false, zoomStart: 45 });
  // CPI by economy (annual YoY) — comparison
  const econ = regionEcon(S).filter(iso => wbPts(S, iso, "FP.CPI.TOTL.ZG").length);
  const yrs = [...new Set(econ.flatMap(iso => wbPts(S, iso, "FP.CPI.TOTL.ZG").map(p => p.x)))].sort();
  const defs = econ.map((iso, i) => { const map = Object.fromEntries(wbPts(S, iso, "FP.CPI.TOTL.ZG").map(p => [p.x, +p.v.toFixed(1)])); return { name: econName(S, iso), color: PALETTE[i % PALETTE.length], data: yrs.map(y => map[y] ?? null) }; });
  if (defs.length) compareLines("ch_cpi", yrs, defs, "", { unit: "CPI YoY %", rate: true, fmt: v => v == null ? "—" : v + "%" });
}

function renderTrade(S) {
  const econ = regionEcon(S), names = (S.region_names || {})[STATE.region] || {};
  const rows = econ.map(iso => { const pts = wbPts(S, iso, "TX.VAL.TECH.CD"); return { name: names[iso] || iso, v: pts.length ? pts[pts.length - 1].v / 1e9 : 0 }; })
    .filter(r => r.v > 0).sort((a, b) => a.v - b.v);
  if (rows.length) rankBar("ch_exp", rows, { unit: "US$B", fmt: v => "$" + (+v).toFixed(0) + "B", lbl: v => "$" + v + "B" });
  const yrs = [...new Set(econ.flatMap(iso => wbPts(S, iso, "TX.VAL.TECH.CD").map(p => p.x)))].sort();
  const defs = econ.filter(iso => wbPts(S, iso, "TX.VAL.TECH.CD").length).map((iso, i) => { const map = Object.fromEntries(wbPts(S, iso, "TX.VAL.TECH.CD").map(p => [p.x, +(p.v / 1e9).toFixed(1)])); return { name: names[iso] || iso, color: PALETTE[i % PALETTE.length], data: yrs.map(y => map[y] ?? null) }; });
  if (defs.length) compareLines("ch_exptrend", yrs, defs, "", { unit: "US$B", fmt: v => v == null ? "—" : "$" + v + "B" });
}

function renderGrowth(S) {
  const wb = S.worldbank || {}, econ = regionEcon(S), names = (S.region_names || {})[STATE.region] || {};
  const have = econ.filter(iso => wbPts(S, iso, "NY.GDP.MKTP.CD").length);
  const yrs = [...new Set(have.flatMap(iso => wbPts(S, iso, "NY.GDP.MKTP.CD").map(p => p.x)))].sort();
  const defs = have.map((iso, i) => { const pts = wbPts(S, iso, "NY.GDP.MKTP.CD"), base = pts[0].v, map = Object.fromEntries(pts.map(p => [p.x, p.v])); return { name: names[iso] || iso, color: PALETTE[i % PALETTE.length], data: yrs.map(y => map[y] != null && base ? +(map[y] / base * 100).toFixed(1) : null) }; });
  if (defs.length) compareLines("ch_gdp", yrs, defs, "", { unit: `idx (${yrs[0] || ""}=100)`, fmt: v => v == null ? "—" : v });
  yieldCurve("ch_curve", (S.us_macro || {}).treasury_latest);
}

/* ====================================================================== *
 *  LAYER 3 — detail tier
 * ====================================================================== */
function renderSM(S, containerId, indicator, isLevel) {
  const cont = document.getElementById(containerId); if (!cont) return;
  const econ = regionEcon(S), names = (S.region_names || {})[STATE.region] || {};
  cont.innerHTML = "";
  econ.forEach(iso => {
    const pts = wbPts(S, iso, indicator); if (!pts.length) return;
    const last = pts[pts.length - 1], val = isLevel ? "$" + (last.v / 1e9).toFixed(0) + "B" : (+last.v).toFixed(1) + "%";
    const cell = document.createElement("div"); cell.className = "sm-cell";
    cell.innerHTML = `<div class="sm-lbl">${names[iso] || iso}</div><div class="sm-val">${val}</div><div class="sm-chart"></div>`;
    cont.appendChild(cell);
    mkEl(cell.querySelector(".sm-chart"), {
      grid: { left: 2, right: 2, top: 4, bottom: 2 },
      xAxis: { type: "category", data: pts.map(p => p.x), show: false }, yAxis: { type: "value", show: false, scale: !isLevel },
      tooltip: { trigger: "axis", valueFormatter: v => isLevel ? "$" + v + "B" : v + "%" },
      series: [{ type: "line", smooth: true, symbol: "none", data: pts.map(p => isLevel ? +(p.v / 1e9).toFixed(1) : +(+p.v).toFixed(1)),
        lineStyle: { color: isLevel ? GREEN : "#2563eb", width: 1.6 }, areaStyle: { color: isLevel ? "rgba(22,163,74,.08)" : "rgba(37,99,235,.08)" } }],
    });
  });
}

function renderScorecards(S) {
  const cont = document.getElementById("scorecards"); if (!cont) return;
  const items = [{ id: "PPIACO", label: "US PPI — all commodities", kind: "price" }, { id: "INDPRO", label: "US industrial production", kind: "growth" }, { id: "TOTALSA", label: "US vehicle sales", kind: "growth", unit: "M (SAAR)", fmt: v => v.toFixed(1) + "M" }];
  cont.innerHTML = "";
  items.forEach(it => {
    const pts = fredPts(S, it.id); if (!pts.length) return;
    const m = vsHistory(pts, 12, "level"), v = verdict(it.kind, m), fmt = it.fmt || (x => x.toFixed(1));
    const chip = (lbl, x) => x == null ? "" : `<span class="sc-m">${lbl} <b class="${x >= 0 ? "up" : "down"}">${x >= 0 ? "+" : ""}${x.toFixed(1)}%</b></span>`;
    const card = document.createElement("div"); card.className = "scorecard";
    card.innerHTML = `<div class="sc-head"><span class="sc-name">${it.label}</span><span class="sc-freq">Monthly · FRED · US</span></div>
      <div class="sc-val">${fmt(m.latest)} <span class="sc-date">${m.date}</span> <span class="verdict ${v.cls}">${v.word}</span></div>
      <div class="sc-metrics">${chip("MoM", m.mom)}${chip("YoY", m.dir)}${chip("3M/3M ann.", m.m3)}</div>
      <div class="sc-hist">YoY vs ${m.yearsHist}y: <span class="sc-bar"><i style="width:${m.pctile || 0}%"></i></span> ${m.pctile != null ? m.pctile + "th pct" : ""}${m.z != null ? ` · ${sign1(m.z)}σ` : ""}</div>
      <div class="sc-chart" id="sc_${it.id}"></div>`;
    cont.appendChild(card);
    comboChart(`sc_${it.id}`, pts.map(p => p.x), pts.map(p => +p.v.toFixed(1)), yoyArr(pts, 12),
      { compact: true, levelName: "Level", levelUnit: it.unit || "index", levelFmt: v => v.toFixed(0), levelColor: GREY });
  });
}

function forecastPanel() {
  const f = [
    { src: "Deloitte", yr: "2026E", val: "~$975B", note: "+26% YoY" },
    { src: "IDC", yr: "2026E", val: "$1.29T", note: "+52.8% YoY" },
    { src: "PwC", yr: "2030E", val: ">$1T", note: "8.6% CAGR from ~$627B (2024)" },
    { src: "WSTS/SIA", yr: "2024A", val: "~$628B", note: "actual base" },
  ];
  return `<div class="cat-head" style="--accent:#0891b2"><h2>Outlook — analyst forecasts <span class="pill warn">forecast</span></h2>
    <span class="cat-blurb">Different houses, different bases &amp; AI-share definitions — shown side-by-side, never as one number.</span></div>
    <div class="fc">${f.map(x => `<div class="fc-card"><div class="fc-src">${x.src}</div><div class="fc-val">${x.val}</div><div class="fc-yr">${x.yr}</div><div class="fc-note">${x.note}</div></div>`).join("")}</div>`;
}

/* ====================================================================== *
 *  ORCHESTRATION
 * ====================================================================== */
function wireTabs() {
  document.querySelectorAll("#regionTabs .tab").forEach(b => { b.disabled = false; b.title = ""; b.onclick = () => { STATE.region = b.dataset.region; render(); }; });
}

function panel(c, id, sub) { return `<div class="card"><h3>${c.title}</h3><div class="csub">${sub}</div><div class="chart" id="${id}"></div></div>`; }

function render() {
  const S = DATA, main = document.getElementById("main");
  if (!S) { main.innerHTML = '<div class="loading">No data — run scripts/fetch_macro.py</div>'; return; }
  document.querySelectorAll("#regionTabs .tab").forEach(b => b.classList.toggle("active", b.dataset.region === STATE.region));
  document.getElementById("asof").textContent = `${STATE.region} · latest available`;
  const inds = buildIndicators(S);
  const board = climateBoardHTML(S, inds);
  const C = Object.fromEntries(CATEGORIES.map(c => [c.key, c]));
  const cyc = inds.find(i => i.cat === "cycle"), dem = inds.find(i => i.cat === "demand" && i.label.indexOf("capex") >= 0);
  const ind = inds.find(i => i.cat === "industry"), pr = inds.find(i => i.cat === "prices"), tr = inds.find(i => i.cat === "trade"), gr = inds.find(i => i.cat === "growth");
  const vline = (i, txt) => i && i.m ? txt(i) : "";

  main.innerHTML = `
    <div class="view-head"><h1>${STATE.region} — macro &amp; semiconductor market environment</h1>
      <div class="regime">${regimeRead(S, inds)}</div></div>

    <div class="layer-tag">① Climate board <span class="dim">latest reading for every tracked indicator, by category · colour = direction · bar = percentile vs own history</span></div>
    ${board.html}

    <div class="layer-tag">② Category detail <span class="dim">level + change + comparison · the multi-layer view</span></div>

    ${catHead(C.cycle, vline(cyc, i => `Billings <b class="${i.m.dir >= 0 ? "up" : "down"}">${pct(i.m.dir)} YoY</b>, ${i.fmt(i.m.latest)}/mo · ${i.m.pctile}th percentile of ${i.m.yearsHist}y.`))}
    <div class="grid">
      ${panel(C.cycle, "ch_bill", `${STATE.region} billings — level (line) + YoY% (bars) · WSTS 3MMA · drag to zoom`)}
      ${panel(C.cycle, "ch_cmp", `By region · ${STATE.region} bold · US$B/mo (3MMA)`)}
    </div>

    ${catHead(C.demand, vline(dem, i => `AI/datacenter capex ${i.v.word.toLowerCase()} — ${i.fmt(i.m.latest)}/Q, <b class="${i.m.dir >= 0 ? "up" : "down"}">${pct(i.m.dir)} YoY</b>.`))}
    <div class="grid">
      ${panel(C.demand, "ch_capex", "Hyperscaler capex — level + YoY% · MSFT/GOOGL/AMZN/META · the dominant semi end-market")}
      ${panel(C.demand, "ch_auto", `Auto production by region · ${STATE.region} bold · M units/yr (OICA, to 2022)`)}
    </div>

    ${catHead(C.industry, vline(ind, i => `${i.label} ${i.v.word.toLowerCase()} at ${i.mode === "rate" ? sign1(i.m.latest) + "%" : pct(i.m.dir) + " YoY"}.`))}
    <div class="grid">
      ${panel(C.industry, "ch_ind", "Industrial production YoY — key chip-making economies · zero = flat")}
      ${panel(C.industry, "ch_indpro", "US industrial production — level + YoY%")}
    </div>

    ${catHead(C.prices, vline(pr, i => `${i.label} ${i.v.word.toLowerCase()} — ${i.mode === "rate" ? sign1(i.m.latest) + "% YoY" : i.fmt(i.m.latest) + ", " + pct(i.m.dir) + " YoY"}.`))}
    <div class="grid">
      ${panel(C.prices, "ch_ppi", "US PPI all-commodities — level + YoY% · input-cost pressure")}
      ${panel(C.prices, "ch_cpi", `CPI by economy · ${STATE.region} · annual YoY% · zero line`)}
    </div>

    ${catHead(C.trade, vline(tr, i => `${STATE.region} high-tech exports ${i.fmt(i.m.latest)} latest yr, <b class="${i.m.dir >= 0 ? "up" : "down"}">${pct(i.m.dir)} YoY</b>.`))}
    <div class="grid">
      ${panel(C.trade, "ch_exp", "High-tech exports — latest year ranking · US$B")}
      ${panel(C.trade, "ch_exptrend", `Export trend by economy · ${STATE.region} · US$B/yr`)}
    </div>

    ${catHead(C.growth, vline(gr, i => `${i.label} ${i.fmt(i.m.latest)}, <b class="${i.m.dir >= 0 ? "up" : "down"}">${pct(i.m.dir)} YoY</b>.`))}
    <div class="grid">
      ${panel(C.growth, "ch_gdp", `GDP — indexed · ${STATE.region} economies · World Bank (annual)`)}
      ${panel(C.growth, "ch_curve", "US Treasury yield curve — cost of money · latest snapshot")}
    </div>

    <div class="layer-tag">③ Drill-down <span class="dim">per-economy small-multiples · full US indicator scorecards · forecasts</span></div>
    <div class="sm-section"><h4>Inflation — CPI, % YoY by economy <span class="dim">World Bank (annual)</span></h4><div class="sm-grid" id="sm_cpi"></div></div>
    <div class="sm-section"><h4>High-tech exports — US$B by economy <span class="dim">World Bank (annual)</span></h4><div class="sm-grid" id="sm_exp"></div></div>
    <div class="sc-section"><h4>US indicator scorecards <span class="dim">level + MoM / YoY / 3M-3M annualized + vs-history · monthly (FRED)</span></h4><div class="sc-grid" id="scorecards"></div></div>
    ${forecastPanel()}`;

  disposeAll();
  // Layer 1 sparks
  board.sparkJobs.forEach(j => { const el = document.getElementById(j.id); if (el && j.vals.length) miniBars(el, j.vals); });
  // Layer 2 panels
  renderCycle(S, inds); renderDemand(S); renderIndustry(S); renderPrices(S); renderTrade(S); renderGrowth(S);
  // Layer 3
  renderSM(S, "sm_cpi", "FP.CPI.TOTL.ZG", false); renderSM(S, "sm_exp", "TX.VAL.TECH.CD", true); renderScorecards(S);

  const us = S.us_macro || {}, gdp = (us.GDP || [])[0], cpi = (us.CPI || [])[0], fredN = Object.keys(S.fred || {}).length;
  document.getElementById("foot").innerHTML =
    `<b>Sources:</b> WSTS (billings) · World Bank (macro) · SEC EDGAR (hyperscaler capex) · OICA + ECB (auto) · FMP (US macro${gdp ? `: GDP ${fmtUSD(gdp.value * (gdp.value < 1e6 ? 1e9 : 1))}` : ""}${cpi ? `, CPI ${(+cpi.value).toFixed(1)}` : ""}). ` +
    `<span class="pill warn">gap</span> Taiwan absent from World Bank → FRED/DGBAS (FRED ${fredN ? "loaded" : "runs on your network"}). ` +
    `<span class="pill warn">free, no API</span> PC/smartphone shipments &amp; manufacturing PMI = press-release only · PPI/IndProd/US-auto via FRED on your network.`;
}

window.addEventListener("resize", () => charts.forEach(c => { try { c.resize(); } catch (e) {} }));
(async () => {
  if (window.MMI) DATA = window.MMI;
  else { try { DATA = await (await fetch("macro-data.json", { cache: "no-store" })).json(); } catch (e) { DATA = null; } }
  wireTabs(); render();
})();
