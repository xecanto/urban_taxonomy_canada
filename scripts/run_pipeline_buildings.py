"""
Master pipeline runner for the buildings taxonomy notebooks.

Executes notebooks_buidings/01..11 in order, in place, using the same
kernel/venv as this script. Each notebook loads its config (paths, CRS, CHM
toggle, output folder, ...) from a city config file via
scripts/pipeline_config.py, so running for a different city means pointing
at a different config file — not editing notebooks.

Run for the default city (config/winnipeg.env):
    .venv\\Scripts\\python.exe scripts\\run_pipeline_buildings.py

Run for another city (looks up config/<city>.env):
    .venv\\Scripts\\python.exe scripts\\run_pipeline_buildings.py --city calgary

Or point at an arbitrary config file:
    .venv\\Scripts\\python.exe scripts\\run_pipeline_buildings.py --config config/calgary.env

Run a subset of phases (e.g. re-run only clustering onward):
    .venv\\Scripts\\python.exe scripts\\run_pipeline_buildings.py --start 9 --end 11

Override the CHM toggle from the config file for this run only:
    .venv\\Scripts\\python.exe scripts\\run_pipeline_buildings.py --no-chm

Region-chunked run for a whole country (see --regions-shapefile below).
Safe to re-run the exact same command after an interruption — already
completed regions/phases are skipped automatically (see --no-resume):
    .venv\\Scripts\\python.exe scripts\\run_pipeline_buildings.py --city canada --regions-shapefile config/regions.gpkg --region-id-col CDUID --timeout -1
    python scripts\\run_pipeline_buildings.py --city canada --regions-shapefile "C:\\Users\\abdur\\Downloads\\canada\\lcd_000b21a_e\\ca_census.shp" --region-id-col CDUID --timeout -1
    python scripts\\run_pipeline_buildings.py --config config/canada_cma_ca.env --regions-shapefile data\\CMA_CA_boundaries.gdb --region-id-col CMAUID --timeout -1

"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = ROOT / "notebooks_buidings"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_config import DEFAULT_CONFIG

NOTEBOOKS = [
    (1,  "01_preprocess.ipynb",              "Preprocessing"),
    (2,  "02_tessellation.ipynb",             "Morphological Tessellation"),
    (3,  "03_graphs.ipynb",                   "Spatial Graphs"),
    (4,  "04_morphometrics.ipynb",            "Morphometric Characters"),
    (5,  "05_merge_chars.ipynb",              "Merge Characters"),
    (6,  "06_morphotopes.ipynb",              "Morphotopes (SA3 Regionalization)"),
    (7,  "07_morphotope_postprocessing.ipynb", "Morphotope Postprocessing"),
    (8,  "08_morphotope_chars.ipynb",         "Morphotope Characters"),
    (9,  "09_clustering.ipynb",               "UMAP + Clustering"),
    (10, "09b_map_to_cells.ipynb",            "Map Clusters to Tessellation Cells"),
    (11, "10_noise.ipynb",                    "Noise Reassignment"),
    (12, "11_export.ipynb",                   "Final Export"),
]


def run_notebook(num, filename, label, env, timeout):
    path = NOTEBOOKS_DIR / filename
    if not path.exists():
        print(f"\n[ERROR] Notebook not found: {path}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"  Phase {num:>2}/{len(NOTEBOOKS)} : {label}")
    print(f"  {filename}")
    print(f"{'=' * 60}")

    t0 = time.time()
    result = subprocess.run(
        [
            sys.executable, "-m", "nbconvert",
            "--to", "notebook", "--execute", "--inplace",
            "--ExecutePreprocessor.timeout", str(timeout),
            str(path),
        ],
        cwd=str(ROOT),
        env=env,
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"\n[ERROR] Phase {num} ({filename}) failed (exit code {result.returncode})")
        print(f"  Open the notebook to see the full traceback in the failing cell's output.")
        sys.exit(result.returncode)

    print(f"\n  Phase {num} completed in {elapsed / 60:.1f} min")
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=int, default=1, help="First phase to run (1-12)")
    parser.add_argument("--end", type=int, default=len(NOTEBOOKS), help="Last phase to run (1-12)")
    parser.add_argument(
        "--city", default=None,
        help="Shorthand for --config config/<city>.env",
    )
    parser.add_argument(
        "--config", default=None,
        help=f"Path to a city config .env file (default: {DEFAULT_CONFIG}). "
             "See config/template.env for the full list of variables.",
    )
    parser.add_argument(
        "--output-root", default=None,
        help="Override OUTPUT_ROOT from the config file for this run",
    )
    parser.add_argument(
        "--chm", dest="include_chm", action="store_true", default=None,
        help="Force-include CHM canopy attributes, overriding the config file",
    )
    parser.add_argument(
        "--no-chm", dest="include_chm", action="store_false",
        help="Force-exclude CHM canopy attributes, overriding the config file",
    )
    parser.add_argument(
        "--timeout", type=int, default=3600,
        help="Per-cell execution timeout in seconds (default: 3600). Pass -1 to disable.",
    )
    parser.add_argument(
        "--regions-shapefile", default=None,
        help="Path to a polygon shapefile/GeoPackage of sub-regions (e.g. CMA/CA "
             "boundaries). When set, the pipeline runs in region-chunked mode: "
             "phases 1-8 run independently per region, morphotope characteristics "
             "are pooled for one global clustering pass (phase 9), then phases "
             "9b/10/11 run per region against that shared taxonomy, and a final "
             "merged export is written. Use this for country/large-area runs that "
             "would otherwise exceed memory in a single unified run.",
    )
    parser.add_argument(
        "--region-id-col", default="id",
        help="Column in --regions-shapefile holding each region's unique id (default: id)",
    )
    parser.add_argument(
        "--buffer-m", type=float, default=500.0,
        help="Metres to buffer each region's boundary outward before clipping, so "
             "tessellation/graph context isn't truncated exactly at the region edge "
             "(default: 500). Buildings only within the buffer ring are dropped "
             "again at the final merge via core_mask.parquet.",
    )
    parser.add_argument(
        "--no-resume", dest="resume", action="store_false", default=True,
        help="Region-chunked mode only. By default, re-running the same command "
             "after an interruption skips any region/phase whose output already "
             "exists on disk (checkpoint files) instead of redoing it. Pass "
             "--no-resume to force a clean rebuild of everything in [start, end].",
    )
    args = parser.parse_args()

    if args.city and args.config:
        parser.error("Pass either --city or --config, not both")
    config_path = args.config or (f"config/{args.city}.env" if args.city else DEFAULT_CONFIG)

    env = os.environ.copy()
    env["CITY_CONFIG"] = config_path
    if args.output_root is not None:
        env["OUTPUT_ROOT"] = args.output_root
    if args.include_chm is not None:
        env["INCLUDE_CHM"] = "1" if args.include_chm else "0"

    # Peek at the config file just to print a helpful summary; notebooks do
    # the real loading themselves (env vars set above still take precedence).
    preview_env = {}
    resolved = Path(ROOT) / config_path
    if resolved.exists():
        for line in resolved.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                preview_env[k.strip()] = v.strip()
    else:
        print(f"[WARNING] Config file not found: {resolved} — notebooks will fall back to their built-in Winnipeg defaults.")

    city_name = env.get("CITY_NAME") or preview_env.get("CITY_NAME", "?")
    city_slug = env.get("CITY_SLUG") or preview_env.get("CITY_SLUG", city_name.lower())
    include_chm = env.get("INCLUDE_CHM") or preview_env.get("INCLUDE_CHM", "1")
    output_root = env.get("OUTPUT_ROOT") or preview_env.get("OUTPUT_ROOT", "outputs")
    target_crs = env.get("TARGET_CRS") or preview_env.get("TARGET_CRS", "EPSG:3978")

    print(f"Buildings taxonomy pipeline — phases {args.start}-{args.end}")
    print(f"City config : {config_path}")
    print(f"City        : {city_name}")
    print(f"CHM canopy  : {'included' if include_chm.strip().lower() not in ('0', 'false', 'no') else 'EXCLUDED'}")
    print(f"Output root : {output_root}")

    if args.regions_shapefile:
        print(f"Mode        : region-chunked ({args.regions_shapefile}, buffer={args.buffer_m}m)")
        print(f"Resume      : {'ON (skipping already-complete regions/phases)' if args.resume else 'OFF (forcing full rebuild)'}")
        from region_pipeline import run_region_pipeline
        run_region_pipeline(
            notebooks_dir=NOTEBOOKS_DIR,
            base_env=env,
            root=output_root,
            city_slug=city_slug,
            regions_shapefile=args.regions_shapefile,
            region_id_col=args.region_id_col,
            target_crs=target_crs,
            buffer_m=args.buffer_m,
            timeout=args.timeout,
            start=args.start,
            end=args.end,
            resume=args.resume,
        )
        return

    total_start = time.time()
    for num, filename, label in NOTEBOOKS:
        if args.start <= num <= args.end:
            run_notebook(num, filename, label, env, args.timeout)

    total = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"  ALL PHASES COMPLETE  ({total / 60:.1f} min total)")
    print(f"  Final outputs: {output_root}/11_exports/")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
