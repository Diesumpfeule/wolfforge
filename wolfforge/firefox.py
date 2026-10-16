"""Take your Firefox data over to LibreWolf.

- Bookmarks  → the universal file (then pushed to LibreWolf)
- Extensions → listed in the universal file; their add-on pages open in LibreWolf (one click each)
- Passwords  → logins.json + key4.db copied into the LibreWolf profile (never into the
               universal file – it would be readable by anyone who gets that file)

Easier if you use a Firefox account: switch on Sync (privacy page) and sign in in LibreWolf.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

from . import bookmarks as bm
from . import paths

SKIP_ADDONS = {"uBlock0@raymondhill.net"}          # LibreWolf ships uBlock Origin already


def extensions(profile: Path) -> list[dict]:
    f = profile / "extensions.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text())
    except ValueError:
        return []
    out = []
    for a in data.get("addons", []):
        if a.get("type") != "extension" or a.get("location") != "app-profile":
            continue
        if a.get("hidden") or a.get("id", "").endswith("@mozilla.org") or a.get("id") in SKIP_ADDONS:
            continue
        name = (a.get("defaultLocale") or {}).get("name") or a.get("id")
        out.append({"id": a["id"], "name": name})
    return out


def addon_url(ext: dict) -> str:
    return "https://addons.mozilla.org/firefox/search/?q=" + quote(ext["name"])


def open_addon_pages(exts: list[dict]) -> bool:
    exe = shutil.which("librewolf") or shutil.which("flatpak")
    if not exe or not exts:
        return False
    urls = [addon_url(e) for e in exts]
    cmd = ([exe] if exe.endswith("librewolf") else [exe, "run", "io.gitlab.librewolf-community"])
    subprocess.Popen(cmd + ["--new-tab", *urls], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def has_logins(profile: Path) -> int:
    f = profile / "logins.json"
    try:
        return len(json.loads(f.read_text()).get("logins", []))
    except (OSError, ValueError):
        return 0


def copy_passwords(ff: Path, lw: Path, replace: bool = False) -> str:
    n_ff, n_lw = has_logins(ff), has_logins(lw)
    if not n_ff:
        return "No saved passwords in the Firefox profile."
    if paths.is_running(lw):
        return "Close LibreWolf first – it must not be running while passwords are copied."
    if n_lw and not replace:
        return (f"LibreWolf already has {n_lw} saved passwords – not overwritten. "
                "Use 'replace' to swap them for Firefox's (yours get backed up).")
    bdir = paths.BACKUP_DIR / time.strftime("logins-%Y%m%d-%H%M%S")
    for name in ("logins.json", "key4.db", "logins-backup.json"):
        if (lw / name).exists():
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(lw / name, bdir / name)
    for name in ("logins.json", "key4.db"):
        shutil.copy2(ff / name, lw / name)
        (lw / name).chmod(0o600)
    (lw / "logins-backup.json").unlink(missing_ok=True)
    return (f"{n_ff} passwords copied. If Firefox had a primary password, LibreWolf asks for the "
            "same one.")


def summary(ff: Path) -> dict:
    return {"profile": str(ff), "bookmarks": len(bm.read_places(ff)),
            "extensions": extensions(ff), "passwords": has_logins(ff)}
