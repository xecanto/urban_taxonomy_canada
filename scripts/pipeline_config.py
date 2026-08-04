"""
Tiny .env-style config loader for the buildings taxonomy pipeline.

No external dependency (no python-dotenv) — just enough to keep all the
per-city knobs (input paths, CRS, CHM toggle, output folder name, ...) out
of the notebooks so switching cities means pointing at a different config
file instead of editing 01_preprocess.ipynb etc.

Precedence: real environment variables (e.g. set by run_pipeline_buildings.py
or by hand before launching Jupyter) always win over the config file — the
file only fills in values that aren't already set.
"""

import os
from pathlib import Path

DEFAULT_CONFIG = "config/winnipeg.env"


def load_env_file(path):
    """Parse KEY=VALUE lines from `path` into os.environ (does not overwrite
    keys that are already set). Blank lines and lines starting with # are
    ignored. Values may be wrapped in single or double quotes."""
    path = Path(path)
    if not path.exists():
        print(f"[pipeline_config] No config file at '{path}' — using in-notebook defaults.")
        return path

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value

    return path


def load_city_config():
    """Load the file named by the CITY_CONFIG env var (default: config/winnipeg.env).

    Call this once at the top of each notebook, right after chdir'ing to the
    project root — paths in the config file are relative to project root.
    """
    config_path = os.environ.get("CITY_CONFIG", DEFAULT_CONFIG)
    resolved = load_env_file(config_path)
    print(f"[pipeline_config] City config: {resolved}")
    return resolved
