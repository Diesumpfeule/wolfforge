"""wolfforge – the LibreWolf overhaul app (Textual)."""
from __future__ import annotations

import copy
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (Button, ContentSwitcher, Footer, Header, Input, Label, ListItem, ListView,
                             Select, Static, Switch)

from .. import ascii as asc
from .. import bookmarks as bm
from .. import config, firefox, generate, paths, prefs, themes

PAGES = [
    ("look", "\U000f03d8  Theme"),
    ("layout", "\U000f056e  Layout & bar"),
    ("sites", "\U000f059f  Websites"),
    ("start", "\U000f02dc  Start page"),
    ("privacy", "\U000f0483  Privacy"),
    ("bookmarks", "\U000f00c0  Bookmarks"),
    ("firefox", "\U000f0239  Import from Firefox"),
    ("file", "\U000f0214  File & apply"),
]

CSS = """
Screen { layout: vertical; }
#body { height: 1fr; }
#sidebar { width: 30; border-right: solid $panel; }
#sidebar ListItem { padding: 1 2; }
.page { padding: 1 3; }
.pagetitle { text-style: bold; color: $accent; padding-bottom: 1; }
.section { text-style: bold; color: $secondary; margin-top: 1; padding-bottom: 1;
           border-bottom: solid $panel; }
.frow { height: auto; margin-bottom: 1; }
.flabelbox { width: 1fr; height: auto; }
.flabel { padding-top: 1; }
.fhelp { color: $text-muted; }
.frow Input, .frow Select { width: 40; }
.frow Switch { margin-right: 30; }
.hint { color: $text-muted; padding-bottom: 1; }
.warn { color: $warning; padding-bottom: 1; }
.btnrow { height: auto; margin: 1 0; align: left middle; }
.btnrow Button { margin-right: 2; }
.btnrow Input { width: 1fr; margin-right: 2; }
.btnrow Select { width: 36; margin-right: 2; }
.list { height: auto; max-height: 16; border: round $panel; margin-bottom: 1; }
.list ListItem { padding: 0 1; height: auto; }
#themelist ListItem { height: 1; }
#themelist Horizontal { height: 1; }
#themelist Label { width: auto; }
.colrow { height: 3; }
.colrow Label { width: 22; padding-top: 1; }
.colrow Input { width: 14; }
.colrow .sw { width: 6; height: 3; margin-right: 1; }
#hero { height: auto; margin-bottom: 1; }
#hero_banner, #hero_art { width: auto; }
#hero_art { margin-left: 4; }
#statusbar { height: 1; background: $panel; padding: 0 2; color: $text-muted; }
Button { height: 1; min-width: 6; border: none; padding: 0 2; background: $panel; color: $text; text-style: bold; }
Button:hover { background: $accent 35%; }
Button:focus { background: $accent 55%; }
Button.-primary, Button.-success { background: $accent; color: $background; }
Button.-warning { background: $warning 75%; color: $background; }
App.-ui-win98 Button { height: 3; border: outer $panel-lighten-2; background: $panel; color: $text; }
App.-ui-win98 Button.-active, App.-ui-win98 Button:focus { border: inner $panel-lighten-2; }
App.-ui-win98 Button.-primary, App.-ui-win98 Button.-success { background: $accent; color: $background; }
App.-ui-wired Button { background: transparent; color: $accent; padding: 0 1; }
App.-ui-wired Button:hover, App.-ui-wired Button:focus { background: $accent; color: $background; }
"""


def textual_theme(p: themes.Palette):
    from textual.theme import Theme as TTheme
    c = p.colors
    return TTheme(name=f"wf-{p.id}-{c['accent'].lstrip('#')}", dark=p.dark, primary=c["accent"],
                  secondary=c["accent2"], accent=c["accent"], background=c["base"], surface=c["mantle"],
                  panel=c["surface"], foreground=c["text"], warning=c["yellow"], error=c["red"],
                  success=c["green"])


def two_tone(lines: list[str], face: str, shade: str) -> Text:
    t = Text(no_wrap=True)
    for i, line in enumerate(lines):
        if i:
            t.append("\n")
        for ch in line:
            t.append(ch, style=shade if ch in asc.SHADE else face)
    return t


class AnimatedArt(Static):
    """ASCII art that glints and twinkles (same effect as swayforge and the start page)."""

    def __init__(self, lines: list[str], palette: dict[str, str], animate: bool = True, **kw) -> None:
        super().__init__("", **kw)
        self.lines, self.palette, self.animate = lines, palette, animate
        self._timer = None

    def on_mount(self) -> None:
        import time
        self._t0 = time.monotonic()
        self.set_animate(self.animate)

    def _draw(self) -> None:
        import time
        from ..anim import rich_frame
        t = (time.monotonic() - self._t0 + 3.0) if self.animate else 10_000.0
        self.update(rich_frame(self.lines, t, self.palette))

    def set_animate(self, on: bool) -> None:
        self.animate = on
        if on and self._timer is None:
            self._timer = self.set_interval(1 / 12, self._draw)
        elif not on and self._timer is not None:
            self._timer.stop()
            self._timer = None
        self._draw()

    def set_art(self, lines: list[str], palette: dict[str, str]) -> None:
        self.lines, self.palette = lines, palette
        self._draw()


