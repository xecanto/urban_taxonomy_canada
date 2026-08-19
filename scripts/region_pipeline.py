"""
Region-chunked orchestration for country/large-area runs of the buildings
taxonomy pipeline (notebooks_buidings/).

A single unified tessellation + graph + morphotope-regionalization run does
not scale to a country the size of Canada (13.7M buildings) — phases 2/3/6
scale worse than linearly and blow past available memory. Instead we split
the study area into regions (e.g. CMA/CA polygons — see conversation/README
for why: they don't cut through continuous urban fabric the way provinces
or census divisions would) and run phases 1-8 independently per region.

Phases 1-8 are spatially local: the tessellation contiguity graph and Ward
regionalization only look at buildings/streets within one region, so running
them per region doesn't change their result, other than truncating spatial
context exactly at the region boundary. To avoid genuinely truncating
context right at each region's true edge, every region's boundary is
buffered outward before clipping (BUFFER_M). Buildings that fall only in the
buffer ring (not the true, unbuffered region) are flagged non-core via
core_mask.parquet and dropped again at the final merge, so they aren't
double-counted by both neighbouring regions.

Only phase 9 (hierarchical taxonomy clustering) is inherently global:
morphotope characteristics from every region are pooled into one table and
clustered once (merge_morphotopes + a single run of 09_clustering.ipynb), so
morphotope labels are comparable everywhere. 09b_map_to_cells.ipynb then maps
that shared taxonomy back onto each region's own tessellation cells; phases
10-11 run per region exactly as they do for a single-city run.
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd

LOCAL_NOTEBOOKS = [
    (1, "01_preprocess.ipynb", "Preprocessing"),
    (2, "02_tessellation.ipynb", "Morphological Tessellation"),
    (3, "03_graphs.ipynb", "Spatial Graphs"),
    (4, "04_morphometrics.ipynb", "Morphometric Characters"),
    (5, "05_merge_chars.ipynb", "Merge Characters"),
    (6, "06_morphotopes.ipynb", "Morphotopes (SA3 Regionalization)"),
    (7, "07_morphotope_postprocessing.ipynb", "Morphotope Postprocessing"),
    (8, "08_morphotope_chars.ipynb", "Morphotope Characters"),
]

GLOBAL_NOTEBOOK = (9, "09_clustering.ipynb", "Hierarchical Taxonomy Clustering (global, pooled)")

PER_REGION_TAIL_NOTEBOOKS = [
    (10, "09b_map_to_cells.ipynb", "Map Shared Taxonomy to Tessellation Cells"),
    (11, "10_noise.ipynb", "Noise Reassignment"),
    (12, "11_export.ipynb", "Final Export"),
]

# One output file per phase that only exists once that phase finished
# writing (i.e. the phase's *last* save call). Used to resume an interrupted
# multi-day run without redoing already-completed phases/regions — a run
# killed mid-region just needs its checkpoint files checked to know where to
# pick back up. Paths are relative to a region's own OUTPUT_ROOT.
LOCAL_PHASE_CHECKPOINTS = {
    1: "01_preprocessed/buildings.gpkg",
    2: "02_tessellation/tessellation.parquet",
    3: "03_graphs/tessellation_graph.parquet",
    4: "04_chars/tessellations_chars.parquet",
    5: "05_primary_chars/primary_chars.parquet",
    6: "06_morphotopes/data_morphotopes.parquet",
    7: "06_morphotopes/data_morphotopes_postprocessed.parquet",
    8: "08_morphotope_chars/morph_chars.parquet",
}
LOCAL_END = max(LOCAL_PHASE_CHECKPOINTS)

TAIL_PHASE_CHECKPOINTS = {
    10: "09_hierarchy/tessellation_clusters.parquet",
    11: "09_hierarchy/tessellation_clusters_final.parquet",
    # 12 (export) filename includes city_slug/rid — checked separately.
}


def region_progress(region_dir, checkpoints):
    """Highest phase N such that every phase <= N has its checkpoint file on
    disk (checked in order — a missing earlier file forces regeneration of
    everything after it too, since later phases depend on earlier outputs)."""
    done = 0
    for num in sorted(checkpoints):
        if (Path(region_dir) / checkpoints[num]).exists():
            done = num
        else:
            break
    return done


class NotebookFailure(RuntimeError):
    """Raised when a per-region notebook phase fails, so the region loop can
    catch it and skip to the next region instead of killing the whole run."""


def run_notebook(notebooks_dir, filename, label, env, timeout, tag="", log_dir=None):
    """Run one notebook phase via nbconvert, teeing its output live to the
    console *and* to a log file under log_dir (if given).

    The log file matters more than it looks: nbconvert executes the same
    shared notebooks_buidings/*.ipynb file in place for every region, so a
    failed region's traceback only ever exists in the *next* region's
    execution overwriting it — there is no per-region record unless we
    capture it ourselves. Without this, a region that fails partway through
    an unattended multi-day run leaves no trace of why (this happened: see
    region 1217 in the Canada run — it silently stalled at phase 1 with no
    recoverable error message once later regions had run).
    """
    path = Path(notebooks_dir) / filename
    if not path.exists():
        raise NotebookFailure(f"Notebook not found: {path}")

    print(f"\n{'-' * 60}")
    print(f"  {tag}{label}")
    print(f"  {filename}")
    print(f"{'-' * 60}")

    log_path = None
    if log_dir is not None:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        safe_tag = "".join(c if c.isalnum() or c in "-_" else "_" for c in tag.strip(": "))
        log_path = Path(log_dir) / f"{safe_tag}_{Path(filename).stem}.log"

    t0 = time.time()
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "nbconvert",
            "--to", "notebook", "--execute", "--inplace",
            "--ExecutePreprocessor.timeout", str(timeout),
            str(path),
        ],
        cwd=str(Path(notebooks_dir).parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    logf = open(log_path, "w", encoding="utf-8", errors="replace") if log_path else None
    try:
        for line in proc.stdout:
            print(line, end="")
            if logf:
                logf.write(line)
        proc.wait()
    finally:
        if logf:
            logf.close()
    elapsed = time.time() - t0

    if proc.returncode != 0:
        suffix = f" — see {log_path}" if log_path else ""
        raise NotebookFailure(f"{tag}{filename} failed (exit code {proc.returncode}){suffix}")

    print(f"  done in {elapsed / 60:.1f} min")
    return elapsed


def load_regions(shapefile_path, id_col, target_crs):
    regions = gpd.read_file(shapefile_path)
    if id_col not in regions.columns:
        raise KeyError(
            f"Region id column '{id_col}' not found in {shapefile_path}. "
            f"Available columns: {list(regions.columns)}. Pass --region-id-col."
        )
    regions = regions.to_crs(target_crs)
    regions[id_col] = regions[id_col].astype(str).str.replace(r"[^A-Za-z0-9_-]", "_", regex=True)

    n_invalid = (~regions.geometry.is_valid).sum()
    if n_invalid:
        print(f"  Fixing {n_invalid} invalid region geometries (make_valid)")
        regions["geometry"] = regions.geometry.make_valid()

    # Some region datasets split one true area into multiple rows sharing the
    # same id — e.g. StatCan's CMA/CA boundaries give Ottawa-Gatineau,
    # Lloydminster, Hawkesbury, and Campbellton one row per province, all
    # under the same CMAUID (since they straddle a provincial line). Downstream
    # code keys each region's output folder by id alone, so leaving duplicates
    # as-is would make the second row silently overwrite the first's outputs
    # — and would re-split exactly the kind of cross-boundary metro this
    # region-chunked approach exists to keep whole. Dissolve them into one
    # multi-part polygon per id instead.
    dupe_ids = regions[id_col][regions[id_col].duplicated(keep=False)].unique()
    if len(dupe_ids):
        print(f"  Dissolving {len(dupe_ids)} region ids split across multiple rows: {sorted(dupe_ids)}")
        regions = regions.dissolve(by=id_col, as_index=False)

    return regions


def prepare_region_boundary(root, rid, geometry, target_crs, buffer_m):
    """Write buffered + unbuffered boundary files for one region."""
    region_dir = Path(root) / "regions" / rid
    region_dir.mkdir(parents=True, exist_ok=True)

    gpd.GeoDataFrame(geometry=[geometry], crs=target_crs).to_file(
        region_dir / "boundary_unbuffered.gpkg", driver="GPKG"
    )
    gpd.GeoDataFrame(geometry=[geometry.buffer(buffer_m)], crs=target_crs).to_file(
        region_dir / "boundary_buffered.gpkg", driver="GPKG"
    )
    return region_dir


def compute_core_mask(root, rid):
    """After phase 1 for a region, flag which buildings fall inside the
    region's TRUE (unbuffered) boundary vs only its buffer ring."""
    region_dir = Path(root) / "regions" / rid
    buildings_path = region_dir / "01_preprocessed" / "buildings.gpkg"
    buildings = gpd.read_file(buildings_path)
    unbuffered = gpd.read_file(region_dir / "boundary_unbuffered.gpkg")
    core = buildings.geometry.centroid.within(unbuffered.union_all())
    pd.DataFrame({"core": core.values}).to_parquet(
        region_dir / "01_preprocessed" / "core_mask.parquet"
    )
    print(f"  [{rid}] core buildings: {int(core.sum()):,} / {len(core):,}")


def merge_morphotopes(root, region_ids):
    """Pool per-region morphotope-level tables into the global (root-level)
    input files phase 9 reads, prefixing morphotope labels with the region
    id so labels stay unique across regions. Idempotent: safe to re-run."""
    all_data, all_chars, used = [], [], []

    for rid in region_ids:
        region_dir = Path(root) / "regions" / rid
        morph_dir = region_dir / "06_morphotopes"
        chars_dir = region_dir / "08_morphotope_chars"

        labels_path = morph_dir / "tessellation_labels_postprocessed.parquet"
        data_path = morph_dir / "data_morphotopes_postprocessed.parquet"
        chars_path = chars_dir / "morph_chars.parquet"
        if not (labels_path.exists() and data_path.exists() and chars_path.exists()):
            print(f"  [WARNING] Region {rid} missing phase 6-8 outputs — skipping in merge")
            continue

        prefix = f"R{rid}_"

        labels = pd.read_parquet(labels_path)
        already_prefixed = labels["morphotope_label"].astype(str).str.startswith(prefix).all()
        if not already_prefixed:
            labels["morphotope_label"] = prefix + labels["morphotope_label"].astype(str)
            labels.to_parquet(labels_path)

        data = pd.read_parquet(data_path)
        if not str(data.index[0]).startswith(prefix):
            data.index = prefix + data.index.astype(str)
            data.to_parquet(data_path)

        chars = pd.read_parquet(chars_path)
        if not str(chars.index[0]).startswith(prefix):
            chars.index = prefix + chars.index.astype(str)
            chars.to_parquet(chars_path)

        all_data.append(data)
        all_chars.append(chars)
        used.append(rid)

    if not all_data:
        raise RuntimeError("No regions had complete phase 6-8 outputs — nothing to merge.")

    merged_data = pd.concat(all_data)
    merged_chars = pd.concat(all_chars)

    (Path(root) / "06_morphotopes").mkdir(parents=True, exist_ok=True)
    (Path(root) / "08_morphotope_chars").mkdir(parents=True, exist_ok=True)
    merged_data.to_parquet(Path(root) / "06_morphotopes" / "data_morphotopes_postprocessed.parquet")
    merged_chars.to_parquet(Path(root) / "08_morphotope_chars" / "morph_chars.parquet")
    print(f"Merged {len(used)}/{len(region_ids)} regions: {len(merged_data):,} morphotopes total")


def merge_exports(root, region_ids, city_slug):
    """Pool final per-region building exports into one country-wide
    GeoPackage, dropping buffer-ring duplicate buildings via core_mask.

    Note: this merges the building-level layer only. Morphotope polygons are
    not reconciled across region seams here — a morphotope straddling a
    buffered boundary will still exist as separate (possibly differently
    shaped) polygons in each neighbouring region's own export. Add a
    geometry-reconciliation pass if you need seamless morphotope polygons.
    """
    all_buildings = []
    for rid in region_ids:
        region_dir = Path(root) / "regions" / rid
        gpkg = region_dir / "11_exports" / f"{city_slug}_{rid}_taxonomy.gpkg"
        core_mask_path = region_dir / "01_preprocessed" / "core_mask.parquet"
        if not gpkg.exists():
            print(f"  [WARNING] Region {rid} has no final export — skipping")
            continue

        bldg = gpd.read_file(gpkg, layer="buildings")
        core = pd.read_parquet(core_mask_path)["core"]
        if len(core) != len(bldg):
            print(
                f"  [WARNING] Region {rid}: core_mask ({len(core)}) and exported "
                f"buildings ({len(bldg)}) length mismatch — skipping dedup for this region"
            )
        else:
            bldg = bldg.iloc[core.values].copy()

        bldg["region_id"] = rid
        all_buildings.append(bldg)

    if not all_buildings:
        raise RuntimeError("No regions had a final export — nothing to merge.")

    merged = pd.concat(all_buildings, ignore_index=True)
    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=all_buildings[0].crs)

    out_dir = Path(root) / "11_exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{city_slug}_taxonomy_merged.gpkg"
    merged.to_file(out_path, layer="buildings", driver="GPKG")
    print(f"Merged export: {len(merged):,} buildings -> {out_path}")
    return out_path


def run_region_pipeline(
    notebooks_dir, base_env, root, city_slug,
    regions_shapefile, region_id_col, target_crs, buffer_m, timeout,
    start=1, end=12, resume=True,
):
    """Full region-chunked pipeline: phases 1-8 per region, one global phase
    9, then phases 9b/10/11 per region, then a final merged export.

    With resume=True (default), every region/phase already checkpointed on
    disk is skipped instead of redone — safe to just re-run the exact same
    command after an interruption (killed terminal, crash, reboot) partway
    through a long country-scale run. Pass resume=False to force a clean
    rebuild of everything in [start, end].
    """
    regions = load_regions(regions_shapefile, region_id_col, target_crs)
    region_ids = regions[region_id_col].tolist()
    print(f"Loaded {len(region_ids)} regions from {regions_shapefile}")

    total_start = time.time()
    failed_regions = {}
    n_skipped = 0

    # --- Phases 1-8, per region ---
    # A single degenerate region (e.g. an uninhabited northern census
    # division with ~0 buildings) shouldn't kill a 293-region run — log it
    # and move on. It's simply excluded from the later merge/global steps
    # (merge_morphotopes/merge_exports already skip regions missing outputs).
    if start <= LOCAL_END:
        for i, (rid, geometry) in enumerate(zip(region_ids, regions.geometry), start=1):
            region_dir = Path(root) / "regions" / rid
            done = region_progress(region_dir, LOCAL_PHASE_CHECKPOINTS) if resume else 0
            phase_start = max(start, done + 1)

            if phase_start > min(end, LOCAL_END):
                n_skipped += 1
                print(f"[{i}/{len(region_ids)}] {rid}: already complete through phase {done} — skipping")
                continue

            print(f"\n{'=' * 60}")
            resume_note = f" (resuming from phase {phase_start}; 1-{done} already done)" if done else ""
            print(f"  Region {i}/{len(region_ids)}: {rid}{resume_note}")
            print(f"{'=' * 60}")

            region_dir = prepare_region_boundary(root, rid, geometry, target_crs, buffer_m)

            env = base_env.copy()
            env["OUTPUT_ROOT"] = str(region_dir)
            env["BOUNDARY_FILE"] = str(region_dir / "boundary_buffered.gpkg")
            env["CITY_SLUG"] = f"{city_slug}_{rid}"

            try:
                for num, filename, label in LOCAL_NOTEBOOKS:
                    if phase_start <= num <= end:
                        run_notebook(notebooks_dir, filename, label, env, timeout, tag=f"[{rid}] Phase {num}: ", log_dir=Path(root) / "logs")
                        if num == 1:
                            compute_core_mask(root, rid)
            except NotebookFailure as e:
                print(f"\n[SKIPPING REGION {rid}] {e}")
                failed_regions[rid] = str(e)
                continue

    if n_skipped:
        print(f"\nResume: skipped {n_skipped}/{len(region_ids)} regions already complete through phase {LOCAL_END}")

    ok_region_ids = [rid for rid in region_ids if rid not in failed_regions]

    # --- Global merge + global clustering ---
    # NOT wrapped in try/except: this step must succeed for the run to mean
    # anything (a broken shared taxonomy silently propagates into every
    # region), so a failure here aborts the whole pipeline instead of being
    # skipped like a single bad region above.
    if start <= 9 <= end:
        global_done = resume and (Path(root) / "09_hierarchy" / "cluster_mapping.parquet").exists() \
            and (Path(root) / "09_hierarchy" / "cdata.parquet").exists()
        if global_done:
            print(f"\n{'=' * 60}")
            print("  Global taxonomy (phase 9) already computed — skipping merge + re-clustering")
            print(f"{'=' * 60}")
        else:
            print(f"\n{'=' * 60}")
            print("  Merging per-region morphotope tables (global taxonomy input)")
            print(f"{'=' * 60}")
            merge_morphotopes(root, ok_region_ids)

            global_env = base_env.copy()
            global_env["OUTPUT_ROOT"] = str(root)
            num, filename, label = GLOBAL_NOTEBOOK
            run_notebook(notebooks_dir, filename, label, global_env, timeout, tag="[GLOBAL] Phase 9: ", log_dir=Path(root) / "logs")

    # --- Phases 9b/10/11, per region, against the shared global taxonomy ---
    if end >= 10:
        for i, rid in enumerate(ok_region_ids, start=1):
            region_dir = Path(root) / "regions" / rid
            tail_checkpoints = dict(TAIL_PHASE_CHECKPOINTS)
            tail_checkpoints[12] = f"11_exports/{city_slug}_{rid}_taxonomy.gpkg"
            done = region_progress(region_dir, tail_checkpoints) if resume else 0
            # tail_checkpoints keys start at 10, so an untouched region has
            # no phase-9 entry to anchor "done" to — treat "nothing done" as
            # phase 9 (global) already satisfies the prerequisite.
            phase_start = max(start, 10, done + 1)

            if phase_start > end:
                print(f"[{i}/{len(ok_region_ids)}] {rid}: tail phases already complete — skipping")
                continue

            env = base_env.copy()
            env["OUTPUT_ROOT"] = str(region_dir)
            env["GLOBAL_HIER_DIR"] = str(root)
            env["CITY_SLUG"] = f"{city_slug}_{rid}"

            try:
                for num, filename, label in PER_REGION_TAIL_NOTEBOOKS:
                    if phase_start <= num <= end:
                        run_notebook(notebooks_dir, filename, label, env, timeout, tag=f"[{rid}] Phase {num}: ", log_dir=Path(root) / "logs")
            except NotebookFailure as e:
                print(f"\n[SKIPPING REGION {rid}] {e}")
                failed_regions[rid] = str(e)
                continue

    # --- Final merged export ---
    if end >= 12:
        print(f"\n{'=' * 60}")
        print("  Merging final per-region exports")
        print(f"{'=' * 60}")
        merge_exports(root, [rid for rid in region_ids if rid not in failed_regions], city_slug)

    total = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"  REGION PIPELINE COMPLETE  ({total / 60:.1f} min total)")
    if failed_regions:
        print(f"  {len(failed_regions)}/{len(region_ids)} regions FAILED and were skipped:")
        for rid, reason in failed_regions.items():
            print(f"    - {rid}: {reason}")
    print(f"{'=' * 60}")
