"""
Export every completed CMA/CA region's buildings layer to GeoJSONSeq, laid
out as one folder per region under the viewer's tile source tree:

    <VIEWER_ROOT>/tiles/<region_slug>/buildings.geojsonl

Folder names come from the region's CMANAME in data/CMA_CA_boundaries.gdb
(slugified), not the numeric CMAUID region id, so the later website can use
human-readable region names directly as folder/route names. tippecanoe (run
separately, from WSL — see scripts/build_pmtiles.sh) then turns each
buildings.geojsonl into buildings.pmtiles in the same folder.

Run from the repo root with the project venv:
    .venv\\Scripts\\python.exe scripts\\export_region_geojsonl.py
    .venv\\Scripts\\python.exe scripts\\export_region_geojsonl.py --force
    .venv\\Scripts\\python.exe scripts\\export_region_geojsonl.py --only 001,535
"""

import argparse
import json
import re
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BOUNDARIES_GDB = ROOT / "data" / "CMA_CA_boundaries.gdb"
REGIONS_DIR = ROOT / "outputs_canada_cma_ca" / "regions"
CITY_SLUG = "canada_cma_ca"  # matches CITY_SLUG used when the region pipeline wrote these exports


def slugify(name):
    # Bilingual CMA/CA names carry a parenthetical province qualifier for
    # the handful of CMAs that straddle a provincial line (e.g. "Ottawa -
    # Gatineau (Ontario part / partie de l'Ontario)") — the region pipeline
    # already dissolves those into one region per CMAUID, so the qualifier
    # is dropped here rather than kept as two near-duplicate slugs.
    name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return slug


def load_region_names():
    gdf = gpd.read_file(BOUNDARIES_GDB)
    gdf["CMAUID"] = gdf["CMAUID"].astype(str)
    # Same-CMAUID duplicate rows (cross-provincial CMAs) collapse to a single
    # region folder — the region pipeline already dissolved them upstream.
    gdf = gdf.drop_duplicates(subset="CMAUID", keep="first")
    names = dict(zip(gdf["CMAUID"], gdf["CMANAME"]))
    types = dict(zip(gdf["CMAUID"], gdf["CMATYPE"]))
    prov = dict(zip(gdf["CMAUID"], gdf["PRUID"]))
    return names, types, prov


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--viewer-root", default=str(ROOT.parent / "urban_taxonomy_viewer"))
    parser.add_argument("--force", action="store_true", help="Re-export even if buildings.geojsonl already exists")
    parser.add_argument("--only", default=None, help="Comma-separated CMAUID region ids to export (default: all)")
    args = parser.parse_args()

    tiles_dir = Path(args.viewer_root) / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    names, types, prov = load_region_names()

    region_dirs = sorted(p for p in REGIONS_DIR.iterdir() if p.is_dir())
    if args.only:
        wanted = set(args.only.split(","))
        region_dirs = [p for p in region_dirs if p.name in wanted]

    only_slugs = {}
    manifest = []
    skipped, failed, done = [], [], []
    t_start = time.time()

    for i, region_dir in enumerate(region_dirs, start=1):
        rid = region_dir.name
        gpkg = region_dir / "11_exports" / f"{CITY_SLUG}_{rid}_taxonomy.gpkg"
        if not gpkg.exists():
            print(f"[{i}/{len(region_dirs)}] {rid}: no export gpkg — skipping")
            skipped.append(rid)
            continue

        name = names.get(rid, rid)
        slug = slugify(name)
        if slug in only_slugs and only_slugs[slug] != rid:
            slug = f"{slug}_{rid}"
        only_slugs[slug] = rid

        out_dir = tiles_dir / slug
        out_path = out_dir / "buildings.geojsonl"
        if out_path.exists() and not args.force:
            print(f"[{i}/{len(region_dirs)}] {rid} ({slug}): buildings.geojsonl already exists — skipping")
            gdf = None
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            try:
                gdf = gpd.read_file(gpkg, layer="buildings")
                if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs(4326)
                if out_path.exists():
                    out_path.unlink()
                gdf.to_file(out_path, driver="GeoJSONSeq")
            except Exception as e:
                print(f"[{i}/{len(region_dirs)}] {rid} ({slug}): FAILED — {e}")
                failed.append(rid)
                continue
            elapsed = time.time() - t0
            print(f"[{i}/{len(region_dirs)}] {rid} ({slug}): {len(gdf):,} buildings -> {out_path} ({elapsed:.1f}s)")
            done.append(rid)

        if gdf is None:
            # Reload just enough to fill in manifest metadata for a skipped region.
            gdf = gpd.read_file(gpkg, layer="buildings", columns=[])

        bounds = gdf.total_bounds.tolist() if len(gdf) else None
        manifest.append({
            "slug": slug,
            "region_id": rid,
            "name": re.sub(r"\s*\(.*?\)\s*$", "", name).strip(),
            "cma_type": types.get(rid),
            "pruid": prov.get(rid),
            "n_buildings": int(len(gdf)),
            "bbox_wgs84": bounds,
        })

    manifest.sort(key=lambda r: r["slug"])
    manifest_path = tiles_dir / "regions_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    total = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"  Exported {len(done)} regions, skipped {len(skipped) + (len(region_dirs) - len(done) - len(skipped) - len(failed))} already-done, {len(failed)} failed")
    if failed:
        print(f"  FAILED: {failed}")
    print(f"  Manifest: {manifest_path}")
    print(f"  Total time: {total / 60:.1f} min")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
