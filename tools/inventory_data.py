"""Privacy-safe inventory of DMR data files.

Prints only: file names, sizes, sha256, sheet names, row/column counts,
header labels (with any cell that looks like a value redacted), and COUNTS of
cells matching identifier patterns. Never prints cell values from data rows.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])

ID_COL_RE = re.compile(
    r"ชื่อ|สกุล|^hn|\bhn\b|เลขบัตร|บัตรประ|ปชช|\bcid\b|\bpid\b|ที่อยู่|บ้านเลขที่|"
    r"^หมู่|ตำบล|โทร|phone|\btel\b|มือถือ|วันเกิด|เกิด|birth|\bdob\b|e-?mail|รหัส|local_id|uid|name",
    re.I)
TITLE_RE = re.compile(r"^\s*(นาย|นาง|น\.ส\.|นส\.|ด\.ช\.|ด\.ญ\.|เด็กชาย|เด็กหญิง|พระ|ว่าที่)")
CID_RE = re.compile(r"^\D*(\d[\s-]?){13}\D*$")
CID_ANY_RE = re.compile(r"(?<!\d)\d{13}(?!\d)")
DIGITS4_RE = re.compile(r"\d{4,}")
DATE_RE = re.compile(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def txt(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def is_valuey(s):
    if not s:
        return False
    try:
        float(s.replace(",", ""))
        return True
    except ValueError:
        pass
    return bool(DATE_RE.search(s) or re.match(r"^\d{4}-\d{2}-\d{2}", s))


def safe_label(s):
    """Return a header label, or a redaction marker if it looks like a value."""
    if not s:
        return ""
    if TITLE_RE.search(s) or DIGITS4_RE.search(s) or DATE_RE.search(s) or len(s) > 80:
        return "[redacted]"
    return s


def header_rows(raw, max_scan=8):
    """Rows above the first data-like row (>=30% numeric/date cells)."""
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


def flatten_headers(raw, rows):
    if not rows:
        return []
    labels = []
    groups = [raw.iloc[r].map(txt).replace("", pd.NA).ffill().fillna("") if k == 0 and len(rows) > 1
              else raw.iloc[r].map(txt) for k, r in enumerate(rows)]
    for j in range(raw.shape[1]):
        parts = [safe_label(g.iloc[j]) for g in groups]
        parts = [p for p in parts if p]
        labels.append(" || ".join(dict.fromkeys(parts)))
    return labels


def sheet_info(raw, sheet):
    rows = header_rows(raw)
    labels = flatten_headers(raw, rows)
    start = (max(rows) + 1) if rows else 0
    body = raw.iloc[start:]
    nonempty_counts = body.notna().sum(axis=1)
    data_rows = int((nonempty_counts >= 2).sum())
    cells = body.map(txt) if hasattr(body, "map") else body.applymap(txt)
    cid_total = int(cells.map(lambda s: bool(CID_RE.match(s))).values.sum())
    title_total = int(cells.map(lambda s: bool(TITLE_RE.search(s))).values.sum())
    flagged = []
    for j, lab in enumerate(labels):
        if lab and ID_COL_RE.search(lab):
            col = cells.iloc[:, j]
            flagged.append({
                "col_index": j, "label": lab,
                "n_nonempty": int((col != "").sum()),
                "n_cid_like_13digit": int(col.map(lambda s: bool(CID_RE.match(s))).sum()),
                "n_name_title": int(col.map(lambda s: bool(TITLE_RE.search(s))).sum()),
            })
    # columns that carry CID-like or name-like values without an ID-ish label
    hidden = []
    for j in range(cells.shape[1]):
        lab = labels[j] if j < len(labels) else ""
        if lab and ID_COL_RE.search(lab):
            continue
        col = cells.iloc[:, j]
        n_cid = int(col.map(lambda s: bool(CID_RE.match(s))).sum())
        n_title = int(col.map(lambda s: bool(TITLE_RE.search(s))).sum())
        if n_cid or n_title >= 3:
            hidden.append({"col_index": j, "label": lab or "(no header)",
                           "n_cid_like_13digit": n_cid, "n_name_title": n_title})
    return {
        "sheet": sheet, "n_rows_raw": int(len(raw)), "n_cols": int(raw.shape[1]),
        "header_rows": [int(r) for r in rows], "n_data_rows": data_rows,
        "labels": [l for l in labels if l],
        "n_cid_like_cells": cid_total, "n_name_title_cells": title_total,
        "id_columns": flagged, "unlabelled_id_like_columns": hidden,
    }


def inventory():
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.name == ".DS_Store":
            continue
        rec = {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha256(p)}
        try:
            if p.suffix.lower() in (".xlsx", ".xls"):
                try:
                    xl = pd.ExcelFile(p)
                except Exception:
                    sys.path.insert(0, str(ROOT.parent))
                    from src.dmr_etl import open_workbook  # damaged-zip fallback
                    xl = open_workbook(p)
                rec["sheets"] = [sheet_info(xl.parse(s, header=None), s) for s in xl.sheet_names]
            elif p.suffix.lower() == ".csv":
                df = pd.read_csv(p, dtype=str, encoding="utf-8-sig", keep_default_na=False)
                cells = df.map(txt)
                rec["n_rows"] = int(len(df))
                rec["columns"] = list(df.columns)
                rec["n_cid_like_cells"] = int(cells.map(lambda s: bool(CID_RE.match(s))).values.sum())
                rec["n_name_title_cells"] = int(cells.map(lambda s: bool(TITLE_RE.search(s))).values.sum())
                per = {}
                for c in df.columns:
                    col = cells[c]
                    n_cid = int(col.map(lambda s: bool(CID_RE.match(s))).sum())
                    n_title = int(col.map(lambda s: bool(TITLE_RE.search(s))).sum())
                    if n_cid or n_title or ID_COL_RE.search(c):
                        per[c] = {"n_nonempty": int((col != "").sum()),
                                  "n_cid_like_13digit": n_cid, "n_name_title": n_title,
                                  "n_digits_only": int(col.str.fullmatch(r"\d+").sum()),
                                  "n_rowN": int(col.str.fullmatch(r"row\d+").sum()),
                                  "n_contains_13digit_run": int(col.map(lambda s: bool(CID_ANY_RE.search(s))).sum()),
                                  "n_contains_rowN": int(col.str.contains(r"::row\d+::").sum())}
                rec["id_like_columns"] = per
        except Exception as e:  # report the error type only
            rec["error"] = type(e).__name__
        out.append(rec)
    return out


if __name__ == "__main__":
    res = inventory()
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(res)} files)")
