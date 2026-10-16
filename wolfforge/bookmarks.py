"""Bookmarks between the universal file and the browser.

Read:  places.sqlite (copied first, so it works while the browser is open).
Write: a bookmarks.html that LibreWolf imports once at its next start
       (browser.places.importBookmarksHTML) – the official, safe way.
"""
from __future__ import annotations

import html
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

ROOTS = {"toolbar_____": "Toolbar", "menu________": "Menu", "unfiled_____": "Other",
         "mobile______": "Mobile"}


def read_places(profile: Path) -> list[dict]:
    db = profile / "places.sqlite"
    if not db.exists():
        return []
    with tempfile.TemporaryDirectory() as tmp:
        for suffix in ("", "-wal"):
            src = Path(str(db) + suffix)
            if src.exists():
                shutil.copy2(src, Path(tmp) / ("places.sqlite" + suffix))
        con = sqlite3.connect(f"file:{tmp}/places.sqlite?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT b.id, b.type, b.parent, b.position, b.title, b.guid, p.url "
                "FROM moz_bookmarks b LEFT JOIN moz_places p ON p.id = b.fk "
                "ORDER BY b.parent, b.position").fetchall()
        finally:
            con.close()
    folders: dict[int, tuple[int, str, str]] = {}      # id → (parent, title, guid)
    for bid, typ, parent, _pos, title, guid, _url in rows:
        if typ == 2:
            folders[bid] = (parent, title or "", guid)

    def path_of(fid: int) -> str | None:
        parts = []
        while fid in folders:
            parent, title, guid = folders[fid]
            if guid in ROOTS:
                parts.append(ROOTS[guid])
                return "/".join(reversed(parts))
            if guid == "root________":
                return None
            parts.append(title.replace("/", "∕"))
            fid = parent
        return None

    out = []
    for _bid, typ, parent, _pos, title, _guid, url in rows:
        if typ != 1 or not url or url.startswith("place:"):
            continue
        folder = path_of(parent)
        if folder is None or folder.startswith("Mobile"):
            continue
        out.append({"title": title or url, "url": url, "folder": folder})
    return out


def merge(existing: list[dict], new: list[dict]) -> tuple[list[dict], int]:
    seen = {(b["url"], b.get("folder", "")) for b in existing}
    added = 0
    out = list(existing)
    for b in new:
        k = (b["url"], b.get("folder", ""))
        if k not in seen:
            seen.add(k)
            out.append(b)
            added += 1
    return out, added


def to_html(bookmarks: list[dict]) -> str:
    """Netscape bookmark file. Folder 'Toolbar/…' → bookmarks toolbar, 'Other/…' → Other bookmarks."""
    now = int(time.time())
    tree: dict = {"_items": [], "_sub": {}}
    for b in bookmarks:
        node = tree
        for part in [p for p in (b.get("folder") or "Menu").split("/") if p]:
            node = node["_sub"].setdefault(part, {"_items": [], "_sub": {}})
        node["_items"].append(b)

    def render(node: dict, depth: int) -> list[str]:
        pad = "    " * depth
        lines = []
        for name, sub in node["_sub"].items():
            attrs = f' ADD_DATE="{now}" LAST_MODIFIED="{now}"'
            if depth == 1 and name == "Toolbar":
                attrs += ' PERSONAL_TOOLBAR_FOLDER="true"'
            if depth == 1 and name == "Other":
                attrs += ' UNFILED_BOOKMARKS_FOLDER="true"'
            title = {"Toolbar": "Bookmarks Toolbar", "Other": "Other Bookmarks"}.get(name, name) \
                if depth == 1 else name
            lines.append(f"{pad}<DT><H3{attrs}>{html.escape(title)}</H3>")
            lines.append(f"{pad}<DL><p>")
            lines += render(sub, depth + 1)
            lines.append(f"{pad}</DL><p>")
        for b in node["_items"]:
            lines.append(f'{pad}<DT><A HREF="{html.escape(b["url"], quote=True)}" ADD_DATE="{now}">'
                         f'{html.escape(b.get("title") or b["url"])}</A>')
        return lines

    # "Menu" items sit directly in the top level (= bookmarks menu)
    top = tree["_sub"].pop("Menu", {"_items": [], "_sub": {}})
    root = {"_items": top["_items"] + tree["_items"], "_sub": {**top["_sub"], **tree["_sub"]}}
    body = render(root, 1)
    return ("<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
            "<!-- wolfforge export. This is an automatically generated file. -->\n"
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n'
            "<TITLE>Bookmarks</TITLE>\n<H1>Bookmarks Menu</H1>\n\n<DL><p>\n"
            + "\n".join(body) + "\n</DL>\n")


def groups_for_startpage(bookmarks: list[dict], limit: int = 72) -> list[tuple[str, list[dict]]]:
    out: dict[str, list[dict]] = {}
    n = 0
    for b in bookmarks:
        if n >= limit:
            break
        folder = b.get("folder") or "Menu"
        parts = folder.split("/")
        name = parts[-1] if len(parts) > 1 else {"Toolbar": "Toolbar", "Menu": "Bookmarks",
                                                  "Other": "Other"}.get(parts[0], parts[0])
        out.setdefault(name, []).append(dict(b))
        n += 1
    k = 1
    for _name, links in out.items():
        for b in links:
            if k <= 9:
                b["n"] = k
                k += 1
    return list(out.items())
