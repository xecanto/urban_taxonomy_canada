**Building geometric features (area, perimeter, compactness, elongation, etc.) are computed AFTER tessellation**, not before. The source `generate_chars.py` needs the tessellation to exist because many characters depend on building-tessellation interactions (e.g., coverage area ratio = building area / tessellation cell area, street alignment, neighbourhood context via tessellation contiguity graph).

From the supplementary material, the 59 primary characters are:

| #     | Code           | Element      | Description                              |
| ----- | -------------- | ------------ | ---------------------------------------- |
| 1     | sdbAre         | Building     | Area                                     |
| 2     | sdbPer         | Building     | Perimeter                                |
| 3     | sdbCoA         | Building     | Courtyard area                           |
| 4     | ssbCCo         | Building     | Circular compactness                     |
| 5     | ssbCor         | Building     | Corners (angle <= 170 deg)               |
| 6     | ssbSqu         | Building     | Squareness                               |
| 7     | ssbERI         | Building     | Equivalent rectangular index             |
| 8     | ssbElo         | Building     | Elongation                               |
| 9     | sdcLAL         | Tessellation | Longest axis length                      |
| 10    | sdcAre         | Tessellation | Area                                     |
| 11    | sscCCo         | Tessellation | Circular compactness                     |
| 12    | sscERI         | Tessellation | Equivalent rectangular index             |
| 13    | sicCAR         | Tessellation | Coverage area ratio (bldg/cell)          |
| 14    | sdsLen         | Street       | Segment length                           |
| 15    | sdsSPW         | Street       | Profile width                            |
| 16    | sdsSPO         | Street       | Profile openness                         |
| 17    | sdsSWD         | Street       | Profile width deviation                  |
| 18    | sssLin         | Street       | Linearity                                |
| 19    | sdsAre         | Street       | Area covered by segment                  |
| 20    | sisBpM         | Street       | Buildings per metre                      |
| 21    | sddAre         | Node         | Area covered by node                     |
| 22    | mtbSWR         | Building     | Shared walls ratio                       |
| 23    | mtbNDi         | Building     | Mean neighbour distance                  |
| 24    | mtcWNe         | Tessellation | Weighted neighbours                      |
| 25    | mdcAre         | Tessellation | Neighbouring cells area                  |
| 26    | ldsAre         | Street       | Reached area (k=3)                       |
| 27    | mtdDeg         | Node         | Degree                                   |
| 28    | mtdMDi         | Node         | Mean distance to neighbours              |
| 29    | midRea         | Node         | Reached cells (k=1)                      |
| 30    | midAre         | Node         | Reached area (k=1)                       |
| 31    | libNCo         | Building     | Courtyards of adjacent buildings         |
| 32    | ldbPWL         | Building     | Perimeter wall length                    |
| 33    | ltbIBD         | Building     | Mean inter-building distance (k=3)       |
| 34    | ltcBuA         | Building     | Building adjacency (k=3)                 |
| 35    | ltcWRB         | Tessellation | Weighted reached blocks (k=3)            |
| 36    | lcdMes         | Node         | Local meshedness (k=5)                   |
| 37    | ldsMSL         | Street       | Mean segment length (k=3)                |
| 38    | ldsCDL         | Node         | Cul-de-sac length (k=3)                  |
| 39    | ldsRea         | Street       | Reached cells (k=3)                      |
| 40    | lddNDe         | Node         | Node density (k=5)                       |
| 41-42 | midRea/midAre  | Node         | Reached cells/area (k=3 network)         |
| 43    | linPDE         | Node         | Proportion cul-de-sacs (k=5)             |
| 44    | linP3W         | Node         | Proportion 3-way intersections (k=5)     |
| 45    | linP4W         | Node         | Proportion 4-way intersections (k=5)     |
| 46    | linWID         | Node         | Weighted node density (k=5)              |
| 47    | lcnClo         | Node         | Local closeness centrality (k=5)         |
| 48    | xcnSCl         | Node         | Square clustering                        |
| 49-57 | mibCou..mibSCo | Building     | 9 connected structure features           |
| 58    | micBAD         | Tessellation | Building area deviation in neighbourhood |
| 59    | midBAD         | Node         | Building area deviation at node          |

**Plus 3 morphotope-level indicators** computed later in notebook 08: `limLPS`, `limAre`, `limPer`.

## What Each Attribute Means

