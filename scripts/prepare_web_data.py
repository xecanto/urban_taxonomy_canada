"""Prepare web-optimized GeoJSON from pipeline exports."""
import geopandas as gpd
import json
import os
from pathlib import Path

SRC = Path("outputs/11_exports")
OUT = Path("outputs/11_exports")

print("Loading morphotopes...")
gdf = gpd.read_file(SRC / "winnipeg_morphotopes.geojson")
print(f"  {len(gdf):,} features")

# Simplify in projected CRS (1m tolerance — invisible at city scale)
gdf_proj = gdf.to_crs("EPSG:3978")
gdf_proj["geometry"] = gdf_proj.geometry.simplify(1.0)
gdf_simple = gdf_proj.to_crs("EPSG:4326")

# Keep only needed columns
keep = ["morph", "final", "building_count",
        "level_1", "level_2", "level_3", "level_4",
        "level_5", "level_6", "level_7", "geometry"]
gdf_simple = gdf_simple[[c for c in keep if c in gdf_simple.columns]]

# Convert float columns to int (smaller JSON)
for col in gdf_simple.columns:
    if col != "geometry" and gdf_simple[col].dtype == "float64":
        gdf_simple[col] = gdf_simple[col].fillna(-1).astype(int)

out_path = OUT / "morphotopes_web.geojson"
gdf_simple.to_file(out_path, driver="GeoJSON", coordinate_precision=5)

orig_size = os.path.getsize(SRC / "winnipeg_morphotopes.geojson") / 1024 / 1024
web_size = os.path.getsize(out_path) / 1024 / 1024
print(f"  Original: {orig_size:.1f} MB")
print(f"  Web:      {web_size:.1f} MB ({100*web_size/orig_size:.0f}%)")
