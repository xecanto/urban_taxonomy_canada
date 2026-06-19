"""Convert exports to FlatGeobuf for streaming web display."""
import geopandas as gpd
import pandas as pd
import os
from pathlib import Path

out = Path("outputs/11_exports")

print("Converting morphotopes to FlatGeobuf...")
morph = gpd.read_file(out / "winnipeg_morphotopes.geojson")
for col in morph.select_dtypes("float64").columns:
    if col != "geometry":
        morph[col] = morph[col].fillna(-1).astype(int)
morph.to_file(out / "morphotopes.fgb", driver="FlatGeobuf")
print(f"  {os.path.getsize(out / 'morphotopes.fgb') / 1024 / 1024:.1f} MB")

print("Converting buildings to FlatGeobuf...")
buildings = gpd.read_file("outputs/01_preprocessed/buildings.gpkg")
clusters = pd.read_parquet("outputs/09_hierarchy/tessellation_clusters_final.parquet")
morph_labels = pd.read_parquet(
    "outputs/06_morphotopes/tessellation_labels_postprocessed.parquet"
)["morphotope_label"]

bldg = buildings.to_crs("EPSG:4326")
for col in clusters.columns:
    bldg[col] = clusters[col].reindex(bldg.index)

keep = ["HEIGHT", "BLDG_POP", "final", "level_1", "level_2", "level_3",
        "level_4", "level_5", "level_6", "level_7", "geometry"]
bldg = bldg[[c for c in keep if c in bldg.columns]]
for col in bldg.select_dtypes("float64").columns:
    if col != "geometry":
        bldg[col] = bldg[col].fillna(-1).round(2)

bldg.to_file(out / "buildings.fgb", driver="FlatGeobuf")
print(f"  {os.path.getsize(out / 'buildings.fgb') / 1024 / 1024:.1f} MB")
print("Done.")
