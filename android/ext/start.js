"use strict";
(async () => {
  const [cfg, data] = await Promise.all([WF.load(), WF.data()]);
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = WF.theme(cfg, data, dark);
  const sp = cfg.start;
  const root = document.documentElement;
  root.style.cssText = WF.pageVars(theme, sp.style);
  root.className = sp.style + (sp.animate ? " animate" : "");
  document.title = sp.title || "Start";
  const $ = id => document.getElementById(id);
  const shade = new Set(data.shade);

  /** Lines of ASCII → a <pre> where light characters get the dimmer colour (the two-tone look). */
  function twoTone(lines, perLine) {
    const pre = document.createElement("pre");
    lines.forEach((line, n) => {
      const holder = document.createElement("span");
      if (perLine) { holder.className = "ln"; holder.style.animationDelay = (n * -0.22) + "s"; }
      let cur = null, cls = "";
      for (const ch of line) {
        const c = ch === " " ? cls : shade.has(ch) ? "s" : "f";
        if (!cur || c !== cls) {
          cur = document.createElement("span");
          cur.className = cls = c || "f";
          holder.appendChild(cur);
        }
        cur.textContent += ch;
      }
      pre.appendChild(holder);
      pre.appendChild(document.createTextNode("\n"));
    });
    return pre;
  }

  /** The title in shaded block letters, in the tallest font that still fits the screen. */
  function banner(text) {
    const box = $("banner");
    box.textContent = "";
    const t = text.trim().toUpperCase().slice(0, 16);
    if (!t) return;
    const cols = Math.floor((box.clientWidth || 320) / 3.7);       // about what fits at the smallest size
    for (const rows of ["6", "5", "4"]) {
      const font = data.banner[rows];
      if (!font) continue;
      const out = Array.from({ length: Number(rows) }, () => "");
      [...t].forEach((ch, i) => {
        const g = font[ch] || font["?"] || [];
        const w = Math.max(0, ...g.map(x => x.length));
        for (let r = 0; r < out.length; r++) out[r] += (i ? " " : "") + (g[r] || "").padEnd(w);
      });
      const width = Math.max(...out.map(l => l.trimEnd().length));
      if (width > cols && rows !== "4") continue;
      const pre = twoTone(out.map(l => l.trimEnd()), false);
      const px = Math.max(4, Math.min(13, Math.floor((box.clientWidth || 320) / (width * 0.62))));
      pre.style.fontSize = px + "px";
      box.appendChild(pre);
      return;
    }
  }

  banner(sp.title || "");
  const art = data.art[sp.art];
  if (art) $("art").appendChild(twoTone(art, true));
  else $("art").hidden = true;

  function tick() {
    const now = new Date();
    const h12 = sp.hour === "12" ? true : sp.hour === "24" ? false : undefined;
    $("clock").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit",
      second: sp.seconds ? "2-digit" : undefined, hour12: h12 });
    $("date").textContent = now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" });
  }
  if (sp.clock) { tick(); setInterval(tick, sp.seconds ? 1000 : 15000); }
  else { $("clock").hidden = true; $("date").hidden = true; }

  $("form").addEventListener("submit", e => {
    e.preventDefault();
    const q = $("q").value.trim();
    if (!q) return;
    const looksLikeAddress = /^[a-z][a-z0-9+.-]*:\/\//i.test(q) || (/^[^\s]+\.[a-z]{2,}(\/\S*)?$/i.test(q) && !q.includes(" "));
    let url = WF.searchUrl(cfg, data, theme, q);
    if (looksLikeAddress) {
      try {
        const u = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(q) ? q : "https://" + q);
        if (u.protocol === "http:" || u.protocol === "https:") url = u.href;
      } catch (err) { /* search for it instead */ }
    }
    location.href = url;
  });

  const groups = $("groups");
  for (const g of WF.bookmarks(sp.bookmarks)) {
    const box = document.createElement("div");
    box.className = "group";
    if (g.name) {
      const h = document.createElement("h2");
      h.textContent = g.name;
      box.appendChild(h);
    }
    for (const l of g.links) {
      const a = document.createElement("a");
      a.href = l.url;
      a.textContent = l.name;
      box.appendChild(a);
    }
    groups.appendChild(box);
  }
})();
