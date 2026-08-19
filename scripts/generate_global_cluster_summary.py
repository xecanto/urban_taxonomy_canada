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
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLUSTER_MAPPING = ROOT / "outputs_canada_cma_ca" / "09_hierarchy" / "cluster_mapping.parquet"
OUT_PATH = ROOT.parent / "urban_taxonomy_viewer" / "public" / "data" / "global_cluster_summary.json"


def main():
    cm = pd.read_parquet(CLUSTER_MAPPING)
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

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output), encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
