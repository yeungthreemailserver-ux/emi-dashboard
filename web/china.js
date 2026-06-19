"use strict";
let DATA = null, MAP = null, KPICHART = null, GTERMS = [];
const STATE = { city: "Ningbo", layer: "gdp", markers: true, lang: "en" };
const LVLW = { 1: "Present", 2: "Strong", 3: "Leading" };
const LVLW_ZH = { 1: "具备", 2: "较强", 3: "领先" };
const TAXFILL = ["", "#E1F5EE", "#5DCAA5", "#0F6E56"];
const TAXFG = ["", "#0F6E56", "#04342C", "#fff"];
const READ_ZH = { cooling: "放缓", accelerating: "加速", flat: "持平", positive: "正增长", negative: "负增长",
  expansion: "扩张", contraction: "收缩", healthy: "健康", "deflation risk": "通缩风险", "too hot": "过热",
  contained: "受控", elevated: "偏高", rising: "上升", easing: "回落" };

// i18n chrome strings
const TT = {
  sub_more: ["More macro indicators", "更多宏观指标"],
  sub_more2: ["hover any term for a definition · NBS / Customs / PBoC headline values", "悬停术语查看定义 · 国家统计局/海关/央行 数据"],
  sub_ind: ["Industry position", "产业地位"],
  sub_ind2: ["China's share of key electronics / clean-energy supply chains", "中国在关键电子/清洁能源供应链中的占比"],
  sub_map: ["Map — economy & industry by province / city", "地图 — 各省/城市的经济与产业"],
  sub_map2: ["colour = macro layer · dots = industry clusters · click a city to zoom + open its dossier", "颜色=宏观层 · 圆点=产业集群 · 点击城市放大并打开档案"],
  colourby: ["Colour map by", "地图着色"],
  clusters: ["Industry clusters", "产业集群"],
  reset: ["Reset view", "重置视图"],
  tap: ["tap to expand", "点击展开"],
  sig: ["Signature strengths", "核心强项"],
  subd: ["Sub-district clusters", "次级区域集群"],
  vc: ["Value-chain role", "价值链定位"],
  dist: ["For an electronics distributor", "对电子分销商而言"],
  buy: ["Source from here", "可在此采购"],
  sell: ["Sell into here", "可向此销售"],
  mfg: ["Manufacturing-type strength", "制造类型强度"],
  hint: ["Click a city marker to open its dossier.", "点击城市标记以打开档案。"],
  src: ["source", "来源"],
};
const Z = () => STATE.lang === "zh";
const tt = (k) => (TT[k] ? TT[k][Z() ? 1 : 0] : k);
const lvlw = (n) => (Z() ? LVLW_ZH[n] : LVLW[n]);

