r"""Small Flask API for serving the generated PMTiles export.

Run from the project root:
  .venv\Scripts\python.exe app.py

The PMTiles file is served at /tiles and a small metadata endpoint is available at /api/tiles.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_file


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PMtiles = BASE_DIR / "outputs" / "11_exports" / "winnipeg.pmtiles"


def _resolve_pmtiles_path() -> Path:
    configured = os.environ.get("PMTILES_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_PMtiles


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


@app.get("/api/tiles")
def tiles_info():
    pmtiles_path = _resolve_pmtiles_path()
    return {
        "url": "/tiles",
        "file": str(pmtiles_path),
    }


@app.get("/tiles")
def tiles_file():
    pmtiles_path = _resolve_pmtiles_path()
    if not pmtiles_path.exists():
        return jsonify({"error": f"PMTiles file not found: {pmtiles_path}"}), 404

    return send_file(
        pmtiles_path,
        mimetype="application/vnd.pmtiles",
        as_attachment=False,
        download_name=pmtiles_path.name,
        conditional=True,
        etag=True,
    )


@app.route("/tiles", methods=["OPTIONS"])
def tiles_preflight():
    return ("", 204)


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=True)