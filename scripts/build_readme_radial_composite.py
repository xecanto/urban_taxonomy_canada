"""
Compose a single README-ready figure from the EXISTING radial taxonomy wheel
and its two legend images -- pure compositing of already-rendered PNGs, no
regeneration, no edits to poster_presentation/scripts/*.py or the source
images themselves.

Layout: the wheel on the left, the two legends stacked on the right, on a
white canvas. Also writes a web-sized (max 1600px wide) copy for a fast-
loading README.

Usage:
    .venv\\Scripts\\python.exe scripts\\build_readme_radial_composite.py
"""

from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

FIGS = Path("poster_presentation/assets/figures")
OUT_DIR = Path("readme_assets")


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def paste_on_white(im: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.paste(im, mask=im.split()[3])
    return bg.convert("RGB")


def build():
    wheel = load_rgba(FIGS / "radial_taxonomy.png")
    rings_legend = load_rgba(FIGS / "legend_wheel_rings.png")
    branches_legend = load_rgba(FIGS / "legend_wheel_branches.png")

    pad = 60
    legend_col_w = max(rings_legend.width, branches_legend.width)
    canvas_w = wheel.width + pad * 3 + legend_col_w
    canvas_h = max(wheel.height, rings_legend.height + branches_legend.height + pad * 3)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
    canvas.paste(wheel, (pad, (canvas_h - wheel.height) // 2), mask=wheel.split()[3])

    legend_x = pad * 2 + wheel.width
    legend_stack_h = rings_legend.height + branches_legend.height + pad
    y0 = (canvas_h - legend_stack_h) // 2
    canvas.paste(rings_legend, (legend_x, y0), mask=rings_legend.split()[3])
    canvas.paste(branches_legend, (legend_x, y0 + rings_legend.height + pad), mask=branches_legend.split()[3])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    full_path = OUT_DIR / "radial_taxonomy_with_legends.png"
    canvas.convert("RGB").save(full_path)
    print(f"saved {full_path}  ({canvas.width} x {canvas.height} px)")

    web_w = 1600
    scale = web_w / canvas.width
    web = canvas.convert("RGB").resize((web_w, int(canvas.height * scale)), Image.LANCZOS)
    web_path = OUT_DIR / "radial_taxonomy_with_legends_web.png"
    web.save(web_path, optimize=True)
    print(f"saved {web_path}  ({web.width} x {web.height} px)")


if __name__ == "__main__":
    build()
