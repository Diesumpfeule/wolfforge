// Asks the background script for this page's styles as early as possible.
"use strict";
(() => {
  if (window.top !== window) return;                 // frames inherit nothing useful; keep it light
  let dark = null;
  try { dark = window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) { /* unknown */ }
  browser.runtime.sendMessage({ t: "css", dark }).catch(() => {});
})();
