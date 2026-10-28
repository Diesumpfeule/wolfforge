"""The universal file: ~/.config/wolfforge/wolfforge.toml.

Everything lives in this one file – look, layout, toolbar, website rules, privacy,
your saved themes, extensions and bookmarks. Copy it to a new machine, run
`wolfforge apply`, done. It's plain TOML, so editing it by hand is fine too.
"""
from __future__ import annotations

import copy
import json
import re
import time
import tomllib
from pathlib import Path

from . import paths

VERSION = 1

TOOLBAR_BUTTONS: dict[str, tuple[str, str]] = {
    # key: (Firefox widget id, label)
    "back": ("back-button", "Back"),
    "forward": ("forward-button", "Forward"),
    "reload": ("stop-reload-button", "Reload / stop"),
    "home": ("home-button", "Home (start page)"),
    "urlbar": ("urlbar-container", "Address bar"),
    "spacer": ("spring", "Flexible space"),
    "downloads": ("downloads-button", "Downloads"),
    "library": ("library-button", "Library (history, bookmarks)"),
    "bookmarks": ("bookmarks-menu-button", "Bookmarks menu"),
    "sidebar": ("sidebar-button", "Sidebar"),
    "screenshot": ("screenshot-button", "Screenshot"),
    "private": ("privatebrowsing-button", "New private window"),
    "print": ("print-button", "Print"),
    "fullscreen": ("fullscreen-button", "Fullscreen"),
    "devtools": ("developer-button", "Developer tools"),
    "extensions": ("unified-extensions-button", "Extensions"),
    "account": ("fxa-toolbar-menu-button", "Firefox account (Sync)"),
}

PRIVACY_LEVELS = {
    "comfort": "LibreWolf privacy, but logins, cookies and history survive a restart; "
               "Netflix/DRM and dark websites work",
    "librewolf": "LibreWolf as shipped – everything cleared on exit, resist-fingerprinting on",
    "fortress": "Maximum: + WebRTC off, WebGL off, letterboxing, strict referrers – some sites break",
}

SITE_PACKS = {
    "github": "GitHub – recolours GitHub's own colour variables (Primer)",
    "wikipedia": "Wikipedia – recolours Wikipedia's design tokens (Codex)",
    "youtube": "YouTube – backgrounds, text, header, search, menus, sidebar, progress bar",
}

SITE_MODES = {
    "invert": "Dark: smart invert (images stay normal)",
    "dim": "Dim: lower brightness + warm tint",
    "theme": "Theme: page background/text in your colours (simple sites only)",
    "off": "Off: never touch this site",
}

DEFAULTS: dict = {
    "version": VERSION,
    "general": {
        "profile": "",               # empty = LibreWolf's default profile
        "follow_system": True,       # take colours/font/art from swayforge if it's installed
        "theme": "type-o",
        "accent": "",
        "layout": "classic",
        "layout_follow": False,      # take the layout from swayforge (win98 → win98, wired → wired)
        "font": "",                  # empty = system font (swayforge's Nerd Font)
        "font_size": 13,
        "radius": -1,                # -1 = from theme (retro themes → 0)
        "art": "auto",
        "animate": True,             # ASCII art glints and twinkles (start page, new tab, app)
        "motion": "wave",            # and moves: wave | float | drift | glint (follows swayforge when you do)
        "density": "compact",        # compact | normal | touch
    },
    "toolbar": {
        "buttons": ["back", "forward", "reload", "urlbar", "downloads", "extensions"],
        "bookmarks_bar": "newtab",   # always | newtab | never
        "tabs": "top",               # top | vertical | hidden (keyboard only)
        "tab_width": 180,            # max px per tab · 0 = tabs stretch to fill the whole bar
        "instant_resize": True,      # tabs re-flow right after closing one (not when the mouse leaves)
        "close_buttons": False,
        "title_banner": True,        # tiny ASCII tag in the empty tab-strip area
    },
    "sites": {
        "engine": "stylus",          # stylus (import file for the Stylus add-on) | usercss (built in, no add-on)
        "dark_request": True,        # ask websites for their dark version
        "scrollbars": True,
        "selection": True,
        "focus_ring": True,
        "caret": True,
        "rules": [],                 # [{domain, mode}]
        "duckduckgo": True,          # DuckDuckGo in your colours (official settings parameters)
        "packs": {"github": False, "wikipedia": False, "youtube": False},   # experimental site themes
    },
    "startpage": {
        "enabled": True,
        "banner": "",                # empty = "librewolf"
        "search": "duckduckgo",
        "bookmarks": True,
        "clock": True,
        "newtab": True,              # restyle about:newtab too
    },
    "privacy": {
        "level": "comfort",
        "sync": False,               # Firefox account sync (bookmarks, passwords, add-ons)
        "remember_passwords": True,
        "drm": True,
        "restore_session": True,
    },
    "themes": {},                    # your saved themes: {id: {label, dark, colors{…}}}
    "extensions": [],                # [{id, name}] – from Firefox import or added by you
    "bookmarks": [],                 # [{title, url, folder}] – folder like "Toolbar/Dev"
    "meta": {"bookmarks_pushed": 0.0},
}

