#!/usr/bin/env python3
"""Build wolfforge for Firefox on Android (an extension).

    python3 android/build.py          # refresh ext/data.json and write dist/wolfforge-android.xpi
    python3 android/build.py --check  # fail when ext/data.json is out of date (used by the tests)

Everything the extension knows about colours comes from the desktop wolfforge: the themes in
wolfforge/data/themes, the ASCII art, the banner font and the website styles in
wolfforge/templates/sites. The styles are rendered once with placeholders instead of colours
(«base», «accent» …); the extension fills in the chosen theme on the phone.
"""
from __future__ import annotations

import json
import sys
import tomllib
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import jinja2  # noqa: E402

from wolfforge import ascii as asc  # noqa: E402
from wolfforge import config, generate, prefs, themes  # noqa: E402

EXT = HERE / "ext"
XPI = HERE / "dist" / "wolfforge-android.xpi"


class Vars(dict):
    """c.base → «base»: a placeholder the extension replaces with the theme's colour."""
    def __getattr__(self, key: str) -> str:
        return f"«{key}»"

    __getitem__ = __getattr__


def mix(a: str, b: str, t: float) -> str:
    return f"color-mix(in srgb, {a} {round((1 - t) * 100)}%, {b})"


def rgba(c: str, a: float) -> str:
    return f"color-mix(in srgb, {c} {round(a * 100)}%, transparent)"


def site_css() -> dict:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(ROOT / "wolfforge/templates"),
                             trim_blocks=True, lstrip_blocks=True)
    ctx = {"c": Vars(), "on_accent": "«on_accent»", "mix": mix, "rgba": rgba}
    touches = {}
    for flag in ("scrollbars", "selection", "caret", "focus_ring"):
        touches[flag] = env.get_template("sites/global.css.j2").render(**ctx, s={flag: True}).strip()
    packs = {}
    for key, domains in generate.PACK_DOMAINS.items():
        packs[key] = {"name": generate.PACK_NAMES[key], "domains": domains,
                      "css": env.get_template(f"sites/{key}.css.j2").render(**ctx).strip()}
    rules = {}
    for mode in ("invert", "dim", "theme"):
        rules[mode] = env.get_template("sites/rule.css.j2").render(**ctx, r={"mode": mode}).strip()
    return {"touches": touches, "packs": packs, "rules": rules}


# about:config switches that exist in Firefox for Android and make sense there
PRIVACY_KEEP = ("privacy.resistFingerprinting", "privacy.fingerprintingProtection", "media.peerconnection.enabled",
                "webgl.disabled", "network.http.referer.", "pdfjs.enableScripting", "dom.security.https_only_mode",
                "media.eme.enabled")
PRIVACY_WHY = {
    "privacy.resistFingerprinting": "Sites see a generic device (also forces light mode and UTC time)",
    "privacy.resistFingerprinting.letterboxing": "Page size is rounded so the screen size leaks less",
    "privacy.fingerprintingProtection": "Firefox's lighter fingerprinting protection",
    "media.peerconnection.enabled": "WebRTC – off stops IP leaks, but also video calls in the browser",
    "webgl.disabled": "WebGL – off closes a fingerprinting door, some 3D pages stop working",
    "network.http.referer.XOriginPolicy": "Tell other sites where you came from: 2 = only the same host",
    "network.http.referer.XOriginTrimmingPolicy": "How much of the address other sites get: 2 = only the host",
    "pdfjs.enableScripting": "Scripts inside PDF files",
    "dom.security.https_only_mode": "Only open encrypted (https) pages",
    "media.eme.enabled": "DRM video (Netflix, Spotify web player …)",
}


def privacy() -> dict:
    out = {}
    for level in ("comfort", "fortress"):
        cfg = {"privacy": {"level": level, "sync": False, "remember_passwords": False, "drm": level == "comfort",
                           "restore_session": False}}
        rows = []
        for k, v in prefs.privacy_prefs(cfg).items():
            if k.startswith(PRIVACY_KEEP):
                rows.append({"pref": k, "value": v, "why": PRIVACY_WHY.get(k, "")})
        out[level] = rows
    return out


def data() -> dict:
    pal = []
    for f in sorted(themes.DATA.glob("*.toml")):
        t = tomllib.loads(f.read_text())
        colors = {k: t["colors"][k] for k in themes.COLOR_KEYS}
        pal.append({"id": f.stem, "label": t.get("label", f.stem), "dark": bool(t.get("dark", True)), "colors": colors})
    art = {f.stem: f.read_text().rstrip("\n").split("\n") for f in sorted(asc.ART_DIR.glob("*.txt"))}
    atlas = json.loads((asc.ART_DIR / "banner.json").read_text())
    return {
        "themes": pal,
        "keys": list(themes.COLOR_KEYS),
        "art": art,
        "shade": "".join(sorted(asc.SHADE)),
        "banner": {rows: atlas[rows] for rows in ("4", "5", "6") if rows in atlas},
        "css": site_css(),
        "search": {k: {"name": v[0], "url": v[1], "param": v[2]} for k, v in config.SEARCH.items()},
        "privacy": privacy(),
    }


def main() -> int:
    text = json.dumps(data(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    target = EXT / "data.json"
    if "--check" in sys.argv:
        if not target.exists() or target.read_text() != text:
            print("android/ext/data.json is out of date – run: python3 android/build.py", file=sys.stderr)
            return 1
        return 0
    target.write_text(text)
    XPI.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(XPI, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(EXT.rglob("*")):
            if f.is_file():
                info = zipfile.ZipInfo(f.relative_to(EXT).as_posix(), (2024, 1, 1, 0, 0, 0))   # same bytes every build
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, f.read_bytes())
    print(f"{target.relative_to(ROOT)} · {XPI.relative_to(ROOT)} ({XPI.stat().st_size // 1024} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
