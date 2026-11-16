"use strict";
(async () => {
  let cfg = await WF.load();
  const data = await WF.data();
  const $ = id => document.getElementById(id);
  const el = (tag, props, ...kids) => {
    const e = Object.assign(document.createElement(tag), props || {});
    for (const k of kids) e.append(k);
    return e;
  };
  const prefersDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;
  let editing = null;                 // id of the own theme whose colours are open

  function say(text) {
    $("status").textContent = text;
    if (text) setTimeout(() => { if ($("status").textContent === text) $("status").textContent = ""; }, 4000);
  }

  async function commit(redraw = true) {
    await WF.save(cfg);
    if (redraw) draw();
  }

  function themeGrid(box, key) {
    box.textContent = "";
    for (const t of WF.allThemes(cfg, data)) {
      const b = el("button", { className: "theme" + (cfg[key] === t.id ? " on" : ""), type: "button" });
      b.style.background = t.colors.base;
      b.style.color = t.colors.text;
      b.append(el("div", { textContent: t.label + (t.custom ? " (yours)" : "") }));
      for (const k of ["accent", "accent2", "red", "green", "yellow", "blue"]) {
        const dot = el("i");
        dot.style.background = t.colors[k];
        b.append(dot);
      }
      b.onclick = () => { cfg[key] = t.id; commit(); };
      box.append(b);
    }
  }

  function select(id, options, value, onchange) {
    const s = $(id);
    s.textContent = "";
    for (const [v, label] of Object.entries(options)) s.add(new Option(label, v));
    s.value = value;
    s.onchange = () => onchange(s.value);
  }

  function check(id, value, onchange) {
    $(id).checked = !!value;
    $(id).onchange = () => onchange($(id).checked);
  }

  function toggleCard(label, note, value, onchange) {
    const box = el("input", { type: "checkbox", checked: !!value });
    box.onchange = () => onchange(box.checked);
    const text = el("span", { className: "grow", textContent: label });
    if (note) text.append(el("small", { textContent: note }));
    return el("div", { className: "card" }, el("label", { className: "row" }, text, box));
  }

  const cap = s => s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ");

  function drawCustom() {
    const box = $("custom");
    box.textContent = "";
    cfg.custom.forEach((t, index) => {
      const card = el("div", { className: "card" });
      const open = editing === t.id;
      const head = el("div", { className: "row" },
        el("span", { className: "grow", textContent: t.label }),
        el("button", { type: "button", textContent: open ? "Close" : "Edit", onclick: () => { editing = open ? null : t.id; drawCustom(); } }),
        el("button", { type: "button", textContent: "Delete", onclick: () => {
          if (!confirm("Delete " + t.label + "?")) return;
          cfg.custom.splice(index, 1);
          if (cfg.theme === t.id) cfg.theme = WF.DEFAULTS.theme;
          if (cfg.themeLight === t.id) cfg.themeLight = WF.DEFAULTS.themeLight;
          commit();
        } }));
      card.append(head);
      if (open) {
        const name = el("input", { type: "text", value: t.label, maxLength: 40 });
        name.onchange = () => { t.label = name.value.trim() || t.label; commit(); };
        card.append(el("div", { className: "row", style: "margin:8px 0" }, name));
        const grid = el("div", { className: "kv" });
        for (const k of data.keys) {
          const pick = el("input", { type: "color", value: t.colors[k] });
          pick.onchange = () => { t.colors[k] = pick.value; t.dark = WF.lum(t.colors.base) < 0.3; commit(); };
          grid.append(el("label", { textContent: cap(k) }), pick);
        }
        card.append(grid);
        const out = el("textarea", { readOnly: true, value: JSON.stringify({ id: t.id, label: t.label, dark: t.dark, colors: t.colors }, null, 1) });
        out.style.minHeight = "90px";
        card.append(el("p", { textContent: "As text (droidforge can import this as a file):" }), out);
      }
      box.append(card);
    });
    if (!cfg.custom.length) box.append(el("p", { textContent: "None yet." }));
  }

  function freeId(label) {
    const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "theme";
    const taken = new Set(WF.allThemes(cfg, data).map(t => t.id));
    let id = "my-" + slug;
    for (let n = 2; taken.has(id); n++) id = "my-" + slug + "-" + n;
    return id;
  }

  function addTheme(t) {
    t.id = freeId(t.label);
    cfg.custom.push({ id: t.id, label: t.label, dark: t.dark, colors: t.colors });
    return t.id;
  }

  function importText(text) {
    const base = WF.theme(Object.assign({}, cfg, { accent: "" }), data, prefersDark());
    let parsed = null;
    try { parsed = JSON.parse(text); } catch (e) { /* not JSON */ }
    if (parsed && parsed._droidforge) {                    // a droidforge backup: its own themes + the chosen one
      let n = 0;
      const idMap = {};
      let mine = [];
      try { mine = JSON.parse(parsed.user_themes || "[]"); } catch (e) { /* none */ }
      for (const raw of mine) {
        const t = WF.cleanTheme(raw, data.keys, null);
        if (t) { idMap[raw.id] = addTheme(t); n++; }
      }
      const pick = id => idMap[id] || (data.themes.some(t => t.id === id) ? id : null);
      if (pick(parsed.theme)) cfg.theme = pick(parsed.theme);
      if (pick(parsed.theme_light)) cfg.themeLight = pick(parsed.theme_light);
      if (typeof parsed.auto_theme === "boolean") cfg.auto = parsed.auto_theme;
      if (typeof parsed.accent === "string" && (parsed.accent === "" || WF.ACCENTS.includes(parsed.accent))) cfg.accent = parsed.accent;
      return "Took the theme from the droidforge backup" + (n ? " and " + n + " of your own themes" : "");
    }
    const t = WF.themeFromText(text, data.keys, base);
    if (!t) return "";
    cfg.theme = addTheme(t);
    editing = cfg.theme;
    return "Imported " + t.label;
  }

  function drawRules() {
    const box = $("rules");
    box.textContent = "";
    const modes = Object.assign({}, WF.MODES, { off: "Leave this site alone" });
    for (const domain of Object.keys(cfg.rules).sort()) {
      const sel = el("select");
      for (const [v, label] of Object.entries(modes)) sel.add(new Option(label, v));
      sel.value = cfg.rules[domain];
      sel.onchange = () => { cfg.rules[domain] = sel.value; commit(false); };
      box.append(el("div", { className: "card" }, el("div", { className: "row" },
        el("span", { className: "grow mono", textContent: domain }), sel,
        el("button", { type: "button", textContent: "✕", ariaLabel: "Remove the rule for " + domain,
          onclick: () => { delete cfg.rules[domain]; commit(); } }))));
    }
  }

  function drawPrivacy(level) {
    const box = $("privacy");
    box.textContent = "";
    for (const row of data.privacy[level] || []) {
      const copy = el("button", { type: "button", textContent: "Copy name" });
      copy.onclick = () => navigator.clipboard.writeText(row.pref).then(() => say("Copied " + row.pref), () => say("Could not copy"));
      box.append(el("div", { className: "card" },
        el("div", { className: "row" },
          el("span", { className: "grow" }, el("code", { textContent: row.pref }), el("small", { textContent: row.why })),
          el("b", { textContent: String(row.value) }), copy)));
    }
    box.append(el("p", { textContent: "Also worth a look in Firefox's own settings: Enhanced Tracking Protection → Strict, " +
      "HTTPS-Only mode, Delete browsing data on quit, and Data collection (all off)." }));
  }

  function draw() {
    const theme = WF.theme(cfg, data, prefersDark());
    document.documentElement.style.cssText = WF.pageVars(theme, "modern");
    check("auto", cfg.auto, v => { cfg.auto = v; commit(); });
    $("themeHint").textContent = cfg.auto ? "Theme while the phone is in dark mode:" : "";
    themeGrid($("themes"), "theme");
    $("lightBox").hidden = !cfg.auto;
    if (cfg.auto) themeGrid($("themesLight"), "themeLight");
    const accents = { "": "The theme's own" };
    for (const k of WF.ACCENTS.slice(1)) accents[k] = k === "accent2" ? "Second accent" : cap(k);
    select("accent", accents, cfg.accent, v => { cfg.accent = v; commit(); });
    drawCustom();

    check("enabled", cfg.enabled, v => { cfg.enabled = v; commit(false); });
    const touchNames = { selection: ["Marked text in your accent colour", ""], caret: ["Text cursor in your accent colour", ""],
      focus_ring: ["Focus outline in your accent colour", ""], scrollbars: ["Scrollbars in your accent colour", "Where a page shows any"],
      accent_color: ["Checkboxes, sliders and radio buttons in your accent colour", ""] };
    const touches = $("touches");
    touches.textContent = "";
    for (const [k, [label, note]] of Object.entries(touchNames)) {
      touches.append(toggleCard(label, note, cfg.touches[k], v => { cfg.touches[k] = v; commit(false); }));
    }
    const packs = $("packs");
    packs.textContent = "";
    for (const [k, p] of Object.entries(data.css.packs)) {
      packs.append(toggleCard(p.name, p.domains.join(", "), cfg.packs[k], v => { cfg.packs[k] = v; commit(false); }));
    }
    drawRules();
    select("ruleMode", Object.assign({}, WF.MODES, { off: "Leave this site alone" }), "theme", () => {});

    const sp = cfg.start;
    $("title").value = sp.title;
    $("title").onchange = () => { sp.title = $("title").value.trim(); commit(false); };
    const arts = { "": "None" };
    for (const k of Object.keys(data.art)) arts[k] = cap(k);
    select("art", arts, data.art[sp.art] ? sp.art : "", v => { sp.art = v; commit(false); });
    select("style", { modern: "Modern – rounded cards", wired: "Wired – terminal look", classic: "Classic 98 – bevelled", minimal: "Minimal – only text" },
      sp.style, v => { sp.style = v; commit(false); });
    check("animate", sp.animate, v => { sp.animate = v; commit(false); });
    check("clock", sp.clock, v => { sp.clock = v; commit(false); });
    check("seconds", sp.seconds, v => { sp.seconds = v; commit(false); });
    select("hour", { auto: "As the phone is set", 24: "24 hours", 12: "12 hours" }, sp.hour, v => { sp.hour = v; commit(false); });
    const engines = {};
    for (const [k, e] of Object.entries(data.search)) engines[k] = e.name;
    select("search", engines, sp.search, v => { sp.search = v; commit(false); });
    check("ddgColors", sp.ddgColors, v => { sp.ddgColors = v; commit(false); });
    $("bookmarks").value = sp.bookmarks;
    $("bookmarks").onchange = () => { sp.bookmarks = $("bookmarks").value; commit(false); };

    $("ddg").textContent = WF.ddgUrl(theme);
    $("backup").value = JSON.stringify(cfg, null, 1);
  }

  $("openStart").onclick = () => browser.tabs.create({ url: browser.runtime.getURL("start.html") });
  $("newTheme").onclick = () => {
    const base = WF.theme(cfg, data, prefersDark());
    const colors = Object.assign({}, base.colors);
    delete colors.on_accent;
    cfg.theme = addTheme({ label: "My " + base.label, dark: base.dark, colors });
    cfg.accent = "";
    editing = cfg.theme;
    commit();
  };
  $("importTheme").onclick = () => $("themeFile").click();
  $("themeFile").onchange = async () => {
    const f = $("themeFile").files[0];
    $("themeFile").value = "";
    if (!f) return;
    if (f.size > 1 << 20) { say("That file is too big to be a theme."); return; }
    const msg = importText(await f.text());
    if (msg) await commit();
    say(msg || "No colours found in that file.");
  };
  $("ruleAdd").onclick = () => {
    let d = $("ruleDomain").value.trim().toLowerCase().replace(/^[a-z]+:\/\//, "").replace(/\/.*$/, "").replace(/^www\./, "");
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(d)) { say("That is not a site name like example.org."); return; }
    cfg.rules[d] = $("ruleMode").value;
    $("ruleDomain").value = "";
    commit();
  };
  select("level", { fortress: "Fortress – strict, some sites break", comfort: "Comfort – protection that stays out of the way" },
    "fortress", drawPrivacy);
  drawPrivacy("fortress");
  $("ddgCopy").onclick = () => navigator.clipboard.writeText($("ddg").textContent).then(() => say("Copied"), () => say("Could not copy"));
  $("backupCopy").onclick = () => navigator.clipboard.writeText($("backup").value).then(() => say("Copied"), () => say("Could not copy"));
  $("backupRestore").onclick = async () => {
    let parsed;
    try { parsed = JSON.parse($("backup").value); } catch (e) { say("That text is not a wolfforge backup."); return; }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) || !("theme" in parsed)) { say("That text is not a wolfforge backup."); return; }
    cfg = WF.merge(WF.DEFAULTS, parsed);
    cfg.custom = (Array.isArray(parsed.custom) ? parsed.custom : []).map(t => WF.cleanTheme(t, data.keys, null)).filter(Boolean)
      .map(t => ({ id: t.id, label: t.label, dark: t.dark, colors: t.colors }));
    const rules = {};
    for (const [d, m] of Object.entries(cfg.rules || {})) if (/^[a-z0-9.-]+\.[a-z]{2,}$/.test(d) && (m in WF.MODES)) rules[d] = m;
    cfg.rules = rules;
    await commit();
    say("Restored.");
  };
  $("reset").onclick = async () => {
    if (!confirm("Reset every wolfforge setting, including your own themes?")) return;
    cfg = WF.merge(WF.DEFAULTS, {});
    await commit();
    say("Reset.");
  };
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  draw();
})();
