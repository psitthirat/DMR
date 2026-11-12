"""Clear outputs and execution counts from the notebooks before they are committed.

Usage: python3 tools/strip_notebooks.py [NOTEBOOK ...]   (default: notebooks/*.ipynb)
tools/run_pipeline.sh writes executed copies to outputs/notebooks/, so the
committed notebooks normally have no outputs; this is the fix when they do.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
paths = [Path(p) for p in sys.argv[1:]] or sorted((ROOT / "notebooks").glob("*.ipynb"))
for path in paths:
    nb = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            if cell.get("outputs") or cell.get("execution_count") is not None:
                changed += 1
            cell["outputs"] = []
            cell["execution_count"] = None
        cell.get("metadata", {}).pop("execution", None)
    nb.get("metadata", {}).pop("widgets", None)
    path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{path.name}: cleared {changed} cell(s)")
