/* Electronic Market Intelligence — comparison terminal. Client-side layer aggregation. */
'use strict';

const LAYER_COLORS = { L0: '#64748b', L1: '#0284c7', L2: '#0e7490', L3: '#16a34a', L4: '#d97706', L5: '#7c3aed' };
const METRICS = {
  revenue:          { label: 'Revenue',        kind: 'usd',  better: 'up' },
  gross_margin:     { label: 'Gross Margin',   kind: 'pct',  better: 'up' },
  operating_income: { label: 'Op Income',      kind: 'usd',  better: 'up' },
  net_income:       { label: 'Earnings',       kind: 'usd',  better: 'up' },
  inventory_days:   { label: 'Inventory Days', kind: 'days', better: 'down' },
  capex:            { label: 'Capex',          kind: 'usd',  better: 'up' },
};
const METRIC_ORDER = ['revenue', 'gross_margin', 'operating_income', 'net_income', 'inventory_days', 'capex'];
const MODES = { value: 'Value', yoy: 'YoY', qoq: 'QoQ' };
const CONSENSUS_METRICS = { revenue: 'revenue', net_income: 'earnings' };

let DATA = null, MARKET = null, SIGNALS = null, COLS = [], LASTQ = null;
let STATE = { view: 'signals', metric: 'revenue', mode: 'value', search: '', expanded: new Set(),
  countries: new Set(), consensus: false, reportedOnly: true, minRev: true, ccOpen: false,
  mregion: 'worldwide', mrange: 10,
  exSubs: new Set(), exOpen: false,
  sigView: 'topics', sigMetric: 'tonecmp', topicLayers: [], topicLabels: 'auto', topicSeg: 'all',
  topicPin: undefined, topicGroups: new Set(), topicDrvAll: false, topicCoAll: false,
  topicCtlOpen: false, topicDrill: null, topicTopN: 30, topicLock: false, drawerW: 440 };
const charts = [];
let TOPIC_PLAY = null;

/* formatting */
const fUSD = v => v == null ? '—' : (Math.abs(v) >= 1e12 ? `$${(v/1e12).toFixed(2)}T` : Math.abs(v) >= 1e9 ? `$${(v/1e9).toFixed(1)}B` : Math.abs(v) >= 1e6 ? `$${(v/1e6).toFixed(0)}M` : `$${(v/1e9).toFixed(2)}B`);
const fPct = v => v == null ? '—' : `${(v*100).toFixed(1)}%`;
const fSign = v => v == null ? '—' : `${v >= 0 ? '+' : ''}${(v*100).toFixed(1)}%`;
const fPP = v => v == null ? '—' : `${v >= 0 ? '+' : ''}${(v*100).toFixed(1)}`;
const fDays = v => v == null ? '—' : `${v.toFixed(0)}`;
const fDdays = v => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(0)}`;
const qLabel = q => { const [y, n] = q.split('Q'); return `Q${n} '${y.slice(2)}`; };
function fmtCell(v, mode, kind) {
  if (v == null) return '—';
  if (mode === 'value') return kind === 'usd' ? fUSD(v) : kind === 'pct' ? fPct(v) : fDays(v);
  return kind === 'usd' ? fSign(v) : kind === 'pct' ? fPP(v) : fDdays(v);
}
function heat(v, scale, invert) {
  if (v == null || isNaN(v)) return 'transparent';
  let x = Math.max(-1, Math.min(1, v / scale)); if (invert) x = -x;
  const c = x >= 0 ? [22, 163, 74] : [220, 38, 38];
  return `rgba(${c[0]},${c[1]},${c[2]},${(Math.abs(x) * 0.42 + 0.06).toFixed(2)})`;
}

/* filtering + aggregation */
const hasCons = c => !!(c.consensus && c.consensus.revenue && c.consensus.revenue.next_q_usd != null);
function filtered() {
  // Exclusions (Memory / NVIDIA / conglomerates) are a MARKET-page tool only — they do NOT
  // filter the Supply-Chain matrix, which always shows the full universe (with ⚠ flags).
  return DATA.companies.filter(c =>
    (STATE.countries.size === 0 || STATE.countries.has(c.region)) &&
    (!STATE.consensus || hasCons(c)) &&
    (!STATE.minRev || (c.metrics.revenue.usd != null && c.metrics.revenue.usd >= 100e6)));
}
function reportedLatest(c) {
  if (!STATE.reportedOnly || !LASTQ) return true;
  const i = c.qi[LASTQ];
  return i != null && c.q.revenue.v[i] != null;
}
function computeColumns(members) {
  const cnt = {};
  members.forEach(c => (c.q.calq || []).forEach((q, i) => { if (c.q.revenue.v[i] != null) cnt[q] = (cnt[q] || 0) + 1; }));
  const qs = Object.keys(cnt).sort();
  if (!qs.length) return [];
  const max = Math.max(...Object.values(cnt));
  return qs.filter(q => cnt[q] >= Math.max(2, 0.5 * max)).slice(-6);
}
function agg(members, metric, field, q) {
  const kind = METRICS[metric].kind;
  if (field === 'value' && kind === 'usd') {
    let s = null;
    for (const c of members) { const i = c.qi[q]; if (i == null) continue; const v = c.q[metric].v[i]; if (v != null) s = (s || 0) + v; }
    return s;
  }
  let n = 0, d = 0, any = false;
  for (const c of members) {
    const i = c.qi[q]; if (i == null) continue;
    const w = c.q.revenue.v[i];
    const x = field === 'value' ? c.q[metric].v[i] : c.q[metric][field][i];
    if (x != null && w != null) { n += w * x; d += w; any = true; }
  }
  return any && d ? n / d : null;
}
function cval(c, metric, field, q) {
  const i = c.qi[q]; if (i == null) return null;
  return field === 'value' ? c.q[metric].v[i] : c.q[metric][field][i];
}
const consMetricsOn = () => STATE.consensus && (STATE.metric in CONSENSUS_METRICS);
function coCons(c, slot, field) {
  const cc = c.consensus && c.consensus[CONSENSUS_METRICS[STATE.metric]]; if (!cc) return null;
  if (field === 'val') return STATE.metric === 'revenue' ? cc[slot + '_q_usd'] : null;
  if (field === 'yoy') return cc[slot + '_q_yoy'];
  // qoq: this-Q vs last actual (precomputed); next-Q vs this-Q estimate
  if (slot === 'this') return cc['this_q_qoq'];
  if (STATE.metric === 'revenue' && cc.next_q_usd != null && cc.this_q_usd) return cc.next_q_usd / cc.this_q_usd - 1;
  return null;
}
function aggCons(members, slot, field) {
  if (field === 'val') {
    if (STATE.metric !== 'revenue') return null;
    let s = null;
    for (const c of members) { const v = c.consensus && c.consensus.revenue && c.consensus.revenue[slot + '_q_usd']; if (v != null) s = (s || 0) + v; }
    return s;
  }
  let n = 0, d = 0;
  for (const c of members) { const g = coCons(c, slot, field), w = c.metrics.revenue.usd; if (g != null && w != null) { n += w * g; d += w; } }
  return d ? n / d : null;
}

/* column model: quarter cells (current mode) + YoY/QoQ summary (value mode only) + consensus (if on) */
function columnDefs() {
  const defs = COLS.map((q, i) => ({ kind: 'q', q, label: qLabel(q), cls: i === COLS.length - 1 ? 'now' : undefined }));
  if (STATE.mode === 'value' && LASTQ) {
    defs.push({ kind: 'yoy', q: LASTQ, label: 'YoY', cls: 'sumcol' });
    defs.push({ kind: 'qoq', q: LASTQ, label: 'QoQ', cls: 'sumcol' });
  }
  if (consMetricsOn()) {
    const tip = "Analyst consensus for each company's NEXT UNREPORTED fiscal quarter. Fiscal years differ, so these are NOT calendar-aligned across companies, and only names that have consensus are summed (≈90–100% per layer). Segment-adjusted names (SEG) have their consensus scaled to the same segment. Treat the layer totals as indicative, not strictly apple-to-apple with the reported quarters.";
    defs.push({ kind: 'cons', slot: 'this', field: 'val', label: 'This-Q ᴱ', cls: 'fwd', tip });
    defs.push({ kind: 'cons', slot: 'this', field: 'qoq', label: 'This-Q QoQ', tip });
    defs.push({ kind: 'cons', slot: 'next', field: 'val', label: 'Next-Q ᴱ', cls: 'fwd', tip });
    defs.push({ kind: 'cons', slot: 'next', field: 'qoq', label: 'Next-Q QoQ', tip });
  }
  return defs;
}
const defFmtMode = d => d.kind === 'cons' ? (d.field === 'val' ? 'value' : d.field)
  : (d.kind === 'q' ? STATE.mode : d.kind);
function groupVal(members, d) {
  if (d.kind === 'cons') return aggCons(members, d.slot, d.field);
  return agg(members, STATE.metric, d.kind === 'q' ? STATE.mode : d.kind, d.q);
}
function coValue(c, d) {
  if (d.kind === 'cons') return coCons(c, d.slot, d.field);
  return cval(c, STATE.metric, d.kind === 'q' ? STATE.mode : d.kind, d.q);
}
function cell(d, v, kind) {
  const m = defFmtMode(d), extra = d.cls ? ' ' + d.cls : '';
  if (m === 'value') return `<td class="num cell${extra}">${fmtCell(v, 'value', kind)}</td>`;
  if (v == null) return `<td class="num cell muted${extra}">—</td>`;
  const scale = kind === 'usd' ? 0.5 : kind === 'pct' ? 0.05 : 25, invert = METRICS[STATE.metric].better === 'down';
  const up = (v >= 0) !== invert;
  return `<td class="cell${extra}"><span class="chip num ${up ? 'up' : 'down'}" style="background:${heat(v, scale, invert)}">${fmtCell(v, m, kind)}</span></td>`;
}

/* render */
function render() {
  if (TOPIC_PLAY && !(STATE.view === 'signals' && STATE.sigView === 'topics')) topicPlayStop();
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === STATE.view));
  const mainEl = document.getElementById('main');
  if (mainEl) mainEl.classList.toggle('has-drawer', STATE.view === 'signals' && STATE.sigView === 'topics');
  if (STATE.view === 'market') return renderMarket();
  if (STATE.view === 'signals') return renderSignals();
  return renderChain();
}
function renderChain() {
  COLS = computeColumns(filtered());
  LASTQ = COLS.length ? COLS[COLS.length - 1] : null;
  const main = document.getElementById('main');
  main.innerHTML = controlsHTML() + matrixHTML()
    + `<div class="panel"><h3 id="ovh"></h3><div class="chart" id="overlay"></div><div class="note" id="ovnote"></div></div>`;
  document.getElementById('ovh').textContent = `${METRICS[STATE.metric].label} · ${MODES[STATE.mode]} — layer trajectories (lead vs lag)`;
  document.getElementById('ovnote').textContent = STATE.mode !== 'value'
    ? 'Growth needs the year-ago quarter; Yahoo provides ~5 quarters of history, so YoY appears only for the most recent quarters.' : '';
  wireControls(main); wireMatrix(main); disposeCharts(); drawOverlay();
}

function controlsHTML() {
  const metrics = METRIC_ORDER.map(k => `<button class="chip ${STATE.metric === k ? 'active' : ''}" data-m="${k}">${METRICS[k].label}</button>`).join('');
  const modes = Object.keys(MODES).map(k => `<button class="seg ${STATE.mode === k ? 'active' : ''}" data-mode="${k}">${MODES[k]}</button>`).join('');
  const nC = STATE.countries.size;
  const ccPanel = STATE.ccOpen ? `<div class="cc-panel">
      <div class="cc-row"><button class="cc-all" data-cc="__all">All countries</button></div>
      <div class="cc-grid">${DATA.regions.map(r => `<button class="cc-chip ${STATE.countries.has(r) ? 'on' : ''}" data-cc="${r}">${r}</button>`).join('')}</div></div>` : '';
  return `<div class="toolbar">
    <div class="metric-switch">${metrics}</div>
    <div class="seg-group">${modes}</div>
    <button class="seg-btn ${STATE.minRev ? 'active' : ''}" id="minRevBtn" title="Hide companies with quarterly revenue below $100M">≥ $100M</button>
    <button class="seg-btn ${STATE.reportedOnly ? 'active' : ''}" id="repBtn" title="Hide companies that haven't reported the latest quarter yet (apple-to-apple)">✓ Reported ${LASTQ ? qLabel(LASTQ) : ''}</button>
    <button class="seg-btn ${STATE.consensus ? 'active' : ''}" id="consBtn" title="Add forward analyst consensus columns; keep only companies that have consensus">◷ Consensus</button>
    <div class="cc-wrap"><button class="seg-btn ${nC ? 'active' : ''}" id="ccBtn">▾ Country${nC ? ` (${nC})` : ''}</button>${ccPanel}</div>
    <input id="search" class="search" placeholder="Filter company…" value="${STATE.search.replace(/"/g, '&quot;')}" />
  </div>`;
}
function wireControls(root) {
  root.querySelectorAll('[data-m]').forEach(b => b.onclick = () => { STATE.metric = b.dataset.m; render(); });
  root.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => { STATE.mode = b.dataset.mode; render(); });
  root.querySelector('#minRevBtn').onclick = () => { STATE.minRev = !STATE.minRev; render(); };
  root.querySelector('#repBtn').onclick = () => { STATE.reportedOnly = !STATE.reportedOnly; render(); };
  root.querySelector('#consBtn').onclick = () => { STATE.consensus = !STATE.consensus; render(); };
  root.querySelector('#ccBtn').onclick = (e) => { e.stopPropagation(); STATE.ccOpen = !STATE.ccOpen; render(); };
  root.querySelectorAll('[data-cc]').forEach(b => b.onclick = (e) => {
    e.stopPropagation(); const r = b.dataset.cc;
    if (r === '__all') STATE.countries.clear();
    else { STATE.countries.has(r) ? STATE.countries.delete(r) : STATE.countries.add(r); }
    render();
  });
  const sb = root.querySelector('#search');
  sb.oninput = () => { STATE.search = sb.value; render(); sb.focus(); sb.setSelectionRange(sb.value.length, sb.value.length); };
}

function matrixHTML() {
  const M = METRICS[STATE.metric], defs = columnDefs();
  const base = filtered(), q = STATE.search.trim().toLowerCase();
  const colspan = defs.length + 1;
  const head = `<th class="l sticky">Layer / Company</th>` + defs.map(d => `<th class="qh${d.cls ? ' ' + d.cls : ''}"${d.tip ? ` title="${d.tip.replace(/"/g, '&quot;')}"` : ''}>${d.label}</th>`).join('');
  let body = '';

  if (q) {
    const hits = base.filter(c => c.ticker.toLowerCase().includes(q) || (c.name || '').toLowerCase().includes(q))
      .sort((a, b) => (b.metrics.revenue.usd || 0) - (a.metrics.revenue.usd || 0));
    body = hits.map((c, idx) => companyRow(c, 0, defs, idx)).join('') || `<tr><td colspan="${colspan}" class="empty">No matches</td></tr>`;
  } else {
    for (const L of DATA.layers) {
      const members = base.filter(c => c.layer === L.layer && reportedLatest(c));
      if (!members.length) continue;
      const open = STATE.expanded.has(L.layer);
      body += groupRow({ key: L.layer, level: 0, open, color: LAYER_COLORS[L.layer], tag: L.layer, name: L.layer_name, n: members.length, members, defs, kind: M.kind });
      if (!open) continue;
      for (const sb of L.sublayers) {
        const sm = members.filter(c => c.sublayer === sb.sublayer);
        if (!sm.length) continue;
        const skey = `${L.layer}|${sb.sublayer}`, sopen = STATE.expanded.has(skey);
        body += groupRow({ key: skey, level: 1, open: sopen, color: LAYER_COLORS[L.layer], tag: sb.sublayer, name: sb.sublayer_name, n: sm.length, members: sm, defs, kind: M.kind });
        if (!sopen) continue;
        body += sm.slice().sort((a, b) => (b.metrics.revenue.usd || 0) - (a.metrics.revenue.usd || 0)).map((c, idx) => companyRow(c, 2, defs, idx)).join('');
      }
    }
    if (!body) body = `<tr><td colspan="${colspan}" class="empty">No companies match the current filters</td></tr>`;
  }
  return `<div class="tbl-wrap"><table class="matrix"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function groupRow({ key, level, open, color, tag, name, n, members, defs, kind }) {
  const pad = 12 + (level ? 18 : 0);
  const cells = defs.map(d => cell(d, groupVal(members, d), kind)).join('');
  return `<tr class="grp lvl${level}" data-exp="${key}" style="--c:${color}">
    <td class="l sticky" style="padding-left:${pad}px"><span class="caret">${open ? '▾' : '▸'}</span>
      <span class="lyr-dot" style="background:${color}"></span><span class="g-tag">${tag}</span>
      <span class="g-name">${name}</span> <span class="g-n">${n}</span></td>${cells}</tr>`;
}
function companyRow(c, level, defs, idx) {
  const kind = METRICS[STATE.metric].kind;
  const cells = defs.map(d => cell(d, coValue(c, d), kind)).join('');
  const flag = c.flag ? `<span class="flag" title="${String(c.flag).replace(/"/g, '&quot;')}">⚠</span>` : '';
  const est = c.estimate_note ? `<span class="estbadge" title="${String(c.estimate_note).replace(/"/g, '&quot;')}">EST</span>` : '';
  const seg = c.seg_note ? `<span class="segbadge" title="${String(c.seg_note).replace(/"/g, '&quot;')}">SEG</span>` : '';
  return `<tr class="co ${idx % 2 ? 'zebra' : ''}" data-tk="${c.ticker}">
    <td class="l sticky" style="padding-left:${12 + level * 18}px"><span class="tk">${c.ticker}</span>
      <span class="co-name">${c.name || ''}</span>${flag}${est}${seg}<span class="co-reg">${c.region || ''}</span></td>${cells}</tr>`;
}
function wireMatrix(root) {
  root.querySelectorAll('tr[data-exp]').forEach(tr => tr.onclick = () => {
    const k = tr.dataset.exp; STATE.expanded.has(k) ? STATE.expanded.delete(k) : STATE.expanded.add(k); render();
  });
  root.querySelectorAll('tr[data-tk]').forEach(tr => tr.onclick = () => openCompany(tr.dataset.tk));
}

