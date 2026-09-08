"""Render assets/icon from the shared mark geometry: run after changing checktokens.mark."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from checktokens import mark  # noqa: E402

SUPERSAMPLE = 8
ICO_SIZES = (16, 20, 24, 32, 48, 64, 128, 256)
ICONSET = (16, 32, 128, 256, 512)


def ramp(width, height, top, bottom):
    """A vertical top-to-bottom colour ramp, stretched from a one-pixel column."""
    from PIL import Image

    column = Image.new("RGBA", (1, max(2, height)))
    for y in range(column.height):
        share = y / (column.height - 1)
        column.putpixel(
            (0, y), tuple(round(a + (b - a) * share) for a, b in zip(top, bottom, strict=True))
        )
    return column.resize((width, height), Image.Resampling.BILINEAR)


def render(pixels, points=None):
    """Draw one square mark; Pillow has no antialiased shapes, so draw big and shrink."""
    from PIL import Image, ImageDraw

    points = pixels if points is None else points
    box = pixels * SUPERSAMPLE
    unit = box / 100
    mask = Image.new("L", (box, box), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, box - 1, box - 1), radius=mark.CORNER * unit, fill=255
    )
    icon = ramp(box, box, (*mark.TOP, 255), (*mark.BOTTOM, 255))
    gloss = (255, 255, 255, round(255 * mark.GLOSS_ALPHA))
    icon.alpha_composite(ramp(box, round(mark.GLOSS_HEIGHT * unit), gloss, (255, 255, 255, 0)))
    draw = ImageDraw.Draw(icon)
    for x, y, width, height, accent in mark.blocks(points):
        draw.rounded_rectangle(
            (x * unit, y * unit, (x + width) * unit - 1, (y + height) * unit - 1),
            radius=height * unit / 2,
            fill=(*(mark.ACCENT if accent else mark.PAPER), 255),
        )
    icon.putalpha(mask)
    return icon.resize((pixels, pixels), Image.Resampling.LANCZOS)


def write_ico(path):
    images = [render(size) for size in ICO_SIZES]
    images[-1].save(
        path,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=images[:-1],
    )


def write_icns(path):
    """iconutil ships with macOS; elsewhere the committed .icns stays as it is."""
    if sys.platform != "darwin":
        print(f"Skipping {path.name}: iconutil needs macOS.")
        return
    with tempfile.TemporaryDirectory() as directory:
        iconset = Path(directory) / "checktokens.iconset"
        iconset.mkdir()
        for points in ICONSET:
            render(points).save(iconset / f"icon_{points}x{points}.png")
            render(points * 2, points).save(iconset / f"icon_{points}x{points}@2x.png")
        subprocess.run(
            ["iconutil", "--convert", "icns", "--output", str(path), str(iconset)], check=True
        )


def main():
    if not shutil.which("iconutil") and sys.platform == "darwin":
        raise SystemExit("iconutil is missing; install Xcode Command Line Tools.")
    target = ROOT / "assets/icon"
    target.mkdir(parents=True, exist_ok=True)
    render(1024).save(target / "checktokens-1024.png")
    write_ico(target / "checktokens.ico")
    write_icns(target / "checktokens.icns")
    print(f"Wrote icons to {target.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
