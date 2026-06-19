# Winnipeg Urban Taxonomy

A computational urban morphology pipeline that classifies Winnipeg's urban fabric into hierarchical morphological types using building footprints, street networks, and 3D building data.

## Overview

This project applies the **Urban Taxonomy** methodology to Winnipeg, Manitoba, Canada. It processes building footprints through morphological tessellation, extracts 59 morphometric features, and uses Ward hierarchical clustering to produce a multi-level classification of urban form — from broad categories (e.g., "Dense Urban Core" vs "Low Density Suburban") down to fine-grained morphological types.

### The Canadian Advantage

Unlike the original European Urban Taxonomy, this pipeline leverages Canada's open 3D building data (HEIGHT, BLDG_POP, volume), enabling richer morphological characterization that includes vertical urban form.

## Pipeline

The pipeline is organized as Jupyter notebooks in the `notebooks/` directory:

| # | Notebook | Description |
|---|----------|-------------|
| 01 | `01_preprocess.ipynb` | Data cleaning & CRS standardization |
| 02 | `02_tessellation.ipynb` | Morphological tessellation |
| 03 | `03_graphs.ipynb` | Spatial relationship graphs |
| 04 | `04_morphometrics.ipynb` | Feature extraction (59 morphometric characters) |
| 05 | `05_merge_chars.ipynb` | Merge character tables |
| 06 | `06_morphotopes.ipynb` | Spatial regionalization into morphotopes |
| 07 | `07_morphotope_postprocessing.ipynb` | Post-processing & noise handling |
| 08 | `08_morphotope_chars.ipynb` | Morphotope-level character aggregation |
| 09 | `09_clustering.ipynb` | Ward hierarchical clustering (KNN-constrained) |
| 10 | `10_noise.ipynb` | Noise morphotope assignment |
| 11 | `11_export.ipynb` | Final exports (GeoJSON, FlatGeobuf, GeoPackage) |

### Clustering Approaches

Two approaches for cutting the dendrogram are supported:

- **Fixed Count**: Target cluster counts (2, 4, 8, 16, 32, 64, 128) — binary branching hierarchy
- **Percentile**: Distance-based percentile cutoffs (90th–99.5th) — data-driven thresholds

## Morphometric Features

59 features are extracted per morphotope, covering:

- **Buildings**: area, perimeter, compactness, squareness, elongation
- **Blocks**: building count, floor area ratio, coverage
- **Plots/Cells**: area, compactness
- **Streets**: length, linearity, width, profile
- **Network**: closeness centrality, intersection types
- **3D**: building height, population, volume, floor count
- **Morphotope**: shape, size (longest path, area)

## Data Sources

- **Building Footprints with Heights & Population**: Open Building Population Layers Canada v3 (OBPL-CA-v3) — [mappedcurrents.ca/projects/obpl-ca-v3](https://mappedcurrents.ca/projects/obpl-ca-v3/)
- **Street Network**: OpenStreetMap via `osmnx`

## Web Viewer

An interactive dashboard for exploring the taxonomy is available in the companion repository [`urban_taxonomy_viewer`](../urban_taxonomy_viewer/). See its README for details.

## Credits

### Team

- **Yuhao Lu** — Professor, University of Manitoba (Supervisor)
- **Jaqueline** — Group Member
- **AbdurRehman Goheer** — Group Member

### Based On

This project is inspired by and builds upon the **Urban Taxonomy** research:

- **Paper**: Fleischmann, M., Feliciotti, A., Romice, O., & Porta, S. (2022). *Methodological foundation of a numerical taxonomy of urban form*. Environment and Planning B: Urban Analytics and City Science, 49(4), 1283–1299. [DOI: 10.1177/23998083211059835](https://doi.org/10.1177/23998083211059835)
- **Website**: [urbantaxonomy.org](https://urbantaxonomy.org/)
- **Source Code**: [github.com/UrbanTaxonomy](https://github.com/UrbanTaxonomy)

### Key Libraries

- [momepy](https://momepy.org/) — Urban morphology measuring toolkit
- [PySAL](https://pysal.org/) — Python Spatial Analysis Library
- [scikit-learn](https://scikit-learn.org/) — Machine learning (clustering)
- [GeoPandas](https://geopandas.org/) — Geospatial data in Python

## License

Academic use. Please cite the original Urban Taxonomy paper and this project when using the methodology or results.
