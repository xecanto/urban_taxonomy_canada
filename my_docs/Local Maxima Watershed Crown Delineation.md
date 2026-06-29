## Full Step-by-Step: Local Maxima + Watershed Crown Delineation

**Your inputs:**

- Raster layer (CHM): height values 0–34m
- Boundary shapefile (Winnipeg)

---

### Step 0: Prep

1. Open ArcGIS Pro, create a new project or use existing
2. Add both layers to the map
3. Set **Processing Environments** (Analysis > Environments):
   - **Processing Extent**: your boundary shapefile
   - **Mask**: your boundary shapefile (clips all outputs to Winnipeg)
   - **Cell Size**: same as your input raster (check in Layer Properties > Source)
   - **Snap Raster**: your input raster
4. Make sure **Spatial Analyst** extension is enabled (Project > Licensing)

---

### Step 1: Remove ground (non-tree) pixels

Your raster goes 0–34m. Anything below ~2m is ground/grass/shrubs, not trees.

**Tool**: Raster Calculator (Spatial Analyst > Map Algebra)

```
Con("your_chm" >= 2, "your_chm", 0)
```

- **Input**: your CHM raster
- **Output**: `CHM_trees`
- This sets everything below 2m to 0 (no data for tree purposes)

> If you want to be cleaner, use `SetNull` instead:
> 
> ```
> SetNull(Raster("merge_raster.tif") < 2, Raster("merge_raster.tif"))
> ```
> 
> This makes below-2m pixels NoData rather than 0, which behaves better in later steps.

---

### Step 2: Smooth the CHM

Smoothing removes small spikes (branches, noise) that would create false treetops.

**Tool**: Focal Statistics (Spatial Analyst > Neighborhood)

| Parameter       | Value                                                                   |
| --------------- | ----------------------------------------------------------------------- |
| Input raster    | `CHM_trees` (from Step 1)                                               |
| Output raster   | `CHM_smooth`                                                            |
| Neighborhood    | **Circle**                                                              |
| Radius          | **3 cells** (start here; increase to 5 if you see too many false peaks) |
| Statistics type | **Mean**                                                                |
| Ignore NoData   | **Checked**                                                             |

> **Why 3 not 5?** Your range goes to 34m so you have large trees. A 3-cell circular window preserves individual peaks in dense areas. If results are over-segmented later, come back and increase to 5.

---

### Step 3: Find local maxima (treetops)

Each local maximum in the smoothed CHM = a treetop candidate.

**Tool**: Focal Statistics (Spatial Analyst > Neighborhood)

| Parameter       | Value                      |
| --------------- | -------------------------- |
| Input raster    | `CHM_smooth` (from Step 2) |
| Output raster   | `CHM_localmax`             |
| Neighborhood    | **Circle**                 |
| Radius          | **5 cells**                |
| Statistics type | **Maximum**                |
| Ignore NoData   | **Checked**                |

> **Tuning the radius — this is the most important parameter:**
> 
> - **3 cells** → detects small crowns, may over-segment (split one tree into multiple)
> - **5 cells** → good default for urban trees
> - **7–9 cells** → for large-canopy trees (e.g., mature elms, oaks)
> - Check your raster cell size: if 1m resolution, 5 cells = 5m radius = ~10m diameter minimum crown. If 0.5m resolution, 5 cells = 2.5m = ~5m diameter.
> 
> **Rule of thumb**: radius ≈ average expected crown radius in cell units

---

### Step 4: Identify treetop pixels

Where the smoothed CHM equals its local maximum, that pixel IS the peak.

**Tool**: Raster Calculator

```
Con(("CHM_smooth" == "CHM_localmax") & ("CHM_smooth" > 2), 1)
```

- **Output**: `treetops_raster`
- This gives you a raster where 1 = treetop, NoData = everything else
- The `> 2` condition filters out ground-level "peaks"

---

### Step 5: Convert treetop raster to points

You need point features to use as watershed pour points.

**Tool**: Raster to Point (Conversion Tools > From Raster)

| Parameter    | Value                           |
| ------------ | ------------------------------- |
| Input raster | `treetops_raster` (from Step 4) |
| Field        | `VALUE`                         |
| Output       | `treetop_points`                |

You should now see a point on each treetop when overlaid on your CHM. **Visually inspect** — zoom into an area you know well:

- Too many points clustered on one tree → go back to Step 3, increase radius
- One point spanning two clearly separate trees → decrease radius

---

### Step 6: Invert the smoothed CHM

Watershed delineation finds basins (low points). We invert the CHM so each treetop becomes the bottom of a "basin" and crown edges become ridges.

**Tool**: Raster Calculator

```
34 - "CHM_smooth"
```

- **Output**: `CHM_inverted`

- Use your actual max value (34) or use:
  
  ```
  Int(("CHM_smooth".maximum - "CHM_smooth") * 100)
  ```
  
  The `Int` and `*100` converts to integer (required by Flow Direction) while preserving decimal precision.

