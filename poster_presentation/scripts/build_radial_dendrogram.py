"""
Build the central radial dendrogram exactly as the interactive viewer does
(same data file, same D3 layout math), reimplemented in Python so it can be
tuned (leg lengths, etc.) and exported as a clean standalone image for the
poster.

Ported 1:1 from c:/urban-form/urban_taxonomy_viewer/src/components/HierarchyView.tsx
+ src/utils/frontier.ts (buildTaxonomyTree) + src/utils/colors.ts (Bold ramp):
  - d3.hierarchy over the SAME public/data/global_cluster_summary.json the
    live app fetches (or the _nochm variant) -- not the per-morphotope
    linkage matrix; this is the app's own small global-summary tree
    (level_1..level_7, max ~254 nodes).
  - d3.cluster() layout: leaves evenly spaced by angle, y = depth / max_depth.
  - Depth -> radius remapping via the app's own easeOutPow(t, 2.2) power-ease
    (root-adjacent splits get more radial room, fine branching compresses
    near the leaves), with the same MIN_R inner-hub trick.
  - Links drawn as the app's own "radial leg then circumferential arc" path
    shape, not straight chords.
  - Colors: the app's default "Bold" 20-colour categorical ramp, indexed by
    each node's level_3 ancestor id (nodes shallower than level_3 render
    grey, matching the live app).

Added beyond what the live widget draws (does not have this built in):
  - A bold-legend panel (colour swatch + bold label per level_3 cluster).

Usage:
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_dendrogram.py
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_dendrogram.py --gamma 1.6 --min-r-frac 0.12
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_dendrogram.py --data ../urban_taxonomy_viewer/public/data/global_cluster_summary_nochm.json --out dendrogram_nochm.png
"""

import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Exact same 20-colour "Bold" categorical ramp as
# urban_taxonomy_viewer/src/utils/colors.ts CUSTOM_RAMPS.Bold
BOLD_RAMP = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
]
GREY = "#111111"  # trunk colour for levels without a level_3 ancestor yet -- black, not grey, per feedback


def ease_out_pow(t: float, gamma: float) -> float:
    return 1 - (1 - t) ** gamma


def angle_delta(a: float, b: float) -> float:
    d = (b - a) % (2 * math.pi)
    if d > math.pi:
        d -= 2 * math.pi
    if d < -math.pi:
        d += 2 * math.pi
    return d


def point_radial(angle: float, radius: float):
    # d3.pointRadial(angle, radius): angle 0 = up (12 o'clock), clockwise.
    return radius * math.sin(angle), radius * math.cos(angle)


class Node:
    __slots__ = ("id", "cluster_by_level", "count", "children", "parent", "depth", "x", "y")

    def __init__(self, node_id, cluster_by_level, count):
        self.id = node_id
        self.cluster_by_level = cluster_by_level  # dict level_name -> cluster id
        self.count = count
        self.children: list["Node"] = []
        self.parent: "Node | None" = None
        self.depth = 0
        self.x = 0.0  # angle fraction, filled in later
        self.y = 0.0  # normalized depth [0,1]


def build_tree(summary: dict, leaf_level: str | None = None) -> Node:
    """Port of buildTaxonomyTree() in src/utils/frontier.ts.

    leaf_level: if given, recursion stops at this level -- nodes there are
    treated as leaves even though children_map has finer children beyond it.
    Used to build a tree with the SAME leaf count/order as the rings wheel
    (level_5, 32 leaves) instead of always walking to the full level_7 (128).
    """
    levels = summary["levels"]
    stop_at = levels.index(leaf_level) if leaf_level else len(levels) - 1

    def build_node(level, cluster, ancestors, depth):
        li = levels.index(level)
        next_level = levels[li + 1] if li + 1 < len(levels) else None
        here = {**ancestors, level: cluster}
        child_ids = []
        if next_level is not None and li < stop_at:
            child_ids = summary["children_map"].get(level, {}).get(str(cluster), [])
        count = next(
            (s["morphotopes"] for s in summary["cluster_summary"].get(level, []) if s["cluster"] == cluster),
            0,
        )
        node = Node(f"{level}_{cluster}", here, count)
        node.depth = depth
        if child_ids:
            for c in child_ids:
                child = build_node(next_level, c, here, depth + 1)
                child.parent = node
                node.children.append(child)
        return node

    base_level = levels[0]
    base_clusters = sorted(s["cluster"] for s in summary["cluster_summary"].get(base_level, []))
    root = Node("root", {}, summary["total_morphotopes"])
    root.depth = 0
    for c in base_clusters:
        child = build_node(base_level, c, {}, 1)
        child.parent = root
        root.children.append(child)
    return root


