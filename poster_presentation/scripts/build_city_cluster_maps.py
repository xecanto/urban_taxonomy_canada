"""
Real per-city cluster maps: for a list of named CMAs/CAs, draw every real
building coloured by its national level_3 cluster (the same "Bold" 20-colour
ramp as the dendrogram / legend_wheel_branches.png), on top of a boundary
layer (grey outline, white fill). Buildings get no outline -- colour only.

Reusable -- edit CITIES below (name -> CMAUID, look up via
data/CMA_CA_boundaries.gdb's CMANAME/CMAUID) and rerun.

Usage:
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_city_cluster_maps.py
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import build_radial_dendrogram as dendro

REGIONS_DIR = Path("outputs_canada_cma_ca/regions")
OUT_DIR = Path("poster_presentation/assets/figures/city_maps")
DPI = 400
LEVEL = "level_3"  # 8 national clusters -- matches the Bold 1-8 legend

CITIES = [
    ("820", "Okotoks"),
    ("830", "Red Deer"),
    ("533", "Ingersoll"),
    ("527", "Cobourg"),
    ("544", "Woodstock"),
]


def load_region_tessellation(cmauid: str) -> gpd.GeoDataFrame:
    base = REGIONS_DIR / cmauid
    tess = gpd.read_parquet(base / "02_tessellation" / "tessellation.parquet")
    tess = tess[tess.index >= 0].sort_index().reset_index(drop=True)
    post = pd.read_parquet(base / "06_morphotopes" / "tessellation_labels_postprocessed.parquet")["morphotope_label"]
    tess["morph"] = post.reset_index(drop=True).values
    clusters = pd.read_parquet(base / "09_hierarchy" / "tessellation_clusters_final.parquet")
    tess[LEVEL] = clusters[LEVEL].reset_index(drop=True).values
    return tess


def load_region_buildings_with_level(cmauid: str) -> gpd.GeoDataFrame:
    base = REGIONS_DIR / cmauid
    buildings = gpd.read_file(base / "01_preprocessed" / "buildings.gpkg", columns=["BLDG_ID"])
    tess = load_region_tessellation(cmauid)
    buildings = gpd.sjoin(
        buildings, tess[[LEVEL, "geometry"]], predicate="within", how="left"
    ).drop(columns="index_right")
    return buildings


def build_one(cmauid: str, name: str):
    base = REGIONS_DIR / cmauid
    boundary = gpd.read_file(base / "boundary_unbuffered.gpkg")
    buildings = load_region_buildings_with_level(cmauid)

    # buildings.gpkg is read from the buffered region, so it can include
    # buildings outside the real (unbuffered) CMA/CA boundary -- drop those.
    boundary_union = boundary.geometry.union_all()
    buildings = buildings[buildings.geometry.centroid.within(boundary_union)]

    cluster_ids = sorted(c for c in buildings[LEVEL].dropna().unique())
    color_map = {c: dendro.BOLD_RAMP[int(c) - 1] for c in cluster_ids}

    minx, miny, maxx, maxy = boundary.total_bounds
    w, h = maxx - minx, maxy - miny
    fig_w = 8.0
    fig_h = fig_w * h / w
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)

    boundary.plot(ax=ax, facecolor="white", edgecolor="#cccccc", linewidth=1.0, zorder=1)

    sub = buildings.dropna(subset=[LEVEL])
    sub.plot(ax=ax, color=sub[LEVEL].map(color_map), edgecolor="none", zorder=2)

    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_title(f"{name} — {LEVEL} clusters (Bold symbology)", fontsize=13, loc="left", pad=8)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{name.lower().replace(' ', '_')}_clusters.png"
    fig.savefig(out_path, facecolor="white", bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    print(f"saved {out_path}  ({len(buildings)} buildings, {len(cluster_ids)} clusters)")


def build_one_morphotopes(cmauid: str, name: str, color_by: str = "level_3"):
    """color_by: 'level_3' -- each morphotope-shaped region coloured by its
    level_3 cluster (Bold ramp), same colouring as the _clusters.png maps.
    'morph_id' -- each region coloured by its own unique morphotope id
    (tab20, cycling) -- the original version, kept as its own flag/output."""
    base = REGIONS_DIR / cmauid
    boundary = gpd.read_file(base / "boundary_unbuffered.gpkg")
    boundary_union = boundary.geometry.union_all()

    tess = load_region_tessellation(cmauid)
    tess = tess[tess.geometry.centroid.within(boundary_union)]

    if color_by == "level_3":
        dissolved = tess.dissolve(by="morph", aggfunc={LEVEL: "first"}).reset_index()
        cluster_ids = sorted(c for c in dissolved[LEVEL].dropna().unique())
        color_map = {c: dendro.BOLD_RAMP[int(c) - 1] for c in cluster_ids}
        sub = dissolved.dropna(subset=[LEVEL])
        colors = sub[LEVEL].map(color_map)
        suffix = "morphotopes"
        title = f"{name} — morphotopes ({LEVEL} clusters, Bold symbology)"
    else:
        dissolved = tess.dissolve(by="morph").reset_index()
        codes = dissolved["morph"].astype("category").cat.codes
        cmap = plt.get_cmap("tab20")
        sub = dissolved
        colors = [cmap(c % 20) for c in codes]
        suffix = "morphotopes_by_id"
        title = f"{name} — morphotopes (by morphotope id)"

    minx, miny, maxx, maxy = boundary.total_bounds
    w, h = maxx - minx, maxy - miny
    fig_w = 8.0
    fig_h = fig_w * h / w
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)

    boundary.plot(ax=ax, facecolor="white", edgecolor="#cccccc", linewidth=1.0, zorder=1)
    sub.plot(ax=ax, color=colors, edgecolor="white", linewidth=0.3, zorder=2)

    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_title(title, fontsize=13, loc="left", pad=8)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{name.lower().replace(' ', '_')}_{suffix}.png"
    fig.savefig(out_path, facecolor="white", bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    print(f"saved {out_path}  ({len(dissolved)} morphotopes)")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--morph-color", choices=["level_3", "morph_id", "both"], default="both",
        help="Colour the morphotope maps by level_3 cluster, by unique morphotope id, or both (default)",
    )
    args = p.parse_args()
    for cmauid, name in CITIES:
        build_one(cmauid, name)
        if args.morph_color in ("level_3", "both"):
            build_one_morphotopes(cmauid, name, color_by="level_3")
        if args.morph_color in ("morph_id", "both"):
            build_one_morphotopes(cmauid, name, color_by="morph_id")


if __name__ == "__main__":
    main()
