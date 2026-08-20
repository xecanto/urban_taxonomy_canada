#!/usr/bin/env bash
# Build one merged, country-wide PMTiles archive (z0-z18) from the per-region
# exports scripts/export_region_geojsonl.py + scripts/build_pmtiles.sh
# already produced. Run from WSL:
#
#   cd /mnt/c/urban-form/urban_taxonomy
#   bash scripts/build_merged_pmtiles.sh
#   TILES_DIR=/mnt/c/urban-form/urban_taxonomy_viewer/tiles_nochm bash scripts/build_merged_pmtiles.sh
#
# Two steps, kept separate deliberately so re-running after a region-level
# rebuild doesn't mean re-tiling the whole country from scratch:
#   1. A fresh low-zoom (z0-z7) overview, tiled once from every region's
#      buildings.geojsonl combined — tippecanoe's default feature/tile-size
#      dropping is exactly what you want at country-overview zooms, so this
#      does NOT pass --no-feature-limit/--no-tile-size-limit.
#   2. tile-join merges that overview with the existing per-region z8-z18
#      PMTiles (built separately, per region, by build_pmtiles.sh) into one
#      z0-z18 archive. tile-join only copies/recombines already-built tiles
#      (no re-simplification), so this step is comparatively fast even
#      though the country-wide z8-z18 build itself took hours.
#
# --no-tile-size-limit on the tile-join step matters: without it, tile-join
# silently DROPS any merged tile whose combined size exceeds its default
# 500KB cap (hit this in practice on est z9/z10 tiles where several
# regions' data combines into one tile) instead of erroring, which is easy
# to miss.
set -uo pipefail

TILES_DIR="${TILES_DIR:-/mnt/c/urban-form/urban_taxonomy_viewer/tiles}"
MINZOOM_OVERVIEW="${MINZOOM_OVERVIEW:-0}"
MAXZOOM_OVERVIEW="${MAXZOOM_OVERVIEW:-7}"
OUT_NAME="${OUT_NAME:-canada.pmtiles}"

if ! command -v tippecanoe >/dev/null 2>&1 || ! command -v tile-join >/dev/null 2>&1; then
    echo "tippecanoe/tile-join not found on PATH (expected in WSL)." >&2
    exit 1
fi

if [ ! -d "$TILES_DIR" ]; then
    echo "Tiles directory not found: $TILES_DIR" >&2
    exit 1
fi

cd "$TILES_DIR" || exit 1

shopt -s nullglob
geojsonl_files=(*/buildings.geojsonl)
pmtiles_files=(*/buildings.pmtiles)
if [ ${#geojsonl_files[@]} -eq 0 ] || [ ${#pmtiles_files[@]} -eq 0 ]; then
    echo "No per-region buildings.geojsonl / buildings.pmtiles found under $TILES_DIR" >&2
    exit 1
fi
echo "Found ${#geojsonl_files[@]} region geojsonl files, ${#pmtiles_files[@]} region pmtiles files."

# Must end in .pmtiles: tippecanoe/tile-join pick their output container
# format (native PMTiles vs. MBTiles/SQLite) from the -o filename's
# extension, not from the final destination name. A ".tmp" suffix here has
# bitten this exact pipeline before (see build_pmtiles.sh) — it silently
# writes MBTiles/SQLite, which a later `mv` then just renames to *.pmtiles
# without converting it, and pmtiles.js rejects the result at load time
# ("Wrong magic number").
overview="tmp.overview_z${MINZOOM_OVERVIEW}_${MAXZOOM_OVERVIEW}.pmtiles"
merged_hi="tmp.merged_hi_zoom.pmtiles"

echo "[1/2] Building z${MINZOOM_OVERVIEW}-z${MAXZOOM_OVERVIEW} overview from ${#geojsonl_files[@]} regions..."
t0=$(date +%s)
if ! tippecanoe -o "$overview" -f -q \
    -Z"$MINZOOM_OVERVIEW" -z"$MAXZOOM_OVERVIEW" \
    -l buildings \
    "${geojsonl_files[@]}"; then
    echo "  FAILED building overview" >&2
    rm -f "$overview"
    exit 1
fi
echo "  done in $(( $(date +%s) - t0 ))s -> $overview ($(du -h "$overview" | cut -f1))"

echo "[2/2] Merging overview + ${#pmtiles_files[@]} per-region z8-z18 tiles..."
t0=$(date +%s)
if ! tile-join -f -q --no-tile-size-limit -o "$merged_hi" "$overview" "${pmtiles_files[@]}"; then
    echo "  FAILED merging" >&2
    rm -f "$overview" "$merged_hi"
    exit 1
fi
mv -f "$merged_hi" "$OUT_NAME"
rm -f "$overview"
echo "  done in $(( $(date +%s) - t0 ))s -> $TILES_DIR/$OUT_NAME ($(du -h "$OUT_NAME" | cut -f1))"

echo ""
echo "============================================================"
echo "  Merged archive ready: $TILES_DIR/$OUT_NAME"
echo "============================================================"
