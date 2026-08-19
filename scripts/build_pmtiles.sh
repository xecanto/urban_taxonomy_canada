#!/usr/bin/env bash
# Batch-build buildings.pmtiles for every region exported by
# scripts/export_region_geojsonl.py. Run from WSL (tippecanoe is installed
# there, not on the Windows side):
#
#   cd /mnt/c/urban-form/urban_taxonomy
#   bash scripts/build_pmtiles.sh
#
# Options (env vars):
#   TILES_DIR   default /mnt/c/urban-form/urban_taxonomy_viewer/tiles
#   MINZOOM     default 8
#   MAXZOOM     default 18
#   FORCE       set to 1 to rebuild pmtiles even if already newer than the geojsonl
#   ONLY        comma-separated region slugs to build (default: all)
set -uo pipefail

TILES_DIR="${TILES_DIR:-/mnt/c/urban-form/urban_taxonomy_viewer/tiles}"
MINZOOM="${MINZOOM:-8}"
MAXZOOM="${MAXZOOM:-18}"
FORCE="${FORCE:-0}"
ONLY="${ONLY:-}"

if ! command -v tippecanoe >/dev/null 2>&1; then
    echo "tippecanoe not found on PATH (expected in WSL)." >&2
    exit 1
fi

if [ ! -d "$TILES_DIR" ]; then
    echo "Tiles directory not found: $TILES_DIR" >&2
    echo "Run scripts/export_region_geojsonl.py from Windows first." >&2
    exit 1
fi

want_slug() {
    local slug="$1"
    [ -z "$ONLY" ] && return 0
    case ",$ONLY," in
        *",$slug,"*) return 0 ;;
        *) return 1 ;;
    esac
}

total=0
built=0
skipped=0
failed=0
failed_slugs=()
t_start=$(date +%s)

for geojsonl in "$TILES_DIR"/*/buildings.geojsonl; do
    [ -e "$geojsonl" ] || continue
    region_dir=$(dirname "$geojsonl")
    slug=$(basename "$region_dir")
    want_slug "$slug" || continue

    total=$((total + 1))
    pmtiles="$region_dir/buildings.pmtiles"

    if [ -f "$pmtiles" ] && [ "$FORCE" != "1" ] && [ "$pmtiles" -nt "$geojsonl" ]; then
        echo "[$total] $slug: buildings.pmtiles up to date — skipping"
        skipped=$((skipped + 1))
        continue
    fi

    echo "[$total] $slug: building pmtiles (z${MINZOOM}-z${MAXZOOM})..."
    t0=$(date +%s)
    # Must end in .pmtiles: tippecanoe picks its output format (native
    # PMTiles vs. MBTiles/SQLite) from the -o filename's extension, not from
    # the final destination name. A ".tmp" suffix here silently produced an
    # MBTiles/SQLite file that a later `mv` just renamed to *.pmtiles without
    # converting it, which pmtiles.js then rejects ("Wrong magic number").
    tmp="$region_dir/buildings.tmp.pmtiles"
    if tippecanoe -o "$tmp" --force -q \
        -Z"$MINZOOM" -z"$MAXZOOM" \
        --no-feature-limit --no-tile-size-limit \
        --detect-shared-borders \
        -l buildings \
        -n "$slug" \
        "$geojsonl"; then
        mv -f "$tmp" "$pmtiles"
        dt=$(( $(date +%s) - t0 ))
        size=$(du -h "$pmtiles" | cut -f1)
        echo "  done in ${dt}s -> $pmtiles ($size)"
        built=$((built + 1))
    else
        echo "  FAILED: $slug"
        rm -f "$tmp"
        failed=$((failed + 1))
        failed_slugs+=("$slug")
    fi
done

elapsed=$(( $(date +%s) - t_start ))
echo ""
echo "============================================================"
echo "  $built built, $skipped skipped (already up to date), $failed failed"
if [ ${#failed_slugs[@]} -gt 0 ]; then
    echo "  FAILED: ${failed_slugs[*]}"
fi
echo "  Total time: $((elapsed / 60))m $((elapsed % 60))s"
echo "============================================================"

[ "$failed" -eq 0 ]
