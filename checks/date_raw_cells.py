"""Raw cells behind the 9 implausible programme dates (task 2).

For each programme row whose enrolment date is after 2026-09-30, or whose
diagnosis date is after its enrolment date, print the raw Excel cell (type and
value) of both date fields, plus the raw enrolment cells of the two rows above
and below for context.  Prints the sheet row number, never names, HNs or IDs.

Run: <DMR>/.venv/bin/python -B -I date_raw_cells.py <DMR root>
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
from src import dmr_etl as E  # noqa: E402
from src.dmr_parse import build_header, clean_text, looks_like_header, parse_date  # noqa: E402

RAW = ROOT / "data" / "case_report"
CUTOFF = pd.Timestamp("2026-09-30")


def show(v):
    return f"{type(v).__name__}:{v!r}"


def crf_cols(raw):
    for i in range(min(5, len(raw))):
        joined = " ".join(clean_text(v) or "" for v in raw.iloc[i])
        if "หน่วยบริการ" in joined and "เพศ" in joined:
            headers = [(clean_text(v) or "").lower() for v in raw.iloc[i]]
            col = {}
            for field, pat in E._CRF_MAP:
                for j, h in enumerate(headers):
                    if h and re.search(pat, h) and field not in col:
                        col[field] = j
            return i, col["dx_date"], col["enroll_date"], headers
    raise ValueError("no header")


for f in sorted(RAW.glob("*.xls*")):
    kind = E.classify_file(str(f))
    if kind not in {"crf", "bangrakam"}:
        continue
    xl = E.open_workbook(f)
    raw = xl.parse(xl.sheet_names[0], header=None)
    if kind == "crf":
        hdr, jdx, jen, headers = crf_cols(raw)
        start = hdr + 1
        hdx, hen = headers[jdx], headers[jen]
    else:
        cols = [c.lower() for c in build_header(raw, 1, 2)]
        jdx = next(j for j, c in enumerate(cols) if re.search(r"วันที่ dx", c))
        jen = next(j for j, c in enumerate(cols) if re.search(r"วันที่เข้า dm", c))
        start, hdx, hen = 3, cols[jdx], cols[jen]
    body = raw.iloc[start:]
    hits = []
    for pos, (i, r) in enumerate(body.iterrows()):
        if looks_like_header(r):
            continue
        dx, en = parse_date(r.iloc[jdx]), parse_date(r.iloc[jen])
        bad_en = pd.notna(en) and en > CUTOFF
        bad_dx = pd.notna(dx) and pd.notna(en) and dx > en
        if bad_en or bad_dx:
            hits.append((pos, i, dx, en, bad_en, bad_dx))
    if not hits:
        continue
    print(f"\n=== {f.name} ({kind})  dx col '{hdx}' | enrol col '{hen}'")
    for pos, i, dx, en, bad_en, bad_dx in hits:
        r = body.iloc[pos]
        print(f" sheet row {i + 1}: {'ENROL>cutoff ' if bad_en else ''}{'DX>ENROL' if bad_dx else ''}")
        print(f"    dx raw   {show(r.iloc[jdx])} -> {dx.date() if pd.notna(dx) else dx}")
        print(f"    enrol raw {show(r.iloc[jen])} -> {en.date() if pd.notna(en) else en}")
        ctx = []
        for k in range(max(0, pos - 2), min(len(body), pos + 3)):
            if k == pos:
                continue
            ctx.append(f"r{body.index[k] + 1}:{show(body.iloc[k, jen])}")
        print("    neighbours' enrol:", " | ".join(ctx))
    # the file's own distribution of raw enrolment cell types
    types = body.iloc[:, jen].map(lambda v: type(v).__name__).value_counts().to_dict()
    print("    enrol cell types in file:", types)
