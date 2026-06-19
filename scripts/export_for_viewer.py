"""
Export pipeline outputs for the web viewer app.
Reusable for any city — just change the paths at the top.

Usage:
  cd c:\urban-form\urban_taxonomy
  .venv\Scripts\python.exe scripts\export_for_viewer.py

Outputs a simplified morphotopes GeoJSON + taxonomy JSON
to the viewer's public/data/ directory.
"""

import geopandas as gpd
import json
import os
import shutil
from pathlib import Path

# ── CONFIGURATION (change these for a different city) ─────────────────────
PIPELINE_OUTPUT = Path("outputs/11_exports")
VIEWER_DATA_DIR = Path("../urban_taxonomy_viewer/public/data")
CITY_NAME = "winnipeg"
SIMPLIFY_TOLERANCE_M = 1.0  # metres in projected CRS
PROJECTED_CRS = "EPSG:3978"  # NAD83 Canada Atlas Lambert
# ──────────────────────────────────────────────────────────────────────────

VIEWER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# 1. Morphotopes GeoJSON (simplified for web)
src = PIPELINE_OUTPUT / f"{CITY_NAME}_morphotopes.geojson"
if src.exists():
    print(f"Loading {src}...")
    gdf = gpd.read_file(src)

    gdf_proj = gdf.to_crs(PROJECTED_CRS)
    gdf_proj["geometry"] = gdf_proj.geometry.simplify(SIMPLIFY_TOLERANCE_M)
    gdf_simple = gdf_proj.to_crs("EPSG:4326")

    keep = ["morph", "final", "building_count",
            "level_1", "level_2", "level_3", "level_4",
            "level_5", "level_6", "level_7", "geometry"]
    gdf_simple = gdf_simple[[c for c in keep if c in gdf_simple.columns]]

    for col in gdf_simple.columns:
        if col != "geometry" and gdf_simple[col].dtype == "float64":
            gdf_simple[col] = gdf_simple[col].fillna(-1).astype(int)

    out = VIEWER_DATA_DIR / "morphotopes.geojson"
    gdf_simple.to_file(out, driver="GeoJSON", coordinate_precision=5)

    orig_mb = os.path.getsize(src) / 1024 / 1024
    web_mb = os.path.getsize(out) / 1024 / 1024
    print(f"  {orig_mb:.1f} MB -> {web_mb:.1f} MB ({len(gdf):,} features)")
else:
    print(f"WARNING: {src} not found")

# 2. Taxonomy hierarchy JSON
src_json = PIPELINE_OUTPUT / "taxonomy_hierarchy.json"
if src_json.exists():
    shutil.copy(src_json, VIEWER_DATA_DIR / "taxonomy_hierarchy.json")
    print(f"Copied {src_json.name}")

print(f"\nDone. Viewer data in {VIEWER_DATA_DIR.resolve()}")
