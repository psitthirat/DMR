"""Check an analysis root against reproducibility/baseline.json (sha256 only).

Usage (from the analysis root):
    python3 tools/check_baseline.py            # inputs and outputs
    python3 tools/check_baseline.py --inputs   # only the data files (right after copying)
    python3 tools/check_baseline.py --write    # record a new baseline for this machine
    --baseline FILE                            # compare with (or write) another baseline file

Exit code 0 when every listed file matches. Figures are listed for information only:
PNG bytes depend on the fonts installed, so they are not part of the check.
"""
import argparse
import getpass
import hashlib
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ["data/case_report/*", "data/corrections/*"]
OUTPUTS = ["data/processed/*.csv", "outputs/tables/*.csv", "docs/data/evidence.json"]
INFO = ["outputs/figures/*.png"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def collect(patterns):
    out = {}
    for pat in patterns:
        for p in sorted(ROOT.glob(pat)):
            if p.is_file() and p.name != ".DS_Store":
                out[str(p.relative_to(ROOT))] = sha(p)
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--inputs", action="store_true")
ap.add_argument("--write", action="store_true")
ap.add_argument("--baseline", type=Path, default=ROOT / "reproducibility" / "baseline.json")
a = ap.parse_args()
BASE = a.baseline

if a.write:
    BASE.parent.mkdir(exist_ok=True)
    BASE.write_text(json.dumps({
        "made_on": getpass.getuser() + " Mac, " + platform.platform() + ", Python " + platform.python_version(),
        "note": "Coded data (identifiers replaced before transfer). MICE seed 20261112 in notebook 02.",
        "inputs": collect(INPUTS), "outputs": collect(OUTPUTS), "figures_info_only": collect(INFO),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", BASE)
    sys.exit(0)

base = json.loads(BASE.read_text(encoding="utf-8"))
groups = [("inputs", INPUTS)] + ([] if a.inputs else [("outputs", OUTPUTS)])
bad = 0
for name, pats in groups:
    now = collect(pats)
    want = base[name]
    missing = sorted(set(want) - set(now))
    extra = sorted(set(now) - set(want))
    differ = sorted(k for k in want if k in now and now[k] != want[k])
    ok = len(want) - len(missing) - len(differ)
    print(f"{name}: {ok}/{len(want)} match" + (f"; missing {missing}" if missing else "")
          + (f"; differ {differ}" if differ else "") + (f"; not in baseline {extra}" if extra else ""))
    bad += len(missing) + len(differ)
if not a.inputs:
    figs = collect(INFO)
    same = sum(1 for k, v in figs.items() if base["figures_info_only"].get(k) == v)
    print(f"figures (information only): {same}/{len(base['figures_info_only'])} byte-identical")
print("ALL MATCH" if bad == 0 else f"{bad} MISMATCH(ES): compare numbers with tools/compare_runs.py")
sys.exit(0 if bad == 0 else 1)
