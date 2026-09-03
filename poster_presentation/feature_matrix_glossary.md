# Feature Matrix Glossary

Explains `assets/figures/feature_matrix_full.png` (built by `scripts/build_feature_matrix.py`) — what the matrix shows, what "low" and "high" mean, and what every one of the 61 characters actually measures.

---

## What the matrix shows

- **Rows** — the 8 top-level fabric clusters of the national taxonomy (`level_3` of the 7-level hierarchy, 2→128 clusters). Each row is the **average value** of every morphotope assigned to that cluster, across all 152 Canadian metro areas.
- **Columns** — all 61 morphometric characters actually used to build the taxonomy (out of ~72 computed — see "Why 61" below).
- **Cell colour** — how that cluster compares to the *other 7 clusters*, for that one column, nothing else.

## What "low" and "high" mean here

Each **column is normalized independently**, min–max, using only the 8 cluster-average values in that column:

```
normalized = (value − min_across_8_clusters) / (max_across_8_clusters − min_across_8_clusters)
```

So for any given column:
- **White / lightest ("low")** = whichever cluster has the *smallest* average value for that specific character, among the 8 clusters.
- **Dark green ("high")** = whichever cluster has the *largest* average value for that specific character, among the 8 clusters.
- **Middle green** = somewhere in between.

Two things this does **not** mean:
1. **Not an absolute scale.** "High" building height in one column and "high" street width in another column are two different clusters compared against two different sets of 8 numbers — you cannot compare shading *across* columns, only *within* a column (down each column).
2. **Not a global percentile.** The normalization only ever sees these 8 cluster averages — not the full distribution of all 58,684 morphotopes or all ~9.6M buildings. A cluster shaded "high" simply has the largest average among the other 7 clusters, however large or small that gap actually is in real units.

If you want the real units (m², metres, degrees, ratios, etc.) for any cell, they're in `outputs_canada_cma_ca/09_hierarchy/cdata.parquet` joined to `cluster_mapping.parquet` — the PNG only encodes relative rank, by design (matches the source paper's own figure style).

---

## Why 61 characters, not 59 or 65

Full trace (see prior conversation for the notebook-by-notebook walkthrough):

| Step | Count |
|---|---|
| Core (non-Canadian) morphometric characters computed by the pipeline | 72 |
| − dropped before clustering, per the **original** Urban Taxonomy source code's own exclusion list (`TO_DROP` in `notebooks_buidings/09_clustering.ipynb`) — mostly enclosure-scale characters, a few redundant orientation/deviation intermediates | −19 |
| = core characters that survive into clustering | **53** |
| + 2 morphotope-shape indicators from the *original* paper's own methodology (`limLPS`, `limAre` — its "3 additional indicator variables", `other materials.pdf` §10; the 3rd, `limPer`, is computed but discarded after one-time outlier filtering) | **55** |
| + 6 genuinely **Canada-only** additions (see below) | **61** |

`floor_count` is also present as a column in the raw data but is excluded here — it isn't an actually-used/validated feature in this pipeline.

---

## Canada-only characters (6)

These do not exist in the original European Urban Taxonomy study — Europe's open cadastral records don't include building height or canopy data:

| Code | Meaning | Source |
|---|---|---|
| `HEIGHT` | Building height | OBPL-CA-v3 |
| `volume` | Building volume (footprint area × height) | derived |
| `chm_mean` | Mean canopy height in a buffer around the building | Meta CHM v2 |
| `chm_std` | Canopy height standard deviation in that buffer | Meta CHM v2 |
| `chm_max` | Max canopy height in that buffer | Meta CHM v2 |
| `chm_cover` | Canopy cover fraction in that buffer | Meta CHM v2 |

Everything else in the matrix is either the original paper's own morphometric character set or its own morphotope-shape indicators — not something this project added.

---

## Full character glossary (61)

Grouped by what they describe. Definitions verified against `notebooks_buidings/04_morphometrics.ipynb` (the exact momepy calls that compute each column) and cross-checked against the source paper's own numbered glossary (`paper_doc/other materials.pdf`, §10).

### Building shape (7)
| Code | Description |
|---|---|
| `sdbAre` | Area of building |
| `sdbPer` | Perimeter of building |
| `sdbCoA` | Courtyard area of building |
| `ssbCCo` | Circular compactness of building (similarity to its minimal enclosing circle) |
| `ssbSqu` | Squareness of building (mean deviation of corners from 90°) |
| `ssbERI` | Equivalent rectangular index of building |
| `ssbElo` | Elongation of building |

