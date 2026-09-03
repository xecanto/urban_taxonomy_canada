"""
Build the full radial taxonomy wheel in ONE figure: the dendrogram drawn
natively in the centre (no separate image, no raster compositing/clipping —
see "why no compositing" below), morphometric character rings, a log-scale
abundance ring, and real building-footprint silhouette thumbnails with
leader lines.

Why no compositing: an earlier version rendered the dendrogram as its own
image (build_radial_dendrogram.py) and pasted it into this script's open
centre via build_radial_composite.py. That worked but had a real ceiling —
raster paste/scale meant no control over how the dendrogram's own legs
looked at the seam, and it added a whole extra alignment-and-scale step to
get right. Drawing it directly into this script's own Axes (same data
coordinates as the rings, same leaf order, same angle convention) removes
that step entirely: the dendrogram is real vector content here, at whatever
size the rings' own hub_r calls for, no scaling/pasting/clipping involved.
build_radial_dendrogram.py still exists and is still useful on its own
(e.g. for a plain non-radial-wheel dendrogram figure) but is no longer
required to build this one.

Leaves = level_5 clusters (32, by default) -- the dendrogram is truncated
to the same level, so both parts share the exact same 32 leaves in the
exact same angular order by construction (not just "close").

Reusable — tweak via CLI flags instead of editing the script.

Usage:
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_rings.py
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_rings.py --level level_4 --no-thumbnails
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_rings.py --dendro-gamma 1.3
"""

import argparse
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyogrio
from matplotlib.patches import Wedge
from matplotlib.transforms import Affine2D

sys.path.insert(0, str(Path(__file__).parent))
import build_radial_dendrogram as dendro  # noqa: E402 -- needs sys.path set first

# Single source of truth for the Bold ramp is build_radial_dendrogram.py
# (itself copied verbatim from urban_taxonomy_viewer/src/utils/colors.ts) --
# referenced here as dendro.BOLD_RAMP so the two never drift apart.

# Keep in sync with build_radial_legends.py -- both were picked for real,
# informative spread (checked via quantiles / fraction-at-single-value)
# rather than following the source paper's picks blindly.
RINGS = [
    {"col": "sdbAre",    "label": "building area",              "cmap": "Oranges"},
    {"col": "ssbCCo",    "label": "building compactness",        "cmap": "Blues"},
    {"col": "sicCAR",    "label": "coverage area ratio",         "cmap": "Purples"},
    {"col": "mtbNDi",    "label": "distance to neighbouring buildings", "cmap": "Reds"},
    {"col": "chm_cover", "label": "canopy cover",  "cmap": "Greens"},
]

REGIONS_DIR = Path("outputs_canada_cma_ca/regions")
_region_cache: dict[str, gpd.GeoDataFrame] = {}


def get_region_tessellation(region: str) -> gpd.GeoDataFrame:
    """Tessellation cells for one region, positionally labelled with their
    morphotope id (see notebooks_buidings/08_morphotope_chars.ipynb for the
    same positional-join technique used across this pipeline)."""
    if region in _region_cache:
        return _region_cache[region]
    tess = gpd.read_parquet(REGIONS_DIR / region / "02_tessellation" / "tessellation.parquet")
    tess = tess[tess.index >= 0].sort_index().reset_index(drop=True)
    labels = pd.read_parquet(
        REGIONS_DIR / region / "06_morphotopes" / "tessellation_labels_postprocessed.parquet"
    )["morphotope_label"].reset_index(drop=True)
    tess["morph"] = labels.values
    _region_cache[region] = tess
    return tess


