"""
Composite the level_5-aligned dendrogram (build_radial_dendrogram.py
--no-legend output) into the open centre of the rings wheel
(build_radial_rings.py output), scaled and centred precisely from the
rings script's own actual geometry (its *_geometry.json sidecar file) --
not eyeballed, and not a second hardcoded copy of the numbers that could
drift out of sync when the rings script's proportions are retuned.

Usage:
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_composite.py
"""

import argparse
import json
from pathlib import Path

from PIL import Image

# Must match build_radial_dendrogram.py's own constants for --no-legend mode
# (these are simple/stable -- xlim and R never change independently of the
# script itself, unlike the rings' proportions which get retuned).
DENDRO_XLIM = 1.15
DENDRO_R = 1.0


def compute_scale(rings_geometry: dict, dendro_size_px: int):
    rings_px_per_unit = (rings_geometry["axes_frac"] * rings_geometry["size_px"]) / (2 * rings_geometry["outer_extent"])
    hub_r_px_in_rings = rings_geometry["hub_r"] * rings_px_per_unit

    dendro_px_per_unit = dendro_size_px / (2 * DENDRO_XLIM)
    dendro_R_px = DENDRO_R * dendro_px_per_unit

    scale = hub_r_px_in_rings / dendro_R_px
    return scale, hub_r_px_in_rings


def build(rings_path: Path, dendro_path: Path, out_path: Path, geometry_path: Path | None = None):
    rings_img = Image.open(rings_path).convert("RGBA")
    dendro_img = Image.open(dendro_path).convert("RGBA")

    if geometry_path is None:
        geometry_path = rings_path.with_name(rings_path.stem + "_geometry.json")
    with open(geometry_path, encoding="utf-8") as f:
        geometry = json.load(f)
    if rings_img.width != geometry["size_px"]:
        print(f"WARNING: rings image is {rings_img.width}px wide but geometry file says {geometry['size_px']}px "
              "-- they may be out of sync (re-run build_radial_rings.py).")

    scale, hub_r_px = compute_scale(geometry, dendro_img.width)
    new_size = max(1, round(dendro_img.width * scale))
    dendro_resized = dendro_img.resize((new_size, new_size), Image.LANCZOS)

    cx, cy = rings_img.width / 2, rings_img.height / 2
    paste_x = round(cx - new_size / 2)
    paste_y = round(cy - new_size / 2)

    combined = rings_img.copy()
    combined.alpha_composite(dendro_resized, (paste_x, paste_y))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.convert("RGB").save(out_path)
    print(f"hub radius in rings image: {hub_r_px:.1f}px; dendrogram scaled {scale:.4f}x to {new_size}px; saved {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rings", default="poster_presentation/assets/figures/radial_taxonomy_rings.png")
    p.add_argument("--dendrogram", default="poster_presentation/assets/figures/dendrogram_center_transparent.png")
    p.add_argument("--out", default="poster_presentation/assets/figures/radial_taxonomy_combined.png")
    p.add_argument("--geometry", default=None,
                    help="Path to the rings' *_geometry.json sidecar (default: inferred from --rings)")
    args = p.parse_args()

    build(Path(args.rings), Path(args.dendrogram), Path(args.out),
          Path(args.geometry) if args.geometry else None)
