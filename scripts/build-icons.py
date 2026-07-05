"""Build PNG + ICO window icons from assets/satori.svg for Tkinter apps.

Uses npx @resvg/resvg-js-cli (Node) when available, then Pillow for square crop + ICO.
Run after updating assets/satori.svg:

  python scripts/build-icons.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SVG = ASSETS / "satori.svg"
PNG = ASSETS / "satori-icon.png"
ICO = ASSETS / "satori-icon.ico"
PNG_ALIAS = ASSETS / "copilot-icon.png"
ICO_ALIAS = ASSETS / "copilot-icon.ico"


def _render_svg_with_resvg(tmp_png: Path) -> bool:
    npx = shutil.which("npx")
    if not npx:
        return False
    cmd = [
        npx,
        "--yes",
        "@resvg/resvg-js-cli",
        str(SVG),
        str(tmp_png),
        "--fit-height",
        "512",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, OSError):
        return False
    return tmp_png.is_file()


def main() -> int:
    if not SVG.is_file():
        print(f"Missing {SVG}", file=sys.stderr)
        return 1

    try:
        from PIL import Image
    except ImportError:
        print("Install: pip install pillow", file=sys.stderr)
        return 1

    ASSETS.mkdir(parents=True, exist_ok=True)
    tmp = ASSETS / "_satori-render.png"
    if not _render_svg_with_resvg(tmp):
        print(
            "Could not render SVG (need Node/npx for @resvg/resvg-js-cli).",
            file=sys.stderr,
        )
        return 1

    img = Image.open(tmp).convert("RGBA")
    tmp.unlink(missing_ok=True)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - w) // 2, (side - h) // 2))
    out = square.resize((256, 256), Image.Resampling.LANCZOS)

    for path in (PNG, PNG_ALIAS):
        out.save(path, format="PNG")
    for path in (ICO, ICO_ALIAS):
        out.save(
            path,
            format="ICO",
            sizes=[(256, 256), (48, 48), (32, 32), (16, 16)],
        )

    # Header variant: light tint on transparent bg for dark UI
    header = square.resize((40, 40), Image.Resampling.LANCZOS).convert("RGBA")
    accent = (147, 197, 253)
    px = header.load()
    for y in range(header.height):
        for x in range(header.width):
            r, g, b, a = px[x, y]
            if a > 24 and (r + g + b) < 420:
                px[x, y] = (*accent, a)
    header.save(ASSETS / "satori-header.png", format="PNG")

    print(f"Wrote {PNG.name}, {ICO.name}, satori-header.png (+ copilot-icon aliases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
