"""Colour palettes: follow swayforge, a bundled theme, or one you saved in the universal file."""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import ascii as asc
from . import paths

COLOR_KEYS = ["crust", "mantle", "base", "surface", "surface2", "overlay", "text",
              "subtext", "accent", "accent2", "red", "green", "yellow", "orange",
              "blue", "magenta", "cyan"]
COLOR_LABELS = {
    "crust": "Deepest background", "mantle": "Toolbars", "base": "Background",
    "surface": "Fields / tabs", "surface2": "Borders", "overlay": "Muted",
    "text": "Text", "subtext": "Muted text", "accent": "Accent", "accent2": "Accent 2",
    "red": "Red", "green": "Green", "yellow": "Yellow", "orange": "Orange",
    "blue": "Blue", "magenta": "Magenta", "cyan": "Cyan",
}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
DATA = Path(__file__).parent / "data/themes"
SYSTEM_ID = "system"

# swayforge bar layout → browser layout that matches it
LAYOUT_FROM_SWAY = {"win98": "win98", "win7": "glass", "wired": "wired", "minimal": "minimal",
                    "sidebar": "compact", "modern": "classic", "solid": "classic",
                    "cathedral": "cathedral", "glass": "glass", "winxp": "luna", "dread": "dread",
                    "win11": "modern", "touch": "modern"}


@dataclass
class Palette:
    id: str
    label: str
    dark: bool
    colors: dict[str, str]
    style: dict = field(default_factory=dict)     # radius, font, font_size, ascii, layout
    source: str = "bundled"                       # bundled | yours | swayforge
    art_lines: list[str] | None = None


def _bundled() -> dict[str, Palette]:
    out = {}
    for f in sorted(DATA.glob("*.toml")):
        d = tomllib.loads(f.read_text())
        out[f.stem] = Palette(f.stem, d.get("label", f.stem), bool(d.get("dark", True)),
                              d["colors"], d.get("style", {}))
    return out


def _yours(cfg: dict) -> dict[str, Palette]:
    out = {}
    for tid, d in cfg.get("themes", {}).items():
        cols = d.get("colors", {})
        if all(k in cols and HEX.match(cols[k]) for k in COLOR_KEYS):
            out[tid] = Palette(tid, d.get("label", tid), bool(d.get("dark", True)), cols,
                               d.get("style", {}), "yours")
    return out


def swayforge_palette() -> Palette | None:
    try:
        d = json.loads(paths.SWAYFORGE_PALETTE.read_text())
        cols = d["colors"]
        if not all(k in cols for k in COLOR_KEYS):
            return None
    except (OSError, ValueError, KeyError):
        return None
    style = {"font": d.get("font", ""), "font_size": d.get("font_size", 13),
             "radius": d.get("radius", 4), "ascii": d.get("art", ""),
             "layout": LAYOUT_FROM_SWAY.get(d.get("layout", ""), "classic"), "motion": d.get("motion", "")}
    return Palette(SYSTEM_ID, f"System ({d.get('label', d.get('theme', 'swayforge'))})",
                   bool(d.get("dark", True)), cols, style, "swayforge", d.get("art_lines"))


def all_palettes(cfg: dict) -> dict[str, Palette]:
    out = {}
    sp = swayforge_palette()
    if sp:
        out[SYSTEM_ID] = sp
    out.update(_bundled())
    out.update(_yours(cfg))
    return out


def active(cfg: dict) -> Palette:
    g = cfg["general"]
    pals = all_palettes(cfg)
    if g.get("follow_system") and SYSTEM_ID in pals:
        p = pals[SYSTEM_ID]
    else:
        name = {"onyx": "noir"}.get(g.get("theme", ""), g.get("theme", ""))   # Onyx merged into Noir
        p = pals.get(name) or pals.get("type-o") or next(iter(pals.values()))
    p = Palette(p.id, p.label, p.dark, dict(p.colors), dict(p.style), p.source, p.art_lines)
    acc = g.get("accent", "")
    if acc in p.colors:
        p.colors["accent"] = p.colors[acc]
    elif HEX.match(acc or ""):
        p.colors["accent"] = acc
    return p


def resolved(cfg: dict) -> dict:
    """Everything the generators need, after theme style + your overrides."""
    g = cfg["general"]
    p = active(cfg)
    radius = g["radius"] if g.get("radius", -1) >= 0 else int(p.style.get("radius", 6))
    font = g.get("font") or p.style.get("font") or "JetBrainsMono Nerd Font"
    size = int(g.get("font_size") or p.style.get("font_size") or 13)
    art_name = g.get("art", "auto")
    if art_name in ("", "auto"):
        art_name = p.style.get("ascii") or "forge"
    lines = p.art_lines if (p.art_lines and g.get("art", "auto") in ("", "auto")) else asc.art(art_name)
    return {"palette": p, "c": p.colors, "radius": radius, "font": font, "font_size": size,
            "art_name": art_name, "art": lines}


def save_theme(cfg: dict, tid: str, label: str, colors: dict, dark: bool = True) -> str:
    tid = re.sub(r"[^a-z0-9-]+", "-", tid.lower()).strip("-") or "mine"
    cfg.setdefault("themes", {})[tid] = {"label": label or tid, "dark": dark,
                                         "colors": {k: colors[k] for k in COLOR_KEYS}}
    cfg["general"]["theme"] = tid
    cfg["general"]["follow_system"] = False
    return tid


# ── colour helpers ───────────────────────────────────────────────────
def rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    ra, ga, ba = rgb(a)
    rb, gb, bb = rgb(b)
    return "#%02x%02x%02x" % (round(ra + (rb - ra) * t), round(ga + (gb - ga) * t), round(ba + (bb - ba) * t))


def rgba(c: str, a: float) -> str:
    r, g, b = rgb(c)
    return f"rgba({r}, {g}, {b}, {a})"


def luminance(c: str) -> float:
    def ch(v: int) -> float:
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(c)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def on(c: str, dark: str = "#000000", light: str = "#ffffff") -> str:
    """Readable text colour on top of c."""
    return dark if luminance(c) > 0.35 else light
