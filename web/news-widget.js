/* EMI shared news widget — lets any page surface entity-relevant headlines from
   window.NEWS (built by scripts/news/build_news.py). Load news-bundle.js before this. */
(function () {
  "use strict";
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }

  window.EMINews = {
    ready: function () { return !!(window.NEWS && window.NEWS.items && window.NEWS.byEntity); },
    asOf: function () { return this.ready() ? (window.NEWS.as_of || "").slice(0, 10) : ""; },
    // de-duplicated, hotness-sorted items across the given entity keys (e.g. ["geo:cn","company:tsmc"])
    items: function (keys, n) {
      if (!this.ready()) return [];
      var seen = {}, out = [];
      (keys || []).forEach(function (k) {
        (window.NEWS.byEntity[k] || []).forEach(function (i) { if (!seen[i]) { seen[i] = 1; out.push(window.NEWS.items[i]); } });
      });
      out.sort(function (a, b) { return b.hot - a.hot; });
      return out.slice(0, n || 5);
    },
    // returns an HTML string for a compact "Latest news" card, or "" if nothing relevant
    block: function (keys, title, n) {
      var its = this.items(keys, n || 5);
      if (!its.length) return "";
      var h = '<div class="newsblock"><div class="nb-h">' + esc(title || "In the news") +
        '<a class="nb-more" href="news.html">all news ↗</a></div>';
      its.forEach(function (it, idx) {
        h += '<a class="nb-item" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">' +
          '<span class="nb-dot"></span><span class="nb-tt">' + esc(it.title) + '</span>' +
          '<span class="nb-src">' + esc(it.sources[0]) + '</span></a>';
        if (idx === 0 && it.so_what) h += '<div class="nb-so"><b>Distributor read:</b> ' + esc(it.so_what) + '</div>';
      });
      h += '<div class="nb-foot">as of ' + esc(this.asOf()) + ' · curated free sources</div></div>';
      return h;
    }
  };
})();