def art_palette(c: dict, main: str = "accent", bold: bool = False) -> dict[str, str]:
    b = "bold " if bold else ""
    return {"face": f"{b}{c[main]}", "shade": themes.mix(c[main], c["base"], 0.5),
            "glint": f"bold {c['text']}", "hot": f"bold {c['yellow']}"}


def swatch(c: dict) -> Text:
    t = Text()
    for k in ("base", "surface", "accent", "accent2", "red", "green", "yellow", "blue", "magenta", "cyan"):
        t.append("  ", style=f"on {c[k]}")
    return t


def section(title: str) -> Static:
    return Static(title, classes="section")


def wid(path: str) -> str:
    return "f__" + path.replace(".", "__")


def path_of(w: str) -> str:
    return w[3:].replace("__", ".")


def get(cfg: dict, path: str):
    node = cfg
    for k in path.split("."):
        node = node[k]
    return node


def put(cfg: dict, path: str, value) -> None:
    keys = path.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node[k]
    node[keys[-1]] = value


def field(cfg: dict, path: str, label: str, kind: str = "str", options=None, help: str = "") -> Horizontal:
    v = get(cfg, path)
    if kind == "bool":
        w = Switch(value=bool(v), id=wid(path))
    elif kind == "choice":
        opts = list(options or [])
        if v not in [o[1] for o in opts]:
            opts.append((str(v), v))
        w = Select(opts, value=v, allow_blank=False, id=wid(path))
    else:
        w = Input(value="" if v is None else str(v), type="integer" if kind == "int" else "text", id=wid(path))
    box = Vertical(Label(label, classes="flabel"), *([Label(help, classes="fhelp")] if help else []),
                   classes="flabelbox")
    return Horizontal(box, w, classes="frow")


