/* EMI shared news widget — lets any page surface entity-relevant news from window.NEWS
   (built by scripts/news/build_news.py). Load news-bundle.js before this.
   Renders the synthesised, English, de-duplicated view: a signal row (direction + count +
   sparkline) + a lead insight (digest) + a few stories, deep-linking back into News. */
(function () {
  "use strict";
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }
  var DIRP = { tailwind: ["↑ Tailwind", "nb-tw"], headwind: ["↓ Headwind", "nb-hw"], watch: ["• Watch", "nb-wa"] };

  function spark(arr, color) {
    arr = (arr || []).filter(function (x) { return typeof x === "number"; });
    if (arr.length < 2) return "";
    var w = 46, h = 16, mx = Math.max.apply(null, arr), mn = Math.min.apply(null, arr), rng = (mx - mn) || 1;
    var pts = arr.map(function (v, i) { return (i / (arr.length - 1) * w).toFixed(1) + "," + (h - (v - mn) / rng * h).toFixed(1); }).join(" ");
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none" aria-hidden="true">' +
      '<polyline points="' + pts + '" fill="none" stroke="' + color + '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }
  function sentColor(s) { return s === "tailwind" ? "#15803d" : s === "headwind" ? "#b91c1c" : "#b45309"; }
  // investor/stock-price framing — keep it out of entity news blocks (it's trader noise)
  var INVESTOR_RX = /\b(overvalued|undervalued|valuation|price target|moving average|top pick|buy rating|sell rating|outperform|underperform|market cap|closed (up|down)|% ytd|year-to-date|wall ?st|stock price|stock quote|share price|shares of|13f|investment management|asset management|capital management)\b|\bstock \(|\b(stock|shares)\b.{0,14}\b(up|down|rose|fell|surg\w*|jump\w*|gain\w*|slump\w*|soar\w*|\d)|\b(acquires?|boosts?|trims?|raises?|cuts?|sells?|buys?)\b[^.]{0,30}\b(shares?|stake|position|holdings?)\b/i;

  window.EMINews = {
    ready: function () { return !!(window.NEWS && window.NEWS.items && window.NEWS.byEntity); },
    asOf: function () { return this.ready() ? (window.NEWS.as_of || "").slice(0, 10) : ""; },
    _concept: function (key) {
      var cs = (this.ready() && window.NEWS.concepts) || [];
      for (var i = 0; i < cs.length; i++) if (cs[i].key === key) return cs[i];
      return null;
    },
    // map a company NAME (e.g. "Micron Technology, Inc.") -> a news key ("company:micron") via labels
    companyKey: function (name) {
      if (!this.ready() || !name) return null;
      var n = " " + String(name).toLowerCase() + " ";
      var alias = { "advanced micro devices": "company:amd", "hon hai": "company:foxconn", "on semiconductor": "company:onsemi" };
      for (var a in alias) if (n.indexOf(a) >= 0) return alias[a];
      var lab = window.NEWS.labels || {}, best = null, blen = 0;
      Object.keys(lab).forEach(function (k) {
        if (k.indexOf("company:") !== 0) return;
        var L = String(lab[k]).toLowerCase();
        if (L.length >= 3 && n.indexOf(L) >= 0 && L.length > blen) { best = k; blen = L.length; }
      });
      return best;
    },
    // de-duplicated items across the keys — investor noise dropped, then ranked so stories that
    // actually NAME the entity come first (avoids a TI-stock story leading the NXP block), then by hot
    items: function (keys, n) {
      if (!this.ready()) return [];
      var lab = window.NEWS.labels || {};
      var labels = (keys || []).map(function (k) { return String(lab[k] || "").toLowerCase(); }).filter(function (s) { return s.length >= 3; });
      // OTHER company names (len>=4, not this entity) — used to spot a story about someone else
      var others = [];
      Object.keys(lab).forEach(function (k) {
        if (k.indexOf("company:") !== 0) return;
        var L = String(lab[k]).toLowerCase();
        if (L.length >= 4 && labels.indexOf(L) < 0) others.push(L);
      });
      // 2 = names the entity · 1 = generic but relevant · 0 = clearly about a DIFFERENT company
      function rel(it) {
        var t = (String(it.title_en || it.title || "") + " " + (it.subject || []).join(" ")).toLowerCase();
        if (labels.some(function (l) { return t.indexOf(l) >= 0; })) return 2;
        return others.some(function (l) { return t.indexOf(l) >= 0; }) ? 0 : 1;
      }
      var seen = {}, out = [];
      (keys || []).forEach(function (k) {
        (window.NEWS.byEntity[k] || []).forEach(function (i) {
          var it = window.NEWS.items[i];
          if (seen[i] || INVESTOR_RX.test(it.title_en || it.title || "")) return;
          seen[i] = 1; out.push(it);
        });
      });
      out.sort(function (a, b) { var r = rel(b) - rel(a); return r !== 0 ? r : b.hot - a.hot; });
      return out.slice(0, n || 6);
    },
    // a compact entity signal: {n, dir, top, spark} or null
    signal: function (keys) {
      var its = this.items(keys, 50);
      if (!its.length) return null;
      var c = null;
      (keys || []).some(function (k) { c = this._concept(k); return !!c; }.bind(this));
      return { n: its.length, dir: c ? c.sentiment : null, top: its[0], spark: c ? c.spark : null };
    },
    // HTML for a compact news card; "" if nothing relevant. linkKey deep-links into News.
    block: function (keys, title, n) {
      var its = this.items(keys, n || 4);
      if (!its.length) return "";
      var top = its[0], c = null;
      for (var i = 0; i < (keys || []).length; i++) { c = this._concept(keys[i]); if (c) break; }
      var dd = (c && DIRP[c.sentiment]) || null;
      var link = "news.html?focus=" + encodeURIComponent((keys || [])[0] || "");
      var h = '<div class="newsblock"><div class="nb-h">' + esc(title || "In the news") +
        '<a class="nb-more" href="' + link + '">open ↗</a></div>';
      h += '<div class="nb-sig">' + (dd ? '<span class="nb-dir ' + dd[1] + '">' + dd[0] + "</span>" : "") +
        '<span class="nb-n">' + its.length + " stor" + (its.length === 1 ? "y" : "ies") + "</span>" +
        ((c && c.spark) ? '<span class="nb-spark">' + spark(c.spark, sentColor(c.sentiment)) + "</span>" : "") + "</div>";
      h += '<div class="nb-lead">' + esc(top.title_en || top.title) + "</div>";
      if (top.digest) h += '<div class="nb-so">' + esc(top.digest) + "</div>";
      its.slice(1, 4).forEach(function (it) {
        h += '<a class="nb-item" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">' +
          '<span class="nb-dot"></span><span class="nb-tt">' + esc(it.title_en || it.title) + "</span>" +
          '<span class="nb-src">' + esc(it.sources[0]) + "</span></a>";
      });
      h += '<div class="nb-foot">as of ' + esc(this.asOf()) + " · curated free sources · click to open in News</div></div>";
      return h;
    }
  };
})();