/* overlay (bottom) */
function mk(id) { const el = document.getElementById(id); if (!el) return null; const c = echarts.init(el); charts.push(c); return c; }
function disposeCharts() { while (charts.length) { try { charts.pop().dispose(); } catch (e) {} } }
const axisStyle = () => ({ axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#475569', fontFamily: 'Fira Code', fontSize: 10 }, splitLine: { lineStyle: { color: '#eef2f7' } } });
function drawOverlay() {
  const c = mk('overlay'); if (!c || !COLS.length) return;
  const M = METRICS[STATE.metric], base = filtered(), valueMode = STATE.mode === 'value';
  const series = DATA.layers.map(L => {
    const members = base.filter(x => x.layer === L.layer && reportedLatest(x));
    if (!members.length) return null;
    let arr = COLS.map(q => agg(members, STATE.metric, STATE.mode, q));
    if (valueMode && M.kind === 'usd') arr = arr.map(v => v == null ? null : +(v / 1e9).toFixed(1));
    else if (!valueMode) arr = arr.map(v => v == null ? null : +(M.kind === 'usd' ? (v * 100).toFixed(1) : M.kind === 'pct' ? (v * 100).toFixed(2) : v.toFixed(1)));
    return { name: `${L.layer} ${L.layer_name}`, type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: arr, itemStyle: { color: LAYER_COLORS[L.layer] }, lineStyle: { width: 2.5 }, connectNulls: true };
  }).filter(Boolean);
  const logY = valueMode && M.kind === 'usd';
  const unit = valueMode ? (M.kind === 'usd' ? 'USD B (log)' : M.kind === 'pct' ? '%' : 'days') : (M.kind === 'usd' ? '%' : M.kind === 'pct' ? 'ppt' : 'days Δ');
  c.setOption({
    animation: false, grid: { left: 56, right: 16, top: 14, bottom: 52 },
    legend: { bottom: 0, textStyle: { color: '#475569', fontSize: 11 }, itemWidth: 18, itemHeight: 2 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: COLS.map(qLabel), boundaryGap: false, ...axisStyle() },
    yAxis: { type: logY ? 'log' : 'value', name: unit, nameTextStyle: { color: '#64748B' }, ...axisStyle(), scale: !valueMode },
    series,
  });
}

/* drilldown */
function openCompany(tk) {
  const c = DATA.companies.find(x => x.ticker === tk); if (!c) return;
  document.getElementById('m-name').textContent = c.name || tk;
  document.getElementById('m-sub').textContent = `${c.ticker} · ${c.layer} ${c.sublayer || ''} · ${c.region} · reports in ${c.currency || '—'} · latest ${c.latest_period}`;
  const m = c.metrics, rc = (c.consensus && c.consensus.revenue) || {}, ec = (c.consensus && c.consensus.earnings) || {};
  const g = c.guidance || {};
  const gHTML = (g.revenue || g.gross_margin) ? `<div class="panel"><h3>Company guidance${g.period ? ' · ' + g.period : ''} — from EDGAR 8-K</h3>
      <div class="statrow">
        ${g.revenue ? stat('Guided Revenue', fUSD(g.revenue.mid)) : ''}
        ${(g.revenue && g.revenue.low) ? stat('Guide Range', fUSD(g.revenue.low) + '–' + fUSD(g.revenue.high)) : ''}
        ${g.gross_margin ? stat('Guided Gross Margin', fPct(g.gross_margin.mid)) : ''}</div>
      <div class="note">Company-issued guidance, parsed from the latest 8-K earnings press release${g.filed ? ' (filed ' + g.filed + ')' : ''}. Compare with the analyst consensus below and the latest actual above.</div></div>` : '';
  document.getElementById('m-body').innerHTML = `
    <div class="statrow">
      ${stat('Revenue', fUSD(m.revenue.usd))}${stat('Rev YoY', fSign(m.revenue.yoy), m.revenue.yoy)}${stat('Rev QoQ', fSign(m.revenue.qoq), m.revenue.qoq)}
      ${stat('Gross Margin', fPct(m.gross_margin.value))}${stat('Op Margin', fPct(m.operating_income.margin))}${stat('Net Margin', fPct(m.net_income.margin))}
      ${stat('Inventory Days', fDays(m.inventory_days.value))}${stat('Capex', fUSD(m.capex.usd))}${stat('Mkt Cap', c.market_cap_usd ? fUSD(c.market_cap_usd) : '—')}</div>
    <div class="panel"><h3>Revenue (bars) & margins (lines)</h3><div class="chart-sm" id="coChart"></div></div>
    ${gHTML}
    <div class="panel"><h3>Forward analyst consensus (midpoint of analyst range)</h3>
      <div class="statrow">
        ${stat('This-Q Rev', fUSD(rc.this_q_usd))}${stat('This-Q YoY', fSign(rc.this_q_yoy), rc.this_q_yoy)}${stat('This-Q QoQ', fSign(rc.this_q_qoq), rc.this_q_qoq)}
        ${stat('Next-Q Rev', fUSD(rc.next_q_usd))}${stat('Next-Q YoY', fSign(rc.next_q_yoy), rc.next_q_yoy)}${stat('EPS YoY (nextQ)', fSign(ec.next_q_yoy), ec.next_q_yoy)}</div>
      <div class="note">Consensus = mean of ${rc.num_analysts || '—'} analyst estimates. Company-issued guidance (CEO/CFO) is a later phase — this is the analyst consensus midpoint.</div></div>`;
  document.getElementById('scrim').classList.add('open'); document.getElementById('modal').classList.add('open');
  coChart(c);
}
function stat(label, value, signed) {
  return `<div class="stat"><div class="l">${label}</div><div class="v ${signed == null ? '' : signed >= 0 ? 'pos' : 'neg'}">${value}</div></div>`;
}
function coChart(c) {
  const el = document.getElementById('coChart'); if (!el) return;
  const ch = echarts.init(el); charts.push(ch); const q = c.q;
  const rev = q.revenue.v.map(v => v == null ? null : +(v / 1e9).toFixed(2));
  const gm = q.gross_margin.v.map(v => v == null ? null : +(v * 100).toFixed(1));
  const om = q.operating_income.v.map((v, i) => (v == null || !q.revenue.v[i]) ? null : +(v / q.revenue.v[i] * 100).toFixed(1));
  ch.setOption({
    animation: false, grid: { left: 50, right: 50, top: 30, bottom: 30 },
    legend: { top: 0, textStyle: { color: '#475569' }, data: ['Revenue $B', 'Gross %', 'Op %'] },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: (q.calq || []).map(qLabel), ...axisStyle() },
    yAxis: [{ type: 'value', name: '$B', ...axisStyle() }, { type: 'value', name: '%', position: 'right', ...axisStyle(), splitLine: { show: false } }],
    series: [
      { name: 'Revenue $B', type: 'bar', data: rev, itemStyle: { color: '#2563eb' }, barWidth: '52%' },
      { name: 'Gross %', type: 'line', yAxisIndex: 1, data: gm, smooth: true, itemStyle: { color: '#16a34a' } },
      { name: 'Op %', type: 'line', yAxisIndex: 1, data: om, smooth: true, itemStyle: { color: '#d97706' } },
    ],
  });
}
function closeModal() { document.getElementById('scrim').classList.remove('open'); document.getElementById('modal').classList.remove('open', 'wide'); }

/* ---------- Market view (WSTS / ECIA / SEMI) ---------- */
const fB = v => v == null ? '—' : '$' + (v / 1e9).toFixed(1) + 'B';
/* Excluded market = WSTS worldwide billings MINUS the companies in the selected L3 chip sub-layers,
   quarter by quarter. Exclude options follow the real taxonomy: 3.1 Analog, 3.2 Logic, 3.4 Memory
   (3.3 IP&E passives aren't WSTS semiconductor billings, so it isn't offered). WSTS is the
   comprehensive base; the window is limited to quarters where each excluded sub-layer is broadly
   covered (≥70% of its companies) — non-US names are ~5q on free data, so memory/analog-heavy
   exclusions are shorter than logic. Respects the Range buttons. */
const SUB_LABELS = { '3.1': 'Analog', '3.2': 'Logic', '3.4': 'Memory' };
const EX_SUBS = ['3.1', '3.2', '3.4'];
function exMarketSeries() {
  const m = MARKET;
  const wmap = {}; m.quarters.forEach((q, i) => { if (m.billings_q.worldwide[i] != null) wmap[q] = m.billings_q.worldwide[i]; });
  const subs = [...STATE.exSubs];
  if (!subs.length) return { quarters: [], billings: [], yoy: [], parts: [] };
  const cos = DATA.companies.filter(c => c.layer === 'L3' && subs.includes(c.sublayer));
  const lastRev = c => { const v = c.q.revenue.v; for (let i = v.length - 1; i >= 0; i--) if (v[i] != null) return v[i]; return 0; };
  // reference = the major companies of the excluded sub-layers (~85% of latest revenue); small ragged
  // names are ignored so they don't collapse the matched window. The window is where every ref reports.
  const sorted = cos.slice().sort((a, b) => lastRev(b) - lastRev(a));
  const tot = sorted.reduce((s, c) => s + lastRev(c), 0) || 1;
  const ref = []; let cum = 0;
  for (const c of sorted) { ref.push(c.ticker); cum += lastRev(c); if (cum >= 0.80 * tot) break; }
  const rev = {}, present = {};                 // ticker|q -> USD ; q -> Set(ref tickers present)
  cos.forEach(c => { const v = c.q.revenue.v; (c.q.calq || []).forEach((q, i) => { if (v[i] != null && wmap[q] != null) { rev[c.ticker + '|' + q] = v[i]; if (ref.includes(c.ticker)) (present[q] = present[q] || new Set()).add(c.ticker); } }); });
  const wq = m.quarters.filter(q => wmap[q] != null);
  let L = null; for (let i = wq.length - 1; i >= 0; i--) { const p = present[wq[i]]; if (p && ref.every(t => p.has(t))) { L = i; break; } }
  if (L == null) return { quarters: [], billings: [], yoy: [], parts: [] };
  let start = L; for (let i = L; i >= 0; i--) { const p = present[wq[i]]; if (p && ref.every(t => p.has(t))) start = i; else break; }
  const quarters = wq.slice(start, L + 1);
  const sub = q => ref.reduce((s, t) => s + (rev[t + '|' + q] || 0), 0);  // matched ref set every quarter
  const val = q => wmap[q] - sub(q);
  const inWin = new Set(quarters);
  const shift = q => { const [y, n] = q.split('Q'); return `${+y - 1}Q${n}`; };
  const billings = quarters.map(val);
  const yoy = quarters.map(q => { const pq = shift(q); return inWin.has(pq) && val(pq) ? val(q) / val(pq) - 1 : null; });
  return { quarters, billings, yoy, parts: subs.sort().map(s => `${s} ${SUB_LABELS[s] || ''}`.trim()), nref: ref.length };
}
const RANGES = [{ y: 5, l: '5Y' }, { y: 10, l: '10Y' }, { y: 15, l: '15Y' }, { y: 20, l: '20Y' }, { y: 30, l: '30Y' }, { y: 99, l: 'Max' }];
function bottomUpPanel(ex) {
  const sb = (s, lab) => `<button class="seg ${STATE.exSubs.has(s) ? 'on' : ''}" data-mex="${s}">${s} ${lab}</button>`;
  const exOn = ex.parts;
  const m = MARKET;
  let title, stat, note;
  if (exOn.length) {                       // WSTS minus the companies in the excluded sub-layers
    const li = ex.quarters.length - 1;
    stat = li >= 0 ? `${ex.quarters[li]} · ${fB(ex.billings[li])} · YoY <b class="${ex.yoy[li] >= 0 ? 'pos' : 'neg'}">${fSign(ex.yoy[li])}</b>` : 'no overlapping data';
    title = `Semiconductor market <span class="seedtag" style="background:#fee2e2;color:#b91c1c">ex-${exOn.join(' & ')}</span> <span class="seedtag" style="background:#e0f2fe;color:#075985">WSTS − sub-layers</span>`;
    note = li >= 0
      ? `WSTS worldwide billings minus the L3 ${exOn.join(' & ')} companies. ${ex.quarters.length} quarters (${ex.quarters[0]}–${ex.quarters[li]}); window limited by the shortest excluded sub-layer's coverage (non-US names are ~5q on free data).`
      : 'no overlapping data for the selected sub-layers';
  } else {                                  // full WSTS history
    const q = m.quarters, wq = m.billings_q.worldwide, wy = m.yoy_q.worldwide, li = q.length - 1;
    stat = `${q[li]} · ${fB(wq[li])} · YoY <b class="${wy[li] >= 0 ? 'pos' : 'neg'}">${fSign(wy[li])}</b>`;
    title = `Semiconductor market — WSTS total <span class="seedtag" style="background:#dcfce7;color:#166534">full history · ${m.quarters[0]}–${m.as_of}</span>`;
    note = `Full WSTS worldwide billings (use the Range buttons above). Exclude L3 sub-layers — 3.1 Analog, 3.2 Logic, 3.4 Memory — to subtract those companies from the market.`;
  }
  return `<div class="panel">
    <h3>${title}</h3>
    <div class="exbar">
      <span class="exlbl">⊘ EXCLUDE</span>${sb('3.1', 'Analog')}${sb('3.2', 'Logic')}${sb('3.4', 'Memory')}
      <span class="dim" style="font-size:12px;margin-left:auto">Latest: ${stat}</span>
    </div>
    <div class="dim" style="font-size:11px;margin:-2px 0 8px">${note}</div>
    <div class="chart-sm" id="mc6"></div>
  </div>`;
}
const REGION_COLS = { worldwide: '#1d4ed8', americas: '#0284c7', europe: '#0e9488', japan: '#d97706', asiapacific: '#7c3aed' };
function rangeSlice(arr, yrs) { const n = Math.min(arr.length, yrs * 4 + 1); return arr.slice(arr.length - n); }
function renderMarket() {
  const main = document.getElementById('main');
  if (!MARKET) { main.innerHTML = '<div class="loading">market.json not loaded — run scripts/build_market.py</div>'; return; }
  const m = MARKET, cyc = m.cycle, reg = STATE.mregion, lbl = m.region_labels[reg];
  const ex = exMarketSeries();
  const yoyLast = m.yoy_q[reg][m.yoy_q[reg].length - 1];
  const tile = (label, val, sub, cls) => `<div class="kpi"><div class="label">${label}</div><div class="value ${cls || ''}">${val}</div><div class="sub dim">${sub || ''}</div></div>`;
  const regBtns = m.regions.map(r => `<button class="seg ${r === reg ? 'on' : ''}" data-reg="${r}">${m.region_labels[r]}</button>`).join('');
  const rngBtns = RANGES.map(r => `<button class="seg ${r.y === STATE.mrange ? 'on' : ''}" data-rng="${r.y}">${r.l}</button>`).join('');
  main.innerHTML = `
    <div class="view-head"><h1>Semiconductor market — WSTS</h1><span class="crumb">WSTS Historical Billings Report · quarterly · ${m.quarters[0]}–${m.as_of}</span></div>
    <div class="view-sub">Authoritative industry billings by region. Bars = quarterly billings; line = YoY %. Up/down-cycle = consecutive quarters of positive/negative worldwide YoY over ${cyc.n_up + cyc.n_down} completed cycles since 1986. ECIA & SEMI panels are seed placeholders.</div>
    <div class="mkbar">
      <div class="seggrp"><span class="seglbl">Region</span>${regBtns}</div>
      <div class="seggrp"><span class="seglbl">Range</span>${rngBtns}</div>
    </div>
    <div class="kpis">
      ${tile('Cycle phase', cyc.phase, 'worldwide · YoY ' + fSign(cyc.last_yoy), 'phase')}
      ${tile('Current run', (cyc.current_dir === 'up' ? '▲ ' : '▼ ') + cyc.current_run_q + 'Q', cyc.current_dir === 'up' ? 'in up-cycle' : 'in down-cycle', cyc.current_dir === 'up' ? 'pos' : 'neg')}
      ${tile('Avg up-cycle', cyc.avg_up_q + 'Q', 'longest ' + cyc.longest_up_q + 'Q', 'pos')}
      ${tile('Avg down-cycle', cyc.avg_down_q + 'Q', 'longest ' + cyc.longest_down_q + 'Q', 'neg')}
      ${tile(lbl + ' / qtr', fB(m.billings_q[reg][m.billings_q[reg].length - 1]), m.as_of)}
      ${tile('YoY', fSign(yoyLast), lbl, yoyLast >= 0 ? 'pos' : 'neg')}
    </div>
    ${bottomUpPanel(ex)}
    <div class="panel"><h3>${lbl} — quarterly billings ($B) + YoY %</h3><div class="chart" id="mc1"></div></div>
    <div class="grid2">
      <div class="panel"><h3>By region — YoY % per quarter</h3><div class="chart-sm" id="mc2"></div></div>
      <div class="panel"><h3>By region — quarterly billings ($B)</h3><div class="chart-sm" id="mc3"></div></div>
    </div>
    <div class="panel"><h3>Memory market — DRAM + NAND industry revenue ($B/qtr) <span class="seedtag" style="background:#ede9fe;color:#6d28d9">TrendForce</span></h3><div class="chart-sm" id="mc7"></div></div>
    <div class="panel"><h3>Leading indicators <span class="seedtag">SEED — replace with official ECIA / SEMI</span></h3><div class="chart-sm" id="mc5"></div></div>`;
  main.querySelectorAll('[data-reg]').forEach(b => b.onclick = () => { STATE.mregion = b.dataset.reg; render(); });
  main.querySelectorAll('[data-rng]').forEach(b => b.onclick = () => { STATE.mrange = +b.dataset.rng; render(); });
  main.querySelectorAll('[data-mex]').forEach(b => b.onclick = () => { const s = b.dataset.mex; STATE.exSubs.has(s) ? STATE.exSubs.delete(s) : STATE.exSubs.add(s); render(); });
  disposeCharts();
  drawMarketCharts(m);
}
function drawMarketCharts(m) {
  const yrs = STATE.mrange, reg = STATE.mregion, ax = axisStyle();
  const g = { left: 56, right: 52, top: 30, bottom: 28 };
  const q = rangeSlice(m.quarters, yrs);
  const Bil = r => rangeSlice(m.billings_q[r], yrs).map(v => +(v / 1e9).toFixed(1));
  const Yoy = r => rangeSlice(m.yoy_q[r], yrs).map(v => v == null ? null : +(v * 100).toFixed(1));
  const col = REGION_COLS[reg];
  // mc1: selected region — billings bars + YoY line (dual axis)
  let c = mk('mc1');
  if (c) c.setOption({ animation: false, grid: g, tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#475569' }, data: ['Billings $B', 'YoY %'] },
    xAxis: { type: 'category', data: q, ...ax },
    yAxis: [{ type: 'value', name: '$B', ...ax }, { type: 'value', name: 'YoY %', position: 'right', ...ax, splitLine: { show: false } }],
    series: [
      { name: 'Billings $B', type: 'bar', data: Bil(reg), itemStyle: { color: '#cfe0f5' } },
      { name: 'YoY %', type: 'line', yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { width: 2.5 }, itemStyle: { color: col }, data: Yoy(reg),
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0 }], lineStyle: { color: '#94a3b8', type: 'dashed' } } }] });
  // mc2: all regions YoY %
  const others = m.regions;
  c = mk('mc2');
  if (c) c.setOption({ animation: false, grid: { left: 48, right: 16, top: 22, bottom: 26 }, tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#475569' }, data: others.map(r => m.region_labels[r]) },
    xAxis: { type: 'category', data: q, ...ax }, yAxis: { type: 'value', name: '%', ...ax },
    series: others.map(r => ({ name: m.region_labels[r], type: 'line', smooth: true, symbol: 'none', lineStyle: { width: r === 'worldwide' ? 2.5 : 1.3 }, itemStyle: { color: REGION_COLS[r] }, data: Yoy(r),
      markLine: r === 'worldwide' ? { silent: true, symbol: 'none', data: [{ yAxis: 0 }], lineStyle: { color: '#cbd5e1', type: 'dashed' } } : undefined })) });
  // mc3: all regions billings
  c = mk('mc3');
  if (c) c.setOption({ animation: false, grid: { left: 48, right: 16, top: 22, bottom: 26 }, tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#475569' }, data: others.map(r => m.region_labels[r]) },
    xAxis: { type: 'category', data: q, ...ax }, yAxis: { type: 'value', name: '$B', ...ax },
    series: others.map(r => ({ name: m.region_labels[r], type: 'line', smooth: true, symbol: 'none', lineStyle: { width: r === 'worldwide' ? 2.5 : 1.3 }, itemStyle: { color: REGION_COLS[r] }, data: Bil(r) })) });
  // mc6: full WSTS history by default; company-derived ex-Memory/NVIDIA (limited) when excluding
  const anyEx = STATE.exSubs.size > 0;
  let xq, bil, yo, barName;
  if (anyEx) {
    const ex = exMarketSeries();
    const sl = Math.min(ex.quarters.length, yrs * 4 + 1);  // respect Range buttons
    xq = ex.quarters.slice(-sl); barName = 'WSTS − excluded $B';
    bil = ex.billings.slice(-sl).map(v => +(v / 1e9).toFixed(1));
    yo = ex.yoy.slice(-sl).map(v => v == null ? null : +(v * 100).toFixed(1));
  } else {
    xq = rangeSlice(m.quarters, yrs); barName = 'WSTS billings $B';
    bil = rangeSlice(m.billings_q.worldwide, yrs).map(v => +(v / 1e9).toFixed(1));
    yo = rangeSlice(m.yoy_q.worldwide, yrs).map(v => v == null ? null : +(v * 100).toFixed(1));
  }
  c = mk('mc6');
  if (c) c.setOption({ animation: false, grid: g, tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#475569' }, data: [barName, 'YoY %'] },
    xAxis: { type: 'category', data: xq, ...ax },
    yAxis: [{ type: 'value', name: '$B', ...ax }, { type: 'value', name: 'YoY %', position: 'right', ...ax, splitLine: { show: false } }],
    series: [
      { name: barName, type: 'bar', data: bil, itemStyle: { color: anyEx ? '#bae6fd' : '#cfe0f5' } },
      { name: 'YoY %', type: 'line', yAxisIndex: 1, smooth: true, symbol: anyEx ? 'circle' : 'none', symbolSize: 5, lineStyle: { width: 2.5 }, itemStyle: { color: '#0369a1' }, data: yo,
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0 }], lineStyle: { color: '#94a3b8', type: 'dashed' } } }] });
  // mc7: memory market — DRAM + NAND stacked bars + total YoY line
  if (m.memory) {
    const mem = m.memory, dram = mem.dram.map(v => +(v / 1e9).toFixed(1)), nand = mem.nand.map(v => +(v / 1e9).toFixed(1));
    const tot = mem.quarters.map((_, i) => mem.dram[i] + mem.nand[i]);
    const myoy = mem.quarters.map((_, i) => i - 4 >= 0 && tot[i - 4] ? +((tot[i] / tot[i - 4] - 1) * 100).toFixed(1) : null);
    c = mk('mc7');
    if (c) c.setOption({ animation: false, grid: g, tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { color: '#475569' }, data: ['DRAM', 'NAND', 'Total YoY %'] },
      xAxis: { type: 'category', data: mem.quarters, ...ax },
      yAxis: [{ type: 'value', name: '$B', ...ax }, { type: 'value', name: 'YoY %', position: 'right', ...ax, splitLine: { show: false } }],
      series: [
        { name: 'DRAM', type: 'bar', stack: 'm', data: dram, itemStyle: { color: '#7c3aed' } },
        { name: 'NAND', type: 'bar', stack: 'm', data: nand, itemStyle: { color: '#c4b5fd' } },
        { name: 'Total YoY %', type: 'line', yAxisIndex: 1, smooth: true, symbol: 'circle', symbolSize: 5, lineStyle: { width: 2.5 }, itemStyle: { color: '#0369a1' }, data: myoy }] });
  }
  // mc5: ECIA book-to-bill + SEMI (seed)
  c = mk('mc5');
  if (c) c.setOption({ animation: false, grid: { left: 50, right: 50, top: 26, bottom: 28 }, tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#475569' }, data: ['ECIA book-to-bill', 'SEMI NA equip $B'] },
    xAxis: { type: 'category', data: m.ecia.months.map(p => p.slice(2)), ...ax },
    yAxis: [{ type: 'value', name: 'B:B', min: 0.8, max: 1.2, ...ax }, { type: 'value', name: '$B', position: 'right', ...ax, splitLine: { show: false } }],
    series: [{ name: 'ECIA book-to-bill', type: 'line', smooth: true, itemStyle: { color: '#16a34a' }, data: m.ecia.book_to_bill,
               markLine: { silent: true, symbol: 'none', data: [{ yAxis: 1 }], lineStyle: { color: '#94a3b8', type: 'dashed' } } },
             { name: 'SEMI NA equip $B', type: 'bar', yAxisIndex: 1, itemStyle: { color: '#f0c98a' }, data: m.semi.na_billings.map(v => +(v / 1e9).toFixed(2)) }] });
}

