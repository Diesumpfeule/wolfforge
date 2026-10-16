"""Preferences: look prefs go into the profile's user.js, privacy into librewolf.overrides.cfg.

Both files may contain your own lines – wolfforge only replaces the block between its markers.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, paths

BEGIN = "// ── wolfforge begin (managed – edit in the app or wolfforge.toml) ──"
END = "// ── wolfforge end ──"


def _js(v) -> str:
    return json.dumps(v)


def toolbar_state(cfg: dict) -> str:
    """browser.uiCustomization.state – the toolbar layout Firefox loads at startup."""
    nav, springs = [], 0
    for key in cfg["toolbar"]["buttons"]:
        wid = config.TOOLBAR_BUTTONS[key][0]
        if wid == "spring":
            springs += 1
            wid = f"customizableui-special-spring{springs}"
        nav.append(wid)
    tabs = ["tabbrowser-tabs", "new-tab-button", "alltabs-button"]
    if cfg["toolbar"]["tabs"] == "vertical":
        tabs = []
    state = {
        "placements": {
            "widget-overflow-fixed-list": [],
            "unified-extensions-area": [],
            "nav-bar": nav,
            "toolbar-menubar": ["menubar-items"],
            "TabsToolbar": tabs,
            "vertical-tabs": ["tabbrowser-tabs"] if cfg["toolbar"]["tabs"] == "vertical" else [],
            "PersonalToolbar": ["personal-bookmarks"],
        },
        "seen": ["save-to-pocket-button", "developer-button", "screenshot-button", "firefox-view-button",
                 "sidebar-button", "reset-pbm-toolbar-button", "profiler-button"],
        "dirtyAreaCache": ["nav-bar", "TabsToolbar", "PersonalToolbar", "toolbar-menubar",
                           "unified-extensions-area", "vertical-tabs"],
        "currentVersion": 23,
        "newElementCount": springs + 1,
    }
    return json.dumps(state, separators=(",", ":"))


def look_prefs(cfg: dict, r: dict, start_url: str | None) -> dict:
    t, s, g = cfg["toolbar"], cfg["sites"], cfg["general"]
    dark = r["palette"].dark
    p = {
        "toolkit.legacyUserProfileCustomizations.stylesheets": True,
        "svg.context-properties.content.enabled": True,
        "browser.compactmode.show": True,
        "browser.uidensity": {"compact": 1, "normal": 0, "touch": 2}.get(g["density"], 1),
        "browser.tabs.inTitlebar": 0,                      # no min/max/close buttons on Sway
        "browser.toolbars.bookmarks.visibility": t["bookmarks_bar"],
        "browser.uiCustomization.state": toolbar_state(cfg),
        "sidebar.revamp": t["tabs"] == "vertical",
        "sidebar.verticalTabs": t["tabs"] == "vertical",
        "browser.theme.content-theme": 0 if dark else 1,
        "browser.theme.toolbar-theme": 0 if dark else 1,
        "layout.css.prefers-color-scheme.content-override": (0 if dark else 1) if s["dark_request"] else 2,
        "browser.newtabpage.activity-stream.showSponsored": False,
        "browser.newtabpage.activity-stream.showSponsoredTopSites": False,
        "browser.newtabpage.activity-stream.feeds.section.topstories": False,
        "browser.newtabpage.activity-stream.showWeather": False,
    }
    if start_url:
        p["browser.startup.homepage"] = start_url
    return p


def privacy_prefs(cfg: dict) -> dict:
    pv = cfg["privacy"]
    level = pv["level"]
    p: dict = {
        "identity.fxaccounts.enabled": bool(pv["sync"]),
        "signon.rememberSignons": bool(pv["remember_passwords"]),
        "media.eme.enabled": bool(pv["drm"]),
        "browser.eme.ui.enabled": bool(pv["drm"]),
    }
    keep = level == "comfort"
    clear = level == "fortress"
    if level in ("comfort", "fortress"):
        p.update({
            "privacy.sanitize.sanitizeOnShutdown": not keep,
            "privacy.clearOnShutdown.cookies": not keep,
            "privacy.clearOnShutdown.history": not keep,
            "privacy.clearOnShutdown.offlineApps": not keep,
            "privacy.clearOnShutdown_v2.cookiesAndStorage": not keep,
            "privacy.clearOnShutdown_v2.historyFormDataAndDownloads": not keep,
            "privacy.clearOnShutdown_v2.browsingHistoryAndDownloads": not keep,
        })
    if keep:
        p.update({
            "privacy.resistFingerprinting": False,          # RFP forces light mode, UTC and fixed sizes
            "privacy.fingerprintingProtection": True,       # Firefox's lighter protection instead
            "webgl.disabled": False,
            "browser.startup.page": 3 if pv["restore_session"] else 1,
        })
    if clear:
        p.update({
            "privacy.resistFingerprinting": True,
            "privacy.resistFingerprinting.letterboxing": True,
            "media.peerconnection.enabled": False,          # WebRTC off (no IP leaks, no video calls)
            "webgl.disabled": True,
            "network.http.referer.XOriginPolicy": 2,
            "network.http.referer.XOriginTrimmingPolicy": 2,
            "pdfjs.enableScripting": False,
            "dom.security.https_only_mode": True,
            "browser.startup.page": 1,
        })
    return p


def dark_request_possible(cfg: dict) -> bool:
    """With resist-fingerprinting on, sites always see 'light' – the dark request can't work."""
    return cfg["privacy"]["level"] == "comfort"


def _block(prefs: dict, fn: str) -> str:
    lines = [BEGIN]
    lines += [f'{fn}({_js(k)}, {_js(v)});' for k, v in prefs.items()]
    lines.append(END)
    return "\n".join(lines) + "\n"


def write_block(path: Path, prefs: dict, fn: str, dry: bool = False) -> str:
    """Replace our block in path (keep everything else). Returns the new content."""
    old = path.read_text() if path.exists() else ""
    if BEGIN in old and END in old:
        a = old.index(BEGIN)
        b = old.index(END) + len(END)
        rest = (old[:a] + old[b:]).strip("\n")
    else:
        rest = old.strip("\n")
    new = _block(prefs, fn) + ("\n" + rest + "\n" if rest else "")
    if not dry and new != old:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new)
    return new


def remove_block(path: Path) -> bool:
    if not path.exists():
        return False
    old = path.read_text()
    if BEGIN not in old:
        return False
    a, b = old.index(BEGIN), old.index(END) + len(END)
    path.write_text((old[:a] + old[b:]).lstrip("\n"))
    return True


def read_user_pref(profile: Path, name: str) -> str | None:
    """Current value from prefs.js (what the browser saved last)."""
    f = profile / "prefs.js"
    if not f.exists():
        return None
    key = f'user_pref({_js(name)}, '
    for line in f.read_text(errors="replace").splitlines():
        if line.startswith(key):
            return line[len(key):].rstrip(");").strip()
    return None


def overrides_path() -> Path:
    return paths.overrides_file()
