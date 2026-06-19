// SE-Asia Hub (Singapore + Malaysia) — Phase 1: macro tiles + supply-chain role map.
// Reuses china.css styling and the China page's digest/sparkline patterns. English-only.
const DATA = window.SEASIA;
const STATE = { country: "sg" };

const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const escAttr = (s) => esc(s).replace(/"/g, "&quot;");
function gloDef(term) { return DATA.glossary && DATA.glossary[term]; }
function glossWrap(text, term) {
  const def = term && gloDef(term);
  return def ? `<span class="gloss" data-tip="${escAttr(def)}">${esc(text)}</span>` : esc(text);
}

// ---- digest: compute the meaningful signal, reference, colour, verdict (ported from china.js) ----
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
  return { s2, latest, prior, ref, band: v.band, good: v.good, metric: v.metric, trend };
}
function digest(vw) {
  if (vw.latest == null) return { color: "var(--muted)", read: "" };
  const x = vw.latest, b = vw.band || [1, 3];
  let read, color;
  if (vw.good === "none") return { color: "var(--ink)", read: "" };
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
  const refY = +y(vw.ref).toFixed(1);
  const bw = (w - 2) / s.length;
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
function valHTML(it) {
  const b = it.basis;
  return esc(it.v) + (b ? `<span class="basis">${esc(b)}</span>` : "");
}
function tileFoot(it) {
  return `<span class="asof">as of ${esc(it.as_of)} · ${esc(it.source || "")}</span>`;
}

// ---- macro tile ----
function macroTile(it) {
  const vw = viewSeries(it);
  const neutral = it.view && it.view.good === "none";
  let verdict = "";
  if (neutral) { verdict = it.note ? `<div class="digest" style="color:var(--muted)">${esc(it.note)}</div>` : ""; }
  else { const dg = digestStr(it, vw); verdict = dg.txt ? `<div class="digest" style="color:${dg.color}">${esc(dg.txt)}</div>` : ""; }
  const spk = (vw.s2 && vw.s2.length > 1) ? `<div class="spk">${sparkBars(vw, 144, 34, neutral)}</div>` : "";
  return `<div class="kpi nostatic">
    <div class="lbl">${glossWrap(it.k, it.glo)}</div>
    <div class="val">${valHTML(it)}</div>
    ${verdict}${spk}
    <div class="src">${tileFoot(it)}</div></div>`;
}

// ---- supply-chain role map (global share per node; no 50% reference line) ----
function roleHTML() {
  const L = DATA.role || [];
  const row = (n) => {
    const pct = Math.max(0, Math.min(100, n.share));
    const col = n.type === "hold" ? "var(--blue)" : "var(--amber)";
    return `<div class="lev-row">
      <div class="lev-top"><span class="lev-term">${glossWrap(n.node, n.glo)}</span><span class="lev-scope">${esc(n.scope)}</span><span class="lev-val" style="color:${col}">${esc(n.disp)}</span></div>
      <div class="lev-bar"><div class="lev-fill" style="width:${pct}%;background:${col}"></div></div>
      <div class="lev-src">${esc(n.source)}${n.year ? " · " + esc(n.year) : ""}</div></div>`;
  };
  const grp = (type, title, cap) => {
    const rows = L.filter((n) => n.type === type).map(row).join("");
    return rows ? `<div class="lev-grp"><div class="lev-h">${title} <span class="lev-cap">${cap}</span></div><div class="lev-rows">${rows}</div></div>` : "";
  };
  return grp("hold", "Globally significant", "· the back-end & equipment hub") + grp("gap", "Moving upstream", "· still limited / mid-stream");
}

// ---- render ----
function render() {
  const D = DATA;
  const cty = D.countries.find((c) => c.key === STATE.country) || {};
  const tiles = (D.macro[STATE.country] || []).map(macroTile).join("");
  const togg = D.countries.map((c) => `<button class="mapbtn${c.key === STATE.country ? " active" : ""}" data-cty="${c.key}">${esc(c.name)}</button>`).join("");
  document.getElementById("main").innerHTML = `
    <div class="cty-head"><h1>SE-Asia Hub <span style="font-size:12px;color:var(--muted);font-weight:400">Singapore + Malaysia · the “China+1” electronics hub</span></h1>
      <div class="sub">${esc(cty.tagline || "")}</div></div>
    <div class="maptools"><span class="mt-label">Country</span>${togg}</div>
    <div class="sech">Macro snapshot <span class="dim">${esc(cty.name)} · official sources, latest prints</span></div>
    <div class="kpis">${tiles}</div>
    <div class="sech">Supply-chain role <span class="dim">SE-Asia's place in the global chip supply chain · global share per node</span></div>
    <div class="lev-take">${esc(D.role_take)}</div>
    <div class="levmap">${roleHTML()}</div>`;
  document.querySelectorAll("[data-cty]").forEach((b) => b.addEventListener("click", () => { STATE.country = b.dataset.cty; render(); }));
}

// professional tooltips: data-tip (custom #ctip, no native title)
function initTooltips() {
  let tip = document.getElementById("ctip");
  if (!tip) { tip = document.createElement("div"); tip.id = "ctip"; document.body.appendChild(tip); }
  document.addEventListener("mouseover", (e) => { const t = e.target.closest("[data-tip]"); if (t) { tip.textContent = t.getAttribute("data-tip"); tip.style.display = "block"; } });
  document.addEventListener("mousemove", (e) => { tip.style.left = Math.min(e.clientX + 14, innerWidth - 320) + "px"; tip.style.top = (e.clientY + 16) + "px"; });
  document.addEventListener("mouseout", (e) => { const t = e.target.closest("[data-tip]"); if (t) tip.style.display = "none"; });
}

initTooltips();
render();
