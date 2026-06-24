/* EMI hub — live "as of" stamp + a News snapshot (top theme + brief) in the News lens card */
(function () {
  "use strict";
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }
  var N = window.NEWS;

  // hero status: "as of <date>" from the news bundle (graceful if absent)
  var asof = document.getElementById("asof");
  if (asof) {
    var stamp = N && (N.as_of || N.generated);
    if (stamp) {
      var d = new Date(stamp);
      asof.textContent = isNaN(d) ? String(stamp).slice(0, 10)
        : d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
    } else { asof.textContent = "—"; }
  }

  // live News snapshot
  var el = document.getElementById("newsSnap");
  if (!el) return;
  if (!N || !N.themes || !N.themes.length) { el.innerHTML = '<span class="snap-dim">Run the news build to populate.</span>'; return; }
  var t = N.themes[0];
  var dir = (["tailwind", "headwind", "watch"].indexOf(t.direction) >= 0) ? t.direction : "watch";
  var brief = N.brief ? esc(N.brief.split(/(?<=\.)\s/)[0]) : "";
  el.innerHTML = '<span class="snap-dir ' + dir + '">' + dir + '</span><span class="snap-theme">' + esc(t.headline) + "</span>" +
    (brief ? '<div class="snap-brief">' + brief + "</div>" : "");
})();