const byName = (n) => (DATA.cities || []).find((c) => c.name === n);
const domColor = (d) => (DATA.domains[d] ? DATA.domains[d][1] : "#94a3b8");
const domName = (d) => (DATA.domains[d] ? (Z() ? DATA.domains[d][2] : DATA.domains[d][0]) : d);
const layerLabel = (l) => (Z() ? (l.label_zh || l.label) : l.label);
const curLayer = () => DATA.layers.find((l) => l.key === STATE.layer) || DATA.layers[0];
const gloDef = (term) => (Z() ? (DATA.glossary_zh[term] || DATA.glossary[term]) : DATA.glossary[term]);
const cityName = (c) => (Z() ? (c.name_zh || c.name) : c.name);
const cityTagline = (c) => Z() ? ((c.zh && c.zh.tagline) ? c.zh.tagline : (c.tagline_zh || c.tagline)) : c.tagline;
const mk = (it) => (Z() ? (it.k_zh || it.k) : it.k);          // macro/industry label
const mnote = (it) => (Z() ? (it.note_zh || it.note) : it.note);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[m]));
const escAttr = (s) => esc(s).replace(/"/g, "&quot;");
const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const MONTHS = { "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec" };
const aslabel = (p) => (p && p.indexOf("-") > 0) ? `${MONTHS[p.split("-")[1]] || p.split("-")[1]} ${p.split("-")[0]}` : p;
function asof(it) {
  if (!it.as_of) return `<span class="asof">${esc(it.source || "")}</span>`;
  const a = it.as_of === "manual" ? (Z() ? "人工录入" : "manual") : aslabel(it.as_of);
  return `<span class="asof${it.manual ? " man" : ""}">${Z() ? "截至 " : "as of "}${esc(a)} · ${esc(it.source || "")}</span>`;
}

// professional tooltips: data-tip instead of native title
function glossWrap(text, term) {
  const def = term && gloDef(term);
  return def ? `<span class="gloss" data-tip="${escAttr(def)}">${esc(text)}</span>` : esc(text);
}
function glossify(text) {
  const raw = String(text == null ? "" : text);
  const hits = [];
  for (const term of GTERMS) {
    const m = new RegExp("\\b" + escRe(term) + "\\b", "i").exec(raw);
    if (m) hits.push({ i: m.index, j: m.index + m[0].length, term, matched: m[0] });
  }
  hits.sort((a, b) => a.i - b.i || (b.j - b.i) - (a.j - a.i));
  let out = "", pos = 0;
  for (const h of hits) {
    if (h.i < pos) continue;
    out += esc(raw.slice(pos, h.i)) + `<span class="gloss" data-tip="${escAttr(gloDef(h.term))}">${esc(h.matched)}</span>`;
    pos = h.j;
  }
  return out + esc(raw.slice(pos));
}

// ---- digest: compute the meaningful signal (YoY/value), reference, colour, verdict ----
function viewSeries(it) {
  const v = it.view || { metric: "value", ref: 0, good: "high" };
  const raw = it.series || [];
  let s2;
  if (v.metric === "yoy") {
    s2 = [];
    for (let i = 1; i < raw.length; i++) { const p = raw[i - 1][1], c = raw[i][1]; if (p) s2.push([raw[i][0], +((c - p) / Math.abs(p) * 100).toFixed(1)]); }
  } else { s2 = raw.map((r) => [r[0], r[1]]); }
  const latest = s2.length ? s2[s2.length - 1][1] : null;
  const prior = s2.length > 1 ? s2[s2.length - 2][1] : null;
  const ref = v.ref != null ? v.ref : 0;
  const trend = (latest != null && prior != null) ? (latest > prior ? "accelerating" : latest < prior ? "cooling" : "flat") : "flat";
  const unit = v.ref === 50 ? "pts" : (it.key === "tbal" ? "$B" : "%");
  return { s2, latest, prior, ref, band: v.band, good: v.good, metric: v.metric, reflbl: v.reflbl, trend, unit };
}
function digest(vw) {
  if (vw.latest == null) return { color: "var(--muted)", read: "" };
  const x = vw.latest, b = vw.band || [1, 3];
  let read, color;
  if (vw.good === "band") { if (x < b[0]) { read = "deflation risk"; color = "var(--amber)"; } else if (x > b[1]) { read = "too hot"; color = "var(--red)"; } else { read = "healthy"; color = "var(--green)"; } }
  else if (vw.good === "low") { read = x <= vw.ref ? "contained" : "elevated"; color = x <= vw.ref ? "var(--green)" : "var(--red)"; }
  else { color = x >= vw.ref ? "var(--green)" : "var(--red)"; read = (vw.ref === 50) ? (x >= 50 ? "expansion" : "contraction") : (x < vw.ref ? "negative" : (vw.prior != null ? vw.trend : "positive")); }
  return { color, read: Z() ? (READ_ZH[read] || read) : read };
}
function digestStr(it, vw) {
  const dg = digest(vw);
  if (vw.latest == null) return { color: dg.color, txt: "" };
  const dunit = vw.ref === 50 ? "" : "%";
  const valStr = vw.metric === "yoy" ? ((vw.latest >= 0 ? "+" : "") + vw.latest + "% YoY") : (vw.latest + dunit);
  return { color: dg.color, txt: valStr + (dg.read ? " · " + dg.read : "") };
}
function sparkBars(vw, w, h) {
  const s = vw.s2; if (!s || s.length < 2) return "";  // need a real trend, not a single block
  w = w || 144; h = h || 34;
  const vals = s.map((p) => p[1]).concat([vw.ref]);
  const mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1;
  const y = (v) => h - 3 - ((v - mn) / rng) * (h - 6);
  const refY = +y(vw.ref).toFixed(1);
  const bw = (w - 2) / s.length;
  const good = (v) => vw.good === "low" ? v <= vw.ref : vw.good === "band" ? (v >= (vw.band[0]) && v <= (vw.band[1])) : v >= vw.ref;
  const fmt = (v) => vw.unit === "$B" ? ("$" + v + "B") : vw.unit === "pts" ? ("" + v) : ((v >= 0 ? "+" : "") + v + "%");
  let bars = "", hits = "";
  s.forEach((p, i) => {
    const x = (1 + i * bw).toFixed(1), vy = y(p[1]);
    const top = Math.min(vy, refY).toFixed(1), ht = Math.max(1.5, Math.abs(vy - refY)).toFixed(1);
    const c = good(p[1]) ? "#16a34a" : (vw.good === "band" && p[1] < vw.band[0] ? "#d97706" : "#dc2626");
    bars += `<rect x="${x}" y="${top}" width="${(bw - 1.3).toFixed(1)}" height="${ht}" rx="1" fill="${c}" opacity="0.82"/>`;
    hits += `<rect x="${x}" y="0" width="${bw.toFixed(1)}" height="${h}" fill="transparent" data-tip="${esc(aslabel(p[0]) + " · " + fmt(p[1]))}"/>`;
  });
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" class="spark" preserveAspectRatio="none">${bars}<line x1="0" y1="${refY}" x2="${w}" y2="${refY}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="3 2"/>${hits}</svg>`;
}

// ---- render ----
function render() {
  const m = DATA.macro;
  const kpis = m.headline.map((k, i) => {
    const vw = viewSeries(k), dg = digestStr(k, vw);
    return `<div class="kpi" data-kpi="${i}">
      <div class="lbl">${glossWrap(mk(k), k.glo)}</div>
      <div class="val">${esc(k.v)}</div>
      <div class="digest" style="color:${dg.color}">${esc(dg.txt)}</div>
      <div class="spk">${sparkBars(vw)}</div>
      <div class="src">${asof(k)} · <span class="exp">${tt("tap")} ↗</span></div></div>`;
  }).join("");
  const more = m.more.map((it, i) => {
    const vw = viewSeries(it), dg = digest(vw), head = `<div class="morec${it.manual ? " man" : ""}" data-more="${i}">`;
    const spk = (it.series && it.series.length > 1) ? `<div class="msp">${sparkBars(vw, 120, 22)}</div>` : "";
    const col = vw.latest != null ? dg.color : "var(--ink)";
    return `${head}<div class="mk">${glossWrap(mk(it), it.glo)}</div><div class="mv" style="color:${col}">${esc(it.v)}</div>${spk}<div class="md">${asof(it)}</div></div>`;
  }).join("");
  const ind = m.industry.map((i) => `<div class="ind"><b>${esc(i.v)}</b><span class="il">${glossWrap(mk(i), i.glo)} · ${esc(mnote(i))}</span></div>`).join("");
  const layerBtns = DATA.layers.map((l) => `<button class="mapbtn${l.key === STATE.layer ? " active" : ""}" data-layer="${l.key}">${esc(layerLabel(l))}</button>`).join("");
  const legend = Object.keys(DATA.domains).map((d) => `<span><i style="color:${DATA.domains[d][1]}">●</i> ${esc(domName(d))}</span>`).join("");
  document.getElementById("main").innerHTML = `
    <div class="cty-head"><h1>${Z() ? "中国" : "China"} <span style="font-size:12px;color:var(--muted);font-weight:400">${Z() ? "市场 · 产业 · 城市" : "market · industry · cities"}</span></h1>
      <div class="sub">${esc(Z() ? (m.tagline_zh || m.tagline) : m.tagline)}</div></div>
    <div class="kpis">${kpis}</div>
    <div class="sech">${tt("sub_more")} <span class="dim">${tt("sub_more2")}</span></div>
    <div class="more-grid">${more}</div>
    <div class="sech">${tt("sub_ind")} <span class="dim">${tt("sub_ind2")}</span></div>
    <div class="indstrip">${ind}</div>
    <div class="sech">${tt("sub_map")} <span class="dim">${tt("sub_map2")}</span></div>
    <div class="maptools">
      <span class="mt-label">${tt("colourby")}</span>${layerBtns}
      <span class="mt-sep"></span>
      <button class="mapbtn ovl active" id="ovlbtn"><i style="color:#7f77dd">●</i> ${tt("clusters")}</button>
      <button class="mapbtn" id="resetbtn">⤢ ${tt("reset")}</button>
    </div>
    <div class="legend">${legend}</div>
    <div class="citywrap">
      <div class="citymap" id="citymap"></div>
      <div class="dossier" id="dossier"></div>
    </div>`;
  document.querySelectorAll(".kpi").forEach((el) => el.addEventListener("click", () => openKpiModal(m.headline[+el.dataset.kpi])));
  document.querySelectorAll(".morec[data-more]").forEach((el) => el.addEventListener("click", () => openKpiModal(m.more[+el.dataset.more])));
  document.querySelectorAll(".mapbtn[data-layer]").forEach((b) => b.addEventListener("click", () => setLayer(b.dataset.layer)));
  document.getElementById("ovlbtn").addEventListener("click", toggleMarkers);
  document.getElementById("resetbtn").addEventListener("click", resetView);
  initMap();
  renderDossier(byName(STATE.city) || DATA.cities[0]);
}

// ---- map ----
function provData(L) { return Object.entries(DATA.provinces).map(([name, o]) => ({ name, value: o[L.field] })); }
function markerData() {
  return DATA.cities.map((c) => ({
    name: c.name, value: [c.lon, c.lat], symbolSize: c.subdistricts ? 17 : 10,
    itemStyle: { color: domColor(c.dom), borderColor: "#fff", borderWidth: 1.4, shadowBlur: 4, shadowColor: "rgba(0,0,0,.18)" },
    tip: `<b>${esc(cityName(c))}</b> · ${esc(domName(c.dom))}<br><span style="color:#64748b">${esc(cityTagline(c))}</span>`,
  }));
}
function visualMapOpt() {
  const L = curLayer(), vals = provData(L).map((d) => d.value).filter((v) => v != null);
  const mn = Math.min(...vals), mx = Math.max(...vals);
  return { type: "continuous", calculable: true, seriesIndex: 0, min: mn, max: mx, left: 12, bottom: 18, itemHeight: 130,
    inRange: { color: L.colors }, text: [`${mx}${L.unit}`, `${mn}${L.unit}`], textStyle: { color: "#64748b", fontSize: 10 } };
}
const TIP_CSS = "border-radius:10px;box-shadow:0 8px 28px rgba(15,23,42,.16);padding:9px 12px;";
function initMap() {
  const el = document.getElementById("citymap");
  if (MAP) { MAP.dispose(); MAP = null; }
  echarts.registerMap("china", DATA.geo);
  MAP = echarts.init(el);
  MAP.setOption({
    tooltip: { trigger: "item", confine: true, backgroundColor: "#fff", borderColor: "rgba(148,163,184,.4)", borderWidth: 0.5,
      extraCssText: TIP_CSS, textStyle: { fontSize: 12, color: "#1e293b" },
      formatter: (p) => {
        if (p.seriesType === "scatter" && p.data) return p.data.tip;
        if (p.seriesType === "map") { const L = curLayer(); const v = p.value; return `<b>${esc(p.name)}</b><br>${esc(layerLabel(L))}: ${(v != null && !isNaN(v)) ? v + " " + L.unit : "—"}`; }
        return esc(p.name);
      } },
    visualMap: visualMapOpt(),
    geo: { map: "china", roam: true, zoom: 1.25, center: [104, 36], scaleLimit: { min: 1, max: 10 },
      itemStyle: { areaColor: "#f0f3f7", borderColor: "#fff", borderWidth: 0.6 },
      emphasis: { itemStyle: { areaColor: "#dbe3ee" }, label: { show: false } } },
    series: [
      { type: "map", geoIndex: 0, name: layerLabel(curLayer()), data: provData(curLayer()) },
      { type: "scatter", coordinateSystem: "geo", geoIndex: 0, zlevel: 5, data: STATE.markers ? markerData() : [],
        emphasis: { label: { show: true, formatter: "{b}", position: "right", fontSize: 11, color: "#0f172a", fontWeight: 700 }, scale: 1.3 }, label: { show: false } },
    ],
  });
  MAP.on("click", (p) => {
    if (p.seriesType === "scatter" && p.data && p.data.name) {
      STATE.city = p.data.name; const c = byName(p.data.name);
      MAP.setOption({ geo: { zoom: 4.5, center: [c.lon, c.lat] } });
      renderDossier(c); document.getElementById("dossier").scrollTop = 0;
    }
  });
  window.addEventListener("resize", () => MAP && MAP.resize());
}
function setLayer(key) {
  STATE.layer = key;
  document.querySelectorAll(".mapbtn[data-layer]").forEach((b) => b.classList.toggle("active", b.dataset.layer === key));
  MAP.setOption({ visualMap: visualMapOpt(), series: [{ name: layerLabel(curLayer()), data: provData(curLayer()) }] });
}
function toggleMarkers() { STATE.markers = !STATE.markers; document.getElementById("ovlbtn").classList.toggle("active", STATE.markers); MAP.setOption({ series: [{}, { data: STATE.markers ? markerData() : [] }] }); }
function resetView() { MAP.setOption({ geo: { zoom: 1.25, center: [104, 36] } }); }

// ---- KPI modal ----
function closeKpiModal() { if (KPICHART) { KPICHART.dispose(); KPICHART = null; } const e = document.getElementById("kpimodal"); if (e) e.remove(); }
function openKpiModal(it) {
  closeKpiModal();
  const vw = viewSeries(it), dg = digestStr(it, vw), s = vw.s2 || [];
  const metricLbl = vw.metric === "yoy" ? "YoY %" : (vw.ref === 50 ? "index" : "%");
  const bg = document.createElement("div"); bg.className = "modal-bg"; bg.id = "kpimodal";
  bg.innerHTML = `<div class="modal"><div class="modal-h"><span class="modal-title">${glossWrap(mk(it), it.glo)}</span><button class="modal-close" aria-label="close">✕</button></div>
    <div class="modal-sub"><b>${esc(it.v)}</b>${dg.txt ? ` · <span style="color:${dg.color};font-weight:600">${esc(dg.txt)}</span>` : ""} · ${esc(Z() ? "截至 " : "as of ")}${esc(it.as_of === "manual" ? "manual" : aslabel(it.as_of))} · ${esc(it.source || "")} · <span class="freqtag">${esc(it.freq || "")}</span></div>
    <div class="modal-chart" id="kpichart"></div>
    ${(it.detail || it.detail_zh) ? `<div class="modal-detail">${glossify(Z() ? (it.detail_zh || it.detail) : it.detail)}</div>` : ""}</div>`;
  bg.addEventListener("click", (e) => { if (e.target === bg) closeKpiModal(); });
  bg.querySelector(".modal-close").addEventListener("click", closeKpiModal);
  document.body.appendChild(bg);
  if (s.length) {
    KPICHART = echarts.init(document.getElementById("kpichart"));
    KPICHART.setOption({
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      tooltip: { trigger: "axis", backgroundColor: "#fff", borderColor: "rgba(148,163,184,.4)", borderWidth: 0.5, extraCssText: TIP_CSS, textStyle: { fontSize: 12, color: "#1e293b" } },
      xAxis: { type: "category", data: s.map((d) => d[0]), axisLabel: { fontSize: 11, color: "#64748b" }, axisTick: { show: false } },
      yAxis: { type: "value", scale: true, name: metricLbl, nameTextStyle: { color: "#94a3b8", fontSize: 10 }, axisLabel: { fontSize: 10, color: "#64748b" }, splitLine: { lineStyle: { color: "#eef2f6" } } },
      series: [{ type: "bar", data: s.map((d) => ({ value: d[1], itemStyle: { color: (vw.good === "low" ? d[1] <= vw.ref : vw.good === "band" ? (d[1] >= vw.band[0] && d[1] <= vw.band[1]) : d[1] >= vw.ref) ? "#16a34a" : (vw.good === "band" && d[1] < vw.band[0] ? "#d97706" : "#dc2626"), borderRadius: 2 } })),
        barWidth: "56%",
        markLine: { silent: true, symbol: "none", data: [{ yAxis: vw.ref }], lineStyle: { color: "#94a3b8", type: "dashed" }, label: { formatter: vw.reflbl || String(vw.ref), fontSize: 10, color: "#64748b", position: "insideEndTop" } } }],
    });
  }
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeKpiModal(); });

// ---- dossier ----
function sanctionOf(a) { const al = a.toLowerCase(); return (DATA.sanctions || []).find((s) => s.match && al.indexOf(s.match.toLowerCase()) >= 0) || null; }
// Simplified-Chinese display name for an anchor company, only when the page is in Chinese mode.
function anchorZh(a) { return (Z() && DATA.company_zh && DATA.company_zh[a]) ? DATA.company_zh[a] : null; }
function clusterHTML(cl, z) {
  const anch = (cl.anchors || []).map((a) => {
    const zh = anchorZh(a);               // Chinese label in zh mode (English original kept in tooltip)
    const label = zh || a;
    const s = sanctionOf(a);
    if (s) return `<span class="chip sanc" data-tip="${escAttr("⚠ " + s.name + " · US " + s.list + " (" + s.date + ") · " + s.note)}">⚠ ${esc(label)}</span>`;
    if (zh) return `<span class="chip" data-tip="${escAttr(a)}">${esc(zh)}</span>`;
    return `<span class="chip">${glossify(a)}</span>`;
  }).join("");
  return `<div class="cluster l${cl.level}"><div class="cl-top"><span class="cl-seg">${glossify(z && z.seg ? z.seg : cl.seg)}</span><span class="cl-lvl l${cl.level}">${lvlw(cl.level)}</span></div>
    <div class="cl-what">${glossify(z && z.what ? z.what : cl.what)}</div>${anch ? `<div class="cl-anch">${anch}</div>` : ""}</div>`;
}
function renderDossier(c) {
  const el = document.getElementById("dossier");
  if (!c) { el.innerHTML = `<div class="dos-hint">${tt("hint")}</div>`; return; }
  const z = (Z() && c.zh) ? c.zh : null;
  const pick = (zv, ev) => glossify((z && zv != null) ? zv : ev);
  let h = `<div class="dos-h"><span class="dos-name">${esc(cityName(c))}</span><span class="dos-dom" style="background:${domColor(c.dom)}">${esc(domName(c.dom))}</span></div>`;
  h += `<div class="dos-tag">${glossify(z ? z.tagline : c.tagline)}</div>`;
  if (c.stats && c.stats.length) h += `<div class="dos-stats">${c.stats.map((s, i) => { const sz = (z && z.stats && z.stats[i]) ? z.stats[i] : s; return `<div class="dos-stat"><div class="k">${esc(sz.k)}</div><div class="v">${esc(sz.v)}</div></div>`; }).join("")}</div>`;
  if (c.clusters && c.clusters.length) h += `<div class="dos-sec"><h5>${tt("sig")}</h5>${c.clusters.map((cl, i) => clusterHTML(cl, z && z.clusters ? z.clusters[i] : null)).join("")}</div>`;
  if (c.subdistricts && c.subdistricts.length) h += `<div class="dos-sec"><h5>${tt("subd")}</h5>${c.subdistricts.map((s, i) => `<div class="sub-row"><b>${esc(s.name)}</b><span>${pick(z && z.subdistricts && z.subdistricts[i] ? z.subdistricts[i].focus : null, s.focus)}</span></div>`).join("")}</div>`;
  if (c.valuechain) h += `<div class="dos-sec"><h5>${tt("vc")}</h5><div class="vc">${pick(z ? z.valuechain : null, c.valuechain)}</div></div>`;
  if (c.sourcing) h += `<div class="dos-sec"><h5>${tt("dist")}</h5><div class="src2">
      <div><div class="lbl">${tt("buy")}</div><ul>${(c.sourcing.buy || []).map((x, i) => `<li>${pick(z && z.sourcing && z.sourcing.buy ? z.sourcing.buy[i] : null, x)}</li>`).join("")}</ul></div>
      <div><div class="lbl">${tt("sell")}</div><ul>${(c.sourcing.sell || []).map((x, i) => `<li>${pick(z && z.sourcing && z.sourcing.sell ? z.sourcing.sell[i] : null, x)}</li>`).join("")}</ul></div></div></div>`;
  if (c.tags) {
    const cells = DATA.taxonomy.map((t) => { const v = c.tags[t] || 0; const bg = v ? `background:${TAXFILL[v]}` : "background:#fafbfd;border:1px solid var(--line)";
      return `<div class="taxc" style="${bg};color:${TAXFG[v] || "#cbd5e1"}" data-tip="${esc(t)}: ${v ? lvlw(v) : "—"}"><div class="tl">${esc(t.slice(0, 8))}</div><div class="tv">${v ? "●".repeat(v) : "·"}</div></div>`;
    }).join("");
    h += `<div class="dos-sec"><h5>${tt("mfg")}</h5><div class="taxg">${cells}</div></div>`;
  }
  if (c.note) h += `<div class="dos-note">${esc(z && z.note ? z.note : c.note)}</div>`;
  el.innerHTML = h;
}

