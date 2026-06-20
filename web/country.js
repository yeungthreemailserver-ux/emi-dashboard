// Generic single-country renderer for APAC country pages (Singapore, Malaysia, ...).
// Reads window.COUNTRY, reuses china.css. English-only. Renders: macro tiles + supply-chain
// role map + (key-city dossiers with selector) OR (one country-level clusters dossier).
const DATA = window.COUNTRY;
const STATE = { city: (DATA.cities && DATA.cities[0]) ? DATA.cities[0].name : null };
const ORIGIN = { US: "USA", DE: "Germany", JP: "Japan", TW: "Taiwan", KR: "South Korea", NL: "Netherlands", FR: "France", EU: "Europe", CH: "Switzerland", AT: "Austria", CN: "China", AU: "Australia", IN: "India", SG: "Singapore", MY: "Malaysia" };
const LVL = { 3: "leading", 2: "strong", 1: "present" };
// manufacturing-type heatmap shading (same scale as the China page / atlas)
const TAXFILL = ["", "#E1F5EE", "#5DCAA5", "#0F6E56"], TAXFG = ["", "#0F6E56", "#04342C", "#fff"];
const domColor = (d) => (DATA.domains && DATA.domains[d]) ? DATA.domains[d][1] : "#1d4ed8";
const domName = (d) => (DATA.domains && DATA.domains[d]) ? DATA.domains[d][0] : d;

