# Poster Content — Canadian Urban Taxonomy

Everything below is ready to copy into your own poster layout. Figures referenced are in `poster_presentation/assets/figures/` (full-res) and `poster_presentation/assets/` (UM logo + sampled brand colors).

---

## Title & Header

**Title:** A Canada-Wide Urban Taxonomy

**Subtitle:** A hierarchical, data-driven classification of urban form across 152 Canadian metro areas — piloted in Winnipeg, scaled nationwide

**Authors:** AbdurRehman Goheer · Hassibe Gómez · Jaqueline de la Cruz

**Supervisor / Affiliation:** Supervised by Dr. Yuhao Lu | Faculty of Architecture, University of Manitoba

**Event line:** Undergraduate Research Showcase — October 22, 2026

---

## Background

Cities are usually mapped by land use or by coarse climate-zone categories — labels that describe function, not form. The **Urban Taxonomy** framework (Fleischmann et al., 2022) instead measures the built environment directly — building shapes, plot patterns, street geometry — and lets a classification emerge bottom-up from those measurements, at every scale from a single block to an entire country.

**Research Question** *(good candidate for a callout box)*
> Does this European framework scale to a country as large and geographically diverse as Canada — and can it be sharpened with data Europe's open records don't offer: building height and satellite-derived canopy height?

---

## Data

- CMA/CA boundaries — Statistics Canada
- Building footprints, height & volume — Open Building Population Layers Canada v3 (OBPL-CA-v3)
- Street network — OpenStreetMap (Geofabrik Canada extract)
- Canopy height & cover — Meta CHM v2, sampled in a buffer around each building
- Study area — 152 Census Metropolitan Areas & Agglomerations across Canada, piloted in Winnipeg, Manitoba

---

## Method (6 steps)

| # | Step | Description |
|---|------|-------------|
| 1 | **Preprocess** | Clean & standardize footprints and street geometry, per metro area |
| 2 | **Tessellate** | Divide each city into building-linked morphological cells |
| 3 | **Measure** | Morphometric characters per cell, plus building height, volume & canopy stats |
| 4 | **Delineate** | Group adjacent similar cells into morphotopes |
| 5 | **Classify** | Ward clustering of ALL 152 metros' morphotopes into ONE shared tree, 7 levels (2→128 types) |
| 6 | **Publish** | Reassign edge cases & export to a national interactive web map |

---

## Results

- One taxonomy, built once across all 152 metro areas, resolves into a full morphological hierarchy — from 2 broad classes to 128 fine-grained types
- Within a single city — Winnipeg's dense downtown grid, older streetcar neighbourhoods, and post-war subdivisions — separate cleanly on form alone, using that same shared national taxonomy

**Why It Matters** *(good candidate for a callout box)*
> Building height, volume & canopy data let the classification split high-rise from low-rise, and leafy from bare, fabric that looks identical in a 2D footprint — distinctions the original European method cannot make.

---

## Conclusions

This is among the first applications of theory-driven, hierarchical urban-form classification at a national scale — and the first to combine it with 3D building form and canopy data. Piloted in Winnipeg and scaled to all 152 Canadian metro areas, the resulting taxonomy is published in two variants (with and without canopy structure) through a purpose-built interactive map, giving planners and residents a reproducible, quantitative language for how Canadian cities are actually built.

## Next Steps

- Extend coverage to the ~24% of Canada outside any CMA/CA boundary
- Fold canopy structure directly into the clustering, not just the character set
- Validate the taxonomy against zoning & land-use records

---

## Figures & Captions

All full-resolution PNGs are in `poster_presentation/assets/figures/`.

### 1. Coverage map — `cluster_map.png` (4453×3665)
A map of Canada with all 152 classified CMAs/CAs shaded by building count (Vancouver, Calgary, Edmonton, Winnipeg, Ottawa, Toronto, Montreal, Quebec City, Halifax labeled).

**Caption:** Every filled region is a CMA/CA this pipeline has classified — shaded by building count. **152 in total**, roughly 9.6 million buildings, one shared taxonomy from Vancouver to Halifax.

### 2. Radial taxonomy wheel — `radial_taxonomy.png` (8800×8800px, 400dpi)
Native radial dendrogram (root through level_5, 32 leaves), same layout math and "Bold" 20-colour ramp as the live web viewer, coloured by each leaf's level_3 ancestor (8 named fabric types). Five morphometric character rings — building area, building compactness, coverage area ratio, distance to neighbouring buildings, canopy cover fraction (Meta CHM v2) — drawn as continuous full-region wedges, a log-scale morphotope-abundance ring, and one real, organically-sampled building-footprint silhouette per leaf (its own morphotope's actual cell geometry, adaptive scale, no rectangular crop). Legends (character ramps + abundance + fabric-branch swatches) are separate standalone files so they can be placed independently.

**Caption:** The national taxonomy tree (root to level_5, 32 leaves), coloured by fabric type, with five morphometric character rings, a morphotope-abundance ring, and one real footprint sample per leaf.