| Attribute        | Description                                                                                                                |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `morph`          | Unique morphotope ID (format: `{component}_{cluster}`). Noise morphotopes have `noise_` prefix.                            |
| `final`          | Finest-level cluster assignment (same as `level_1`), with noise cells assigned via KNN                                     |
| `building_count` | Number of buildings in this morphotope                                                                                     |
| `level_1`        | **Finest** — 173 clusters. Individual urban fabric types (e.g., "detached bungalows on wide lots")                         |
| `level_2`        | 121 clusters. Similar types merged                                                                                         |
| `level_3`        | 87 clusters. Recognizable neighbourhood types                                                                              |
| `level_4`        | 53 clusters. Broad neighbourhood categories                                                                                |
| `level_5`        | 36 clusters. Major urban form families                                                                                     |
| `level_6`        | 19 clusters. Structural categories (e.g., "compact grid", "suburban sprawl", "industrial")                                 |
| `level_7`        | **Coarsest** — 10 clusters. Fundamental urban fabric branches (analogous to source's L1 "Coherent" vs "Incoherent" fabric) |

The hierarchy is **nested**: every `level_1` cluster belongs to exactly one `level_2`, which belongs to one `level_3`, etc.



______________________________________________________________________________________________________________________________________________________________________________________



## QGIS Visualization Guide

### Step 1: Load the data

- Drag `winnipeg_taxonomy.gpkg` into QGIS
- It has two layers: **morphotopes** (dissolved polygons) and **buildings** (original footprints)
- Or use the GeoJSON files for web-friendly formats

### Step 2: Best symbology for each level

**For the overview map (start here):**

1. Right-click `morphotopes` layer → **Properties → Symbology**
2. Choose **Categorized**
3. Column: **`level_7`** (10 classes — the coarsest, most readable)
4. Click **Classify**
5. Color ramp: use **Spectral** or **Set3** (qualitative, not sequential)
6. Set fill opacity to ~70% so you can see streets underneath

**For detailed analysis:**

| What you want to see     | Column           | Symbology type                  | Color ramp      |
| ------------------------ | ---------------- | ------------------------------- | --------------- |
| 10 fundamental types     | `level_7`        | Categorized                     | Spectral / Set3 |
| 19 structural categories | `level_6`        | Categorized                     | tab20 / Paired  |
| 36 urban families        | `level_5`        | Categorized                     | Random colors   |
| Full detail (173 types)  | `level_1`        | Categorized                     | Random colors   |
| Building density         | `building_count` | Graduated (Quantile, 5 classes) | YlOrRd          |

### Step 3: Recommended layer order (bottom to top)

```
1. OpenStreetMap basemap (via QuickMapServices plugin)
2. winnipeg_tessellation.geojson — cell boundaries (thin gray outline, no fill)
3. morphotopes — colored by level_7 (70% opacity)
4. buildings — colored by level_7 (match parent morphotope color)
```

### Step 4: Interpret what you see

At **level_7** (10 clusters), you should see patterns like:

| Cluster pattern                                    | Likely interpretation (Winnipeg context)                    |
| -------------------------------------------------- | ----------------------------------------------------------- |
| Downtown core, tight grid, tall buildings          | **Coherent Dense Fabric** — traditional urban blocks        |
| Wolseley/River Heights, regular lots, shared walls | **Coherent Interconnected Fabric** — older residential grid |
| Suburban crescents, detached houses, wide lots     | **Incoherent Small-Scale Fabric** — post-war suburbs        |
| Strip malls, big-box stores, parking lots          | **Incoherent Large-Scale Fabric** — commercial/industrial   |
| High-rise clusters (e.g., Portage/Main towers)     | **Large-Scale Homogeneous** — modernist towers              |

### Step 5: Drill down

Once you identify a `level_7` cluster of interest:

1. Select it → right-click → **Filter** → `"level_7" = 3` (for example)
2. Switch symbology column to `level_5` or `level_3` to see subtypes within that broad category
3. This mimics how the source paper navigates the taxonomy tree

### Step 6: Quick quality check

- Zoom into an area you know well (e.g., Osborne Village vs. Tuxedo vs. industrial on Logan)
- Verify that visually different neighbourhoods get different cluster colors
- If two obviously different areas share a color at `level_7`, drill down to `level_5` — they should separate there

### Bonus: Label the clusters

At `level_7` with 10 clusters, you can manually name them in QGIS:

1. Symbology → double-click each class
2. Change the **Legend** label from "3" to "Downtown Core" etc.
3. Use the morphometric profiles in `summary_stats.csv` to guide naming (high `sdbAre` = large buildings, high `sicCAR` = dense coverage, high `lcdMes` = connected streets)



______________________________________________________________________________________________________________________________________________________________________________________



**What we added (that the source doesn't have):**

| Column        | Source has it?             | How it enters our pipeline         |
| ------------- | -------------------------- | ---------------------------------- |
| `HEIGHT`      | No (EUBUCCO has no height) | Building-level attribute from OBPL |
| `BLDG_POP`    | No                         | Population per building from OBPL  |
| `volume`      | No                         | Computed as `area * HEIGHT`        |
| `floor_count` | No                         | Computed as `HEIGHT / 3.0`         |

**Where they influence results:**

1. **Primary chars** (notebook 05) — all 4 are included alongside the 55 source characters, giving us 59 features total instead of 55

2. **Morphotope clustering** (notebook 06) — the `QuantileTransformer` scales all 59 features uniformly, then Ward clustering uses them to decide which tessellation cells are morphologically similar. HEIGHT and volume directly affect which cells get grouped together — a block of 10-storey towers will separate from a block of bungalows partly *because* of these columns

3. **Morphotope aggregated data** (notebook 07) — each morphotope gets `median`, `mean`, `std`, `p25`, `p75` for all 4 columns. So you can compare morphotopes by their population density and vertical profile

4. **Hierarchy clustering** (notebook 09) — the median HEIGHT, BLDG_POP, volume, floor_count of each morphotope are 4 of the 59 features used in the KNN + Ward hierarchy. They influence which morphotopes get grouped at coarser levels

5. **Noise assignment** (notebook 10) — KNN classifier uses all 59 features including these 4 to assign noise cells

**The practical impact:** Two morphotopes with identical footprint patterns but different heights/populations will be classified differently. For example, a downtown block of 15-storey towers (HEIGHT=45, BLDG_POP=30) and a suburban strip mall with the same building footprint shape (HEIGHT=5, BLDG_POP=0.5) will separate into different clusters — something the European source *cannot* distinguish since they have no height or population data.

**What we're NOT yet doing (could improve):**

The Canadian columns are treated as 4 additional raw features alongside the 55 morphometric ones. We could go further:

- **Population density per morphotope** — `sum(BLDG_POP) / morphotope_area` as a morphotope-level char in notebook 08
- **Vertical density** — `sum(volume) / morphotope_area` (FAR-like metric at morphotope scale)
- **Height heterogeneity** — `std(HEIGHT)` within a morphotope captures mixed-height areas

Want me to add these as morphotope-level characters in notebook 08?