class WolfforgeApp(App):
    ENABLE_COMMAND_PALETTE = False      # Textual's Ctrl+P command search – not useful here
    TITLE = "wolfforge"
    SUB_TITLE = "LibreWolf overhaul"
    CSS = CSS
    BINDINGS = [Binding("ctrl+s", "apply", "Save & apply", priority=True),
                Binding("ctrl+l", "redraw", "Redraw", priority=True),
                Binding("ctrl+r", "restart", "Restart LibreWolf"),
                Binding("ctrl+q", "quit", "Quit", priority=True)]

    def __init__(self, page: str = "look") -> None:
        super().__init__()
        self.cfg = config.load()
        self.start_page = page if page in dict(PAGES) else "look"
        self.dirty = False
        self.loading = True
        self.edit_colors = dict(themes.active(self.cfg).colors)

    # ── layout ───────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield ListView(*[ListItem(Label(label), id=f"nav-{pid}") for pid, label in PAGES], id="sidebar",
                           initial_index=[p for p, _ in PAGES].index(self.start_page))
            with ContentSwitcher(initial=f"page-{self.start_page}", id="pages"):
                for pid, _ in PAGES:
                    yield getattr(self, f"page_{pid}")()
        yield Static("", id="statusbar")
        yield Footer()

    def page(self, pid: str, *children) -> VerticalScroll:
        title = dict(PAGES)[pid].split("  ", 1)[-1]
        return VerticalScroll(Static(title, classes="pagetitle"), *children, id=f"page-{pid}", classes="page")

    def on_mount(self) -> None:
        for k, v in self.edit_colors.items():
            self.query_one(f"#sw__{k}", Static).styles.background = v
        self.use_palette()
        self.status()
        self.set_timer(0.5, self._loaded)

    def _loaded(self) -> None:
        self.loading = False

    def use_palette(self) -> None:
        th = textual_theme(themes.active(self.cfg))
        self.register_theme(th)
        self.theme = th.name
        for x in ("win98", "wired"):
            self.set_class(self.cfg["general"]["layout"] == x, f"-ui-{x}")
        r = themes.resolved(self.cfg)
        on = bool(self.cfg["general"].get("animate", True))
        for w in self.query("#hero_art").results(AnimatedArt):
            w.set_art(r["art"], art_palette(r["c"], "accent2"))
            w.set_animate(on)
        for w in self.query("#hero_banner").results(AnimatedArt):
            w.set_art(asc.best_banner("wolf", 60), art_palette(r["c"], bold=True))
            w.set_animate(on)

    def action_redraw(self) -> None:
        self.refresh(repaint=True, layout=True)
        self.screen.refresh(repaint=True, layout=True)

    def status(self, extra: str = "") -> None:
        prof = paths.librewolf_profile(self.cfg["general"]["profile"])
        running = paths.is_running(prof)
        p = themes.active(self.cfg)
        msg = (f"{p.label}  │  {self.cfg['general']['layout']}  │  privacy: {self.cfg['privacy']['level']}  │  "
               f"LibreWolf: {'running' if running else 'closed'}  │  "
               f"{'● unsaved – Ctrl+S' if self.dirty else '✓ saved'}")
        self.query_one("#statusbar", Static).update(msg + (f"  │  {extra}" if extra else ""))

    # ── pages ────────────────────────────────────────────────────────
    def page_look(self) -> VerticalScroll:
        cfg = self.cfg
        r = themes.resolved(cfg)
        c = r["c"]
        pals = themes.all_palettes(cfg)
        items = [ListItem(Horizontal(Label(f"{p.label}{'  (yours)' if p.source == 'yours' else ''}"[:44].ljust(46)),
                                     Label(swatch(p.colors))), name=pid) for pid, p in pals.items()]
        ids = list(pals)
        cur = themes.SYSTEM_ID if cfg["general"]["follow_system"] and themes.SYSTEM_ID in pals \
            else cfg["general"]["theme"]
        has_sys = themes.SYSTEM_ID in pals
        arts = [("Theme's motif", "auto")] + [(n, n) for n in asc.all_art()]
        acc = [("Theme default", "")] + [(k, k) for k in ("accent2", "blue", "cyan", "green", "yellow",
                                                            "orange", "red", "magenta")]
        colrows = [Horizontal(Label(themes.COLOR_LABELS[k]), Static(" ", classes="sw", id=f"sw__{k}"),
                              Input(self.edit_colors[k], id=f"col__{k}", max_length=7), classes="colrow")
                   for k in themes.COLOR_KEYS]
        return self.page(
            "look",
            Horizontal(AnimatedArt(asc.best_banner("wolf", 60), art_palette(c, bold=True),
                                   cfg["general"].get("animate", True), id="hero_banner"),
                       AnimatedArt(r["art"], art_palette(c, "accent2"), cfg["general"].get("animate", True),
                                   id="hero_art"), id="hero"),
            Static("Recolours LibreWolf's toolbars, tabs, menus, address bar, about: pages, new tab and "
                   "start page. With swayforge it follows your system theme automatically.", classes="hint"),
            field(cfg, "general.follow_system", "Follow the system theme (swayforge)", "bool",
                  help="found" if has_sys else "swayforge palette not found – pick a theme below"),
            ListView(*items, id="themelist", classes="list", initial_index=ids.index(cur) if cur in ids else 0),
            field(cfg, "general.accent", "Accent colour", "choice", acc),
            field(cfg, "general.art", "ASCII art", "choice", arts, help="start page, new tab, header"),
            field(cfg, "general.animate", "Animate the ASCII art", "bool", help="glint + sparks, here and in LibreWolf"),
            field(cfg, "general.font", "Font", help="empty = theme/system font · a Nerd Font looks best"),
            field(cfg, "general.font_size", "Font size", "int"),
            field(cfg, "general.radius", "Corner radius", "int", help="-1 = from theme · 0 = square"),
            section("Edit colours → save as your own theme"),
            Static("Change any colour, then give it a name and save. Saved themes live in the universal "
                   "file (wolfforge.toml) – they travel with it.", classes="hint"),
            *colrows,
            Horizontal(Input(placeholder="name of your theme", id="theme_name"),
                       Button("Save as my theme", id="theme_save", variant="success"),
                       Button("Reset colours", id="theme_reset"), classes="btnrow"),
        )

    def page_layout(self) -> VerticalScroll:
        cfg = self.cfg
        lay_items = [ListItem(Label(f"[b]{k:<9}[/b] [dim]{escape(v)}[/]"), name=k) for k, v in generate.LAYOUTS.items()]
        lays = list(generate.LAYOUTS)
        cur = cfg["general"]["layout"]
        add_opts = [(lbl, k) for k, (_w, lbl) in config.TOOLBAR_BUTTONS.items()]
        return self.page(
            "layout",
            ListView(*lay_items, id="layoutlist", classes="list",
                     initial_index=lays.index(cur) if cur in lays else 0),
            field(cfg, "general.layout_follow", "Take the layout from swayforge", "bool",
                  help="Classic 98 → win98, Wired → wired, others → classic"),
            field(cfg, "toolbar.tabs", "Tabs", "choice",
                  [("On top", "top"), ("Vertical (sidebar)", "vertical"), ("Hidden – keyboard only", "hidden")],
                  help="hidden: Ctrl+Tab / Ctrl+PgUp/PgDn still switch"),
            field(cfg, "toolbar.bookmarks_bar", "Bookmarks bar", "choice",
                  [("Always", "always"), ("Only on new tab", "newtab"), ("Never", "never")]),
            field(cfg, "general.density", "Density", "choice",
                  [("Compact", "compact"), ("Normal", "normal"), ("Touch", "touch")]),
            field(cfg, "toolbar.tab_width", "Max tab width (px)", "int", help="0 = tabs stretch to fill the bar"),
            field(cfg, "toolbar.instant_resize", "Re-flow tabs right after closing one", "bool",
                  help="off = Firefox default: widths stay until the mouse leaves the tab bar"),
            field(cfg, "toolbar.close_buttons", "Close buttons on tabs", "bool", help="off = only on hover"),
            field(cfg, "toolbar.title_banner", "ASCII tag in the tab bar", "bool"),
            section("Toolbar buttons (left → right)"),
            Static("Select a button, move it with ↑/↓ or remove it. The address bar always stays. "
                   "Applied at LibreWolf's next start – your toolbar is saved in the universal file.",
                   classes="hint"),
            ListView(*self._button_items(), id="buttonlist", classes="list"),
            Horizontal(Button("↑ Up", id="btn_up"), Button("↓ Down", id="btn_down"),
                       Button("Remove", id="btn_remove", variant="warning"), classes="btnrow"),
            Horizontal(Select(add_opts, prompt="add a button …", id="btn_add_sel"),
                       Button("Add", id="btn_add", variant="primary"),
                       Button("Read from LibreWolf", id="btn_read"), classes="btnrow"),
        )

    def _button_items(self) -> list[ListItem]:
        return [ListItem(Label(f"{i + 1:>2}. {config.TOOLBAR_BUTTONS[k][1]}"), name=k)
                for i, k in enumerate(self.cfg["toolbar"]["buttons"])]

    def page_sites(self) -> VerticalScroll:
        cfg = self.cfg
        warn = [] if prefs.dark_request_possible(cfg) else [Static(
            "⚠ At this privacy level resist-fingerprinting is on – every site sees 'light', so the "
            "dark-mode request does nothing. Use site rules below, or privacy level 'comfort'.", classes="warn")]
        modes = [(v, k) for k, v in config.SITE_MODES.items()]
        return self.page(
            "sites",
            Static("Safe touches never break a page: a site's own styles always win.", classes="hint"),
            field(cfg, "sites.dark_request", "Ask websites for their dark version", "bool"),
            *warn,
            field(cfg, "sites.scrollbars", "Scrollbars in your colours", "bool"),
            field(cfg, "sites.selection", "Text selection in your accent", "bool"),
            field(cfg, "sites.caret", "Cursor (caret) in your accent", "bool"),
            field(cfg, "sites.focus_ring", "Focus ring in your accent", "bool"),
            section("DuckDuckGo in your colours"),
            Static("Uses DuckDuckGo's own appearance settings (background, text, links, header, font) – "
                   "works on every search started from the start page. For the address bar, add it once "
                   "as a search engine: Copy URL → LibreWolf Settings → Search → Search Shortcuts → Add, "
                   "paste, then pick it as default engine.", classes="hint"),
            field(cfg, "sites.duckduckgo", "Theme DuckDuckGo", "bool"),
            Horizontal(Button("Copy search URL", id="ddg_copy", variant="primary"),
                       Button("Open search settings", id="ddg_settings"), classes="btnrow"),
            section("Theme packs (experimental)"),
            Static("Recolour sites that build their look from colour variables – they keep working, only "
                   "colours change. If a site's update renames its variables, the pack simply does nothing.",
                   classes="hint"),
            *[field(cfg, f"sites.packs.{k}", v, "bool") for k, v in config.SITE_PACKS.items()],
            section("Per-site rules (opt-in)"),
            Static("For sites without a dark mode. 'invert' works almost everywhere, 'theme' only on "
                   "simple text sites. Remove a rule if a site looks wrong.", classes="hint"),
            ListView(*self._rule_items(), id="rulelist", classes="list"),
            Horizontal(Input(placeholder="example.org", id="rule_domain"),
                       Select(modes, value="invert", allow_blank=False, id="rule_mode"),
                       Button("Add", id="rule_add", variant="primary"),
                       Button("Remove selected", id="rule_remove", variant="warning"), classes="btnrow"),
        )

    def _rule_items(self) -> list[ListItem]:
        rules = self.cfg["sites"]["rules"]
        if not rules:
            return [ListItem(Label("[dim]no rules yet[/]"), name="")]
        return [ListItem(Label(f"{r['domain']:<34} {r['mode']}"), name=str(i)) for i, r in enumerate(rules)]

    def page_start(self) -> VerticalScroll:
        cfg = self.cfg
        eng = [(v[0], k) for k, v in config.SEARCH.items()]
        return self.page(
            "start",
            Static("Your home page: 3D banner, ASCII art, clock, search and your bookmarks as tiles. "
                   "Type anywhere to search, 1–9 open the first links.", classes="hint"),
            field(cfg, "startpage.enabled", "Use the wolfforge start page as home", "bool"),
            field(cfg, "startpage.banner", "Banner text", help="empty = librewolf"),
            field(cfg, "startpage.search", "Search engine", "choice", eng),
            field(cfg, "startpage.bookmarks", "Show bookmarks", "bool"),
            field(cfg, "startpage.clock", "Show clock", "bool"),
            field(cfg, "startpage.newtab", "ASCII art on the new-tab page too", "bool"),
            Horizontal(Button("Open start page", id="start_open"), classes="btnrow"),
        )

    def page_privacy(self) -> VerticalScroll:
        cfg = self.cfg
        lv = [(f"{k} – {v}", k) for k, v in config.PRIVACY_LEVELS.items()]
        return self.page(
            "privacy",
            Static("LibreWolf already blocks telemetry, studies, Pocket, sponsored content and trackers. "
                   "Pick how far it goes beyond that. Written to librewolf.overrides.cfg – applied at the "
                   "next start.", classes="hint"),
            field(cfg, "privacy.level", "Level", "choice", lv),
            field(cfg, "privacy.sync", "Firefox Sync (account)", "bool",
                  help="bookmarks, passwords, add-ons from your Firefox account"),
            field(cfg, "privacy.remember_passwords", "Offer to save passwords", "bool"),
            field(cfg, "privacy.drm", "DRM (Netflix, Spotify web, Disney+)", "bool"),
            field(cfg, "privacy.restore_session", "Reopen last tabs", "bool", help="level 'comfort' only"),
        )

    def page_bookmarks(self) -> VerticalScroll:
        marks = self.cfg["bookmarks"]
        folders: dict[str, int] = {}
        for b in marks:
            folders[b.get("folder", "Menu")] = folders.get(b.get("folder", "Menu"), 0) + 1
        rows = [ListItem(Label(f"{f:<40} {n:>4}")) for f, n in sorted(folders.items())] or \
            [ListItem(Label("[dim]none yet – pull them from LibreWolf or import from Firefox[/]"))]
        return self.page(
            "bookmarks",
            Static(f"{len(marks)} bookmarks in the universal file. They show on the start page and travel "
                   "with the file.", classes="hint", id="bm_count"),
            ListView(*rows, id="bmfolders", classes="list"),
            Horizontal(Button("Pull from LibreWolf", id="bm_pull", variant="primary"),
                       Button("Push to LibreWolf", id="bm_push", variant="warning"),
                       Button("Edit in the file ✎", id="bm_edit"), classes="btnrow"),
            Static("Pull = add LibreWolf's bookmarks to the file (nothing is deleted). "
                   "Push = the file replaces LibreWolf's bookmarks at its next start (needs LibreWolf "
                   "closed; the old ones are backed up).", classes="hint"),
        )

    def page_firefox(self) -> VerticalScroll:
        ff = paths.firefox_profile()
        if not ff:
            return self.page("firefox", Static("No Firefox profile found (~/.mozilla/firefox).", classes="hint"),
                             Static("Tip: with a Firefox account just switch on Sync on the Privacy page and "
                                    "sign in in LibreWolf – bookmarks, passwords and add-ons follow.",
                                    classes="hint"))
        s = firefox.summary(ff)
        exts = ", ".join(e["name"] for e in s["extensions"]) or "none"
        return self.page(
            "firefox",
            Static(f"Firefox profile: {str(ff).replace(str(paths.HOME), '~')}\n"
                   f"{s['bookmarks']} bookmarks · {s['passwords']} saved passwords · add-ons: {exts}",
                   classes="hint"),
            Static("Easiest with a Firefox account: Privacy → Firefox Sync on, then sign in in LibreWolf. "
                   "Without an account, take it over here:", classes="hint"),
            Horizontal(Button("Import bookmarks", id="ff_bm", variant="primary"),
                       Button("Import add-on list", id="ff_ext"),
                       Button("Open add-on pages in LibreWolf", id="ff_ext_open"), classes="btnrow"),
            section("Passwords"),
            Static("Copied straight into the LibreWolf profile (logins.json + key4.db) – never into the "
                   "universal file. LibreWolf must be closed.", classes="hint"),
            Horizontal(Label("Replace LibreWolf's saved passwords", classes="flabel flabelbox"),
                       Switch(False, id="ff_replace"), classes="frow"),
            Horizontal(Button("Copy passwords", id="ff_pw", variant="warning"), classes="btnrow"),
        )

    def page_file(self) -> VerticalScroll:
        prof = paths.librewolf_profile(self.cfg["general"]["profile"])
        return self.page(
            "file",
            Static("Everything – look, layout, toolbar, website rules, privacy, your themes, add-on list and "
                   "bookmarks – lives in one file:", classes="hint"),
            Static(f"  {paths.UNIVERSAL}", classes="hint"),
            Horizontal(Button("Save & apply (Ctrl+S)", id="apply", variant="success"),
                       Button("Restart LibreWolf (Ctrl+R)", id="restart", variant="warning"),
                       Button("Open file ✎", id="open_file"), classes="btnrow"),
            section("Move it"),
            Horizontal(Input(str(paths.HOME / "wolfforge.toml"), id="io_path"),
                       Button("Export", id="export", variant="primary"), Button("Import", id="import"),
                       classes="btnrow"),
            section("About"),
            Static("wolfforge – proof of concept, written by Claude (Anthropic). Provided as is, without any "
                   "warranty; use at your own risk. Not affiliated with LibreWolf or Mozilla.", classes="hint"),
            section("Profile"),
            field(self.cfg, "general.profile", "LibreWolf profile folder",
                  help=f"empty = default ({str(prof).replace(str(paths.HOME), '~') if prof else 'none found'})"),
            Static(f"Generated: <profile>/chrome/wolfforge/*.css, user.js block, "
                   f"{str(prefs.overrides_path()).replace(str(paths.HOME), '~')} block, "
                   f"{str(paths.STATE_DIR / 'start.html').replace(str(paths.HOME), '~')}.\n"
                   "Your own CSS goes into chrome/userChrome.css and userContent.css below the @import – "
                   "it always wins.", classes="hint"),
        )

    # ── events ───────────────────────────────────────────────────────
    @on(ListView.Highlighted, "#sidebar")
    def nav(self, ev: ListView.Highlighted) -> None:
        if ev.item and ev.item.id:
            self.query_one("#pages", ContentSwitcher).current = "page-" + ev.item.id[4:]

    def changed(self, note: str = "") -> None:
        if self.loading:
            return
        self.dirty = True
        self.status(note)

    @on(Input.Changed)
    def input_changed(self, ev: Input.Changed) -> None:
        w = ev.input.id or ""
        if w.startswith("col__"):
            k = w[5:]
            if themes.HEX.match(ev.value):
                self.edit_colors[k] = ev.value
                self.query_one(f"#sw__{k}", Static).styles.background = ev.value
            return
        if not w.startswith("f__"):
            return
        path = path_of(w)
        old = get(self.cfg, path)
        if isinstance(old, int) and not isinstance(old, bool):
            try:
                put(self.cfg, path, int(ev.value))
            except ValueError:
                return
        else:
            put(self.cfg, path, ev.value)
        self.changed()

    @on(Switch.Changed)
    def switch_changed(self, ev: Switch.Changed) -> None:
        w = ev.switch.id or ""
        if w.startswith("f__"):
            put(self.cfg, path_of(w), ev.value)
            if w in (wid("general.follow_system"), wid("general.animate")):
                self.use_palette()
            self.changed()

    @on(Select.Changed)
    def select_changed(self, ev: Select.Changed) -> None:
        w = ev.select.id or ""
        if w.startswith("f__") and ev.value is not Select.BLANK:
            put(self.cfg, path_of(w), ev.value)
            if w in (wid("general.accent"), wid("general.art")):
                self.use_palette()
            self.changed()

    @on(ListView.Selected, "#themelist")
    def pick_theme(self, ev: ListView.Selected) -> None:
        tid = ev.item.name or ""
        if tid == themes.SYSTEM_ID:
            self.cfg["general"]["follow_system"] = True
        else:
            self.cfg["general"]["follow_system"] = False
            self.cfg["general"]["theme"] = tid
        self.query_one(f"#{wid('general.follow_system')}", Switch).value = tid == themes.SYSTEM_ID
        self.edit_colors = dict(themes.active(self.cfg).colors)
        for k, v in self.edit_colors.items():
            self.query_one(f"#col__{k}", Input).value = v
        self.use_palette()
        self.changed(f"theme: {themes.active(self.cfg).label}")

    @on(ListView.Selected, "#layoutlist")
    def pick_layout(self, ev: ListView.Selected) -> None:
        self.cfg["general"]["layout"] = ev.item.name
        self.use_palette()
        self.changed(f"layout: {ev.item.name}")

    def refresh_list(self, sel: str, items: list[ListItem], index: int | None = None) -> None:
        lv = self.query_one(sel, ListView)
        lv.clear()
        lv.extend(items)
        if index is not None and items:
            lv.index = max(0, min(index, len(items) - 1))

    @on(Button.Pressed)
    def button(self, ev: Button.Pressed) -> None:
        bid = ev.button.id or ""
        tb = self.cfg["toolbar"]["buttons"]
        if bid in ("btn_up", "btn_down", "btn_remove"):
            lv = self.query_one("#buttonlist", ListView)
            i = lv.index
            if i is None or i >= len(tb):
                return
            if bid == "btn_remove":
                if tb[i] == "urlbar":
                    self.notify("The address bar stays.", severity="warning")
                    return
                tb.pop(i)
                j = i
            else:
                j = i - 1 if bid == "btn_up" else i + 1
                if not 0 <= j < len(tb):
                    return
                tb[i], tb[j] = tb[j], tb[i]
            self.refresh_list("#buttonlist", self._button_items(), j)
            self.changed()
        elif bid == "btn_add":
            v = self.query_one("#btn_add_sel", Select).value
            if v is Select.BLANK:
                return
            if v in tb and v != "spacer":
                self.notify("Already in the toolbar.")
                return
            tb.append(v)
            self.refresh_list("#buttonlist", self._button_items(), len(tb) - 1)
            self.changed()
        elif bid == "btn_read":
            self.read_toolbar()
        elif bid == "rule_add":
            dom = self.query_one("#rule_domain", Input).value.strip().lower()
            dom = dom.removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]
            if not generate.DOMAIN.match(dom):
                self.notify("That doesn't look like a domain (example.org).", severity="error")
                return
            mode = self.query_one("#rule_mode", Select).value
            rules = [r for r in self.cfg["sites"]["rules"] if r["domain"] != dom]
            rules.append({"domain": dom, "mode": mode})
            self.cfg["sites"]["rules"] = rules
            self.query_one("#rule_domain", Input).value = ""
            self.refresh_list("#rulelist", self._rule_items(), len(rules) - 1)
            self.changed(f"rule: {dom} → {mode}")
        elif bid == "rule_remove":
            lv = self.query_one("#rulelist", ListView)
            item = lv.highlighted_child
            if item and item.name:
                self.cfg["sites"]["rules"].pop(int(item.name))
                self.refresh_list("#rulelist", self._rule_items(), lv.index)
                self.changed()
        elif bid == "theme_save":
            name = self.query_one("#theme_name", Input).value.strip()
            if not name:
                self.notify("Give your theme a name first.", severity="warning")
                return
            dark = themes.luminance(self.edit_colors["base"]) < 0.4
            tid = themes.save_theme(self.cfg, name, name, self.edit_colors, dark)
            self.query_one(f"#{wid('general.follow_system')}", Switch).value = False
            self.use_palette()
            self.changed(f"saved theme '{tid}'")
            self.notify(f"Theme “{name}” saved – it's in the theme list after the next start of the app.")
        elif bid == "theme_reset":
            self.edit_colors = dict(themes.active(self.cfg).colors)
            for k, v in self.edit_colors.items():
                self.query_one(f"#col__{k}", Input).value = v
        elif bid == "ddg_copy":
            url = generate.ddg_search_url(self.cfg)
            copied = False
            if shutil.which("wl-copy"):
                copied = subprocess.run(["wl-copy", url], check=False).returncode == 0
            (paths.STATE_DIR / "duckduckgo-search-url.txt").write_text(url + "\n")
            self.notify(("Copied! " if copied else "Saved to ~/.local/share/wolfforge/duckduckgo-search-url.txt – ")
                        + "LibreWolf → Settings → Search → Search Shortcuts → Add → paste. "
                        "Name it e.g. 'DuckDuckGo (themed)', keyword @d, then choose it as default.", timeout=12)
            self.copy_to_clipboard(url)
        elif bid == "ddg_settings":
            if not self.open_in_browser("about:preferences#search"):
                self.notify("LibreWolf not found", severity="error")
        elif bid == "start_open":
            self.action_apply()
            if not self.open_in_browser((paths.STATE_DIR / "start.html").as_uri()):
                self.notify("LibreWolf not found", severity="error")
        elif bid == "bm_pull":
            self.pull_bookmarks()
        elif bid == "bm_push":
            self.push_bookmarks()
        elif bid in ("bm_edit", "open_file"):
            self.edit_file()
        elif bid == "ff_bm":
            ff = paths.firefox_profile()
            new = bm.read_places(ff) if ff else []
            self.cfg["bookmarks"], n = bm.merge(self.cfg["bookmarks"], new)
            self.changed(f"{n} bookmarks imported from Firefox")
            self.notify(f"{n} new bookmarks from Firefox. Push them to LibreWolf on the Bookmarks page.")
        elif bid == "ff_ext":
            ff = paths.firefox_profile()
            exts = firefox.extensions(ff) if ff else []
            known = {e["id"] for e in self.cfg["extensions"]}
            add = [e for e in exts if e["id"] not in known]
            self.cfg["extensions"] += add
            self.changed(f"{len(add)} add-ons listed")
            self.notify(f"{len(add)} add-ons added to the list. 'Open add-on pages' installs them in "
                        "LibreWolf with one click each.")
        elif bid == "ff_ext_open":
            exts = self.cfg["extensions"] or (firefox.extensions(paths.firefox_profile())
                                              if paths.firefox_profile() else [])
            if not firefox.open_addon_pages(exts):
                self.notify("Nothing to open (or LibreWolf not found).", severity="warning")
        elif bid == "ff_pw":
            ff = paths.firefox_profile()
            lw = paths.librewolf_profile(self.cfg["general"]["profile"])
            if ff and lw:
                self.notify(firefox.copy_passwords(ff, lw, self.query_one("#ff_replace", Switch).value),
                            timeout=8)
        elif bid == "apply":
            self.action_apply()
        elif bid == "restart":
            self.action_restart()
        elif bid == "export":
            dst = Path(os.path.expanduser(self.query_one("#io_path", Input).value.strip()))
            config.save(self.cfg)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths.UNIVERSAL, dst)
            self.notify(f"Exported to {dst}")
        elif bid == "import":
            src = Path(os.path.expanduser(self.query_one("#io_path", Input).value.strip()))
            if not src.is_file():
                self.notify("File not found", severity="error")
                return
            try:
                self.cfg = config.load(src)
            except Exception as e:                       # noqa: BLE001 – show any TOML error
                self.notify(f"Can't read it: {e}", severity="error")
                return
            config.save(self.cfg)
            self.notify("Imported – restarting the app view …")
            self.exit(result="reload")

    # ── actions ──────────────────────────────────────────────────────
    def action_apply(self) -> None:
        res = generate.apply(self.cfg)
        config.save(self.cfg)
        self.dirty = False
        if res.errors:
            self.notify("\n".join(res.errors), severity="error", timeout=10)
        else:
            self.notify(f"Applied: {len(res.written)} file(s) updated."
                        + ("\n" + "\n".join(res.notes) if res.notes else ""), timeout=8)
        self.status()

    def action_restart(self) -> None:
        if self.dirty:
            self.action_apply()
        self.restart_browser()

    @work(thread=True)
    def restart_browser(self) -> None:
        prof = paths.librewolf_profile(self.cfg["general"]["profile"])
        if paths.is_running(prof):
            subprocess.run(["pkill", "-TERM", "-x", "librewolf"], check=False)
            for _ in range(40):
                if not paths.is_running(prof):
                    break
                time.sleep(0.25)
        ok = self.open_in_browser(None)
        self.call_from_thread(self.status, "LibreWolf restarted" if ok else "LibreWolf not found")

    @staticmethod
    def open_in_browser(url: str | None) -> bool:
        exe = shutil.which("librewolf")
        cmd = [exe] if exe else (["flatpak", "run", "io.gitlab.librewolf-community"] if shutil.which("flatpak")
                                 else None)
        if not cmd:
            return False
        subprocess.Popen(cmd + ([url] if url else []), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def pull_bookmarks(self) -> None:
        prof = paths.librewolf_profile(self.cfg["general"]["profile"])
        if not prof:
            self.notify("No LibreWolf profile found", severity="error")
            return
        self.cfg["bookmarks"], n = bm.merge(self.cfg["bookmarks"], bm.read_places(prof))
        self.changed(f"{n} bookmarks pulled")
        self.notify(f"{n} new bookmarks from LibreWolf added to the file.")

    def push_bookmarks(self) -> None:
        prof = paths.librewolf_profile(self.cfg["general"]["profile"])
        if not prof:
            self.notify("No LibreWolf profile found", severity="error")
            return
        res = generate.Result()
        if generate.push_to_browser(self.cfg, prof, res):
            config.save(self.cfg)
            self.notify("\n".join(res.notes), timeout=8)
        else:
            self.notify("\n".join(res.errors), severity="error", timeout=8)

    def read_toolbar(self) -> None:
        prof = paths.librewolf_profile(self.cfg["general"]["profile"])
        raw = prefs.read_user_pref(prof, "browser.uiCustomization.state") if prof else None
        if not raw:
            self.notify("LibreWolf hasn't saved a toolbar yet.", severity="warning")
            return
        import json
        try:
            state = json.loads(json.loads(raw))
        except ValueError:
            self.notify("Couldn't read LibreWolf's toolbar.", severity="error")
            return
        back = {w: k for k, (w, _l) in config.TOOLBAR_BUTTONS.items()}
        keys = []
        for w in state.get("placements", {}).get("nav-bar", []):
            if w.startswith("customizableui-special-spring"):
                keys.append("spacer")
            elif w in back and back[w] not in keys:
                keys.append(back[w])
        if "urlbar" not in keys:
            keys.insert(0, "urlbar")
        self.cfg["toolbar"]["buttons"] = keys
        self.refresh_list("#buttonlist", self._button_items(), 0)
        self.changed("toolbar read from LibreWolf")

    def edit_file(self) -> None:
        config.save(self.cfg)
        editor = os.environ.get("EDITOR") or shutil.which("nvim") or shutil.which("nano") or "vi"
        with self.suspend():
            subprocess.run([*shlex.split(editor), str(paths.UNIVERSAL)], check=False)
        try:
            self.cfg = config.load()
        except Exception as e:                           # noqa: BLE001
            self.notify(f"The file has an error now: {e}", severity="error", timeout=10)
            return
        self.notify("File reloaded. Ctrl+S applies it.")
        self.exit(result="reload")


def run(page: str = "look") -> None:
    from ..crash import run_app
    while True:
        result = run_app("wolfforge", WolfforgeApp(page))
        if result != "reload":
            break
