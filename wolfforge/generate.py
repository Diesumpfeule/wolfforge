"""Turn the universal file into LibreWolf files: userChrome/userContent, start page, prefs."""
from __future__ import annotations

import html
import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

from . import ascii as asc
from . import bookmarks as bm
from . import config, paths, prefs, themes

MARK = "wolfforge generated"
LAYOUTS = {
    "classic": "Classic – tabs on top, address bar below, themed",
    "compact": "Compact – tabs and address bar in one row (most space for pages)",
    "minimal": "Minimal – toolbar hides, appears on hover or Ctrl+L (keyboard use)",
    "win98": "Classic 98 – bevelled buttons, sunken address bar, title-bar tabs",
    "wired": "Wired – terminal look: [brackets], > prompt, scanlines",
    "cathedral": "Cathedral – gothic: serif tabs with ✠, double rules, framed start page",
    "glass": "Glass – see-through toolbars, floating rounded tabs, hairline edges, accent outline",
    "luna": "Luna XP – blue title gradient, rounded tabs, green Go button, beige toolbar",
    "dread": "Dread – survival horror: worn inventory-slot tabs, rust rules, blood-red focus glow",
    "modern": "Modern 11 – soft rounded pills, roomy, accent bar under the active tab, Mica-like",
}
TAGS = {"classic": "░▒▓ librewolf", "compact": "▓▒░", "minimal": "░▒▓ librewolf",
        "win98": "■ LibreWolf 98", "wired": "[ wired :: online ]", "cathedral": "❦ ✠ ❦",
        "glass": "◇ librewolf", "luna": "LibreWolf XP", "dread": "☠ save room", "modern": "librewolf"}

_env = jinja2.Environment(loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
                          trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
                          autoescape=False)
DOMAIN = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$")


@dataclass
class Result:
    written: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def bevel(c: dict) -> dict:
    """Win98 3D-edge colours – the exact same formula as swayforge's render.bevel(),
    so the browser and the Classic 98 bar show identical greys and title gradients."""
    mix = themes.mix
    face = mix(c["surface"], c["text"], 0.10)
    return {"face": face, "hi": mix(face, c["text"], 0.6), "lo": mix(face, c["crust"], 0.85),
            "dk": c["crust"], "pressed": mix(face, c["crust"], 0.35), "title": c["accent"],
            "title2": mix(c["accent"], c["base"], 0.55)}


def css_string(lines: list[str]) -> str:
    esc = [l.replace("\\", "\\\\").replace('"', '\\"') for l in lines]
    return '"' + "\\A ".join(esc) + '"'


def two_tone_html(lines: list[str]) -> str:
    out = []
    for line in lines:
        buf, cur = [], None
        for ch in line:
            cls = "s" if ch in asc.SHADE else "f"
            if ch == " ":
                buf.append(" ")
                continue
            if cls != cur:
                if cur:
                    buf.append("</span>")
                buf.append(f'<span class="{cls}">')
                cur = cls
            buf.append(html.escape(ch))
        if cur:
            buf.append("</span>")
        out.append("".join(buf))
    return "\n".join(out)


def ddg_params(c: dict, dark: bool, font: str) -> dict:
    """DuckDuckGo's official appearance parameters (duckduckgo.com/params) in your colours."""
    h = lambda x: x.lstrip("#")                                        # noqa: E731
    return {"kae": "d" if dark else "-1", "k7": h(c["base"]), "k8": h(c["text"]), "k9": h(c["accent"]),
            "kaa": h(c["accent2"]), "kx": h(c["subtext"]), "kj": h(c["mantle"]), "kt": font, "ka": font,
            "ku": "-1"}


def ddg_search_url(cfg: dict) -> str:
    """For LibreWolf → Settings → Search → Add: a DuckDuckGo engine in your colours."""
    from urllib.parse import urlencode
    r = themes.resolved(cfg)
    return "https://duckduckgo.com/?q=%s&" + urlencode(ddg_params(r["c"], r["palette"].dark, r["font"]))