> **Important**: Flow Direction requires an **integer** raster. If your CHM has decimal values:
> 
> ```
> Int((34 - "CHM_smooth") * 100)
> ```

---

### Step 7: Flow Direction

**Tool**: Flow Direction (Spatial Analyst > Hydrology)

| Parameter                            | Value                        |
| ------------------------------------ | ---------------------------- |
| Input surface                        | `CHM_inverted` (from Step 6) |
| Output raster                        | `flow_dir`                   |
| Flow direction type                  | **D8**                       |
| Force all edge cells to flow outward | **Checked**                  |

---

### Step 8: Watershed (crown delineation)

Each treetop pour point defines one "drainage basin" = one tree crown.

**Tool**: Watershed (Spatial Analyst > Hydrology)

| Parameter               | Value                                          |
| ----------------------- | ---------------------------------------------- |
| Input D8 flow direction | `flow_dir` (from Step 7)                       |
| Input pour point data   | `treetop_points` (from Step 5)                 |
| Pour point field        | `OBJECTID` (each point gets a unique crown ID) |
| Output raster           | `crown_zones`                                  |

Each cell in `crown_zones` now has a unique ID corresponding to its parent tree.

---

### Step 9: Mask crowns to actual canopy

The watershed extends crowns into open ground. Clip back to only where trees exist.

**Tool**: Raster Calculator

```
Con("CHM_trees" >= 2, "crown_zones")
```

- **Output**: `crown_zones_clipped`
- This removes crown assignments from ground pixels

---

### Step 10: Raster to Polygon

**Tool**: Raster to Polygon (Conversion Tools > From Raster)

| Parameter         | Value                                                |
| ----------------- | ---------------------------------------------------- |
| Input raster      | `crown_zones_clipped` (from Step 9)                  |
| Field             | `VALUE`                                              |
| Output            | `tree_crowns_raw`                                    |
| Simplify polygons | **Unchecked** (pipeline does its own simplification) |

---

### Step 11: Cleanup

**11a. Add HEIGHT per crown**

**Tool**: Zonal Statistics as Table (Spatial Analyst > Zonal)

| Parameter          | Value                                              |
| ------------------ | -------------------------------------------------- |
| Input zone         | `tree_crowns_raw`                                  |
| Zone field         | `gridcode` (or `VALUE`)                            |
| Input value raster | `CHM_trees` (original, not smoothed)               |
| Statistics type    | **Maximum** (tree height = tallest point in crown) |
| Output table       | `crown_heights`                                    |

Then **Join Field** (Data Management):

- Input: `tree_crowns_raw`
  - input field: gridcode
- Join table: `crown_heights`
  - Join field: gridcode
- Transfer fields: `MAX`

Then **Calculate Field**:

- Field name: `HEIGHT`
- Expression: `!MAX!`

**11b. Remove junk polygons**

**Tool**: Select by Attributes → Export

```sql
Shape_Area >= 3 AND Shape_Area <= 500
```

- Removes tiny fragments (< 3 m²) and merged mega-canopy (> 500 m²)
- Adjust thresholds based on your area — 500 m² is generous for single trees

**11c. Remove donut holes (optional)**

**Tool**: Eliminate Polygon Part (Data Management > Generalization)

- Minimum area: 2 m²
- This fills small gaps inside crowns

---

### Step 12: Export for the pipeline

**Tool**: Export Features (right-click layer > Data > Export Features)

| Parameter | Value                                                      |
| --------- | ---------------------------------------------------------- |
| Output    | `data/winnipeg_trees.gpkg` (in your project's data folder) |
| Format    | GeoPackage                                                 |

**Verify CRS**: Must be **EPSG:3978**. If not:

- **Project** tool (Data Management > Projections) to reproject before exporting

**Final schema should have at minimum:**

| Column     | Type    | Source                  |
| ---------- | ------- | ----------------------- |
| `geometry` | Polygon | crown polygons          |
| `HEIGHT`   | Float   | max CHM value per crown |

---

### Summary of outputs at each step

| Step | Output                | What it is                       |
| ---- | --------------------- | -------------------------------- |
| 1    | `CHM_trees`           | CHM with ground removed          |
| 2    | `CHM_smooth`          | Smoothed canopy surface          |
| 3    | `CHM_localmax`        | Local maximum surface            |
| 4    | `treetops_raster`     | Binary: 1 = treetop              |
| 5    | `treetop_points`      | Point features at each treetop   |
| 6    | `CHM_inverted`        | Inverted CHM (integer)           |
| 7    | `flow_dir`            | D8 flow direction                |
| 8    | `crown_zones`         | Each cell labeled by its tree ID |
| 9    | `crown_zones_clipped` | Crowns masked to canopy only     |
| 10   | `tree_crowns_raw`     | Polygon footprints per crown     |
| 11   | `tree_crowns_clean`   | With HEIGHT, junk removed        |
| 12   | `winnipeg_trees.gpkg` | Final GeoPackage for pipeline    |

---

Once you have `winnipeg_trees.gpkg`, let me know and I'll adapt the notebooks to run on trees instead of buildings.