def get_footprint_thumbnail(morph_id: str, max_cells: int = 220, margin_frac: float = 0.06):
    """Real, COMPLETE building footprints belonging to one morphotope --
    never a rectangular bounding-box crop. Earlier versions queried
    buildings.gpkg with a literal square/rectangular bbox: any real urban
    grid fills a square window edge-to-edge, so the result always read as
    "a rectangular chunk cut out of the city" (and could slice a building
    in half right at the window edge). Fixed by selecting spatially: union
    the morphotope's own tessellation-cell geometry (an organic, irregular
    shape -- Voronoi-like cells around real buildings, not a rectangle),
    then keep only buildings whose centroid actually falls inside that
    shape. Every building shown is therefore whole (never cut), and the
    sample's outer silhouette is the morphotope's own natural, non-rectangular
    boundary, not a box. The plot's own axis limits are then set to the
    selected buildings' real bounds (small margin) -- not a bigger uniform
    window -- so no empty rectangular padding either.

    Some morphotopes are spatially FRAGMENTED (several disconnected patches
    -- e.g. a few separate settlements sharing the same statistical profile)
    -- checked this directly: 5 of the 32 representative morphotopes have
    >1 connected component, 3 of those roughly 50/50 split. Use ONLY the
    LARGEST one (most cells = clearest, most representative single patch)
    -- "if a cluster has 3 locations in one region, show the one with the
    best visibility," not all three stitched together.

    If that component is still large (too many cells to be a clean sample),
    take a SAMPLE of its cells -- the max_cells nearest the component's own
    centroid, a genuine spatial subset of that same morphotope, not a wider
    crop window -- rather than trying to show every cell it has.

    Returns a GeoDataFrame + natural bbox in the region's own CRS, or None.
    """
    region = morph_id[1:].split("_")[0]  # "R535_3804_710" -> "535"
    region_dir = REGIONS_DIR / region
    if not region_dir.exists():
        return None
    tess = get_region_tessellation(region)
    cells = tess[tess["morph"] == morph_id]
    if cells.empty:
        return None

    # Pick the largest connected component of this morphotope's own cells
    # (by cell count) instead of the whole (possibly fragmented) extent.
    if len(cells) > 1:
        merged = gpd.GeoDataFrame(geometry=[cells.geometry.buffer(0.01).unary_union])
        parts = merged.explode(index_parts=False).geometry
        if len(parts) > 1:
            cell_pts = cells.geometry.centroid
            counts = [cell_pts.within(part).sum() for part in parts]
            best_part = parts.iloc[int(np.argmax(counts))]
            cells = cells[cell_pts.within(best_part).values]
            if cells.empty:
                return None

    # Too many cells in this one patch? Take a spatial SAMPLE (nearest
    # max_cells to the patch's own centroid) instead of a bigger crop.
    if len(cells) > max_cells:
        c = cells.geometry.centroid
        cx0, cy0 = c.x.mean(), c.y.mean()
        dist = ((c.x - cx0) ** 2 + (c.y - cy0) ** 2)
        cells = cells.loc[dist.nsmallest(max_cells).index]

    # Union of the SELECTED cells' own organic shape (buffered a few metres
    # so buildings sitting right at a cell boundary aren't dropped) -- this
    # is the true, non-rectangular sampling region.
    sample_shape = cells.geometry.buffer(3.0).unary_union
    minx, miny, maxx, maxy = sample_shape.bounds

    # Coarse bbox read for I/O speed only; the real (non-rectangular)
    # selection happens after, via the spatial predicate below.
    buildings = pyogrio.read_dataframe(
        region_dir / "01_preprocessed" / "buildings.gpkg", bbox=(minx, miny, maxx, maxy)
    )
    if buildings.empty:
        return None
    buildings = buildings[buildings.geometry.centroid.within(sample_shape)]
    if buildings.empty:
        return None

    # Natural bbox = actual selected buildings' own bounds + a small margin
    # (not the cell union's bounds, and not a bigger uniform window).
    bminx, bminy, bmaxx, bmaxy = buildings.total_bounds
    mx, my = (bmaxx - bminx) * margin_frac, (bmaxy - bminy) * margin_frac
    bbox = (bminx - mx, bminy - my, bmaxx + mx, bmaxy + my)
    return buildings, bbox


def render_thumbnail(morph_id: str, out_path: Path, size_px: int = 1200, dpi: int = 400,
                      max_cells: int = 220, margin_frac: float = 0.06):
    result = get_footprint_thumbnail(morph_id, max_cells=max_cells, margin_frac=margin_frac)
    if result is None:
        return False
    buildings, bbox = result
    fig, ax = plt.subplots(figsize=(size_px / dpi, size_px / dpi), dpi=dpi)
    buildings.plot(ax=ax, facecolor="black", edgecolor="none")
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])
    ax.set_aspect("equal")
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)
    return True