ENGINES = {
    "stylus": "Stylus extension – import the file wolfforge writes (themes any site, you control it in Stylus)",
    "usercss": "userContent.css – built in, automatic, no extension (rules use Firefox's @-moz-document)",
}
PACK_DOMAINS = {"github": ["github.com"],
                "wikipedia": ["wikipedia.org", "wikimedia.org", "wiktionary.org"],
                "youtube": ["youtube.com"]}
PACK_COMMENTS = {
    "github": "── Theme pack: GitHub (Primer colour variables) – experimental ───────────────",
    "wikipedia": "── Theme pack: Wikipedia (Codex design tokens) – experimental ────────────────",
    "youtube": "── Theme pack: YouTube ───────────────────────────────────────────────────────────\n"
               "   YouTube re-defines its colours on every [dark] element and has two token sets\n"
               "   (yt-spec and the newer yt-sys) – all of them are overridden here.",
}
PACK_NAMES = {"github": "GitHub", "wikipedia": "Wikipedia", "youtube": "YouTube"}


def _moz_selector(domains: list[str]) -> str:
    return ", ".join(f'domain("{d}")' for d in domains)


def site_styles(ctx: dict) -> list[dict]:
    """Everything that themes websites, as separate styles: {key, name, domains, selector, comment, css}.
    No domains = every website. Used for userContent.css (wrapped in @-moz-document) and for Stylus."""
    out = []
    css = _env.get_template("sites/global.css.j2").render(**ctx).strip("\n")
    if css.strip():
        out.append({"key": "global", "name": "wolfforge: all websites", "domains": [], "selector": "",
                    "comment": "", "css": css})
    for k in ("github", "wikipedia", "youtube"):
        if k in ctx["packs"]:
            body = _env.get_template(f"sites/{k}.css.j2").render(**ctx).rstrip("\n")
            out.append({"key": k, "name": f"wolfforge: {PACK_NAMES[k]}", "domains": PACK_DOMAINS[k],
                        "selector": _moz_selector(PACK_DOMAINS[k]), "comment": PACK_COMMENTS[k], "css": body})
    for r in ctx["s"].get("rules", []):
        if r["mode"] == "off":
            continue
        body = _env.get_template("sites/rule.css.j2").render(**ctx, r=r).rstrip("\n")
        out.append({"key": f"rule:{r['domain']}", "name": f"wolfforge: site rule {r['domain']}",
                    "domains": [r["domain"]], "selector": _moz_selector([r["domain"]]),
                    "comment": f"site rule: {r['domain']} → {r['mode']}", "css": body})
    return out


def stylus_json(styles: list[dict]) -> str:
    """A Stylus backup file (Manage → Backup → Import). Names and ids stay the same between runs,
    so importing again updates the styles instead of adding copies."""
    out = []
    for st in styles:
        out.append({
            "enabled": True, "name": st["name"],
            "description": "Generated by wolfforge from your theme – import again after changing it.",
            "author": "wolfforge", "url": None, "updateUrl": None, "md5Url": None, "originalMd5": None,
            "_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "wolfforge/" + st["key"])),
            "sections": [{"code": st["css"], "urls": [], "urlPrefixes": [], "domains": st["domains"],
                          "regexps": []}],
        })
    return json.dumps(out, indent=2, ensure_ascii=False) + "\n"


STYLUS_FILE = "stylus-import.json"