const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const escAttr = (s) => esc(s).replace(/"/g, "&quot;");
function gloDef(t) { return DATA.glossary && DATA.glossary[t]; }
function glossWrap(text, term) { const d = term && gloDef(term); return d ? `<span class="gloss" data-tip="${escAttr(d)}">${esc(text)}</span>` : esc(text); }
// auto-scan free text for glossary terms and wrap the first non-overlapping occurrences
function glossify(raw) {
  raw = String(raw == null ? "" : raw);
  const lower = raw.toLowerCase(), hits = [];
  for (const t of Object.keys(DATA.glossary || {})) { let from = 0, i; const tl = t.toLowerCase(); while ((i = lower.indexOf(tl, from)) >= 0) { hits.push({ i, j: i + t.length, term: t, m: raw.slice(i, i + t.length) }); from = i + t.length; } }
  hits.sort((a, b) => a.i - b.i || (b.j - b.i) - (a.j - a.i));
  let out = "", pos = 0;
  for (const h of hits) { if (h.i < pos) continue; out += esc(raw.slice(pos, h.i)) + `<span class="gloss" data-tip="${escAttr(gloDef(h.term))}">${esc(h.m)}</span>`; pos = h.j; }
  return out + esc(raw.slice(pos));
}

// ---- digest / sparkline (ported from the China page) ----
function viewSeries(it) {
  const v = it.view || { metric: "value", ref: 0, good: "high" };
  const raw = it.series || [];
  let s2;
  if (v.metric === "yoy") { s2 = []; for (let i = 1; i < raw.length; i++) { const p = raw[i - 1][1], c = raw[i][1]; if (p) s2.push([raw[i][0], +((c - p) / Math.abs(p) * 100).toFixed(1)]); } }
  else { s2 = raw.map((r) => [r[0], r[1]]); }
  const latest = s2.length ? s2[s2.length - 1][1] : null;
  const prior = s2.length > 1 ? s2[s2.length - 2][1] : null;
  const ref = v.ref != null ? v.ref : 0;
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
  const dg = digest(vw);
  if (vw.latest == null || vw.good === "none") return { color: dg.color, txt: "" };
  const dunit = vw.ref === 50 ? "" : "%";
  const valStr = vw.metric === "yoy" ? ((vw.latest >= 0 ? "+" : "") + vw.latest + "% YoY") : (vw.latest + dunit);
  return { color: dg.color, txt: valStr + (dg.read ? " · " + dg.read : "") };
}
function sparkBars(vw, w, h, neutral) {
  const s = vw.s2; if (!s || s.length < 2) return "";
  w = w || 144; h = h || 34;
  const vals = s.map((p) => p[1]).concat([vw.ref]);
  const mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1;
  const y = (v) => h - 3 - ((v - mn) / rng) * (h - 6);
  const refY = +y(vw.ref).toFixed(1), bw = (w - 2) / s.length;
  const good = (v) => vw.good === "low" ? v <= vw.ref : vw.good === "band" ? (v >= vw.band[0] && v <= vw.band[1]) : v >= vw.ref;
  let bars = "", hits = "";
  s.forEach((p, i) => {
    const x = (1 + i * bw).toFixed(1), vy = y(p[1]);
    const top = Math.min(vy, refY).toFixed(1), ht = Math.max(1.5, Math.abs(vy - refY)).toFixed(1);
    const c = neutral ? "#94a3b8" : (good(p[1]) ? "#16a34a" : (vw.good === "band" && p[1] < vw.band[0] ? "#d97706" : "#dc2626"));
    bars += `<rect x="${x}" y="${top}" width="${(bw - 1.3).toFixed(1)}" height="${ht}" rx="1" fill="${c}" opacity="0.82"/>`;
    hits += `<rect x="${x}" y="0" width="${bw.toFixed(1)}" height="${h}" fill="transparent" data-tip="${escAttr(p[0] + " · " + p[1])}"/>`;
  });
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" class="spark" preserveAspectRatio="none">${bars}<line x1="0" y1="${refY}" x2="${w}" y2="${refY}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="3 2"/>${hits}</svg>`;
}
const valHTML = (it) => esc(it.v) + (it.basis ? `<span class="basis">${esc(it.basis)}</span>` : "");
const tileFoot = (it) => `<span class="asof">as of ${esc(it.as_of)} · ${esc(it.source || "")}</span>`;
function macroTile(it) {
  const vw = viewSeries(it), neutral = it.view && it.view.good === "none";
  let verdict = "";
  if (neutral) verdict = it.note ? `<div class="digest" style="color:var(--muted)">${esc(it.note)}</div>` : "";
  else { const dg = digestStr(it, vw); verdict = dg.txt ? `<div class="digest" style="color:${dg.color}">${esc(dg.txt)}</div>` : ""; }
  const spk = (vw.s2 && vw.s2.length > 1) ? `<div class="spk">${sparkBars(vw, 144, 34, neutral)}</div>` : "";
  return `<div class="kpi nostatic"><div class="lbl">${glossWrap(it.k, it.glo)}</div><div class="val">${valHTML(it)}</div>${verdict}${spk}<div class="src">${tileFoot(it)}</div></div>`;
}

// ---- supply-chain role map (global share; no 50% reference line) ----
function roleHTML() {
  const L = DATA.role || [];
  const row = (n) => {
    const pct = Math.max(0, Math.min(100, n.share)), col = n.type === "hold" ? "var(--blue)" : "var(--amber)";
    return `<div class="lev-row"><div class="lev-top"><span class="lev-term">${glossWrap(n.node, n.glo)}</span><span class="lev-scope">${esc(n.scope)}</span><span class="lev-val" style="color:${col}">${esc(n.disp)}</span></div>
      <div class="lev-bar"><div class="lev-fill" style="width:${pct}%;background:${col}"></div></div>
      <div class="lev-src">${esc(n.source)}${n.year ? " · " + esc(n.year) : ""}</div></div>`;
  };
  const grp = (type, title, cap) => { const r = L.filter((n) => n.type === type).map(row).join(""); return r ? `<div class="lev-grp"><div class="lev-h">${title} <span class="lev-cap">${cap}</span></div><div class="lev-rows">${r}</div></div>` : ""; };
  return grp("hold", "Globally significant", "· the region's strengths") + grp("gap", "Moving upstream", "· still limited / mid-stream");
}

// ---- dossiers (city or country-level clusters) ----
function anchorChip(a) {
  if (a && typeof a === "object" && a.o) { const hq = ORIGIN[a.o] || a.o; return `<span class="chip foreign" data-tip="${escAttr("HQ: " + hq)}">${esc(a.n)}<sup class="orig">${esc(a.o)}</sup></span>`; }
  const name = (a && typeof a === "object") ? a.n : a;
  return `<span class="chip" data-tip="${escAttr("Local · " + DATA.name + "-HQ")}">${esc(name)}</span>`;
}
function clusterHTML(cl) {
  const anch = (cl.anchors || []).map(anchorChip).join("");
  return `<div class="cluster l${cl.level}"><div class="cl-top"><span class="cl-seg">${glossify(cl.seg)}</span><span class="cl-lvl l${cl.level}">${LVL[cl.level] || ""}</span></div>
    <div class="cl-what">${glossify(cl.what)}</div>${anch ? `<div class="cl-anch">${anch}</div>` : ""}</div>`;
}
function dossierHTML(d) {
  let h = "";
  if (d.tagline) h += `<div class="dos-tag">${glossify(d.tagline)}</div>`;
  if (d.stats && d.stats.length) h += `<div class="dos-stats">${d.stats.map((s) => `<div class="dos-stat"><div class="k">${esc(s.k)}</div><div class="v">${esc(s.v)}</div></div>`).join("")}</div>`;
  if (d.clusters && d.clusters.length) h += `<div class="dos-sec"><h5>Signature strengths</h5>
    <div class="dos-legend"><span><i class="dot cn"></i>Local (${esc(DATA.name)})</span><span><i class="dot for"></i>Foreign HQ</span><span class="leg-hint">· hover a company for HQ</span></div>
    ${d.clusters.map(clusterHTML).join("")}</div>`;
  if (d.subdistricts && d.subdistricts.length) h += `<div class="dos-sec"><h5>Sub-district clusters</h5>${d.subdistricts.map((s) => `<div class="sub-row"><b>${esc(s.name)}</b><span>${glossify(s.focus)}</span></div>`).join("")}</div>`;
  if (d.valuechain) h += `<div class="dos-sec"><h5>Value-chain role</h5><div class="vc">${glossify(d.valuechain)}</div></div>`;
  if (d.sourcing) h += `<div class="dos-sec"><h5>For a component distributor</h5><div class="src2">
    <div><div class="lbl">Source here</div><ul>${(d.sourcing.buy || []).map((x) => `<li>${glossify(x)}</li>`).join("")}</ul></div>
    <div><div class="lbl">Sell into here</div><ul>${(d.sourcing.sell || []).map((x) => `<li>${glossify(x)}</li>`).join("")}</ul></div></div></div>`;
  const tax = DATA.taxonomy || [];
  if (d.tags && tax.length) {
    const cells = tax.map((t) => { const v = d.tags[t] || 0, bg = v ? `background:${TAXFILL[v]}` : "background:#fafbfd;border:1px solid var(--line)";
      return `<div class="taxc" style="${bg};color:${TAXFG[v] || "#cbd5e1"}" data-tip="${escAttr(t + ": " + (v ? LVL[v] : "—"))}"><div class="tl">${esc(t.slice(0, 8))}</div><div class="tv">${v ? "●".repeat(v) : "·"}</div></div>`; }).join("");
    h += `<div class="dos-sec"><h5>Manufacturing-type strength</h5><div class="taxg">${cells}</div></div>`;
  }
  if (d.note) h += `<div class="dos-note">${esc(d.note)}</div>`;
  return h;
}

