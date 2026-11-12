"""Characterise the non-empty rows the รพ.สต. loader skips (no name), using flags
and counts only. Never prints a cell value.

Run: <DMR>/.venv/bin/python -B -I skipped_rows.py <DMR root>
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
from src import dmr_etl as E  # noqa: E402
from src.dmr_parse import build_header, clean_text, looks_like_header  # noqa: E402

TOTAL_WORDS = re.compile(r"รวม|เฉลี่ย|ร้อยละ|สรุป|total|mean|ค่าเฉลี่ย|จำนวน", re.I)


def filled(v):
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    return str(v).strip() != ""


summary = []
for path in sorted((ROOT / "data" / "case_report").glob("*.xls*")):
    if E.classify_file(str(path)) != "rphc":
        continue
    xl = E.open_workbook(path)
    for sheet in xl.sheet_names:
        if E._EXCLUDE_SHEET_RE.search(sheet) or not E._DM_SHEET_RE.search(sheet):
            continue
        raw = xl.parse(sheet, header=None)
        cols = [c.lower() for c in build_header(raw, 1, 2)]
        body = raw.iloc[3:].reset_index(drop=True)
        name_j = next((j for j, c in enumerate(cols)
                       if not c.partition("||")[2].strip() and re.search(r"ชื่อ", c)), None)
        age_j = next((j for j, c in enumerate(cols)
                      if not c.partition("||")[2].strip() and re.search(r"^อายุ", c)), None)
        for i, r in body.iterrows():
            if not any(filled(v) for v in r):
                continue
            header_like = bool(looks_like_header(r))
            has_name = name_j is not None and clean_text(r.iloc[name_j]) is not None
            if has_name and not header_like:
                continue  # loaded
            n_filled = sum(filled(v) for v in r)
            has_total_word = any(isinstance(v, str) and TOTAL_WORDS.search(v) for v in r)
            has_age = age_j is not None and filled(r.iloc[age_j])
            n_numeric = sum(isinstance(v, (int, float)) and pd.notna(v) for v in r)
            summary.append({"file": path.name, "header_like": header_like,
                            "has_total_word": has_total_word, "has_age": has_age,
                            "filled_cells": n_filled, "numeric_cells": n_numeric,
                            "ge3": n_filled >= 3})

s = pd.DataFrame(summary)
print("skipped non-empty rows:", len(s))
print(s.groupby(["file", "ge3", "header_like", "has_total_word", "has_age"]).agg(
    rows=("file", "size"), median_filled=("filled_cells", "median"),
    max_filled=("filled_cells", "max"), median_numeric=("numeric_cells", "median")).to_string())
