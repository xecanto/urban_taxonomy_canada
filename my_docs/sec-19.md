You can reproduce their threshold selection with a parameter sweep.

For each candidate minimum-building threshold (\lambda), rerun SA3 and record:

- total inertia/TWSS;

- number of morphotopes;

- proportion of buildings labelled as noise;

- median morphotope size;

- optionally, total mapped area retained.

Use values such as:

λ=10,25,50,75,100,150,200,250



Then plot:

1. **Inertia versus (\lambda)**

2. **Noise proportion versus (\lambda)**

Look for the point where the inertia curve changes from steep growth to slower growth—the elbow or stabilization point. Do not select it from inertia alone, because a lower inertia at high (\lambda) may simply result from more buildings being discarded as noise.

A practical table would look like this:

| Minimum buildings | Inertia | Noise % | Morphotopes |
| ----------------- | ------- | ------- | ----------- |
| 25                | …       | …       | …           |
| 50                | …       | …       | …           |
| 75                | …       | …       | …           |
| 100               | …       | …       | …           |

For Canada, run this separately for several representative places, such as a dense downtown, an inner suburb, a low-density suburb, and a smaller city. If the elbow consistently occurs around the same value, adopt one national threshold. If it varies substantially, consider region-specific thresholds.

For the CHM extension, repeat the sweep twice:

- original morphology variables only;

- morphology plus CHM variables.

This will show whether the 300 m CHM attributes shift the stabilization point.

In pseudocode:

```python
thresholds = [10, 25, 50, 75, 100, 150, 200, 250]
results = []

for threshold in thresholds:
    regions = run_sa3(
        buildings,
        minimum_buildings=threshold
    )

    results.append({
        "threshold": threshold,
        "inertia": calculate_twss(regions, feature_columns),
        "noise_pct": calculate_noise_percentage(regions),
        "n_regions": count_regions(regions),
        "median_region_size": median_region_size(regions)
    })
```

The key is that TWSS must be calculated using the same standardized feature matrix used by SA3, and only for the buildings assigned to regions. Also report the excluded/noise percentage beside it.
