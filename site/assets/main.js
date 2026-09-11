// SPDX-License-Identifier: CC-BY-SA-4.0
// Progressive enhancement only. The page reads completely without this file.
(() => {
  "use strict";

  const root = document.documentElement;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const hasScrollTimelines = CSS.supports("animation-timeline", "scroll()");

  // Engines without CSS scroll timelines get the same thread motion from two
  // custom properties: --p (page progress) and --hero-p (hero weave).
  if (!hasScrollTimelines && !reduced.matches) {
    let queued = false;
    const update = () => {
      const max = root.scrollHeight - innerHeight;
      const p = max > 0 ? Math.min(1, Math.max(0, scrollY / max)) : 1;
      const heroP = Math.min(1, Math.max(0, scrollY / (innerHeight * 0.7)));
      root.style.setProperty("--p", p.toFixed(4));
      root.style.setProperty("--hero-p", heroP.toFixed(4));
      queued = false;
    };
    addEventListener("scroll", () => {
      if (!queued) { queued = true; requestAnimationFrame(update); }
    }, { passive: true });
    addEventListener("resize", update);
    update();
  }

  // Copy the quick-start commands.
  const button = document.getElementById("copy");
  const block = document.getElementById("quickstart");
  const status = document.getElementById("copy-status");
  button?.addEventListener("click", async () => {
    if (!block) return;
    try {
      await navigator.clipboard.writeText(block.innerText.trim());
      button.textContent = "Copied";
      if (status) status.textContent = "Commands copied to the clipboard.";
    } catch {
      const range = document.createRange();
      range.selectNodeContents(block);
      const selection = getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
      if (status) status.textContent = "Commands selected. Copy them with the keyboard.";
    }
    setTimeout(() => {
      button.textContent = "Copy commands";
      if (status) status.textContent = "";
    }, 2400);
  });
})();
