"""Check the coded workbooks against the originals. Prints counts only.

Usage:
    python -B -I verify_coded.py DMR_ROOT CODED_CASE_REPORT DEID_REPORT_JSON SCAN_CODE_DIR

1. Same sheets, same shape, and every cell outside the identifier columns identical
   (same value AND same Python type, as pandas reads them, header=None and header=0).
2. No identifier from the original files left anywhere in the coded files
   (names, HN, national ID, phone, participant codes), including free-text cells.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

DMR = Path(sys.argv[1]).expanduser()
CODED = Path(sys.argv[2]).expanduser()
REP = json.loads(Path(sys.argv[3]).expanduser().read_text(encoding="utf-8"))
sys.path.insert(0, str(Path(sys.argv[4]).expanduser()))
sys.argv = ["scan_code", str(DMR), "/dev/null", "/dev/null"]
import scan_code as sc  # noqa: E402  (identifier sets from the ORIGINAL raw files)
sys.path.insert(0, str(DMR))
from src.dmr_etl import open_workbook  # noqa: E402


def same(a, b):
    ma = a is None or a is pd.NaT or (not isinstance(a, str) and pd.isna(a))
    mb = b is None or b is pd.NaT or (not isinstance(b, str) and pd.isna(b))
    if ma or mb:
        return ma and mb, False
    if type(a) is not type(b):
        return a == b, True  # (equal?, type differs)
    return a == b, False


problems = Counter()
checked = 0
for f in REP["files"]:
    orig = open_workbook(DMR / "data" / "case_report" / f["file"])
    new = pd.ExcelFile(CODED / f["written_as"])
    if orig.sheet_names != new.sheet_names:
        problems[(f["file"], "sheet names differ")] += 1
        continue
    id_cols = {s["sheet"]: {c["col"] for c in s["columns"]} for s in f["sheets"]}
    stray_cols = {s["sheet"]: {x["col"] for x in s.get("stray_blanked", [])} for s in f["sheets"]}
    for s in orig.sheet_names:
        for hdr in (None, 0):
            a = orig.parse(s, header=hdr)
            b = new.parse(s, header=hdr)
            if a.shape != b.shape:
                problems[(f["file"], s, f"shape header={hdr}")] += 1
                continue
            if hdr == 0 and list(map(str, a.columns)) != list(map(str, b.columns)):
                problems[(f["file"], s, "column names")] += 1
            for j in range(a.shape[1]):
                if j in id_cols[s]:
                    continue
                for i in range(a.shape[0]):
                    eq, tdiff = same(a.iat[i, j], b.iat[i, j])
                    checked += 1
                    if not eq and j in stray_cols[s] and same(None, b.iat[i, j])[0]:
                        problems[(f["file"], s, f"stray identifier blanked (expected) header={hdr}")] += 1
                    elif not eq:
                        problems[(f["file"], s, f"value header={hdr}")] += 1
                    elif tdiff:
                        problems[(f["file"], s, f"type header={hdr}")] += 1
print(f"cells compared outside identifier columns: {checked:,}")
print("cell differences:", dict(problems) if problems else "none")

# 2. identifiers left in the coded files
ids = sc.collect_identifiers()
digits, names_full, surnames = sc.build_matchers(ids)
# words that occur outside the name columns of the ORIGINAL files are ordinary
# words (ผู้ป่วย, ส่งเสริม, place names), not evidence of a person's name
idcols = {(f["file"], s["sheet"]): {c["col"] for c in s["columns"]} for f in REP["files"] for s in f["sheets"]}
orig_text = []  # string cells outside the identifier columns of the ORIGINAL files
row_names = {}  # (file, sheet, row) -> original name cell, for same-row checks
for f in REP["files"]:
    xl = open_workbook(DMR / "data" / "case_report" / f["file"])
    for srec in f["sheets"]:
        s = srec["sheet"]
        raw = xl.parse(s, header=None)
        namecols = [c["col"] for c in srec["columns"] if c["kind"] == "name"]
        for i in range(raw.shape[0]):
            for j in namecols:
                v = raw.iat[i, j]
                if isinstance(v, str):
                    row_names[(f["written_as"], s, i)] = row_names.get((f["written_as"], s, i), "") + " " + v
        for j in range(raw.shape[1]):
            if j in idcols[(f["file"], s)]:
                continue
            orig_text.extend(v for v in raw.iloc[:, j] if isinstance(v, str))


def n_cells_with(w):
    return sum(1 for t in orig_text if w in t)


pairs = [(a, b) for a, b in names_full if not a.startswith("ชื่อ")]
specific_pairs = [(a, b) for a, b in pairs if not (n_cells_with(a) >= 3 and (not b or n_cells_with(b) >= 3))]
specific_surnames = {x for x in surnames if n_cells_with(x) < 3}
shape = lambda v: re.sub(r"[ก-๙]+", "ก", re.sub(r"[A-Za-z]+", "a", re.sub(r"\d", "9", str(v))))[:24]
left = Counter()
for p in sorted(CODED.glob("*.xlsx")):
    xl = pd.ExcelFile(p)
    for s in xl.sheet_names:
        raw = xl.parse(s, header=None)
        for j in range(raw.shape[1]):
            lab = next((txt for txt in (str(raw.iat[r, j]) for r in range(min(3, len(raw)))) if txt and txt != "nan"), "")[:20]
            for i, v in enumerate(raw.iloc[:, j]):
                if v is None or (not isinstance(v, str) and pd.isna(v)):
                    continue
                t = str(v)
                dl = re.sub(r"[\s-]", "", t)
                for kind, vals in digits.items():
                    for d in re.findall(r"\d{5,}|[A-Za-z]*\d{3,}[A-Za-z0-9]*", dl):
                        if d in vals or d.split(".")[0] in vals:
                            left[(p.name, s, j, lab, f"ID:{kind} shape={shape(v)}")] += 1
                if isinstance(v, str):
                    for first, last in specific_pairs:
                        if first in t and (not last or last in t):
                            own = row_names.get((p.name, s, i), "")
                            left[(p.name, s, j, lab, f"ID:name pair len={len(first)}+{len(last)} same_row={first in own and last in own}")] += 1
                            break
                if isinstance(v, str) and re.search(r"(?<!\d)\d{13}(?!\d)", dl):
                    left[(p.name, s, j, lab, "13digit in text")] += 1
                if isinstance(v, str):
                    hit = [x for x in specific_surnames if x in t]
                    if hit:
                        own = row_names.get((p.name, s, i), "")
                        left[(p.name, s, j, lab, f"surname len={len(hit[0])} in_orig_cells={n_cells_with(hit[0])} same_row={any(x in own for x in hit)}")] += 1
print("identifier hits in coded files (file, sheet, col, top label, kind -> cells):")
for k, n in sorted(left.items()):
    print("  ", k, n)
if not left:
    print("   none")