**Modelled on Fig. 3 of Fleischmann et al. (2026), "The hierarchical morphotope classification"** (`paper_doc/main research paper.pdf`) — same idea (radial tree + character rings + abundance ring + example footprints), adapted for this dataset:
- **Scope:** their Fig. 3 shows the 26 coarsest branches of a 6-country, ~500,000-morphotope European tree; ours shows level_5 (32 leaves) of the Canada-wide, 152-CMA/CA, 58,684-morphotope tree — same method (SA³ delineation + Ward linkage), different study area and a deeper cut for more resolution.
- **Rings:** they picked 5 attributes from their own 59; we picked our own 5 for genuinely informative spread in this dataset (checked quantiles/zero-fraction first — dropped 2 near-degenerate candidates). One ring, **canopy cover fraction**, has no equivalent in their figure at all — it comes from Meta CHM v2, which they didn't have. Their paper explicitly names the lack of height data as a limitation ("might help distinguish... modernist housing... very different height-wise") — this ring is a direct answer to that gap, not just a stylistic addition.
- **Examples per branch:** they show **two** example morphotopes per branch (nearest to each branch's centroid), explicitly "not to scale" (fixed crop, illustrative only). We show **one** per leaf, but sampled adaptively at that morphotope's own real extent, from its own true (non-rectangular) cell geometry, so it reads as an honest, to-scale sample rather than a generic icon.
- **Level boundaries:** their tree marks bifurcation levels with dashed guide circles; ours omits them (removed after an earlier design pass) in favour of a cleaner center.

**What you could still add**, if useful: a second thumbnail ring (their two-per-branch convention) instead of one; dashed level-boundary rings back in if reviewers expect that convention; a short inset table (like their Table 1) breaking down fabric-type share by province instead of just country, echoing their per-country breakdown at a Canadian scale.

### 3. Full feature matrix — `feature_matrix_full.png` (5932×2050) — **regenerated as ONE combined figure**
A single continuous heatmap: 8 rows (top-level fabric Types) × all 61 morphometric characters actually used in the pipeline, white→dark-green shaded by relative value (per-column min–max). The **6 Canada-only columns are labeled in gold** at the right-hand end (building height, building volume, mean/std/max canopy height, canopy cover fraction) — data the original European taxonomy never had. `limLPS`/`limAre` (likely-occupied-area indicator, area of largest connected structures) are plain-labeled since those are part of the *original* paper's own methodology (its "3 additional indicator variables," §10 of the supplementary material), not a Canadian addition. Column labels are verified directly against the pipeline's own `04_morphometrics.ipynb` (exact momepy calls) and the `TO_DROP` list in `09_clustering.ipynb` (which — copied from the original source code — explains why only 61 of the ~72 core characters computed actually survive into clustering), not guessed.

**Caption:** Relative value of every morphometric character (columns) across the 8 top-level fabric types (rows), Canada-wide. Gold column labels mark the characters this Canadian run adds beyond the original European taxonomy.

### 4. Interactive viewer screenshot — `viewer_screenshot.png` (3840×2160)
National-zoom screenshot of the live web app, showing building clusters across Canada plus its own live radial-dendrogram widget (bottom right) — a nice visual echo of figure 2.

**Caption:** The full national classification — roughly 9.6 million buildings across 152 metro areas, every hierarchy level, with and without canopy data — is published in a purpose-built web viewer: pan and zoom any Canadian city, recolor buildings by any level of the taxonomy, and trace how a single block's classification unfolds up the tree in a live radial dendrogram.

*(Two other figures are also sitting in that folder if useful: `dendrogram.png` — a standard truncated Ward dendrogram from the national linkage matrix, and `cluster_detail.png` — a zoomed-in map of downtown Winnipeg at a fine hierarchy level. Not required, just there if you want a 5th/6th panel.)*

---

## Footer

**Acknowledgments:** Supervised by **Dr. Yuhao Lu**, Faculty of Architecture, University of Manitoba.

**Method Adapted From:** Fleischmann, M., Feliciotti, A., Romice, O., & Porta, S. (2022). Methodological foundation of a numerical taxonomy of urban form. *Environment and Planning B: Urban Analytics and City Science*, 49(4), 1283–1299.

**Built With:** momepy · PySAL · GeoPandas · scikit-learn — React · MapLibre GL · D3.js

---

## Brand Reference (for your own layout)

- **UM logo:** `poster_presentation/assets/UM-logo-horizontal-CMYK.png` (full colour, for light backgrounds) and `UM-logo-horizontal-reverse-rgb.png` (colour shield + white text, for dark/colour backgrounds) — both official downloads from umanitoba.ca/about-um/brand.
- **Colors sampled directly from the logo:**
  - Lake blue `#0061b0`
  - Sky blue `#00a4e6`
  - Wheat gold `#fdb414`
  - Bison brown `#3d150a`
- **Board:** assigned 4'H × 8'W board; a 4"H × 11"W space in the board's upper-right corner is reserved by the event for the board number — that's on the physical board, not something to design into your file.