def context(cfg: dict) -> dict:
    r = themes.resolved(cfg)
    c = r["c"]
    layout = cfg["general"]["layout"] if cfg["general"]["layout"] in LAYOUTS else "classic"
    if cfg["general"].get("follow_system") and r["palette"].source == "swayforge" \
            and cfg["general"].get("layout_follow", False):
        layout = r["palette"].style.get("layout", layout)
    sp = cfg["startpage"]
    face, shade = asc.layers(r["art"])
    banner_text = sp.get("banner") or "librewolf"
    eng = config.SEARCH.get(sp.get("search", "duckduckgo"), config.SEARCH["duckduckgo"])
    rules = [x for x in cfg["sites"].get("rules", [])
             if DOMAIN.match(str(x.get("domain", "")).lower()) and x.get("mode") in config.SITE_MODES]
    sites = dict(cfg["sites"], rules=rules)
    engine = cfg["sites"].get("engine", "stylus")
    ctx = {
        "engine": engine if engine in ENGINES else "stylus",
        "mark": MARK, "p": r["palette"], "c": c, "radius": r["radius"], "font": r["font"],
        "font_size": r["font_size"], "layout": layout, "t": cfg["toolbar"], "s": sites, "sp": sp,
        "bv": bevel(c), "on_accent": themes.on(c["accent"]), "tag": TAGS.get(layout, ""),
        "rgba": themes.rgba, "mix": themes.mix, "on": themes.on,
        "art_rows": len(r["art"]), "art_face": css_string(face), "art_shade": css_string(shade),
        "art_html": two_tone_html(r["art"]),
        "banner_html": two_tone_html(asc.best_banner(banner_text, 120)),
        "title": banner_text, "search_name": eng[0], "search_url": eng[1], "search_param": eng[2],
        "groups": bm.groups_for_startpage(cfg.get("bookmarks", [])),
        "ddg": ddg_params(c, r["palette"].dark, r["font"])
        if cfg["sites"].get("duckduckgo", True) and sp.get("search") == "duckduckgo" else {},
        "packs": {k for k, v in cfg["sites"].get("packs", {}).items() if v},
        "animate": bool(cfg["general"].get("animate", True)),
        "motion": (r["palette"].style.get("motion") if r["palette"].source == "swayforge" else "")
        or cfg["general"].get("motion", "wave"),
        "shade_chars": "".join(sorted(asc.SHADE)),
    }
    ctx["site_styles"] = site_styles(ctx)
    return ctx


def render(name: str, ctx: dict) -> str:
    return _env.get_template(name).render(**ctx)


def _stub(path: Path, import_line: str, comment: str, res: Result, dry: bool) -> None:
    """userChrome.css / userContent.css belong to you – make sure they import ours first."""
    old = path.read_text() if path.exists() else ""
    if import_line in old:
        return
    new = f"{import_line}\n\n/* {comment} */\n" + (("\n" + old) if old.strip() else "")
    if not dry:
        if old.strip():
            backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new)
    res.written.append(str(path))


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    d = paths.BACKUP_DIR / time.strftime("%Y%m%d-%H%M%S")
    d.mkdir(parents=True, exist_ok=True)
    dst = d / path.name
    shutil.copy2(path, dst)
    return dst


def _write(path: Path, content: str, res: Result, dry: bool) -> None:
    if path.exists() and path.read_text(errors="replace") == content:
        return
    if path.exists() and MARK not in path.read_text(errors="replace")[:400]:
        res.notes.append(f"{path.name} has no '{MARK}' line – you took it over, left alone")
        return
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    res.written.append(str(path))


def _stylus_file(ctx: dict, res: Result, dry: bool) -> None:
    """With engine 'stylus': write the import file. Say so only when its content changed,
    because then the Stylus add-on has an older copy and wants the file again."""
    f = paths.STATE_DIR / STYLUS_FILE
    if ctx["engine"] != "stylus":
        return
    text = stylus_json(ctx["site_styles"])
    if f.exists() and f.read_text(errors="replace") == text:
        return
    if not dry:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    res.written.append(str(f))
    res.notes.append(f"Websites: import {f} in Stylus (Manage → Import) – "
                     f"{len(ctx['site_styles'])} styles, importing again updates them.")


def write_stylus(cfg: dict) -> tuple[Path, int]:
    """Always (re)write the Stylus import file. Returns (path, number of styles)."""
    ctx = context(cfg)
    f = paths.STATE_DIR / STYLUS_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(stylus_json(ctx["site_styles"]))
    return f, len(ctx["site_styles"])


