"""Generate D3-compatible hierarchy tree JSON from the scipy linkage matrix + cluster mapping."""
import numpy as np
import pandas as pd
import json
from pathlib import Path
from scipy.cluster.hierarchy import to_tree

OUT = Path("outputs/11_exports")

Z = np.load("outputs/09_hierarchy/linkage_matrix.npy")
cm = pd.read_parquet("outputs/09_hierarchy/cluster_mapping.parquet")

level_cols = sorted([c for c in cm.columns if c.startswith("level_")])

def build_d3_tree(node):
    if node.is_leaf():
        morph_id = cm.index[node.id]
        labels = {col: int(cm.loc[morph_id, col]) for col in level_cols}
        return {
            "id": morph_id,
            "leaf": True,
            "distance": 0,
            "count": 1,
            **labels,
        }
    return {
        "id": f"n{node.id}",
        "leaf": False,
        "distance": round(float(node.dist), 3),
        "count": int(node.count),
        "children": [build_d3_tree(node.left), build_d3_tree(node.right)],
    }

root, _ = to_tree(Z, rd=True)
tree = build_d3_tree(root)

# Also build a summary tree (only first 4 levels of branching for the viz)
def prune_tree(node, max_depth, depth=0):
    if node.get("leaf") or depth >= max_depth:
        labels = {k: v for k, v in node.items() if k.startswith("level_")}
        if not labels and "children" in node:
            # Aggregate: collect all leaf level values
            leaves = []
            stack = [node]
            while stack:
                n = stack.pop()
                if n.get("leaf") or "children" not in n:
                    leaves.append(n)
                else:
                    stack.extend(n["children"])
            for col in level_cols:
                vals = [l.get(col) for l in leaves if l.get(col) is not None]
                if vals:
                    labels[col] = max(set(vals), key=vals.count)
        return {
            "id": node["id"],
            "leaf": True,
            "distance": node.get("distance", 0),
            "count": node.get("count", 1),
            **labels,
        }
    if "children" in node:
        return {
            "id": node["id"],
            "leaf": False,
            "distance": node.get("distance", 0),
            "count": node.get("count", 1),
            "children": [prune_tree(c, max_depth, depth + 1) for c in node["children"]],
        }
    return node

# Pruned trees at different depths for visualization
trees = {}
for depth in [3, 5, 7, 10, 15]:
    trees[f"depth_{depth}"] = prune_tree(tree, depth)

# Cluster-level summary: for each level, list of clusters with their count
cluster_summary = {}
for col in level_cols:
    counts = cm[col].value_counts().sort_index()
    cluster_summary[col] = [
        {"cluster": int(k), "morphotopes": int(v)} for k, v in counts.items()
    ]

output = {
    "tree": trees["depth_10"],
    "trees": trees,
    "cluster_summary": cluster_summary,
    "levels": level_cols,
    "total_morphotopes": len(cm),
}

with open(OUT / "hierarchy_tree.json", "w") as f:
    json.dump(output, f)

print(f"Tree JSON: {Path(OUT / 'hierarchy_tree.json').stat().st_size / 1024:.0f} KB")
print(f"Levels: {level_cols}")
for col in level_cols:
    print(f"  {col}: {cm[col].nunique()} clusters")
