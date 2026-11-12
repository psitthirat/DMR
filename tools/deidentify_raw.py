"""De-identify the DMR raw workbooks before they leave the p.sitthirat Mac.

Usage:
    python -B -I deidentify_raw.py DMR_ROOT DST_CASE_REPORT KEY_CSV REPORT_JSON

Reads DMR_ROOT/data/case_report/*.xls* (never writes there) and writes coded copies
to DST_CASE_REPORT, plus an updated _filename_map.csv. Every sheet keeps its name,
row and column positions and every cell value except the identifier columns:

    ชื่อ-สกุล / ชื่อ         -> courtesy title the ETL knows + "N00001"
                               (ETL derives sex from the title; same name -> same token)
    สกุล                     -> blank
    HN                       -> "HN000001", one token per normalised HN across all files
    เลขบัตรปชช               -> "ID00001"
    เลขประชาชน               -> blank (not read by the ETL)
    รหัสประจำตัว...           -> token of the same type (int/float -> 90000001, text -> "P00001")
    เบอร์โทร, ที่อยู่           -> blank

Cells in those columns that are labels (a repeated header such as "ชื่อ-สกุล ผู้ป่วย")
are left alone so the loaders still recognise repeated header blocks.
Formula cells are written as the values Excel cached (what pandas reads today).
.xls files are written as .xlsx; _filename_map.csv new_filename is updated to match.

The token key goes to KEY_CSV only. The report holds counts, never values.
"""
import csv
import datetime as dt
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import openpyxl.cell._writer as _cell_writer
from openpyxl import Workbook

# openpyxl writes numbers with "%.16g", which can move a float by one ULP
# (e.g. BMI from a formula). repr() round-trips exactly.
_orig_safe_string = _cell_writer.safe_string


def _exact_safe_string(value):
    if isinstance(value, float) and math.isfinite(value):
        return repr(value)
    return _orig_safe_string(value)


_cell_writer.safe_string = _exact_safe_string

DMR = Path(sys.argv[1]).expanduser()
DST = Path(sys.argv[2]).expanduser()
KEY = Path(sys.argv[3]).expanduser()
REPORT = Path(sys.argv[4]).expanduser()
SRC = DMR / "data" / "case_report"

sys.path.insert(0, str(DMR))
from src.dmr_etl import open_workbook, _MALE_TITLES, _FEMALE_TITLES  # noqa: E402
from src.dmr_parse import clean_text  # noqa: E402

TITLES = sorted(set(_MALE_TITLES + _FEMALE_TITLES), key=len, reverse=True)

RULES = [  # (kind, regex on the column's own header label)
    ("name", re.compile(r"^ชื่อ-สกุล|^ชื่อ$")),
    ("surname", re.compile(r"^สกุล$")),
    ("hn", re.compile(r"^hn$", re.I)),
    ("national_id", re.compile(r"^เลขบัตรปชช")),
    ("blank_id", re.compile(r"^เลขประชาชน")),
    ("code", re.compile(r"^รหัสประจำตัว")),
    ("phone", re.compile(r"^(เบอร์)?โทร")),
    ("address", re.compile(r"^ที่อยู่")),
]
LABEL_LIKE = {
    "name": re.compile(r"^ชื่อ"), "surname": re.compile(r"^สกุล"), "hn": re.compile(r"^hn", re.I),
    "national_id": re.compile(r"^เลข"), "blank_id": re.compile(r"^เลข"),
    "code": re.compile(r"^รหัส"), "phone": re.compile(r"โทร"), "address": re.compile(r"^ที่อยู่"),
}
DATE_RE = re.compile(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}")


