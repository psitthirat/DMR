"""Aggregate inventory of the raw DMR workbooks: sheets, non-empty rows, rows the
loader keeps, and rows it skips. Prints counts only, never cell contents.

Run: python3 -B -I raw_inventory.py <DMR root>
(-B so importing the repo's src/ never writes .pyc files under DMR/.)
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
from src import dmr_etl as E  # noqa: E402
from src.dmr_parse import clean_text  # noqa: E402

RAW = ROOT / "data" / "case_report"
fmap = pd.read_csv(RAW / "_filename_map.csv", encoding="utf-8-sig")
sender_of = dict(zip(fmap["new_filename"], fmap["sender"]))


def is_filled(v):
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    return str(v).strip() != ""


def nonempty(frame):
    """Rows with at least one non-blank cell."""
    return frame.map(is_filled).any(axis=1)


def ncells(frame):
    return frame.map(is_filled).sum(axis=1)


rows = []
for path in sorted(RAW.glob("*.xls*")):
    kind = E.classify_file(str(path))
    xl = E.open_workbook(path)
    loaded = E.LOADERS[kind](str(path)) if kind in E.LOADERS else None
    n_loaded = 0 if loaded is None else len(loaded)
    for si, sheet in enumerate(xl.sheet_names):
        raw = xl.parse(sheet, header=None)
        # which sheet / body rows the loader reads, mirroring each loader
        read, body_start = False, None
        if kind == "crf":
            read = si == 0
            if read:
                body_start = None
                for i in range(min(5, len(raw))):
                    joined = " ".join(clean_text(v) or "" for v in raw.iloc[i])
                    if "หน่วยบริการ" in joined and "เพศ" in joined:
                        body_start = i + 1
                        break
        elif kind in ("bangrakam", "pcc"):
            read = si == 0
            body_start = 3 if read else None
        elif kind == "rphc":
            read = (not E._EXCLUDE_SHEET_RE.search(sheet)) and bool(E._DM_SHEET_RE.search(sheet)) and raw.shape[0] >= 4
            body_start = 3 if read else None
        elif kind in ("relational", "survey"):
            read = None  # multi-sheet loaders; counted at file level only
        body = raw.iloc[body_start:] if (read and body_start is not None) else raw
        ne = nonempty(body) if len(body) else pd.Series([], dtype=bool)
        cells = ncells(body) if len(body) else pd.Series([], dtype=int)
        rows.append({
            "file": path.name, "sender": sender_of.get(path.name), "loader": kind,
            "sheet_idx": si, "sheet": sheet, "sheet_read": read,
            "rows_total": len(raw), "header_rows": (body_start if read else None),
            "body_nonempty": int(ne.sum()),
            "body_ge3_cells": int((cells >= 3).sum()),
            "n_loaded_file": n_loaded,
        })

inv = pd.DataFrame(rows)
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 200)
pd.set_option("display.max_colwidth", 40)
print(inv.to_string(index=False))
out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
if out:
    inv.to_csv(out, index=False)