/* ---------- Signals view: guided supply-chain journey (L1 -> L2 -> L3) ---------- */
const SIG_BG = { strong: '#16a34a', moderate: '#86efac', tight: '#f59e0b', soft: '#fb923c', negative: '#dc2626', na: '#eef2f7' };
const SIG_FG = { strong: '#fff', moderate: '#065f46', tight: '#fff', soft: '#fff', negative: '#fff', na: '#94a3b8' };
const JOURNEY = [
  { layer: 'L0', n: 0, name: 'Distribution (the channel)', tagline: 'the broad-market demand pulse',
    verdict: 'Distributors see orders across thousands of customers before they reach chipmakers. Avnet & Arrow: book-to-bill back above parity in all regions, lead times extending, inventories restocking — the broad industrial/auto/mass-market cycle has turned up, led by volume (not yet price).',
    connector: 'that broad demand pulls the whole chain' },
  { layer: 'L1', n: 1, name: 'Foundry', tagline: 'where AI demand lands first',
    verdict: 'TSMC sees every chip order — and the read is unambiguous: AI-accelerator demand keeps climbing, CoWoS advanced packaging is sold out into 2027, and capex was raised to $52–56B.',
    connector: 'That $52–56B of capex turns straight into equipment orders' },
  { layer: 'L2', n: 2, name: 'Equipment & Materials', tagline: 'the capex super-cycle, measured',
    verdict: 'The tool makers confirm it. ASML bookings hit 2× estimates — memory tools overtook logic for the first time ever — and Lam lifted 2026 WFE to $140B+. The money TSMC & Micron promised is real and being spent.',
    connector: 'Those tools build the memory & logic capacity below' },
  { layer: 'L3', n: 3, name: 'Components', tagline: 'where the cycle splits',
    verdict: 'Logic and memory are red-hot and sold out, with memory pricing up 65%+ a quarter. Analog/auto is only now crawling off the bottom. Same industry, opposite ends of the cycle.',
    connector: null },
];
const PILLS = [['AI super-cycle — confirmed across 3 layers', 'up'], ['Bottleneck: packaging + memory', 'warn'],
  ['Capex super-cycle: WFE → $140B', 'up'], ['Auto: bottoming, fragile', 'down'], ['China: equipment headwind', 'down']];
const L3ORDER = { '3.2': 1, '3.4': 2, '3.1': 3 };

function sigJcard(c, idx, sparks) {
  const meters = [['Demand', c.signals.demand], ['Supply', c.signals.supply], ['Pricing', c.signals.pricing], ['Inventory', c.signals.inventory], ['Capex', c.signals.capex]]
    .map(([lab, lv]) => `<div class="meter"><span class="ml">${lab}</span><span class="mp" style="background:${SIG_BG[lv] || '#eef2f7'};color:${SIG_FG[lv] || '#94a3b8'}">${lv === 'na' ? '—' : lv}</span></div>`).join('');
  const t = c.trend, arr = t.length > 1 ? (t[t.length - 1][1] > t[0][1] ? ' ↑' : t[t.length - 1][1] < t[0][1] ? ' ↓' : '') : '';
  const sc = c.sentiment > 0 ? '#16a34a' : c.sentiment < 0 ? '#dc2626' : '#64748b';
  const spark = t.length > 1 ? (sparks.push({ id: 'sp' + idx, trend: t }), `<div class="spark" id="sp${idx}"></div>`) : '';
  const themes = c.themes.map(th => `<span class="th" style="color:${th[1] === 'up' ? '#16a34a' : th[1] === 'down' ? '#dc2626' : '#7c3aed'}">${th[1] === 'up' ? '▲' : th[1] === 'down' ? '▼' : '✦'} ${th[0]}</span>`).join('');
  return `<div class="jcard">
    <div class="jc-top"><span class="lyr-dot" style="background:${LAYER_COLORS[c.layer]}"></span><b>${c.name}</b>
      <span class="dim" style="font-size:10px">${c.sublayer} · ${c.period}</span>
      <span class="jc-sent" style="color:${sc}">${c.sentiment > 0 ? '▲' : c.sentiment < 0 ? '▼' : '■'} ${c.sentiment > 0 ? '+' : ''}${c.sentiment}${arr}</span>${spark}</div>
    <div class="jc-meters">${meters}</div>
    <div class="sigquote">“${c.quote}”</div>
    <div class="jc-themes">${themes}</div>
  </div>`;
}

const SIG_LAYERORD = c => (({ L0: 0, L1: 1, L2: 2, L3: 3 }[c.layer]) ?? 9) * 100 + (parseFloat(c.sublayer) || 0) + (L3ORDER[c.sublayer] ? L3ORDER[c.sublayer] / 100 : 0);
/* message optimism per level, and the credibility discount */
const LVL_OPT = { strong: 85, moderate: 45, tight: 55, soft: -25, negative: -70, na: null };
function sigOpt(cell) { const r = LVL_OPT[cell.review], o = LVL_OPT[cell.outlook]; if (r == null && o == null) return null; if (r == null) return o; if (o == null) return r; return Math.round(0.4 * r + 0.6 * o); }
function sigDisc(call, signal) { let d = Math.round((1 - (call.confidence == null ? 0.8 : call.confidence)) * 35); if ((call.evasion || []).join(' ').toLowerCase().includes(signal)) d += 8; return Math.max(0, Math.min(40, d)); }
const CYCLE_METRICS = [['tonecmp', 'Optimism ⟶ discounted'], ['tone', 'Optimism'], ['toneadj', 'Optimism (Tone discounted)'], ['demand', 'Demand'], ['supply', 'Supply'], ['pricing', 'Pricing'], ['inventory', 'Inventory'], ['capex', 'Capex']];
const FLOW_METRICS = [['sentiment', 'Sentiment'], ['demand', 'Demand'], ['supply', 'Supply'], ['pricing', 'Pricing'], ['inventory', 'Inventory'], ['capex', 'Capex']];
function toneColor(v) { const x = Math.max(-1, Math.min(1, v / 100)), c = x >= 0 ? [22, 163, 74] : [220, 38, 38]; return `rgba(${c[0]},${c[1]},${c[2]},${(Math.abs(x) * 0.78 + 0.10).toFixed(2)})`; }
/* per-quarter continuous Tone Index (-100..+100); adj => discounted by that quarter's Q&A confidence */
function cellTone(S, tk, p, adj) {
  const g = sig => S.facts.find(f => f.ticker === tk && f.period === p && f.signal === sig && f.segment === 'overall');
  const sf = g('sentiment'); if (!sf || sf.value == null) return null;
  const fv = ['demand', 'supply', 'pricing', 'inventory', 'capex'].map(s => { const f = g(s); return f ? TONE_LVL[f.label] : null; }).filter(v => v != null);
  const fund = fv.length ? fv.reduce((a, b) => a + b, 0) / fv.length : 0;
  let idx = 100 * Math.max(-1, Math.min(1, 0.5 * (sf.value / 2) + 0.5 * fund));
  if (adj) { const cf = g('confidence'); idx *= (cf && cf.value != null ? cf.value : 1); }
  return Math.round(idx);
}

function sigSentColor(v) { const x = Math.max(-1, Math.min(1, v / 2)); const c = x >= 0 ? [22, 163, 74] : [220, 38, 38]; return `rgba(${c[0]},${c[1]},${c[2]},${(Math.abs(x) * 0.7 + 0.12).toFixed(2)})`; }
/* continuous Tone Index (-100..+100): blend of language tone + 5 fundamentals + net theme direction */
const TONE_LVL = { strong: 1, moderate: 0.5, tight: 0.6, soft: -0.5, negative: -1 };
function toneIndex(c) {
  const tone = (c.sentiment || 0) / 2;                                  // -1..1 (language read)
  const fv = Object.values(c.signals || {}).map(l => TONE_LVL[l]).filter(v => v != null);
  const fund = fv.length ? fv.reduce((a, b) => a + b, 0) / fv.length : 0; // -1..1 (fundamentals)
  const th = c.themes || [], tv = th.length ? th.reduce((a, t) => a + (t[1] === 'up' ? 1 : t[1] === 'down' ? -1 : 0.3), 0) / th.length : 0;
  const raw = 0.45 * tone + 0.40 * fund + 0.15 * Math.max(-1, Math.min(1, tv));
  return Math.round(100 * Math.max(-1, Math.min(1, raw)));
}