def apply(cfg: dict | None = None, dry: bool = False, push_bookmarks: bool = False) -> Result:
    cfg = cfg or config.load()
    res = Result()
    paths.ensure_dirs()
    profile = paths.librewolf_profile(cfg["general"].get("profile", ""))
    if profile is None:
        res.errors.append("No LibreWolf profile found. Start LibreWolf once (it creates one), "
                          "then run this again.")
        return res
    ctx = context(cfg)
    chrome = profile / "chrome"

    _write(chrome / "wolfforge/chrome.css", render("chrome.css.j2", ctx), res, dry)
    _write(chrome / "wolfforge/content.css", render("content.css.j2", ctx), res, dry)
    _stub(chrome / "userChrome.css", '@import url("wolfforge/chrome.css");',
          "Your own browser-UI rules below – they win over wolfforge's.", res, dry)
    _stub(chrome / "userContent.css", '@import url("wolfforge/content.css");',
          "Your own page rules below – they win over wolfforge's.", res, dry)

    _stylus_file(ctx, res, dry)

    start_url = None
    if cfg["startpage"]["enabled"]:
        start = paths.STATE_DIR / "start.html"
        _write(start, render("start.html.j2", ctx), res, dry)
        start_url = start.as_uri()

    if push_bookmarks:
        push_to_browser(cfg, profile, res, dry)

    userjs = profile / "user.js"
    before = userjs.read_text() if userjs.exists() else ""
    # privacy prefs go into user.js as well: user.js always wins over LibreWolf's defaults,
    # whichever folder this LibreWolf version reads librewolf.overrides.cfg from
    new = prefs.write_block(userjs, prefs.look_prefs(cfg, themes.resolved(cfg), start_url)
                            | prefs.privacy_prefs(cfg), "user_pref", dry)
    if new != before:
        res.written.append(str(userjs))

    ov = prefs.overrides_path()
    before = ov.read_text() if ov.exists() else ""
    new = prefs.write_block(ov, prefs.privacy_prefs(cfg), "pref", dry)
    if new != before:
        res.written.append(str(ov))

    if cfg["sites"]["dark_request"] and not prefs.dark_request_possible(cfg):
        res.notes.append("Dark-mode request has no effect at this privacy level (resist-fingerprinting "
                         "makes every site see 'light'). Use site rules, or privacy level 'comfort'.")
    if paths.is_running(profile):
        res.notes.append("LibreWolf is running – changes show after a restart.")
    return res


def push_to_browser(cfg: dict, profile: Path, res: Result, dry: bool = False) -> bool:
    """Bookmarks from the universal file replace LibreWolf's at its next start (one time).

    Written into prefs.js (not user.js): LibreWolf resets the switch itself after importing,
    so it really happens once. Needs LibreWolf closed, otherwise it would overwrite prefs.js.
    """
    if paths.is_running(profile):
        res.errors.append("Close LibreWolf first – bookmarks can only be handed over while it's closed.")
        return False
    marks = cfg.get("bookmarks", [])
    html_file = paths.STATE_DIR / "bookmarks-import.html"
    current = bm.read_places(profile)
    if not dry:
        paths.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        if current:
            (paths.BACKUP_DIR / time.strftime("browser-bookmarks-%Y%m%d-%H%M%S.html")).write_text(
                bm.to_html(current))
        html_file.write_text(bm.to_html(marks))
        pj = profile / "prefs.js"
        lines = [l for l in (pj.read_text(errors="replace").splitlines() if pj.exists() else [])
                 if "browser.places.importBookmarksHTML" not in l and "browser.bookmarks.file" not in l]
        lines += ['user_pref("browser.places.importBookmarksHTML", true);',
                  f'user_pref("browser.bookmarks.file", {json.dumps(str(html_file))});']
        pj.write_text("\n".join(lines) + "\n")
        cfg.setdefault("meta", {})["bookmarks_pushed"] = time.time()
    res.notes.append(f"{len(marks)} bookmarks replace LibreWolf's at its next start "
                     f"(the {len(current)} current ones are backed up).")
    res.written.append(str(profile / "prefs.js"))
    return True


def preview_json(cfg: dict) -> str:
    """Debug helper: the resolved look as JSON."""
    r = themes.resolved(cfg)
    return json.dumps({"theme": r["palette"].label, "colors": r["c"], "font": r["font"],
                       "radius": r["radius"], "art": r["art_name"]}, indent=2)
