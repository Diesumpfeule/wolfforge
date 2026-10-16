"""Generates docs/img/banner.svg – the README header (font-independent: pure rects and lines)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wolfforge.ascii import SHADE, shadow  # noqa: E402

CW, CH = 12, 24            # one character cell → "██" = a 24×24 pixel
PAD_X, PAD_Y = 48, 40
STOPS = ["#6c8fd8", "#3fbf5f", "#c96a3a", "#e05a4f"]   # Green Night → Type O → Rust → Wired


def build(word: str = "wolfforge", tagline: str = "librewolf · themes · layouts · start page · privacy · bookmarks") -> str:
    lines = shadow(word)
    cols = max(map(len, lines))
    w = cols * CW + 2 * PAD_X
    h = len(lines) * CH + 2 * PAD_Y + 46
    rects, paths = [], []
    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            x, y = PAD_X + c * CW, PAD_Y + r * CH
            if ch == "█":
                rects.append(f'<rect x="{x}" y="{y}" width="{CW + .4}" height="{CH + .4}"/>')
            elif ch in SHADE:
                cx, cy = x + CW / 2, y + CH / 2
                up = ch in "║╚╝╠╣╩╬"
                down = ch in "║╔╗╠╣╦╬"
                left = ch in "═╗╝╣╦╩╬"
                right = ch in "═╔╚╠╦╩╬"
                for o in (-2.5, 2.5):
                    if left or right:
                        x1 = x if left else cx + (o if up else -o)
                        x2 = x + CW if right else cx + (-o if up else o)
                        if left and not right:
                            x2 = cx + (o if down else -o) if (up or down) else x + CW / 2
                        if right and not left:
                            x1 = cx + (o if down else -o) if (up or down) else x + CW / 2
                        paths.append(f"M{x1:.1f} {cy + o:.1f}H{x2:.1f}")
                    if up or down:
                        y1 = y if up else cy + (o if left else -o)
                        y2 = y + CH if down else cy + (-o if left else o)
                        if up and not down:
                            y2 = cy + (o if right else -o) if (left or right) else cy
                        if down and not up:
                            y1 = cy + (o if right else -o) if (left or right) else cy
                        paths.append(f"M{cx + o:.1f} {y1:.1f}V{y2:.1f}")
    stops = "".join(f'<stop offset="{i / (len(STOPS) - 1):.2f}" stop-color="{s}"/>' for i, s in enumerate(STOPS))
    ty = PAD_Y + len(lines) * CH + 34
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <linearGradient id="g" gradientUnits="userSpaceOnUse" x1="{PAD_X}" x2="{w - PAD_X}" y1="0" y2="0">{stops}</linearGradient>
  <linearGradient id="gs" gradientUnits="userSpaceOnUse" x1="{PAD_X}" x2="{w - PAD_X}" y1="0" y2="0">{stops.replace('stop-color', 'stop-opacity="0.45" stop-color')}</linearGradient>
  <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#ffffff" opacity="0.025"/></pattern>
</defs>
<rect width="{w}" height="{h}" rx="10" fill="#0a0c0a"/>
<rect width="{w}" height="{h}" rx="10" fill="url(#scan)"/>
<path d="{"".join(paths)}" stroke="url(#gs)" stroke-width="1.6" fill="none"/>
<g fill="url(#g)">{"".join(rects)}</g>
<text x="{PAD_X}" y="{ty}" font-family="ui-monospace, 'JetBrains Mono', 'DejaVu Sans Mono', Menlo, Consolas, monospace"
      font-size="17" fill="#8fa88f" letter-spacing="1">&gt; {tagline}<tspan fill="#3fbf5f">█<animate attributeName="opacity"
      values="1;1;0;0" dur="1.1s" repeatCount="indefinite"/></tspan></text>
</svg>
'''


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "docs/img/banner.svg"
    out.write_text(build())
    print(out)
