"""
Combine the 24 DM-Remission case-report workbooks into one patient-level table.

The workbooks fall into five layouts.  Each gets its own loader; every loader
returns rows in the same harmonised schema (see ``SCHEMA`` below), so the
master table is just a concatenation.

    A  crf        "Case Record Form DM Remission" - one row per patient,
                  fixed 22-24 columns, free-text medication fields.
                  Sites: พิมาย, ท่าวุ้ง (multi-site file), กงหรา, หูแร่ x3,
                         อุ้มผาง
    A' crf_wide   Same concept, site-specific column layouts:
                  บางระกำ (grouped 2-row header) and PCC คลองศาลา
                  (one column per drug per visit, monthly anthropometry).
    B  rphc       รพ.สต. summary workbooks - sheets เบาหวาน / ความดัน /
                  กลุ่มเสี่ยง, two-row header with a "ก่อน" and a "หลัง"
                  block, one column per drug holding a dose string.
    C  relational บ้านตาขุน - four sheets keyed on รหัสประจำตัวผู้เข้าร่วม,
                  with follow-up values packed as "date | value | date | value".
    D  survey     "for edit ข้อมูลคนไข้โครงการ 2" - a Google-Forms export with
                  baseline and 3-month HbA1c and a tablet-count column.

Run ``python -m src.dmr_etl`` (or call ``build_master``) to write
``data/processed/dmr_master.csv``.
"""

from __future__ import annotations

