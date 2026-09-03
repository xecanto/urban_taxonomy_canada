"""
Build the "methodology overview" flow diagram (pipeline stages a-h) using
REAL captures from one worked example -- Winnipeg (CMAUID 602) -- instead of
generic icons/sketches. Same idea as the source paper's own figure and the
hand-drawn mockup this replaces: one small real neighbourhood carried through
elements -> morphometrics -> link -> SA^3 -> morphotopes, then a real
national dendrogram for the linkage step and real whole-city cluster maps
for the final hierarchical fabric.

Reusable -- rerun any time the underlying data changes.

Usage:
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_methodology_diagram.py
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import FancyArrowPatch
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).parent))
import build_radial_dendrogram as dendro

REGION = "602"  # Winnipeg (Statistics Canada CMAUID) -- the pilot city, data already cached locally
REGIONS_DIR = Path("outputs_canada_cma_ca/regions")
OUT_DIR = Path("poster_presentation/assets/figures/methodology")
DPI = 400

# Colour scheme echoes the source paper figure: red = real-world input,
# green = derived/generated, blue = individual (intrinsic) metrics,
# orange = combined (contextual) metrics.
RED = "#c0392b"
GREEN = "#4c8c4a"
BLUE = "#2f6fa5"
ORANGE = "#d98c2b"
GREY = "#888888"

# Crop window in EPSG:3979 (buildings.gpkg CRS) -- hand-picked via a density
# + cluster-diversity scan of the whole region: highest building count among
# windows that also span >1 level_1 cluster and >1 level_3 cluster, so the
# elements->morphotopes panels actually show real morphological variety
# instead of one uniform subdivision.
CX, CY, HALF = -156910.69, 99128.09, 450.0


def window_box():
    return box(CX - HALF, CY - HALF, CX + HALF, CY + HALF)


def load_tessellation_full():
    """Region-wide tessellation, positionally joined to morphotope labels,
    cluster levels, and cell-level characters -- same positional-join
    technique used throughout this pipeline (index>=0 filter + sort_index
    aligns every one of these per-cell parquet files to the same row order)."""
    base = REGIONS_DIR / REGION
    tess = gpd.read_parquet(base / "02_tessellation" / "tessellation.parquet")
    tess = tess[tess.index >= 0].sort_index()
    tess["orig_idx"] = tess.index.values  # keep the raw cell id -- needed to align tessellation_graph.parquet's (focal, neighbor) edges
    tess = tess.reset_index(drop=True)

    def load_aligned(path, cols=None):
        df = pd.read_parquet(path)
        df = df[df.index >= 0].sort_index().reset_index(drop=True)
        return df[cols] if cols else df

    pre = pd.read_parquet(base / "06_morphotopes" / "tessellation_labels_morphotopes.parquet")["morphotope_label"]
    post = pd.read_parquet(base / "06_morphotopes" / "tessellation_labels_postprocessed.parquet")["morphotope_label"]
    tess["pre_morph"] = pre.reset_index(drop=True).values
    tess["morph"] = post.reset_index(drop=True).values

    clusters = pd.read_parquet(base / "09_hierarchy" / "tessellation_clusters_final.parquet")
    for lvl in ["level_1", "level_2", "level_3", "level_5"]:
        tess[lvl] = clusters[lvl].reset_index(drop=True).values

    chars = load_aligned(base / "04_chars" / "tessellations_chars.parquet", ["sicCAR"])
    tess["sicCAR"] = chars["sicCAR"].values

    return tess


def load_window_data():
    base = REGIONS_DIR / REGION
    win = window_box()
    bbox = win.bounds

    buildings = gpd.read_file(base / "01_preprocessed" / "buildings.gpkg", bbox=bbox)
    buildings = buildings[buildings.geometry.centroid.within(win)].reset_index(drop=True)
    chars = pd.read_parquet(base / "04_chars" / "buildings_chars.parquet")
    new_cols = [c for c in ["sdbAre", "ssbCCo", "mtbNDi", "chm_cover"] if c not in buildings.columns]
    buildings = buildings.merge(chars[["BLDG_ID"] + new_cols], on="BLDG_ID", how="left")

    roads = gpd.read_file(base / "01_preprocessed" / "roads.gpkg", bbox=bbox)
    roads = roads[roads.geometry.intersects(win)].reset_index(drop=True)

    tess_full = load_tessellation_full()
    tess = tess_full[tess_full.geometry.centroid.within(win)].reset_index(drop=True)

    buildings = gpd.sjoin(
        buildings, tess[["morph", "level_1", "level_3", "level_5", "geometry"]], predicate="within", how="left"
    ).drop(columns="index_right")

    return buildings, roads, tess, tess_full, win


def style_ax(ax, win):
    ax.set_aspect("equal")
    ax.axis("off")
    minx, miny, maxx, maxy = win.bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)


def save_panel(fig, out_path):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.patch.set_alpha(0)
    fig.savefig(OUT_DIR / out_path, dpi=DPI, transparent=True, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"saved {OUT_DIR / out_path}")


def square_fig(size_in=2.3):
    fig, ax = plt.subplots(figsize=(size_in, size_in), dpi=DPI)
    return fig, ax


# --- a) elements: real footprints / real streets / real (generated) tessellation ---

def panel_buildings(buildings, win):
    fig, ax = square_fig()
    buildings.plot(ax=ax, facecolor="#555555", edgecolor="none")
    style_ax(ax, win)
    save_panel(fig, "a_buildings.png")


def panel_streets(roads, win):
    fig, ax = square_fig()
    roads.plot(ax=ax, color=RED, linewidth=1.1)
    style_ax(ax, win)
    save_panel(fig, "a_streets.png")


def panel_tessellation(tess, win):
    fig, ax = square_fig()
    tess.plot(ax=ax, facecolor="none", edgecolor=GREEN, linewidth=0.5)
    style_ax(ax, win)
    save_panel(fig, "a_tessellation.png")


# --- b) morphometrics: real per-building metrics, individual vs contextual ---

def panel_metric(buildings, win, column, cmap, out_name):
    fig, ax = square_fig()
    vmin, vmax = buildings[column].quantile([0.05, 0.95])
    buildings.plot(ax=ax, column=column, cmap=cmap, edgecolor="none", linewidth=0, vmin=vmin, vmax=vmax)
    style_ax(ax, win)
    save_panel(fig, out_name)


# --- c) link to buildings: real building <-> tessellation-cell attachment ---

def panel_link(buildings, tess, win):
    fig, ax = square_fig()
    tess.plot(ax=ax, facecolor="#eeeeee", edgecolor="#bbbbbb", linewidth=0.3)
    buildings.plot(ax=ax, facecolor=RED, edgecolor="none", alpha=0.85)

    tess_r = tess.reset_index(drop=True)
    tess_cent = tess_r.geometry.centroid
    b_cent = buildings.geometry.centroid
    joined = gpd.sjoin(buildings, tess_r[["geometry"]], predicate="within", how="left")

    for i, row in joined.iloc[::4].iterrows():
        cell_i = row["index_right"]
        if pd.isna(cell_i):
            continue
        bx, by = b_cent.loc[i].x, b_cent.loc[i].y
        tx, ty = tess_cent.loc[int(cell_i)].x, tess_cent.loc[int(cell_i)].y
        ax.plot([bx, tx], [by, ty], color=BLUE, linewidth=0.25, alpha=0.5, zorder=2)
    style_ax(ax, win)
    save_panel(fig, "c_link.png")


# --- d) SA^3: pre-postprocess spatial agglomerative grouping, cell level ---

def panel_sa3(tess, win):
    fig, ax = square_fig()
    codes = tess["pre_morph"].astype("category").cat.codes
    ax.set_prop_cycle(None)
    tess.assign(_c=codes).plot(ax=ax, column="_c", cmap="tab20", edgecolor="white", linewidth=0.15)
    style_ax(ax, win)
    save_panel(fig, "d_sa3.png")


def panel_sa3_network(tess, win):
    """Real spatial contiguity graph (03_graphs/tessellation_graph.parquet)
    restricted to the window's own cells, coloured by the same pre-process
    SA^3 group as panel_sa3's cell map (identical categorical encoding on
    the same tess["pre_morph"] column, so the colours match)."""
    from matplotlib.collections import LineCollection

    base = REGIONS_DIR / REGION
    graph = pd.read_parquet(base / "03_graphs" / "tessellation_graph.parquet").reset_index()
    graph = graph[(graph["focal"] != graph["neighbor"]) & (graph["focal"] >= 0) & (graph["neighbor"] >= 0)]

    orig_ids = set(tess["orig_idx"])
    edges = graph[graph["focal"].isin(orig_ids) & graph["neighbor"].isin(orig_ids)]

    codes = tess["pre_morph"].astype("category").cat.codes
    code_by_id = pd.Series(codes.values, index=tess["orig_idx"].values)
    cent = tess.set_index("orig_idx").geometry.centroid
    vmax = max(codes.max(), 1)
    cmap = plt.get_cmap("tab20")

    fig, ax = square_fig()

    f_ids, n_ids = edges["focal"].to_numpy(), edges["neighbor"].to_numpy()
    fx, fy = cent.loc[f_ids].x.to_numpy(), cent.loc[f_ids].y.to_numpy()
    nx_, ny_ = cent.loc[n_ids].x.to_numpy(), cent.loc[n_ids].y.to_numpy()
    segs = np.stack([np.column_stack([fx, fy]), np.column_stack([nx_, ny_])], axis=1)
    edge_colors = cmap(code_by_id.loc[f_ids].to_numpy() / vmax)
    ax.add_collection(LineCollection(segs, colors=edge_colors, linewidths=0.18, alpha=0.6, zorder=1))

    xs, ys = cent.x.to_numpy(), cent.y.to_numpy()
    node_colors = code_by_id.reindex(cent.index).to_numpy()
    ax.scatter(xs, ys, c=node_colors, cmap="tab20", vmin=0, vmax=vmax, s=0.5, zorder=2, linewidths=0)

    style_ax(ax, win)
    save_panel(fig, "d_sa3_network.png")


# --- e) morphotopes: final coherent regions, dissolved to clean patches ---

def panel_morphotopes(tess, win):
    fig, ax = square_fig()
    dissolved = tess.dissolve(by="morph")
    codes = pd.Series(dissolved.index).astype("category").cat.codes.values
    dissolved = dissolved.reset_index()
    dissolved["_c"] = codes
    dissolved.plot(ax=ax, column="_c", cmap="tab20", edgecolor="white", linewidth=0.6)
    style_ax(ax, win)
    save_panel(fig, "e_morphotopes.png")


# --- f) morphotope-level morphometrics: real aggregated character profiles,
# as a small matrix (morphotopes x characters) -- same visual language as
# the poster's own feature_matrix_full.png, at diagram-panel scale ---

def panel_heatmap(buildings, tess):
    chars = ["sdbAre", "ssbCCo", "mtbNDi", "chm_cover"]
    agg = buildings.groupby("morph")[chars].mean()
    sicCAR = tess.groupby("morph")["sicCAR"].mean()
    agg = agg.join(sicCAR)
    chars = chars + ["sicCAR"]
    agg = agg.dropna()

    sizes = tess["morph"].value_counts()
    top_morphs = sizes[sizes.index.isin(agg.index)].sort_values(ascending=False).index[:6]
    agg = agg.loc[top_morphs]

    norm = (agg - agg.min()) / (agg.max() - agg.min() + 1e-9)

    fig, ax = plt.subplots(figsize=(2.3, 2.3), dpi=DPI)
    ax.imshow(norm.values, cmap="Greens", aspect="equal", vmin=0, vmax=1)

    labels = ["area", "compact.", "n. dist.", "canopy", "coverage"]
    ax.set_xticks(range(len(chars)))
    ax.set_xticklabels(labels, rotation=90, fontsize=6, color="#333333")
    ax.set_yticks(range(len(agg)))
    ax.set_yticklabels([f"M{i+1}" for i in range(len(agg))], fontsize=6, color="#333333")
    ax.set_xticks(np.arange(-0.5, len(chars), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(agg), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    save_panel(fig, "f_heatmap.png")


# --- g) morphotope linkage: real national dendrogram, viewer colours ---

def panel_dendrogram(dendro_data):
    dendro.build(
        data_path=dendro_data,
        level="level_3",
        gamma=1.4,
        min_r_frac=0.16,
        size_px=1200,
        out_path=OUT_DIR / "g_dendrogram.png",
        dpi=DPI,
        leaf_level="level_5",
        no_legend=True,
    )


# --- h) hierarchical urban fabric: real buildings, coloured by cluster,
# same neighbourhood window as a)-e), at 3 granularities ---

def panel_level_map(buildings, win, level, out_name):
    fig, ax = square_fig()
    sub = buildings.dropna(subset=[level])
    cats = sorted(sub[level].unique())
    if len(cats) <= len(dendro.BOLD_RAMP):
        color_map = {c: dendro.BOLD_RAMP[i] for i, c in enumerate(cats)}
    else:
        cmap = plt.get_cmap("tab20")
        color_map = {c: cmap(i % 20) for i, c in enumerate(cats)}
    sub.plot(ax=ax, color=sub[level].map(color_map), edgecolor="none")
    style_ax(ax, win)
    save_panel(fig, out_name)


# --- compose everything into one flow diagram, matching the draft mockup's
# a)-h) column layout but with real captures instead of generic icons ---

def _place_image(fig, path, rect):
    """rect = (left, bottom, width, height) in figure fraction."""
    ax = fig.add_axes(rect)
    im = mpimg.imread(OUT_DIR / path)
    ax.imshow(im)
    ax.axis("off")
    return ax


def _arrow(fig, x0, x1, y):
    fig.add_artist(FancyArrowPatch(
        (x0, y), (x1, y), transform=fig.transFigure,
        arrowstyle="-|>", mutation_scale=14, linewidth=1.3, color="#555555", zorder=10,
    ))


def compose_diagram():
    fig_w, fig_h = 22.0, 6.6
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor("white")

    fig.text(0.01, 0.975, "URBAN TAXONOMY FOR CANADA — METHODOLOGY OVERVIEW",
              fontsize=20, fontweight="bold", va="top", ha="left", color="#1a1a2e")
    fig.text(0.01, 0.935, "From raw spatial data to hierarchical urban types — real captures from the Winnipeg pilot region (CMA 602)",
              fontsize=11.5, va="top", ha="left", color="#555555")

    row_top, row_h = 0.16, 0.68

    # a) elements: 3 stacked small squares
    col_a_x, col_a_w = 0.015, 0.075
    for i, p in enumerate(["a_buildings.png", "a_streets.png", "a_tessellation.png"]):
        _place_image(fig, p, (col_a_x, row_top + (2 - i) * row_h / 3.35, col_a_w, row_h / 3.6))

    # b) morphometrics: 2 stacked squares (individual / contextual)
    col_b_x, col_b_w = 0.115, 0.075
    _place_image(fig, "b_individual.png", (col_b_x, row_top + row_h * 0.52, col_b_w, row_h * 0.46))
    _place_image(fig, "b_contextual.png", (col_b_x, row_top, col_b_w, row_h * 0.46))

    # c) link to buildings
    col_c_x, col_c_w = 0.215, 0.10
    _place_image(fig, "c_link.png", (col_c_x, row_top + row_h * 0.05, col_c_w, row_h * 0.9))

    # d) SA^3: cell map + contiguity-graph, same colours, stacked
    col_d_x, col_d_w = 0.335, 0.10
    _place_image(fig, "d_sa3_network.png", (col_d_x, row_top + row_h * 0.52, col_d_w, row_h * 0.46))
    _place_image(fig, "d_sa3.png", (col_d_x, row_top, col_d_w, row_h * 0.46))

    # e) morphotopes
    col_e_x, col_e_w = 0.455, 0.10
    _place_image(fig, "e_morphotopes.png", (col_e_x, row_top + row_h * 0.05, col_e_w, row_h * 0.9))

    # f) aggregated morphometrics (radar)
    col_f_x, col_f_w = 0.575, 0.10
    _place_image(fig, "f_heatmap.png", (col_f_x, row_top + row_h * 0.05, col_f_w, row_h * 0.9))

    # g) morphotope linkage (dendrogram)
    col_g_x, col_g_w = 0.695, 0.13
    _place_image(fig, "g_dendrogram.png", (col_g_x, row_top - 0.02, col_g_w, row_h + 0.04))

    # h) hierarchical urban fabric: 3 small city maps
    col_h_x, col_h_w = 0.865, 0.115
    labels_h = ["Level 1 (coarse)", "Level 3 (medium)", "Level 5 (fine)"]
    for i, (p, lbl) in enumerate(zip(["h_level1.png", "h_level3.png", "h_level5.png"], labels_h)):
        y = row_top + (2 - i) * row_h / 3.35
        _place_image(fig, p, (col_h_x, y, col_h_w, row_h / 3.9))
        fig.text(col_h_x + col_h_w / 2, y - 0.012, lbl, fontsize=8, va="top", ha="center", color="#444444")

    arrow_y = row_top + row_h / 2
    col_edges = [
        (col_a_x + col_a_w, col_b_x),
        (col_b_x + col_b_w, col_c_x),
        (col_c_x + col_c_w, col_d_x),
        (col_d_x + col_d_w, col_e_x),
        (col_e_x + col_e_w, col_f_x),
        (col_f_x + col_f_w, col_g_x),
        (col_g_x + col_g_w, col_h_x),
    ]
    for x0, x1 in col_edges:
        _arrow(fig, x0 + 0.003, x1 - 0.003, arrow_y)

    # bottom labelled strip, matching the mockup's a)-h) footer bar
    footer_y = 0.075
    fig.add_artist(plt.Line2D([0.01, 0.995], [footer_y + 0.03, footer_y + 0.03],
                               transform=fig.transFigure, color="#1a1a2e", linewidth=1.0))
    cols = [
        ("a) elements", col_a_x, "Real footprints, streets, tessellation"),
        ("b) morphometrics", col_b_x, "Individual + contextual, per building"),
        ("c) link to buildings", col_c_x, "Metrics joined to each footprint"),
        ("d) SA³", col_d_x, "Spatial agglomerative clustering"),
        ("e) morphotopes", col_e_x, "Coherent, dissolved regions"),
        ("f) morphometrics", col_f_x, "Aggregated per morphotope"),
        ("g) morphotope linkage", col_g_x, "Ward clustering (national)"),
        ("h) hierarchical urban fabric", col_h_x, "Types at multiple levels"),
    ]
    for title, x, sub in cols:
        fig.text(x, footer_y, title, fontsize=9, fontweight="bold", va="top", ha="left", color="#1a1a2e")
        fig.text(x, footer_y - 0.045, sub, fontsize=7, va="top", ha="left", color="#666666")

    out_path = OUT_DIR.parent / "methodology_overview.png"
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)
    print(f"saved {out_path}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dendro-data",
        default="../urban_taxonomy_viewer/public/data/global_cluster_summary.json",
    )
    args = p.parse_args()

    print("loading window data...")
    buildings, roads, tess, tess_full, win = load_window_data()
    print(f"  buildings={len(buildings)} roads={len(roads)} cells(window)={len(tess)} cells(region)={len(tess_full)}")

    panel_buildings(buildings, win)
    panel_streets(roads, win)
    panel_tessellation(tess, win)

    panel_metric(buildings, win, "sdbAre", "Blues", "b_individual.png")
    panel_metric(buildings, win, "chm_cover", "Oranges", "b_contextual.png")

    panel_link(buildings, tess, win)
    panel_sa3(tess, win)
    panel_sa3_network(tess, win)
    panel_morphotopes(tess, win)
    panel_heatmap(buildings, tess)

    panel_dendrogram(Path(args.dendro_data))

    panel_level_map(buildings, win, "level_1", "h_level1.png")
    panel_level_map(buildings, win, "level_3", "h_level3.png")
    panel_level_map(buildings, win, "level_5", "h_level5.png")

    compose_diagram()


if __name__ == "__main__":
    main()
