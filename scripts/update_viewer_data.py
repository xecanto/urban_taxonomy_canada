r"""
Regenerate viewer data with BOTH clustering approaches:
  - pct_level_1..7  : old percentile-based distance cutoffs
  - fc_level_1..7   : current fixed-count cluster targets

Reads the linkage matrix to recompute percentile levels, and reads the
current cluster_mapping for fixed-count levels.  Exports simplified
FGB + hierarchy tree JSON to the viewer.

Usage:
  cd c:\urban-form\urban_taxonomy
  .venv\Scripts\python.exe scripts/update_viewer_data.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
import geopandas as gpd
import json
from scipy.cluster.hierarchy import fcluster, to_tree
from pathlib import Path

VIEWER_DATA = Path("../urban_taxonomy_viewer/public/data")
VIEWER_DATA.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════
# 1.  LOAD & RECOMPUTE BOTH APPROACHES
# ═══════════════════════════════════════════════════════════
print("═" * 60)
print("Loading linkage matrix & cluster mappings …")
Z = np.load("outputs/09_hierarchy/linkage_matrix.npy")
cm_new = pd.read_parquet("outputs/09_hierarchy/cluster_mapping.parquet")
morph_labels = pd.read_parquet(
    "outputs/06_morphotopes/tessellation_labels_postprocessed.parquet"
)["morphotope_label"]

# ── Recompute percentile-based levels ─────────────────────
distances = Z[:, 2]
PERCENTILES = [90, 93, 95, 97, 98, 99, 99.5]
cm_pct = pd.DataFrame(index=cm_new.index)
for i, p in enumerate(PERCENTILES):
    cutoff = float(np.percentile(distances, p))
    labels = fcluster(Z, t=cutoff, criterion="distance")
    cm_pct[f"pct_level_{i + 1}"] = labels.astype(int)

# ── Rename current fixed-count levels ─────────────────────
cm_fc = cm_new.copy()
cm_fc.columns = [f"fc_{c}" for c in cm_fc.columns]
for c in cm_fc.columns:
    cm_fc[c] = cm_fc[c].astype(int)

pct_cols = sorted(cm_pct.columns)
fc_cols  = sorted(cm_fc.columns)

print("\nPercentile-based levels:")
for c in pct_cols:
    print(f"  {c}: {cm_pct[c].nunique()} clusters")
print("Fixed-count levels:")
for c in fc_cols:
    print(f"  {c}: {cm_fc[c].nunique()} clusters")

# ═══════════════════════════════════════════════════════════
# 2.  MORPHOTOPES  →  FlatGeobuf  (no simplification)
# ═══════════════════════════════════════════════════════════
print("\n" + "═" * 60)
print("Exporting morphotopes (1 m simplification) …")
morph = gpd.read_file("outputs/11_exports/winnipeg_morphotopes.geojson")

# 1-metre simplification in projected CRS
morph_proj = morph.to_crs("EPSG:3978")
morph_proj["geometry"] = morph_proj.geometry.simplify(1.0)
morph = morph_proj.to_crs("EPSG:4326")

# Drop any existing level_* columns (they come from the notebook re-run)
drop = [c for c in morph.columns if c.startswith("level_")]
morph = morph.drop(columns=drop, errors="ignore")

# Add both approaches
for c in pct_cols:
    morph[c] = morph["morph"].map(cm_pct[c].to_dict()).fillna(-1).astype(int)
for c in fc_cols:
    col_orig = c.replace("fc_", "")
    morph[c] = morph["morph"].map(cm_new[col_orig].to_dict()).fillna(-1).astype(int)

morph.to_file(VIEWER_DATA / "morphotopes.fgb", driver="FlatGeobuf")
sz = (VIEWER_DATA / "morphotopes.fgb").stat().st_size / 1024 / 1024
print(f"  {len(morph):,} features  →  {sz:.1f} MB")
print(f"  Columns: {[c for c in morph.columns if c != 'geometry']}")

# ═══════════════════════════════════════════════════════════
# 3.  BUILDINGS  →  FlatGeobuf
# ═══════════════════════════════════════════════════════════
print("\n" + "═" * 60)
print("Exporting buildings …")
bldg = gpd.read_file("outputs/01_preprocessed/buildings.gpkg")
bldg = bldg.to_crs("EPSG:4326")

# Map both approaches via morphotope labels → building index
for c in pct_cols:
    bldg[c] = morph_labels.map(cm_pct[c].to_dict()).reindex(bldg.index).fillna(-1).astype(int)
for c in fc_cols:
    col_orig = c.replace("fc_", "")
    bldg[c] = morph_labels.map(cm_new[col_orig].to_dict()).reindex(bldg.index).fillna(-1).astype(int)

keep = ["HEIGHT", "BLDG_POP"] + pct_cols + fc_cols + ["geometry"]
bldg = bldg[[c for c in keep if c in bldg.columns]]
for c in bldg.select_dtypes("float64").columns:
    if c != "geometry":
        bldg[c] = bldg[c].fillna(-1).round(2)

bldg.to_file(VIEWER_DATA / "buildings.fgb", driver="FlatGeobuf")
sz = (VIEWER_DATA / "buildings.fgb").stat().st_size / 1024 / 1024
print(f"  {len(bldg):,} features  →  {sz:.1f} MB")

# ═══════════════════════════════════════════════════════════
# 4.  HIERARCHY TREE  JSON  (both level sets on every leaf)
# ═══════════════════════════════════════════════════════════
print("\n" + "═" * 60)
print("Generating hierarchy tree JSON …")

all_level_cols = pct_cols + fc_cols

def build_d3_tree(node):
    if node.is_leaf():
        mid = cm_new.index[node.id]
        labels = {}
        for c in pct_cols:
            labels[c] = int(cm_pct.loc[mid, c])
        for c in fc_cols:
            col_orig = c.replace("fc_", "")
            labels[c] = int(cm_new.loc[mid, col_orig])
        return {"id": mid, "leaf": True, "distance": 0, "count": 1, **labels}
    return {
        "id": f"n{node.id}", "leaf": False,
        "distance": round(float(node.dist), 3),
        "count": int(node.count),
        "children": [build_d3_tree(node.left), build_d3_tree(node.right)],
    }

root, _ = to_tree(Z, rd=True)
full_tree = build_d3_tree(root)

def prune_tree(node, max_depth, depth=0):
    if node.get("leaf") or depth >= max_depth:
        labels = {k: v for k, v in node.items() if "level_" in k}
        if not labels and "children" in node:
            leaves = []
            stack = [node]
            while stack:
                n = stack.pop()
                if n.get("leaf") or "children" not in n:
                    leaves.append(n)
                else:
                    stack.extend(n["children"])
            for col in all_level_cols:
                vals = [l.get(col) for l in leaves if l.get(col) is not None]
                if vals:
                    labels[col] = max(set(vals), key=vals.count)
        return {
            "id": node["id"], "leaf": True,
            "distance": node.get("distance", 0),
            "count": node.get("count", 1), **labels,
        }
    if "children" in node:
        return {
            "id": node["id"], "leaf": False,
            "distance": node.get("distance", 0),
            "count": node.get("count", 1),
            "children": [prune_tree(c, max_depth, depth + 1) for c in node["children"]],
        }
    return node

trees = {f"depth_{d}": prune_tree(full_tree, d) for d in [3, 5, 7, 10, 15]}

cluster_summary = {}
for c in pct_cols:
    counts = cm_pct[c].value_counts().sort_index()
    cluster_summary[c] = [{"cluster": int(k), "morphotopes": int(v)} for k, v in counts.items()]
for c in fc_cols:
    col_orig = c.replace("fc_", "")
    counts = cm_new[col_orig].value_counts().sort_index()
    cluster_summary[c] = [{"cluster": int(k), "morphotopes": int(v)} for k, v in counts.items()]

trees["full"] = full_tree
output = {
    "tree": full_tree,
    "trees": trees,
    "cluster_summary": cluster_summary,
    "levels": all_level_cols,
    "total_morphotopes": len(cm_new),
}
with open(VIEWER_DATA / "hierarchy_tree.json", "w") as f:
    json.dump(output, f)
print(f"  {(VIEWER_DATA / 'hierarchy_tree.json').stat().st_size / 1024:.0f} KB")

# ═══════════════════════════════════════════════════════════
# 5.  TAXONOMY HIERARCHY  JSON
# ═══════════════════════════════════════════════════════════
tax = []
for c in all_level_cols:
    src = cm_pct if c in pct_cols else cm_new
    col = c if c in pct_cols else c.replace("fc_", "")
    level_data = morph.groupby(c).agg(
        count=("morph", "count"),
        buildings=("building_count", "sum"),
    ).reset_index()
    tax.append({
        "level": c,
        "clusters": level_data.rename(columns={c: c}).to_dict(orient="records"),
    })

with open(VIEWER_DATA / "taxonomy_hierarchy.json", "w") as f:
    json.dump(tax, f, indent=2, default=str)

print("\n" + "═" * 60)
print("DONE.  Viewer data at:", VIEWER_DATA.resolve())
print(f"  Percentile levels: {pct_cols}")
print(f"  Fixed-count levels: {fc_cols}")
