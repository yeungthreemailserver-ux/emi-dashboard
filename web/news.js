/* EMI News & Trends — analysis-first renderer for window.NEWS (scripts/news/build_news.py) */
(function () {
  "use strict";
  var N = window.NEWS;
  var main = document.getElementById("main");
  var STATE = { open: -1, concept: null, angle: null };
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
      '<div class="tc-top"><span class="tc-dir ' + d.c + '" data-dir="' + t.direction + '">' + d.i + " " + d.t + "</span>" + conf + '<span class="tc-angs">' + angc + "</span></div>" +
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

  function render() {
    var c = N.counts || {}, asof = (N.as_of || "").slice(0, 10);
    var html = '<div class="nhead"><h1>News &amp; Trends</h1><div class="nmeta">week of <b>' + esc(asof) + '</b> · ' + (c.clusters || 0) + ' stories analysed · curated free sources · Sonnet analysis</div></div>';

    // 1) BLUF — bottom line up front
    if (N.brief) html += '<div class="bluf"><div class="bluf-k">Bottom line</div><div class="bluf-t">' + esc(N.brief) + "</div></div>";

    // 2) KEY JUDGMENTS — the analysis (so-what + act + watch + talk-tracks), leads the page
    html += '<div class="sec-title">Key judgments</div><div class="sec-sub">ranked assessments for a distributor — what it means, what to do, what to watch · expand for talk-tracks, drivers &amp; evidence</div>';
    // angle filter bar (the 360° lenses)
    var jang = {};
    (N.themes || []).forEach(function (t) { (t.angles || []).forEach(function (a) { jang[a] = (jang[a] || 0) + 1; }); });
    var angBtns = '<button class="angle-chip' + (STATE.angle ? "" : " on") + '" data-angle="">All <span>' + (N.themes || []).length + "</span></button>";
    (N.angles || []).forEach(function (a) { if (jang[a.id]) angBtns += '<button class="angle-chip' + (STATE.angle === a.id ? " on" : "") + '" data-angle="' + a.id + '">' + esc(a.label) + " <span>" + jang[a.id] + "</span></button>"; });
    html += '<div class="angle-bar">' + angBtns + "</div>";
    var vis = STATE.angle ? (N.themes || []).filter(function (t) { return (t.angles || []).indexOf(STATE.angle) >= 0; }) : (N.themes || []);
    html += '<div class="themes">' + vis.map(function (t) { return themeCard(t, (N.themes || []).indexOf(t)); }).join("") + "</div>";

    // 3) MARKET LANDSCAPE — descriptive heat map (supporting, not the headline)
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
    main.querySelectorAll(".angle-chip[data-angle], .cov-chip[data-angle]").forEach(function (b) {
      b.onclick = function () { STATE.angle = b.getAttribute("data-angle") || null; STATE.open = -1; render(); window.scrollTo({ top: 0, behavior: "smooth" }); };
    });
    main.querySelectorAll(".cov-chip[data-cov]").forEach(function (b) {
      b.onclick = function () { STATE.concept = b.getAttribute("data-cov"); var ce = document.getElementById("concevid"); ce.innerHTML = conceptEvidence(); ce.scrollIntoView({ behavior: "smooth", block: "nearest" }); };
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
