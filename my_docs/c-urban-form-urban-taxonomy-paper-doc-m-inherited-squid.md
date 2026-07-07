# Plan: Add CHM Raster Layer to `notebooks_buidings` Urban Taxonomy Pipeline

## Context
The `notebooks_buidings/` directory holds the original buildings + street-network urban taxonomy pipeline. The user wants to enrich this pipeline with LiDAR-derived tree canopy height data from the CHM (Canopy Height Model) raster already present in the project. This adds a **green-infrastructure dimension** to the existing built-form morphometrics, letting the clustering distinguish, for example, high-canopy suburban streets from low-canopy commercial corridors that may look similar in 2D building morphology alone.

The CHM is already processed and available as a mosaic at `arcgis/merge_raster.tif` (93 MB, 1.19 m resolution, 0–34 m values, EPSG:3979).

---

## What Changes

### New file: `notebooks_buidings/04b_chm_chars.ipynb`

Insert this notebook between notebooks 04 and 05. It:

1. **Loads inputs** — tessellation from `outputs/02_tessellation/tessellation.parquet` and the merged CHM raster from `arcgis/merge_raster.tif`.

2. **Aligns CRS** — tessellation is EPSG:3978; CHM is EPSG:3979. Reproject tessellation geometries to EPSG:3979 (or open raster with rasterio and let `rasterstats` handle it via `all_touched=True`).

3. **Extracts zonal statistics per tessellation cell** using `rasterstats.zonal_stats` (or pure rasterio if not installed):
   - `chm_mean` — mean canopy height (m); proxy for overall tree cover density + height
   - `chm_std` — std dev of height; captures canopy heterogeneity / complexity
   - `chm_max` — max canopy height; detects presence of mature trees
   - `chm_cover` — fraction of pixels > 2 m (binary canopy presence threshold); direct canopy cover %

4. **Handles no-data** — CHM uses 0 for non-vegetated pixels; `chm_cover` counts pixels ≥ 2 m so grassed/bare ground (pixel = 0 or 1) is treated as no canopy. `chm_mean` / `chm_std` / `chm_max` use all pixels including 0 (so they inherently capture canopy density, not just height of covered fraction).

5. **Saves** to `outputs/04b_chm_chars/chm_chars.parquet` — a plain DataFrame indexed by tessellation cell ID with 4 float columns.

```python
# Key implementation sketch:
import rasterio, numpy as np, pandas as pd, geopandas as gpd
from rasterstats import zonal_stats          # pip install rasterstats if missing

tessellation = gpd.read_parquet("outputs/02_tessellation/tessellation.parquet")
# Reproject tess geometry to EPSG:3979 for raster sampling
tess_3979 = tessellation.to_crs("EPSG:3979")

CHM_PATH = "arcgis/merge_raster.tif"
stats = zonal_stats(tess_3979, CHM_PATH, stats=["mean", "std", "max"],
                    add_stats={"cover": lambda x: (x >= 2).mean()},
                    nodata=None)

chm_df = pd.DataFrame(stats, index=tessellation.index,
                       columns=["chm_mean", "chm_std", "chm_max", "chm_cover"])
chm_df.fillna(0, inplace=True)
chm_df.to_parquet(OUT / "chm_chars.parquet")
```

---

### Modified file: `notebooks_buidings/05_merge_chars.ipynb`

**Cell `setup`** — add load of chm_chars:
```python
chm_df = pd.read_parquet("outputs/04b_chm_chars/chm_chars.parquet")
```

**Cell `merge`** — after all existing merges, add:
```python
merged = merged.join(chm_df, how="left")
```

**USED_KEYS** — append at end:
```python
# CHM (LiDAR canopy height model) additions
"chm_mean", "chm_std", "chm_max", "chm_cover",
```

These 4 features flow through to both morphotope clustering (nb06) and hierarchy clustering (nb09) automatically — they are NOT added to TO_DROP, so they participate in Ward clustering.

---

## Dependencies

`rasterstats` is not part of the current venv. Two options:
- **Recommended:** `pip install rasterstats` in the venv (small package, wraps rasterio which is already present via geopandas).
- **Fallback (no install):** Pure rasterio — iterate chunks of tessellation cells with `rasterio.mask.mask`, extract numpy arrays, compute stats manually. Slower but zero new dependencies.

The plan uses `rasterstats` as primary path with a note to install it.

---

## Files Touched

| File | Action |
|------|--------|
| `notebooks_buidings/04b_chm_chars.ipynb` | **Create new** |
| `notebooks_buidings/05_merge_chars.ipynb` | **Edit** — 2 cells: add load + merge of chm_df; add 4 keys to USED_KEYS |

Notebooks 01–04, 06–11 are **untouched**.

---

## Verification

1. Run `04b_chm_chars.ipynb` → check `outputs/04b_chm_chars/chm_chars.parquet` has ~274k rows and 4 non-null float columns with sensible ranges (chm_mean ~0–15 m, chm_cover 0–1).
2. Run `05_merge_chars.ipynb` → confirm "Missing (ok if not computed)" does **not** list the 4 new chm columns.
3. Run `06_morphotopes.ipynb` → morphotope count should be similar to the no-CHM run (within ~5%); existence of chm features in primary_chars is the key check.
4. Spot-check: tessellation cells in known park areas (e.g. Assiniboine Park bounds) should have high `chm_cover` and `chm_mean`; downtown cells near portage/main should have near-zero values.
