/* EMI News & Trends — analysis-first renderer for window.NEWS (scripts/news/build_news.py) */
(function () {
  "use strict";
  var N = window.NEWS;
  var main = document.getElementById("main");
  var STATE = { open: -1, concept: null, angle: null, tree: { supply: true }, view: "feed" };
  var ANGLEL = {};
  ((window.NEWS && window.NEWS.angles) || []).forEach(function (a) { ANGLEL[a.id] = a.label; });

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }
  function ageStr(h) { if (h == null) return ""; if (h < 1) return "just now"; if (h < 24) return Math.round(h) + "h ago"; return Math.round(h / 24) + "d ago"; }

  var tip = document.getElementById("ctip");
  if (!tip) { tip = document.createElement("div"); tip.id = "ctip"; document.body.appendChild(tip); }
  function showTip(html, ev) { tip.innerHTML = html; tip.style.display = "block"; var x = ev.clientX + 14, y = ev.clientY + 16; if (x + 300 > innerWidth) x = ev.clientX - 312; tip.style.left = x + "px"; tip.style.top = y + "px"; }
  function hideTip() { tip.style.display = "none"; }

  var DIR = {
    tailwind: { c: "dir-tailwind", i: "↑", t: "Tailwind", d: "Good for a distributor — rising component demand, pricing power, or new design-ins." },
    headwind: { c: "dir-headwind", i: "↓", t: "Headwind", d: "Bad for a distributor — softening demand/prices, or a shrinking addressable market." },
    watch: { c: "dir-watch", i: "•", t: "Watch", d: "Mixed or uncertain — could break either way; worth monitoring." }
  };

  // ---- sparkline ----
  function spark(arr, color) {
    if (!arr || arr.length < 2) return "";
    var w = 60, h = 16, max = Math.max.apply(null, arr), min = Math.min.apply(null, arr), rng = (max - min) || 1;
    var pts = arr.map(function (v, i) { return ((i / (arr.length - 1)) * (w - 2) + 1).toFixed(1) + "," + (h - 1 - ((v - min) / rng) * (h - 3)).toFixed(1); }).join(" ");
    return '<svg width="' + w + '" height="' + h + '"><polyline points="' + pts + '" fill="none" stroke="' + (color || "var(--blue)") + '" stroke-width="1.4"/></svg>';
  }

  // ---- theme cards ----
  function evRows(indices) {
    return (indices || []).slice(0, 8).map(function (i) {
      var it = N.items[i]; if (!it) return "";
      var trk = (it.days_seen > 1) ? ' · <span class="ev-track">tracked ' + it.days_seen + "d</span>" : "";
      return '<a class="evrow" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer"><span class="ev-dot"></span><span class="ev-tt">' + esc(it.title) + '</span><span class="ev-src">' + esc(it.sources[0]) + " · " + (it.date ? esc(it.date) : '<i class="undated">undated</i>') + trk + "</span></a>";
    }).join("");
  }
  function themeCard(t, i) {
    var d = DIR[t.direction] || DIR.watch;
    var open = STATE.open === i;
    var conf = (t.confidence && CONFLBL[t.confidence]) ? '<span class="tc-conf cf-' + t.confidence + '">' + CONFLBL[t.confidence] + "</span>" : "";
    var angc = (t.angles || []).map(function (a) { return '<span class="tc-ang">' + esc(ANGLEL[a] || a) + "</span>"; }).join("");
    var aff = [].concat((t.affected && t.affected.companies) || [], (t.affected && t.affected.end_markets) || []);
    var body = "";
    if (open) {
      body = '<div class="tc-body">' +
        ((t.customer_track || t.supplier_track) ? '<div class="tc-lbl">Talk tracks</div>' +
          (t.customer_track ? '<div class="tc-track tt-cust"><b>Say to customer</b>' + esc(t.customer_track) + "</div>" : "") +
          (t.supplier_track ? '<div class="tc-track tt-sup"><b>Tell supplier</b>' + esc(t.supplier_track) + "</div>" : "") : "") +
        ((t.why && t.why.length) ? '<div class="tc-lbl">Why (drivers)</div><ul class="tc-drv">' + t.why.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" : "") +
        (t.risk ? '<div class="tc-lbl">Risk to this call</div><div class="tc-risk">' + esc(t.risk) + "</div>" : "") +
        (aff.length ? '<div class="tc-lbl">Affected</div><div class="tc-aff">' + aff.map(function (a) { return '<span class="chip">' + esc(a) + "</span>"; }).join("") + "</div>" : "") +
        '<div class="tc-lbl">Evidence (' + (t.items ? t.items.length : 0) + ')</div><div class="tc-evid">' + evRows(t.items) + "</div></div>";
    }
    return '<div class="tcard d-' + esc(t.direction) + (open ? " open" : "") + '" data-theme="' + i + '">' +
      '<div class="tc-top"><span class="tc-dir ' + d.c + '" data-dir="' + t.direction + '">' + d.i + " " + d.t + "</span>" + conf +
      (t.corrob_types ? '<span class="tc-corr">✓ ' + t.corrob_types + " source type" + (t.corrob_types > 1 ? "s" : "") + "</span>" : "") +
      (t.thin ? '<span class="tc-thin">⚠ thinly sourced</span>' : "") +
      '<span class="tc-angs">' + angc + "</span></div>" +
      '<div class="tc-headline">' + esc(t.headline) + "</div>" +
      (t.so_what ? '<div class="tc-sowhat">' + esc(t.so_what) + "</div>" : "") +
      (t.action ? '<div class="tc-line tc-act"><b>Act</b>' + esc(t.action) + "</div>" : "") +
      (t.watch ? '<div class="tc-line tc-watch"><b>Watch</b>' + esc(t.watch) + "</div>" : "") +
      '<div class="tc-foot"><span class="tc-vol"><b>' + (t.volume || 0) + "</b> stories</span>" +
      '<span class="tc-expand">' + (open ? "hide detail ▲" : "why · risk · evidence ▾") + "</span></div>" + body + "</div>";
  }
  var CONFLBL = { high: "high confidence", moderate: "moderate confidence", low: "low confidence" };

  // ---- treemap (recursive longest-edge split — good aspect ratios) ----
  function layout(items, x, y, w, h) {
    if (!items.length) return;
    if (items.length === 1) { items[0].rect = { x: x, y: y, w: w, h: h }; return; }
    var total = items.reduce(function (s, it) { return s + it.value; }, 0), half = total / 2, acc = 0, idx = 0;
    for (var i = 0; i < items.length; i++) { if (acc + items[i].value > half && i > 0) break; acc += items[i].value; idx = i; }
    var g1 = items.slice(0, idx + 1), g2 = items.slice(idx + 1);
    if (!g2.length) { g2 = [g1.pop()]; }
    var s1 = g1.reduce(function (s, it) { return s + it.value; }, 0), frac = s1 / total;
    if (w >= h) { var w1 = w * frac; layout(g1, x, y, w1, h); layout(g2, x + w1, y, w - w1, h); }
    else { var h1 = h * frac; layout(g1, x, y, w, h1); layout(g2, x, y + h1, w, h - h1); }
  }
  var SENTLBL = { tailwind: "Tailwind — good for a distributor", headwind: "Headwind — bad for a distributor", watch: "Watch — mixed / uncertain", neutral: "Neutral — no clear read yet" };
  function tileColor(c) {
    switch (c.sentiment) {                       // muted diverging (consulting-exhibit tones)
      case "tailwind": return ["#d4e7dd", "#15543a"];
      case "headwind": return ["#ecd9d2", "#8a3a28"];
      case "watch": return ["#ece3cc", "#7a5a1c"];
      default: return ["#e8eaee", "#516072"];
    }
  }
  var TMGROUPS = [
    { type: "comp", label: "Components", bg: "#f6f4fe", tx: "#6d28d9" },
    { type: "company", label: "Suppliers & makers", bg: "#eff6ff", tx: "#1d4ed8" },
    { type: "em", label: "End-markets", bg: "#ecfdf5", tx: "#047857" },
    { type: "theme", label: "Themes", bg: "#fff7ed", tx: "#b45309" }
  ];
  function tilesIn(concepts, x, y, w, h, out) {
    var data = concepts.map(function (c) { return { c: c, value: c.count }; });
    layout(data, x, y, w, h);
    data.forEach(function (d) {
      var r = d.rect, col = tileColor(d.c), big = r.w > 56 && r.h > 28;
      var arrow = (d.c.verdict === "rising" || d.c.verdict === "breaking") ? " ▲" : d.c.verdict === "cooling" ? " ▼" : "";
      var cap = Math.floor(r.w / 7.4), nm = esc(d.c.label);
      if (nm.length > cap) nm = nm.slice(0, Math.max(3, cap - 1)) + "…";
      var newt = d.c.is_new ? '<tspan font-size="9.5" fill="#b91c1c"> NEW</tspan>' : "";
      var label = big ? '<text x="' + (r.x + 7) + '" y="' + (r.y + 16) + '" font-size="12" font-weight="700" fill="' + col[1] + '">' + nm + newt + "</text>" +
        '<text x="' + (r.x + 7) + '" y="' + (r.y + 31) + '" font-size="10.5" fill="' + col[1] + '">' + d.c.count + arrow + "</text>" : "";
      out.push('<g class="tile" data-key="' + esc(d.c.key) + '" data-label="' + esc(d.c.label) + '" data-count="' + d.c.count + '" data-sent="' + (d.c.sentiment || "neutral") + '" data-verdict="' + (d.c.verdict || "") + '" style="cursor:pointer"><rect x="' + (r.x + 1).toFixed(1) + '" y="' + (r.y + 1).toFixed(1) + '" width="' + Math.max(0, r.w - 2).toFixed(1) + '" height="' + Math.max(0, r.h - 2).toFixed(1) + '" rx="3" fill="' + col[0] + '"/>' + label + "</g>");
    });
  }
  function treemapSVG(concepts) {
    var W = 1000, H = 380, HDR = 21, G = 6;
    var groups = TMGROUPS.map(function (gd) {
      var cs = concepts.filter(function (c) { return c.type === gd.type; }).sort(function (a, b) { return b.count - a.count; });
      return { gd: gd, cs: cs, value: cs.reduce(function (s, c) { return s + c.count; }, 0) };
    }).filter(function (gr) { return gr.cs.length; });
    if (!groups.length) return "";
    var gw = groups.map(function (gr) { return { gr: gr, value: gr.value }; });
    layout(gw, 0, 0, W, H);
    var parts = [];
    gw.forEach(function (w) {
      var r = w.rect, gd = w.gr.gd, hx = r.x + G / 2 + 10, hy = r.y + G / 2 + 15;
      parts.push('<rect x="' + (r.x + G / 2).toFixed(1) + '" y="' + (r.y + G / 2).toFixed(1) + '" width="' + (r.w - G).toFixed(1) + '" height="' + (r.h - G).toFixed(1) + '" rx="6" fill="#fbfcfd" stroke="#e5e8ec"/>' +
        '<text x="' + hx + '" y="' + hy + '" font-size="10.5" font-weight="700" letter-spacing="0.07em" fill="#334155">' + esc(gd.label.toUpperCase()) +
        '<tspan fill="#aab2bd" font-weight="400">  ' + w.gr.value + "</tspan></text>" +
        '<line x1="' + hx + '" y1="' + (hy + 7) + '" x2="' + (r.x + r.w - G / 2 - 8) + '" y2="' + (hy + 7) + '" stroke="#eef1f4"/>');
      tilesIn(w.gr.cs, r.x + G / 2 + 6, r.y + G / 2 + HDR + 6, r.w - G - 12, r.h - G - HDR - 12, parts);
    });
    return '<svg viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="xMidYMid meet">' + parts.join("") + "</svg>";
  }

  // ---- themeriver (streamgraph, silhouette baseline) ----
  var RIVERCOL = ["#2f5f86", "#3f8e76", "#b07a4e", "#7d6fa0", "#a05f6a", "#8a7a3a", "#5f7a8a"];
  function riverSVG(river) {
    var days = river.days || [], series = river.series || [];
    if (days.length < 3) {
      return '<div class="river-note"><i class="ti"></i>ThemeRiver fills in as the daily build accumulates history — <b>' + days.length + ' day' + (days.length === 1 ? "" : "s") + '</b> so far. Concept momentum (rising/cooling) needs ~3 days; check back after a few daily runs.</div>';
    }
    var W = 1000, H = 200, pad = 24, n = days.length;
    var xs = days.map(function (_, i) { return pad + (i / (n - 1)) * (W - 2 * pad); });
    var totals = days.map(function (_, di) { return series.reduce(function (s, ser) { return s + (ser.values[di] || 0); }, 0); });
    var maxTot = Math.max.apply(null, totals.concat([1]));
    var sc = (H - 2 * pad) / maxTot;
    var base = days.map(function (_, di) { return H / 2 + (totals[di] * sc) / 2; });
    var cum = days.map(function () { return 0; });
    var polys = series.map(function (ser, si) {
      var top = [], bot = [];
      for (var di = 0; di < n; di++) {
        var y0 = base[di] - cum[di] * sc;
        var y1 = y0 - (ser.values[di] || 0) * sc;
        bot.push(xs[di].toFixed(1) + "," + y0.toFixed(1));
        top.push(xs[di].toFixed(1) + "," + y1.toFixed(1));
        cum[di] += (ser.values[di] || 0);
      }
      var pts = top.concat(bot.reverse()).join(" ");
      return '<polygon points="' + pts + '" fill="' + RIVERCOL[si % RIVERCOL.length] + '" opacity="0.85"><title>' + esc(ser.label) + "</title></polygon>";
    }).join("");
    var leg = series.map(function (ser, si) { return '<span style="white-space:nowrap;margin-right:12px"><i style="color:' + RIVERCOL[si % RIVERCOL.length] + '">●</i> ' + esc(ser.label) + "</span>"; }).join("");
    return '<svg viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="xMidYMid meet">' + polys + "</svg><div class=\"viz-legend\">" + leg + "</div>";
  }

  function conceptEvidence() {
    if (!STATE.concept) return "";
    var its = (N.byEntity[STATE.concept] || []).map(function (i) { return N.items[i]; }).filter(Boolean).slice(0, 8);
    var lbl = (N.labels && N.labels[STATE.concept]) || STATE.concept;
    return '<div class="conc-evid"><div class="ce-h">Evidence for <b>' + esc(lbl) + "</b> (" + its.length + ")</div>" +
      (its.length ? its.map(function (it) { var trk = (it.days_seen > 1) ? ' · <span class="ev-track">tracked ' + it.days_seen + "d</span>" : ""; return '<a class="evrow" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer"><span class="ev-dot"></span><span class="ev-tt">' + esc(it.title) + '</span><span class="ev-src">' + esc(it.sources[0]) + " · " + (it.date ? esc(it.date) : '<i class="undated">undated</i>') + trk + "</span></a>"; }).join("") : '<div class="nempty">No stories.</div>') + "</div>";
  }

  function coverageHTML() {
    var cv = N.coverage; if (!cv) return "";
    function row(title, arr, kind) {
      return '<div class="cov-row"><span class="cov-rlbl">' + title + '</span><div class="cov-chips">' +
        (arr || []).map(function (x) {
          var gap = !x.count;
          var attr = gap ? "" : (kind === "angle" ? ' data-angle="' + x.id + '"' : ' data-cov="' + kind + ":" + x.id + '"');
          return '<span class="cov-chip' + (gap ? " gap" : "") + '"' + attr + ">" + esc(x.label) + "<b>" + x.count + "</b></span>";
        }).join("") + "</div></div>";
    }
    var srcRow = (cv.sources && cv.sources.length) ? '<div class="cov-row"><span class="cov-rlbl">Sources</span><div class="cov-chips">' +
      cv.sources.map(function (s) { return '<span class="cov-chip" style="cursor:default">' + esc(s.label) + "<b>" + s.count + "</b></span>"; }).join("") + "</div></div>" : "";
    return '<div class="sec-title">Coverage check</div><div class="sec-sub">every area the structured scan probed this week — <b>grey = a gap</b>, so market detection stays complete · click to drill</div>' +
      '<div class="cov-panel">' + row("Lenses", cv.angles, "angle") + row("End-markets", cv.end_markets, "em") + row("Geographies", cv.geographies, "geo") + srcRow + "</div>";
  }

  function conflictsHTML() {
    var cf = N.conflicts || [];
    if (!cf.length) return "";
    return '<div class="sec-title">Signal conflicts</div><div class="sec-sub">where this week\'s sources <b>disagree</b> on direction — treat as uncertain, verify before acting</div>' +
      '<div class="conflicts">' + cf.map(function (x) {
        return '<div class="cf-row" data-cov="' + esc(x.key) + '"><span class="cf-lbl">' + esc(x.label) + '</span><span class="cf-bars"><span class="cf-pos">▲ ' + x.pos + " tightening/up</span><span class=\"cf-neg\">▼ " + x.neg + " easing/down</span></span></div>";
      }).join("") + "</div>";
  }

  // ---- daily 3 highlights (top judgments, click to open) ----
  function highlightsHTML() {
    var top = (N.themes || []).slice(0, 3);
    if (!top.length) return "";
    return '<div class="sec-title">Today’s 3 highlights</div><div class="sec-sub">the must-know — click to open the full judgment</div>' +
      '<div class="hl-grid">' + top.map(function (t, i) {
        var d = DIR[t.direction] || DIR.watch;
        return '<div class="hl-card d-' + esc(t.direction) + '" data-theme="' + i + '"><div class="hl-rank">' + (i + 1) + "</div>" +
          '<div class="hl-body"><span class="hl-dir ' + d.c + '">' + d.i + " " + d.t + "</span>" +
          '<div class="hl-headline">' + esc(t.headline) + "</div>" +
          (t.so_what ? '<div class="hl-so">' + esc(t.so_what) + "</div>" : "") +
          '<div class="hl-open">open ↓</div></div></div>';
      }).join("") + "</div>";
  }

  // ---- latest trend + emerging (Exploding-Topics-style metric cards) ----
  var STATUS = { breaking: { l: "Exploding", c: "st-hot" }, rising: { l: "Rising", c: "st-hot" }, steady: { l: "Steady", c: "st-mid" }, active: { l: "Active", c: "st-mid" }, cooling: { l: "Cooling", c: "st-cool" } };
  function trendCard(c, isNew) {
    var s = STATUS[c.verdict] || STATUS.active;
    var col = (c.verdict === "rising" || c.verdict === "breaking") ? "#b91c1c" : (c.verdict === "cooling" ? "#1d4ed8" : "#94a3b8");
    var growth = (c.prev > 0) ? ((c.delta >= 0 ? "+" : "") + Math.round(c.delta * 100) + "%") : "new";
    var gcls = (c.prev > 0 && c.delta < 0) ? "down" : "up";
    var sp = spark(c.spark, col) || '<div class="tcw-flat">— momentum builds over days —</div>';
    return '<div class="trend-card" data-cov="' + esc(c.key) + '">' + (isNew ? '<span class="tcw-new">NEW</span>' : "") +
      '<div class="tcw-top"><span class="tcw-name">' + esc(c.label) + '</span><span class="tcw-status ' + s.c + '">' + s.l + "</span></div>" +
      '<div class="tcw-metrics"><span class="tcw-vol"><b>' + c.count + "</b> stories</span><span class=\"tcw-growth " + gcls + '">' + growth + " growth</span></div>" +
      '<div class="tcw-spark">' + sp + "</div></div>";
  }
  function trendHTML() {
    var cs = (N.concepts || []).slice();
    if (!cs.length) return "";
    var rising = cs.filter(function (c) { return c.verdict === "rising" || c.verdict === "breaking"; }).sort(function (a, b) { return b.delta - a.delta; });
    var list = (rising.length ? rising : cs).slice(0, 8);
    var emerging = cs.filter(function (c) { return c.is_new; });
    return '<div class="sec-title">Latest trend</div><div class="sec-sub">what’s moving — volume, growth vs the 30-day baseline &amp; momentum · click a card to drill</div>' +
      '<div class="trend-grid">' + list.map(function (c) { return trendCard(c, false); }).join("") + "</div>" +
      (emerging.length ? '<div class="trend-emh">Emerging · new vs baseline</div><div class="trend-grid">' + emerging.map(function (c) { return trendCard(c, true); }).join("") + "</div>"
        : '<div class="trend-build">Emerging: building — needs a few days of history to flag what’s genuinely new.</div>');
  }

  // ---- browse by structure (ontology tree) ----
  // the framework as a topic-tree hierarchy: branch (Demand/Supply/Forces/Geography)
  // → group (value-chain stage / region) → leaf (an ontology entity that drills to its
  // stories). p = "rt" (rail, compact) or "tr" (analysis page). Reuses data-branch/data-cov.
  function taxoTree(p) {
    if (!N.taxonomy) return "";
    var lt = p === "rt" ? "button" : "span";
    return N.taxonomy.map(function (b) {
      var open = !!STATE.tree[b.id];
      var body = "";
      if (open) {
        body = '<div class="' + p + '-body">' + b.groups.map(function (g) {
          var leaves = g.leaves.map(function (l) {
            var cls = p + "-leaf" + (STATE.concept === l.cov ? " on" : "") + (l.count ? "" : " muted");
            var nb = p === "rt" ? "<span>" + l.count + "</span>" : "<b>" + l.count + "</b>";
            return "<" + lt + ' class="' + cls + '" data-cov="' + esc(l.cov) + '">' + esc(l.label) + nb + "</" + lt + ">";
          }).join("");
          return '<div class="' + p + '-grp"><div class="' + p + '-glabel">' + esc(g.label) + (g.kicker ? ' <i>' + esc(g.kicker) + "</i>" : "") + "</div><div class=\"" + p + "-gleaves\">" + leaves + "</div></div>";
        }).join("") + "</div>";
      }
      var inner = '<span class="' + p + '-chev">' + (open ? "▾" : "▸") + '</span><span class="' + p + '-name">' + esc(b.label) + "</span>" +
        '<span class="' + p + '-kick">' + esc(b.kicker) + '</span><span class="' + p + '-n">' + b.count + "</span>";
      var head = p === "rt"
        ? '<button class="rt-head" data-branch="' + b.id + '">' + inner + "</button>"
        : '<div class="tr-head" data-branch="' + b.id + '" role="button" tabindex="0">' + inner + "</div>";
      return '<div class="' + p + '-branch' + (open ? " open" : "") + '">' + head + body + "</div>";
    }).join("");
  }
  function treeHTML() {
    if (!N.taxonomy) return "";
    return '<div class="sec-title">Browse by framework</div><div class="sec-sub">the same news as a topic tree — demand · the value chain · market forces · geography</div><div class="tree">' + taxoTree("tr") + "</div>";
  }

  // ---- signal board: the news aggregated as structured data (step 3 — AGGREGATE) ----
  function dirArrows(net) {
    if (net > 0) return '<span class="sg-up">' + new Array(Math.min(net, 4) + 1).join("▲") + "</span>";
    if (net < 0) return '<span class="sg-dn">' + new Array(Math.min(-net, 4) + 1).join("▼") + "</span>";
    return '<span class="sg-fl">▬</span>';
  }
  function signalsHTML() {
    var s = N.signals; if (!s || !s.n_records) return "";
    var maxT = Math.max.apply(null, s.by_type.map(function (t) { return t.count; }).concat([1]));
    var types = s.by_type.map(function (t) {
      var split = (t.up ? '<span class="sg-up">▲' + t.up + "</span>" : "") + (t.down ? ' <span class="sg-dn">▼' + t.down + "</span>" : "");
      return '<div class="sg-trow" title="' + esc(t.ex.join(" · ")) + '"><span class="sg-tlbl">' + esc(t.label) + "</span>" +
        '<span class="sg-bar"><span class="sg-fill" style="width:' + Math.round(t.count / maxT * 100) + '%"></span></span>' +
        '<span class="sg-tn">' + t.count + "</span><span class=\"sg-split\">" + split + "</span></div>";
    }).join("");
    var price = (s.price || []).map(function (p) {
      var sr = (p.series || []).slice(); if (sr.length < 2) sr = [0].concat(sr);
      return '<button class="sg-prow" data-cov="' + esc(p.cov) + '" title="net direction over the window — click for stories">' +
        '<span class="sg-plbl">' + esc(p.label) + "</span>" +
        '<span class="sg-spark">' + spark(sr, p.net >= 0 ? "#15803d" : "#b91c1c") + "</span>" +
        '<span class="sg-dir">' + dirArrows(p.net) + "</span>" +
        '<span class="sg-pn">' + (p.up ? "▲" + p.up : "") + (p.down ? " ▼" + p.down : "") + "</span></button>";
    }).join("") || '<div class="sg-empty">No price / shortage signals in the window yet.</div>';
    var maxC = Math.max.apply(null, (s.capex_by_region || []).map(function (c) { return c.count; }).concat([1]));
    var capex = (s.capex_by_region || []).slice(0, 8).map(function (c) {
      return '<button class="sg-crow" data-cov="' + esc(c.cov) + '" title="capacity / capex events tagged to this region — click for stories">' +
        '<span class="sg-clbl">' + esc(c.label) + "</span>" +
        '<span class="sg-bar"><span class="sg-fill cx" style="width:' + Math.round(c.count / maxC * 100) + '%"></span></span>' +
        '<span class="sg-cn">' + c.count + "</span></button>";
    }).join("") || '<div class="sg-empty">No capex events tagged to a region yet.</div>';
    return '<div class="sec-title">Signal board <span class="dim">the news as structured data</span></div>' +
      '<div class="sec-sub">every major event decomposed into a typed record, then aggregated across the rolling 30-day window — query the fields, not the headlines. ' + s.n_records + ' signal records.</div>' +
      '<div class="sgboard">' +
        '<div class="sg-card"><div class="sg-h">Event-type mix</div><div class="sg-body">' + types + "</div></div>" +
        '<div class="sg-card"><div class="sg-h">Price &amp; supply pressure <span class="dim">by component</span></div><div class="sg-body">' + price + "</div></div>" +
        '<div class="sg-card"><div class="sg-h">Capacity &amp; capex <span class="dim">by region</span></div><div class="sg-body">' + capex + "</div>" +
          '<div class="sg-kpi"><span class="sg-kn">' + s.ma_count + '</span><span class="sg-kl">M&amp;A / investment events in the window</span></div></div>' +
      "</div>";
  }

  // ---- corners: focused desks by domain (map onto the angle lenses) ----
  var CORNERS = [
    { a: "parts", label: "Products", kick: "parts we sell" },
    { a: "demand", label: "End-industries", kick: "who buys" },
    { a: "supplier", label: "Suppliers", kick: "our line-card" },
    { a: "channel", label: "Competitors", kick: "other distributors" },
    { a: "scm", label: "Supply chain", kick: "lead time · allocation" },
    { a: "geopolitics", label: "Geopolitics", kick: "policy · tariffs" },
    { a: "technology", label: "Technology", kick: "roadmap · design-in" },
    { a: "macro", label: "Macro", kick: "cycle · demand" }
  ];
  function cornerName(a) { var c = CORNERS.filter(function (x) { return x.a === a; })[0]; return c ? c.label : a; }
  function cornersHTML() {
    var all = '<button class="corner' + (STATE.angle ? "" : " on") + '" data-angle=""><span class="cr-kick">everything</span><span class="cr-label">All news</span><span class="cr-n">' + (N.themes || []).length + " judgments</span></button>";
    var cards = CORNERS.map(function (cn) {
      var st = (N.byAngle && N.byAngle[cn.a] ? N.byAngle[cn.a].length : 0);
      var ci = N.corner_insights && N.corner_insights[cn.a];
      var kp = ci && ci.points ? ci.points.length : 0;
      return '<button class="corner' + (STATE.angle === cn.a ? " on" : "") + (st ? "" : " quiet") + '" data-angle="' + cn.a + '">' +
        '<span class="cr-kick">' + esc(cn.kick) + '</span><span class="cr-label">' + esc(cn.label) + "</span>" +
        '<span class="cr-n">' + (kp ? kp + " key point" + (kp === 1 ? "" : "s") + " · " : "") + st + " stories</span></button>";
    }).join("");
    return '<div class="sec-title">Corners</div><div class="sec-sub">jump to a focused desk — each is combined from its OWN stories, so the desks differ</div><div class="corners">' + all + cards + "</div>";
  }

  // ---- Techmeme-style story river, in our framework ----
  var TF = [["components", "comp", "f-comp"], ["companies", "company", "f-company"], ["end_markets", "em", "f-em"], ["themes", "theme", "f-theme"], ["geographies", "geo", "f-geo"]];
  function itemTagsFeed(it) {
    var out = "";
    TF.forEach(function (f) { (it.tags[f[0]] || []).forEach(function (id) { var key = f[1] + ":" + id; out += '<span class="chip ' + f[2] + '" data-cov="' + esc(key) + '">' + esc((N.labels && N.labels[key]) || id) + "</span>"; }); });
    return out;
  }
  function feedHTML() {
    var idxs;
    if (STATE.concept && N.byEntity[STATE.concept]) idxs = N.byEntity[STATE.concept];
    else if (STATE.angle && N.byAngle && N.byAngle[STATE.angle]) idxs = N.byAngle[STATE.angle];
    else idxs = N.items.map(function (_, i) { return i; });
    var jmap = {};
    (N.themes || []).forEach(function (t) { (t.items || []).forEach(function (i) { if (jmap[i] == null) jmap[i] = { dir: t.direction, so: t.so_what }; }); });
    var rows = idxs.slice(0, 90).map(function (i) {
      var it = N.items[i]; if (!it) return "";
      var jm = jmap[i], dd = DIR[jm && jm.dir] || null;
      var read = (jm && jm.so) ? '<div class="fd-read d-' + esc(jm.dir) + '"><b>' + (dd ? dd.t : jm.dir) + "</b> " + esc(jm.so) + "</div>" : "";
      var more = (it.n > 1) ? '<div class="fd-more">+ ' + it.n + " reports · " + esc(it.sources.join(", ")) + "</div>" : "";
      var trk = (it.days_seen > 1) ? " · <span class=\"ev-track\">tracked " + it.days_seen + "d</span>" : "";
      var op = Math.min(1, (it.hot || 0) / 85 + 0.3).toFixed(2);
      var head = esc(it.title_en || it.title);
      var dig = it.digest ? '<div class="fd-dig">' + esc(it.digest) + "</div>" : "";
      var typ = it.etype ? '<span class="fd-type">' + esc(it.etype) + "</span>" : "";
      var mdir = it.metric && it.metric.direction;
      var met = (mdir === "up" || mdir === "down") ? '<span class="fd-metric ' + mdir + '">' + (mdir === "up" ? "▲" : "▼") + (it.metric.magnitude ? " " + esc(it.metric.magnitude) : "") + "</span>" : "";
      return '<div class="fd-item" data-i="' + i + '"><span class="fd-dot" style="opacity:' + op + '"></span>' +
        '<div class="fd-body"><div class="fd-headrow"><span class="fd-head">' + head + "</span>" + typ + met + "</div>" +
        '<div class="fd-meta"><span class="fd-src">' + esc(it.sources[0]) + "</span> · " + (it.date ? esc(it.date) : '<i class="undated">undated</i>') + ' · <span class="fd-corr">' + (it.sources ? it.sources.length : 1) + " src</span>" + (it.merged > 1 ? ' · <span class="fd-merged">' + it.merged + " articles</span>" : "") + (it.claims && it.claims.length ? ' · ' + it.claims.length + " facts" : "") + trk + "</div>" +
        dig + '<div class="fd-tags">' + itemTagsFeed(it) + "</div>" + more + "</div></div>";
    }).join("");
    return '<div class="feed">' + (rows || '<div class="nempty">No stories.</div>') + "</div>";
  }
  // left rail: category tiles (corners + the ontology tree) that drive the right pane
  function railHTML() {
    var allOn = (!STATE.angle && !STATE.concept) ? " on" : "";
    var items = '<button class="rail-item' + allOn + '" data-angle=""><span class="ri-label">All news</span><span class="ri-n">' + (N.items || []).length + "</span></button>";
    items += CORNERS.map(function (cn) {
      var n = (N.byAngle && N.byAngle[cn.a] ? N.byAngle[cn.a].length : 0);
      return '<button class="rail-item' + (STATE.angle === cn.a ? " on" : "") + '" data-angle="' + cn.a + '"><span class="ri-label">' + esc(cn.label) + '</span><span class="ri-n">' + n + "</span></button>";
    }).join("");
    // browse-by-framework tree (leaves filter the right pane)
    var tree = taxoTree("rt");
    return '<div class="rail-grp">Corners</div><div class="rail-list">' + items + "</div>" +
      '<div class="rail-grp">Browse by framework</div><div class="rail-tree">' + tree + "</div>";
  }

  function sentColor(s) { return s === "tailwind" ? "#15803d" : s === "headwind" ? "#b91c1c" : "#b45309"; }
  // two scannable highlight cards: the day's defining event + the week's dominant trend.
  // Shown only on the unfiltered landing — when you drill into a desk, its own key points take over.
  function highlightStripHTML(angle) {
    var h = (angle && N.corner_highlights && N.corner_highlights[angle]) ? N.corner_highlights[angle] : N.highlights;
    if (!h || (!h.daily && !h.weekly)) return "";
    var cards = "";
    if (h.daily) {
      var d = h.daily, dd = DIR[d.sentiment] || DIR.watch;
      var m = d.metric || {}, met = (m.direction === "up" || m.direction === "down") ?
        '<span class="hl2-met ' + m.direction + '">' + (m.direction === "up" ? "▲" : "▼") + (m.magnitude ? " " + esc(m.magnitude) : "") + "</span>" : "";
      cards += '<div class="hl2-card d-' + esc(d.sentiment) + '">' +
        '<div class="hl2-kick"><span class="hl2-tag">Today</span><span class="hl2-cap">the defining story</span>' + (d.is_new ? '<span class="hl2-new">new</span>' : "") + "</div>" +
        '<div class="hl2-hl">' + esc(d.headline) + "</div>" +
        '<div class="hl2-meta">' + (d.etype ? '<span class="hl2-type">' + esc(d.etype) + "</span>" : "") + met +
        (d.merged > 1 ? '<span class="hl2-x">' + d.merged + " reports</span>" : "") +
        '<span class="hl2-read ' + dd.c + '">' + dd.i + " " + dd.t + "</span></div></div>";
    }
    if (h.weekly) {
      var w = h.weekly, wd = DIR[w.sentiment] || DIR.watch;
      var sr = (w.spark || []).slice(); if (sr.length < 2) sr = [0].concat(sr);
      cards += '<div class="hl2-card d-' + esc(w.sentiment) + '">' +
        '<div class="hl2-kick"><span class="hl2-tag">This week</span><span class="hl2-cap">the dominant trend</span><span class="hl2-trend">' + esc(w.verdict) + "</span></div>" +
        '<div class="hl2-hl">' + esc(w.label) + (w.headline ? '<span class="hl2-sub">' + esc(w.headline) + "</span>" : "") + "</div>" +
        '<div class="hl2-meta"><span class="hl2-spark">' + spark(sr, sentColor(w.sentiment)) + "</span>" +
        '<span class="hl2-x">' + w.total + " mentions · " + w.days + "d tracked</span>" +
        '<span class="hl2-read ' + wd.c + '">' + wd.i + " " + wd.t + "</span></div></div>";
    }
    return '<div class="hl2">' + cards + "</div>";
  }
  // single contextual bottom line: global when nothing/an entity is selected, the desk's own
  // bottom line when a corner is active (Option A).
  function heroHTML() {
    var text = N.brief, kick = "The big picture";
    if (STATE.angle) {
      var ci = N.corner_insights && N.corner_insights[STATE.angle];
      if (ci && ci.bottom_line) { text = ci.bottom_line; kick = "The big picture · " + cornerName(STATE.angle) + " desk"; }
    }
    if (!text) return "";
    return '<div class="bluf"><div class="bluf-k">' + esc(kick) + '</div><div class="bluf-t">' + esc(text) + "</div></div>";
  }
  function kpRow(headline, dir, so) {
    var d = DIR[dir] || DIR.watch;
    return '<div class="kp-row d-' + esc(dir) + '"><span class="kp-dir ' + d.c + '">' + d.i + '</span><div class="kp-b"><div class="kp-hl">' + esc(headline) + "</div>" + (so ? '<div class="kp-so">' + esc(so) + "</div>" : "") + "</div></div>";
  }
  // per-corner key points: each desk is combined from ITS OWN bucket of atoms (not the global
  // pool sliced by angle), so corners say genuinely different things. Falls back to the global
  // pool only if a desk has no distinct synthesis.
  function keyPointsHTML(angle) {
    if (angle) {
      var ci = N.corner_insights && N.corner_insights[angle];
      if (ci && ci.points && ci.points.length) {
        return '<div class="kp">' +
          '<div class="kp-h">Key points · ' + esc(cornerName(angle)) + ' <span class="dim">combined from this desk’s ' + (ci.n || ci.points.length) + " stories</span></div>" +
          ci.points.map(function (p) { return kpRow(p.headline, p.direction, p.so_what); }).join("") + "</div>";
      }
      var ts = (N.themes || []).filter(function (t) { return (t.angles || []).indexOf(angle) >= 0; });
      if (!ts.length) return "";
      return '<div class="kp"><div class="kp-h">Key points · ' + esc(cornerName(angle)) + ' <span class="dim">combined from all sources</span></div>' +
        ts.slice(0, 6).map(function (t) { return kpRow(t.headline, t.direction, t.so_what); }).join("") + "</div>";
    }
    var all = (N.themes || []);
    if (!all.length) return "";
    return '<div class="kp"><div class="kp-h">Key points today <span class="dim">combined from all sources</span></div>' +
      all.slice(0, 6).map(function (t) { return kpRow(t.headline, t.direction, t.so_what); }).join("") + "</div>";
  }

  function feedView() {
    var lbl = STATE.concept ? ((N.labels && N.labels[STATE.concept]) || STATE.concept) : (STATE.angle ? cornerName(STATE.angle) : null);
    var clear = (STATE.concept || STATE.angle) ? '<button class="fclear" id="feedclear">✕ clear filter</button>' : "";
    return '<div class="split"><aside class="rail">' + railHTML() + "</aside>" +
      '<div class="stream">' +
      (!STATE.concept ? highlightStripHTML(STATE.angle) : "") +
      keyPointsHTML(STATE.angle) +
      '<div class="sec-title">Stories' + (lbl ? ' · <span class="kj-corner">' + esc(lbl) + "</span>" : "") + ' <span class="dim">— sources, de-duplicated</span></div>' +
      '<div class="sec-sub">click a story to open its facts &amp; sources</div>' + clear + feedHTML() + "</div></div>";
  }

  // ---- news detail modal (overlay; keeps the page underneath) ----
  function judgmentFor(i) { var f = null; (N.themes || []).forEach(function (t) { if (f == null && (t.items || []).indexOf(i) >= 0) f = t; }); return f; }
  function relatedItems(i) {
    var it = N.items[i], key = null, M = { components: "comp", companies: "company", themes: "theme", end_markets: "em" };
    ["components", "companies", "themes", "end_markets"].some(function (f) { if (it.tags[f] && it.tags[f].length) { key = M[f] + ":" + it.tags[f][0]; return true; } return false; });
    if (!key || !N.byEntity[key]) return [];
    return N.byEntity[key].filter(function (j) { return j !== i; }).slice(0, 5);
  }
  function escClose(e) { if (e.key === "Escape") closeModal(); }
  function closeModal() { var m = document.getElementById("newsmodal"); if (m) m.remove(); document.body.style.overflow = ""; document.removeEventListener("keydown", escClose); }
  function openModal(i) {
    var it = N.items[i]; if (!it) return;
    closeModal();
    var jm = judgmentFor(i), d = DIR[jm && jm.direction];
    var read = jm ? '<div class="modal-read d-' + esc(jm.direction) + '"><span class="mr-k">Distributor read · ' + (d ? d.t : jm.direction) + "</span>" +
      (jm.so_what ? "<p>" + esc(jm.so_what) + "</p>" : "") +
      (jm.action ? '<div class="mr-line"><b>Act</b> ' + esc(jm.action) + "</div>" : "") +
      (jm.watch ? '<div class="mr-line"><b>Watch</b> ' + esc(jm.watch) + "</div>" : "") + "</div>" : "";
    var rel = relatedItems(i);
    var relHTML = rel.length ? '<div class="modal-relh">Related stories</div><div class="modal-rel">' + rel.map(function (j) {
      var rj = N.items[j]; return '<button class="mrel" data-i="' + j + '"><span class="mrel-t">' + esc(rj.title_en || rj.title) + '</span><span class="mrel-s">' + esc(rj.sources[0]) + (rj.date ? " · " + esc(rj.date) : "") + "</span></button>";
    }).join("") + "</div>" : "";
    var mdir = it.metric && it.metric.direction, sig = "";
    if (it.etype) sig += '<span class="msig-type">' + esc(it.etype) + "</span>";
    if (mdir === "up" || mdir === "down") sig += '<span class="msig-met ' + mdir + '">' + (mdir === "up" ? "▲" : "▼") + (it.metric.magnitude ? " " + esc(it.metric.magnitude) : "") + "</span>";
    (it.subject || []).forEach(function (s) { sig += '<span class="msig-e">' + esc(s) + "</span>"; });
    (it.object || []).forEach(function (o) { sig += '<span class="msig-e obj">' + esc(o) + "</span>"; });
    var sigHTML = sig ? '<div class="modal-sig">' + sig + "</div>" : "";
    var ov = document.createElement("div");
    ov.className = "modal-ov"; ov.id = "newsmodal";
    ov.innerHTML = '<div class="modal" role="dialog" aria-modal="true" aria-label="News detail">' +
      '<button class="modal-x" aria-label="Close">✕</button>' +
      '<div class="modal-meta"><span class="fd-src">' + esc(it.sources[0]) + "</span> · " + (it.date ? esc(it.date) : "undated") +
      ' · <span class="fd-corr">' + (it.sources ? it.sources.length : 1) + " src</span>" + (it.merged > 1 ? ' · <span class="fd-merged">merged ' + it.merged + " articles</span>" : "") + (it.days_seen > 1 ? " · tracked " + it.days_seen + "d" : "") + "</div>" +
      '<a class="modal-head" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">' + esc(it.title_en || it.title) + "</a>" +
      (it.digest ? '<div class="modal-digest">' + esc(it.digest) + "</div>" : "") + sigHTML +
      (it.claims && it.claims.length ? '<div class="modal-factsh">Key facts · de-duplicated</div><ul class="modal-facts">' + it.claims.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" : "") +
      read + '<div class="modal-tags">' + itemTagsFeed(it) + "</div>" + relHTML +
      '<a class="modal-open" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">Open original ↗</a></div>';
    document.body.appendChild(ov); document.body.style.overflow = "hidden";
    ov.onclick = function (e) { if (e.target === ov) closeModal(); };
    ov.querySelector(".modal-x").onclick = closeModal;
    document.addEventListener("keydown", escClose);
    ov.querySelectorAll(".chip[data-cov]").forEach(function (c) { c.onclick = function () { STATE.concept = c.getAttribute("data-cov"); STATE.angle = null; closeModal(); render(); window.scrollTo({ top: 0, behavior: "smooth" }); }; });
    ov.querySelectorAll(".mrel[data-i]").forEach(function (b) { b.onclick = function () { openModal(+b.getAttribute("data-i")); }; });
  }

  function render() {
    var c = N.counts || {}, asof = (N.as_of || "").slice(0, 10);
    var html = '<div class="nhead"><h1>News &amp; Trends</h1><div class="nmeta">week of <b>' + esc(asof) + '</b> · ' + (c.clusters || 0) + ' stories analysed · curated free sources · Sonnet analysis</div></div>';

    // view toggle — Feed (Techmeme river) ↔ Analysis
    html += '<div class="view-tabs"><button class="view-tab' + (STATE.view === "feed" ? " on" : "") + '" data-view="feed">Feed</button>' +
      '<button class="view-tab' + (STATE.view !== "feed" ? " on" : "") + '" data-view="analysis">Analysis</button></div>';

    // BLUF — one bottom line up front (both modes); swaps to the selected desk's bottom line
    html += heroHTML();

    if (STATE.view === "feed") { html += feedView(); main.innerHTML = html; wire(); return; }

    // 2) DAILY 3 HIGHLIGHTS + LATEST TREND + CORNERS
    html += highlightsHTML();
    html += trendHTML();
    html += signalsHTML();
    html += cornersHTML();

    // 3) KEY JUDGMENTS — a DISTINCT synthesis per corner; rich theme cards for "All news"
    var cn = STATE.angle ? cornerName(STATE.angle) : null;
    if (STATE.angle) {
      var ci = N.corner_insights && N.corner_insights[STATE.angle];
      html += '<div class="sec-title">Key judgments · <span class="kj-corner">' + esc(cn) + ' desk</span></div><div class="sec-sub">combined from this desk’s own stories — distinct from the other corners</div>';
      html += keyPointsHTML(STATE.angle);
      var evIdx = (N.byAngle && N.byAngle[STATE.angle]) || [];
      html += '<div class="sec-title2">Stories on this desk <span class="dim">— de-duplicated</span></div>' +
        (evIdx.length ? '<div class="conc-evid">' + evRows(evIdx) + "</div>" : '<div class="nempty">No stories.</div>');
    } else {
      html += '<div class="sec-title">Key judgments</div><div class="sec-sub">ranked assessments — what it means, what to do, what to watch · expand for talk-tracks, drivers &amp; evidence</div>';
      html += '<div class="themes">' + (N.themes || []).map(function (t, i) { return themeCard(t, i); }).join("") + "</div>";
    }

    // signal conflicts (sources disagree) — a credibility/uncertainty check
    html += conflictsHTML();

    // 4) BROWSE BY STRUCTURE — the ontology tree
    html += treeHTML();

    // 5) MARKET LANDSCAPE — descriptive heat map (supporting, not the headline)
    var comps = (N.concepts || []).filter(function (x) { return x.type === "comp"; }).slice(0, 3).map(function (x) { return x.label.split(/[ /&]/)[0].toLowerCase(); });
    var sc = { tailwind: 0, headwind: 0 };
    (N.concepts || []).forEach(function (x) { if (sc[x.sentiment] != null) sc[x.sentiment]++; });
    var lead = sc.tailwind >= sc.headwind ? "tailwinds" : "headwinds";
    var exTitle = comps.length ? ("Coverage concentrates in " + comps.join(", ") + " — and most read as " + lead + " for distributors") : "The components market at a glance";
    html += '<div class="sec-title">Market landscape</div><div class="sec-sub">where this week\'s coverage sits — the evidence behind the judgments above</div>';
    html += '<div class="exhibit"><div class="ex-kick">Exhibit — components market heat map</div>' +
      '<div class="ex-title">' + esc(exTitle) + "</div>" +
      '<div class="ex-sub">Tile size = share of coverage · colour = the distributor read · ▲▼ = week-on-week momentum · click a tile for its stories</div>';
    html += '<div class="tmap">' + treemapSVG(N.concepts || []) + "</div>";
    html += '<div class="viz-legend"><span class="sw sw-tw"></span>tailwind<span class="sw sw-hw"></span>headwind<span class="sw sw-wa"></span>watch<span class="sw sw-ne"></span>neutral</div>';
    html += '<div class="ex-source">Source: curated electronics trade &amp; distribution media (incl. DigiTimes, 国际电子商情, 集微网) · ' + (c.clusters || 0) + " stories · as of " + esc(asof) + "</div></div>";
    html += coverageHTML();
    html += '<div id="concevid">' + conceptEvidence() + "</div>";
    html += '<div class="river-wrap">' + riverSVG(N.river || {}) + "</div>";
    main.innerHTML = html;
    wire();
  }

  function wire() {
    main.querySelectorAll(".view-tab[data-view]").forEach(function (b) {
      b.onclick = function () { STATE.view = b.getAttribute("data-view"); STATE.concept = null; STATE.angle = null; render(); window.scrollTo({ top: 0 }); };
    });
    // feed tag chips filter (must NOT open the story modal)
    main.querySelectorAll(".feed .chip[data-cov]").forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); STATE.concept = b.getAttribute("data-cov"); STATE.angle = null; render(); window.scrollTo({ top: 0, behavior: "smooth" }); };
    });
    // left rail — corners + tree leaves + branch toggles
    main.querySelectorAll(".rail-item[data-angle]").forEach(function (b) {
      b.onclick = function () { STATE.angle = b.getAttribute("data-angle") || null; STATE.concept = null; render(); window.scrollTo({ top: 0 }); };
    });
    main.querySelectorAll(".rt-leaf[data-cov]").forEach(function (b) {
      b.onclick = function () { STATE.concept = b.getAttribute("data-cov"); STATE.angle = null; render(); window.scrollTo({ top: 0 }); };
    });
    main.querySelectorAll(".rt-head[data-branch]").forEach(function (b) {
      b.onclick = function () { var k = b.getAttribute("data-branch"); STATE.tree[k] = !STATE.tree[k]; render(); };
    });
    // feed story → detail modal (keeps the page)
    main.querySelectorAll(".fd-item[data-i]").forEach(function (b) {
      b.onclick = function () { openModal(+b.getAttribute("data-i")); };
    });
    var fcl = document.getElementById("feedclear"); if (fcl) fcl.onclick = function () { STATE.concept = null; STATE.angle = null; render(); };
    main.querySelectorAll(".corner[data-angle], .cov-chip[data-angle]").forEach(function (b) {
      b.onclick = function () { STATE.angle = b.getAttribute("data-angle") || null; STATE.concept = null; STATE.open = -1; render(); var k = main.querySelector(".corners"); if (k) k.scrollIntoView({ behavior: "smooth", block: "start" }); };
    });
    main.querySelectorAll(".cov-chip[data-cov], .cf-row[data-cov], .trend-card[data-cov], .tr-leaf[data-cov], .sg-prow[data-cov], .sg-crow[data-cov]").forEach(function (b) {
      b.onclick = function () { STATE.concept = b.getAttribute("data-cov"); var ce = document.getElementById("concevid"); ce.innerHTML = conceptEvidence(); ce.scrollIntoView({ behavior: "smooth", block: "nearest" }); };
    });
    // daily-3 highlight → open that judgment and scroll to it
    main.querySelectorAll(".hl-card[data-theme]").forEach(function (card) {
      card.onclick = function () { var i = +card.getAttribute("data-theme"); STATE.open = i; render(); var t = main.querySelector('.tcard[data-theme="' + i + '"]'); if (t) t.scrollIntoView({ behavior: "smooth", block: "center" }); };
    });
    // tree branch toggle
    main.querySelectorAll(".tr-head[data-branch]").forEach(function (h) {
      h.onclick = function () { var b = h.getAttribute("data-branch"); STATE.tree[b] = !STATE.tree[b]; render(); };
    });
    main.querySelectorAll(".tcard[data-theme]").forEach(function (card) {
      card.onclick = function (e) { if (e.target.closest("a")) return; var i = +card.getAttribute("data-theme"); STATE.open = (STATE.open === i ? -1 : i); render(); };
    });
    main.querySelectorAll(".tc-dir[data-dir]").forEach(function (b) {
      var d = DIR[b.getAttribute("data-dir")]; if (!d) return;
      b.onmousemove = function (e) { e.stopPropagation(); showTip("<b>" + d.t + "</b><br>" + d.d, e); };
      b.onmouseleave = hideTip;
    });
    main.querySelectorAll(".tile[data-key]").forEach(function (g) {
      g.onclick = function () { STATE.concept = g.getAttribute("data-key"); document.getElementById("concevid").innerHTML = conceptEvidence(); document.getElementById("concevid").scrollIntoView({ behavior: "smooth", block: "nearest" }); };
      g.onmousemove = function (e) {
        var v = g.getAttribute("data-verdict"), mom = (v && v !== "active" && v !== "steady") ? " · " + v : "";
        showTip("<b>" + g.getAttribute("data-label") + "</b><br><span style='color:#64748b'>" + g.getAttribute("data-count") + " stories" + mom + "</span><br>" + (SENTLBL[g.getAttribute("data-sent")] || ""), e);
      };
      g.onmouseleave = hideTip;
    });
  }

  if (!N || !N.themes) { main.innerHTML = '<div class="nempty">News bundle not found. Run <code>python scripts/news/run_news.py</code>.</div>'; return; }
  render();
})();