def txt(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def is_valuey(s):
    try:
        float(s.replace(",", ""))
        return True
    except ValueError:
        return bool(DATE_RE.search(s) or re.match(r"^\d{4}-\d{2}-\d{2}", s))


def header_rows(raw, max_scan=8):
    hdr = []
    for i in range(min(max_scan, len(raw))):
        cells = [txt(v) for v in raw.iloc[i]]
        nonempty = [c for c in cells if c]
        if not nonempty:
            continue
        valuey = sum(is_valuey(c) for c in nonempty) / len(nonempty)
        if valuey >= 0.3 and hdr:
            break
        if valuey < 0.3:
            hdr.append(i)
        if len(hdr) >= 3:
            break
    return hdr


def own_labels(raw, rows):
    """The lowest non-empty header cell of each column (its own label)."""
    out = []
    for j in range(raw.shape[1]):
        lab = ""
        for r in rows:
            t = txt(raw.iat[r, j])
            if t:
                lab = t
        out.append(lab)
    return out


def is_missing(v):
    if v is None or v is pd.NaT:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


class Tokens:
    def __init__(self, fmt):
        self.fmt, self.map = fmt, {}

    def get(self, key):
        if key not in self.map:
            self.map[key] = self.fmt(len(self.map) + 1)
        return self.map[key]


names = Tokens(lambda n: f"N{n:05d}")
hns = Tokens(lambda n: f"HN{n:06d}")
cids = Tokens(lambda n: f"ID{n:05d}")
codes_num = Tokens(lambda n: 90000000 + n)
codes_txt = Tokens(lambda n: f"P{n:05d}")
key_rows = []
id_digits = set()  # digits of blanked phone / unused national ID cells
report = {"files": [], "kept_label_like": 0}


def hn_norm(s):
    s = re.sub(r"\.0+$", "", s.strip())
    return re.sub(r"\D", "", s).lstrip("0")


def transform(kind, v, where):
    if is_missing(v):
        return v, False
    s = clean_text(v)
    if s is None:
        return v, False
    if LABEL_LIKE[kind].search(s):
        report["kept_label_like"] += 1
        return v, False
    if kind in ("surname", "blank_id", "phone", "address"):
        if kind in ("blank_id", "phone"):
            d = re.sub(r"\D", "", s)
            if len(d) >= 6:
                id_digits.add(d)
                id_digits.add(d.lstrip("0"))
        return None, True
    if kind == "name":
        title = next((t for t in TITLES if s.startswith(t)), "")
        tok = names.get(s)
        key_rows.append(("name", s, tok, *where))
        return title + tok, True
    if kind == "hn":
        k = hn_norm(s)
        if not k:  # no digits at all: not an identifier ("-", "ไม่มี")
            return v, False
        tok = hns.get(k)
        key_rows.append(("hn", s, tok, *where))
        return tok, True
    if kind == "national_id":
        k = re.sub(r"\D", "", s) or s
        tok = cids.get(k)
        key_rows.append(("national_id", s, tok, *where))
        return tok, True
    if kind == "code":
        if isinstance(v, (int, np.integer)) or (isinstance(v, (float, np.floating)) and float(v).is_integer()):
            tok = codes_num.get(str(int(v)))
            key_rows.append(("code", s, tok, *where))
            return (float(tok) if isinstance(v, (float, np.floating)) else tok), True
        tok = codes_txt.get(s)
        key_rows.append(("code", s, tok, *where))
        return tok, True
    raise ValueError(kind)


def py(v):
    """numpy / pandas scalars to plain Python for openpyxl."""
    if is_missing(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def write_book(path, frames):
    wb = Workbook()
    wb.remove(wb.active)
    eq_strings = 0
    for name, df in frames:
        ws = wb.create_sheet(title=name)
        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                v = py(df.iat[i, j])
                if v is None:
                    continue
                c = ws.cell(row=i + 1, column=j + 1, value=v)
                if isinstance(v, str) and v.startswith("="):
                    c.data_type = "s"  # literal text, not a formula
                    eq_strings += 1
    wb.save(path)
    return eq_strings


DST.mkdir(parents=True, exist_ok=True)
renamed = {}
books = []
for p in sorted(SRC.glob("*.xls*")):
    xl = open_workbook(p)
    frames, frec = [], {"file": p.name, "sheets": []}
    for s in xl.sheet_names:
        raw = xl.parse(s, header=None)
        rows = header_rows(raw)
        start = (max(rows) + 1) if rows else 0
        labels = own_labels(raw, rows)
        srec = {"sheet": s, "header_rows": rows, "columns": []}
        df = raw.copy().astype(object)
        for j, lab in enumerate(labels):
            kind = next((k for k, rx in RULES if lab and rx.search(lab)), None)
            if not kind:
                continue
            changed = 0
            for i in range(start, df.shape[0]):
                nv, ch = transform(kind, df.iat[i, j], (p.name, s, j))
                if ch:
                    df.iat[i, j] = nv
                    changed += 1
            srec["columns"].append({"col": j, "label": lab, "kind": kind, "cells_changed": changed})
        frames.append((s, df))
        frec["sheets"].append(srec)
    books.append((p, frames, frec))

# Stray identifiers: a number in a non-identifier column whose digits equal an
# HN, national ID or phone number seen in the identifier columns (e.g. an HN typed
# into the background sheet's age column). Blanked; counted per column.
stray_keys = set(hns.map) | set(cids.map) | id_digits
for p, frames, frec in books:
    for (s, df), srec in zip(frames, frec["sheets"]):
        idc = {c["col"] for c in srec["columns"]}
        start = (max(srec["header_rows"]) + 1) if srec["header_rows"] else 0
        for j in range(df.shape[1]):
            if j in idc:
                continue
            n = 0
            for i in range(start, df.shape[0]):
                v = df.iat[i, j]
                if is_missing(v) or isinstance(v, (bool, np.bool_, dt.datetime, dt.date, dt.time, pd.Timestamp)):
                    continue
                if isinstance(v, (float, np.floating)) and not float(v).is_integer():
                    continue
                d = re.sub(r"\D", "", str(int(v)) if isinstance(v, (int, float, np.integer, np.floating)) else str(v))
                k = d.lstrip("0")
                if len(k) >= 6 and re.fullmatch(r"[\d\s.-]+", str(v).strip()) and (k in stray_keys or d in stray_keys):
                    key_rows.append(("stray", clean_text(v), "", p.name, s, j))
                    df.iat[i, j] = None
                    n += 1
            if n:
                srec.setdefault("stray_blanked", []).append({"col": j, "cells": n})

for p, frames, frec in books:
    out_name = p.name if p.suffix.lower() == ".xlsx" else p.stem + ".xlsx"
    if out_name != p.name:
        renamed[p.name] = out_name
    frec["written_as"] = out_name
    frec["literal_eq_strings"] = write_book(DST / out_name, frames)
    report["files"].append(frec)
print("stray identifiers blanked:", [(f["file"][:24], s["sheet"], x) for f in report["files"] for s in f["sheets"] for x in s.get("stray_blanked", [])])

# filename map: only new_filename of renamed files changes
src_map = SRC / "_filename_map.csv"
raw_bytes = src_map.read_bytes()
bom = raw_bytes.startswith(b"\xef\xbb\xbf")
text = raw_bytes.decode("utf-8-sig")
newline = "\r\n" if "\r\n" in text else "\n"
rows = list(csv.reader(text.splitlines()))
head, body = rows[0], rows[1:]
ci = head.index("new_filename")
n_map = 0
for r in body:
    if r[ci] in renamed:
        r[ci] = renamed[r[ci]]
        n_map += 1
with open(DST / "_filename_map.csv", "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as fh:
    w = csv.writer(fh, lineterminator=newline)
    w.writerows([head] + body)
report["filename_map_rows_updated"] = n_map
report["renamed"] = renamed

KEY.parent.mkdir(parents=True, exist_ok=True)
with open(KEY, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["kind", "original", "token", "file", "sheet", "col"])
    seen = set()
    for r in key_rows:
        if r[:3] + r[3:5] not in seen:
            seen.add(r[:3] + r[3:5])
            w.writerow(r)
KEY.chmod(0o600)
report["tokens"] = {"name": len(names.map), "hn": len(hns.map), "national_id": len(cids.map),
                    "code_numeric": len(codes_num.map), "code_text": len(codes_txt.map)}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

# console: counts only
print("tokens:", report["tokens"], "| label-like cells kept:", report["kept_label_like"])
print("renamed:", renamed, "| map rows updated:", n_map)
agg = Counter()
for f in report["files"]:
    for s in f["sheets"]:
        for c in s["columns"]:
            agg[(c["kind"], c["label"])] += c["cells_changed"]
for (k, lab), n in sorted(agg.items()):
    print(f"  {k:12s} {lab[:30]:30s} {n}")
print("literal '=' strings:", sum(f["literal_eq_strings"] for f in report["files"]))