// ---- custom tooltip (professional, replaces native title) ----
function initTooltip() {
  let tip = document.getElementById("ctip");
  if (!tip) { tip = document.createElement("div"); tip.id = "ctip"; document.body.appendChild(tip); }
  document.addEventListener("mouseover", (e) => { const t = e.target.closest("[data-tip]"); if (t) { tip.textContent = t.getAttribute("data-tip"); tip.style.display = "block"; } });
  document.addEventListener("mouseout", (e) => { const t = e.target.closest("[data-tip]"); if (t) tip.style.display = "none"; });
  document.addEventListener("mousemove", (e) => { if (tip.style.display === "block") { const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 14); tip.style.left = x + "px"; tip.style.top = (e.clientY + 18) + "px"; } });
}
function toggleLang() { STATE.lang = STATE.lang === "en" ? "zh" : "en"; const b = document.getElementById("langtoggle"); if (b) b.textContent = STATE.lang === "en" ? "简体中文" : "English"; render(); }

(function () {
  if (window.CHINA) DATA = window.CHINA;
  if (!DATA) { document.getElementById("main").innerHTML = `<div class="loading">No data — run scripts/build_china_bundle.py</div>`; return; }
  GTERMS = Object.keys(DATA.glossary).sort((a, b) => b.length - a.length);
  initTooltip();
  const lb = document.getElementById("langtoggle"); if (lb) lb.addEventListener("click", toggleLang);
  render();
})();
