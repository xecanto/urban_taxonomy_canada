"""
Master pipeline runner — executes all 7 phases in order.
Run from the project root:
  cd c:\urban-form\urban_taxonomy
  .venv\Scripts\python.exe scripts/run_pipeline.py

To run a single phase:
  .venv\Scripts\python.exe scripts/run_pipeline.py --start 3 --end 3
"""

import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = [
    (1, "01_preprocess.py",   "Preprocessing"),
    (2, "02_tessellation.py", "Morphological Tessellation"),
    (3, "03_morphometrics.py","Morphometric Features"),
    (4, "04_clustering.py",   "UMAP + HDBSCAN Clustering"),
    (5, "05_morphotopes.py",  "SA3 Spatial Regionalization"),
    (6, "06_taxonomy.py",     "Hierarchical Taxonomy"),
    (7, "07_export.py",       "Final Exports"),
]

def run_phase(phase_num, script_name, phase_label):
    script_path = Path("scripts") / script_name
    print(f"\n{'='*60}")
    print(f"  Phase {phase_num}/7 : {phase_label}")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        check=False,
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n[ERROR] Phase {phase_num} failed (exit code {result.returncode})")
        sys.exit(result.returncode)
    print(f"\n  Phase {phase_num} completed in {elapsed/60:.1f} min")
    return elapsed


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end",   type=int, default=7)
    args = parser.parse_args()

    total_start = time.time()
    for num, script, label in SCRIPTS:
        if args.start <= num <= args.end:
            run_phase(num, script, label)

    total = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  ALL PHASES COMPLETE  ({total/60:.1f} min total)")
    print(f"  Final outputs: outputs/07_exports/")
    print(f"{'='*60}")
