"""Crash handler: no wolfforge app dies silently (same reports folder as swayforge).

When something crashes, a report is written to ~/.local/share/swayforge/crashes/,
a desktop notification says what happened and where the report is, and – if the
app ran in a terminal – the window stays open with the error until you press Enter
(it closes by itself after 5 minutes). The settings app lists recent reports under
About & updates.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

APP = "wolfforge"
CRASH_DIR = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "swayforge" / "crashes"


def _versions() -> str:
    out = [f"python {platform.python_version()} · {platform.platform()}"]
    for mod in ("swayforge", "wolfforge", "textual", "rich"):
        m = sys.modules.get(mod)
        v = getattr(m, "__version__", "") if m else ""
        if not v and m:
            try:
                from importlib.metadata import version
                v = version(mod)
            except Exception:  # noqa: BLE001
                v = ""
        if m:
            out.append(f"{mod} {v or '?'}")
    return " · ".join(out)


def write_report(app: str, exc: BaseException | None, context: str = "") -> Path:
    CRASH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = CRASH_DIR / f"{stamp}-{app.replace(' ', '-')}.log"
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else "(no traceback)"
    path.write_text(
        f"{app} crashed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"command: {' '.join(sys.argv)}\n{_versions()}\n"
        + (f"context: {context}\n" if context else "") + "\n" + tb)
    # keep the folder small
    for old in sorted(CRASH_DIR.glob("*.log"))[:-30]:
        old.unlink(missing_ok=True)
    return path


def summary(exc: BaseException | None) -> str:
    if not exc:
        return "unknown error"
    msg = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {msg}"[:160]


def notify(title: str, body: str) -> None:
    try:
        subprocess.Popen(["notify-send", "-u", "critical", "-a", APP, title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def report(app: str, exc: BaseException | None, hold: bool = True) -> Path:
    """Write the report, tell the user, keep the terminal open if there is one."""
    path = write_report(app, exc)
    short = summary(exc)
    home = str(Path.home())
    notify(f"{app} crashed", f"{short}\nReport: {str(path).replace(home, '~')}")
    if hold and sys.stdin and sys.stdin.isatty() and sys.stdout and sys.stdout.isatty():
        try:
            sys.stdout.write("\033[0m\033[?25h\n")         # leave any half-drawn TUI behind
            print(f"✗ {app} crashed: {short}")
            print(f"  Full report: {path}")
            print("  Nothing was lost – settings are saved separately. Please send the report if it")
            print("  keeps happening.\n")
            subprocess.run(["sh", "-c", "stty sane 2>/dev/null; read -t 300 -rp 'Press Enter to close ' _"],
                           check=False)
        except (OSError, KeyboardInterrupt):
            pass
    return path


def run_app(app_name: str, app) -> object:
    """Run a Textual app; if it crashed, report it. Returns the app's result."""
    result = app.run()
    exc = getattr(app, "_exception", None)
    if exc is not None or (app.return_code not in (0, None)):
        report(app_name, exc or RuntimeError(f"exited with code {app.return_code}"))
    return result


def guard(app_name: str, fn, *args, **kwargs):
    """Run fn; any uncaught exception becomes a crash report instead of a silent exit."""
    try:
        return fn(*args, **kwargs)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:  # noqa: BLE001
        report(app_name, e)
        return 1


def recent(limit: int = 5) -> list[Path]:
    return sorted(CRASH_DIR.glob("*.log"), reverse=True)[:limit] if CRASH_DIR.is_dir() else []
