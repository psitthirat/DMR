"""Block anything that could carry patient-level data into this public repository.

Usage:
    python3 tools/precommit_check.py --staged   # files staged for commit (git pre-commit hook)
    python3 tools/precommit_check.py --all      # every tracked file (GitHub Actions)

Install the hook once per clone:  sh tools/install_hooks.sh
Standard library only, so it runs before any environment is set up.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_DIRS = ("data/", "DMR-data/", "outputs/", "reference/", "DMR-key/")
BLOCKED_EXT = {".csv", ".tsv", ".xlsx", ".xls", ".docx", ".parquet", ".feather",
               ".dta", ".sav", ".rds", ".dmg", ".zip", ".pkl", ".pickle", ".sqlite", ".db"}
MAX_BYTES = 2_000_000
# A bare 13-digit integer (Thai national ID length): not part of a decimal, a longer
# number or a hex digest.
THIRTEEN = re.compile(r"(?<![0-9A-Fa-f.])\d{13}(?![0-9A-Fa-f])")
TEXT_EXT = {".py", ".ipynb", ".md", ".js", ".html", ".css", ".json", ".txt", ".sh",
            ".yml", ".yaml", ".toml", ".cfg", ".svg"}


def files(mode):
    if mode == "--staged":
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
    else:
        cmd = ["git", "ls-files", "-z"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def check(path):
    problems = []
    p = ROOT / path
    if path.startswith(BLOCKED_DIRS) or path == "data":
        problems.append("path is a data/output folder")
    if p.suffix.lower() in BLOCKED_EXT:
        problems.append(f"blocked file type {p.suffix}")
    if p.is_symlink():
        problems.append("symlink")
        return problems
    if not p.is_file():
        return problems
    if p.stat().st_size > MAX_BYTES:
        problems.append(f"larger than {MAX_BYTES:,} bytes")
    if p.suffix.lower() == ".ipynb":
        nb = json.loads(p.read_text(encoding="utf-8"))
        for i, cell in enumerate(nb.get("cells", [])):
            if cell.get("outputs") or cell.get("execution_count"):
                problems.append(f"notebook cell {i} has outputs; run tools/strip_notebooks.py")
                break
    if p.suffix.lower() in TEXT_EXT:
        text = p.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if THIRTEEN.search(line):
                problems.append(f"line {n}: bare 13-digit number")
    return problems


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--staged"
    bad = 0
    for path in files(mode):
        for problem in check(path):
            print(f"BLOCKED {path}: {problem}")
            bad += 1
    if bad:
        print(f"{bad} problem(s). Nothing patient-level may enter this public repository.")
        sys.exit(1)
    print("precommit_check: OK")


if __name__ == "__main__":
    main()
