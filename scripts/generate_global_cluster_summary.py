"""
Generate a small, region-independent cluster summary for the viewer's
legend/symbology, from the single global taxonomy clustering
(outputs_canada_cma_ca/09_hierarchy/cluster_mapping.parquet).

level_1..level_7 cluster ids mean the same taxonomy class in every region
(phase 9 clusters all regions' morphotopes together, once), so this doesn't
need to be region-specific and doesn't require the much heavier per-region
dendrogram (hierarchy_tree.json, still not generated for the CMA/CA data).
This is just: for each level, how many morphotopes are in each cluster, plus
which level_(N+1) clusters each level_N cluster splits into (each level
strictly refines the previous one -- level_3 cluster 2 always has the same
level_2/level_1 ancestors for every row), which the viewer's future
"subdivide just this one cluster" drill-down will need.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\generate_global_cluster_summary.py

The no-CHM run is a genuinely separate clustering pass (its own
cluster_mapping.parquet/linkage), so its taxonomy differs from the CHM run's
-- generate its own summary into a separate file for the Hierarchy Tree to
pick up when that dataset is selected (the legend/map-coloring stays on the
CHM summary always, by design, so a color keeps meaning the same cluster
id regardless of which dataset is shown):
    .venv\\Scripts\\python.exe scripts\\generate_global_cluster_summary.py ^
        --cluster-mapping outputs_canada_cma_ca_nochm\\09_hierarchy\\cluster_mapping.parquet ^
        --output-path ..\\urban_taxonomy_viewer\\public\\data\\global_cluster_summary_nochm.json
"""

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CLUSTER_MAPPING = ROOT / "outputs_canada_cma_ca" / "09_hierarchy" / "cluster_mapping.parquet"
DEFAULT_OUT_PATH = ROOT.parent / "urban_taxonomy_viewer" / "public" / "data" / "global_cluster_summary.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cluster-mapping", default=str(DEFAULT_CLUSTER_MAPPING))
    parser.add_argument("--output-path", default=str(DEFAULT_OUT_PATH))
    args = parser.parse_args()

    cluster_mapping = Path(args.cluster_mapping)
    out_path = Path(args.output_path)

    cm = pd.read_parquet(cluster_mapping)
    level_cols = sorted([c for c in cm.columns if c.startswith("level_")])
    print(f"Loaded {len(cm):,} morphotopes, levels: {level_cols}")

    cluster_summary = {}
    for col in level_cols:
        counts = cm[col].value_counts().sort_index()
        cluster_summary[col] = [
            {"cluster": int(k), "morphotopes": int(v)} for k, v in counts.items()
        ]
        print(f"  {col}: {cm[col].nunique()} clusters")

    # children_map[level_N][cluster_id] -> sorted list of level_(N+1) cluster
    # ids that occur among rows with that level_N value.
    children_map = {}
    for i in range(len(level_cols) - 1):
        parent_col, child_col = level_cols[i], level_cols[i + 1]
        grouped = cm.groupby(parent_col)[child_col].unique()
        children_map[parent_col] = {
            str(int(parent)): sorted(int(c) for c in children)
            for parent, children in grouped.items()
        }

    output = {
        "levels": level_cols,
        "cluster_summary": cluster_summary,
        "children_map": children_map,
        "total_morphotopes": len(cm),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output), encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
