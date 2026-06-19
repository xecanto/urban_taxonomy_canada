"""Convert pipeline .py scripts to Jupyter notebooks, splitting on section markers."""
import json
import re
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

def make_cell(cell_type, source_lines, cell_id=None):
    cell = {
        "cell_type": cell_type,
        "id": cell_id or uuid.uuid4().hex[:8],
        "metadata": {},
        "source": source_lines,
    }
    if cell_type == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
    return cell

def py_to_notebook(py_path: Path, out_path: Path):
    text = py_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    cells = []

    # Extract the docstring as the first markdown cell
    if lines[0].startswith('"""'):
        doc_lines = []
        i = 0
        # multi-line docstring
        if lines[0].count('"""') == 1:
            doc_lines.append(lines[0].replace('"""', '').strip())
            i = 1
            while i < len(lines) and '"""' not in lines[i]:
                doc_lines.append(lines[i])
                i += 1
            i += 1  # skip closing """
        else:
            doc_lines.append(lines[0].replace('"""', '').strip())
            i = 1

        # Skip blank lines after docstring
        while i < len(lines) and lines[i].strip() == "":
            i += 1

        md_text = "\n".join(doc_lines).strip()
        if md_text:
            md_source = ["# " + md_text.split("\n")[0] + "\n"]
            for dl in md_text.split("\n")[1:]:
                md_source.append(dl + "\n")
            # Remove trailing \n from last line
            if md_source:
                md_source[-1] = md_source[-1].rstrip("\n")
            cells.append(make_cell("markdown", md_source))

        remaining_lines = lines[i:]
    else:
        remaining_lines = lines

    # Now split remaining code on section markers: # ── N. ...
    section_pattern = re.compile(r"^# ── \d")
    current_chunk = []
    current_header = None

    def flush_chunk():
        nonlocal current_chunk, current_header
        # Strip leading/trailing blank lines
        while current_chunk and current_chunk[0].strip() == "":
            current_chunk.pop(0)
        while current_chunk and current_chunk[-1].strip() == "":
            current_chunk.pop()

        if not current_chunk:
            current_chunk = []
            current_header = None
            return

        if current_header:
            # Extract section title from the marker line
            title = re.sub(r"^# ── \d+[./]\d*\s*", "", current_header)
            title = title.strip().rstrip("─").strip()
            if title:
                cells.append(make_cell("markdown", [f"## {title}"]))

        # Build source lines
        source = []
        for j, line in enumerate(current_chunk):
            if j < len(current_chunk) - 1:
                source.append(line + "\n")
            else:
                source.append(line)
        cells.append(make_cell("code", source))
        current_chunk = []
        current_header = None

    for line in remaining_lines:
        if section_pattern.match(line):
            flush_chunk()
            current_header = line
        else:
            current_chunk.append(line)

    flush_chunk()

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.14.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }

    out_path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  {py_path.name} -> {out_path.name}  ({len(cells)} cells)")


if __name__ == "__main__":
    nb_dir = SCRIPTS_DIR.parent / "notebooks"
    nb_dir.mkdir(exist_ok=True)

    scripts = sorted(SCRIPTS_DIR.glob("[0-9][0-9]_*.py"))
    for s in scripts:
        out = nb_dir / s.with_suffix(".ipynb").name
        py_to_notebook(s, out)

    # Also convert run_pipeline.py
    rp = SCRIPTS_DIR / "run_pipeline.py"
    if rp.exists():
        py_to_notebook(rp, nb_dir / "run_pipeline.ipynb")

    print(f"\nDone. {len(scripts)+1} notebooks written to {nb_dir}")
