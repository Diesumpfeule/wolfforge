// Tests for the extension's logic. Run: node android/test.js
"use strict";
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const WF = require("./ext/common.js");
const data = JSON.parse(fs.readFileSync(path.join(__dirname, "ext/data.json"), "utf8"));
const cfg = over => WF.merge(WF.DEFAULTS, over || {});
let n = 0;
const test = (name, fn) => { fn(); n++; };

test("every theme has every colour", () => {
  assert.ok(data.themes.length >= 20);
  for (const t of data.themes) for (const k of data.keys) assert.match(t.colors[k], /^#[0-9a-f]{6}$/i, t.id + "." + k);
});

test("no placeholder is left in any generated CSS", () => {
  for (const host of ["example.org", "github.com", "en.m.wikipedia.org", "m.youtube.com"]) {
    for (const mode of ["", "theme", "dim", "invert"]) {
      const css = WF.cssFor(cfg({ rules: mode ? { [host]: mode } : {} }), data, host, true);
      assert.ok(css.length > 20, host);
      assert.ok(!/[«»]/.test(css), host + " " + mode);
      assert.ok(!css.includes("currentColor"), "unknown colour key for " + host);
    }
  }
});

test("packs match the site and its subdomains only", () => {
  assert.strictEqual(WF.packFor(data, "github.com"), "github");
  assert.strictEqual(WF.packFor(data, "gist.github.com"), "github");
  assert.strictEqual(WF.packFor(data, "notgithub.com"), "");
  assert.strictEqual(WF.packFor(data, "de.m.wikipedia.org"), "wikipedia");
});

test("off switches: everything, one site, one pack", () => {
  assert.strictEqual(WF.cssFor(cfg({ enabled: false }), data, "github.com", true), "");
  assert.strictEqual(WF.cssFor(cfg({ rules: { "github.com": "off" } }), data, "gist.github.com", true), "");
  const without = WF.cssFor(cfg({ packs: { github: false } }), data, "github.com", true);
  assert.ok(!without.includes("--bgColor-default"));
  assert.ok(WF.cssFor(cfg(), data, "github.com", true).includes("--bgColor-default"));
});

test("the longest matching rule wins", () => {
  const c = cfg({ rules: { "example.org": "dim", "shop.example.org": "invert" } });
  assert.strictEqual(WF.ruleFor(c, "shop.example.org").mode, "invert");
  assert.strictEqual(WF.ruleFor(c, "www.example.org").mode, "dim");
  assert.strictEqual(WF.ruleFor(c, "example.com").mode, "");
});

test("theme choice: accent, dark/light, unknown ids", () => {
  const mocha = data.themes.find(t => t.id === "catppuccin-mocha");
  assert.strictEqual(WF.theme(cfg({ accent: "red" }), data, true).colors.accent, mocha.colors.red);
  assert.strictEqual(WF.theme(cfg({ auto: true }), data, false).id, "catppuccin-latte");
  assert.strictEqual(WF.theme(cfg({ auto: true }), data, true).id, "catppuccin-mocha");
  assert.strictEqual(WF.theme(cfg({ theme: "gone" }), data, true).id, "catppuccin-mocha");
  assert.match(WF.theme(cfg(), data, true).colors.on_accent, /^#(000000|ffffff)$/);
});

test("own themes: cleaned, used, broken ones ignored", () => {
  const mine = { id: "my-x", label: "X", colors: Object.assign({}, data.themes[0].colors, { base: "#ffffff" }) };
  const c = cfg({ custom: [mine, { id: "bad", colors: { base: "red" } }], theme: "my-x" });
  assert.strictEqual(WF.allThemes(c, data).length, data.themes.length + 1);
  const t = WF.theme(c, data, true);
  assert.strictEqual(t.id, "my-x");
  assert.strictEqual(t.dark, false);
});

test("theme files: toml, json, rubbish", () => {
  const base = WF.theme(cfg(), data, true);
  const toml = 'label = "Mine"\n[colors]\nbase = "#101010"\ntext = "#fafafa"\naccent = "#ff0000"\n';
  const t = WF.themeFromText(toml, data.keys, base);
  assert.strictEqual(t.label, "Mine");
  assert.strictEqual(t.colors.accent, "#ff0000");
  assert.strictEqual(t.colors.mantle, base.colors.mantle);
  assert.strictEqual(WF.themeFromText(JSON.stringify(data.themes[3]), data.keys, base).colors.base, data.themes[3].colors.base);
  assert.strictEqual(WF.themeFromText("hello", data.keys, base), null);
  assert.strictEqual(WF.themeFromText('{"colors": {"base": "javascript:1"}}', data.keys, base), null);
});

test("bookmarks: groups, bare hosts, unsafe addresses dropped", () => {
  const g = WF.bookmarks("# A\nWiki | en.wikipedia.org\nhttps://github.com\nbad | javascript:alert(1)\n# Empty\n# B\nx | data:text/html,hi\nNews | https://example.org/a|b");
  assert.strictEqual(g.length, 2);
  assert.deepStrictEqual(g[0].links.map(l => l.name), ["Wiki", "github.com"]);
  assert.strictEqual(g[0].links[0].url, "https://en.wikipedia.org/");
  assert.strictEqual(g[1].name, "B");
  assert.strictEqual(g[1].links.length, 1);
});

test("search addresses", () => {
  const t = WF.theme(cfg(), data, true);
  assert.ok(WF.searchUrl(cfg(), data, t, "a b&c").startsWith("https://duckduckgo.com/?q=a%20b%26c&kae=d"));
  assert.strictEqual(WF.searchUrl(cfg({ start: { search: "brave" } }), data, t, "x"), "https://search.brave.com/search?q=x");
  assert.strictEqual(WF.searchUrl(cfg({ start: { ddgColors: false } }), data, t, "x"), "https://duckduckgo.com/?q=x");
});

test("settings of the wrong type are ignored", () => {
  const c = cfg({ enabled: "yes", touches: "all", start: { clock: 0, title: "ok" }, rules: { "a.org": "dim" } });
  assert.strictEqual(c.enabled, true);
  assert.strictEqual(c.touches.selection, true);
  assert.strictEqual(c.start.clock, true);
  assert.strictEqual(c.start.title, "ok");
  assert.deepStrictEqual(c.rules, { "a.org": "dim" });
});

test("the manifest lists files that exist", () => {
  const m = JSON.parse(fs.readFileSync(path.join(__dirname, "ext/manifest.json"), "utf8"));
  const files = [...m.background.scripts, ...m.content_scripts[0].js, m.browser_action.default_popup, m.options_ui.page, m.icons["48"]];
  for (const f of files) assert.ok(fs.existsSync(path.join(__dirname, "ext", f)), f);
  for (const page of ["popup.html", "options.html", "start.html"]) {
    const html = fs.readFileSync(path.join(__dirname, "ext", page), "utf8");
    for (const m2 of html.matchAll(/(?:src|href)="([^"#:]+)"/g)) assert.ok(fs.existsSync(path.join(__dirname, "ext", m2[1])), page + " → " + m2[1]);
    assert.ok(!/<script(?![^>]*src=)/.test(html), page + ": inline scripts are blocked in extension pages");
  }
});

console.log(n + " tests passed");
