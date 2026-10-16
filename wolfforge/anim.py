"""Animated ASCII art – same effect as swayforge (shared code, kept in sync).

Two layers on top of any motif, so your own art animates too:
- a band of light sweeps diagonally across it every few seconds ("glint"),
- sparks and stars (* + . ' `) twinkle on their own.
Intro: the motif ignites out of sparks (used by the terminal greeting and the installer).
"""
from __future__ import annotations


from .ascii import SHADE

SPARKS = set("*+.'`")
PERIOD = 6.0          # seconds between two glints
SWEEP = 1.4           # how long one glint takes to cross
BAND = 5.0            # glint width in columns


def _hash(*v: int) -> float:
    h = 2166136261
    for x in v:
        h = ((h ^ (x & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def cells(lines: list[str], t: float, intro: float | None = None):
    """Yield (row, col, char, kind) – kind: face | shade | glint | hot | off.

    intro = seconds since the ignite started (None = no intro, fully lit)."""
    width = max(map(len, lines), default=1)
    diag = width + len(lines) * 2 + BAND * 2
    phase = (t % PERIOD) / SWEEP
    pos = -BAND + phase * diag if phase <= 1 else -1e9
    slot = int(t * 4)                                     # twinkle changes 4× a second
    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            if ch == " ":
                yield r, c, ch, "off"
                continue
            if intro is not None:
                k = _hash(r, c, 7)
                heat = intro / 0.8
                if heat < k:
                    yield r, c, " ", "off"
                    continue
                if heat < k + 0.22:
                    yield r, c, "*+'.`"[int(_hash(r, c, int(intro * 20)) * 5)], "hot"
                    continue
            lone = (c == 0 or line[c - 1] == " ") and (c + 1 >= len(line) or line[c + 1] == " ")
            if ch in SPARKS and lone and _hash(r, c, slot) < 0.35:      # only free-standing sparks
                yield r, c, ".+*'"[int(_hash(c, r, slot) * 4)], "hot"
                continue
            d = (c + r * 2) - pos
            if 0 <= d < BAND:
                yield r, c, ch, "glint"
            else:
                yield r, c, ch, "shade" if ch in SHADE else "face"


# ── Textual / Rich ───────────────────────────────────────────────────
def rich_frame(lines: list[str], t: float, styles: dict[str, str], intro: float | None = None):
    from rich.text import Text
    out = Text(no_wrap=True)
    row = 0
    for r, _c, ch, kind in cells(lines, t, intro):
        while row < r:
            out.append("\n")
            row += 1
        out.append(ch, style=styles.get(kind, ""))
    return out
