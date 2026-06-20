/* EMI hub — inject a live News snapshot (top theme + brief) into the News lens card */
(function () {
  "use strict";
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }
  var el = document.getElementById("newsSnap");
  if (!el) return;
  var N = window.NEWS;
  if (!N || !N.themes || !N.themes.length) { el.innerHTML = '<span class="snap-dim">Run the news build to populate.</span>'; return; }
  var t = N.themes[0];
  var dir = (["tailwind", "headwind", "watch"].indexOf(t.direction) >= 0) ? t.direction : "watch";
  var brief = N.brief ? esc(N.brief.split(/(?<=\.)\s/)[0]) : "";
  el.innerHTML = '<span class="snap-dir ' + dir + '">' + dir + '</span><span class="snap-theme">' + esc(t.headline) + "</span>" +
    (brief ? '<div class="snap-dim" style="margin-top:5px">' + brief + "</div>" : "");
})();
