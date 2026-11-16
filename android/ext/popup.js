"use strict";
(async () => {
  const [cfg, data] = await Promise.all([WF.load(), WF.data()]);
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.style.cssText = WF.pageVars(WF.theme(cfg, data, dark), cfg.start.style);
  const $ = id => document.getElementById(id);

  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  let host = "";
  try {
    const u = new URL(tab.url);
    if (u.protocol === "http:" || u.protocol === "https:") host = u.hostname;
  } catch (e) { /* no page */ }

  async function changed() {
    await WF.save(cfg);
    if (tab && host) await browser.tabs.reload(tab.id);
    window.close();
  }

  if (host) {
    const domain = host.replace(/^www\./, "").replace(/^m\./, "");
    const rule = WF.ruleFor(cfg, host);
    const pack = WF.packFor(data, host);
    $("site").textContent = host;
    $("siteCard").hidden = false;
    $("packNote").textContent = pack ? "Theme pack: " + data.css.packs[pack].name + (cfg.packs[pack] ? "" : " (switched off)") : "";
    const sel = $("mode");
    const options = Object.assign({ "": pack ? "Theme pack only" : "Small touches only" }, WF.MODES);
    options.off = "Leave this site alone";
    for (const [value, label] of Object.entries(options)) sel.add(new Option(label, value));
    sel.value = rule.mode || "";
    sel.onchange = () => {
      if (rule.domain) delete cfg.rules[rule.domain];
      if (sel.value) cfg.rules[rule.domain || domain] = sel.value;
      changed();
    };
  } else {
    $("site").textContent = "No website in this tab.";
  }
  $("enabled").checked = cfg.enabled;
  $("enabled").onchange = () => { cfg.enabled = $("enabled").checked; changed(); };
  $("start").onclick = () => { browser.tabs.create({ url: browser.runtime.getURL("start.html") }); window.close(); };
  $("options").onclick = () => { browser.runtime.openOptionsPage(); window.close(); };
})();
