document.addEventListener("keydown", e => {
  if (e.key === "ArrowLeft") {
    const a = document.querySelector(".nav-prev[href]");
    if (a) location = a.href;
  }
  if (e.key === "ArrowRight") {
    const a = document.querySelector(".nav-next[href]");
    if (a) location = a.href;
  }
});
(function () {
  let x0;
  document.addEventListener("touchstart", e => {
    x0 = e.changedTouches[0].clientX;
  }, { passive: true });
  document.addEventListener("touchend", e => {
    if (x0 == null) return;
    const dx = e.changedTouches[0].clientX - x0;
    x0 = null;
    if (Math.abs(dx) < 50) return;
    const a = document.querySelector(dx > 0 ? ".nav-prev[href]" : ".nav-next[href]");
    if (a) location = a.href;
  }, { passive: true });
})();
