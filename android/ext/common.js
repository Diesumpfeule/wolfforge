// Shared by the background script and the extension's pages: settings, themes, building the CSS.
"use strict";

const WF = (() => {
  const DEFAULTS = {
    enabled: true,
    theme: "catppuccin-mocha",
    auto: false,                  // follow the phone's dark/light mode
    themeLight: "catppuccin-latte",
    accent: "",                   // "" = the theme's own, else a colour key
    custom: [],                   // your own themes: {id, label, dark, colors}
    touches: { selection: true, caret: true, focus_ring: true, scrollbars: true, accent_color: true },
    packs: { github: true, wikipedia: true, youtube: true },
    rules: {},                    // domain → "theme" | "dim" | "invert"
    start: {
      title: "firefox", art: "forge", animate: true, clock: true, seconds: false, hour: "auto",
      search: "duckduckgo", ddgColors: true, style: "modern",
      bookmarks: "# Daily\nWikipedia | https://en.wikipedia.org\nGitHub | https://github.com\n# Watch\nYouTube | https://www.youtube.com",
    },
  };
  const ACCENTS = ["accent", "accent2", "red", "green", "yellow", "orange", "blue", "magenta", "cyan", "text"];
  const MODES = { off: "Off", theme: "Your colours", dim: "Dim", invert: "Invert (dark mode by force)" };

  let dataCache = null;

  function merge(base, over) {
    const out = Array.isArray(base) ? base.slice() : Object.assign({}, base);
    if (!over || typeof over !== "object") return out;
    for (const k of Object.keys(over)) {
      const b = base[k], o = over[k];
      if (b && typeof b === "object" && !Array.isArray(b) && k !== "rules") out[k] = merge(b, o);
      else if (b === undefined || typeof b === typeof o) out[k] = o;
    }
    return out;
  }

  async function data() {
    if (!dataCache) dataCache = await (await fetch(browser.runtime.getURL("data.json"))).json();
    return dataCache;
  }

  async function load() {
    const got = await browser.storage.local.get("cfg");
    return merge(DEFAULTS, got.cfg || {});
  }

  function save(cfg) {
    return browser.storage.local.set({ cfg });
  }

  const HEX = /^#[0-9a-fA-F]{6}$/;

  /** A theme as stored or imported → a clean one, or null. Missing colours come from `base`. */
  function cleanTheme(t, keys, base) {
    if (!t || typeof t !== "object" || !t.colors) return null;
    const colors = {};
    let found = 0;
    for (const k of keys) {
      if (HEX.test(t.colors[k] || "")) { colors[k] = t.colors[k].toLowerCase(); found++; }
      else if (base) colors[k] = base.colors[k];
      else return null;
    }
    if (found < 3) return null;
    return { id: String(t.id || "my-theme"), label: String(t.label || t.id || "My theme"),
      dark: typeof t.dark === "boolean" ? t.dark : lum(colors.base) < 0.3, colors, custom: true };
  }

  function allThemes(cfg, d) {
    const mine = (cfg.custom || []).map(t => cleanTheme(t, d.keys, null)).filter(Boolean);
    return mine.concat(d.themes);
  }

  function lum(hex) {
    const v = [1, 3, 5].map(i => parseInt(hex.substr(i, 2), 16) / 255)
      .map(x => (x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4)));
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  }

  /** The theme to use right now, accent applied. prefersDark: what the phone says (for "auto"). */
  function theme(cfg, d, prefersDark) {
    const all = allThemes(cfg, d);
    const id = cfg.auto && prefersDark === false ? cfg.themeLight : cfg.theme;
    const t = all.find(x => x.id === id) || d.themes.find(x => x.id === DEFAULTS.theme) || d.themes[0];
    const colors = Object.assign({}, t.colors);
    if (cfg.accent && cfg.accent !== "accent" && colors[cfg.accent]) colors.accent = colors[cfg.accent];
    colors.on_accent = lum(colors.accent) > 0.35 ? "#000000" : "#ffffff";
    return { id: t.id, label: t.label, dark: t.dark, colors };
  }

  function fill(css, colors) {
    return css.replace(/«([a-z0-9_]+)»/g, (m, k) => colors[k] || "currentColor");
  }

  function hostMatches(host, domain) {
    return host === domain || host.endsWith("." + domain);
  }

  /** The rule for a host: the longest matching domain wins. */
  function ruleFor(cfg, host) {
    let best = "", mode = "";
    for (const [domain, m] of Object.entries(cfg.rules || {})) {
      if (hostMatches(host, domain) && domain.length > best.length) { best = domain; mode = m; }
    }
    return { domain: best, mode };
  }

  /** Which theme pack covers this host, or "". */
  function packFor(d, host) {
    for (const [key, p] of Object.entries(d.css.packs)) {
      if (p.domains.some(x => hostMatches(host, x))) return key;
    }
    return "";
  }

  /** All CSS for one page. Empty when wolfforge is off (in general or for this site). */
  function cssFor(cfg, d, host, prefersDark) {
    if (!cfg.enabled) return "";
    const rule = ruleFor(cfg, host);
    if (rule.mode === "off") return "";
    const t = theme(cfg, d, prefersDark);
    const parts = [];
    for (const [k, on] of Object.entries(cfg.touches)) {
      if (!on) continue;
      if (k === "accent_color") parts.push(":root { accent-color: «accent»; }");
      else if (d.css.touches[k]) parts.push(d.css.touches[k]);
    }
    const pack = packFor(d, host);
    if (pack && cfg.packs[pack]) parts.push(d.css.packs[pack].css);
    if (rule.mode && d.css.rules[rule.mode]) parts.push(d.css.rules[rule.mode]);
    return fill(parts.join("\n"), t.colors);
  }

  /** DuckDuckGo with its own appearance settings in your colours (search engine URL, %s = the query). */
  function ddgUrl(t) {
    const h = x => x.replace("#", "");
    const c = t.colors;
    const p = { kae: t.dark ? "d" : "-1", k7: h(c.base), k8: h(c.text), k9: h(c.accent), kaa: h(c.accent2),
      kx: h(c.subtext), kj: h(c.mantle), ku: "-1" };
    return "https://duckduckgo.com/?q=%s&" + Object.entries(p).map(([k, v]) => k + "=" + encodeURIComponent(v)).join("&");
  }

  function searchUrl(cfg, d, t, query) {
    const q = encodeURIComponent(query);
    const eng = d.search[cfg.start.search] || d.search.duckduckgo;
    if (cfg.start.search === "duckduckgo" && cfg.start.ddgColors) return ddgUrl(t).replace("%s", q);
    return eng.url + "?" + eng.param + "=" + q;
  }

  /** "# Group" / "Name | URL" lines → [{name, links: [{name, url}]}]. Unsafe addresses are dropped. */
  function bookmarks(text) {
    const groups = [];
    let cur = null;
    for (const raw of String(text || "").split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      if (line.startsWith("#")) { cur = { name: line.replace(/^#+\s*/, ""), links: [] }; groups.push(cur); continue; }
      const at = line.lastIndexOf("|");
      let name = at >= 0 ? line.slice(0, at).trim() : "", url = (at >= 0 ? line.slice(at + 1) : line).trim();
      if (!/^[a-z][a-z0-9+.-]*:/i.test(url)) url = "https://" + url;
      let parsed;
      try { parsed = new URL(url); } catch (e) { continue; }
      if (!["http:", "https:"].includes(parsed.protocol)) continue;
      if (!name) name = parsed.hostname.replace(/^www\./, "");
      if (!cur) { cur = { name: "", links: [] }; groups.push(cur); }
      cur.links.push({ name, url: parsed.href });
    }
    return groups.filter(g => g.links.length);
  }

  /** A theme from a file: droidforge/wolfforge JSON, or a swayforge/wolfforge .toml. */
  function themeFromText(text, keys, base) {
    const trimmed = String(text).trim();
    if (trimmed.startsWith("{")) {
      try { return cleanTheme(JSON.parse(trimmed), keys, base); } catch (e) { /* try the line format */ }
    }
    const colors = {};
    let label = "Imported";
    for (const line of trimmed.split("\n")) {
      let m = /^\s*([a-z0-9_]+)\s*=\s*"(#[0-9a-fA-F]{6})"/.exec(line);
      if (m && keys.includes(m[1])) { colors[m[1]] = m[2]; continue; }
      m = /^\s*(?:name|label)\s*=\s*"([^"]+)"/.exec(line);
      if (m) label = m[1];
    }
    return cleanTheme({ id: label, label, colors }, keys, base);
  }

  /** CSS custom properties for the extension's own pages. */
  function pageVars(t, style) {
    const c = t.colors;
    const radius = { modern: 14, wired: 0, classic: 0, minimal: 0 }[style] ?? 14;
    return Object.keys(c).map(k => `--${k.replace("_", "-")}: ${c[k]};`).join(" ") +
      ` --r: ${radius}px; color-scheme: ${t.dark ? "dark" : "light"};`;
  }

  return { DEFAULTS, ACCENTS, MODES, merge, data, load, save, cleanTheme, allThemes, lum, theme, fill, hostMatches,
    ruleFor, packFor, cssFor, ddgUrl, searchUrl, bookmarks, themeFromText, pageVars };
})();

if (typeof module !== "undefined") module.exports = WF;
