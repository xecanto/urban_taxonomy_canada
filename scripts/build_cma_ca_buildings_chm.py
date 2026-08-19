"""
One-off data-prep script: join the 156-city CHM computation output back onto
the full OBPL building attributes, to produce a single buildings file usable
as BUILDINGS_FILE for a CMA/CA region-chunked run.

Why this join is needed: the separate 156-city pipeline only computed and
exported chm_mean/std/max/cover (+ BLDG_ID, CMAUID/CMANAME/CMATYPE, geometry)
— it does not carry HEIGHT or the other OBPL attributes the buildings
taxonomy pipeline needs (see notebooks_buidings/01_preprocess.ipynb, notably
the HEIGHT-fillna step and the HEIGHT/volume/floor_count clustering features
in 09_clustering.ipynb). Those attributes live only in the original
OBPL_CA_v3_Footprints_Canada.gpkg. Both files share the same BLDG_ID, so a
plain attribute join reunites them.

Usage:
    .venv\\Scripts\\python.exe scripts\\build_cma_ca_buildings_chm.py
"""

import geopandas as gpd
import pandas as pd
import pyogrio

OBPL_FILE = "data/OBPL_CA_v3_Footprints_Canada/OBPL_CA_v3_Footprints_Canada.gpkg"
CHM_FILE = r"C:\Users\abdur\Downloads\156 cities\output\final\combined_chm_stats_cma_ca.parquet"
OUT_FILE = "data/canada_cma_ca_buildings_chm.gpkg"
OUT_LAYER = "buildings_chm_stats"

# Attribute columns to carry over from OBPL (everything except BLDG_ID, which
# is the join key, and geometry, which we keep from the CHM side since that's
# the geometry that was actually used to compute the CHM stats).
OBPL_ATTR_COLS = [
    "BLDG_ID", "HEIGHT", "DBUID", "DB_RATIO", "DAUID", "DA_RATIO",
    "CSDUID", "CSD_RATIO", "CDUID", "CD_RATIO", "ORPHAN_RATIO",
    "HAS_ORPHAN_BONUS", "BLDG_POP", "POP_SOURCE", "QF_O", "QF_V",
]


def main():
    print(f"Reading OBPL attributes (no geometry) from {OBPL_FILE} ...")
    obpl_attrs = pyogrio.read_dataframe(
        OBPL_FILE, columns=OBPL_ATTR_COLS, read_geometry=False
    )
    print(f"  {len(obpl_attrs):,} rows, {obpl_attrs['BLDG_ID'].nunique():,} unique BLDG_ID")

    print(f"\nReading CHM stats + geometry from {CHM_FILE} ...")
    chm = gpd.read_parquet(CHM_FILE)
    print(f"  {len(chm):,} rows, {chm['BLDG_ID'].nunique():,} unique BLDG_ID, CRS={chm.crs}")

    print("\nJoining on BLDG_ID (left join, keeping every CHM-computed row) ...")
    merged = chm.merge(obpl_attrs, on="BLDG_ID", how="left")
    del chm, obpl_attrs

    unmatched = merged["HEIGHT"].isna().sum()
    print(f"  Merged: {len(merged):,} rows. Unmatched (no OBPL attrs found): {unmatched:,}")

    print(f"\nWriting {OUT_FILE} (layer={OUT_LAYER}) ...")
    merged.to_file(OUT_FILE, layer=OUT_LAYER, driver="GPKG")
    print(f"Done. Columns: {list(merged.columns)}")


if __name__ == "__main__":
    main()
