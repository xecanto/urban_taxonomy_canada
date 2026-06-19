"""Generate full-detail web data: coordinate quantization only, NO simplification."""
import geopandas as gpd
import pandas as pd
import os
from pathlib import Path

out = Path("outputs/11_exports")

# --- Morphotopes: full geometry, quantized to 6dp (11cm precision) ---
print("Morphotopes...")
morph = gpd.read_file(out / "winnipeg_morphotopes.geojson")
for col in morph.select_dtypes("float64").columns:
    if col != "geometry":
        morph[col] = morph[col].fillna(-1).astype(int)
morph.to_file(out / "morphotopes_full.geojson", driver="GeoJSON", coordinate_precision=6)
size = os.path.getsize(out / "morphotopes_full.geojson") / 1024 / 1024
print(f"  {len(morph):,} features, {size:.1f} MB")

# --- Buildings: full geometry + cluster labels ---
print("Buildings...")
buildings = gpd.read_file("outputs/01_preprocessed/buildings.gpkg")
clusters = pd.read_parquet("outputs/09_hierarchy/tessellation_clusters_final.parquet")
morph_labels = pd.read_parquet(
    "outputs/06_morphotopes/tessellation_labels_postprocessed.parquet"
)["morphotope_label"]

buildings_wgs = buildings.to_crs("EPSG:4326")
buildings_wgs["morphotope"] = morph_labels.reindex(buildings_wgs.index)
for col in clusters.columns:
    buildings_wgs[col] = clusters[col].reindex(buildings_wgs.index)

keep = [
    "HEIGHT", "BLDG_POP", "morphotope", "final",
    "level_1", "level_2", "level_3", "level_4",
    "level_5", "level_6", "level_7", "initially_noise", "geometry",
]
buildings_wgs = buildings_wgs[[c for c in keep if c in buildings_wgs.columns]]
for col in buildings_wgs.select_dtypes("float64").columns:
    if col != "geometry":
        buildings_wgs[col] = buildings_wgs[col].fillna(-1).round(2)

buildings_wgs.to_file(out / "buildings_full.geojson", driver="GeoJSON", coordinate_precision=6)
size = os.path.getsize(out / "buildings_full.geojson") / 1024 / 1024
print(f"  {len(buildings_wgs):,} features, {size:.1f} MB")

print("Done.")
