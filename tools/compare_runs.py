"""Compare two DMR analysis roots: result tables, evidence.json and master shape.

Aggregate output only: table cells are already aggregates; for the patient-level
master only shapes and per-column counts of changed cells are printed.

Usage: python -B -I compare_runs.py OLD_ROOT NEW_ROOT [--rtol 1e-9]
"""
import argparse
import json
import math
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("old", type=Path)
ap.add_argument("new", type=Path)
ap.add_argument("--rtol", type=float, default=1e-9)
ap.add_argument("--max-cells", type=int, default=400)
a = ap.parse_args()


def same(x, y):
    if isinstance(x, float) and isinstance(y, float):
        if math.isnan(x) and math.isnan(y):
            return True
        if math.isnan(x) or math.isnan(y):
            return False
        return math.isclose(x, y, rel_tol=a.rtol, abs_tol=1e-12)
    try:
        if pd.isna(x) and pd.isna(y):
            return True
    except (TypeError, ValueError):
        pass
    return x == y


print("# tables")
old_t = sorted((a.old / "outputs/tables").glob("*.csv"))
new_t = {p.name: p for p in (a.new / "outputs/tables").glob("*.csv")}
for p in old_t:
    if p.name not in new_t:
        print(f"{p.name}: MISSING in new")
        continue
    o = pd.read_csv(p, encoding="utf-8-sig")
    n = pd.read_csv(new_t[p.name], encoding="utf-8-sig")
    if list(o.columns) != list(n.columns) or o.shape != n.shape:
        print(f"{p.name}: SHAPE/COLUMNS {o.shape} -> {n.shape}")
        if list(o.columns) != list(n.columns):
            print("   cols old:", list(o.columns))
            print("   cols new:", list(n.columns))
        # still show row-level diff on the common first column
        key = o.columns[0]
        print("   rows only old:", sorted(set(o[key].astype(str)) - set(n[key].astype(str))))
        print("   rows only new:", sorted(set(n[key].astype(str)) - set(o[key].astype(str))))
        continue
    diffs = []
    for i in range(len(o)):
        for c in o.columns:
            if not same(o.at[i, c], n.at[i, c]):
                diffs.append((i, c, o.at[i, c], n.at[i, c]))
    if diffs:
        print(f"{p.name}: {len(diffs)} cells differ")
        for i, c, x, y in diffs[: a.max_cells]:
            lab = " | ".join(str(o.iloc[i, k]) for k in range(min(2, o.shape[1])))
            print(f"   r{i} [{lab}] {c}: {x} -> {y}")
    else:
        print(f"{p.name}: identical")
for name in sorted(set(new_t) - {p.name for p in old_t}):
    print(f"{name}: NEW only")

print("\n# evidence.json")
eo = json.loads((a.old / "docs/data/evidence.json").read_text())
en = json.loads((a.new / "docs/data/evidence.json").read_text())


def walk(x, y, path):
    out = []
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if k not in x or k not in y:
                out.append((path + "/" + k, x.get(k, "<absent>"), y.get(k, "<absent>")))
            else:
                out += walk(x[k], y[k], path + "/" + k)
    elif isinstance(x, list) and isinstance(y, list):
        if len(x) != len(y):
            out.append((path, f"len {len(x)}", f"len {len(y)}"))
        for i, (u, v) in enumerate(zip(x, y)):
            out += walk(u, v, f"{path}[{i}]")
    else:
        if isinstance(x, float) and isinstance(y, float):
            if not same(x, y):
                out.append((path, x, y))
        elif x != y:
            out.append((path, x, y))
    return out


d = walk(eo, en, "")
print(f"{len(d)} differing leaves")
for pth, x, y in d[: a.max_cells]:
    if "/sources/" in pth or "sha256" in pth:
        print(f"   {pth}: (hash changed)")
    else:
        print(f"   {pth}: {x} -> {y}")

print("\n# master (shape and per-column changed-cell counts only)")
mo = pd.read_csv(a.old / "data/processed/dmr_master.csv", low_memory=False)
mn = pd.read_csv(a.new / "data/processed/dmr_master.csv", low_memory=False)
print("shape", mo.shape, "->", mn.shape)
if mo.shape == mn.shape and list(mo.columns) == list(mn.columns):
    for c in mo.columns:
        so, sn = mo[c], mn[c]
        if pd.api.types.is_numeric_dtype(so) and pd.api.types.is_numeric_dtype(sn) and not pd.api.types.is_bool_dtype(so):
            ch = ~((so - sn).abs().le(1e-9) | (so.isna() & sn.isna()))
        else:
            ch = ~((so.astype(str) == sn.astype(str)))
        if ch.sum():
            print(f"   {c}: {int(ch.sum())} rows changed")
else:
    print("   columns only old:", sorted(set(mo.columns) - set(mn.columns)))
    print("   columns only new:", sorted(set(mn.columns) - set(mo.columns)))