import glob
import io
import os
import re
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .dmr_parse import (
    DRUG_PATTERNS,
    RANGES,
    build_header,
    clean_text,
    looks_like_header,
    norm_education,
    norm_scheme,
    norm_sex,
    parse_comorbidities,
    parse_date,
    parse_dose,
    parse_regimen,
    to_num,
    to_num_r,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "case_report"
PROC_DIR = ROOT / "data" / "processed"

# --------------------------------------------------------------------------
# harmonised schema
# --------------------------------------------------------------------------

SCHEMA = [
    # provenance
    "patient_uid", "source_file", "source_family", "facility", "local_id",
    # demographics
    "sex", "age", "scheme", "education",
    # history
    "dx_date", "enroll_date", "dm_duration_y",
    "comorbid_raw", "hypertension", "dyslipidaemia", "ckd", "cvd", "gout",
    "copd_asthma", "n_comorbid",
    # anthropometry
    "height_cm", "weight_pre", "weight_post", "bmi_pre", "bmi_post",
    "waist_pre", "waist_post",
    # glycaemia
    "fbs_pre", "fbs_3m", "fbs_6m", "fbs_9m", "fbs_post",
    "hba1c_pre", "hba1c_mid", "hba1c_post",
    # other labs
    "creatinine_pre", "egfr_pre", "ldl_pre", "hdl_pre", "tg_pre", "chol_pre",
    "creatinine_post", "egfr_post",
    # medication - raw
    "med_pre_raw", "med_mid_raw", "med_post_raw", "med_other_raw",
    # medication - derived
    "on_any_pre", "on_any_mid", "on_any_post",
    "on_insulin_pre", "on_insulin_mid", "on_insulin_post",
    "n_class_pre", "n_class_mid", "n_class_post", "tabs_pre", "tabs_post",
    "med_status_pre", "med_status_mid", "med_status_post",
    # service use and cost - only the บ้านตาขุน HIS export carries these
    "post_engaged", "n_post_visits", "n_post_measures", "followup_months",
    "labcost_pre", "labcost_post", "drugcost_pre", "drugcost_post",
    "drugcost_post_last", "member_status", "clinic_first", "clinic_last",
    "care_note",
    # time-bound ("at 6 months") raw pulls, filled by the loaders
    "hba1c_m6_raw", "fbs_m6_raw", "bmi_m6_raw", "waist_m6_raw",
    "on_any_m6_raw", "n_class_m6_raw", "m6_offset_months",
    "hba1c_m3_raw", "fbs_m3_raw", "bmi_m3_raw", "waist_m3_raw",
    "on_any_m3_raw", "m3_offset_months",
]

# Maximum believable oral-antidiabetic burden, tablets/day.  Cells above this
# are dispensing quantities or typos ("201", "212"), not daily doses.
MAX_TABS_PER_DAY = 20

NUMERIC_COLS = [
    "age", "dm_duration_y", "n_comorbid", "height_cm", "weight_pre",
    "weight_post", "bmi_pre", "bmi_post", "waist_pre", "waist_post",
    "fbs_pre", "fbs_3m", "fbs_6m", "fbs_9m", "fbs_post", "hba1c_pre",
    "hba1c_mid", "hba1c_post", "creatinine_pre", "egfr_pre", "ldl_pre",
    "hdl_pre", "tg_pre", "chol_pre", "creatinine_post", "egfr_post",
    "on_any_pre", "on_any_mid", "on_any_post", "on_insulin_pre",
    "on_insulin_mid", "on_insulin_post",
    "n_class_pre", "n_class_mid", "n_class_post", "tabs_pre", "tabs_post",
    "hypertension", "dyslipidaemia", "ckd", "cvd", "gout", "copd_asthma",
    "post_engaged", "n_post_visits", "n_post_measures", "followup_months",
    "labcost_pre", "labcost_post", "drugcost_pre", "drugcost_post",
    "drugcost_post_last",
    "hba1c_m6_raw", "fbs_m6_raw", "bmi_m6_raw", "waist_m6_raw",
    "on_any_m6_raw", "n_class_m6_raw", "m6_offset_months",
    "hba1c_m3_raw", "fbs_m3_raw", "bmi_m3_raw", "waist_m3_raw",
    "on_any_m3_raw", "m3_offset_months",
]

# Columns that only the บ้านตาขุน export supplies; absent elsewhere by design.
REGISTRY_ONLY_COLS = [
    "post_engaged", "n_post_visits", "n_post_measures", "followup_months",
    "labcost_pre", "labcost_post", "drugcost_pre", "drugcost_post",
    "drugcost_post_last", "member_status", "clinic_first", "clinic_last",
    "care_note",
    # time-bound ("at 6 months") raw pulls, filled by the loaders
    "hba1c_m6_raw", "fbs_m6_raw", "bmi_m6_raw", "waist_m6_raw",
    "on_any_m6_raw", "n_class_m6_raw", "m6_offset_months",
]


def _blank_row() -> dict:
    return {c: np.nan for c in SCHEMA}


# --------------------------------------------------------------------------
# robust workbook opening
# --------------------------------------------------------------------------

_STD_CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""


def open_workbook(path: str | Path) -> pd.ExcelFile:
    """
    ``pd.ExcelFile`` that also copes with one damaged workbook.

    The อุ้มผาง file has a corrupted first local-file header, so its
    ``[Content_Types].xml`` entry cannot be inflated even though every other
    part of the zip is intact.  That part is pure boilerplate, so it is
    regenerated in memory and the workbook is rebuilt before parsing.  The
    cell data is untouched.
    """
    path = str(path)
    try:
        return pd.ExcelFile(path)
    except Exception:
        pass
    with open(path, "rb") as fh:
        raw = fh.read()
    src = zipfile.ZipFile(io.BytesIO(raw))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        dst.writestr("[Content_Types].xml", _STD_CONTENT_TYPES)
        for name in src.namelist():
            if name == "[Content_Types].xml" or "." not in os.path.basename(name):
                continue
            try:
                dst.writestr(name, src.read(name))
            except Exception:
                continue
    buf.seek(0)
    return pd.ExcelFile(buf, engine="openpyxl")


# --------------------------------------------------------------------------
# shared post-processing
# --------------------------------------------------------------------------

def _derive_from_regimens(row: dict, pre: dict, mid: dict, post: dict) -> None:
    """
    Fill the medication-derived fields from three parsed regimens.

    ``status == 'no_change'`` means the site wrote "ยังไม่ปรับยา" - the
    regimen is the same as the previous timepoint, so it is carried forward.
    """
    if post["status"] == "no_change":
        post = mid if mid["status"] in {"on_drug", "no_drug"} else pre
    if mid["status"] == "no_change":
        mid = pre

    row["med_pre_raw"] = pre["raw"]
    row["med_mid_raw"] = mid["raw"]
    row["med_post_raw"] = post["raw"]
    for tag, d in (("pre", pre), ("mid", mid), ("post", post)):
        row[f"on_any_{tag}"] = d["on_any"]
        row[f"on_insulin_{tag}"] = d["on_insulin"]
        row[f"n_class_{tag}"] = d["n_classes"]
        row[f"med_status_{tag}"] = d["status"]


def _finalise(rows: list[dict], family: str, path: str) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in SCHEMA:
        if c not in df:
            df[c] = np.nan
    df["source_family"] = family
    df["source_file"] = os.path.basename(path)
    return df[SCHEMA]


# --------------------------------------------------------------------------
# A. Case Record Form (standard layout)
# --------------------------------------------------------------------------

# The CRF ships in a 22-column and a 24-column version; the 24-column one
# splits "FBS ระหว่างโครงการ" into 3 / 6 / 9 months.  Columns are matched by
# their header text, not by position, so either version works.
_CRF_MAP = [
    ("local_id",      r"รหัสประจำตัว|เลขบัตร|^hn$"),
    ("facility",      r"หน่วยบริการ"),
    ("sex",           r"^เพศ"),
    ("age",           r"^อายุ"),
    ("scheme",        r"สิทธิการรักษา"),
    ("dx_date",       r"วันที่.*วินิจฉัย|วันที่ dx"),
    ("enroll_date",   r"วันที่.*เข้า.*(โครงการ|remission)"),
    ("comorbid_raw",  r"โรคร่วม"),
    ("med_pre_raw",   r"ยาลดระดับน้ำตาลก่อนเข้า"),
    ("med_mid_raw",   r"ยาลดระดับน้ำตาลระหว่าง"),
    ("med_post_raw",  r"ยาลดระดับน้ำตาลหลังจบ"),
    ("med_other_raw", r"ยาโรคประจำตัวอื่น"),
    ("bmi_pre",       r"ดัชนีมวลกาย ณ วันเข้า"),
    ("bmi_post",      r"ดัชนีมวลกายเมื่อสิ้นสุด"),
    ("waist_pre",     r"รอบเอว ณ วันเข้า"),
    ("waist_post",    r"รอบเอวเมื่อสิ้นสุด"),
    ("fbs_pre",       r"fbs ก่อนเข้าร่วม"),
    ("fbs_3m",        r"fbs ระหว่าง.*3"),
    ("fbs_6m",        r"fbs ระหว่าง.*6"),
    ("fbs_9m",        r"fbs ระหว่าง.*9"),
    ("fbs_post",      r"fbs หลังจบ"),
    ("hba1c_pre",     r"hba1c ก่อนเข้าร่วม"),
    ("hba1c_mid",     r"hba1c ระหว่าง"),
    ("hba1c_post",    r"hba1c หลังจบ"),
]

# 22-column CRF: a single "FBS ระหว่างเข้าร่วมโครงการ" column.  Treated as the
# 6-month value, which is the midpoint the template asks for.
_CRF_MAP_FALLBACK = [("fbs_6m", r"fbs ระหว่างเข้าร่วมโครงการ$")]


def load_crf(path: str, sheet: str | None = None) -> pd.DataFrame:
    xl = open_workbook(path)
    sheet = sheet or xl.sheet_names[0]
    raw = xl.parse(sheet, header=None)

    # find the header row: the one containing "รหัสประจำตัว" / "หน่วยบริการ"
    hdr_row = None
    for i in range(min(5, len(raw))):
        joined = " ".join(clean_text(v) or "" for v in raw.iloc[i])
        if "หน่วยบริการ" in joined and "เพศ" in joined:
            hdr_row = i
            break
    if hdr_row is None:
        return _finalise([], "crf", path)

    headers = [(clean_text(v) or "").lower() for v in raw.iloc[hdr_row]]
    body = raw.iloc[hdr_row + 1:].reset_index(drop=True)

    col_of: dict[str, int] = {}
    for field, pat in _CRF_MAP:
        for j, h in enumerate(headers):
            if h and re.search(pat, h) and field not in col_of:
                col_of[field] = j
    fbs6_labelled = "fbs_6m" in col_of      # matched the month-labelled header
    for field, pat in _CRF_MAP_FALLBACK:
        if field not in col_of:
            for j, h in enumerate(headers):
                if h and re.search(pat, h):
                    col_of[field] = j
                    break

    rows = []
    for i, r in body.iterrows():
        if looks_like_header(r):
            continue
        g = lambda f: r.iloc[col_of[f]] if f in col_of else None  # noqa: E731

        # a row counts as a patient if it has an age or any glycaemic value
        age = to_num_r(g("age"), "age")
        anchor = [to_num_r(g(f), "fbs") for f in ("fbs_pre", "fbs_6m", "fbs_post")]
        anchor += [to_num_r(g(f), "hba1c") for f in ("hba1c_pre", "hba1c_post")]
        if pd.isna(age) and all(pd.isna(v) for v in anchor):
            continue

        row = _blank_row()
        row["local_id"] = clean_text(g("local_id")) or f"row{i + 1}"
        row["facility"] = clean_text(g("facility"))
        row["sex"] = norm_sex(g("sex"))
        row["age"] = age
        row["scheme"] = norm_scheme(g("scheme"))
        row["dx_date"] = parse_date(g("dx_date"))
        row["enroll_date"] = parse_date(g("enroll_date"))
        row["comorbid_raw"] = clean_text(g("comorbid_raw"))
        row.update(parse_comorbidities(g("comorbid_raw")))
        for f, kind in [("bmi_pre", "bmi"), ("bmi_post", "bmi"),
                        ("waist_pre", "waist_cm"), ("waist_post", "waist_cm"),
                        ("fbs_pre", "fbs"), ("fbs_3m", "fbs"), ("fbs_6m", "fbs"),
                        ("fbs_9m", "fbs"), ("fbs_post", "fbs"),
                        ("hba1c_pre", "hba1c"), ("hba1c_mid", "hba1c"),
                        ("hba1c_post", "hba1c")]:
            row[f] = to_num_r(g(f), kind)
        row["med_other_raw"] = clean_text(g("med_other_raw"))
        # only the 24-column CRF has a column explicitly labelled
        # "FBS ระหว่างเข้าร่วมโครงการ 6 เดือน"; `fbs_6m_labelled` records
        # whether this row's 6-month FBS came from it or from the 22-column
        # version's single unlabelled mid-programme column
        if fbs6_labelled:
            row["fbs_m6_raw"] = to_num_r(g("fbs_6m"), "fbs")
        _derive_from_regimens(
            row,
            parse_regimen(g("med_pre_raw")),
            parse_regimen(g("med_mid_raw")),
            parse_regimen(g("med_post_raw")),
        )
        rows.append(row)
    return _finalise(rows, "crf", path)


# --------------------------------------------------------------------------
# A'. บางระกำ - CRF with a grouped two-row header
# --------------------------------------------------------------------------

def load_bangrakam(path: str) -> pd.DataFrame:
    xl = open_workbook(path)
    raw = xl.parse(xl.sheet_names[0], header=None)
    cols = [c.lower() for c in build_header(raw, 1, 2)]
    body = raw.iloc[3:].reset_index(drop=True)

    def find(pat):
        for j, c in enumerate(cols):
            if re.search(pat, c):
                return j
        return None

    idx = {
        "local_id": find(r"เลขบัตรปชช"),
        "facility": find(r"หน่วยบริการ\|\|"),
        "sex": find(r"^เพศ\|\|"), "age": find(r"^อายุ\|\|"),
        "scheme": find(r"สิทธิการรักษา"), "dx_date": find(r"วันที่ dx"),
        "enroll_date": find(r"วันที่เข้า dm"), "comorbid_raw": find(r"^โรคร่วม"),
        "med_pre_raw": find(r"ยาลดระดับน้ำตาล\|\|ก่อน"),
        "med_mid_raw": find(r"ยาลดระดับน้ำตาล\|\|ระหว่าง"),
        "med_post_raw": find(r"ยาลดระดับน้ำตาล\|\|ปัจจุบัน"),
        "med_other_raw": find(r"ยาโรคประจำตัว"),
        "bmi_pre": find(r"bmi\|\|วันเข้า"), "bmi_post": find(r"bmi\|\|ปัจจุบัน"),
        "waist_pre": find(r"รอบเอว\|\|วันเข้า"),
        "waist_post": find(r"รอบเอว\|\|ปัจจุบัน"),
        "fbs_pre": find(r"fbs\|\|ก่อน"), "fbs_3m": find(r"fbs\|\|3"),
        "fbs_6m": find(r"fbs\|\|6"), "fbs_9m": find(r"fbs\|\|9"),
        "fbs_post": find(r"fbs\|\|ปัจจุบัน"),
        "hba1c_pre": find(r"hba1c\|\|ก่อน"),
        "hba1c_mid": find(r"hba1c\|\|ระหว่าง"),
        "hba1c_post": find(r"hba1c\|\|ปัจจุบัน"),
    }

    rows = []
    for i, r in body.iterrows():
        g = lambda f: r.iloc[idx[f]] if idx.get(f) is not None else None  # noqa: E731
        age = to_num_r(g("age"), "age")
        if pd.isna(age) and pd.isna(to_num_r(g("fbs_pre"), "fbs")):
            continue
        row = _blank_row()
        row["local_id"] = clean_text(g("local_id")) or f"row{i + 1}"
        row["facility"] = clean_text(g("facility"))
        row["sex"] = norm_sex(g("sex"))
        row["age"] = age
        row["scheme"] = norm_scheme(g("scheme"))
        row["dx_date"] = parse_date(g("dx_date"))
        row["enroll_date"] = parse_date(g("enroll_date"))
        row["comorbid_raw"] = clean_text(g("comorbid_raw"))
        row.update(parse_comorbidities(g("comorbid_raw")))
        for f, kind in [("bmi_pre", "bmi"), ("bmi_post", "bmi"),
                        ("waist_pre", "waist_cm"), ("waist_post", "waist_cm"),
                        ("fbs_pre", "fbs"), ("fbs_3m", "fbs"), ("fbs_6m", "fbs"),
                        ("fbs_9m", "fbs"), ("fbs_post", "fbs"),
                        ("hba1c_pre", "hba1c"), ("hba1c_mid", "hba1c"),
                        ("hba1c_post", "hba1c")]:
            row[f] = to_num_r(g(f), kind)
        row["med_other_raw"] = clean_text(g("med_other_raw"))
        # this template labels its FBS follow-ups "3 / 6 / 9 เดือน" against
        # enrolment, so the 6-month value is genuinely labelled
        row["fbs_m6_raw"] = to_num_r(g("fbs_6m"), "fbs")
        _derive_from_regimens(row, parse_regimen(g("med_pre_raw")),
                              parse_regimen(g("med_mid_raw")),
                              parse_regimen(g("med_post_raw")))
        rows.append(row)
    return _finalise(rows, "crf", path)


# --------------------------------------------------------------------------
# A''. PCC คลองศาลา - one column per drug per visit
# --------------------------------------------------------------------------

def load_pcc(path: str) -> pd.DataFrame:
    xl = open_workbook(path)
    raw = xl.parse(xl.sheet_names[0], header=None)
    cols = [c.lower() for c in build_header(raw, 1, 2)]
    body = raw.iloc[3:].reset_index(drop=True)

    def find(pat):
        for j, c in enumerate(cols):
            if re.search(pat, c):
                return j
        return None

    def find_all(pat):
        return [j for j, c in enumerate(cols) if re.search(pat, c)]

    # medication blocks: before / at entry / 3 mo / 6 mo, each with three drugs
    med_blocks = {
        "pre":  find_all(r"ยาลดระดับน้ำตาลก่อนเข้าร่วมโครงการ"),
        "entry": find_all(r"ยาลดระดับน้ำตาลวันเข้าร่วม"),
        "m3":   find_all(r"ยาลดระดับน้ำตาลระหว่างเข้าร่วมโครงการ 3"),
        "m6":   find_all(r"ยาลดระดับน้ำตาลระหว่างเข้าร่วมโครงการ 6"),
    }
    drug_of = {}
    for block, idxs in med_blocks.items():
        for j in idxs:
            sub = cols[j].split("||")[1]
            drug_of[j] = ("metformin" if "metformin" in sub else
                          "glipizide" if "glipizide" in sub else
                          "pioglitazone" if "pioglitazone" in sub else None)

    def summarise(r, block):
        """Collapse a visit's three drug columns into on/off + class count."""
        doses, classes = [], set()
        for j in med_blocks[block]:
            d = parse_dose(r.iloc[j])
            doses.append(d)
            if pd.notna(d) and d > 0 and drug_of.get(j):
                classes.add(drug_of[j])
        if all(pd.isna(d) for d in doses):
            return {"classes": set(), "n_classes": np.nan, "on_any": np.nan,
                    "on_insulin": np.nan, "n_oral": np.nan,
                    "status": "unknown", "raw": None,
                    "tabs": np.nan}
        tabs = np.nansum([d for d in doses]) if any(pd.notna(d) for d in doses) else np.nan
        return {"classes": classes, "n_classes": len(classes),
                "on_any": int(len(classes) > 0), "on_insulin": 0,
                "n_oral": len(classes),
                "status": "on_drug" if classes else "no_drug",
                "raw": "; ".join(f"{drug_of[j]}={clean_text(r.iloc[j])}"
                                 for j in med_blocks[block]
                                 if clean_text(r.iloc[j])) or None,
                "tabs": tabs}

    # last non-missing BMI / waist across the monthly follow-up columns
    bmi_fu = find_all(r"ดัชนีมวลกายเมื่อสิ้นสุด")
    waist_fu = find_all(r"รอบเอวระหว่")
    fbs_fu = {"3": find(r"fbs ระหว่าง.*\|\|3 mo"), "6": find(r"fbs ระหว่าง.*\|\|6 mo"),
              "9": find(r"fbs ระหว่าง.*\|\|9 mo"), "12": find(r"fbs ระหว่าง.*\|\|12 mo")}
    hba_fu = [find(r"hba1c ระหว่าง.*\|\|12 mo"), find(r"hba1c ระหว่าง.*\|\|9 mo"),
              find(r"hba1c ระหว่าง.*\|\|6 mo"), find(r"hba1c ระหว่าง.*\|\|3 mo"),
              find(r"hba1c ระหว่าง.*\|\|2 mo"), find(r"hba1c ระหว่าง.*\|\|เริ่ม")]

    def last_val(r, idxs, kind):
        """Latest recorded value: scan the visit columns from late to early."""
        for j in idxs:
            if j is None:
                continue
            v = to_num_r(r.iloc[j], kind)
            if pd.notna(v):
                return v
        return np.nan

    idx = {"local_id": find(r"^hn\|\|"), "facility": find(r"หน่วยบริการ"),
           "sex": find(r"^เพศ"), "age": find(r"^อายุ"),
           "scheme": find(r"สิทธิการรักษา"), "dx_date": find(r"วินิจฉัย"),
           "enroll_date": find(r"วันที่เริ่มเข้าโครงการ"),
           "comorbid_raw": find(r"โรคร่วม"), "bmi_pre": find(r"ดัชนีมวลกาย ณ"),
           "waist_pre": find(r"รอบเอว ณ"), "weight_pre": find(r"น้ำหนัก ณ"),
           "fbs_pre": find(r"fbs ก่อนเข้าร่วม"),
           "hba1c_pre": find(r"hba1c ก่อนเข้าร่วม"),
           "med_other_raw": find(r"ยาโรคประจำตัวอื่น")}

    rows = []
    for i, r in body.iterrows():
        g = lambda f: r.iloc[idx[f]] if idx.get(f) is not None else None  # noqa: E731
        age = to_num_r(g("age"), "age")
        if pd.isna(age):
            continue
        row = _blank_row()
        row["local_id"] = clean_text(g("local_id")) or f"row{i + 1}"
        row["facility"] = clean_text(g("facility")) or "PCC คลองศาลา"
        row["sex"] = norm_sex(g("sex"))
        row["age"] = age
        row["scheme"] = norm_scheme(g("scheme"))
        row["dx_date"] = parse_date(g("dx_date"))
        row["enroll_date"] = parse_date(g("enroll_date"))
        row["comorbid_raw"] = clean_text(g("comorbid_raw"))
        row.update(parse_comorbidities(g("comorbid_raw")))
        row["bmi_pre"] = to_num_r(g("bmi_pre"), "bmi")
        row["waist_pre"] = to_num_r(g("waist_pre"), "waist_cm")
        row["weight_pre"] = to_num_r(g("weight_pre"), "weight_kg")
        row["fbs_pre"] = to_num_r(g("fbs_pre"), "fbs")
        row["hba1c_pre"] = to_num_r(g("hba1c_pre"), "hba1c")
        row["bmi_post"] = last_val(r, list(reversed(bmi_fu)), "bmi")
        row["waist_post"] = last_val(r, list(reversed(waist_fu)), "waist_cm")
        row["hba1c_post"] = last_val(r, hba_fu, "hba1c")
        for lab, j in fbs_fu.items():
            if j is not None and lab in {"3", "6", "9"}:
                row[f"fbs_{lab}m"] = to_num_r(r.iloc[j], "fbs")
        row["fbs_post"] = last_val(
            r, [fbs_fu["12"], fbs_fu["9"], fbs_fu["6"], fbs_fu["3"]], "fbs")

        # time-bound pull: this template labels its follow-up columns by month,
        # so the 6-month value can be read straight off
        for field, j, kind in [("hba1c", find(r"hba1c ระหว่าง.*\|\|6 mo"), "hba1c"),
                               ("bmi", find(r"ดัชนีมวลกายเมื่อสิ้นสุด.*\|\|6 mo"), "bmi"),
                               ("waist", find(r"รอบเอวระหว่.*\|\|6 mo"), "waist_cm")]:
            if j is not None:
                row[f"{field}_m6_raw"] = to_num_r(r.iloc[j], kind)
        row["med_other_raw"] = clean_text(g("med_other_raw"))

        pre = summarise(r, "pre")
        entry = summarise(r, "entry")
        m3 = summarise(r, "m3")
        m6 = summarise(r, "m6")
        if m6["status"] != "unknown":          # labelled 6-month medication
            row["on_any_m6_raw"] = m6["on_any"]
            row["n_class_m6_raw"] = m6["n_classes"]
        if m3["status"] != "unknown":          # labelled 3-month medication
            row["on_any_m3_raw"] = m3["on_any"]
        post = m6 if m6["status"] != "unknown" else m3
        base = pre if pre["status"] != "unknown" else entry
        _derive_from_regimens(row, base, m3, post)
        row["tabs_pre"] = base.get("tabs", np.nan)
        row["tabs_post"] = post.get("tabs", np.nan)
        rows.append(row)
    return _finalise(rows, "crf_pcc", path)


# --------------------------------------------------------------------------
# B. รพ.สต. summary workbooks
# --------------------------------------------------------------------------

# Sub-header label -> (target field, measurement kind).  Applied inside both
# the "ก่อน" and the "หลัง" block.
_RPHC_LABS = {
    "ส่วนสูง": ("height_cm", "height_cm"),
    "รอบเอว": ("waist", "waist_cm"),
    "เอว": ("waist", "waist_cm"),
    "นน": ("weight", "weight_kg"),
    "น้ำหนัก": ("weight", "weight_kg"),
    "fbs": ("fbs", "fbs"),
    "hba1c": ("hba1c", "hba1c"),
    "cr": ("creatinine", "creatinine"),
    "egfr": ("egfr", "egfr"),
    "total cholesterol": ("chol", "chol"),
    "hdl": ("hdl", "hdl"),
    "ldl": ("ldl", "ldl"),
    "tg": ("tg", "tg"),
}

# Sub-header label -> drug class, for the one-column-per-drug medication block.
_RPHC_DRUGS = {
    "ยา gpz": "glipizide", "ยาgpz": "glipizide", "gpz": "glipizide",
    "ยา mfm": "metformin", "ยามfm": "metformin", "mfm": "metformin",
    # รพ.สต.หนองโน's หลัง block spells it with a Latin "m"; until 2026-11-11 the
    # column went unread, so post-programme metformin was invisible there
    "ยาmfm": "metformin",
    "ยา pioglitazole": "pioglitazone", "ยา   pioglitazole": "pioglitazone",
    "pioglitazole": "pioglitazone",
    "mixtard": "insulin", "mixtrad": "insulin",
}
# "ยาไขมัน" (lipid drug) and "ยาอื่น" are recorded too but are NOT
# glucose-lowering, so they are excluded from the on/off outcome.  (Checked
# 2026-11-11: the only "ยาอื่น" columns, in หนองโน, hold antihypertensives,
# aspirin and vitamins - no glucose-lowering drug.)

# รพ.สต.หนองโน adds a "การปรับยา" block of tick boxes: หยุด / ลดยา / เท่าเดิม /
# เพิ่มยา.  Where the site stopped every drug it ticked "หยุด" and left the
# whole หลัง dose block blank, which on its own reads as "not recorded".  The
# tick resolves it (decided 2026-11-11 by Peerasit Sitthirat for the project
# team): an empty หลัง dose block plus "หยุด" is a recorded stop.  Wherever the
# dose block has a value, the dose block governs.
_RPHC_ADJUST_GROUP = "การปรับยา"
_RPHC_STOP_TICK = "หยุด"

_DM_SHEET_RE = re.compile(r"เบาหวาน|^dm$", re.I)
_EXCLUDE_SHEET_RE = re.compile(r"เสี่ยง|ความดัน|^ht$", re.I)


def load_rphc(path: str) -> pd.DataFrame:
    """Load the DM sheet of a รพ.สต. summary workbook."""
    xl = open_workbook(path)
    out = []
    for sheet in xl.sheet_names:
        if _EXCLUDE_SHEET_RE.search(sheet) or not _DM_SHEET_RE.search(sheet):
            continue
        raw = xl.parse(sheet, header=None)
        if raw.shape[0] < 4:
            continue
        # A1 holds a title such as "ข้อมูลผู้ป่วยเบาหวาน รพสต. บ้านฝาง".
        # Some sites pasted the risk-group title by mistake, so strip any
        # "ข้อมูล...เบาหวาน" preamble rather than one fixed phrase.
        title = clean_text(raw.iloc[0, 0]) or ""
        facility = re.sub(r"^ข้อมูล\S*\s*(ผู้ป่วย|กลุ่มเสี่ยง)?\s*เบาหวาน\s*", "",
                          title).strip() or None

        cols = [c.lower() for c in build_header(raw, 1, 2)]
        body = raw.iloc[3:].reset_index(drop=True)

        # map each column to (period, field)
        colmap: dict[int, tuple[str, str, str]] = {}
        id_cols: dict[str, int] = {}
        adjust_cols: dict[str, int] = {}
        for j, c in enumerate(cols):
            group, _, sub = c.partition("||")
            group, sub = group.strip(), sub.strip()
            if sub and group.startswith(_RPHC_ADJUST_GROUP):
                adjust_cols[sub] = j
                continue
            if not sub:
                if re.search(r"ชื่อ", group) and "name" not in id_cols:
                    id_cols["name"] = j
                elif re.search(r"^อายุ", group):
                    id_cols["age"] = j
                elif re.search(r"^hn", group):
                    id_cols["hn"] = j
                elif re.search(r"การศึกษา", group):
                    id_cols["education"] = j
                elif re.search(r"^ลำดับ", group):
                    id_cols["seq"] = j
                continue
            period = ("pre" if "ก่อน" in group else
                      "post" if "หลัง" in group else None)
            if period is None:
                continue
            key = sub.rstrip()
            if key in _RPHC_DRUGS:
                colmap[j] = (period, "drug", _RPHC_DRUGS[key])
            else:
                for lab, (field, kind) in _RPHC_LABS.items():
                    if key.startswith(lab):
                        colmap[j] = (period, field, kind)
                        break

        rows = []
        for i, r in body.iterrows():
            if looks_like_header(r):
                continue
            name = clean_text(r.iloc[id_cols["name"]]) if "name" in id_cols else None
            if not name:
                continue
            age = to_num_r(r.iloc[id_cols["age"]], "age") if "age" in id_cols else np.nan

            row = _blank_row()
            row["facility"] = facility
            row["local_id"] = (clean_text(r.iloc[id_cols["hn"]]) if "hn" in id_cols
                               else None) or f"row{i + 1}"
            row["age"] = age
            row["education"] = (norm_education(r.iloc[id_cols["education"]])
                                if "education" in id_cols else None)
            row["sex"] = _sex_from_thai_name(name)

            doses = {"pre": {}, "post": {}}
            for j, (period, field, kind) in colmap.items():
                if j >= len(r):
                    continue
                if field == "drug":
                    doses[period][kind] = parse_dose(r.iloc[j])
                elif field == "height_cm":
                    v = to_num_r(r.iloc[j], "height_cm")
                    if pd.notna(v):
                        row["height_cm"] = v
                else:
                    tgt = {"waist": "waist", "weight": "weight", "fbs": "fbs",
                           "hba1c": "hba1c", "creatinine": "creatinine",
                           "egfr": "egfr", "chol": "chol", "hdl": "hdl",
                           "ldl": "ldl", "tg": "tg"}[field]
                    colname = f"{tgt}_{period}"
                    if colname in SCHEMA:
                        row[colname] = to_num_r(r.iloc[j], kind)

            # BMI from height + weight where the template does not carry it
            for period in ("pre", "post"):
                w, h = row.get(f"weight_{period}"), row.get("height_cm")
                if pd.notna(w) and pd.notna(h) and h > 0:
                    bmi = w / (h / 100) ** 2
                    row[f"bmi_{period}"] = bmi if 12 <= bmi <= 70 else np.nan

            _derive_from_doses(row, doses["pre"], doses["post"])
            stop_j = adjust_cols.get(_RPHC_STOP_TICK)
            if (stop_j is not None and stop_j < len(r)
                    and clean_text(r.iloc[stop_j]) is not None
                    and row["med_status_post"] == "unknown"):
                row.update(on_any_post=0, on_insulin_post=0, n_class_post=0,
                           tabs_post=0.0, med_status_post="no_drug",
                           med_post_raw=f"{_RPHC_ADJUST_GROUP}={_RPHC_STOP_TICK}")
            rows.append(row)
        out.append(_finalise(rows, "rphc", path))
    if not out:
        return _finalise([], "rphc", path)
    return pd.concat(out, ignore_index=True)


def _derive_from_doses(row: dict, pre: dict, post: dict) -> None:
    """Derive the medication fields from per-drug daily-dose dictionaries."""
    def summarise(d):
        if not d or all(pd.isna(v) for v in d.values()):
            return dict(on_any=np.nan, on_insulin=np.nan, n_classes=np.nan,
                        tabs=np.nan, status="unknown", raw=None)
        on = {k for k, v in d.items() if pd.notna(v) and v > 0}
        oral_tabs = np.nansum([v for k, v in d.items()
                               if k != "insulin" and pd.notna(v)])
        return dict(on_any=int(len(on) > 0),
                    on_insulin=int("insulin" in on),
                    n_classes=len(on),
                    tabs=float(oral_tabs),
                    status="on_drug" if on else "no_drug",
                    raw="; ".join(f"{k}={v:g}" for k, v in sorted(d.items())
                                  if pd.notna(v)) or None)

    p, q = summarise(pre), summarise(post)

    # A "no drug" หลัง block only counts as a stop when every drug the patient
    # took at baseline has a recorded หลัง value.  If a baseline drug's หลัง cell
    # is blank while another drug is recorded 0, the template cannot say whether
    # that drug was stopped, so the follow-up status is unknown, not "stopped"
    # (decided 2026-11-11 by Peerasit Sitthirat; 4 patients at the time).
    if q["status"] == "no_drug":
        baseline_on = {k for k, v in pre.items() if pd.notna(v) and v > 0}
        if any(pd.isna(post.get(k, np.nan)) for k in baseline_on):
            q = dict(on_any=np.nan, on_insulin=np.nan, n_classes=np.nan,
                     tabs=np.nan, status="unknown", raw=q["raw"])

    for tag, d in (("pre", p), ("post", q)):
        row[f"on_any_{tag}"] = d["on_any"]
        row[f"on_insulin_{tag}"] = d["on_insulin"]
        row[f"n_class_{tag}"] = d["n_classes"]
        row[f"med_status_{tag}"] = d["status"]
    row["tabs_pre"], row["tabs_post"] = p["tabs"], q["tabs"]
    row["med_pre_raw"], row["med_post_raw"] = p["raw"], q["raw"]
    row["med_status_mid"] = "unknown"


_MALE_TITLES = ("นาย", "ด.ช.", "เด็กชาย", "พระ", "ว่าที่ร้อย", "ร.ต.", "จ.ส.อ", "พ.ต.")
_FEMALE_TITLES = ("นาง", "น.ส.", "นางสาว", "ด.ญ.", "เด็กหญิง", "นส.")


def _sex_from_thai_name(name: str | None):
    """
    Infer sex from the Thai courtesy title.

    The รพ.สต. template has no sex column, but every name carries a title
    (นาย = Mr, นาง / น.ส. = Mrs / Miss).  ``นางสาว`` and ``นาง`` both start
    with ``นาง`` so the female check runs first.
    """
    s = clean_text(name)
    if not s:
        return None
    if s.startswith(_FEMALE_TITLES):
        return "Female"
    if s.startswith(_MALE_TITLES):
        return "Male"
    return None


# --------------------------------------------------------------------------
# C. บ้านตาขุน - relational HIS export, packed follow-up strings
#
# Four sheets keyed on รหัสประจำตัวผู้เข้าร่วม:
#   ข้อมูลพื้นฐาน            demographics, diagnosis, baseline values, clinic
#                           membership status
#   ข้อมูล Lab หลังเข้าร่วม   follow-up series, "date | value | date | value ..."
#   ข้อมูลยาลดน้ำตาล         glucose-lowering drugs dispensed before / after the
#                           index date, as a pipe-separated drug list
#   ข้อมูลค่าใช้จ่าย          per-visit costs, "date | lab cost | drug cost | ..."
# --------------------------------------------------------------------------

def _unpack_series(cell, stride: int = 2):
    """
    Unpack a packed follow-up string into a date-ordered list of tuples.

    ``stride=2`` for "date | value | date | value ..."  (the lab sheet)
    ``stride=3`` for "date | lab cost | drug cost | ..." (the cost sheet)

    Returns ``[(Timestamp, v1[, v2]), ...]`` sorted by date, so ``[-1]`` is the
    most recent record and ``[0]`` the earliest.
    """
    s = clean_text(cell)
    if s is None:
        return []
    parts = [p.strip() for p in s.split("|")]
    out = []
    for i in range(0, len(parts) - stride + 1, stride):
        d = parse_date(parts[i])
        vals = [to_num(parts[i + j]) for j in range(1, stride)]
        if any(pd.notna(v) for v in vals):
            out.append((d, *vals))
    out.sort(key=lambda t: (pd.Timestamp.max if pd.isna(t[0]) else t[0]))
    return out


def load_bantakhun(path: str) -> pd.DataFrame:
    xl = open_workbook(path)
    base = xl.parse("ข้อมูลพื้นฐาน")
    lab = xl.parse("ข้อมูล Lab หลังเข้าร่วม")
    med = xl.parse("ข้อมูลยาลดน้ำตาล")
    cost = xl.parse("ข้อมูลค่าใช้จ่าย")

    key = "รหัสประจำตัวผู้เข้าร่วม"
    for d in (lab, med, cost):
        d.index = d[key].astype(str)

    def col(df, pat):
        for c in df.columns:
            if re.search(pat, str(c), re.I):
                return c
        return None

    c_lab = {"weight": col(lab, r"น้ำหนักหลัง"), "waist": col(lab, r"รอบเอวหลัง"),
             "bmi": col(lab, r"ดัชนีมวลกายหลัง"), "hba1c": col(lab, r"hba1cหลัง"),
             "fbs": col(lab, r"fbsหลัง")}
    c_med = {"pre": col(med, r"ก่อนเข้าร่วม"), "post": col(med, r"หลังเข้าร่วม")}
    c_cost = {"pre": col(cost, r"ก่อนเข้าร่วม"), "post": col(cost, r"หลังเข้าร่วม")}
    KIND = {"weight": "weight_kg", "waist": "waist_cm", "bmi": "bmi",
            "hba1c": "hba1c", "fbs": "fbs"}

    def one(df, pid):
        if pid not in df.index:
            return None
        r = df.loc[pid]
        return r.iloc[0] if isinstance(r, pd.DataFrame) else r

    rows = []
    for _, r in base.iterrows():
        pid = clean_text(r[key])
        if pid is None:
            continue
        row = _blank_row()
        row["local_id"] = pid
        row["facility"] = "รพ.บ้านตาขุน"
        row["sex"] = norm_sex(r.get("เพศ"))
        row["age"] = to_num_r(r.get("อายุ"), "age")
        row["scheme"] = norm_scheme(r.get("สิทธิการรักษา"))
        row["dx_date"] = parse_date(r.get("วันที่ได้รับการวินิจฉัย"))
        row["enroll_date"] = parse_date(r.get("วันที่เข้าร่วม"))
        row["comorbid_raw"] = clean_text(r.get("โรคร่วมสำคัญ"))
        row.update(parse_comorbidities(r.get("โรคร่วมสำคัญ")))
        row["weight_pre"] = to_num_r(r.get("น้ำหนักก่อนเข้าร่วมโครงการ"), "weight_kg")
        row["waist_pre"] = to_num_r(r.get("รอบเอวก่อนเข้าร่วมโครงการ"), "waist_cm")
        row["bmi_pre"] = to_num_r(r.get("ดัชนีมวลกายก่อนเข้าร่วมโครงการ"), "bmi")
        row["fbs_pre"] = to_num_r(r.get("fbsก่อนเข้าร่วมโครงการ"), "fbs")
        row["hba1c_pre"] = to_num_r(r.get("hba1cก่อนเข้าร่วมโครงการ"), "hba1c")

        # clinic membership and care setting - only in this export
        row["member_status"] = clean_text(r.get("clinic_member_status_name"))
        row["clinic_first"] = clean_text(r.get("first_clinic"))
        row["clinic_last"] = clean_text(r.get("last_clinic"))
        row["care_note"] = clean_text(r.get("note"))

        # ---- follow-up series -------------------------------------------
        lr = one(lab, pid)
        last_dates, n_meas = [], 0
        if lr is not None:
            for field, c in c_lab.items():
                if c is None:
                    continue
                series = _unpack_series(lr[c], stride=2)
                if not series:
                    continue
                n_meas = max(n_meas, len(series))
                lo, hi = RANGES[KIND[field]]
                val = series[-1][1]
                row[f"{field}_post"] = val if lo <= val <= hi else np.nan
                if pd.notna(series[-1][0]):
                    last_dates.append(series[-1][0])
        row["n_post_measures"] = n_meas or np.nan
        if last_dates and pd.notna(row["enroll_date"]):
            months = (max(last_dates) - row["enroll_date"]).days / 30.44
            row["followup_months"] = months if 0 < months < 120 else np.nan

        # time-bound pulls: the measurement nearest each anchor, accepted only
        # inside that anchor's tolerance window
        if lr is not None:
            for anchor, (target, tol, _src) in ANCHORS.items():
                offsets = []
                for field, c in c_lab.items():
                    if c is None or field == "weight":
                        continue
                    hit = pick_nearest(_unpack_series(lr[c], stride=2),
                                       row["enroll_date"], target, tol)
                    if hit is None:
                        continue
                    off, val = hit
                    lo, hi = RANGES[KIND[field]]
                    if lo <= val <= hi:
                        row[f"{field}_{anchor}_raw"] = val
                        offsets.append(off)
                if offsets:
                    row[f"{anchor}_offset_months"] = float(np.mean(offsets))

        # ---- costs -------------------------------------------------------
        cr = one(cost, pid)
        n_post_visits = 0
        if cr is not None:
            for tag in ("pre", "post"):
                c = c_cost[tag]
                if c is None:
                    continue
                series = _unpack_series(cr[c], stride=3)
                if not series:
                    continue
                if tag == "post":
                    n_post_visits = len(series)
                    row["drugcost_post_last"] = series[-1][2]
                row[f"labcost_{tag}"] = float(np.nanmean([t[1] for t in series]))
                row[f"drugcost_{tag}"] = float(np.nanmean([t[2] for t in series]))
        row["n_post_visits"] = n_post_visits or np.nan

        # ---- medication --------------------------------------------------
        # The drug columns are a pipe-separated list of every glucose-lowering
        # drug DISPENSED in the window - not a current-regimen field.  A blank
        # post cell is therefore ambiguous on its own: it means either "no drug
        # dispensed after the index date" (a genuine stop) or "this patient was
        # never followed up".
        #
        # The other three sheets resolve it.  A patient with post-index
        # laboratory results or post-index visits demonstrably kept attending,
        # so a blank drug list for them means no glucose-lowering drug was
        # dispensed.  With no post-index contact at all, the cell stays missing.
        #
        # This inference is validated against pharmacy cost in notebook 01:
        # the "blank and still attending" group averages ~97 THB of drug cost
        # per visit against ~910 THB for those still on drugs, and 63 % of them
        # have zero drug cost at their last visit.
        mr = one(med, pid)
        pre_txt = post_txt = None
        if mr is not None:
            pre_txt = clean_text(mr[c_med["pre"]]) if c_med["pre"] else None
            post_txt = clean_text(mr[c_med["post"]]) if c_med["post"] else None

        engaged = bool(n_post_visits) or n_meas > 0
        row["post_engaged"] = int(engaged)

        pre_reg = parse_regimen(pre_txt)
        if post_txt is None and engaged:
            post_reg = {"classes": set(), "n_classes": 0, "on_any": 0,
                        "on_insulin": 0, "n_oral": 0,
                        "status": "no_drug_inferred", "raw": None}
        else:
            post_reg = parse_regimen(post_txt)
        _derive_from_regimens(row, pre_reg, parse_regimen(None), post_reg)
        rows.append(row)
    return _finalise(rows, "relational", path)


# --------------------------------------------------------------------------
# D. "for edit" survey export
# --------------------------------------------------------------------------

def load_survey(path: str) -> pd.DataFrame:
    """
    The Google-Forms export.  Its ``medication`` sheet is the widest one and
    is the only sheet with both a baseline and a 3-month HbA1c plus pre/post
    weight and waist, so that is the sheet used.
    """
    xl = open_workbook(path)
    df = xl.parse("medication")
    bg = xl.parse("background")

    def col(d, pat):
        for c in d.columns:
            if re.search(pat, str(c), re.I):
                return c
        return None

    # sex / education live only on the background sheet -> join on name + HN
    bg_key = col(bg, r"ชื่อ-สกุล")
    bg_sex = col(bg, r"^เพศ")
    bg_edu = col(bg, r"^การศึกษา")
    bg_dm_year = col(bg, r"ปีที่เป็นโรคเบาหวาน")
    lookup = {}
    if bg_key:
        for _, r in bg.iterrows():
            k = clean_text(r[bg_key])
            if k and k not in lookup:
                lookup[k] = r

    c = {
        "facility": col(df, r"หน่วยงาน"), "name": col(df, r"ชื่อ-สกุล"),
        "age": col(df, r"^อายุ"), "hn": col(df, r"^hn$"),
        "comorbid": col(df, r"โรคประจำตัวอื่น"),
        "tabs": col(df, r"จำนวนเม็ดยาเบาหวาน"),
        "inj": col(df, r"^จำนวนยาฉีด$"), "meds": col(df, r"ยาที่ใช้ประจำ"),
        # follow-up drug burden at 3 months - the form records counts, not a regimen
        "tabs_post": col(df, r"จำนวนเม็ดยาหลัง"),
        "inj_post": col(df, r"จำนวนยาฉีดหลัง"),
        "w_pre": col(df, r"น้ำหนัก ก่อน"), "w_post": col(df, r"น้ำหนักหลัง"),
        "waist_pre": col(df, r"รอบเอวก่อน"), "waist_post": col(df, r"รอบเอวหลัง"),
        "height": col(df, r"ส่วนสูง"), "a1c_pre": col(df, r"^hba1c$"),
        "a1c_post": col(df, r"hba1c 3 เดือน"),
    }

    rows = []
    for i, r in df.iterrows():
        name = clean_text(r[c["name"]]) if c["name"] else None
        if not name:
            continue
        row = _blank_row()
        row["local_id"] = clean_text(r[c["hn"]]) if c["hn"] else f"row{i + 1}"
        row["facility"] = clean_text(r[c["facility"]]) if c["facility"] else None
        row["age"] = to_num_r(r[c["age"]], "age") if c["age"] else np.nan
        row["comorbid_raw"] = clean_text(r[c["comorbid"]]) if c["comorbid"] else None
        row.update(parse_comorbidities(row["comorbid_raw"]))
        row["height_cm"] = to_num_r(r[c["height"]], "height_cm") if c["height"] else np.nan
        row["weight_pre"] = to_num_r(r[c["w_pre"]], "weight_kg") if c["w_pre"] else np.nan
        row["weight_post"] = to_num_r(r[c["w_post"]], "weight_kg") if c["w_post"] else np.nan
        row["waist_pre"] = to_num_r(r[c["waist_pre"]], "waist_cm") if c["waist_pre"] else np.nan
        row["waist_post"] = to_num_r(r[c["waist_post"]], "waist_cm") if c["waist_post"] else np.nan
        row["hba1c_pre"] = to_num_r(r[c["a1c_pre"]], "hba1c") if c["a1c_pre"] else np.nan
        row["hba1c_post"] = to_num_r(r[c["a1c_post"]], "hba1c") if c["a1c_post"] else np.nan
        for period in ("pre", "post"):
            w, h = row[f"weight_{period}"], row["height_cm"]
            if pd.notna(w) and pd.notna(h) and h > 0:
                b = w / (h / 100) ** 2
                row[f"bmi_{period}"] = b if 12 <= b <= 70 else np.nan

        bgr = lookup.get(name)
        if bgr is not None:
            row["sex"] = norm_sex(bgr[bg_sex]) if bg_sex else None
            row["education"] = norm_education(bgr[bg_edu]) if bg_edu else None
            if bg_dm_year:
                y = to_num(bgr[bg_dm_year])
                if pd.notna(y) and y > 2400:
                    row["dx_date"] = pd.Timestamp(year=int(y) - 543, month=7, day=1)
        # the background sheet's sex field is often blank; fall back to the
        # Thai courtesy title in the name
        if row["sex"] is None or (isinstance(row["sex"], float) and pd.isna(row["sex"])):
            row["sex"] = _sex_from_thai_name(name)

        # Medication in this export is a COUNT of tablets and injections, at
        # baseline and again at 3 months - not a regimen field like the CRF's.
        # "On a drug" therefore means "count > 0", which is a weaker statement
        # than a named regimen: it cannot distinguish a diabetes tablet from a
        # mis-entered one, and it carries no drug classes.  The cohort's
        # outcome is tagged `count_based` so the notebook never silently
        # compares it with the programme cohort's regimen-based figure.
        def cnt(key):
            return to_num(r[c[key]]) if c.get(key) else np.nan

        tabs, inj = cnt("tabs"), cnt("inj")
        tabs_post, inj_post = cnt("tabs_post"), cnt("inj_post")

        row["tabs_pre"] = tabs
        row["tabs_post"] = tabs_post
        if pd.notna(tabs) or pd.notna(inj):
            row["on_any_pre"] = int((tabs or 0) > 0 or (inj or 0) > 0)
            row["on_insulin_pre"] = int((inj or 0) > 0)
            row["med_status_pre"] = "on_drug" if row["on_any_pre"] else "no_drug"
        if pd.notna(tabs_post) or pd.notna(inj_post):
            row["on_any_post"] = int((tabs_post or 0) > 0 or (inj_post or 0) > 0)
            row["on_insulin_post"] = int((inj_post or 0) > 0)
            row["med_status_post"] = "on_drug" if row["on_any_post"] else "no_drug"
            row["on_any_m3_raw"] = row["on_any_post"]
        else:
            row["med_status_post"] = "unknown"
        row["med_pre_raw"] = clean_text(r[c["meds"]]) if c["meds"] else None
        row["hba1c_m3_raw"] = row["hba1c_post"]      # the form's "HbA1C 3 เดือน"
        row["waist_m3_raw"] = row["waist_post"]      # "รอบเอวหลัง 3 เดือน"
        rows.append(row)
    return _finalise(rows, "survey", path)


# --------------------------------------------------------------------------
# file routing
# --------------------------------------------------------------------------

def classify_file(path: str) -> str:
    """
    Decide which loader a workbook needs, **from its contents**.

    Routing deliberately does not depend on the filename: the source files were
    renamed to their facility name for legibility (see
    ``data/case_report/_filename_map.csv``), and a pipeline that broke when a
    file was renamed would be a trap.  Every rule below inspects sheet names or
    header text instead.
    """
    try:
        xl = open_workbook(path)
        sheets = xl.sheet_names
    except Exception:
        return "unknown"

    # C - the relational HIS export: four specific, uniquely-named sheets
    if {"ข้อมูลพื้นฐาน", "ข้อมูลยาลดน้ำตาล"} <= set(sheets):
        return "relational"

    # D - the Google-Forms export: a `medication` sheet beside a `background` one
    if {"medication", "background"} <= set(sheets):
        return "survey"

    # B - รพ.สต. summary: a DM sheet AND a hypertension/risk sheet side by side
    if (any(_DM_SHEET_RE.search(s) and not _EXCLUDE_SHEET_RE.search(s) for s in sheets)
            and any(_EXCLUDE_SHEET_RE.search(s) for s in sheets)):
        return "rphc"

    # the remaining CRF variants are told apart by their header row
    try:
        head = xl.parse(sheets[0], header=None, nrows=4)
        cells = [clean_text(v) or "" for _, row in head.iterrows() for v in row]
        joined = " | ".join(cells).lower()
    except Exception:
        return "crf"

    # A'' - PCC: one column per drug per visit, and monthly anthropometry
    if "1 mo." in joined and "ยาลดระดับน้ำตาลวันเข้าร่วมโครงการ" in joined:
        return "pcc"
    # A' - บางระกำ: grouped two-row header using these short labels
    if "เลขบัตรปชช" in joined and "วันที่ dx." in joined:
        return "bangrakam"
    return "crf"


LOADERS = {
    "crf": load_crf,
    "bangrakam": load_bangrakam,
    "pcc": load_pcc,
    "rphc": load_rphc,
    "relational": load_bantakhun,
    "survey": load_survey,
}


# --------------------------------------------------------------------------
# duplicate handling
# --------------------------------------------------------------------------

# หูแร่ submitted three overlapping workbooks (an original plus two
# "เพิ่มเติม" versions that re-send the original rows).  Keep the largest.
def drop_duplicate_patients(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Remove patients sent in more than one workbook.

    Identity key: facility + sex + age + the baseline measurement vector.
    Names are not available in every family and are not needed: within a
    facility the chance of two patients sharing sex, age, baseline BMI,
    waist, FBS and HbA1c to the recorded precision is negligible.
    The record kept is the one from the file contributing the most rows,
    which is the most recent resubmission.
    """
    key_cols = ["facility", "sex", "age", "bmi_pre", "waist_pre",
                "fbs_pre", "hba1c_pre"]
    k = df[key_cols].astype(str).agg("|".join, axis=1)
    # rows whose key is all-missing cannot be matched; never treat as dupes
    informative = df[["age", "bmi_pre", "fbs_pre", "hba1c_pre"]].notna().sum(axis=1) >= 2
    file_size = df["source_file"].map(df["source_file"].value_counts())
    order = pd.DataFrame({"k": k, "inf": informative, "sz": file_size}).sort_values(
        ["sz"], ascending=False)
    seen, keep_idx = set(), []
    for idx in order.index:
        if not informative.loc[idx]:
            keep_idx.append(idx)
            continue
        if k.loc[idx] in seen:
            continue
        seen.add(k.loc[idx])
        keep_idx.append(idx)
    keep = df.loc[sorted(keep_idx)]
    dropped = df.drop(index=keep.index)
    return keep.reset_index(drop=True), dropped.reset_index(drop=True)


# --------------------------------------------------------------------------
# hand-checked date decisions
# --------------------------------------------------------------------------

DATE_CORRECTIONS = ROOT / "data" / "corrections" / "date_corrections.csv"
_DATE_ACTIONS = {"blank", "set", "keep"}


def apply_date_corrections(df: pd.DataFrame, path: str | Path = DATE_CORRECTIONS
                           ) -> pd.DataFrame:
    """
    Apply the date decisions recorded in ``data/corrections/date_corrections.csv``.

    Each rule picks out one record without any identifier: the source file, the
    date field with its parsed value, and the other date on the same row.  The
    ``action`` is ``blank`` (the cell is wrong and the right value cannot be read
    off it, so it is set missing rather than guessed), ``set`` (replace with
    ``new_value``) or ``keep`` (checked and left as it is; the rule records why).
    The ``date_correction`` column marks every record a rule touched.

    A rule that matches no record is reported and skipped, so a resubmitted
    workbook with the date fixed at source simply stops matching.  A rule that
    matches more than one record is an error.
    """
    df = df.copy()
    df["date_correction"] = None
    if not Path(path).exists():
        return df
    rules = pd.read_csv(path, dtype=str, encoding="utf-8").fillna("")
    for _, r in rules.iterrows():
        if r["action"] not in _DATE_ACTIONS:
            raise ValueError(f"unknown date-correction action: {r.to_dict()}")
        field, other = r["field"], r["other_field"]
        hit = (df["source_file"].eq(r["source_file"])
               & pd.to_datetime(df[field]).eq(pd.Timestamp(r["value"]))
               & pd.to_datetime(df[other]).eq(pd.Timestamp(r["other_value"])))
        n = int(hit.sum())
        if n > 1:
            raise ValueError(f"date correction matches {n} records: {r.to_dict()}")
        if n == 0:
            print(f"date correction matched no record (fixed at source?): "
                  f"{r['source_file']} {field}={r['value']}")
            continue
        if r["action"] == "blank":
            df.loc[hit, field] = pd.NaT
        elif r["action"] == "set":
            df.loc[hit, field] = pd.Timestamp(r["new_value"])
        df.loc[hit, "date_correction"] = f"{field}:{r['action']}"
    return df


# --------------------------------------------------------------------------
# derived analysis variables
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# time-bound ("at 6 months") outcomes
#
# The original outcomes used each patient's LAST recorded value, which is not
# anchored in time: "post" meant 3-12 months depending on the site.  These
# variables fix the timepoint instead, at 6 months after enrolment.
#
# The workbooks support that anchor very unevenly, so every 6-month value
# carries a tier saying HOW its timing was established.  Nothing is silently
# assumed - the assumption is a column.
#
#   measured  a real measurement date, taken from a dated follow-up series and
#             accepted when it falls within +/- TOL months of the target.
#             (บ้านตาขุน only - it is the sole workbook with dates.)
#   labelled  a column the template explicitly labels as that many months
#             since enrolment: the CRF's "FBS ระหว่างเข้าร่วมโครงการ 6 เดือน"
#             and PCC คลองศาลา's "6 mo." columns.
#   assumed   a single unlabelled follow-up column, taken to be about 6 months.
#             Applies to the รพ.สต. template - whose *risk-group* sheet, in the
#             same workbook, is labelled "หลังเข้าโครงการ 6 เดือน" - and to the
#             CRF's mid-programme columns.
#
# NOTE ON THE CRF: its "หลังจบโครงการ 6 เดือน" columns are anchored to the
# programme's END, not to enrolment.  That is a different clock and is NOT
# used for these variables; the mid-programme column is used instead, at the
# `assumed` tier.
# --------------------------------------------------------------------------

M6_TARGET = 6.0          # months after enrolment
M6_TOL = 3.0             # a measurement 3-9 months out still counts as "6 months"
M3_TARGET = 3.0          # a second anchor, for the sources that only reach 3 months
M3_TOL = 1.5             # 1.5-4.5 months; narrower so the two windows stay distinct

# (source_family, measure) -> (source column, tier)
M6_SOURCE = {
    # บ้านตาขุน: extracted from the dated series by the loader
    ("relational", "hba1c"): ("hba1c_m6_raw", "measured"),
    ("relational", "fbs"):   ("fbs_m6_raw", "measured"),
    ("relational", "bmi"):   ("bmi_m6_raw", "measured"),
    ("relational", "waist"): ("waist_m6_raw", "measured"),
    ("relational", "med"):   (None, None),   # drug sheet carries no dates

    # PCC คลองศาลา: explicit "6 mo." columns
    ("crf_pcc", "hba1c"): ("hba1c_m6_raw", "labelled"),
    ("crf_pcc", "fbs"):   ("fbs_6m", "labelled"),
    ("crf_pcc", "bmi"):   ("bmi_m6_raw", "labelled"),
    ("crf_pcc", "waist"): ("waist_m6_raw", "labelled"),
    ("crf_pcc", "med"):   ("on_any_m6_raw", "labelled"),

    # CRF: only FBS is labelled against enrolment - and only in the 24-column
    # version.  The 22-column version (รพ.พิมาย) has a single unlabelled
    # "FBS ระหว่างเข้าร่วมโครงการ" column, which is `assumed`, not `labelled`.
    # The value is a list tried in order, so those rows fall through to the
    # weaker tier instead of borrowing the stronger one.
    ("crf", "hba1c"): ("hba1c_mid", "assumed"),
    ("crf", "fbs"):   [("fbs_m6_raw", "labelled"), ("fbs_6m", "assumed")],
    ("crf", "bmi"):   ("bmi_post", "assumed"),
    ("crf", "waist"): ("waist_post", "assumed"),
    ("crf", "med"):   ("on_any_mid", "assumed"),

    # รพ.สต.: one unlabelled "หลัง" block
    ("rphc", "hba1c"): ("hba1c_post", "assumed"),
    ("rphc", "fbs"):   ("fbs_post", "assumed"),
    ("rphc", "bmi"):   ("bmi_post", "assumed"),
    ("rphc", "waist"): ("waist_post", "assumed"),
    ("rphc", "med"):   ("on_any_post", "assumed"),

    # survey export: its only follow-up HbA1c is at 3 months, not 6
    ("survey", "hba1c"): (None, None),
    ("survey", "fbs"):   (None, None),
    ("survey", "bmi"):   (None, None),
    ("survey", "waist"): (None, None),
    ("survey", "med"):   (None, None),
}

# The 3-month anchor.  Far fewer sources reach it, and it exists mainly so the
# 2566 survey export - whose only follow-up is at 3 months - can be analysed at
# its own timepoint instead of being dropped or silently compared with 6-month
# figures.  An entry missing here simply means that source has no 3-month value.
M3_SOURCE = {
    ("survey", "hba1c"): ("hba1c_m3_raw", "labelled"),
    ("survey", "waist"): ("waist_m3_raw", "labelled"),
    ("survey", "med"):   ("on_any_m3_raw", "labelled"),

    ("relational", "hba1c"): ("hba1c_m3_raw", "measured"),
    ("relational", "fbs"):   ("fbs_m3_raw", "measured"),
    ("relational", "bmi"):   ("bmi_m3_raw", "measured"),
    ("relational", "waist"): ("waist_m3_raw", "measured"),

    ("crf", "fbs"):     ("fbs_3m", "labelled"),
    ("crf_pcc", "fbs"): ("fbs_3m", "labelled"),
    ("crf_pcc", "med"): ("on_any_m3_raw", "labelled"),
}

ANCHORS = {"m6": (M6_TARGET, M6_TOL, M6_SOURCE), "m3": (M3_TARGET, M3_TOL, M3_SOURCE)}

M6_MEASURES = ["hba1c", "fbs", "bmi", "waist", "med"]
# Tiers accepted in the primary time-bound analysis.
M6_PRIMARY_TIERS = ("measured", "labelled")


def pick_nearest(series, enroll, target=M6_TARGET, tol=M6_TOL):
    """
    From a dated series, the measurement closest to ``target`` months after
    ``enroll``, provided it lies within ``tol`` months of it.

    Returns ``(offset_in_months, value)`` or ``None``.
    """
    if pd.isna(enroll):
        return None
    best = None
    for item in series:
        d, v = item[0], item[1]
        if pd.isna(d) or pd.isna(v):
            continue
        off = (d - enroll).days / 30.44
        if abs(off - target) <= tol and (
                best is None or abs(off - target) < abs(best[0] - target)):
            best = (off, v)
    return best


# --------------------------------------------------------------------------
# facility registry: canonical names and provider level
#
# Sites wrote their own name into the workbook, so the same facility appears as
# "รพสต. บ้านหนองโอง", "หนองโก", "โรงพยาบาลกงหรา" and so on.  FACILITY_INFO is
# the single place those raw strings are mapped onto a canonical name and a
# provider level, supplied by the programme team.
#
#   community_hospital  โรงพยาบาลชุมชน - a district hospital with inpatient
#                       beds, its own pharmacy and laboratory
#   primary_care        โรงพยาบาลส่งเสริมสุขภาพตำบล (รพ.สต.) - a sub-district
#                       health-promoting hospital, no inpatient beds
#
# Two entries need explaining:
#   * PCC คลองศาลา is counted as community_hospital despite the "PCC" name.
#     The project team agreed this because คลองศาลา was split off from
#     รพ.เพชรบูรณ์ into a new building of its own, staffed by dedicated doctors
#     and nurses, so its capacity is that of a community hospital (reason given
#     by Peerasit Sitthirat for the team, 2026-11-11; replaces the earlier note
#     that it sits inside a community hospital).
#   * The workbook labelled "โรงพยาบาลกงหรา" is in fact from รพ.สต.บ้านโล๊ะจังกะ,
#     a health centre in that hospital's network (confirmed by the programme
#     team).  It is renamed here and counted as primary_care.
# --------------------------------------------------------------------------

COMMUNITY_HOSPITAL = "community_hospital"
PRIMARY_CARE = "primary_care"

FACILITY_INFO = {
    # raw string in the workbook -> (canonical name, provider level)
    "รพ.ท่าวุ้ง":                              ("รพ.ท่าวุ้ง", COMMUNITY_HOSPITAL),
    "รพ.บางระกำ":                              ("รพ.บางระกำ", COMMUNITY_HOSPITAL),
    "รพ. พิมาย":                               ("รพ.พิมาย", COMMUNITY_HOSPITAL),
    "PCC คลองศาลา":                            ("PCC คลองศาลา", COMMUNITY_HOSPITAL),
    "อุ้มผาง":                                 ("รพ.อุ้มผาง", COMMUNITY_HOSPITAL),
    "รพ.อุ้มผาง":                              ("รพ.อุ้มผาง", COMMUNITY_HOSPITAL),
    "รพ.บ้านตาขุน":                            ("รพ.บ้านตาขุน", COMMUNITY_HOSPITAL),

    "รพ.สต.หูแร่":                             ("รพ.สต.หูแร่", PRIMARY_CARE),
    "โรงพยาบาลกงหรา":                          ("รพ.สต.บ้านโล๊ะจังกะ", PRIMARY_CARE),
    "รพสต. บ้านฝาง":                           ("รพ.สต.บ้านฝาง", PRIMARY_CARE),
    "รพสต. ดูนสาด":                            ("รพ.สต.ดูนสาด", PRIMARY_CARE),
    "รพสต.หัวนาคำ":                            ("รพ.สต.หัวนาคำ", PRIMARY_CARE),
    "รพ.สต. บ้านโนนสมบูรณ์":                   ("รพ.สต.บ้านโนนสมบูรณ์", PRIMARY_CARE),
    "รพสต. บ้านโนนสัง อ.กระนวน จ.ขอนแก่น":     ("รพ.สต.บ้านโนนสัง", PRIMARY_CARE),
    "รพสต. บ้านหนองโอง":                       ("รพ.สต.บ้านหนองโอง", PRIMARY_CARE),
    "รพสต. ห้วยยาง อ.กระนวน จ.ขอนแก่น":        ("รพ.สต.ห้วยยาง", PRIMARY_CARE),
    "รพสต.หนองกุงใหญ่ อ.กระนวน จ.ขอนแก่น":     ("รพ.สต.หนองกุงใหญ่", PRIMARY_CARE),
    "รพสต. รพ.ต.น้ำอ้อม":                      ("รพ.สต.น้ำอ้อม", PRIMARY_CARE),
    "รพสต. บ้านทุ่งใหญ่ อ.กระนวน จ.ขอนแก่น":   ("รพ.สต.บ้านทุ่งใหญ่", PRIMARY_CARE),
    "รพ.สต. หนองโน":                           ("รพ.สต.หนองโน", PRIMARY_CARE),
    "รพสต.ห้วยโจด อ.กระนวน จ.ขอนแก่น":         ("รพ.สต.ห้วยโจด", PRIMARY_CARE),
    "หนองโก":                                  ("รพ.สต.หนองโก", PRIMARY_CARE),
}


def resolve_facility(raw):
    """Canonical facility name and provider level for a raw workbook string."""
    name = clean_text(raw)
    if name is None:
        return (None, None)
    if name in FACILITY_INFO:
        return FACILITY_INFO[name]
    # the 2023 survey export names รพ.สต. in full; everything in it is
    # primary care except the district hospital entries
    if name.startswith("โรงพยาบาลส่งเสริมสุขภาพตำบล"):
        short = name.replace("โรงพยาบาลส่งเสริมสุขภาพตำบล", "รพ.สต.").strip()
        return (short, PRIMARY_CARE)
    if name.startswith("โรงพยาบาล") or name.startswith("รพ."):
        return (name, COMMUNITY_HOSPITAL)
    return (name, None)


# --------------------------------------------------------------------------
# cohort definition
#
# The 24 workbooks are not all the same study, so each patient is tagged.
#
#   program        the DM-Remission cohort proper: the CRF workbooks, the
#                  รพ.สต. summary workbooks, PCC คลองศาลา and บางระกำ.
#                  Baseline and end-of-programme values, and a medication
#                  field recording the current regimen at each visit.
#
#   registry       รพ.บ้านตาขุน.  A hospital-information-system export of the
#                  diabetes register, indexed at 1 Oct 2023 (that one date is
#                  the only value in วันที่เข้าร่วม).  It is a *register*, not a
#                  programme roster: it includes 115 patients recorded as
#                  deceased, 78 lost to follow-up and 25 who moved away, and
#                  its care-setting note lists patients treated at other
#                  hospitals entirely.
#
#                  Its medication field is a dispensing list rather than a
#                  current regimen, but the other three sheets make cessation
#                  recoverable - see the note in ``load_bantakhun``.  It is
#                  therefore analysable for the medication outcome as well as
#                  the biochemical ones, and ``med_outcome_valid`` is True.
#                  It is still reported as its own cohort, because a register
#                  containing deceased and disengaged patients is a different
#                  population from a programme roster.
#
#   survey_2023    the "for edit" Google-Forms export.  Baseline and 3-month
#                  HbA1c, and a baseline tablet count, but no follow-up
#                  medication column at all - cessation is not recoverable.
# --------------------------------------------------------------------------

COHORT_OF_FAMILY = {
    "crf": "program", "crf_pcc": "program", "rphc": "program",
    "relational": "registry", "survey": "survey_2023",
}

# Cohorts in which a drug-cessation outcome can actually be measured.
#
# The 2566 survey joins this set, but on a different footing from the other
# two: its medication is a COUNT of tablets and injections at baseline and at
# 3 months, not a named regimen.  `med_outcome_basis` records that difference
# so nothing downstream compares a count-based rate with a regimen-based one
# by accident.
MED_OUTCOME_COHORTS = {"program", "registry", "survey_2023"}

MED_OUTCOME_BASIS = {
    "program": "regimen",       # the drug actually prescribed at each visit
    "registry": "dispensing",   # drugs dispensed, plus attendance evidence
    "survey_2023": "count",     # a tablet / injection count
}

# The follow-up timepoint each cohort's medication outcome is measured at.
MED_OUTCOME_ANCHOR = {"program": "m6", "registry": None, "survey_2023": "m3"}

# Registry membership states that mean the patient was still in active care.
# Death, disengagement and transfer out are recorded explicitly, so they can be
# excluded rather than silently diluting a follow-up outcome.
ACTIVE_MEMBER_STATUS = "ยังรักษาอยู่"


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add the change scores, outcome flags and analysis covariates."""
    df = df.copy()

    df["cohort"] = df["source_family"].map(COHORT_OF_FAMILY).fillna("other")
    df["med_outcome_valid"] = df["cohort"].isin(MED_OUTCOME_COHORTS)
    df["med_outcome_basis"] = df["cohort"].map(MED_OUTCOME_BASIS)

    # Active in care at the time of the extract.  Only the registry records a
    # membership state; everywhere else the patient is in the cohort by virtue
    # of having been enrolled, so they count as active.
    df["active_in_care"] = np.where(
        df["member_status"].notna(),
        df["member_status"].eq(ACTIVE_MEMBER_STATUS), True)

    # implausible tablet counts are dispensing quantities, not daily doses
    for c in ("tabs_pre", "tabs_post"):
        df[c] = df[c].where(df[c].between(0, MAX_TABS_PER_DAY))

    # tidy the facility strings (the รพ.สต. titles carry dot leaders)
    df["facility"] = (df["facility"].astype(str)
                      .str.replace(r"[.…]{3,}", "", regex=True)
                      .str.replace(r"\s+", " ", regex=True).str.strip()
                      .replace({"": np.nan, "nan": np.nan, "None": np.nan}))
    # a few sites recorded a facility *code* instead of a name (อุ้มผาง wrote
    # 11243); fall back to the site named in the file
    numeric_fac = df["facility"].astype(str).str.fullmatch(r"\d+").fillna(False)
    df.loc[numeric_fac, "facility"] = (
        df.loc[numeric_fac, "source_file"].str.replace(r"\.xlsx?$", "", regex=True)
        .str.split(r"[ _]").str[0])

    # canonical facility name + provider level (see FACILITY_INFO)
    resolved = df["facility"].map(resolve_facility)
    df["facility"] = resolved.map(lambda t: t[0])
    df["provider_level"] = resolved.map(lambda t: t[1])

    # Last observed regimen: the end-of-programme column where the site filled
    # it in, otherwise the during-programme column.  Many CRF workbooks left
    # "ยาลดระดับน้ำตาลหลังจบจากโครงการ" blank because the programme had not
    # ended, but recorded the during-programme regimen.
    df["on_any_last"] = df["on_any_post"].where(
        df["on_any_post"].notna(), df["on_any_mid"])
    df["n_class_last"] = df["n_class_post"].where(
        df["n_class_post"].notna(), df["n_class_mid"])
    df["med_last_timepoint"] = np.where(
        df["on_any_post"].notna(), "end_of_programme",
        np.where(df["on_any_mid"].notna(), "during_programme", None))

    # ---- time-bound ("at 6 months") variables --------------------------
    # For each measure, pull the value its layout can offer for the 6-month
    # timepoint, and record which tier that value came from.  The tier is
    # carried as data so the primary analysis can restrict to measured +
    # labelled and the sensitivity analysis can add assumed.
    def fill_anchor(frame, anchor, source_map):
        """
        Populate `<measure>_<anchor>` and its `_tier` for every source family.

        A source spec may be a list, tried in order, so a family whose stronger
        column is empty for a given row falls through to the weaker tier rather
        than borrowing the stronger one's label.
        """
        for measure in M6_MEASURES:
            tgt = f"on_any_{anchor}" if measure == "med" else f"{measure}_{anchor}"
            frame[tgt] = np.nan
            frame[f"{tgt}_tier"] = None
            for fam, grp in frame.groupby("source_family"):
                spec = source_map.get((fam, measure), (None, None))
                chain = spec if isinstance(spec, list) else [spec]
                for src, tier in chain:
                    if src is None or src not in frame.columns:
                        continue
                    vals = pd.to_numeric(grp[src], errors="coerce")
                    take = vals.notna() & frame.loc[grp.index, tgt].isna()
                    frame.loc[grp.index[take], tgt] = vals[take]
                    frame.loc[grp.index[take], f"{tgt}_tier"] = tier
            # a tier only means something where a value actually landed
            frame.loc[frame[tgt].isna(), f"{tgt}_tier"] = None

    for anchor, (_t, _tol, source_map) in ANCHORS.items():
        fill_anchor(df, anchor, source_map)

    df["n_class_m6"] = np.where(
        df["source_family"].eq("crf_pcc"), df["n_class_m6_raw"],
        np.where(df["source_family"].eq("crf"), df["n_class_mid"],
                 np.where(df["source_family"].eq("rphc"), df["n_class_post"], np.nan)))

    # one overall timing grade per patient: the weakest tier among the
    # measures they actually contribute
    _rank = {"measured": 0, "labelled": 1, "assumed": 2}
    tier_cols = [f"{('on_any_m6' if m == 'med' else m + '_m6')}_tier" for m in M6_MEASURES]
    df["m6_tier"] = (df[tier_cols].apply(
        lambda r: max((t for t in r if isinstance(t, str)),
                      key=lambda t: _rank[t], default=None), axis=1))
    df["m6_primary"] = df["m6_tier"].isin(M6_PRIMARY_TIERS)

    # changes at 6 months
    df["d_hba1c_m6"] = df["hba1c_m6"] - df["hba1c_pre"]
    df["d_fbs_m6"] = df["fbs_m6"] - df["fbs_pre"]
    df["d_bmi_m6"] = df["bmi_m6"] - df["bmi_pre"]
    df["d_waist_m6"] = df["waist_m6"] - df["waist_pre"]

    # follow-up glycaemia: the latest available value
    df["fbs_last"] = df[["fbs_post", "fbs_9m", "fbs_6m", "fbs_3m"]].bfill(axis=1).iloc[:, 0]
    df["hba1c_last"] = df[["hba1c_post", "hba1c_mid"]].bfill(axis=1).iloc[:, 0]

    # change scores
    df["d_fbs"] = df["fbs_last"] - df["fbs_pre"]
    df["d_hba1c"] = df["hba1c_last"] - df["hba1c_pre"]
    df["d_bmi"] = df["bmi_post"] - df["bmi_pre"]
    df["d_waist"] = df["waist_post"] - df["waist_pre"]
    df["d_weight"] = df["weight_post"] - df["weight_pre"]
    df["d_tabs"] = df["tabs_post"] - df["tabs_pre"]
    df["pct_weight_loss"] = np.where(
        df["weight_pre"].notna() & df["weight_post"].notna() & (df["weight_pre"] > 0),
        -(df["weight_post"] - df["weight_pre"]) / df["weight_pre"] * 100, np.nan)

    # ---- diabetes duration at enrolment -------------------------------
    # enrolment date minus diagnosis date, in years.
    dur = (df["enroll_date"] - df["dx_date"]).dt.days / 365.25
    df["dm_duration_y"] = dur.where((dur >= 0) & (dur <= 50))

    # A negative duration means the diagnosis is dated AFTER the index date.
    # In the registry that is not an error: it is a rolling disease register
    # indexed at one fixed date, so 293 patients were diagnosed later and
    # entered afterwards.  They are flagged as incident rather than discarded,
    # because "diagnosed after the index date" is itself information - these
    # are new patients, not patients with a missing duration.
    df["dm_incident_after_index"] = np.where(dur.notna(), (dur < 0).astype(float), np.nan)
    df.loc[df["dm_incident_after_index"] == 1, "dm_duration_y"] = 0.0

    # ---- follow-up length and cost ------------------------------------
    df["d_drugcost"] = df["drugcost_post"] - df["drugcost_pre"]
    df["d_labcost"] = df["labcost_post"] - df["labcost_pre"]
    df["pct_drugcost_change"] = np.where(
        df["drugcost_pre"].notna() & df["drugcost_post"].notna()
        & (df["drugcost_pre"] > 0),
        (df["drugcost_post"] - df["drugcost_pre"]) / df["drugcost_pre"] * 100, np.nan)
    # zero glucose-lowering spend at the last visit - an independent,
    # pharmacy-side check on the medication field
    df["zero_drugcost_last"] = np.where(
        df["drugcost_post_last"].notna(),
        (df["drugcost_post_last"] == 0).astype(float), np.nan)

    # ---- outcomes ----------------------------------------------------
    # 1. Drug cessation (primary).  Denominator: patients on a glucose-
    #    lowering drug at baseline, in a cohort where the follow-up regimen
    #    is genuinely recorded, and with that follow-up value present.
    eligible = (df["on_any_pre"] == 1) & df["on_any_last"].notna() & df["med_outcome_valid"]
    df["drug_stop_eligible"] = eligible
    df["drug_stopped"] = np.where(eligible, (df["on_any_last"] == 0).astype(float), np.nan)

    # Stricter variant, with a different meaning in each cohort because the
    # available corroboration differs:
    #   programme - the end-of-programme medication column only, dropping rows
    #               whose last regimen was carried from the during-programme
    #               column;
    #   registry  - cessation must ALSO show zero glucose-lowering spend at the
    #               last visit, so the medication inference is confirmed by the
    #               pharmacy record rather than resting on a blank cell.
    prog_strict = (eligible & (df["cohort"] != "registry")
                   & (df["med_last_timepoint"] == "end_of_programme"))
    reg_strict = eligible & (df["cohort"] == "registry") & df["zero_drugcost_last"].notna()

    df["drug_stopped_strict"] = np.nan
    df.loc[prog_strict, "drug_stopped_strict"] = (
        df.loc[prog_strict, "on_any_post"] == 0).astype(float)
    df.loc[reg_strict, "drug_stopped_strict"] = (
        (df.loc[reg_strict, "on_any_last"] == 0)
        & (df.loc[reg_strict, "zero_drugcost_last"] == 1)).astype(float)

    # 2. Dose reduction (any fall in daily oral tablets, cessation included)
    df["dose_reduced"] = np.where(
        eligible & df["tabs_pre"].notna() & df["tabs_post"].notna(),
        (df["tabs_post"] < df["tabs_pre"]).astype(float), np.nan)

    # 3. Glycaemic targets
    df["fbs_target_pre"] = np.where(df["fbs_pre"].notna(), (df["fbs_pre"] < 126).astype(float), np.nan)
    df["fbs_target_post"] = np.where(df["fbs_last"].notna(), (df["fbs_last"] < 126).astype(float), np.nan)
    df["a1c_lt7_pre"] = np.where(df["hba1c_pre"].notna(), (df["hba1c_pre"] < 7).astype(float), np.nan)
    df["a1c_lt7_post"] = np.where(df["hba1c_last"].notna(), (df["hba1c_last"] < 7).astype(float), np.nan)
    df["a1c_lt65_post"] = np.where(df["hba1c_last"].notna(), (df["hba1c_last"] < 6.5).astype(float), np.nan)

    # 4. Remission (ADA/EASD 2021 operational proxy): HbA1c < 6.5 % at the
    #    last follow-up while off all glucose-lowering drugs.  The consensus
    #    also requires the HbA1c to be measured at least 3 months after the
    #    drugs stop; these workbooks do not carry the date of the stop, so
    #    that condition cannot be checked and the figure is an upper bound.
    ok = df["hba1c_last"].notna() & df["on_any_last"].notna() & df["med_outcome_valid"]
    df["remission"] = np.where(
        ok, ((df["hba1c_last"] < 6.5) & (df["on_any_last"] == 0)).astype(float), np.nan)

    # ---- time-bound outcomes ------------------------------------------
    # Same definitions as above, but evaluated at the 6-month timepoint
    # instead of at the last recorded value.
    elig_m6 = (df["on_any_pre"] == 1) & df["on_any_m6"].notna() & df["med_outcome_valid"]
    df["drug_stop_m6_eligible"] = elig_m6
    df["drug_stopped_m6"] = np.where(elig_m6, (df["on_any_m6"] == 0).astype(float), np.nan)

    df["a1c_lt7_m6"] = np.where(df["hba1c_m6"].notna(),
                                (df["hba1c_m6"] < 7).astype(float), np.nan)
    df["a1c_lt65_m6"] = np.where(df["hba1c_m6"].notna(),
                                 (df["hba1c_m6"] < 6.5).astype(float), np.nan)
    df["fbs_target_m6"] = np.where(df["fbs_m6"].notna(),
                                   (df["fbs_m6"] < 126).astype(float), np.nan)

    ok_m6 = df["hba1c_m6"].notna() & df["on_any_m6"].notna() & df["med_outcome_valid"]
    df["remission_m6"] = np.where(
        ok_m6, ((df["hba1c_m6"] < 6.5) & (df["on_any_m6"] == 0)).astype(float), np.nan)

    # ---- 3-month outcomes ---------------------------------------------
    # The same definitions at the 3-month anchor.  In practice this is where
    # the 2566 survey lives: it is the only cohort whose medication follow-up
    # is at 3 months, and PCC คลองศาลา is the only programme site with a
    # 3-month medication column.
    elig_m3 = (df["on_any_pre"] == 1) & df["on_any_m3"].notna() & df["med_outcome_valid"]
    df["drug_stop_m3_eligible"] = elig_m3
    df["drug_stopped_m3"] = np.where(elig_m3, (df["on_any_m3"] == 0).astype(float), np.nan)

    df["d_hba1c_m3"] = df["hba1c_m3"] - df["hba1c_pre"]
    df["d_fbs_m3"] = df["fbs_m3"] - df["fbs_pre"]
    df["d_bmi_m3"] = df["bmi_m3"] - df["bmi_pre"]
    df["d_waist_m3"] = df["waist_m3"] - df["waist_pre"]

    df["a1c_lt7_m3"] = np.where(df["hba1c_m3"].notna(),
                                (df["hba1c_m3"] < 7).astype(float), np.nan)
    df["a1c_lt65_m3"] = np.where(df["hba1c_m3"].notna(),
                                 (df["hba1c_m3"] < 6.5).astype(float), np.nan)

    ok_m3 = df["hba1c_m3"].notna() & df["on_any_m3"].notna() & df["med_outcome_valid"]
    df["remission_m3"] = np.where(
        ok_m3, ((df["hba1c_m3"] < 6.5) & (df["on_any_m3"] == 0)).astype(float), np.nan)

    # ---- covariates ---------------------------------------------------
    df["age_group"] = pd.cut(df["age"], [0, 45, 55, 65, 200],
                             labels=["<45", "45-54", "55-64", "65+"], right=False)
    df["bmi_cat"] = pd.cut(df["bmi_pre"], [0, 18.5, 23, 25, 30, 100],
                           labels=["Underweight", "Normal", "Overweight",
                                   "Obese I", "Obese II+"], right=False)
    df["a1c_cat_pre"] = pd.cut(df["hba1c_pre"], [0, 6.5, 7, 8, 9, 100],
                               labels=["<6.5", "6.5-6.9", "7.0-7.9",
                                       "8.0-8.9", ">=9"], right=False)
    df["baseline_monotherapy"] = np.where(
        df["n_class_pre"].notna(), (df["n_class_pre"] <= 1).astype(float), np.nan)
    df["followup_cat"] = pd.cut(df["followup_months"], [0, 12, 24, 36, 1000],
                                labels=["<12 mo", "12-23 mo", "24-35 mo", "36+ mo"],
                                right=False)
    df["dm_duration_cat"] = pd.cut(df["dm_duration_y"], [0, 2, 5, 10, 100],
                                   labels=["<2 y", "2-4 y", "5-9 y", "10+ y"],
                                   right=False)
    return df


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def build_master(raw_dir: str | Path = RAW_DIR, verbose: bool = True):
    """
    Read every workbook, harmonise, de-duplicate and derive.

    Returns ``(master, audit, dropped)`` where ``audit`` has one row per
    source file.
    """
    files = sorted(glob.glob(str(Path(raw_dir) / "*.xls*")))
    frames, audit = [], []
    for f in files:
        kind = classify_file(f)
        try:
            part = LOADERS[kind](f) if kind in LOADERS else _finalise([], "unknown", f)
            err = None
        except Exception as exc:                      # keep going, record why
            part = _finalise([], kind, f)
            err = f"{type(exc).__name__}: {exc}"
        frames.append(part)
        audit.append({
            "file": os.path.basename(f), "loader": kind, "n_rows": len(part),
            "n_sex": part["sex"].notna().sum(),
            "n_hba1c_pre": part["hba1c_pre"].notna().sum(),
            "n_hba1c_post": part["hba1c_last" if "hba1c_last" in part else "hba1c_post"].notna().sum(),
            "n_fbs_pre": part["fbs_pre"].notna().sum(),
            "n_med_pre": part["on_any_pre"].notna().sum(),
            "n_med_post": part["on_any_post"].notna().sum(),
            "error": err,
        })
        if verbose:
            print(f"{os.path.basename(f)[:46]:48s} {kind:11s} n={len(part):5d}"
                  + (f"  !! {err}" if err else ""))

    master = pd.concat(frames, ignore_index=True)
    master["patient_uid"] = (
        master["source_file"].str.slice(0, 18) + "::" +
        master["facility"].fillna("?").astype(str).str.slice(0, 18) + "::" +
        master["local_id"].astype(str) + "::" + master.index.astype(str))

    master, dropped = drop_duplicate_patients(master)
    master = apply_date_corrections(master)
    master = add_derived(master)
    for c in NUMERIC_COLS:
        master[c] = pd.to_numeric(master[c], errors="coerce")
    return master, pd.DataFrame(audit), dropped


def main():
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    master, audit, dropped = build_master()
    master.to_csv(PROC_DIR / "dmr_master.csv", index=False)
    audit.to_csv(PROC_DIR / "dmr_source_audit.csv", index=False)
    dropped.to_csv(PROC_DIR / "dmr_dropped_duplicates.csv", index=False)
    print(f"\nmaster      : {master.shape[0]} patients x {master.shape[1]} cols")
    print(f"duplicates  : {len(dropped)} rows removed")
    print(f"written to  : {PROC_DIR}")


if __name__ == "__main__":
    main()