### Building context (6)
| Code | Description |
|---|---|
| `libNCo` | Number of courtyards of adjacent buildings |
| `ldbPWL` | Perimeter wall length of adjacent buildings |
| `ltcBuA` | Building adjacency within the tessellation neighbourhood |
| `mtbAli` | Alignment of neighbouring buildings (orientation similarity) |
| `mtbNDi` | Mean distance to neighbouring buildings |
| `ltbIBD` | Mean inter-building distance (larger neighbourhood) |
| `stbSAl` | Street alignment of building |

### Connected building structures (9)
*"Connected" = the union of all directly-touching buildings, treated as one shape.*
| Code | Description |
|---|---|
| `mibCou` | Connected buildings count |
| `mibAre` | Connected buildings area |
| `mibLen` | Connected buildings perimeter |
| `mibElo` | Connected buildings elongation |
| `mibERI` | Connected buildings equivalent rectangular index |
| `mibCCo` | Connected buildings circular compactness |
| `mibLAL` | Connected buildings longest axis length |
| `mibFR` | Connected buildings facade ratio (area / perimeter) |
| `mibSCo` | Connected buildings square compactness |

### Tessellation cell (8)
*The tessellation cell is the "plot-like" polygon generated around each building.*
| Code | Description |
|---|---|
| `sdcLAL` | Longest axis length of tessellation cell |
| `sdcAre` | Area of tessellation cell |
| `sscCCo` | Circular compactness of tessellation cell |
| `sscERI` | Equivalent rectangular index of tessellation cell |
| `mtcWNe` | Weighted neighbours of tessellation cell |
| `mdcAre` | Area covered by neighbouring cells |
| `sicCAR` | Coverage area ratio (building area / cell area) |
| `micBAD` | Building area deviation in the tessellation neighbourhood |

### Street segment (9)
| Code | Description |
|---|---|
| `sdsLen` | Length of street segment |
| `sssLin` | Linearity of street segment (straightness) |
| `ldsMSL` | Mean segment length of street network (3 topological hops) |
| `sisBpM` | Buildings per metre of street segment |
| `sdsSPW` | Width of street profile |
| `sdsSPO` | Openness of street profile |
| `sdsSWD` | Width deviation of street profile |
| `sdsAre` | Area covered by street segment |
| `ldsCDL` | Cul-de-sac length of street network (3 hops) |

### Street node / network (14)
| Code | Description |
|---|---|
| `sddAre` | Area covered by street node |
| `mtdMDi` | Mean distance to neighbouring street nodes |
| `midRea` | Reached cells by neighbouring nodes (1 hop) |
| `midAre` | Reached area by neighbouring nodes (1 hop) |
| `lcdMes` | Local meshedness of street network (5 hops) |
| `lddNDe` | Node density of street network (5 hops) |
| `linWID` | Weighted node density of street network (5 hops) |
| `linPDE` | Proportion of dead-ends / cul-de-sacs (5 hops) |
| `linP3W` | Proportion of 3-way intersections (5 hops) |
| `linP4W` | Proportion of 4-way intersections (5 hops) |
| `lcnClo` | Local closeness centrality of street network (5 hops) |
| `xcnSCl` | Square clustering of street network |
| `midBAD` | Building area deviation among node-attached buildings |

### Morphotope-shape indicators — original paper's own (2)
| Code | Description |
|---|---|
| `limLPS` | "Likely occupied area" indicator — flags morphotopes dominated by blocky, industrial-style buildings |
| `limAre` | Summed area of the 10 largest connected building structures in the morphotope |

### Canada-only additions (6)
| Code | Description |
|---|---|
| `HEIGHT` | Building height |
| `volume` | Building volume |
| `chm_mean` | Mean canopy height (Meta CHM v2) |
| `chm_std` | Canopy height standard deviation (Meta CHM v2) |
| `chm_max` | Max canopy height (Meta CHM v2) |
| `chm_cover` | Canopy cover fraction (Meta CHM v2) |

---

## Regenerating the figure

```
.venv\Scripts\python.exe poster_presentation\scripts\build_feature_matrix.py
```

See the script's own docstring for flags (`--level`, `--cell-size`, `--data-dir`, `--out`).