def assign_cluster_layout(root: Node, max_depth: int):
    """Port of d3.cluster().size([2*PI, 1]).separation(() => 1)."""
    leaves = []

    def collect_leaves(n: Node):
        if not n.children:
            leaves.append(n)
        else:
            for c in n.children:
                collect_leaves(c)

    collect_leaves(root)
    n_leaves = len(leaves)
    for i, leaf in enumerate(leaves):
        leaf.x = (i + 0.5) / n_leaves  # fraction of full circle

    def assign_parent_x(n: Node):
        for c in n.children:
            assign_parent_x(c)
        if n.children:
            n.x = (n.children[0].x + n.children[-1].x) / 2

    assign_parent_x(root)

    def assign_y(n: Node):
        n.y = n.depth / max_depth
        for c in n.children:
            assign_y(c)

    assign_y(root)


def get_cluster_id(n: Node, level: str):
    return n.cluster_by_level.get(level, -1)


def get_color(n: Node, level: str, cluster_ids: list):
    cid = get_cluster_id(n, level)
    if cid not in cluster_ids:
        return GREY
    idx = cluster_ids.index(cid)
    return BOLD_RAMP[idx % len(BOLD_RAMP)]


def build(
    data_path: Path, level: str, gamma: float, min_r_frac: float,
    size_px: int, out_path: Path, dpi: int = 150,
    leaf_level: str | None = None, no_legend: bool = False, leaf_order_out: Path | None = None,
):
    with open(data_path, encoding="utf-8") as f:
        summary = json.load(f)

    levels = summary["levels"]
    root = build_tree(summary, leaf_level=leaf_level)
    max_depth = (levels.index(leaf_level) + 1) if leaf_level else len(levels)  # root(0) .. leaf_level
    assign_cluster_layout(root, max_depth)

    cluster_ids = sorted(s["cluster"] for s in summary["cluster_summary"].get(level, []))

    if leaf_order_out is not None:
        leaves_list = []

        def collect(n: Node):
            if not n.children:
                leaves_list.append(n)
            else:
                for c in n.children:
                    collect(c)

        collect(root)
        leaf_level_name = leaf_level or levels[-1]
        order = [leaf.cluster_by_level[leaf_level_name] for leaf in leaves_list]
        leaf_order_out.parent.mkdir(parents=True, exist_ok=True)
        with open(leaf_order_out, "w", encoding="utf-8") as f:
            json.dump({"level": leaf_level_name, "order": order}, f)
        print(f"saved leaf order ({len(order)} leaves) to {leaf_order_out}")

    R = 1.0
    MIN_R = min_r_frac * R

    def radial_r(t):
        return MIN_R + ease_out_pow(t, gamma) * (R - MIN_R)

    def node_pos(n: Node):
        angle = n.x * 2 * math.pi
        r = radial_r(n.y)
        px, py = point_radial(angle, r)
        return px, py

    fig_size = size_px / dpi
    legend_w = 0.0 if no_legend else fig_size * 0.42
    fig = plt.figure(figsize=(fig_size + legend_w, fig_size), dpi=dpi)
    if no_legend:
        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    else:
        ax = fig.add_axes([0.02, 0.01, fig_size / (fig_size + legend_w) - 0.02, 0.89])
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)
    ax.set_aspect("equal")
    ax.axis("off")

    # --- links: radial leg then circumferential arc, same as the app ---
    def draw_links(n: Node):
        for c in n.children:
            s_rad = radial_r(n.y)
            t_angle = c.x * 2 * math.pi
            s_angle = n.x * 2 * math.pi
            bx, by = point_radial(t_angle, s_rad)
            cx_, cy_ = node_pos(c)
            px, py = node_pos(n)

            delta = angle_delta(t_angle, s_angle)
            n_steps = max(2, int(abs(delta) / (2 * math.pi) * 200) + 2)
            arc_pts = []
            for i in range(n_steps + 1):
                a = t_angle + delta * (i / n_steps)
                arc_pts.append(point_radial(a, s_rad))

            xs = [cx_, bx] + [p[0] for p in arc_pts] + [px]
            ys = [cy_, by] + [p[1] for p in arc_pts] + [py]
            color = get_color(c, level, cluster_ids)
            ax.plot(xs, ys, color=color, linewidth=1.1, alpha=0.75, zorder=3, solid_capstyle="round")
            draw_links(c)

    draw_links(root)

    # --- nodes ---
    def draw_nodes(n: Node):
        x, y = node_pos(n)
        is_leaf = not n.children
        color = get_color(n, level, cluster_ids)
        size = 8 if is_leaf else 5
        alpha = 0.95 if is_leaf else 0.55
        ax.scatter([x], [y], s=size, color=color, alpha=alpha, zorder=4, linewidths=0)
        for c in n.children:
            draw_nodes(c)

    draw_nodes(root)

    if not no_legend:
        fig.text(
            0.015, 0.965,
            f"Taxonomy hierarchy ({level} colouring), levels 1-{max_depth}\n"
            f"{summary['total_morphotopes']:,} morphotopes -- ported from the live viewer's own D3 layout",
            fontsize=11, ha="left", va="top",
        )

        # --- bold legend ---
        lax = fig.add_axes([fig_size / (fig_size + legend_w) + 0.01, 0.05, legend_w / (fig_size + legend_w) - 0.05, 0.9])
        lax.axis("off")
        lax.set_title(f"Clusters ({level})", fontsize=12, fontweight="bold", loc="left", pad=6)

        counts = {s["cluster"]: s["morphotopes"] for s in summary["cluster_summary"].get(level, [])}
        n_items = len(cluster_ids)
        for i, cid in enumerate(cluster_ids):
            y = 1 - (i + 0.7) / (n_items + 0.5)
            color = BOLD_RAMP[i % len(BOLD_RAMP)]
            lax.add_patch(plt.Rectangle((0.02, y - 0.018), 0.09, 0.036, color=color, transform=lax.transAxes))
            lax.text(0.15, y, f"Cluster {cid}", fontsize=11, fontweight="bold",
                      va="center", transform=lax.transAxes, color="#222222")
            lax.text(0.98, y, f"{counts.get(cid, 0):,}", fontsize=10, fontweight="bold",
                      va="center", ha="right", transform=lax.transAxes, color="#555555")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if no_legend:
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
        fig.savefig(out_path, transparent=True)
        svg_path = out_path.with_suffix(".svg")
        fig.savefig(svg_path, transparent=True)
    else:
        fig.savefig(out_path, facecolor="white")
        svg_path = out_path.with_suffix(".svg")
        fig.savefig(svg_path, facecolor="white")
    plt.close(fig)
    print(f"saved {out_path} and {svg_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="../urban_taxonomy_viewer/public/data/global_cluster_summary.json",
                    help="Path to the viewer's global_cluster_summary(.json|_nochm.json)")
    p.add_argument("--level", default="level_3", help="Which level colours the tree (level_1..level_7)")
    p.add_argument("--gamma", type=float, default=2.2, help="Depth easing power (app default 2.2) -- lower = longer outer legs")
    p.add_argument("--min-r-frac", type=float, default=0.2, help="Inner hub radius as a fraction of outer radius (app default ~0.2)")
    p.add_argument("--size-px", type=int, default=1600, help="Width of the dendrogram panel in px at --dpi")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--out", default="poster_presentation/assets/figures/dendrogram_center.png")
    p.add_argument("--leaf-level", default=None,
                    help="Truncate the tree so this level's clusters are the leaves (e.g. level_5, "
                         "to match the 32-leaf rings wheel) instead of walking to the full level_7 (128)")
    p.add_argument("--no-legend", action="store_true",
                    help="Square, transparent-background, dendrogram-only output (no title/legend panel) -- "
                         "for compositing into radial_taxonomy_rings.png's open centre")
    p.add_argument("--leaf-order-out", default=None,
                    help="Also save the leaf cluster-id order (DFS, same order as drawn) as JSON here, "
                         "so build_radial_rings.py can be given the identical order for angular alignment")
    args = p.parse_args()

    build(
        Path(args.data), args.level, args.gamma, args.min_r_frac,
        args.size_px, Path(args.out), args.dpi,
        leaf_level=args.leaf_level, no_legend=args.no_legend,
        leaf_order_out=Path(args.leaf_order_out) if args.leaf_order_out else None,
    )
