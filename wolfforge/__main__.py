"""wolfforge command line. Without arguments: the app."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import bookmarks as bm
from . import config, firefox, generate, paths, themes


def _print_result(res: generate.Result, quiet: bool) -> int:
    for e in res.errors:
        print("✗", e, file=sys.stderr)
    if not quiet:
        for w in res.written:
            print("  wrote", w.replace(str(paths.HOME), "~"))
        for n in res.notes:
            print("·", n)
    return 1 if res.errors else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(epilog="Proof of concept, written by Claude (Anthropic). No warranty – use at your own risk.", prog="wolfforge", description="LibreWolf overhaul – theme, layout, toolbar, "
                                 "privacy and bookmarks from one file")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("app", help="open the app (default)")
    p.add_argument("--page", default="look")
    p = sub.add_parser("apply", help="write everything into LibreWolf")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("theme", help="switch theme")
    p.add_argument("name", nargs="?")
    p.add_argument("--list", action="store_true")
    p = sub.add_parser("layout", help="switch layout")
    p.add_argument("name", nargs="?", choices=list(generate.LAYOUTS))
    p = sub.add_parser("bookmarks", help="pull from / push to LibreWolf")
    p.add_argument("action", choices=["pull", "push", "list"])
    p = sub.add_parser("import-firefox", help="bookmarks + add-on list (+ passwords) from Firefox")
    p.add_argument("--passwords", action="store_true")
    p.add_argument("--replace-passwords", action="store_true")
    p = sub.add_parser("export", help="copy the universal file")
    p.add_argument("file")
    p = sub.add_parser("import", help="use another universal file")
    p.add_argument("file")
    sub.add_parser("restart", help="restart LibreWolf")
    sub.add_parser("status", help="what wolfforge sees")
    a = ap.parse_args(argv)

    if a.cmd in (None, "app"):
        from .tui.app import run
        run(getattr(a, "page", "look"))
        return 0

    cfg = config.load()
    if a.cmd == "apply":
        res = generate.apply(cfg, dry=a.dry_run)
        if not a.dry_run:
            config.save(cfg)
        return _print_result(res, a.quiet)
    if a.cmd == "theme":
        pals = themes.all_palettes(cfg)
        if a.list or not a.name:
            for pid, pal in pals.items():
                print(f"{'*' if themes.active(cfg).id == pid else ' '} {pid:<20} {pal.label}")
            return 0
        if a.name not in pals:
            print(f"Unknown theme: {a.name}", file=sys.stderr)
            return 1
        cfg["general"]["follow_system"] = a.name == themes.SYSTEM_ID
        if a.name != themes.SYSTEM_ID:
            cfg["general"]["theme"] = a.name
        config.save(cfg)
        return _print_result(generate.apply(cfg), True)
    if a.cmd == "layout":
        if not a.name:
            for k, v in generate.LAYOUTS.items():
                print(f"{'*' if cfg['general']['layout'] == k else ' '} {k:<9} {v}")
            return 0
        cfg["general"]["layout"] = a.name
        config.save(cfg)
        return _print_result(generate.apply(cfg), True)
    if a.cmd == "bookmarks":
        prof = paths.librewolf_profile(cfg["general"]["profile"])
        if a.action == "list":
            for b in cfg["bookmarks"]:
                print(f"{b.get('folder', ''):<24} {b['title'][:40]:<42} {b['url']}")
            return 0
        if not prof:
            print("No LibreWolf profile found.", file=sys.stderr)
            return 1
        if a.action == "pull":
            cfg["bookmarks"], n = bm.merge(cfg["bookmarks"], bm.read_places(prof))
            config.save(cfg)
            print(f"{n} new bookmarks pulled ({len(cfg['bookmarks'])} total).")
            return 0
        res = generate.Result()
        ok = generate.push_to_browser(cfg, prof, res)
        if ok:
            config.save(cfg)
        return _print_result(res, False)
    if a.cmd == "import-firefox":
        ff = paths.firefox_profile()
        if not ff:
            print("No Firefox profile found.", file=sys.stderr)
            return 1
        cfg["bookmarks"], n = bm.merge(cfg["bookmarks"], bm.read_places(ff))
        known = {e["id"] for e in cfg["extensions"]}
        add = [e for e in firefox.extensions(ff) if e["id"] not in known]
        cfg["extensions"] += add
        config.save(cfg)
        print(f"{n} bookmarks and {len(add)} add-ons taken over from {ff}.")
        if add:
            print("  Install them in LibreWolf: wolfforge → Import from Firefox → Open add-on pages")
        if a.passwords or a.replace_passwords:
            lw = paths.librewolf_profile(cfg["general"]["profile"])
            print(firefox.copy_passwords(ff, lw, a.replace_passwords) if lw else "No LibreWolf profile.")
        print("Next: wolfforge bookmarks push (with LibreWolf closed).")
        return 0
    if a.cmd == "export":
        config.save(cfg)
        dst = Path(a.file).expanduser()
        shutil.copy2(paths.UNIVERSAL, dst)
        print(f"Exported: {dst}")
        return 0
    if a.cmd == "import":
        src = Path(a.file).expanduser()
        new = config.load(src)
        config.save(new)
        print("Imported. Applying …")
        return _print_result(generate.apply(new), False)
    if a.cmd == "restart":
        prof = paths.librewolf_profile(cfg["general"]["profile"])
        subprocess.run(["pkill", "-TERM", "-x", "librewolf"], check=False)
        for _ in range(40):
            if not paths.is_running(prof):
                break
            time.sleep(0.25)
        exe = shutil.which("librewolf")
        if exe:
            subprocess.Popen([exe], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0
    if a.cmd == "status":
        prof = paths.librewolf_profile(cfg["general"]["profile"])
        r = themes.resolved(cfg)
        print(f"universal file  {paths.UNIVERSAL}")
        print(f"LibreWolf       {prof or 'no profile found'}{'  (running)' if paths.is_running(prof) else ''}")
        print(f"overrides       {paths.overrides_file()}")
        print(f"Firefox         {paths.firefox_profile() or 'not found'}")
        print(f"theme           {r['palette'].label}  ({r['palette'].source})")
        print(f"layout          {cfg['general']['layout']}  · tabs {cfg['toolbar']['tabs']}")
        print(f"privacy         {cfg['privacy']['level']}  · sync {'on' if cfg['privacy']['sync'] else 'off'}")
        print(f"bookmarks       {len(cfg['bookmarks'])}  · add-ons listed {len(cfg['extensions'])}")
        return 0
    return 0


if __name__ == "__main__":
    from .crash import guard
    sys.exit(guard("wolfforge", main))