function renderSignals() {
  const main = document.getElementById('main');
  if (!SIGNALS) { main.innerHTML = '<div class="loading">transcripts.json not loaded — run scripts/load_transcripts.py</div>'; return; }
  const S = SIGNALS;
  const subs = [['overview', 'Overview'], ['topics', 'Topics · trends'], ['tree', 'Topic tree'], ['company', 'By company'], ['journey', 'Journey · now'], ['cycle', 'Cycle · over time'], ['matrix', 'Optimism − Discount'], ['flow', 'Propagation'], ['radar', 'Divergence & inflection'], ['roadmap', 'Capability roadmap']];
  const tabs = subs.map(([k, l]) => `<button class="seg ${STATE.sigView === k ? 'on' : ''}" data-sv="${k}">${l}</button>`).join('');
  const sparks = [];
  const body = STATE.sigView === 'cycle' ? sigCycleBody(S)
    : STATE.sigView === 'topics' ? sigTopicsBody(S)
      : STATE.sigView === 'tree' ? sigTreeBody(S)
      : STATE.sigView === 'overview' ? sigOverviewBody(S)
        : STATE.sigView === 'company' ? sigCompanyBody(S)
          : STATE.sigView === 'matrix' ? sigMatrixBody(S)
            : STATE.sigView === 'flow' ? sigFlowBody(S)
              : STATE.sigView === 'radar' ? sigRadarBody(S, sparks)
                : STATE.sigView === 'roadmap' ? sigRoadmapBody(S)
                  : sigJourneyBody(S, sparks);
  main.innerHTML = `
    <div class="view-head"><h1>Earnings-call intelligence</h1><span class="crumb">${S.calls.length} companies · ${S.periods[0]}–${S.as_of} · model-extracted from free transcripts</span></div>
    <div class="view-sub">One signal cube, three lenses: <b>Journey</b> walks the chain L1→L3 now · <b>Cycle</b> reads each signal over time · <b>Divergence</b> surfaces tensions & turning points.</div>
    <div class="mkbar"><div class="seggrp"><span class="seglbl">Lens</span>${tabs}</div></div>
    ${body}
    ${sigMethodology()}`;
  main.querySelectorAll('[data-sv]').forEach(b => b.onclick = () => { STATE.sigView = b.dataset.sv; render(); });
  main.querySelectorAll('[data-co]').forEach(b => b.onclick = () => { STATE.coView = b.dataset.co; render(); });
  main.querySelectorAll('[data-goto]').forEach(b => b.onclick = () => { STATE.sigView = 'topics'; STATE.topicPin = b.dataset.goto; STATE.inspScroll = 0; render(); });
  main.querySelectorAll('[data-tdrill]').forEach(b => b.onclick = () => { topicPlayStop(); STATE.topicDrill = b.dataset.tdrill || null; STATE.topicPin = null; render(); });
  main.querySelectorAll('[data-topn]').forEach(sl => sl.oninput = () => {
    STATE.topicTopN = +sl.value;
    const bi = topicBubbleItems(SIGNALS.topics, SIGNALS), v = main.querySelector('.topn-val');
    if (v) v.innerHTML = `<b>${bi.items.length}</b> / ${bi.total} topics`;
    const el = main.querySelector('#topicchart'), ex = el && echarts.getInstanceByDom(el); if (ex) ex.dispose();
    sigTopicsChart(SIGNALS);
  });
  main.querySelectorAll('[data-sm]').forEach(b => b.onclick = () => { STATE.sigMetric = b.dataset.sm; render(); });
  main.querySelectorAll('[data-tl]').forEach(b => b.onclick = () => {
    topicPlayStop();
    const k = b.dataset.tl;
    if (k === 'all') { STATE.topicLayers = []; }
    else { const s = new Set(STATE.topicLayers || []); s.has(k) ? s.delete(k) : s.add(k); STATE.topicLayers = [...s]; }
    render();
  });
  main.querySelectorAll('[data-tq]').forEach(b => b.onclick = () => { topicPlayStop(); STATE.topicQ = +b.dataset.tq; render(); });
  main.querySelectorAll('[data-tplay]').forEach(b => b.onclick = () => topicPlayToggle());
  main.querySelectorAll('[data-tlabels]').forEach(b => b.onclick = () => { STATE.topicLabels = b.dataset.tlabels; render(); });
  main.querySelectorAll('[data-tseg]').forEach(b => b.onclick = () => { topicPlayStop(); STATE.topicSeg = b.dataset.tseg; render(); });
  main.querySelectorAll('[data-tctl]').forEach(b => b.onclick = () => { STATE.topicCtlOpen = STATE.topicCtlOpen === false; render(); });
  const cs = main.querySelector('#cosearch');
  if (cs) {
    const dd = main.querySelector('#cosearch_dd'), T = SIGNALS.topics;
    let acts = [], active = -1;   // suggestion actions (in display order) + keyboard-highlighted index
    const setActive = i => { active = i; dd.querySelectorAll('[data-idx]').forEach(el => el.classList.toggle('active', +el.dataset.idx === i)); };
    const choose = i => {
      const a = acts[i]; if (!a) return; cs.value = ''; dd.style.display = 'none';
      if (a.kind === 'topic') { STATE.topicLock = a.id; STATE.topicPin = a.id; STATE.inspScroll = 0; }   // lock the bubble + open panel
      else { const s = new Set(STATE.topicLayers || []); s.add(a.code); STATE.topicLayers = [...s]; topicPlayStop(); }   // add filter
      render();
    };
    cs.oninput = () => {
      const q = cs.value.trim().toLowerCase(); acts = []; active = -1;
      if (!q) { dd.style.display = 'none'; dd.innerHTML = ''; return; }
      const sel = STATE.topicLayers || [];
      const tHits = (T.items || []).filter(it => (it.label + ' ' + it.id + ' ' + ((TOPIC_KW[it.id] || []).join(' '))).toLowerCase().includes(q)).slice(0, 8);
      const cHits = topicCos().filter(c => !sel.includes(c.ticker) && (c.name + ' ' + c.ticker + ' ' + c.layer + ' ' + c.sublayer).toLowerCase().includes(q)).slice(0, 5);
      const layEntries = [['L0', 'L0 · Distribution'], ['L1', 'L1 · Foundry'], ['L2', 'L2 · Equipment'], ['L3', 'L3 · Components'], ['3.1', 'Analog / MCU'], ['3.2', 'Logic / GPU'], ['3.4', 'Memory']];
      const lHits = layEntries.filter(([code, lab]) => !sel.includes(code) && (code + ' ' + lab).toLowerCase().includes(q)).slice(0, 5);
      let html = '';
      if (tHits.length) { html += `<div class="sdh">Topics — open</div>`; tHits.forEach(it => { const i = acts.push({ kind: 'topic', id: it.id }) - 1; html += `<div class="cosearch-item" data-idx="${i}"><span class="tdot" style="background:${favColor((topicLLMFav(it.id, T) || {}).net) || (T.categories.find(c => c.id === it.cat) || {}).color}"></span>${it.label}</div>`; }); }
      if (cHits.length) { html += `<div class="sdh">Companies — filter</div>`; cHits.forEach(c => { const i = acts.push({ kind: 'filter', code: c.ticker }) - 1; html += `<div class="cosearch-item" data-idx="${i}"><span class="lyr-dot" style="background:${LAYER_COLORS[c.layer]}"></span>${c.name} <span class="dim">${c.layer} · ${c.sublayer}</span></div>`; }); }
      if (lHits.length) { html += `<div class="sdh">Layers — filter</div>`; lHits.forEach(([code, lab]) => { const i = acts.push({ kind: 'filter', code }) - 1; html += `<div class="cosearch-item" data-idx="${i}"><span class="lyr-dot" style="background:${LAYER_COLORS[code] || LAYER_COLORS['L' + code[0]] || '#94a3b8'}"></span>${lab}</div>`; }); }
      dd.innerHTML = html || '<div class="cosearch-item dim">no match</div>';
      dd.style.display = 'block';
      dd.querySelectorAll('[data-idx]').forEach(el => { el.onmousedown = e => { e.preventDefault(); choose(+el.dataset.idx); }; el.onmouseenter = () => setActive(+el.dataset.idx); });
    };
    cs.onkeydown = e => {
      if (dd.style.display === 'none' || !acts.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(Math.min(acts.length - 1, active + 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(Math.max(0, active - 1)); }
      else if (e.key === 'Enter') { e.preventDefault(); choose(active >= 0 ? active : 0); }
      else if (e.key === 'Escape') { dd.style.display = 'none'; }
    };
    cs.onblur = () => setTimeout(() => { if (dd) dd.style.display = 'none'; }, 150);
  }
  disposeCharts();
  sparks.forEach(s => {
    const ch = mk(s.id); if (!ch) return;
    const data = s.trend.map(x => x[1]), min = s.range ? s.range[0] : -2, max = s.range ? s.range[1] : 2;
    const up = data[data.length - 1] >= data[0], col = up ? '#16a34a' : '#dc2626';
    ch.setOption({ animation: false, grid: { left: 2, right: 2, top: 4, bottom: 4 },
      xAxis: { type: 'category', show: false, data: s.trend.map(x => x[0]) }, yAxis: { type: 'value', show: false, min, max },
      tooltip: { trigger: 'axis', formatter: p => p.map(x => `${x.axisValue}: ${s.pct ? Math.round(x.data * 100) + '%' : (x.data > 0 ? '+' : '') + x.data}`).join('') },
      series: [{ type: 'line', data, smooth: true, symbol: 'none', lineStyle: { width: 2, color: col }, areaStyle: { opacity: 0.15, color: col } }] });
  });
  if (STATE.sigView === 'flow') sigFlowChart(S);
  if (STATE.sigView === 'topics') sigTopicsChart(S);
  if (STATE.sigView === 'tree') sigTreeChart(S);
}

/* Lens — Topic trends: a HOT-vs-MOMENTUM map. One bubble per topic, for a chosen as-of quarter.
   x = total mentions (how hot) · y = momentum vs trailing-4Q avg · colour = category · shape = stance · size = heat. */
function topicTrailAvg(series, i) { const w = series.slice(Math.max(0, i - 4), i); return w.length ? w.reduce((a, b) => a + b, 0) / w.length : 0; }
function topicMomentum(series, i, k) { const w = series.slice(Math.max(0, i - 4), i); if (!w.length) return null; const base = w.reduce((a, b) => a + b, 0) / w.length; return (series[i] - base) / (base + (k == null ? 20 : k)); }
function momSmooth(T) { return T && T.mom_smooth != null ? T.mom_smooth : 20; }
const STANCE_TAG = { excited: '<span class="stag exc">excited</span>', concern: '<span class="stag con">concern</span>', mixed: '<span class="stag mix">mixed</span>' };
const STANCE_SYMBOL = { excited: 'circle', concern: 'diamond', mixed: 'roundRect' };
function _hex2rgb(h) { h = (h || '#000').replace('#', ''); return [parseInt(h.slice(0, 2), 16) || 0, parseInt(h.slice(2, 4), 16) || 0, parseInt(h.slice(4, 6), 16) || 0]; }
function cLight(hex, a) { const c = _hex2rgb(hex); return `rgb(${c.map(v => Math.round(v + (255 - v) * a)).join(',')})`; }
function cRgba(hex, a) { const c = _hex2rgb(hex); return `rgba(${c[0]},${c[1]},${c[2]},${a})`; }
function sparkSVG(vals, color, w, h) {  // tiny inline trend line for tooltips
  vals = (vals || []).filter(v => v != null); if (vals.length < 2) return '';
  const mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1, n = vals.length;
  const X = i => (i / (n - 1) * (w - 4) + 2), Y = v => (h - 2 - ((v - mn) / rng) * (h - 4));
  const pts = vals.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
  return `<svg width="${w}" height="${h}" style="vertical-align:middle"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${X(n - 1).toFixed(1)}" cy="${Y(vals[n - 1]).toFixed(1)}" r="2.2" fill="${color}"/></svg>`;
}
function wrapLabel(s, max) {  // wrap a long label into <=max-char lines so it takes less horizontal room
  const words = String(s).split(' '), lines = []; let cur = '';
  for (const w of words) { if (!cur) cur = w; else if ((cur + ' ' + w).length <= max) cur += ' ' + w; else { lines.push(cur); cur = w; } }
  if (cur) lines.push(cur);
  return lines.join('\n');
}
/* key-concept quotes pulled from the call themes (used by the inspector's Key concepts section) */
function topicQuotes(it, S, maxN) {
  const kw = TOPIC_KW[it.id] || [it.label.toLowerCase().split(' ')[0]];
  const quotes = [];
  (S.calls || []).forEach(c => (c.themes || []).forEach(t => { if (kw.some(k => (t[0] || '').toLowerCase().includes(k))) quotes.push({ co: c.name, txt: t[0], dir: t[1] }); }));
  if (!quotes.length) return '';
  return quotes.slice(0, maxN || 8).map(x => `<div class="tq"><span class="tqco">${x.co}</span> <span class="tqdir ${x.dir}">${x.dir === 'up' ? '▲' : x.dir === 'down' ? '▼' : '◆'}</span> ${x.txt}</div>`).join('');
}
/* focus a topic from search: pin it into the inspector */
function focusTopic(id) { STATE.topicPin = id; render(); }
/* aggregate net sentiment (-1..+1) for a topic in a given segment, over the selected companies */
function topicSent(it, S, seg, q) {
  const sd = (S.topics && S.topics.sentiment) || {}; let sum = 0, cnt = 0;
  topicSelCos().forEach(c => { const arr = ((sd[c.ticker] || {})[it.id] || {})[seg]; const v = arr ? arr[q] : null; if (v != null) { sum += v; cnt++; } });
  return cnt ? sum / cnt : null;
}
function sentLabel(v) { if (v == null) return { t: '—', c: '#94a3b8' }; if (v >= 0.2) return { t: 'Positive', c: '#16a34a' }; if (v <= -0.2) return { t: 'Negative', c: '#dc2626' }; return { t: 'Neutral', c: '#d97706' }; }
const TOPIC_LAYERS = [['all', 'All layers'], ['L0', 'L0 · Distribution'], ['L1', 'L1 · Foundry'], ['L2', 'L2 · Equipment'], ['L3', 'L3 · Components']];
const TOPIC_KW = { ai_demand: ['ai', 'data center', 'data-center', 'accelerator'], agentic_ai: ['agentic', 'inference'], sovereign_ai: ['sovereign'],
  auto: ['auto'], industrial: ['industrial', 'broad-market', 'broad market', 'mass-market', 'mass market'], consumer: ['smartphone', ' pc', 'consumer'],
  hbm: ['hbm', 'high-bandwidth'], mem_pricing: ['pricing', 'asp', 'price'], mem_strategic: ['strategic', 'supply agreement', 'sca', 'long-term', '5-yr', '5-year'],
  capex: ['capex', 'wfe'], capacity: ['capacity', 'sold out', 'sold-out', 'tight'], leadtimes: ['lead time', 'lead-time', 'lead times'],
  cowos: ['cowos', 'packaging'], nodes: ['n2', 'a16', '2nm', 'node'], highna: ['high-na', 'euv'], hbm4: ['hbm4'], nand_qlc: ['nand', 'qlc'],
  china: ['china'], tariffs: ['tariff', 'trade'], inventory: ['inventory', 'double-order', 'double order', 'channel'] };
/* selected supply-chain layers / sub-layers (multi-select). [] = all. */
function topicLayerSel() { return STATE.topicLayers || []; }
/* companies matching the current selection (by layer OR sub-layer code); [] = all companies */
function topicCos() { return (SIGNALS && SIGNALS.topics && SIGNALS.topics.companies) || (SIGNALS && SIGNALS.companies) || []; }
function topicSelCos() { const s = topicLayerSel(), cos = topicCos(); return s.length ? cos.filter(c => s.includes(c.layer) || s.includes(c.sublayer) || s.includes(c.ticker)) : cos; }
function topicItemsForLayer(T) {
  const s = topicLayerSel(); if (!s.length) return T.items;
  const pc = (SIGNALS && SIGNALS.topics && SIGNALS.topics.per_company) || {}, seg = topicSeg(), tks = topicSelCos().map(c => c.ticker);
  return T.items.filter(it => tks.some(tk => { const arr = ((pc[tk] || {})[it.id] || {})[seg]; return arr && arr.some(v => v > 0); }));  // topics the selected cos raise (in this segment)
}
function topicSeg() { return STATE.topicSeg || 'all'; }
/* recompute a topic's mentions/company + breadth for the chosen SPEECH SEGMENT and selected companies */
function topicEffSeries(it, S) {
  const sel = topicLayerSel(), seg = topicSeg();
  if (!sel.length && seg === 'all') return { ser: it.series || [], brd: it.breadth || [] };  // fast path
  const pc = (S.topics && S.topics.per_company) || {}, tks = topicSelCos().map(c => c.ticker);
  const n = (it.series || []).length, ser = [], brd = [];
  for (let i = 0; i < n; i++) {
    let sum = 0, cnt = 0, have = 0;
    tks.forEach(tk => { const arr = ((pc[tk] || {})[it.id] || {})[seg]; if (arr) { cnt++; sum += arr[i] || 0; if ((arr[i] || 0) >= 1) have++; } });
    ser.push(cnt ? +(sum / cnt).toFixed(1) : 0); brd.push(have);
  }
  return { ser, brd };
}
function topicAsOf(T) { const last = T.periods.length - 1, pf = T.plot_from || 0; let q = STATE.topicQ; if (q == null || q < pf || q > last) q = last; return q; }
function topicPlayStop() { if (TOPIC_PLAY) { clearInterval(TOPIC_PLAY); TOPIC_PLAY = null; } }
function topicPlayToggle() {
  if (TOPIC_PLAY) { topicPlayStop(); render(); return; }
  TOPIC_PLAY = setInterval(() => {
    const T = SIGNALS && SIGNALS.topics; if (!T) { topicPlayStop(); return; }
    const pf = T.plot_from || 0, last = T.periods.length - 1, q = topicAsOf(T);
    STATE.topicQ = q >= last ? pf : q + 1; render();
  }, 1200);
  render();
}

/* ── Topic TAXONOMY DRILL-DOWN ─────────────────────────────────────────────────────
   Variable-depth tree (topics.tree.nodes + leaf items' .parent). The bubble chart shows the
   CHILDREN of the current drill node (STATE.topicDrill, null = the L1 roots): internal nodes
   render as aggregated, drillable group bubbles; leaves render as the usual topic bubbles.
   Group "heat" = MEAN of its descendant leaves' per-company avg (same scale as a leaf), so a
   group and a leaf are comparable on one axis. */
const TREE_ROOT_COLOR = { products: '#b07aa1', endmkt: '#f28e2b', ops: '#76b7b2', commercial: '#4e79a7', macro: '#e15759' };
/* primary topic map encodings: SHAPE = domain (the L1 root), COLOUR = sentiment (green optimistic → red cautious). */
const DOMAIN_SHAPE = { products: 'circle', endmkt: 'triangle', ops: 'roundRect', commercial: 'diamond', macro: 'pin' };
function topicShape(id, T) { return DOMAIN_SHAPE[topicRootOf(id, T)] || 'circle'; }
function sentDotColor(v) {  // diverging optimistic↔cautious scale
  if (v == null) return '#cbd5e1';
  if (v >= 0.35) return '#15803d'; if (v >= 0.12) return '#22c55e';
  if (v > -0.12) return '#f59e0b'; if (v > -0.35) return '#ef4444'; return '#b91c1c';
}
function shapeSVG(sym, c) {  // tiny inline glyph for the legend (matches the bubble symbols)
  c = c || '#64748b';
  const g = { circle: '<circle cx="6" cy="6" r="5"/>', triangle: '<polygon points="6,1 11,11 1,11"/>',
    diamond: '<polygon points="6,1 11,6 6,11 1,6"/>', roundRect: '<rect x="1" y="1" width="10" height="10" rx="3"/>',
    pin: '<path d="M6 0C9 0 11 2 11 5C11 8.5 6 13 6 13C6 13 1 8.5 1 5C1 2 3 0 6 0Z"/>' }[sym] || '<circle cx="6" cy="6" r="5"/>';
  return `<svg width="13" height="13" viewBox="0 0 12 13" style="vertical-align:-2px" fill="${c}">${g}</svg>`;
}
function topicTree(T) { T = T || (SIGNALS && SIGNALS.topics) || {}; return (T.tree && T.tree.nodes) ? T.tree : null; }
function topicRootOf(id, T) {  // walk parent pointers to the L1 root id (handles node ids AND leaf-parented leaves)
  T = T || SIGNALS.topics; const tr = topicTree(T); if (!tr) return null;
  const items = T.items || [];
  const parentOf = i => tr.nodes[i] ? tr.nodes[i].parent : ((items.find(x => x.id === i) || {}).parent || null);
  let cur = id, pid = parentOf(id);
  while (pid) { cur = pid; pid = parentOf(pid); }
  return cur;
}
function topicNodeColor(id, T) { return TREE_ROOT_COLOR[topicRootOf(id, T)] || '#64748b'; }
function topicChildNodes(parentId, T) {  // direct children of parentId (null = roots): inner node ids + leaf items
  const tr = topicTree(T), pid = parentId || null;
  const innerIds = tr ? Object.keys(tr.nodes).filter(n => (tr.nodes[n].parent || null) === pid) : [];
  const leafItems = (T.items || []).filter(it => (it.parent || null) === pid);
  return { innerIds, leafItems };
}
function topicDescLeaves(nodeId, T) {  // all leaf ids beneath an inner node (recursive)
  const { innerIds, leafItems } = topicChildNodes(nodeId, T);
  let out = leafItems.map(it => it.id);
  innerIds.forEach(n => { out = out.concat(topicDescLeaves(n, T)); });
  return out;
}
function topicGroupItem(nodeId, T, S) {  // aggregate an inner node into a pseudo-topic-item for the chart
  const node = topicTree(T).nodes[nodeId], leafIds = topicDescLeaves(nodeId, T);
  const allow = new Set(topicItemsForLayer(T).map(it => it.id));   // respect the layer filter
  const leaves = (T.items || []).filter(it => leafIds.indexOf(it.id) >= 0 && allow.has(it.id));
  const effs = leaves.map(it => topicEffSeries(it, S)), n = (T.periods || []).length, ser = [], brd = [];
  for (let i = 0; i < n; i++) { const vs = effs.map(e => e.ser[i] || 0); ser.push(effs.length ? +Math.max(...vs).toFixed(1) : 0); brd.push(Math.max(0, ...effs.map(e => e.brd[i] || 0))); }   // group heat = its hottest child (so the hottest theme leads)
  return { id: nodeId, label: node.label, isGroup: true, childCount: leaves.length, parent: node.parent, leafIds: leaves.map(it => it.id), color: topicNodeColor(nodeId, T), series: ser, breadth: brd, who: '', note: leaves.length + ' topics', stance: 'mixed', facet: node.facet };
}
function topicChildDisplay(parentId, T, S) {  // the bubbles to show at this drill level (groups + leaves)
  const { innerIds, leafItems } = topicChildNodes(parentId, T);
  const allow = new Set(topicItemsForLayer(T).map(it => it.id));
  const groups = innerIds.map(n => topicGroupItem(n, T, S)).filter(g => g.childCount > 0);
  const leaves = leafItems.filter(it => allow.has(it.id)).map(it => { const e = topicEffSeries(it, S); return Object.assign({}, it, { series: e.ser, breadth: e.brd, color: topicNodeColor(it.id, T), isGroup: false }); });
  return groups.concat(leaves);
}
function topicDisplayItems(T, S) {  // start at L2 (children of every L1 root); drill a group → its L3
  if (!topicTree(T)) { return topicItemsForLayer(T).map(it => { const e = topicEffSeries(it, S); return Object.assign({}, it, { series: e.ser, breadth: e.brd, color: (T.categories.find(c => c.id === it.cat) || {}).color, isGroup: false }); }); }
  const drill = STATE.topicDrill || null;
  if (drill) return topicChildDisplay(drill, T, S);
  const tr = topicTree(T), roots = Object.keys(tr.nodes).filter(n => !tr.nodes[n].parent);   // L2 overview
  let out = []; roots.forEach(r => { out = out.concat(topicChildDisplay(r, T, S)); });
  return out;
}
function topicCrumb(T) {  // breadcrumb: All ▸ Products ▸ Memory  (each clickable to jump up)
  if (!topicTree(T)) return '';
  const nodes = topicTree(T).nodes, chain = []; let id = STATE.topicDrill || null;
  while (id) { chain.unshift({ id, label: nodes[id].label, color: topicNodeColor(id, T) }); id = nodes[id].parent; }
  const root = `<button class="crumb ${!chain.length ? 'on' : ''}" data-tdrill="">All domains</button>`;
  const rest = chain.map((c, i) => `<span class="crumb-sep">▸</span><button class="crumb ${i === chain.length - 1 ? 'on' : ''}" data-tdrill="${c.id}"><span class="lyr-dot" style="background:${c.color}"></span>${c.label}</button>`).join('');
  return `<div class="topic-crumb">${root}${rest}</div>`;
}
/* group inspector (right drawer when hovering/at a group): its children as a clickable drill list */
function topicGroupInspectorHTML(g, S) {
  const T = S.topics, q = topicAsOf(T), kids = topicChildDisplay(g.id, T, S);
  const pct = m => (m >= 0 ? '+' : '') + Math.round((m || 0) * 100) + '%';
  const rows = kids.slice().sort((a, b) => b.series[q] - a.series[q]).map(k => {
    const m = topicMomentum(k.series, q, momSmooth(T)), act = k.isGroup ? `data-tdrill="${k.id}"` : `data-goto="${k.id}"`;
    return `<div class="grp-row" ${act}><span class="tdot" style="background:${k.color}"></span><span class="grp-lab">${k.label}${k.isGroup ? ` <span class="dim">▸ ${k.childCount}</span>` : ''}</span><span class="ov-x">${(+k.series[q]).toFixed(1)}×</span><span class="tmom ${m >= 0 ? 'up' : 'down'}">${pct(m)}</span></div>`;
  }).join('');
  return `<div class="insp"><div class="insp-banner"><span class="tddot" style="background:${g.color}"></span><b>${g.label}</b><button class="unpin" data-gclose="1" title="Close">✕</button>
      <div class="insp-sub">${g.childCount} topics · click to drill in</div></div>
    <div class="insp-sec"><h5>Inside ${g.label} <span class="dim">— heat × momentum</span></h5>${rows}</div>
    <div class="dim" style="font-size:11px;margin-top:8px">Click a row or a bubble: ▸ rows drill into a sub-group; the rest open a topic's full outlook.</div></div>`;
}
function renderGroupInspector(g, S) {
  const dp = document.getElementById('topicdetail'); if (!dp) return;
  dp.innerHTML = topicGroupInspectorHTML(g, S);
  dp.querySelectorAll('[data-gclose]').forEach(b => b.onclick = () => { dp.innerHTML = ''; });
  dp.querySelectorAll('[data-tdrill]').forEach(b => b.onclick = () => { STATE.topicDrill = b.dataset.tdrill || null; STATE.topicPin = null; render(); });
  dp.querySelectorAll('[data-goto]').forEach(b => b.onclick = () => { STATE.topicPin = b.dataset.goto; STATE.inspScroll = 0; render(); });
}

/* ── Topic INSPECTOR: pinned right-panel detail = stats charts + forward outlook ──────
   Hover a bubble = lightweight tooltip; click = open this full inspector pop-up (right drawer).
   Built to scale: the per-company list is a distribution headline + collapsible layer groups. */
function toutDir(d) { return ({ improving: ['▲', 'Improving', 'up'], stabilizing: ['→', 'Stabilizing', 'mix'], deteriorating: ['▼', 'Deteriorating', 'down'], mixed: ['◆', 'Mixed', 'mix'] })[d] || ['◆', d || '—', 'mix']; }
function sentCell(v) { if (v == null) return { bg: '#f3f5f8', txt: '' }; const t = Math.max(-1, Math.min(1, v)); const col = t >= 0 ? '#16a34a' : '#dc2626'; return { bg: cLight(col, 1 - Math.abs(t) * 0.82), txt: (v >= 0 ? '+' : '') + v.toFixed(1) }; }
function topicOutlookFor(S, id) { return ((S.topics && S.topics.outlook) || {})[id] || null; }
/* which topic's pop-up is open — a string id when the user clicked a bubble, else null (closed). */
function topicPinId(S) { return (typeof STATE.topicPin === 'string') ? STATE.topicPin : null; }
function topicCoName(tk) { const c = topicCos().find(x => x.ticker === tk); return c ? c.name : tk; }
function topicCoSub(tk) { const c = topicCos().find(x => x.ticker === tk); return c ? (c.sublayer || c.layer) : ''; }
/* unified per-company record for a topic: mentions · trajectory · stance (LLM if judged, else lexicon) · evidence */
function topicCompanyRecords(it, S, q) {
  const id = it.id, seg = topicSeg(), pc = (S.topics.per_company) || {}, sd = (S.topics.sentiment) || {}, O = topicOutlookFor(S, id);
  const allow = (O && O.companies) ? new Set(Object.keys(O.companies)) : null;   // outlook topics: only the LLM-validated companies
  const recs = [];
  topicSelCos().forEach(co => {
    const tk = co.ticker;
    if (allow && !allow.has(tk)) return;   // drop keyword false-positives / tangential mentions for validated topics
    const carr = ((pc[tk] || {})[id] || {})[seg];
    let traj = (O && O.matrix && O.matrix.companies[tk]) ? O.matrix.companies[tk].traj : null;
    if (!traj) { const s = ((sd[tk] || {})[id] || {}); traj = Array.isArray(s.all) ? s.all : (Array.isArray(s[seg]) ? s[seg] : null); }
    const everMention = carr ? carr.some(v => v > 0) : (traj && traj.some(v => v != null));
    if (!everMention) return;
    const latest = traj ? traj.slice(0, q + 1).reverse().find(x => x != null) : null;
    let stance = null, point = null;
    if (O && O.companies && O.companies[tk]) { stance = O.companies[tk].stance; point = O.companies[tk].point; }
    if (!stance) stance = latest == null ? 'neutral' : (latest >= 0.2 ? 'positive' : latest <= -0.2 ? 'negative' : 'neutral');
    recs.push({ tk, name: topicCoName(tk), layer: co.layer, sub: co.sublayer || co.layer, mentions: carr ? (carr[q] || 0) : 0, traj, stance, point, latest: latest == null ? null : latest, ev: (O && O.evidence && O.evidence[tk]) || [] });
  });
  return recs;
}
/* the top-of-panel EXECUTIVE SUMMARY: direction + headline + summary + highlights / lowlights.
   Outlook topics get the LLM forward call (drivers split into highlights vs lowlights+risks);
   non-outlook topics get a generated overview from counts + lexicon sentiment. */
function toutExecHTML(it, S, q) {
  const O = topicOutlookFor(S, it.id), T = S.topics;
  const eff = topicEffSeries(it, S), ser = eff.ser, brd = eff.brd;
  const mom = topicMomentum(ser, q, momSmooth(T)), brdNow = (brd || [])[q], denom = topicSelCos().length;
  const heats = topicItemsForLayer(T).map(x => topicEffSeries(x, S).ser[q]).sort((a, b) => a - b), med = heats[Math.floor(heats.length / 2)];
  const quad = ser[q] >= med ? (mom >= 0 ? 'Hot & accelerating' : 'Still hot · losing steam') : (mom >= 0 ? 'Emerging' : 'Fading');
  if (O) {
    const d = toutDir((O.outlook || {}).direction);
    return `<div class="insp-sec insp-exec">
      <div class="insp-dir ${d[2]}"><span class="tout-arrow">${d[0]}</span><span class="tout-dirlab">${d[1]}</span><span class="tout-conf">confidence ${(O.outlook || {}).confidence || '—'} · ${quad}</span></div>
      <div class="insp-headline">${(O.outlook || {}).headline || ''}</div>
      <div class="tout-summary">${(O.outlook || {}).summary || ''}</div></div>`;
  }
  // LLM-derived INSIGHT first (we now have per-company favorability for ~every topic): lead with a
  // direct-English read + a concrete management reason, then the statistics underneath.
  const lrows = topicLLMRows(it.id, T), agg = topicLLMFav(it.id, T);
  if (lrows.length && agg) {
    const posL = lrows.filter(r => r.fav === 'bullish').length, negL = lrows.filter(r => r.fav === 'bearish').length;
    const net = agg.net, dir = net >= 0.2 ? ['▲', 'Bullish', 'up', '#16a34a'] : net <= -0.2 ? ['▼', 'Bearish', 'down', '#dc2626'] : ['◆', 'Mixed', 'mix', '#d97706'];
    const wantSide = net < -0.05 ? 'bearish' : 'bullish';
    const side = lrows.filter(r => r.fav === wantSide); const pick = (side.length ? side : lrows).slice().sort((a, b) => (b.why || '').length - (a.why || '').length)[0] || lrows[0];
    return `<div class="insp-sec insp-exec">
      <div class="insp-dir ${dir[2]}"><span class="tout-arrow">${dir[0]}</span><span class="tout-dirlab">${dir[1]}</span><span class="tout-conf">${posL} bullish · ${negL} cautious of ${lrows.length} · ${quad}</span></div>
      <div class="insp-headline">${it.label} — management leans <b style="color:${dir[3]}">${dir[1].toLowerCase()}</b> this quarter</div>
      <div class="tout-summary"><b>${pick.co}:</b> ${pick.why || ''}</div>
      <div class="dim" style="font-size:11px;margin-top:6px">Raised by <b>${brdNow} of ${denom}</b> · ~${(+ser[q]).toFixed(1)}× per call · momentum ${(mom >= 0 ? '+' : '') + Math.round(mom * 100)}% vs 4Q norm. Per-company stance below.</div></div>`;
  }
  const recs = topicCompanyRecords(it, S, q);
  const top = recs.slice().sort((a, b) => b.mentions - a.mentions).slice(0, 3).map(r => r.name).join(', ');
  const pos = recs.filter(r => r.stance === 'positive').length, neg = recs.filter(r => r.stance === 'negative').length;
  return `<div class="insp-sec insp-exec">
    <div class="insp-headline">${it.label} — <span style="text-transform:lowercase">${quad}</span></div>
    <div class="tout-summary">Raised by <b>${brdNow} of ${denom}</b> companies (~${(+ser[q]).toFixed(1)}× per call), momentum <b style="color:${mom >= 0 ? '#16a34a' : '#dc2626'}">${(mom >= 0 ? '+' : '') + Math.round(mom * 100)}%</b> vs its 4-quarter norm. Stance leans <b style="color:#16a34a">${pos} positive</b> / <b style="color:#dc2626">${neg} cautious</b>. Most active: <b>${top || '—'}</b>.</div></div>`;
}
function stanceBadgeMini(s) { const m = ({ positive: ['Pos', '#16a34a'], neutral: ['Neu', '#d97706'], negative: ['Neg', '#dc2626'] })[s] || ['—', '#94a3b8']; return `<span class="smx-badge" style="color:${m[1]};border-color:${m[1]}">${m[0]}</span>`; }
const SUBLABEL_INSP = { '0': 'Distribution', '1.1': 'Foundry', '2.1': 'Equipment', '3.1': 'Analog / MCU', '3.2': 'Logic / GPU', '3.3': 'Discrete / power', '3.4': 'Memory' };
/* the scale-safe company section: distribution headline + top movers + collapsible layer groups */
function toutCompaniesHTML(it, S, q) {
  const recs = topicCompanyRecords(it, S, q); if (!recs.length) return '';
  const O = topicOutlookFor(S, it.id), P = (S.topics.periods) || [];
  const pos = recs.filter(r => r.stance === 'positive').length, neg = recs.filter(r => r.stance === 'negative').length, tot = recs.length, neu = tot - pos - neg;
  const dist = `<div class="dist-bar"><span style="width:${pos / tot * 100}%;background:#16a34a"></span><span style="width:${neu / tot * 100}%;background:#d97706"></span><span style="width:${neg / tot * 100}%;background:#dc2626"></span></div>
    <div class="dist-leg"><span style="color:#16a34a">●</span> ${pos} Positive · <span style="color:#d97706">●</span> ${neu} Neutral · <span style="color:#dc2626">●</span> ${neg} Negative</div>`;
  const dots = recs.map(r => { const v = r.latest; if (v == null) return ''; const left = ((Math.max(-1, Math.min(1, v)) + 1) / 2 * 100).toFixed(1), col = v >= 0.2 ? '#16a34a' : v <= -0.2 ? '#dc2626' : '#d97706'; return `<span class="cons-dot" style="left:${left}%;background:${col}" title="${r.name} ${v >= 0 ? '+' : ''}${v.toFixed(1)}"></span>`; }).join('');
  const cons = `<div class="cons"><div class="cons-axis"><span>neg</span><span>neutral</span><span>pos</span></div><div class="cons-track"><span class="cons-mid"></span>${dots}</div>${O ? `<div class="cons-note"><b>Consensus: ${O.consensus || '—'}</b> — ${O.consensus_note || ''}</div>` : ''}</div>`;
  const delta = r => { const t = (r.traj || []).filter(x => x != null); return t.length >= 2 ? t[t.length - 1] - t[0] : 0; };
  const movers = recs.slice().filter(r => (r.traj || []).filter(x => x != null).length >= 2).sort((a, b) => Math.abs(delta(b)) - Math.abs(delta(a))).slice(0, 3);
  const moversHTML = movers.length ? `<div class="topmovers"><span class="dim" style="font-size:10px">Biggest moves:</span>${movers.map(r => { const dv = delta(r), c = dv >= 0 ? '#16a34a' : '#dc2626'; return `<span class="mover"><span class="lyr-dot" style="background:${LAYER_COLORS[r.layer] || '#94a3b8'}"></span>${r.name} <b style="color:${c}">${dv >= 0 ? '▲' : '▼'}${Math.abs(dv).toFixed(1)}</b></span>`; }).join('')}</div>` : '';
  const SR = { positive: 1, neutral: 0, negative: -1 };
  const byGrp = {}; recs.forEach(r => { (byGrp[r.sub] = byGrp[r.sub] || []).push(r); });
  const cellRow = r => {
    const cells = P.map((p, i) => { const v = (r.traj || [])[i]; if (v == null) return `<span class="smx-c miss" title="${qLabel(p)}: not mentioned this quarter"></span>`; const sc = sentCell(v); return `<span class="smx-c" style="background:${sc.bg}" title="${qLabel(p)}: ${sc.txt}">${sc.txt}</span>`; }).join('');
    const ev = (r.ev || []).map(e => `• [${(e.seg || '').toUpperCase()}] ${e.t}`).join('\n').replace(/"/g, '&quot;');
    return `<div class="smx-row" title="${ev}"><span class="smx-co"><span class="lyr-dot" style="background:${LAYER_COLORS[r.layer] || '#94a3b8'}"></span>${r.name}</span>${cells}<span class="smx-st">${stanceBadgeMini(r.stance)}<span class="smx-pt">${r.point || ''}</span></span></div>`;
  };
  const groups = Object.keys(byGrp).sort().map(g => {
    const rs = byGrp[g], open = STATE.topicGroups.has(g);
    // layer header is the SAME row format as the company rows: a per-quarter AVERAGE row (aligned columns, same cells)
    const qavg = P.map((_, i) => { const vs = rs.map(r => (r.traj || [])[i]).filter(v => v != null); return vs.length ? vs.reduce((a, b) => a + b, 0) / vs.length : null; });
    const avgCells = qavg.map((v, i) => v == null ? `<span class="smx-c miss" title="${qLabel(P[i])}: —"></span>` : `<span class="smx-c" style="background:${sentCell(v).bg}" title="${qLabel(P[i])}: avg ${sentCell(v).txt}">${sentCell(v).txt}</span>`).join('');
    const vals = qavg.filter(v => v != null), savg = vals.length ? vals[vals.length - 1] : null;   // label = latest quarter's layer avg
    const al = savg == null ? ['→', 'n/a', '#94a3b8'] : savg >= 0.2 ? ['▲', 'Positive', '#16a34a'] : savg <= -0.2 ? ['▼', 'Negative', '#dc2626'] : ['→', 'Neutral', '#d97706'];
    const avgTxt = savg == null ? '—' : (savg >= 0 ? '+' : '') + savg.toFixed(1);
    const hdr = `<div class="lgrp-h smx-row" data-lgrp="${g}"><span class="smx-co"><span class="lgrp-tw">${open ? '▾' : '▸'}</span><span class="lyr-dot" style="background:${LAYER_COLORS['L' + String(g)[0]] || '#94a3b8'}"></span><b>${g} ${SUBLABEL_INSP[g] || ''}</b></span>${avgCells}<span class="smx-st lgrp-avg" style="color:${al[2]}"><b>${avgTxt}</b> ${al[0]} ${al[1]} <span class="dim" style="font-weight:400">· ${rs.length} cos</span></span></div>`;
    const body = open ? `<div class="lgrp-body"><div class="smx-row smx-hdr"><span class="smx-co"></span>${P.map(p => `<span class="smx-c">${qLabel(p)}</span>`).join('')}<span class="smx-st">stance · why</span></div>${rs.slice().sort((a, b) => (b.latest || 0) - (a.latest || 0)).map(cellRow).join('')}</div>` : '';
    return `<div class="lgrp">${hdr}${body}</div>`;
  }).join('');
  return `<div class="insp-sec"><h5>Where companies stand <span class="dim">— ${tot} cos · click a layer to expand</span></h5>${dist}${moversHTML}${cons}<div class="lgrps">${groups}</div>
    <div class="dim" style="font-size:10px;margin-top:7px"><span class="hatchkey"></span> = not mentioned that quarter · coloured = sentiment (−1…+1, green positive)</div></div>`;
}
function toutSpeakerHTML(it, S, q) {
  const stance = [['ceo', 'CEO'], ['cfo', 'CFO'], ['q', 'Analyst Q'], ['a', 'Mgmt A']].map(([sg, lab]) => { const v = topicSent(it, S, sg, q), L = sentLabel(v); return `<div class="tdrow"><span class="tdl">${lab}</span><span class="tdspark"></span><span class="tdval" style="color:${L.c}">${L.t}${v != null ? ` <span style="color:#94a3b8;font-weight:400">${v >= 0 ? '+' : ''}${v.toFixed(1)}</span>` : ''}</span></div>`; }).join('');
  return `<div class="insp-sec"><h5>Stance by speaker — how they feel about it</h5>${stance}</div>`;
}
/* detailed highlights / lowlights — rendered BELOW the charts (kept out of the top summary) */
function toutHiloHTML(it, S) {
  const O = topicOutlookFor(S, it.id); if (!O || !(O.drivers || []).length) return '';
  const tag = t => `<span class="drv-tag">${topicCoName(t)}</span>`;
  const ups = (O.drivers || []).filter(x => x.polarity === 'pos');
  const downs = (O.drivers || []).filter(x => x.polarity !== 'pos');
  const hi = ups.map(x => `<div class="hl-item"><span class="hl-mk up">▲</span><div><b>${x.label}</b> <span class="dim">— ${x.detail}</span> ${(x.companies || []).map(tag).join('')}</div></div>`).join('') || '<div class="dim" style="font-size:11px">—</div>';
  const lo = (downs.map(x => `<div class="hl-item"><span class="hl-mk dn">▼</span><div><b>${x.label}</b> <span class="dim">— ${x.detail}</span> ${(x.companies || []).map(tag).join('')}</div></div>`).join('')
    + (O.risks || []).map(r => `<div class="hl-item"><span class="hl-mk warn">⚠</span><div>${r}</div></div>`).join('')) || '<div class="dim" style="font-size:11px">—</div>';
  return `<div class="insp-sec"><h5>Highlights &amp; lowlights <span class="dim">— what's driving it &amp; the risks</span></h5>
    <div class="exec-hl-grid"><div class="hl-col"><h6 class="hl-up">Highlights</h6>${hi}</div><div class="hl-col"><h6 class="hl-dn">Lowlights &amp; risks</h6>${lo}</div></div></div>`;
}
function toutConceptsHTML(it, S) { const qh = topicQuotes(it, S, 6); return qh ? `<div class="insp-sec"><h5>Key concepts from the calls</h5>${qh}</div>` : ''; }
/* LLM company-by-company stance (favorability + why) — works for ANY enriched topic */
function toutLLMReadHTML(it, S) {
  const T = S.topics, rows = topicLLMRows(it.id, T); if (!rows.length) return '';
  const agg = topicLLMFav(it.id, T), c = f => f === 'bullish' ? '#16a34a' : f === 'bearish' ? '#dc2626' : '#d97706';
  const list = rows.map(r => `<div class="llm-row"><span class="llm-co">${r.co}</span><span class="llm-fav" style="color:${c(r.fav)}">${r.fav}</span><span class="llm-why" title="${(r.why || '').replace(/"/g, '&quot;')}">${r.why || ''}</span></div>`).join('');
  return `<div class="insp-sec"><h5>LLM stance — by company <span class="dim">net ${agg.net >= 0 ? '+' : ''}${agg.net.toFixed(2)} · ${rows.length} cos · gpt-5.4-mini</span></h5>${list}</div>`;
}
/* full pinned inspector — works for ANY topic (outlook sections skipped when no synthesis exists) */
function topicInspectorHTML(it, S, q) {
  const T = S.topics, cat = (T.categories || []).find(c => c.id === it.cat) || {};
  const domColor = topicNodeColor(it.id, T), pathStr = (it.path_labels && it.path_labels.length > 1) ? it.path_labels.slice(0, -1).join(' › ') : (cat.label || '');
  const locked = (typeof STATE.topicLock === 'string') && STATE.topicLock === it.id;
  const eff = topicEffSeries(it, S), ser = eff.ser, brd = eff.brd;
  const mom = topicMomentum(ser, q, momSmooth(T)), brdNow = (brd || [])[q], denom = topicSelCos().length;
  const heats = topicItemsForLayer(T).map(x => topicEffSeries(x, S).ser[q]).sort((a, b) => a - b), med = heats[Math.floor(heats.length / 2)];
  const quad = ser[q] >= med ? (mom >= 0 ? 'Hot & accelerating' : 'Still hot · losing steam') : (mom >= 0 ? 'Emerging' : 'Fading');
  return `<div class="insp">
    <div class="insp-banner"><span class="tddot" style="background:${domColor}"></span><b>${it.label}</b><span class="lockchip ${locked ? 'on' : ''}">${locked ? '📌 Locked' : '👁 Preview'}</span><button class="unpin" data-unpin="1" title="${locked ? 'Release lock' : 'Close'}">✕</button>
      <div class="insp-sub"><span style="color:${domColor};font-weight:700">${pathStr}</span> · ${brdNow} / ${denom} companies · ~${(+ser[q]).toFixed(1)}× per call</div></div>
    ${toutExecHTML(it, S, q)}
    <div class="insp-sec"><h5>Mention &amp; breadth trend</h5><div class="insp-charts"><div class="insp-ch"><div class="chlbl">Avg mentions per company</div><div class="chart-xs" id="tspk_m"></div></div><div class="insp-ch"><div class="chlbl">Companies mentioning it</div><div class="chart-xs" id="tspk_c"></div></div></div></div>
    ${toutHiloHTML(it, S)}
    ${toutCompaniesHTML(it, S, q)}
    ${toutSpeakerHTML(it, S, q)}
    ${toutLLMReadHTML(it, S)}
    ${toutConceptsHTML(it, S)}
  </div>`;
}
/* idle drawer content (nothing selected): a compact quarter summary so the panel is always useful */
function topicIdleSummaryHTML(S) {
  const T = S.topics, q = topicAsOf(T), bi = topicBubbleItems(T, S).items;
  const pct = m => (m >= 0 ? '+' : '') + Math.round((m || 0) * 100) + '%';
  const mom = it => topicMomentum(it.series, q, momSmooth(T));
  const dot = it => `<span class="tdot" style="background:${sentDotColor(topicSent(it, S, topicSeg(), q))}"></span>`;
  const row = (it, extra) => `<div class="isum-row" data-goto="${it.id}">${dot(it)}<span class="isum-lab">${it.label}</span>${extra}</div>`;
  const hottest = bi.slice(0, 6).map(it => row(it, `<span class="ov-x">${(+it.series[q]).toFixed(1)}×</span>`)).join('');
  const ranked = bi.map(it => ({ it, m: mom(it) })).filter(r => r.m != null).sort((a, b) => b.m - a.m);
  const accel = ranked.filter(r => r.m > 0.02).slice(0, 4).map(r => row(r.it, `<span class="tmom up">${pct(r.m)}</span>`)).join('') || '<div class="dim" style="font-size:12px">—</div>';
  const cool = ranked.filter(r => r.m < -0.02).slice(-3).reverse().map(r => row(r.it, `<span class="tmom down">${pct(r.m)}</span>`)).join('') || '<div class="dim" style="font-size:12px">—</div>';
  return `<div class="insp">
    <div class="insp-banner"><b>This quarter — ${qLabel(T.periods[q])}</b><div class="insp-sub">${bi.length} topics shown · hover a bubble to preview · click to lock</div></div>
    <div class="insp-sec"><h5>🔥 Hottest</h5>${hottest}</div>
    <div class="insp-sec"><h5>🚀 Accelerating</h5>${accel}</div>
    <div class="insp-sec"><h5>❄️ Cooling</h5>${cool}</div>
    <div class="dim" style="font-size:11px;padding:2px 2px 10px">Counts are token-free (regex over transcripts). Click any row or bubble for its full outlook.</div>
  </div>`;
}
function miniTrendChart(id, series, color, name, type, T) {
  const el = document.getElementById(id); if (!el) return;
  const ex = echarts.getInstanceByDom(el); if (ex) ex.dispose();   // hover re-renders the drawer; avoid leaking instances
  const sc = echarts.init(el); charts.push(sc);
  sc.setOption({ animation: false, grid: { left: 34, right: 10, top: 10, bottom: 20 }, tooltip: { trigger: 'axis', confine: true },
    xAxis: { type: 'category', data: (T.periods || []).map(qLabel), ...axisStyle() },
    yAxis: { type: 'value', name: name, nameTextStyle: { color: '#94a3b8', fontSize: 9 }, ...axisStyle() },
    series: [{ type: type, data: series, smooth: true, symbol: 'circle', symbolSize: 5, barWidth: '52%', itemStyle: { color: color, borderRadius: [3, 3, 0, 0] }, lineStyle: { color: color, width: 2 }, areaStyle: type === 'line' ? { color: cRgba(color, 0.12) } : undefined }] });
}
/* paint the inspector into the right drawer for the active (hovered/clicked) topic;
   a placeholder prompt when nothing is active yet */
function renderTopicInspector(S) {
  const dp = document.getElementById('topicdetail'); if (!dp) return false;
  const T = S.topics, q = topicAsOf(T), pin = topicPinId(S);
  const idle = () => { dp.innerHTML = topicIdleSummaryHTML(S); dp.querySelectorAll('[data-goto]').forEach(b => b.onclick = () => { STATE.topicLock = b.dataset.goto; STATE.topicPin = b.dataset.goto; STATE.inspScroll = 0; render(); }); };
  if (!pin) { idle(); return false; }   // nothing selected → quarter summary
  const it = (T.items || []).find(x => x.id === pin); if (!it) { idle(); return false; }
  dp.innerHTML = topicInspectorHTML(it, S, q);
  const eff = topicEffSeries(it, S), cat = (T.categories || []).find(c => c.id === it.cat) || {};
  miniTrendChart('tspk_m', eff.ser, cat.color, 'per co.', 'bar', T);
  miniTrendChart('tspk_c', eff.brd, '#64748b', 'cos', 'line', T);
  dp.querySelectorAll('[data-unpin]').forEach(b => b.onclick = () => { STATE.topicPin = null; STATE.topicLock = false; STATE.inspScroll = 0; render(); });
  dp.querySelectorAll('[data-lgrp]').forEach(b => b.onclick = () => { STATE.inspScroll = dp.scrollTop; const g = b.dataset.lgrp; STATE.topicGroups.has(g) ? STATE.topicGroups.delete(g) : STATE.topicGroups.add(g); renderTopicInspector(S); });
  dp.querySelectorAll('[data-drvall]').forEach(b => b.onclick = () => { STATE.inspScroll = dp.scrollTop; STATE.topicDrvAll = !STATE.topicDrvAll; renderTopicInspector(S); });
  dp.scrollTop = STATE.inspScroll || 0;   // preserve scroll across drawer re-renders
  return true;
}

/* Reusable filter bar (Layer · sub-layer · search · Segment · As-of · Labels) — shared by the
   Topics / Overview / By-company lenses. opts.search/labels/play toggle the lens-specific bits.
   All controls drive the same STATE (topicLayers/topicSeg/topicQ) so every lens reacts together. */
function topicFilterToggle() {
  return `<button class="lnk tctl-toggle" data-tctl="1">${STATE.topicCtlOpen !== false ? '▴ Hide filters' : '▾ Filters'}</button>`;
}
function topicFilterBar(S, opts) {
  opts = opts || {};
  const T = S.topics, pf = T.plot_from || 0, q = topicAsOf(T), sel = topicLayerSel();
  const SUBLABEL = { '3.1': 'Analog / MCU', '3.2': 'Logic / GPU', '3.3': 'Discrete / power', '3.4': 'Memory' };
  const subsBy = {}; topicCos().forEach(c => { if (c.layer && c.sublayer) (subsBy[c.layer] = subsBy[c.layer] || new Set()).add(c.sublayer); });
  const multiSub = new Set(Object.keys(subsBy).filter(L => subsBy[L].size > 1));
  const lsel = TOPIC_LAYERS.map(([k, l]) => { const on = k === 'all' ? sel.length === 0 : sel.includes(k); const caret = multiSub.has(k) ? ' ▾' : ''; return `<button class="seg ${on ? 'on' : ''}" data-tl="${k}">${k === 'all' ? '' : `<span class="lyr-dot" style="background:${LAYER_COLORS[k] || '#94a3b8'}"></span>`}${l}${caret}</button>`; }).join('');
  const subGrps = [...multiSub].filter(L => sel.includes(L) || [...subsBy[L]].some(sc => sel.includes(sc))).sort().map(L => {
    const chips = [...subsBy[L]].sort().map(sc => `<button class="seg ${sel.includes(sc) ? 'on' : ''}" data-tl="${sc}"><span class="lyr-dot" style="background:${LAYER_COLORS[L] || '#94a3b8'}"></span>${SUBLABEL[sc] || sc}</button>`).join('');
    return `<div class="seggrp"><span class="seglbl">${L} sub</span>${chips}</div>`;
  }).join('');
  const selTk = sel.filter(code => topicCos().some(c => c.ticker === code));
  const coChips = selTk.map(tk => { const co = topicCos().find(c => c.ticker === tk) || {}; return `<button class="seg on" data-tl="${tk}"><span class="lyr-dot" style="background:${LAYER_COLORS[co.layer] || '#94a3b8'}"></span>${co.name || tk} ✕</button>`; }).join('');
  const coGrp = opts.search ? `<div class="seggrp"><span class="cosearch-wrap"><input id="cosearch" class="cosearch" placeholder="Search topics, companies, layers…" autocomplete="off"><div id="cosearch_dd" class="cosearch-dd"></div></span>${coChips}</div>` : (coChips ? `<div class="seggrp">${coChips}</div>` : '');
  const qsel = T.periods.map((p, i) => i >= pf ? `<button class="seg ${i === q ? 'on' : ''}" data-tq="${i}">${qLabel(p)}</button>` : '').join('');
  const playBtn = opts.play ? `<button class="seg ${TOPIC_PLAY ? 'on' : ''}" data-tplay="1">${TOPIC_PLAY ? '⏸ Pause' : '▶ Play'}</button>` : '';
  const labMode = STATE.topicLabels || 'auto';
  const labSel = opts.labels ? `<div class="seggrp"><span class="seglbl">Labels</span>${[['auto', 'Auto'], ['all', 'All'], ['off', 'Off']].map(([k, l]) => `<button class="seg ${labMode === k ? 'on' : ''}" data-tlabels="${k}">${l}</button>`).join('')}</div>` : '';
  const segSel = [['all', 'All speech'], ['prepared', 'Prepared'], ['ceo', 'CEO'], ['cfo', 'CFO'], ['q', 'Analyst Q'], ['a', 'Mgmt A']].map(([k, l]) => `<button class="seg ${topicSeg() === k ? 'on' : ''}" data-tseg="${k}">${l}</button>`).join('');
  const selLabel = sel.map(code => { const co = topicCos().find(c => c.ticker === code); return co ? co.name : code; }).join(' + ');
  const segName = { all: '', prepared: 'Prepared remarks', ceo: 'CEO remarks', cfo: 'CFO remarks', q: 'Analyst questions', a: 'Mgmt answers' }[topicSeg()] || '';
  if (STATE.topicCtlOpen === false) return `<div class="ctl-collapsed dim" data-tctl="1">Layer: <b>${sel.length ? selLabel : 'All'}</b> · Segment: <b>${segName || 'All speech'}</b> · As of <b>${qLabel(T.periods[q])}</b> <span class="lnk" style="margin-left:6px">▾ change</span></div>`;
  return `<div class="topicctl">
    <div class="mkbar tight"><div class="seggrp"><span class="seglbl">Layer</span>${lsel}</div>${subGrps}${coGrp}</div>
    <div class="mkbar tight"><div class="seggrp"><span class="seglbl">Segment</span>${segSel}</div><div class="seggrp"><span class="seglbl">As of</span>${qsel}${playBtn}</div>${labSel}</div>
  </div>`;
}

/* Lens — OVERVIEW: "the quarter in one view". Synthesizes all topics into a scannable brief:
   dominant themes, what's accelerating/cooling, and the validated forward outlooks. */
const DIRBADGE = { improving: ['▲', '#16a34a', 'Improving'], stabilizing: ['→', '#d97706', 'Stabilizing'], deteriorating: ['▼', '#dc2626', 'Deteriorating'], mixed: ['◆', '#d97706', 'Mixed'] };
function sigOverviewBody(S) {
  const T = S.topics; if (!T) return `<div class="panel"><div class="dim">No topic data.</div></div>`;
  const q = topicAsOf(T), catOf = id => (T.categories || []).find(c => c.id === id) || {};
  // filter-aware: only topics raised by the selected layer(s), with series/breadth for the chosen segment
  const items = topicItemsForLayer(T).map(it => { const e = topicEffSeries(it, S); return Object.assign({}, it, { series: e.ser, breadth: e.brd }); });
  const segName = { all: '', prepared: 'Prepared remarks', ceo: 'CEO remarks', cfo: 'CFO remarks', q: 'Analyst questions', a: 'Mgmt answers' }[topicSeg()] || '';
  const mom = it => topicMomentum(it.series, q, momSmooth(T));
  const pct = m => (m >= 0 ? '+' : '') + Math.round((m || 0) * 100) + '%';
  const dot = it => `<span class="tdot" style="background:${catOf(it.cat).color}"></span>`;
  const goto = (it, extra) => `<div class="ov-row" data-goto="${it.id}">${dot(it)}<span class="ov-lab">${it.label}</span>${extra}</div>`;
  const hottest = items.slice().sort((a, b) => b.series[q] - a.series[q]).slice(0, 5);
  const ranked = items.map(it => ({ it, m: mom(it) })).filter(r => r.m != null).sort((a, b) => b.m - a.m);
  const accel = ranked.filter(r => r.m > 0.02).slice(0, 5), cool = ranked.filter(r => r.m < -0.02).slice(-5).reverse();
  const O = T.outlook || {};
  const outRows = Object.keys(O).map(id => { const o = O[id], it = items.find(x => x.id === id) || {}, d = DIRBADGE[(o.outlook || {}).direction] || ['◆', '#64748b', '—']; return { id, label: it.label || id, cat: it.cat, d, o }; });
  const impv = outRows.filter(o => o.d[0] === '▲').map(o => o.label), stab = outRows.filter(o => o.d[0] === '→').map(o => o.label), wors = outRows.filter(o => o.d[0] === '▼').map(o => o.label);
  const takeaway = `<b>${(hottest[0] || {}).label} &amp; ${(hottest[1] || {}).label}</b> dominate this quarter's calls${accel.length ? ` — <b style="color:#16a34a">${accel[0].it.label}</b> is the fastest-accelerating theme (${pct(accel[0].m)})` : ''}. ${impv.length ? `Forward read: <b style="color:#16a34a">${impv.join(', ')}</b> improving` : ''}${stab.length ? `; <b style="color:#d97706">${stab.join(', ')}</b> stabilizing` : ''}${wors.length ? `; <b style="color:#dc2626">${wors.join(', ')}</b> under pressure` : ''}.`;
  const hotRow = it => goto(it, `<span class="ov-x">${(+it.series[q]).toFixed(1)}×</span><span class="tmom ${mom(it) >= 0 ? 'up' : 'down'}">${pct(mom(it))}</span><span class="ov-b">${(it.breadth || [])[q] || 0} cos</span>`);
  const momRow = r => goto(r.it, `<span class="tmom ${r.m >= 0 ? 'up' : 'down'}">${pct(r.m)}</span><span class="ov-x">${(+r.it.series[q]).toFixed(1)}×</span>`);
  const outCard = o => `<div class="ov-out" data-goto="${o.id}"><div class="ov-out-h"><span class="tdot" style="background:${catOf(o.cat).color}"></span><b>${o.label}</b><span class="ov-dir" style="color:${o.d[1]}">${o.d[0]} ${o.d[2]}</span></div><div class="ov-out-hl">${(o.o.outlook || {}).headline || ''}</div></div>`;
  return `<div class="panel">
    <div class="thead-row"><h3>Quarter in one view <span class="dim" style="font-weight:400;font-size:13px">— ${qLabel(T.periods[q])} · ${items.length} topics${segName ? ` · <span style="color:var(--blue)">${segName}</span>` : ''}</span></h3>${topicFilterToggle()}</div>
    ${topicFilterBar(S, {})}
    <div class="ov-take">${takeaway}</div>
    <div class="ov-grid">
      <div class="ov-card"><h4>🔥 Dominant themes <span class="dim">— most-raised</span></h4>${hottest.map(hotRow).join('')}</div>
      <div class="ov-card"><h4>🚀 Accelerating <span class="dim">— momentum vs 4Q</span></h4>${accel.map(momRow).join('') || '<div class="dim" style="font-size:12px">—</div>'}</div>
      <div class="ov-card"><h4>❄️ Cooling</h4>${cool.map(momRow).join('') || '<div class="dim" style="font-size:12px">—</div>'}</div>
    </div>
    <h4 style="margin:16px 0 8px">🧭 Forward outlooks <span class="dim" style="font-weight:400">— LLM-validated, click to open</span></h4>
    <div class="ov-outs">${outRows.map(outCard).join('')}</div>
    <div class="dim" style="font-size:11px;margin-top:12px">Counts &amp; momentum are token-free (regex over transcripts); forward outlooks are LLM-validated (false-positives excluded). Click any row to open the topic.</div>
  </div>`;
}

/* Lens — BY COMPANY: flip topic→company. Pick a company, see its stance across every topic it raised. */
function sigCompanyBody(S) {
  const T = S.topics; if (!T) return `<div class="panel"><div class="dim">No topic data.</div></div>`;
  const cos = topicSelCos(), q = topicAsOf(T), P = T.periods || [], seg = topicSeg(), catOf = id => (T.categories || []).find(c => c.id === id) || {};
  const sel = (STATE.coView && cos.find(c => c.ticker === STATE.coView)) ? STATE.coView : (cos[0] || {}).ticker;
  const co = cos.find(c => c.ticker === sel) || {};
  const chips = cos.slice().sort((a, b) => (a.layer + a.sublayer).localeCompare(b.layer + b.sublayer)).map(c => `<button class="seg ${c.ticker === sel ? 'on' : ''}" data-co="${c.ticker}"><span class="lyr-dot" style="background:${LAYER_COLORS[c.layer] || '#94a3b8'}"></span>${c.name}</button>`).join('');
  const pc = T.per_company || {}, sd = T.sentiment || {}, segName = { all: '', prepared: 'Prepared remarks', ceo: 'CEO remarks', cfo: 'CFO remarks', q: 'Analyst questions', a: 'Mgmt answers' }[seg] || '';
  const rows = (T.items || []).map(it => {
    const traj = ((sd[sel] || {})[it.id] || {})[seg] || [];
    if (traj[q] == null) return null;   // raised THIS quarter only (sentiment non-null = actually mentioned; counts are nearest-filled so unreliable)
    const carr = ((pc[sel] || {})[it.id] || {})[seg] || [];
    return { it, mentions: carr[q] || 0, traj, latest: traj[q] };
  }).filter(Boolean).sort((a, b) => b.mentions - a.mentions);
  const exc = rows.filter(r => r.latest != null && r.latest >= 0.2).sort((a, b) => b.latest - a.latest);
  const cau = rows.filter(r => r.latest != null && r.latest <= -0.2).sort((a, b) => a.latest - b.latest);
  const vocal = rows.slice(0, 3).map(r => r.it.label);
  const badge = v => { const m = v == null ? ['—', '#94a3b8'] : v >= 0.2 ? ['Positive', '#16a34a'] : v <= -0.2 ? ['Negative', '#dc2626'] : ['Neutral', '#d97706']; return `<span class="smx-badge" style="color:${m[1]};border-color:${m[1]}">${m[0]}</span>`; };
  // right-side commentary = WHAT THEY SAID: LLM per-company "why" (validated) → real management quote
  // (token-free, pulled from the transcript) → a data-derived tone phrase only as a last resort.
  const quotes = T.quotes || {};
  const tonePhrase = r => { const nn = r.traj.filter(v => v != null); if (nn.length <= 1) return ''; const f = nn[0], l = nn[nn.length - 1], d = l - f, fs = (f >= 0 ? '+' : '') + f.toFixed(1), ls = (l >= 0 ? '+' : '') + l.toFixed(1); return l <= -0.2 ? `turned cautious (${fs}→${ls})` : d >= 0.3 ? `tone improving (${fs}→${ls})` : d <= -0.3 ? `tone softening (${fs}→${ls})` : `steady tone (~${ls})`; };
  const why = r => {
    const O = topicOutlookFor(S, r.it.id), pt = (O && O.companies && O.companies[sel]) ? O.companies[sel].point : '';
    if (pt) return { txt: pt, cls: 'llm' };
    const q2 = (quotes[sel] || {})[r.it.id];
    if (q2) return { txt: '“' + q2 + '”', cls: 'quote' };
    return { txt: tonePhrase(r), cls: 'tone' };
  };
  const row = r => {
    const cells = P.map((p, i) => { const v = r.traj[i]; if (v == null) return `<span class="smx-c miss" title="${qLabel(p)}: not mentioned"></span>`; const sc = sentCell(v); return `<span class="smx-c" style="background:${sc.bg}" title="${qLabel(p)}: ${sc.txt}">${sc.txt}</span>`; }).join('');
    const w = why(r);
    return `<div class="cv-row" data-goto="${r.it.id}"><span class="cv-lab"><span class="tdot" style="background:${catOf(r.it.cat).color}"></span>${r.it.label}</span>${cells}<span class="cv-st">${badge(r.latest)}</span><span class="cv-m">${r.mentions}×</span><span class="cv-why ${w.cls}" title="${(w.txt || '').replace(/"/g, '&quot;')}">${w.txt}</span></div>`;
  };
  const hdr = `<div class="cv-row cv-hdr"><span class="cv-lab">topic</span>${P.map(p => `<span class="smx-c">${qLabel(p)}</span>`).join('')}<span class="cv-st">latest</span><span class="cv-m">/call</span><span class="cv-why">commentary</span></div>`;
  const summary = `<b>${co.name}</b> raised <b>${rows.length}</b> topics this quarter — most on <b>${vocal.join(', ') || '—'}</b>. ${exc.length ? `Bullish on <b style="color:#16a34a">${exc.slice(0, 3).map(r => r.it.label).join(', ')}</b>` : ''}${cau.length ? `${exc.length ? '; ' : ''}cautious on <b style="color:#dc2626">${cau.slice(0, 3).map(r => r.it.label).join(', ')}</b>` : ''}.`;
  return `<div class="panel">
    <div class="thead-row"><h3>By company <span class="dim" style="font-weight:400;font-size:13px">— ${co.name} · ${co.layer} ${co.sublayer} · ${qLabel(T.periods[q])}${segName ? ` · <span style="color:var(--blue)">${segName}</span>` : ''}</span></h3>${topicFilterToggle()}</div>
    ${topicFilterBar(S, {})}
    <div class="mkbar" style="margin:8px 0 10px"><div class="seggrp" style="flex-wrap:wrap"><span class="seglbl">Company</span>${chips}</div></div>
    <div class="ov-take">${summary}</div>
    <div class="cv">${hdr}${rows.map(row).join('') || '<div class="dim" style="font-size:12px;padding:8px 0">No topic mentions found for this company.</div>'}</div>
    <div class="dim" style="font-size:11px;margin-top:10px">Heatmap = this company's per-quarter lexicon sentiment on each topic (green positive); hatched = not mentioned. Click a row to open the topic. Sorted by mentions/call this quarter.</div>
  </div>`;
}

/* Lens — TOPIC TREE: the whole taxonomy as a collapsible ECharts tree.
   Subjects branch into dimensions (Demand/Supply/Pricing/Capability); leaves = measured topics.
   node size = mentions · leaf colour = sentiment · internal-node colour = dimension. */
const FACET_COLOR = { demand: '#f28e2b', supply: '#76b7b2', product: '#b07aa1', price: '#4e79a7', risk: '#e15759' };
/* LLM demand/supply reads → aggregate favorability per (subject, dimension), for the tree's Demand/Supply nodes */
function favColor(net) { if (net == null) return '#cbd5e1'; if (net >= 0.34) return '#15803d'; if (net >= 0.1) return '#22c55e'; if (net > -0.1) return '#f59e0b'; if (net > -0.34) return '#ef4444'; return '#b91c1c'; }
function favLabel(net) { return net == null ? '' : net >= 0.1 ? '▲ bullish' : net <= -0.1 ? '▼ bearish' : '→ mixed'; }
function topicDimReads(T) { return (T.dimension_reads && T.dimension_reads.companies) || {}; }
function topicSubjectProducts(subjId, T) {  // family products (parent is a node) under a subject node
  const nodes = topicTree(T).nodes;
  return (T.items || []).filter(it => it.kind === 'product' && it.path && it.path.indexOf(subjId) >= 0 && nodes[it.parent]);
}
function topicAggDim(subjId, facet, T) {  // mean favorability of the subject's products on this dimension (skip 'na')
  const reads = topicDimReads(T), prods = topicSubjectProducts(subjId, T);
  const sk = facet === 'demand' ? 'demand_state' : 'supply_state', fk = facet === 'demand' ? 'demand_favorable' : 'supply_favorable';
  let sum = 0, n = 0; const rows = [];
  Object.keys(reads).forEach(co => prods.forEach(p => {
    const r = (reads[co] || {})[p.id]; if (!r || r[sk] === 'na') return;
    sum += r[fk] === 'bullish' ? 1 : r[fk] === 'bearish' ? -1 : 0; n++;
    rows.push({ co: topicCoName(co), prod: p.label, state: r[sk], fav: r[fk] });
  }));
  rows.sort((a, b) => ({ bullish: 0, neutral: 1, bearish: 2 }[a.fav] - { bullish: 0, neutral: 1, bearish: 2 }[b.fav]));
  return { net: n ? sum / n : null, n, rows };
}
/* per-topic LLM favorability aggregated across companies (any topic, not just products) */
function topicLLMFav(tid, T) {
  const reads = topicDimReads(T); let sum = 0, n = 0;
  Object.keys(reads).forEach(co => { const r = (reads[co] || {})[tid]; if (r && r.favorable) { sum += r.favorable === 'bullish' ? 1 : r.favorable === 'bearish' ? -1 : 0; n++; } });
  return n ? { net: sum / n, n } : null;
}
function topicLLMRows(tid, T) {
  const reads = topicDimReads(T), rows = [], ord = { bullish: 0, neutral: 1, bearish: 2 };
  Object.keys(reads).forEach(co => { const r = (reads[co] || {})[tid]; if (r && r.favorable) rows.push({ co: topicCoName(co), fav: r.favorable, ds: r.demand_state, ss: r.supply_state, why: r.why }); });
  return rows.sort((a, b) => ord[a.fav] - ord[b.fav]);
}
function sigTreeBody(S) {
  const T = S.topics; if (!T || !topicTree(T)) return `<div class="panel"><div class="dim">No topic tree in bundle — re-run scripts/load_transcripts.py</div></div>`;
  const q = topicAsOf(T), nLeaves = topicItemsForLayer(T).length, h = Math.max(640, nLeaves * 26 + 40);
  const segName = { all: '', prepared: 'Prepared remarks', ceo: 'CEO remarks', cfo: 'CFO remarks', q: 'Analyst questions', a: 'Mgmt answers' }[topicSeg()] || '';
  const FACET = [['demand', 'Demand'], ['supply', 'Supply'], ['product', 'Product / capability'], ['price', 'Pricing'], ['risk', 'Macro / risk']];
  const facetKey = FACET.map(f => `<span class="tlg"><span class="tdot" style="background:${FACET_COLOR[f[0]]}"></span>${f[1]}</span>`).join('');
  return `<div class="panel">
    <div class="thead-row"><h3>Topic tree — subjects × dimensions <span class="dim" style="font-weight:400;font-size:13px">— ${qLabel(T.periods[q])}${segName ? ` · <span style="color:var(--blue)">${segName}</span>` : ''} · node size = mentions · colour = sentiment</span></h3>${topicFilterToggle()}</div>
    ${topicFilterBar(S, {})}
    <div class="chart" id="treechart" style="height:${h}px"></div>
    <div class="tlgrow" style="margin-top:6px"><span class="dim" style="font-size:11px;font-weight:700;margin-right:4px">Dimension node</span>${facetKey}</div>
    <div class="tlgrow" style="margin-top:2px"><span class="dim" style="font-size:11px;font-weight:700;margin-right:4px">Leaf colour</span>${shapeSVG('circle', '#15803d')} optimistic ${shapeSVG('circle', '#f59e0b')} neutral ${shapeSVG('circle', '#b91c1c')} cautious <span class="dim" style="font-size:11px">· click a branch to collapse/expand · click a leaf to open its outlook</span></div>
  </div>`;
}
function sigTreeChart(S) {
  const T = S.topics; const ch = mk('treechart'); if (!ch || !T || !topicTree(T)) return;
  const q = topicAsOf(T), seg = topicSeg(), nodes = topicTree(T).nodes;
  const items = {}; topicItemsForLayer(T).forEach(it => items[it.id] = it);   // respect the layer filter
  const sz = v => v == null ? 9 : Math.max(9, Math.min(46, 9 + Math.sqrt(v) * 5.6));
  const leafNode = it => {
    const heat = topicEffSeries(it, S).ser[q], sentv = topicSent(it, S, seg, q);
    const node = { name: it.label, value: +(+heat).toFixed(1), symbolSize: sz(heat),
      itemStyle: { color: sentDotColor(sentv), borderColor: '#fff', borderWidth: 1 },
      label: { color: '#0f172a', fontWeight: 500 }, tid: it.id, dparent: it.parent };
    const kids = Object.values(items).filter(x => (x.parent || null) === it.id);   // a topic can parent sub-topics (HBM ▸ HBM4)
    if (kids.length) node.children = kids.map(leafNode);
    return node;
  };
  const innerNode = id => {
    const n = nodes[id];
    const leaves = Object.values(items).filter(it => (it.parent || null) === id).map(leafNode);
    const inner = Object.keys(nodes).filter(k => (nodes[k].parent || null) === id).map(innerNode);
    const node = { name: n.label, symbolSize: 13, label: { color: '#334155', fontWeight: 700 }, children: leaves.concat(inner) };
    let col;
    if (n.facet === 'demand' || n.facet === 'supply') {   // product-dimension node → colour by LLM-read favorability
      const agg = topicAggDim(n.parent, n.facet, T);
      if (agg.n) { col = favColor(agg.net); Object.assign(node, { isDim: n.facet, dimNet: agg.net, dimRows: agg.rows, netLabel: favLabel(agg.net), symbolSize: 13 + Math.min(14, agg.n * 1.4) }); }
    }
    if (!col) col = FACET_COLOR[n.facet] || '#94a3b8';   // domain/subject nodes (End Markets, Ops…) keep their facet colour
    Object.assign(node, { itemStyle: { color: col, borderColor: '#fff', borderWidth: 1.5 }, lineStyle: { color: cRgba(col, 0.55) } });
    return node;
  };
  const roots = Object.keys(nodes).filter(n => !nodes[n].parent).map(innerNode);
  const data = [{ name: 'Topics', symbolSize: 7, itemStyle: { color: '#cbd5e1' }, label: { show: false }, children: roots }];
  ch.setOption({ animation: true, animationDuration: 450,
    tooltip: { trigger: 'item', confine: true, formatter: p => {
      const d = p.data; if (!d) return '';
      if (d.isDim) {
        const head = `<b>${d.name}</b> — ${d.netLabel || 'no LLM reads'}${d.dimNet != null ? ` (net ${d.dimNet >= 0 ? '+' : ''}${d.dimNet.toFixed(2)} · ${d.dimRows.length})` : ''}`;
        const rows = (d.dimRows || []).slice(0, 14).map(r => { const c = r.fav === 'bullish' ? '#16a34a' : r.fav === 'bearish' ? '#dc2626' : '#d97706'; return `${r.co} · ${r.prod}: <span style="color:${c}">${r.state}/${r.fav}</span>`; }).join('<br/>');
        return head + (rows ? `<br/>${rows}` : '');
      }
      return d.tid ? `<b>${d.name}</b><br/>${d.value}× per call` : `<b>${d.name}</b>`;
    } },
    series: [{ type: 'tree', data, top: '1%', left: '6%', bottom: '1%', right: '21%',
      layout: 'orthogonal', orient: 'LR', edgeShape: 'curve', edgeForkPosition: '55%',
      initialTreeDepth: -1, expandAndCollapse: true, symbol: 'circle', roam: false,
      label: { position: 'right', verticalAlign: 'middle', align: 'left', fontSize: 12, distance: 6, formatter: p => { const d = p.data; if (d && d.tid) return `${p.name}  ${p.value}×`; if (d && d.isDim && d.netLabel) return `${p.name}  ${d.netLabel}`; return p.name; } },
      leaves: { label: { position: 'right', verticalAlign: 'middle', align: 'left', formatter: p => `${p.name}  ${p.value}×` } },
      emphasis: { focus: 'relative', lineStyle: { width: 2 } },
      lineStyle: { color: '#d7dee8', width: 1.2, curveness: 0.45 } }] });
  ch.off('click'); ch.on('click', p => { if (p.data && p.data.tid) { STATE.sigView = 'topics'; STATE.topicPin = p.data.tid; STATE.topicDrill = p.data.dparent || null; STATE.inspScroll = 0; render(); } });
}
/* Topic-map bubbles = the hottest PRIMARY topics (atomic grain: parent is an internal node, so
   generation sub-leaves like HBM4 are excluded → no parent/child double-count), ranked by mentions,
   capped to STATE.topicTopN. The slider trims how many show. */
function topicBubbleItems(T, S) {
  const tr = topicTree(T), q = topicAsOf(T);
  let leaves = topicItemsForLayer(T);
  if (tr) leaves = leaves.filter(it => tr.nodes[it.parent]);   // primary grain only
  const eff = leaves.map(it => { const e = topicEffSeries(it, S); return Object.assign({}, it, { series: e.ser, breadth: e.brd }); });
  eff.sort((a, b) => (b.series[q] || 0) - (a.series[q] || 0));
  return { items: eff.slice(0, Math.max(3, STATE.topicTopN || 30)), total: eff.length };
}
function sigTopicsBody(S) {
  const T = S.topics;
  if (!T) return `<div class="panel"><div class="dim">No topic data — re-run scripts/load_transcripts.py</div></div>`;
  const pf = T.plot_from || 0, q = topicAsOf(T), catOf = id => T.categories.find(c => c.id === id) || {};
  const items = topicItemsForLayer(T).map(it => { const e = topicEffSeries(it, S); return Object.assign({}, it, { series: e.ser, breadth: e.brd }); });  // layer-effective, so lists track the filter
  const pct = m => (m >= 0 ? '+' : '') + Math.round(m * 100) + '%';
  const sel = topicLayerSel(), segMode = topicSeg();
  const selLabel = sel.map(code => { const co = topicCos().find(c => c.ticker === code); return co ? co.name : code; }).join(' + ');
  const ranked = items.map(it => ({ it, m: topicMomentum(it.series, q, momSmooth(T)), cur: it.series[q] })).filter(r => r.m != null).sort((a, b) => b.m - a.m);
  const trow = r => `<div class="trow"><span class="tdot" style="background:${catOf(r.it.cat).color}"></span><span class="tlab">${r.it.label}</span>${STANCE_TAG[r.it.stance] || ''}<span class="tmom ${r.m >= 0 ? 'up' : 'down'}">${pct(r.m)}</span></div>`;
  const heating = ranked.slice(0, 6).map(trow).join('');
  const cooling = ranked.slice(-5).reverse().map(trow).join('');
  const keyc = items.slice().sort((a, b) => b.series[q] - a.series[q]).slice(0, 5).map(it => {
    const m = topicMomentum(it.series, q, momSmooth(T)), b = (it.breadth || [])[q];
    return `<div class="trow"><span class="tdot" style="background:${catOf(it.cat).color}"></span><span class="tlab"><b>${it.label}</b> <span class="dim">— ${it.note || ''}</span></span><span class="kco">${b != null ? b + ' cos' : ''}</span><span class="tmom ${m >= 0 ? 'up' : 'down'}">${pct(m)}</span></div>`;
  }).join('');
  const _tr = topicTree(T), _roots = _tr ? Object.keys(_tr.nodes).filter(n => !_tr.nodes[n].parent) : [];
  const shapeKey = _roots.map(r => `<span class="tlg">${shapeSVG(DOMAIN_SHAPE[r], '#64748b')} ${_tr.nodes[r].label}</span>`).join('');
  const colorKey = `<span class="tlg">${shapeSVG('circle', '#15803d')} optimistic</span><span class="tlg">${shapeSVG('circle', '#f59e0b')} neutral</span><span class="tlg">${shapeSVG('circle', '#b91c1c')} cautious</span><span class="dim" style="font-size:11px">— size = # companies (relative)</span>`;
  const segName = { all: '', prepared: 'Prepared remarks', ceo: 'CEO remarks', cfo: 'CFO remarks', q: 'Analyst questions', a: 'Mgmt answers' }[segMode] || '';
  return `<div class="panel"><div class="thead-row"><h3>Topic map — what's hot, and where the momentum is (${qLabel(T.periods[q])})${segName ? ` · <span style="color:var(--blue)">${segName}</span>` : ''}${sel.length ? ` · <span style="color:var(--text-dim)">${selLabel}</span>` : ''}</h3>
      ${topicFilterToggle()}</div>
    ${topicFilterBar(S, { labels: true, play: true })}
    ${(() => { const bi = topicBubbleItems(T, S); const shown = bi.items.length, tot = bi.total; return `<div class="topn-bar"><span class="cosearch-wrap"><input id="cosearch" class="cosearch" placeholder="Search topics / companies / layers…" autocomplete="off"><div id="cosearch_dd" class="cosearch-dd"></div></span><span class="seglbl" style="margin-left:6px">Show top</span><input type="range" class="topn-slider" min="3" max="${tot}" value="${Math.min(STATE.topicTopN || 30, tot)}" data-topn><span class="topn-val"><b>${shown}</b> / ${tot} topics</span><span class="dim" style="font-size:11px;margin-left:8px">by count · hover = preview · <b>click = lock</b> · empty space = close</span></div>`; })()}
    <div class="topiccap dim">X = avg mentions/company (how hot) · Y = momentum vs prior 4Q (emerging ↑) · size = # companies · <b>shape = domain</b> · <b>colour = sentiment</b> (green optimistic → red cautious).</div>
    <div class="topicwrap2" style="--drawer-w:${STATE.drawerW || 440}px"><div class="chart" id="topicchart" style="height:600px"></div><div class="topic-split" id="topicsplit" title="Drag to resize"></div><div class="topicdetail drawer" id="topicdetail"></div></div>
    <div class="tlgrow"><span class="dim" style="font-size:11px;font-weight:700;margin-right:4px">Shape = domain</span>${shapeKey}</div>
    <div class="tlgrow" style="margin-top:2px"><span class="dim" style="font-size:11px;font-weight:700;margin-right:4px">Colour = sentiment</span>${colorKey}</div>
    <div class="tcols">
      <div class="tcol"><h4>🔥 Hot &amp; accelerating <span class="dim" style="font-weight:400">— highest momentum</span></h4>${heating}</div>
      <div class="tcol"><h4>❄️ Losing steam <span class="dim" style="font-weight:400">— momentum fading</span></h4>${cooling}</div>
      <div class="tcol" style="grid-column:1 / -1"><h4>🔑 Key concepts in play <span class="dim" style="font-weight:400">— most-discussed this quarter, with what's driving them</span></h4>${keyc}</div>
    </div>
    <div class="dim" style="font-size:11px;margin-top:10px">X = <b>average mentions per company</b> that quarter, counted from the <b>actual earnings-call transcripts</b> by keyword tally. The X axis is compressed (square-root) so the many low-mention topics don't pile up on the left while AI sits far right — the numbers on the axis are the real counts. Momentum (Y) = this quarter vs trailing-4Q average, smoothed. <b>Labels</b>: Auto hides crowded ones (hover to see), All forces every label, Off = clean dots.${T.source === 'real' ? ' <b>Measured from real transcripts.</b>' : ''} Some paywalled middle quarters are nearest-filled per company.</div></div>`;
}
function sigTopicsChart(S) {
  const T = S.topics, ch = mk('topicchart'); if (!ch || !T) return;
  const ax = axisStyle(), q = topicAsOf(T);
  const items = topicBubbleItems(T, S).items;   // top-N primary topics by mention count
  if (!items.length) return;
  const heats = items.map(it => it.series[q]);
  const maxH = Math.max(...heats, 1);
  const LMIN = 0.5;
  const sx = v => Math.log10(Math.max(v, LMIN)) - Math.log10(LMIN);   // LOG scale: spreads the dense low-mention cluster
  const xMax = +(sx(maxH) * 1.06 + 0.06).toFixed(3);
  const med = (a => { const s = a.slice().sort((x, y) => x - y), n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; })(heats);
  const plotMed = sx(med);
  // auto-fit Y to the actual momentum cloud (keep the 0 line in view, no empty top)
  const moms = items.map(it => { const m = topicMomentum(it.series, q, momSmooth(T)); return m == null ? 0 : m; });
  const yMax = Math.min(1.6, Math.max(0.6, Math.ceil((Math.max(...moms) + 0.12) * 10) / 10));  // cap so one off-a-tiny-base outlier can't blow up the axis
  const yMin = Math.max(-0.8, Math.min(-0.1, Math.floor((Math.min(...moms) - 0.05) * 10) / 10));
  const catOf = id => T.categories.find(c => c.id === id) || {};
  // AUTO-SIZE: normalise # companies to the current max so bubbles stay bounded (~11–37px) at any roster size
  const maxBrd = Math.max(1, ...items.map(it => (it.breadth && it.breadth[q]) || 0));
  const sizeOf = b => 11 + Math.sqrt((b || 0) / maxBrd) * 26;
  // single scatter series (sorted big→small) so label de-overlap works GLOBALLY, not per-category
  const data = items.slice().sort((a, b) => b.series[q] - a.series[q]).map(it => {
    const cat = catOf(it.cat), sentv = topicSent(it, S, topicSeg(), q), llm = topicLLMFav(it.id, T), color = llm ? favColor(llm.net) : sentDotColor(sentv), m = topicMomentum(it.series, q, momSmooth(T)), heat = it.series[q];
    const brd = (it.breadth && it.breadth[q] != null) ? it.breadth[q] : 5;  // # companies that raised it
    const mv = m == null ? 0 : m, quad = heat >= med ? (mv >= 0 ? 'Hot &amp; accelerating' : 'Still hot · losing steam') : (mv >= 0 ? 'Emerging' : 'Fading');
    // "related" cluster for hover-highlight = the SUBJECT (L2 node: Memory/Processor/…/AI&DC) when one
    // exists, else the L1 domain (Supply&Ops, Macro, cyclical End-markets) — broader than the dimension parent.
    const cluster = (it.path && it.path.length >= 3) ? it.path[1] : ((it.path && it.path[0]) || it.parent);
    return { value: [+sx(heat).toFixed(3), +Math.max(yMin, Math.min(yMax, mv)).toFixed(3)],
      symbol: topicShape(it.id, T), symbolSize: sizeOf(brd),
      tid: it.id, parent: it.parent, cluster: cluster, tname: it.label, lab: wrapLabel(it.label, 18), cur: heat, base: +topicTrailAvg(it.series, q).toFixed(1), mom: mv, sent: sentv, stance: it.stance, who: it.who, brd: brd, ser: it.series, brdser: it.breadth || [], note: it.note || '', quad: quad, cc: color, cn: (cat.label || ''),
      itemStyle: { color: color, opacity: 0.92, borderWidth: 1, borderColor: cRgba('#0f172a', 0.14) } };
  });
  const series = [{ type: 'scatter', data, z: 5,
    emphasis: { scale: 1.3, focus: 'none', label: { show: true, fontWeight: 800, color: '#0b1220' }, itemStyle: { opacity: 1 } },
    labelLayout: { hideOverlap: true },
    label: { show: true, position: 'right', distance: 7, formatter: p => p.data.lab, fontSize: 11, lineHeight: 13, color: '#0f172a', fontWeight: 700 } }];
  if (series[0]) {
    series[0].markArea = { silent: true, data: [
      [{ xAxis: plotMed, yAxis: 0, itemStyle: { color: 'transparent' }, label: { show: true, position: 'insideTopRight', distance: 8, color: '#9aa7b8', fontSize: 10, fontWeight: 700, formatter: 'HOT & ACCELERATING' } }, { xAxis: xMax, yAxis: yMax }],
      [{ xAxis: plotMed, yAxis: yMin, itemStyle: { color: 'transparent' }, label: { show: true, position: 'insideBottomRight', distance: 8, color: '#9aa7b8', fontSize: 10, fontWeight: 700, formatter: 'STILL HOT · LOSING STEAM' } }, { xAxis: xMax, yAxis: 0 }],
      [{ xAxis: 0, yAxis: 0, itemStyle: { color: 'transparent' }, label: { show: true, position: 'insideTopLeft', distance: 8, color: '#9aa7b8', fontSize: 10, fontWeight: 700, formatter: 'EMERGING' } }, { xAxis: plotMed, yAxis: yMax }],
      [{ xAxis: 0, yAxis: yMin, itemStyle: { color: 'transparent' }, label: { show: true, position: 'insideBottomLeft', distance: 8, color: '#9aa7b8', fontSize: 10, fontWeight: 700, formatter: 'FADING' } }, { xAxis: plotMed, yAxis: 0 }],
    ] };
    series[0].markLine = { silent: true, symbol: 'none', z: 0, lineStyle: { color: '#eef2f7', width: 1, type: 'dashed' }, label: { show: false }, data: [{ yAxis: 0 }] };
  }
  ch.setOption({ animation: false,
    textStyle: { fontFamily: '"Fira Sans", system-ui, sans-serif' },
    grid: { left: 58, right: 158, top: 26, bottom: 56 },
    legend: { show: false },
    tooltip: { show: false },
    xAxis: { type: 'value', name: 'avg mentions per company →', nameLocation: 'middle', nameGap: 38, nameTextStyle: { color: '#94a3b8', fontSize: 11 }, min: 0, max: xMax,
      axisLine: { show: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
    yAxis: { type: 'value', name: 'momentum vs prior 4Q', nameGap: 16, nameTextStyle: { color: '#94a3b8', fontSize: 11, align: 'left' }, min: yMin, max: yMax,
      axisLine: { show: false }, axisTick: { show: false }, axisLabel: { formatter: v => (v > 0 ? '+' : '') + Math.round(v * 100) + '%', color: '#94a3b8', fontSize: 11 }, splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } } },
    series });
  // custom round-number x ticks at the √ positions (readable real counts), + label visibility per mode
  const mode = STATE.topicLabels || 'auto';
  let gfx = [];
  try {
    const yBot = ch.convertToPixel({ yAxisIndex: 0 }, yMin);
    [1, 2, 5, 10, 20, 50, 100].filter(t => t <= maxH * 1.05).forEach(t => {
      const xp = ch.convertToPixel({ xAxisIndex: 0 }, sx(t));
      if (xp != null) gfx.push({ type: 'text', silent: true, style: { text: '' + t, x: xp, y: yBot + 9, textAlign: 'center', textVerticalAlign: 'top', fill: '#94a3b8', fontSize: 11, fontFamily: '"Fira Sans",system-ui,sans-serif' } });
    });
  } catch (e) { /* not ready */ }
  // place each label on whichever side is free (right/left/top/bottom) so far more fit without overlap
  let place = data.map(() => ({ show: mode === 'all', position: 'right' }));
  if (mode === 'off') place = data.map(() => ({ show: false, position: 'right' }));
  if (mode === 'auto') {
    try {
      const W = ch.getWidth(), H = ch.getHeight(), placed = [];
      data.map((d, i) => ({ i, d, px: ch.convertToPixel({ seriesIndex: 0 }, d.value) })).filter(o => o.px)
        .sort((a, b) => b.d.cur - a.d.cur)
        .forEach(o => {
          const lines = (o.d.lab || o.d.tname).split('\n'), lw = Math.max(...lines.map(l => l.length));
          const w = lw * 7 + 10, hh = lines.length * 13 + 6, r = (o.d.symbolSize || 14) / 2 + 6, cx = o.px[0], cy = o.px[1];
          const cands = [['right', cx + r, cy - hh / 2], ['left', cx - r - w, cy - hh / 2], ['top', cx - w / 2, cy - r - hh], ['bottom', cx - w / 2, cy + r]];
          for (const c of cands) {
            const x0 = c[1], y0 = c[2], x1 = x0 + w, y1 = y0 + hh;
            if (x0 < 2 || x1 > W - 2 || y0 < 22 || y1 > H - 30) continue;
            if (placed.some(b => !(x1 < b.x0 || x0 > b.x1 || y1 < b.y0 || y0 > b.y1))) continue;
            placed.push({ x0: x0 - 4, y0: y0 - 3, x1: x1 + 4, y1: y1 + 3 }); place[o.i] = { show: true, position: c[0] }; break;   // pad for spacing
          }
        });
    } catch (e) { /* not ready */ }
  }
  // paint(hl): hl=null → default (labels per mode). hl=tid → highlight the hovered topic's TREE FAMILY
  // (same parent branch): only those bubbles stay solid + show labels; everything else dims + hides label.
  const paint = hl => {
    if (hl && !data.some(d => d.tid === hl)) hl = null;   // locked topic filtered out → don't dim everything
    const cl = hl ? (data.find(d => d.tid === hl) || {}).cluster : null;
    const lockId = (typeof STATE.topicLock === 'string') ? STATE.topicLock : null;
    ch.setOption({ graphic: gfx, series: [{ data: data.map((d, i) => {
      const fam = !hl || d.cluster === cl, locked = d.tid === lockId;
      return Object.assign({}, d, {
        symbolSize: locked ? d.symbolSize + 3 : d.symbolSize,   // locked = a touch larger + soft glow, always visible (subtle)
        label: { show: locked || (hl ? fam : place[i].show), position: place[i].position, opacity: (locked || fam) ? 1 : 0, fontWeight: 700 },
        itemStyle: Object.assign({}, d.itemStyle, {
          opacity: locked ? 1 : (hl ? (fam ? 0.96 : 0.08) : 0.92),
          shadowBlur: locked ? 9 : 0, shadowColor: locked ? cRgba('#0f172a', 0.22) : 'transparent' }) });
    }) }] });
  };
  // Interaction: HOVER always previews · CLICK a bubble LOCKS it (stays when you move away) · click empty / ✕ unlocks.
  let curHL = null, restoreT = null;
  const lockTid = () => (typeof STATE.topicLock === 'string') ? STATE.topicLock : null;
  const cancelRestore = () => { if (restoreT) { clearTimeout(restoreT); restoreT = null; } };
  const showInsp = tid => { STATE.topicPin = tid; renderTopicInspector(S); };
  const restore = () => { const L = lockTid(); curHL = L; paint(L); showInsp(L); };   // mouse left → revert to the locked topic (or empty)
  restore();   // initial paint + drawer (shows the locked topic if any, else empty/full-width)
  ch.off('mouseover'); ch.on('mouseover', p => { const d = p.data; if (!d || !d.tid) return; cancelRestore(); if (d.tid !== curHL) { curHL = d.tid; paint(d.tid); } showInsp(d.tid); });
  ch.off('mouseout'); ch.on('mouseout', () => { cancelRestore(); restoreT = setTimeout(restore, 160); });
  ch.off('globalout'); ch.on('globalout', () => { cancelRestore(); restore(); });
  // CLICK = geometry-based single source of truth (ECharts data-click misses small/label hits): the nearest
  // bubble within a threshold gets LOCKED (persists on mouse-leave); a click in open space unlocks + closes.
  ch.off('click');
  const zr = ch.getZr(); zr.off('click'); zr.on('click', e => {
    const x = e.offsetX != null ? e.offsetX : e.zrX, y = e.offsetY != null ? e.offsetY : e.zrY;
    let best = null, bestD = 1e9;
    data.forEach(d => { const pp = ch.convertToPixel({ seriesIndex: 0 }, d.value); if (pp) { const dd = Math.hypot(pp[0] - x, pp[1] - y); if (dd < bestD) { bestD = dd; best = d; } } });
    cancelRestore();
    if (best && bestD < (best.symbolSize / 2 + 22)) { STATE.inspScroll = 0; STATE.topicLock = best.tid; curHL = best.tid; paint(best.tid); showInsp(best.tid); }
    else { STATE.topicLock = null; STATE.topicPin = null; curHL = null; paint(null); renderTopicInspector(S); }
  });
  // resizable splitter: drag the divider to change the chart ↔ drawer ratio
  const split = document.getElementById('topicsplit'), wrap = split && split.parentElement;
  if (split && wrap) split.onmousedown = e => {
    e.preventDefault(); split.classList.add('dragging');
    const startX = e.clientX, startW = STATE.drawerW || 440, rect = wrap.getBoundingClientRect();
    const onMove = ev => { const w = Math.max(300, Math.min(rect.width - 340, startW - (ev.clientX - startX))); STATE.drawerW = Math.round(w); wrap.style.setProperty('--drawer-w', STATE.drawerW + 'px'); ch.resize(); };
    const onUp = () => { split.classList.remove('dragging'); document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
    document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
  };
}
/* Lens — Optimism − Discount = Net, by signal × company (your formula) */
function sigMatrixBody(S) {
  const SIG5 = [['demand', 'Demand'], ['supply', 'Supply'], ['pricing', 'Pricing'], ['inventory', 'Inventory'], ['capex', 'Capex']];
  const callOf = tk => S.calls.find(c => c.ticker === tk) || {};
  const co = S.companies.slice().sort((a, b) => SIG_LAYERORD(a) - SIG_LAYERORD(b));
  const head = `<th>Company</th>` + SIG5.map(s => `<th>${s[1]}</th>`).join('') + `<th>Avg</th>`;
  const cellHtml = (v, bold) => `<td class="cyc" style="background:${toneColor(v)};color:#0f172a${bold ? ';font-weight:800' : ''}">${v >= 0 ? '+' : ''}${v}</td>`;
  const rows = co.map(c => {
    const sm = S.sigmatrix[c.ticker] || {}, call = callOf(c.ticker), nets = [];
    const cells = SIG5.map(([k, l]) => {
      const cell = sm[k]; if (!cell) return `<td class="cyc na"></td>`;
      const opt = sigOpt(cell); if (opt == null) return `<td class="cyc na"></td>`;
      const disc = sigDisc(call, k), net = Math.sign(opt) * Math.max(0, Math.abs(opt) - disc);
      nets.push(net);
      return `<td class="cyc" style="background:${toneColor(net)};color:#0f172a" title="${c.name} · ${l}: optimism ${opt >= 0 ? '+' : ''}${opt} − discount ${disc} = net ${net >= 0 ? '+' : ''}${net}  [review: ${cell.review}, outlook: ${cell.outlook}]">${net >= 0 ? '+' : ''}${net}</td>`;
    }).join('');
    const avg = nets.length ? Math.round(nets.reduce((a, b) => a + b, 0) / nets.length) : null;
    return `<tr><td class="cycname"><span class="lyr-dot" style="background:${LAYER_COLORS[c.layer]}"></span>${c.name} <span class="dim" style="font-size:10px">${c.sublayer}</span></td>${cells}${avg == null ? '<td class="cyc na"></td>' : cellHtml(avg, true)}</tr>`;
  }).join('');
  return `<div class="panel"><h3>Optimism − Discount = Net &nbsp;<span class="dim" style="font-weight:400;font-size:13px">by signal × company (latest call)</span></h3>
    <div class="dim" style="font-size:12px;margin-bottom:10px"><b>Message optimism</b> (0.4 × Review + 0.6 × Outlook of each signal, −100…+100) <b>minus a credibility discount</b> (weak Q&A confidence + evasion on that topic) <b>= Net</b>. e.g. optimism +85, discount 10 → +75. Distributors (L0) carry the richer Review/Outlook extraction. Hover any cell for the full breakdown.</div>
    <table class="cyctab"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>
    <div class="dim" style="font-size:11px;margin-top:8px">green = optimistic · red = negative · deeper = stronger · blank = n/a (distributors report no capex signal). <b>Avg</b> = mean of the company's signal nets.</div></div>`;
}

/* Lens C — Propagation: a signal across layers over time (lead-lag wave) */
function sigFlowBody(S) {
  const eff = FLOW_METRICS.some(m => m[0] === STATE.sigMetric) ? STATE.sigMetric : 'sentiment';
  const msel = FLOW_METRICS.map(([k, l]) => `<button class="seg ${eff === k ? 'on' : ''}" data-sm="${k}">${l}</button>`).join('');
  return `<div class="panel"><h3>Propagation — <span style="text-transform:capitalize">${eff}</span> across the chain, over time</h3>
    <div class="mkbar" style="margin:0 0 6px"><div class="seggrp"><span class="seglbl">Signal</span>${msel}</div></div>
    <div class="chart" id="flowchart"></div>
    <div class="dim" style="font-size:11px;margin-top:6px">Each line is a supply-chain layer (averaged). Watch the order in which layers turn — demand lands at Foundry/Logic first and ripples to Equipment with a lag; on <b>sentiment</b> you can see L3 (Components) climb as auto/analog recovers toward the equipment & foundry plateau.</div></div>`;
}
function sigFlowChart(S) {
  const metric = FLOW_METRICS.some(m => m[0] === STATE.sigMetric) ? STATE.sigMetric : 'sentiment', ax = axisStyle();
  const LN = { L1: 'L1 Foundry', L2: 'L2 Equipment', L3: 'L3 Components' };
  const col = { L1: LAYER_COLORS.L1, L2: LAYER_COLORS.L2, L3: LAYER_COLORS.L3 };
  const series = ['L1', 'L2', 'L3'].map(ly => {
    const data = S.periods.map(p => {
      const vs = S.facts.filter(f => f.layer === ly && f.period === p && f.signal === metric && f.segment === 'overall' && f.value != null).map(f => f.value);
      return vs.length ? +(vs.reduce((a, b) => a + b, 0) / vs.length).toFixed(2) : null;
    });
    return { name: LN[ly], type: 'line', smooth: true, connectNulls: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 3, color: col[ly] }, itemStyle: { color: col[ly] }, data };
  });
  const ch = mk('flowchart'); if (!ch) return;
  ch.setOption({ animation: false, grid: { left: 44, right: 18, top: 28, bottom: 26 }, tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#475569' }, data: ['L1 Foundry', 'L2 Equipment', 'L3 Components'] },
    xAxis: { type: 'category', data: S.periods.map(qLabel), ...ax },
    yAxis: { type: 'value', name: 'signal', min: -2, max: 2, interval: 1, ...ax },
    series });
}

/* Lens F — Capability roadmap (structural signal that leads capex) */
function sigRoadmapBody(S) {
  const cap = S.capability || [], BASE = 2024, QN = 20;
  const idx = p => { const [y, n] = p.split('Q'); return (+y - BASE) * 4 + (+n - 1); };
  const SC = { hvm: '#16a34a', ramp: '#2563eb', dev: '#d97706', planned: '#94a3b8' };
  const nowPct = idx('2026Q1') / QN * 100;
  const LN = { L1: 'Foundry (L1)', L2: 'Equipment (L2)', L3: 'Components (L3)' };
  const axis = `<div class="gaxis">${[2024, 2025, 2026, 2027, 2028].map(y => `<span>${y}</span>`).join('')}</div>`;
  const groups = ['L1', 'L2', 'L3'].map(ly => {
    const rows = cap.filter(c => c.layer === ly).map(c => {
      const s = Math.max(0, idx(c.start)), e = Math.min(QN - 1, idx(c.end));
      const left = s / QN * 100, w = Math.max((e - s + 1) / QN * 100, 3);
      return `<div class="grow"><div class="glabel" title="${c.name} — ${c.note}">${c.name}</div>
        <div class="gtrack"><div class="gnow" style="left:${nowPct}%"></div>
          <div class="gbar" style="left:${left}%;width:${w}%;background:${SC[c.status]}" title="${c.name}: ${c.status}${c.note ? ' · ' + c.note : ''}"></div></div></div>`;
    }).join('');
    return `<div class="glayer" style="--c:${LAYER_COLORS[ly]}"><div class="glayer-h"><span class="lyr-dot" style="background:${LAYER_COLORS[ly]}"></span>${LN[ly]}</div>${rows}</div>`;
  }).join('');
  const legend = `<span class="glg" style="background:#16a34a">HVM</span><span class="glg" style="background:#2563eb">ramping</span><span class="glg" style="background:#d97706">development</span><span class="glg" style="background:#94a3b8">planned</span>`;
  return `<div class="panel"><h3>Capability roadmap — the tech transitions driving capex</h3>
    <div class="dim" style="font-size:12px;margin-bottom:10px">The structural / forward signal: node, HBM and packaging transitions <b>lead</b> the cyclical signals. Red line = now (2026Q1). &nbsp; ${legend}</div>
    ${axis}${groups}</div>`;
}

/* Definitions & methodology — reference block shown under every Signals lens */
function sigMethodology() {
  return `<div class="panel defsbox"><h3>📐 Definitions &amp; methodology — reference</h3><div class="defs">
    <p><b>Optimism Index (−100…+100)</b> = 0.5 × language tone + 0.5 × the five fundamentals. How positive a call is — blending <i>what management said</i> with <i>what the numbers showed</i>.</p>
    <p><b>Optimism (Tone discounted)</b> = Optimism × Q&amp;A confidence (0–1). The optimism marked down by how candid / non-evasive management was under analyst questioning.</p>
    <p><b>Optimism − Discount matrix (per signal)</b>: Message optimism (0.4 × Review + 0.6 × Outlook) − credibility discount (weak Q&amp;A confidence + evasion on that topic) = <b>Net</b>.</p>
    <p><b>The five signals</b>: Demand · Supply (capacity / availability / lead-times) · Pricing (ASP / gross margin) · Inventory (days / channel weeks) · Capex.</p>
    <p><b>Review vs Outlook</b>: Review = the reported quarter (backward-looking, factual). Outlook = guidance (forward-looking — where spin lives, so it carries more discount).</p>
    <p><b>Level → score</b>: strong +85 (fundamental +1) · tight +55 (+0.6) · moderate +45 (+0.5) · soft −25 (−0.5) · negative −70 (−1) · n/a = blank.</p>
    <p class="ex"><b>Worked example — Micron, 2026Q1.</b> Language tone +2 (→ +1) and the five fundamentals average 0.92 → Optimism = 100 × (0.5 × 1 + 0.5 × 0.92) = <b>+96</b>. Q&amp;A confidence 0.97 → Optimism (Tone discounted) = 96 × 0.97 ≈ <b>+93</b>.</p>
    <p class="dim" style="font-size:11px;margin-top:6px">Signals are model-extracted from free earnings-call transcripts — indicative; spot-check before acting.</p>
  </div></div>`;
}

/* Lens A — Journey (now) */
function sigJourneyBody(S, sparks) {
  let idx = 0;
  const stations = JOURNEY.map(j => {
    const cs = S.calls.filter(c => c.layer === j.layer).sort((a, b) => SIG_LAYERORD(a) - SIG_LAYERORD(b));
    const cards = cs.map(c => sigJcard(c, idx++, sparks)).join('');
    const conn = j.connector ? `<div class="jconn">${j.connector} ↓</div>` : '';
    return `<div class="jstation" style="--c:${LAYER_COLORS[j.layer]}">
      <div class="jhead"><span class="jnum">${j.n}</span><div>
        <div class="jtitle">Level ${j.n} · ${j.name} <span class="dim" style="font-weight:400">— ${j.tagline}</span></div>
        <div class="jverdict">${j.verdict}</div></div></div>
      <div class="jcards">${cards}</div></div>${conn}`;
  }).join('');
  const pills = PILLS.map(([t, d]) => `<span class="vpill ${d}">${d === 'up' ? '▲' : d === 'down' ? '▼' : '◆'} ${t}</span>`).join('');
  const finale = `<div class="panel jfinale"><h3>The synthesis — what the whole chain corroborates</h3>${S.callouts.map(x => `<div class="callout">${x}</div>`).join('')}</div>`;
  return `<div class="vbanner">${pills}</div>${stations}${finale}`;
}

/* Lens B — Cycle (signal over time, by company × quarter) */
function sigCycleBody(S) {
  const metric = CYCLE_METRICS.some(m => m[0] === STATE.sigMetric) ? STATE.sigMetric : 'tonecmp';
  const combo = metric === 'tonecmp';
  const cont = metric === 'tone' || metric === 'toneadj' || combo;
  const sgn = x => (x >= 0 ? '+' : '') + x;
  const fm = {}; S.facts.forEach(f => { if (f.segment === 'overall') fm[f.ticker + '|' + f.period + '|' + f.signal] = f; });
  const co = S.companies.slice().sort((a, b) => SIG_LAYERORD(a) - SIG_LAYERORD(b));
  const msel = CYCLE_METRICS.map(([k, l]) => `<button class="seg ${metric === k ? 'on' : ''}" data-sm="${k}">${l}</button>`).join('');
  const head = `<th>Company</th>` + S.periods.map(p => `<th>${qLabel(p)}</th>`).join('');
  const rows = co.map(c => {
    const cells = S.periods.map(p => {
      if (combo) {
        const raw = cellTone(S, c.ticker, p, false);
        if (raw == null) return `<td class="cyc na"></td>`;
        const adj = cellTone(S, c.ticker, p, true);
        const shave = Math.abs(raw) - Math.abs(adj);              // pts of conviction removed by weak Q&A candor (>=0)
        const gcls = shave >= 20 ? 'big' : shave >= 8 ? 'mid' : 'sm';
        const gtxt = shave <= 2 ? '≈' : '−' + shave;
        return `<td class="cyc tcc" style="background:${toneColor(adj)};color:#0f172a" title="${c.name} ${p}: optimism ${sgn(raw)} → tone-discounted ${sgn(adj)} · weak Q&A candor shaved ${shave} pts of conviction">`
          + `<span class="tcc-v">${sgn(adj)}</span><span class="tcc-g ${gcls}">${gtxt}</span></td>`;
      }
      if (cont) {
        const v = cellTone(S, c.ticker, p, metric === 'toneadj');
        if (v == null) return `<td class="cyc na"></td>`;
        return `<td class="cyc" style="background:${toneColor(v)};color:#0f172a" title="${c.name} ${p}: ${metric === 'toneadj' ? 'credibility-adjusted ' : ''}tone ${v >= 0 ? '+' : ''}${v}">${v >= 0 ? '+' : ''}${v}</td>`;
      }
      // per-signal (Demand/Supply/Pricing/Inventory/Capex): same concept — score the label, then tone-discount it
      const f = fm[c.ticker + '|' + p + '|' + metric];
      if (!f || f.label === 'na' || LVL_OPT[f.label] == null) return `<td class="cyc na"></td>`;
      const raw = LVL_OPT[f.label];
      const cf = fm[c.ticker + '|' + p + '|confidence'];
      const conf = cf && cf.value != null ? cf.value : 1;
      const adj = Math.round(raw * conf);
      const shave = Math.abs(raw) - Math.abs(adj);
      const gcls = shave >= 20 ? 'big' : shave >= 8 ? 'mid' : 'sm';
      const gtxt = shave <= 2 ? '≈' : '−' + shave;
      return `<td class="cyc tcc" style="background:${toneColor(adj)};color:#0f172a" title="${c.name} ${p}: ${metric} ${f.label} (${sgn(raw)}) → tone-discounted ${sgn(adj)} · weak Q&A candor shaved ${shave} pts">`
        + `<span class="tcc-lab">${f.label}</span><span class="tcc-v">${sgn(adj)}</span><span class="tcc-g ${gcls}">${gtxt}</span></td>`;
    }).join('');
    return `<tr><td class="cycname"><span class="lyr-dot" style="background:${LAYER_COLORS[c.layer]}"></span>${c.name} <span class="dim" style="font-size:10px">${c.sublayer}</span></td>${cells}</tr>`;
  }).join('');
  const lbl = (CYCLE_METRICS.find(m => m[0] === metric) || ['', metric])[1];
  const SIGWORD = { demand: 'Demand', supply: 'Supply', pricing: 'Pricing', inventory: 'Inventory', capex: 'Capex' };
  const note = metric === 'pricing' ? 'Micron: soft → negative → moderate → strong — the memory-pricing inflection, now scored and tone-discounted in one row.'
    : metric === 'tonecmp' ? 'Both numbers in one cell: the <b>big number</b> is tone-discounted optimism; the <b>chip</b> shows how many points weak Q&A candor shaved off — <b style="color:#166534">≈</b> = credible (tone held its conviction) · <b style="color:#92400e">−mid</b> = softened · <b style="color:#991b1b">−big</b> = heavily discounted. Candid memory calls keep almost all their optimism; guarded calls (ASML / Renesas) get marked down most.'
    : metric === 'toneadj' ? 'Optimism × Q&A confidence — optimism marked down by how candid management was under questioning. ASML / Renesas discount the most.'
      : SIGWORD[metric] ? `<b>${SIGWORD[metric]}</b> signal from the same earnings-call extraction — now <b>same concept as Optimism</b>: the qualitative read is scored (strong +85 · tight +55 · moderate +45 · soft −25 · negative −70), then tone-discounted by that call’s Q&A candor. The small word is the original read; the <b>big number</b> is the tone-discounted score; the <b>chip</b> shows points shaved (≈ = credible · −N = discounted).`
        : 'Optimism Index (−100…+100) = ½ language tone + ½ the five fundamentals. Switch to “Optimism (Tone discounted)” to mark it down by Q&A confidence. (See Definitions below.)';
  const chip = combo || !!SIGWORD[metric];
  return `<div class="panel"><h3>Cycle — ${lbl} by company × quarter</h3>
    <div class="mkbar" style="margin:0 0 10px"><div class="seggrp"><span class="seglbl">Signal</span>${msel}</div></div>
    <table class="cyctab"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>
    <div class="dim" style="font-size:11px;margin-top:8px">${note} · green = optimistic · red = negative · deeper = stronger${chip ? ' · ≈/−N chip = pts shaved by weak Q&A candor' : ''} · blank = n/a.</div></div>`;
}

/* Lens C — Divergence & inflection radar (the alpha) */
function sigRadarBody(S, sparks) {
  const nm = tk => (S.companies.find(c => c.ticker === tk) || {}).name || tk;
  // inflections: pricing/sentiment/demand sign-cross or strong momentum
  const inflx = [];
  ['pricing', 'sentiment', 'demand'].forEach(sig => {
    S.companies.forEach(c => {
      const ser = S.periods.map(p => S.facts.find(f => f.ticker === c.ticker && f.period === p && f.signal === sig && f.segment === 'overall'))
        .filter(f => f && f.value != null);
      for (let i = 1; i < ser.length; i++) {
        const a = ser[i - 1].value, b = ser[i].value;
        if (a < 0 && b >= 0) inflx.push({ dir: 'up', t: `${nm(c.ticker)} · ${sig} turned up`, d: `${ser[i - 1].label} → ${ser[i].label} at ${qLabel(ser[i].period)}` });
        else if (a >= 0 && b < 0) inflx.push({ dir: 'down', t: `${nm(c.ticker)} · ${sig} rolled over`, d: `${ser[i - 1].label} → ${ser[i].label} at ${qLabel(ser[i].period)}` });
      }
      if (ser.length >= 3 && ser[ser.length - 1].value - ser[0].value >= 2) inflx.push({ dir: 'up', t: `${nm(c.ticker)} · ${sig} accelerating`, d: `${ser[0].label} → ${ser[ser.length - 1].label} across ${ser.length} quarters` });
    });
  });
  // divergences: segment demand where companies disagree
  const segs = {};
  S.facts.filter(f => f.signal === 'demand' && f.segment !== 'overall').forEach(f => { (segs[f.segment] = segs[f.segment] || []).push(f); });
  const divs = [];
  Object.entries(segs).forEach(([seg, arr]) => {
    if (arr.length < 2) return;
    const hi = arr.filter(f => f.value >= 1).map(f => nm(f.ticker)), lo = arr.filter(f => f.value <= -1).map(f => nm(f.ticker));
    if (hi.length && lo.length) divs.push({ seg, hi, lo });
  });
  const inflHTML = inflx.length ? inflx.map(x => `<div class="radrow ${x.dir}"><b>${x.dir === 'up' ? '▲' : '▼'} ${x.t}</b><span class="dim">${x.d}</span></div>`).join('') : '<div class="dim">No sign-crossing inflections in the window.</div>';
  const divHTML = divs.length ? divs.map(d => `<div class="radrow warn"><b>⚠ ${d.seg.replace('_', '-').toUpperCase()} — split read</b><span class="dim">strong: ${d.hi.join(', ')} · soft: ${d.lo.join(', ')}</span></div>`).join('') : '<div class="dim">No cross-company divergences in the segments captured.</div>';
  // Credibility-adjusted tone: continuous Tone Index (-100..+100) discounted by Q&A confidence
  const seg = (v, solid) => { const cc = v >= 0 ? '#16a34a' : '#dc2626'; const w = Math.abs(v) / 100 * 50, left = v >= 0 ? 50 : 50 - w; return `left:${left}%;width:${w}%;background:${cc};opacity:${solid ? 1 : 0.28}`; };
  const cred = S.calls.map((c, i) => {
    const tone = toneIndex(c), adj = Math.round(tone * c.confidence), disc = tone - adj;
    const pct = Math.round(c.confidence * 100), cc = c.confidence >= 0.9 ? '#16a34a' : c.confidence >= 0.82 ? '#f59e0b' : '#dc2626';
    const ct = c.conftrend || [], sid = 'cf' + i;
    const soft = Object.values(c.signals || {}).some(l => l === 'soft' || l === 'negative');
    const flag = tone >= 60 && (c.confidence < 0.85 || soft);
    const arr = ct.length > 1 ? (ct[ct.length - 1][1] > ct[ct.length - 2][1] ? '<span style="color:#16a34a">↑</span>' : ct[ct.length - 1][1] < ct[ct.length - 2][1] ? '<span style="color:#dc2626">↓ slipping</span>' : '→') : '';
    if (ct.length > 1) sparks.push({ id: sid, trend: ct, range: [0.4, 1], pct: true });
    return { c, tone, adj, disc, pct, cc, sid, ct, flag, arr };
  }).sort((a, b) => b.adj - a.adj).map(r => {
    const c = r.c, sgn = v => (v >= 0 ? '+' : '') + v;
    return `<div class="credrow">
      <div class="credhd"><span class="lyr-dot" style="background:${LAYER_COLORS[c.layer]}"></span><b>${c.name}</b>
        ${r.flag ? '<span class="redflag">⚑ tone &gt; fundamentals / hedged</span>' : ''}
        <span class="credconf" style="margin-left:auto">Q&amp;A conf <b style="color:${r.cc}">${r.pct}% ${r.arr}</b></span>
        ${r.ct.length > 1 ? `<span class="credspark" id="${r.sid}"></span>` : ''}</div>
      <div class="tonewrap">
        <span class="tonebar"><span class="zero"></span><span class="tseg" style="${seg(r.tone, false)}"></span><span class="tseg" style="${seg(r.adj, true)}"></span></span>
        <span class="tonenum">Tone <b>${sgn(r.tone)}</b> → <b style="color:${r.adj >= 0 ? '#16a34a' : '#dc2626'}">${sgn(r.adj)}</b> <span class="dim">(discounted ${r.disc})</span></span></div>
      <div class="creddodge">Dodged: ${(c.evasion || []).join(' · ') || '—'}</div></div>`;
  }).join('');
  const finale = S.callouts.map(x => `<div class="callout">${x}</div>`).join('');
  return `<div class="grid2">
    <div class="panel"><h3>⟳ Inflections — signals that just turned</h3>${inflHTML}<div class="dim" style="font-size:11px;margin-top:6px">Turning points are where the alpha is: a signal crossing zero (e.g., memory pricing) leads the move.</div></div>
    <div class="panel"><h3>⚔ Divergences — where the chain disagrees</h3>${divHTML}<div class="dim" style="font-size:11px;margin-top:6px">When layers/companies split on the same end-market, that tension is the signal worth chasing.</div></div>
  </div>
  <div class="panel"><h3>🛈 Credibility-adjusted tone — should we discount the optimism?</h3>
    <div class="dim" style="font-size:12px;margin-bottom:10px"><b>Tone (−100…+100)</b> = 0.45 × language tone + 0.40 × the five fundamentals + 0.15 × net theme direction. <b>Adjusted = Tone × Q&A confidence</b> — marking optimism down by how candid management was. Faded bar = raw tone; solid = trust-adjusted; the gap is the discount. Sorted by adjusted tone. <i>(Derived from structured signals, not word-level NLP — see note below.)</i></div>
    ${cred}</div>
  <div class="panel jfinale"><h3>The synthesis — what the whole chain corroborates</h3>${finale}</div>`;
}

/* boot */
const _grab = async (key, file) => {
  if (window.EMI && window.EMI[key]) return window.EMI[key];           // embedded (open index.html directly, no server)
  try { return await (await fetch(file, { cache: 'no-store' })).json(); } catch (e) { return null; }  // served over HTTP
};
async function boot() {
  DATA = await _grab('data', 'data.json');
  if (!DATA) { document.getElementById('main').innerHTML = `<div class="loading">No data found. Rebuild the bundle:<br><code>python scripts/bundle.py</code><br>then re-open <code>web/index.html</code>.</div>`; return; }
  DATA.companies.forEach(c => { c.qi = {}; (c.q.calq || []).forEach((q, i) => c.qi[q] = i); });
  MARKET = await _grab('market', 'market.json');
  SIGNALS = await _grab('signals', 'transcripts.json');
  document.getElementById('asof').textContent = DATA.as_of || '—';
  document.getElementById('m-close').onclick = closeModal;
  document.getElementById('scrim').onclick = closeModal;
  document.querySelectorAll('.tab').forEach(t => t.onclick = () => { STATE.view = t.dataset.tab; render(); });
  window.addEventListener('resize', () => charts.forEach(c => { try { c.resize(); } catch (e) {} }));
  render();
}
boot();
