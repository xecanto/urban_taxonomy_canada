r"""Small Flask API for serving the generated per-region PMTiles exports.

Run from the project root:
  .venv\Scripts\python.exe app.py

Serves tiles/ (the CHM run) and tiles_nochm/ (same 152 regions/slugs, same
taxonomy, no CHM columns) — both produced by
scripts/export_region_geojsonl.py + scripts/build_pmtiles.sh — directly
under their own folder name, e.g.:

  GET /tiles/winnipeg/buildings.pmtiles
  GET /tiles/regions_manifest.json
  GET /tiles_nochm/winnipeg/buildings.pmtiles

This mirrors the exact URL layout the static files will have once uploaded
to a real host — the viewer only ever needs TILES_BASE_URL (see
urban_taxonomy_viewer/src/config/regions.ts) to change, not the paths.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, request, send_from_directory


BASE_DIR = Path(__file__).resolve().parent
VIEWER_ROOT = BASE_DIR.parent / "urban_taxonomy_viewer"
# Whitelisted, not a free-form path segment, so this can't be used to serve
# arbitrary folders from the viewer checkout.
ALLOWED_DATASETS = {"tiles", "tiles_nochm"}


def _resolve_dataset_dir(dataset: str) -> Path:
    configured = os.environ.get(f"{dataset.upper()}_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return VIEWER_ROOT / dataset


app = Flask(__name__)
ALLOWED_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "Access-Control-Request-Headers", "Range, Content-Type"
        )
        response.headers["Access-Control-Expose-Headers"] = (
            "Accept-Ranges, Content-Length, Content-Range, ETag, Content-Type"
        )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/<dataset>/<path:subpath>")
def tiles_file(dataset: str, subpath: str):
    if dataset not in ALLOWED_DATASETS:
        abort(404)
    tiles_dir = _resolve_dataset_dir(dataset)
    if not tiles_dir.exists():
        abort(404, f"Tiles directory not found: {tiles_dir}")

    mimetype = "application/vnd.pmtiles" if subpath.endswith(".pmtiles") else None
    # send_from_directory resolves subpath safely under tiles_dir (rejects
    # any ../ escape) and handles Range requests + conditional GET for us.
    return send_from_directory(
        tiles_dir, subpath,
        mimetype=mimetype,
        conditional=True,
        etag=True,
    )


@app.route("/<dataset>/<path:subpath>", methods=["OPTIONS"])
def tiles_preflight(dataset: str, subpath: str):
    return ("", 204)


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=True)