// ---- render ----
function render() {
  const D = DATA;
  const tiles = (D.macro || []).map(macroTile).join("");
  let lower = "";
  if (D.cities && D.cities.length) {
    const sel = D.cities.map((c) => `<button class="mapbtn${c.name === STATE.city ? " active" : ""}" data-city="${escAttr(c.name)}">${esc(c.name)}</button>`).join("");
    const city = D.cities.find((c) => c.name === STATE.city) || D.cities[0];
    lower = `<div class="sech">Key cities <span class="dim">click a city for its cluster dossier</span></div>
      <div class="maptools"><span class="mt-label">City</span>${sel}</div>
      <div class="dossier citydoss"><div class="dos-h"><span class="dos-name">${esc(city.name)}</span>${city.dom ? `<span class="dos-dom" style="background:${domColor(city.dom)}">${esc(domName(city.dom))}</span>` : ""}<span class="dos-area">${esc(city.area || "")}</span></div>${dossierHTML(city)}</div>`;
  } else if (D.clusters && D.clusters.length) {
    lower = `<div class="sech">Key clusters <span class="dim">${esc(D.name)}'s chip ecosystem</span></div>
      <div class="dossier citydoss">${dossierHTML({ stats: D.stats, clusters: D.clusters, subdistricts: D.subdistricts, valuechain: D.valuechain, sourcing: D.sourcing, tags: D.tags, note: D.note })}</div>`;
  }
  document.getElementById("main").innerHTML = `
    <div class="cty-head"><h1>${esc(D.name)} <span style="font-size:12px;color:var(--muted);font-weight:400">market · industry · supply-chain role</span></h1>
      <div class="sub">${esc(D.tagline || "")}</div></div>
    <div class="sech">Macro snapshot <span class="dim">official sources · latest prints</span></div>
    <div class="kpis">${tiles}</div>
    <div class="sech">Supply-chain role <span class="dim">${esc(D.name)}'s place in the global chip supply chain · global share per node</span></div>
    <div class="lev-take">${esc(D.role_take || "")}</div>
    <div class="levmap">${roleHTML()}</div>
    ${lower}`;
  document.querySelectorAll("[data-city]").forEach((b) => b.addEventListener("click", () => { STATE.city = b.dataset.city; render(); }));
}

function initTooltips() {
  let tip = document.getElementById("ctip");
  if (!tip) { tip = document.createElement("div"); tip.id = "ctip"; document.body.appendChild(tip); }
  document.addEventListener("mouseover", (e) => { const t = e.target.closest("[data-tip]"); if (t) { tip.textContent = t.getAttribute("data-tip"); tip.style.display = "block"; } });
  document.addEventListener("mousemove", (e) => { tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; });
  document.addEventListener("mouseout", (e) => { const t = e.target.closest("[data-tip]"); if (t) tip.style.display = "none"; });
}

initTooltips();
render();
