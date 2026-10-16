"""ASCII art: block + 3D shadow font and motifs (shared with swayforge).

All art here is original to swayforge. Add your own by dropping a text file into
~/.config/wolfforge/ascii/<name>.txt (or swayforge's) – it shows up everywhere art can be chosen.
"""
from __future__ import annotations

from . import paths

# ── 5-row block font ─────────────────────────────────────────────────
FONT: dict[str, list[str]] = {
    "A": [" ██ ", "█  █", "████", "█  █", "█  █"],
    "B": ["███ ", "█  █", "███ ", "█  █", "███ "],
    "C": [" ███", "█   ", "█   ", "█   ", " ███"],
    "D": ["███ ", "█  █", "█  █", "█  █", "███ "],
    "E": ["███", "█  ", "██ ", "█  ", "███"],
    "F": ["███", "█  ", "██ ", "█  ", "█  "],
    "G": [" ███", "█   ", "█ ██", "█  █", " ██ "],
    "H": ["█  █", "█  █", "████", "█  █", "█  █"],
    "I": ["███", " █ ", " █ ", " █ ", "███"],
    "J": ["  █", "  █", "  █", "█ █", " █ "],
    "K": ["█  █", "█ █ ", "██  ", "█ █ ", "█  █"],
    "L": ["█  ", "█  ", "█  ", "█  ", "███"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "N": ["█  █", "██ █", "█ ██", "█  █", "█  █"],
    "O": [" ██ ", "█  █", "█  █", "█  █", " ██ "],
    "P": ["███ ", "█  █", "███ ", "█   ", "█   "],
    "Q": [" ██ ", "█  █", "█  █", "█ ██", " ███"],
    "R": ["███ ", "█  █", "███ ", "█ █ ", "█  █"],
    "S": [" ███", "█   ", " ██ ", "   █", "███ "],
    "T": ["███", " █ ", " █ ", " █ ", " █ "],
    "U": ["█  █", "█  █", "█  █", "█  █", " ██ "],
    "V": ["█   █", "█   █", " █ █ ", " █ █ ", "  █  "],
    "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    "X": ["█   █", " █ █ ", "  █  ", " █ █ ", "█   █"],
    "Y": ["█ █", "█ █", " █ ", " █ ", " █ "],
    "Z": ["████", "   █", " ██ ", "█   ", "████"],
    "0": [" ██ ", "█ ██", "██ █", "█  █", " ██ "],
    "1": [" █ ", "██ ", " █ ", " █ ", "███"],
    "2": ["███ ", "   █", " ██ ", "█   ", "████"],
    "3": ["███ ", "   █", " ██ ", "   █", "███ "],
    "4": ["█  █", "█  █", "████", "   █", "   █"],
    "5": ["████", "█   ", "███ ", "   █", "███ "],
    "6": [" ██ ", "█   ", "███ ", "█  █", " ██ "],
    "7": ["████", "   █", "  █ ", " █  ", " █  "],
    "8": [" ██ ", "█  █", " ██ ", "█  █", " ██ "],
    "9": [" ██ ", "█  █", " ███", "   █", " ██ "],
    " ": ["  ", "  ", "  ", "  ", "  "],
    "-": ["   ", "   ", "███", "   ", "   "],
    "_": ["   ", "   ", "   ", "   ", "███"],
    ".": [" ", " ", " ", " ", "█"],
    ":": [" ", "█", " ", "█", " "],
    "/": ["   █", "  █ ", " █  ", "█   ", "    "],
    "!": ["█", "█", "█", " ", "█"],
    "?": ["███ ", "   █", " ██ ", "    ", " █  "],
    ">": ["█  ", " █ ", "  █", " █ ", "█  "],
}


def banner(text: str, fill: str = "█") -> list[str]:
    rows = ["", "", "", "", ""]
    for ch in text.upper():
        glyph = FONT.get(ch, FONT["?"])
        for i in range(5):
            rows[i] += glyph[i].replace("█", fill) + " "
    return [r.rstrip() for r in rows]


# ── 3D shadow font (generated from the block font above) ────────────
# Every pixel becomes "██"; a double-line shadow (╔═╗ …) is traced down and to the right.
_BOX = {
    (0, 0, 1, 1): "═", (1, 1, 0, 0): "║", (0, 1, 1, 0): "╗", (0, 1, 0, 1): "╔",
    (1, 0, 1, 0): "╝", (1, 0, 0, 1): "╚", (1, 1, 1, 0): "╣", (1, 1, 0, 1): "╠",
    (0, 1, 1, 1): "╦", (1, 0, 1, 1): "╩", (1, 1, 1, 1): "╬", (0, 0, 1, 0): "═",
    (0, 0, 0, 1): "═", (1, 0, 0, 0): "║", (0, 1, 0, 0): "║", (0, 0, 0, 0): "═",
}
SHADE = set("░▒═║╔╗╚╝╠╣╦╩╬")


def shadow(text: str) -> list[str]:
    rows = ["", "", "", "", ""]
    for ch in text.upper():
        glyph = FONT.get(ch, FONT["?"])
        for i in range(5):
            rows[i] += glyph[i] + " "
    width = max(len(r) for r in rows)
    face = {(r, 2 * c + k) for r in range(5) for c, ch in enumerate(rows[r]) if ch == "█" for k in (0, 1)}
    sh = ({(r, c + 1) for r, c in face} | {(r + 1, c + 1) for r, c in face}
          | {(r + 1, c) for r, c in face}) - face

    def vlink(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return a in sh and b in sh and (a[0], a[1] - 1) in face

    out = [[" "] * (2 * width + 2) for _ in range(6)]
    for r, c in face:
        out[r][c] = "█"
    for r, c in sh:
        up, down = vlink((r - 1, c), (r, c)), vlink((r, c), (r + 1, c))
        left, right = (r, c - 1) in sh, (r, c + 1) in sh
        if not left and right and (r + 1, c) in face and (r, c - 1) in face:
            down = True                                         # inner corner ╔
        elif not up and not right and (r, c - 1) in face and (down or (r + 1, c) in face):
            left = down = True                                  # cap ╗ beside a block
        elif not left and right and not up and (r - 1, c) in face and not down:
            up = True                                           # bottom edge starts ╚
        out[r][c] = _BOX[(up, down, left, right)]
    return [l.rstrip() for l in ("".join(o) for o in out)]


def best_banner(text: str, max_cols: int = 80) -> list[str]:
    """3D shadow banner if it fits, otherwise the flat block font."""
    s = shadow(text)
    return s if max(map(len, s), default=0) <= max_cols else banner(text)


def layers(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split art into (face, shade) layers of equal size – for two-colour rendering."""
    face = ["".join(" " if ch in SHADE else ch for ch in l) for l in lines]
    shade = ["".join(ch if ch in SHADE else " " for ch in l) for l in lines]
    return face, shade


# ── Motifs (original swayforge art) ──────────────────────────────────
ART: dict[str, str] = {
    "forge": r"""
        \   |   /           ▄▄▄▄
      --  *  *  *  --      ████▓▒
        /   |   \          ▀██▀
                            ██
   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄     ██
  ▀███████████████████▓▓▒░  ██
      ▀▀▀███████████▀▀▀
           ▐███████▌
         ▄▄█████████▄▄
        ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
""",
    "crt": r"""
   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
  █▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█░
  █ ▓▒░                  ░▒▓ █▒
  █ ▒  C:/> boot forge       █▒
  █ ░  memory .... 640K ok   █▒
  █ ░  C:/> _                █▒
  █ ▓▒░                  ░▒▓ █▒
  █▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█▒
   ▀▀▀▀▀▀▀▀▀▀██████▀▀▀▀▀▀▀▀▀▀░
         ▄▄▄▄██████▄▄▄▄
        ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
""",
    "cyberdeck": r"""
   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
   █ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ █
   █ ▓ > ssh pi@deck       ▓ █
   █ ▓ [ link .... up ]    ▓ █
   █ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ █
   █▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█
  ▐▌▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▐▌
  ▐▌ ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀  ▐▌
  ▐▌  ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀   ▐▌
  ▐▌ ▀▀ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ ▀▀   ▐▌
  ▐█▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█▌
""",
    "gamepad": r"""
     ▄▄██████▄▄▄▄▄▄▄▄▄▄▄▄██████▄▄
   ▄██▀▀                      ▀▀██▄
  ██▀    ▄█▄                 O    ▀██
 ██    ▄▄███▄▄   ▄▄  ▄▄   O     O   ██
 ██     ▀███▀    ▀▀  ▀▀      O      ██
 ██▄      ▀     ▄██▄▄▄▄▄▄██▄       ▄██
  ▀██▄▄▄▄▄▄▄▄▄██▀▀        ▀▀██▄▄▄▄██▀
    ▀▀▀▀▀▀▀▀▀▀▀              ▀▀▀▀▀▀
""",
    "lantern": r"""
             ▄█▄
            ▄███▄
          ▄█▀▀▀▀▀█▄
          █ ░▒▓▒░ █
          █ ▒ ▲ ▒ █
          █ ▓ █ ▓ █
          █ ▒▀▀▀▒ █
          █ ░▒▓▒░ █
          ▀█▄▄▄▄▄█▀
            ▀▀▀▀▀
""",
    "anvil": r"""
      ____________________________
     /                            \__
    |    s w a y f o r g e         __|
     \_____________        _______/
                   |      |
                ___|      |___
               /______________\
""",
    "rose": r"""
            _,--._
          ,'  _   `.
         /  ,' `.   \
        |  (  @  )   |
         \  `._,'   /
          `-.____,-'
         .    ||    .
          \   ||   /
           `-.||.-'
              ||
              ||
              ||
""",
    "moon": r"""
                    .-''''-.
       *          .'  .-.   '.        *
                 /   (   )    \
    ----===**    |    '-'     |
                  \    .     /
        *          '-.____.-'
   /\       /\     /\        /\
  /  \/\   /  \   /  \  /\  /  \
 /      \_/    \_/    \/  \/    \
""",
    "bat": r"""
 ▄▄                                ▄▄
 ███▄▄          ▄    ▄          ▄▄███
  ▀█████▄▄     ▐█▄▄▄▄█▌     ▄▄█████▀
    ▀███████▄▄ ▐█░▀▀░█▌ ▄▄███████▀
      ▀████████▓█▄▄▄▄█▓████████▀
        ▀▀█████▀▓████▓▀█████▀▀
           ▀▀    ▀▀▀▀    ▀▀
""",
    "terminal": r"""
   .--------------------------.
   | .----------------------. |
   | | C:\> boot            | |
   | | memory ........ ok   | |
   | | video ......... ok   | |
   | | C:\> _               | |
   | '----------------------' |
   '----------.____.----------'
          ____|____|____
         [______________]
""",
    "wired": r"""
     o-------o            o
     |\     / \          /|
     | \   /   o--------o |
     |  \ /    |        | |
     o---@-----+--o     o-o
        / \    |   \   /
       o   o---o----o-o
   [ node 07 :: connected ]
   [ signal  :: ||||||||-- ]
""",
    "skull": r"""
        .--------.
       /  _    _  \
      |  (o)  (o)  |
      |      ^     |
       \   '----' /
        '-.____.-'
         |_|__|_|
""",
}


def user_art() -> dict[str, str]:
    out = {}
    for d in (paths.SWAYFORGE_ASCII, paths.CONFIG_DIR / "ascii"):   # yours from swayforge too
        if d.is_dir():
            for f in sorted(d.glob("*.txt")):
                out[f.stem] = "\n" + f.read_text().rstrip("\n") + "\n"
    return out


def all_art() -> dict[str, str]:
    return ART | user_art()


def art(name: str) -> list[str]:
    a = all_art().get(name) or ART["forge"]
    lines = a.strip("\n").split("\n")
    pad = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    return [l[pad:].rstrip() for l in lines]
