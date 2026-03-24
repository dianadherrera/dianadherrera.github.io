// Share button — only enabled when native share sheet is available
(function () {
  const btn = document.querySelector(".share-btn");
  if (!btn || !navigator.share) return;
  btn.classList.add("supported");
  btn.addEventListener("click", async () => {
    try { await navigator.share({ title: document.title, url: location.href }); } catch {}
  });
})();

// Arrow key navigation — read the site like a book
// → Right: next poem, or go deeper (into collection/chapter/first poem)
// ← Left: previous poem, or go up (breadcrumb parent)
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

  if (e.key === "ArrowLeft") {
    const a = document.querySelector(".nav-prev[href]")
      || document.querySelector(".breadcrumb li:last-child a");
    if (a && a.href !== location.href) {
      location = a.href;
    } else {
      // current page is the breadcrumb link — go up one level
      const items = document.querySelectorAll(".breadcrumb li a");
      if (items.length > 1) location = items[items.length - 2].href;
    }
  }

  if (e.key === "ArrowRight") {
    const a = document.querySelector(".nav-next[href]")
      || document.querySelector(".collection-card")
      || document.querySelector(".toc a[href]")
      || document.querySelector(".home-nav a");
    if (a) location = a.href;
  }
});