SEARCH = {
    "duckduckgo": ("DuckDuckGo", "https://duckduckgo.com/", "q"),
    "startpage": ("Startpage", "https://www.startpage.com/sp/search", "query"),
    "brave": ("Brave Search", "https://search.brave.com/search", "q"),
    "searxng": ("SearXNG (searx.be)", "https://searx.be/search", "q"),
    "google": ("Google", "https://www.google.com/search", "q"),
    "kagi": ("Kagi", "https://kagi.com/search", "q"),
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in ("themes",):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path: Path | None = None) -> dict:
    p = path or paths.UNIVERSAL
    data = {}
    if p.exists():
        data = tomllib.loads(p.read_text())
    cfg = _merge(DEFAULTS, data)
    cfg["toolbar"]["buttons"] = [b for b in cfg["toolbar"]["buttons"] if b in TOOLBAR_BUTTONS] or \
        list(DEFAULTS["toolbar"]["buttons"])
    if "urlbar" not in cfg["toolbar"]["buttons"]:
        cfg["toolbar"]["buttons"].insert(0, "urlbar")
    return cfg


def save(cfg: dict, path: Path | None = None) -> Path:
    p = path or paths.UNIVERSAL
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        bdir = paths.BACKUP_DIR
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / f"wolfforge-{time.strftime('%Y%m%d-%H%M%S')}.toml").write_text(p.read_text())
        _prune(bdir, 20)
    p.write_text(dumps(cfg))
    return p


def _prune(d: Path, keep: int) -> None:
    files = sorted(d.glob("wolfforge-*.toml"))
    for f in files[:-keep]:
        f.unlink(missing_ok=True)


# ── TOML writer with arrays of tables ([[bookmarks]]) ───────────────
_BARE = re.compile(r"^[A-Za-z0-9_-]+$")
HEADER = """\
# wolfforge – one file for your whole LibreWolf setup.
# Look, layout, toolbar, website rules, privacy, saved themes, extensions, bookmarks.
# Edit here or in the app (`wolfforge`), then run `wolfforge apply`.
"""

ORDER = ["version", "general", "toolbar", "sites", "startpage", "privacy", "themes",
         "extensions", "bookmarks", "meta"]


def _key(k: str) -> str:
    return k if _BARE.match(k) else json.dumps(k)


def _val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_val(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_key(k)} = {_val(x)}" for k, x in v.items()) + " }"
    raise TypeError(type(v))


def _table(name: str, d: dict, out: list[str]) -> None:
    scal = {k: v for k, v in d.items() if not isinstance(v, dict)
            and not (isinstance(v, list) and v and all(isinstance(x, dict) for x in v))}
    subs = {k: v for k, v in d.items() if isinstance(v, dict)}
    arrs = {k: v for k, v in d.items() if k not in scal and k not in subs}
    out.append(f"\n[{name}]")
    for k, v in scal.items():
        out.append(f"{_key(k)} = {_val(v)}")
    for k, v in subs.items():
        _table(f"{name}.{_key(k)}", v, out)
    for k, v in arrs.items():
        for item in v:
            out.append(f"\n[[{name}.{_key(k)}]]")
            out.extend(f"{_key(a)} = {_val(b)}" for a, b in item.items())


def dumps(cfg: dict) -> str:
    out = [HEADER.rstrip()]
    keys = ORDER + [k for k in cfg if k not in ORDER]
    for k in keys:
        if k not in cfg:
            continue
        v = cfg[k]
        if isinstance(v, dict):
            _table(_key(k), v, out)
        elif isinstance(v, list) and all(isinstance(x, dict) for x in v):
            if k == "bookmarks":
                out.append("\n# ── Bookmarks ── folder: \"Toolbar\", \"Menu\", \"Other\" + subfolders like \"Toolbar/Dev\"")
            for item in v:
                out.append(f"\n[[{_key(k)}]]")
                out.extend(f"{_key(a)} = {_val(b)}" for a, b in item.items())
        else:
            out.append(f"{_key(k)} = {_val(v)}")
    return "\n".join(out) + "\n"
