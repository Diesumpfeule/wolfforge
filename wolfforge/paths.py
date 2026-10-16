"""Where things live: wolfforge's own files and the LibreWolf / Firefox profiles."""
from __future__ import annotations

import configparser
import os
from pathlib import Path

HOME = Path.home()
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share")

CONFIG_DIR = XDG_CONFIG / "wolfforge"
UNIVERSAL = CONFIG_DIR / "wolfforge.toml"        # THE file: themes, layout, bar, sites, privacy, bookmarks
STATE_DIR = XDG_DATA / "wolfforge"
BACKUP_DIR = STATE_DIR / "backups"
SWAYFORGE_PALETTE = XDG_DATA / "swayforge/generated/palette.json"
SWAYFORGE_ASCII = XDG_CONFIG / "swayforge/ascii"

# LibreWolf keeps the legacy dir if it exists, otherwise the XDG one (vendor/app).
LIBREWOLF_ROOTS = [
    HOME / ".librewolf",
    XDG_CONFIG / "librewolf/librewolf",
    HOME / ".var/app/io.gitlab.librewolf-community/.librewolf",
]
FIREFOX_ROOTS = [
    HOME / ".mozilla/firefox",
    XDG_CONFIG / "mozilla/firefox",
    HOME / ".var/app/org.mozilla.firefox/.mozilla/firefox",
    HOME / "snap/firefox/common/.mozilla/firefox",
]


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, STATE_DIR, BACKUP_DIR, CONFIG_DIR / "ascii"):
        d.mkdir(parents=True, exist_ok=True)


def _profiles(root: Path) -> list[tuple[str, Path, bool]]:
    """(name, path, is_default) from a profiles.ini."""
    ini = root / "profiles.ini"
    if not ini.is_file():
        return []
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read(ini)
    except configparser.Error:
        return []
    install_default = {cp[s].get("Default") for s in cp.sections() if s.startswith("Install")}
    out = []
    for s in cp.sections():
        if not s.startswith("Profile"):
            continue
        sec = cp[s]
        p = sec.get("Path", "")
        path = root / p if sec.get("IsRelative", "1") == "1" else Path(p)
        if path.is_dir():
            default = p in install_default or sec.get("Default") == "1"
            out.append((sec.get("Name", path.name), path, default))
    # an [Install…] default beats the old Default=1 flag
    if any(p[1].name in {Path(d).name for d in install_default if d} for p in out):
        out = [(n, p, p.name in {Path(d).name for d in install_default if d}) for n, p, _ in out]
    return out


def browser_profiles(roots: list[Path]) -> list[tuple[str, Path, bool]]:
    for r in roots:
        found = _profiles(r)
        if found:
            return found
    return []


def librewolf_root() -> Path | None:
    for r in LIBREWOLF_ROOTS:
        if (r / "profiles.ini").is_file():
            return r
    return None


def librewolf_profile(explicit: str = "") -> Path | None:
    if explicit:
        p = Path(os.path.expanduser(explicit))
        return p if p.is_dir() else None
    profs = browser_profiles(LIBREWOLF_ROOTS)
    for _n, p, d in profs:
        if d:
            return p
    return profs[0][1] if profs else None


def overrides_file() -> Path:
    """librewolf.overrides.cfg next to the profile root LibreWolf actually uses."""
    root = librewolf_root()
    if root is None:
        root = next((r for r in LIBREWOLF_ROOTS if r.is_dir()), LIBREWOLF_ROOTS[1])
    if root == XDG_CONFIG / "librewolf/librewolf":   # XDG layout reads ~/.config/librewolf/…cfg
        return root.parent / "librewolf.overrides.cfg"
    return root / "librewolf.overrides.cfg"


def firefox_profile() -> Path | None:
    profs = browser_profiles(FIREFOX_ROOTS)
    best = [p for _n, p, d in profs if d] or [p for _n, p, _d in profs]
    # prefer the one with the most data
    best.sort(key=lambda p: (p / "places.sqlite").stat().st_size if (p / "places.sqlite").exists() else 0,
              reverse=True)
    return best[0] if best else None


def is_running(profile: Path | None) -> bool:
    """A live LibreWolf/Firefox holds a 'lock' symlink in the profile."""
    if profile is None:
        return False
    lock = profile / "lock"
    if not lock.is_symlink():
        return False
    target = os.readlink(lock)                     # e.g. "127.0.1.1:+12345"
    pid = target.rsplit("+", 1)[-1]
    return not pid.isdigit() or Path(f"/proc/{pid}").exists()