def build(
    data_dir: Path, level: str, out_path: Path, thumbnails: bool,
    thumb_dir: Path, size_px: int = 2000, dpi: int = 150, force_thumbnails: bool = False,
    hub_r: float = 0.46, ring_w: float = 0.035, abund_gap: float = 0.02,
    abund_width: float = 0.08, thumb_gap: float = 0.06,
    thumb_width: float = 0.16, thumb_height: float = 0.4,
    sample_max_cells: int = 220, sample_margin_frac: float = 0.06,
    dendro_data: str | None = None, dendro_gamma: float = 1.35, dendro_min_r_frac: float = 0.18,
):
    cdata = pd.read_parquet(data_dir / "cdata.parquet")
    cmap_df = pd.read_parquet(data_dir / "cluster_mapping.parquet")
    df = cdata.join(cmap_df)

    ring_cols = [r["col"] for r in RINGS]
    agg = df.groupby(level)[ring_cols].mean()
    ancestor = df.groupby(level)["level_3"].first()
    morph_count = df.groupby(level).size()

    # representative morphotope id per leaf = the one with the largest
    # "area of largest connected structures" (limAre) -- biggest, most
    # visually legible built-up patch in that leaf.
    id_col = "morph_id"
    df2 = df.reset_index(names=id_col)
    rep_idx = df2.groupby(level)["limAre"].idxmax()
    rep = df2.loc[rep_idx].set_index(level)[id_col]

    leaves = agg.join(ancestor).join(morph_count.rename("n_morphotopes"))
    leaves["rep_morph"] = rep

    # --- build the dendrogram tree FIRST (before drawing) so its own DFS
    # leaf order can be used to arrange the rings -- single source of truth,
    # no separate leaf-order file needed: whatever order the tree naturally
    # produces IS the order the wedges are drawn in, by construction.
    dendro_summary_path = Path(dendro_data) if dendro_data else (
        Path(__file__).resolve().parent.parent.parent.parent / "urban_taxonomy_viewer" / "public" / "data" / "global_cluster_summary.json"
    )
    with open(dendro_summary_path, encoding="utf-8") as f:
        dsummary = json.load(f)
    droot = dendro.build_tree(dsummary, leaf_level=level)
    dlevels = dsummary["levels"]
    dmax_depth = dlevels.index(level) + 1
    dendro.assign_cluster_layout(droot, dmax_depth)

    dleaf_nodes = []

    def _collect_leaves(node):
        if not node.children:
            dleaf_nodes.append(node)
        else:
            for c in node.children:
                _collect_leaves(c)

    _collect_leaves(droot)
    leaf_order = [leaf.cluster_by_level[level] for leaf in dleaf_nodes]
    leaves = leaves.loc[leaf_order]

    n = len(leaves)
    cluster_ids_l3 = sorted(df["level_3"].unique())

    norms = {}
    for r in RINGS:
        s = leaves[r["col"]]
        lo, hi = s.quantile(0.02), s.quantile(0.98)
        norms[r["col"]] = ((s.clip(lo, hi) - lo) / (hi - lo + 1e-12)).values

    # --- render standalone thumbnails first (also used to composite below) ---
    thumb_paths: dict = {}
    if thumbnails:
        thumb_dir.mkdir(parents=True, exist_ok=True)
        ok, fail = 0, 0
        for leaf_id, row in leaves.iterrows():
            morph_id = row["rep_morph"]
            out = thumb_dir / f"thumb_{level}_{leaf_id}.png"
            if out.exists() and not force_thumbnails:
                thumb_paths[leaf_id] = out
                ok += 1
                continue
            try:
                success = render_thumbnail(morph_id, out, max_cells=sample_max_cells,
                                            margin_frac=sample_margin_frac)
            except Exception as e:
                print(f"  thumbnail failed for leaf {leaf_id} ({morph_id}): {e}")
                success = False
            if success:
                thumb_paths[leaf_id] = out
                ok += 1
            else:
                fail += 1
        print(f"thumbnails: {ok} saved to {thumb_dir}, {fail} failed")

    n_rings = len(RINGS)
    angle_step = 2 * math.pi / n
    abund_r0 = hub_r + n_rings * ring_w + abund_gap
    abund_r1 = abund_r0 + abund_width
    thumb_r0 = abund_r1 + thumb_gap

    # Thumbnails are drawn ROTATED to point radially outward (long axis
    # along the radius, short axis tangential) instead of axis-aligned
    # squares. This decouples the two dimensions: tangential WIDTH is the
    # only thing that can make neighbours overlap, so it alone is solved
    # against the arc available at the inner edge (thumb_r0 -- the tightest
    # point, since available arc only grows with radius from there); radial
    # HEIGHT has no neighbour to collide with (petals all point straight out
    # from the centre) so it's a free parameter -- this is how the samples
    # actually get bigger without just pushing everything further out.
    if thumbnails:
        safety = 0.85
        chord = 2 * thumb_r0 * math.sin(angle_step / 2) if n else thumb_width
        thumb_width = min(thumb_width, chord * safety)
    outer_extent = (thumb_r0 + thumb_height + 0.05) if thumbnails else (abund_r1 + 0.05)

    # Save the geometry actually used, for reference / reuse by other tools.
    geometry = {
        "hub_r": hub_r, "ring_w": ring_w, "n_rings": n_rings,
        "abund_r0": abund_r0, "abund_r1": abund_r1,
        "thumb_r0": thumb_r0, "thumb_width": thumb_width, "thumb_height": thumb_height,
        "outer_extent": outer_extent, "axes_frac": 0.94,
        "size_px": size_px, "thumbnails": thumbnails,
    }
    geom_path = out_path.with_name(out_path.stem + "_geometry.json")
    with open(geom_path, "w", encoding="utf-8") as f:
        json.dump(geometry, f, indent=2)

    # Plain square figure -- no embedded legend column. Legends are now
    # separate images (build_radial_legend_branches.py / _rings.py) so this
    # figure is just the wheel itself, at full resolution.
    fig = plt.figure(figsize=(size_px / dpi, size_px / dpi), dpi=dpi)
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    ax.set_xlim(-outer_extent, outer_extent)
    ax.set_ylim(-outer_extent, outer_extent)
    ax.set_aspect("equal")
    ax.axis("off")

    # --- dendrogram, drawn natively into this same Axes (no compositing) ---
    # (droot etc. already built above, before the leaf-order step)
    dcluster_ids = cluster_ids_l3

    dendro_outer_r = hub_r * 0.94  # small margin so it doesn't touch the innermost ring
    dendro_min_r = hub_r * dendro_min_r_frac

    def d_radial_r(t):
        return dendro_min_r + dendro.ease_out_pow(t, dendro_gamma) * (dendro_outer_r - dendro_min_r)

    def d_node_pos(node):
        angle = node.x * 2 * math.pi
        r = d_radial_r(node.y)
        return dendro.point_radial(angle, r)

    def draw_dendro_links(node):
        for c in node.children:
            s_rad = d_radial_r(node.y)
            t_angle = c.x * 2 * math.pi
            s_angle = node.x * 2 * math.pi
            bx, by = dendro.point_radial(t_angle, s_rad)
            cx_, cy_ = d_node_pos(c)
            px, py = d_node_pos(node)
            delta = dendro.angle_delta(t_angle, s_angle)
            n_steps = max(2, int(abs(delta) / (2 * math.pi) * 200) + 2)
            arc_pts = [dendro.point_radial(t_angle + delta * (i / n_steps), s_rad) for i in range(n_steps + 1)]
            xs = [cx_, bx] + [p[0] for p in arc_pts] + [px]
            ys = [cy_, by] + [p[1] for p in arc_pts] + [py]
            color = dendro.get_color(c, "level_3", dcluster_ids)
            ax.plot(xs, ys, color=color, linewidth=1.3, alpha=0.85, zorder=6, solid_capstyle="round")
            draw_dendro_links(c)

    draw_dendro_links(droot)

    def draw_dendro_nodes(node):
        x, y = d_node_pos(node)
        is_leaf = not node.children
        color = dendro.get_color(node, "level_3", dcluster_ids)
        ax.scatter([x], [y], s=(10 if is_leaf else 6), color=color,
                   alpha=(0.95 if is_leaf else 0.6), zorder=7, linewidths=0)
        for c in node.children:
            draw_dendro_nodes(c)

    draw_dendro_nodes(droot)

    # Full continuous regions (pie-slice wedges touching edge-to-edge), not a
    # grid of small boxes with white gutters -- leaves are separated only by
    # thin straight radial lines from the hub outward, drawn once below.
    leaf_disp_h = [0.0] * n  # each leaf's ACTUAL rendered thumbnail length (not the box ceiling) -- dividers use this
    for i, (leaf_id, row) in enumerate(leaves.iterrows()):
        a0 = i * angle_step
        a1 = (i + 1) * angle_step
        a_mid = (a0 + a1) / 2
        # matplotlib.patches.Wedge uses its OWN angle convention (0deg = east,
        # increasing counter-clockwise) which is a mirror image of the
        # point_radial() convention used everywhere else in this script (and
        # in build_radial_dendrogram.py: 0 = up/north, increasing clockwise).
        # A naive "-90" shift only rotates, it doesn't undo that mirroring --
        # this must be a reflection (deg = 90 - my_angle), with start/end
        # swapped since Wedge sweeps CCW from theta1 to theta2.
        deg0, deg1 = 90 - math.degrees(a1), 90 - math.degrees(a0)

        for ring_i, r in enumerate(RINGS):
            cmap = plt.get_cmap(r["cmap"])
            val = norms[r["col"]][i]
            color = cmap(0.25 + 0.65 * val)
            r0 = hub_r + ring_i * ring_w
            r1 = r0 + ring_w
            w = Wedge((0, 0), r1, deg0, deg1, width=r1 - r0, facecolor=color, edgecolor=color, linewidth=0.3)
            ax.add_patch(w)

        # abundance (log-scale morphotope count) -- deliberately a bar, not a
        # full region, so its varying height stays readable as a value.
        max_log = math.log10(leaves["n_morphotopes"].max() + 1)
        val_log = math.log10(row["n_morphotopes"] + 1) / max_log
        r1 = abund_r0 + val_log * (abund_r1 - abund_r0)
        w = Wedge((0, 0), r1, deg0, deg1, width=r1 - abund_r0, facecolor="#7fb8e0", edgecolor="#7fb8e0", linewidth=0.3)
        ax.add_patch(w)

        # --- thumbnail, rotated to point radially outward ---
        # No dotted leader line to each thumbnail's centre any more -- see
        # the grey radial dividers drawn once, below, at the wedge
        # boundaries instead (replaces per-thumbnail leaders + the old
        # separate outer boundary guide circle in one cleaner element).
        if thumbnails and leaf_id in thumb_paths:
            img = plt.imread(thumb_paths[leaf_id])
            img_h_px, img_w_px = img.shape[0], img.shape[1]
            aspect = img_w_px / img_h_px
            # fit the (roughly square) source image into the thumb_width x
            # thumb_height box, preserving its aspect ratio (no distortion)
            if aspect > thumb_width / thumb_height:
                disp_w, disp_h = thumb_width, thumb_width / aspect
            else:
                disp_h, disp_w = thumb_height, thumb_height * aspect
            leaf_disp_h[i] = disp_h

            # Local frame: x in [-disp_w/2, disp_w/2] (tangential), y in
            # [0, disp_h] (radial, base at the leader line's outer end).
            # rotate_deg(-a_mid_deg) sends local +y (up) to the outward
            # radial unit vector (sin(a_mid), cos(a_mid)) -- same convention
            # point_radial() uses everywhere else in this script.
            trans = (
                Affine2D().rotate_deg(-math.degrees(a_mid))
                .translate(thumb_r0 * math.sin(a_mid), thumb_r0 * math.cos(a_mid))
                + ax.transData
            )
            # No border box, per feedback -- the source figure's thumbnails
            # float directly on white with no frame, just the leader line.
            ax.imshow(img, extent=(-disp_w / 2, disp_w / 2, 0, disp_h), transform=trans,
                      cmap="gray", interpolation="antialiased", zorder=2)

    # Radial dividers, two segments per leaf boundary:
    #  - WHITE, hub -> ring edge: separates the wedges themselves (this is
    #    what makes them read as "full regions" rather than a checkerboard).
    #  - GREY, ring edge -> where the footprint actually ends: takes over
    #    the job the dotted per-thumbnail leader lines used to do (now
    #    removed), continuing from the SAME point the rings already end at
    #    -- not from the centre. Stops exactly at the real rendered content
    #    (the longer of the two neighbouring thumbnails' actual disp_h, not
    #    the box ceiling thumb_height) -- an earlier version ran a fixed
    #    amount past every thumbnail's box regardless of its real content
    #    length, which overshot by a lot whenever a thumbnail's true aspect
    #    ratio made it much shorter than the box. Together these replace the
    #    old separate "outer boundary" guide circle too.
    for i in range(n):
        a = i * angle_step
        x0, y0 = hub_r * math.sin(a), hub_r * math.cos(a)
        x1, y1 = (abund_r1 + 0.02) * math.sin(a), (abund_r1 + 0.02) * math.cos(a)
        ax.plot([x0, x1], [y0, y1], color="white", linewidth=1.1, zorder=5)
        if thumbnails:
            neighbour_h = max(leaf_disp_h[i - 1], leaf_disp_h[i % n])
            if neighbour_h > 0:
                r_divider_out = thumb_r0 + neighbour_h
                x2, y2 = r_divider_out * math.sin(a), r_divider_out * math.cos(a)
                ax.plot([x1, x2], [y1, y2], color="#cfcfcf", linewidth=0.8, zorder=1)


    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)
    print(f"saved {out_path} (thumb_width after overlap-safety adjustment: {thumb_width:.4f}, thumb_height: {thumb_height:.4f})")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default="outputs_canada_cma_ca/09_hierarchy")
    p.add_argument("--level", default="level_5", help="Leaf level for the rings (default level_5, 32 clusters)")
    p.add_argument("--size-px", type=int, default=8800, help="Print quality: default is 22in at 400dpi")
    p.add_argument("--dpi", type=int, default=400)
    p.add_argument("--out", default="poster_presentation/assets/figures/radial_taxonomy.png",
                    help="This is now the complete figure (dendrogram + rings + thumbnails), not just the rings")
    p.add_argument("--thumb-dir", default="poster_presentation/assets/figures/thumbnails")
    p.add_argument("--no-thumbnails", dest="thumbnails", action="store_false")
    p.add_argument("--force-thumbnails", action="store_true", help="Re-fetch/redraw thumbnails even if cached on disk")
    p.add_argument("--hub-r", type=float, default=0.46, help="Open centre radius, for the dendrogram (default 0.46, bigger = more room for it)")
    p.add_argument("--ring-w", type=float, default=0.035, help="Width of each of the 5 character rings (thin)")
    p.add_argument("--abund-gap", type=float, default=0.02, help="Gap between character rings and the abundance ring")
    p.add_argument("--abund-width", type=float, default=0.08, help="Width of the abundance ring")
    p.add_argument("--thumb-gap", type=float, default=0.06, help="Gap between the rings and the thumbnails")
    p.add_argument("--thumb-width", type=float, default=0.16,
                    help="Tangential (max) width of each thumbnail -- auto-shrunk if needed to avoid overlap with neighbours")
    p.add_argument("--thumb-height", type=float, default=0.4,
                    help="Radial length of each thumbnail -- free to enlarge, no neighbour can overlap it in this direction")
    p.add_argument("--sample-max-cells", type=int, default=220,
                    help="If a morphotope's largest connected patch has more cells than this, sample only the "
                         "nearest N to its own centroid (a spatial subset of that SAME morphotope) instead of "
                         "showing everything -- never widens the crop into a bigger rectangular window")
    p.add_argument("--sample-margin-frac", type=float, default=0.06,
                    help="Small margin around the selected buildings' own natural bounds, as a fraction of "
                         "their extent -- just enough that nothing touches the frame edge, not a bigger window")
    p.add_argument("--dendro-data", default=None,
                    help="Path to global_cluster_summary.json (default: ../urban_taxonomy_viewer/public/data/global_cluster_summary.json)")
    p.add_argument("--dendro-gamma", type=float, default=1.35,
                    help="Dendrogram depth-easing power (app default 2.2 -- lower gives longer, more visible outer legs; 1.35 default here for print clarity)")
    p.add_argument("--dendro-min-r-frac", type=float, default=0.18,
                    help="Dendrogram's own inner hub radius, as a fraction of hub_r")
    args = p.parse_args()

    build(
        Path(args.data_dir), args.level, Path(args.out), args.thumbnails,
        Path(args.thumb_dir), args.size_px, args.dpi, args.force_thumbnails,
        args.hub_r, args.ring_w, args.abund_gap, args.abund_width, args.thumb_gap,
        args.thumb_width, args.thumb_height,
        args.sample_max_cells, args.sample_margin_frac,
        args.dendro_data, args.dendro_gamma, args.dendro_min_r_frac,
    )
