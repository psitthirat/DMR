"""
Low-level parsing helpers for the DM Remission case-report files.

Everything here is pure / side-effect free so it can be unit-checked from the
notebook.  Three families of messiness are handled:

1. Dates   - mixed Buddhist Era (2568) and Gregorian (2025) years, Thai
             day/month/year strings, and Excel two-digit-year mis-reads
             (a cell typed "9/10/68" meaning BE 2568 comes back as 1968).
2. Numbers - lab values entered with trailing comments, e.g. "118  (2/8/67)",
             "ไม่ได้มาเจาะ", "6.5%", ">200".
3. Drugs   - two very different encodings:
             (a) one column per drug holding a dose string ("1x2", "2-0-1",
                 "off", "-", "1/2x1hs")   -> รพ.สต. summary workbooks
             (b) one free-text column holding the whole regimen
                 ("Metformin (500) 2*2 po pc, Glipizide (5) 1x1")  -> CRF
"""

from __future__ import annotations

import datetime as _dt
import math
import re
import unicodedata

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------

def clean_text(x) -> str | None:
    """Normalise a cell to a stripped string, or None if it is effectively blank."""
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    s = unicodedata.normalize("NFC", str(x))
    s = s.replace(" ", " ").replace("​", "")
    s = re.sub(r"\s+", " ", s).strip()
    if s == "" or s.lower() in {"nan", "nat", "none", "null"}:
        return None
    return s


# Tokens that mean "nothing recorded here" as opposed to "recorded as absent".
_MISSING_TOKENS = {
    "-", "--", "?", "ไม่ทราบ", "ไม่ได้มาเจาะ", "ไม่มาเจาะ", "ไม่ได้ตรวจ",
    "ไม่มาตามนัด", "รอผล", "n/a", "na", "ยังไม่จบโครงการ", "ยังไม่จบ",
    "ยังไม่ปรับยา", "ยังไม่ได้ปรับยา",
}

# Tokens that positively mean "no glucose-lowering drug".
_NO_DRUG_TOKENS = {
    "0", "off", "off ยา", "offยา", "ไม่มี", "ไม่มียา", "ปฏิเสธ", "diet",
    "diet control", "ไม่ได้ใช้ยา", "หยุดยา", "stop", "none", "no",
}


def is_missing_token(s) -> bool:
    s = clean_text(s)
    return s is None or s.lower() in _MISSING_TOKENS


# --------------------------------------------------------------------------
# numbers
# --------------------------------------------------------------------------

_NUM_RE = re.compile(r"[-+]?\d{1,6}(?:[.,]\d+)?")


def to_num(x, lo: float | None = None, hi: float | None = None):
    """
    Pull the first plausible number out of a cell.

    "118  (2/8/67)" -> 118.0      (the parenthesised part is a sample date)
    "6.5 %"          -> 6.5
    ">200"           -> 200.0
    "ไม่ได้มาเจาะ"    -> nan

    ``lo``/``hi`` apply a physiological plausibility window; values outside it
    become nan so a typo like FBS = 105115 does not poison a mean.
    """
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        if isinstance(x, float) and math.isnan(x):
            return np.nan
        v = float(x)
    else:
        s = clean_text(x)
        if s is None or is_missing_token(s):
            return np.nan
        # drop anything in brackets first: it is nearly always a sample date
        s = re.sub(r"\([^)]*\)", " ", s)
        m = _NUM_RE.search(s.replace(",", "."))
        if not m:
            return np.nan
        try:
            v = float(m.group(0))
        except ValueError:
            return np.nan
    if lo is not None and v < lo:
        return np.nan
    if hi is not None and v > hi:
        return np.nan
    return v


# Physiological windows used throughout the pipeline.
RANGES = {
    "age": (15, 110),
    "height_cm": (100, 210),
    "weight_kg": (25, 220),
    "bmi": (12, 70),
    "waist_cm": (40, 200),
    "fbs": (30, 600),
    "hba1c": (3.5, 20),
    "creatinine": (0.2, 15),
    "egfr": (1, 200),
    "chol": (50, 500),
    "hdl": (10, 150),
    "ldl": (10, 400),
    "tg": (20, 1500),
}


def to_num_r(x, kind: str):
    """``to_num`` with the plausibility window for a named measurement."""
    lo, hi = RANGES[kind]
    return to_num(x, lo, hi)


# --------------------------------------------------------------------------
# dates
# --------------------------------------------------------------------------

_THAI_MONTHS = {
    "ม.ค": 1, "มค": 1, "มกราคม": 1,
    "ก.พ": 2, "กพ": 2, "กุมภาพันธ์": 2,
    "มี.ค": 3, "มีค": 3, "มีนาคม": 3,
    "เม.ย": 4, "เมย": 4, "เมษายน": 4,
    "พ.ค": 5, "พค": 5, "พฤษภาคม": 5,
    "มิ.ย": 6, "มิย": 6, "มิถุนายน": 6,
    "ก.ค": 7, "กค": 7, "กรกฎาคม": 7,
    "ส.ค": 8, "สค": 8, "สิงหาคม": 8,
    "ก.ย": 9, "กย": 9, "กันยายน": 9,
    "ต.ค": 10, "ตค": 10, "ตุลาคม": 10,
    "พ.ย": 11, "พย": 11, "พฤศจิกายน": 11,
    "ธ.ค": 12, "ธค": 12, "ธันวาคม": 12,
}


def _fix_year(y: int) -> int:
    """
    Map a raw year field onto a Gregorian year.

    2400+ .......... Buddhist Era, subtract 543           (2568 -> 2025)
    1940-1999 ...... Excel read a two-digit BE year as 19xx.  A cell typed
                     "68" meant BE 2568; Excel stored 1968.  Add 57.
                     (1968 -> 2025, 1957 -> 2014)
    otherwise ...... already Gregorian
    """
    if y >= 2400:
        return y - 543
    if 1940 <= y <= 1999:
        return y + 57
    return y


def parse_date(x, lo_year: int = 1960, hi_year: int = 2035):
    """
    Parse a date cell into a Gregorian ``pd.Timestamp`` (NaT if unusable).

    Accepts real datetimes, "2568-01-15", "03/02/2558", "12-05-2566",
    "Dx.HT 20/03/2564", "1 ส.ค. 67", and bare years such as "2567".
    """
    if isinstance(x, (_dt.datetime, _dt.date)) and not isinstance(x, bool):
        y = _fix_year(x.year)
        try:
            out = pd.Timestamp(year=y, month=x.month, day=x.day)
        except ValueError:
            return pd.NaT
        return out if lo_year <= out.year <= hi_year else pd.NaT

    s = clean_text(x)
    if s is None or is_missing_token(s):
        return pd.NaT

    # Thai month names ------------------------------------------------------
    for name, mm in _THAI_MONTHS.items():
        if name in s:
            nums = re.findall(r"\d+", s)
            if len(nums) >= 2:
                d, y = int(nums[0]), int(nums[-1])
                y = _fix_year(y + 2500 if y < 100 else y)
                try:
                    out = pd.Timestamp(year=y, month=mm, day=min(d, 28))
                except ValueError:
                    return pd.NaT
                return out if lo_year <= out.year <= hi_year else pd.NaT

    # numeric patterns ------------------------------------------------------
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)          # y-m-d
    if m:
        y, mo, d = (int(g) for g in m.groups())
    else:
        m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", s)     # d-m-y
        if m:
            d, mo, y = (int(g) for g in m.groups())
            if y < 100:
                y += 2500            # two-digit Thai year, e.g. 67 -> 2567 BE
        else:
            m = re.fullmatch(r"\D*(\d{4})\D*", s)                      # bare year
            if not m:
                return pd.NaT
            y, mo, d = int(m.group(1)), 1, 1

    y = _fix_year(y)
    if mo > 12 and d <= 12:          # day/month written the other way round
        mo, d = d, mo
    try:
        out = pd.Timestamp(year=y, month=mo, day=min(d, 28) if d > 28 else d)
    except ValueError:
        return pd.NaT
    return out if lo_year <= out.year <= hi_year else pd.NaT


# --------------------------------------------------------------------------
# categoricals
# --------------------------------------------------------------------------

def norm_sex(x):
    s = clean_text(x)
    if s is None:
        return None
    s = s.lower().rstrip(".")
    if s.startswith(("ญ", "หญิง", "f", "female")):
        return "Female"
    if s.startswith(("ช", "ชาย", "m", "male")):
        return "Male"
    return None


_SCHEME_RULES = [
    ("UCS",  ["บัตรทอง", "หลักประกัน", "uc", "ucs", "30 บาท", "ผู้สูงอายุ",
              "ผู้พิการ", "อสม", "ท.", "บัตรผู้มีอายุ", "สิทธิว่าง"]),
    ("CSMBS", ["ข้าราชการ", "กรมบัญชีกลาง", "เบิกได้", "csmbs", "อปท",
               "องค์การบริหาร", "รัฐวิสาหกิจ"]),
    ("SSS",  ["ประกันสังคม", "sss", "ปกส"]),
    ("Self-pay/Other", ["ชำระเงิน", "จ่ายเอง", "ต่างด้าว", "ต่างชาติ",
                        "ไม่มีสิทธิ", "บุคคลที่มีปัญหาสถานะ"]),
]


def norm_scheme(x):
    """Collapse the free-text benefit-scheme field onto the four Thai schemes."""
    s = clean_text(x)
    if s is None:
        return None
    low = s.lower()
    for label, keys in _SCHEME_RULES:
        if any(k in low for k in keys):
            return label
    return "Other"


_EDU_RULES = [
    ("None/Primary", ["ป.1", "ป.4", "ป.6", "ป4", "ป6", "ประถม", "ป ", "ไม่ได้เรียน",
                      "ไม่เกินชั้นประถม", "อ่านไม่ออก"]),
    ("Secondary",    ["ม.3", "ม.6", "ม3", "ม6", "มัธยม", "ปวช", "ปวส", "อนุปริญญา",
                      "ไม่เกินชั้นมัธยม"]),
    ("Tertiary",     ["ป.ตรี", "ปริญญา", "ป.โท", "ป ตรี", "ปตรี"]),
]


def norm_education(x):
    s = clean_text(x)
    if s is None or s in {"ไม่ทราบ"}:
        return None
    low = s.lower()
    for label, keys in _EDU_RULES:
        if any(k in low for k in keys):
            return label
    return None


# --------------------------------------------------------------------------
# comorbidity
# --------------------------------------------------------------------------

COMORBID_PATTERNS = {
    "hypertension": r"\bht\b|ความดัน|hypertension|smart ht",
    "dyslipidaemia": r"\bdlp\b|\bdlipid|ไขมัน|dyslipid|hyperlip",
    "ckd":           r"\bckd\b|ไตเรื้อรัง|ไตวาย|\bckd st|renal",
    "cvd":           r"\bihd\b|\bcad\b|\bmi\b|หัวใจ|\bcva\b|stroke|อัมพ",
    "gout":          r"\bgout\b|เก๊าท์",
    "copd_asthma":   r"\bcopd\b|asthma|ถุงลม|หอบ",
}


def parse_comorbidities(x) -> dict:
    """Flag the comorbidities named in a free-text field.

    Returns a dict of 0/1 flags plus ``n_comorbid``.  When the field is blank
    the flags are ``nan`` (unknown), not 0, so the notebook can distinguish
    "not recorded" from "recorded as absent".
    """
    s = clean_text(x)
    out = {k: np.nan for k in COMORBID_PATTERNS}
    out["n_comorbid"] = np.nan
    if s is None:
        return out
    low = s.lower()
    if low in {"ปฏิเสธ", "ไม่มี", "none", "no", "-"}:
        for k in COMORBID_PATTERNS:
            out[k] = 0
        out["n_comorbid"] = 0
        return out
    total = 0
    for k, pat in COMORBID_PATTERNS.items():
        hit = int(bool(re.search(pat, low)))
        out[k] = hit
        total += hit
    out["n_comorbid"] = total
    return out


# --------------------------------------------------------------------------
# drug dose strings  (รพ.สต. one-column-per-drug layout)
# --------------------------------------------------------------------------

_FRACTION_WORDS = {"1/2": 0.5, "½": 0.5, "1/4": 0.25, "3/4": 0.75, "1/3": 1 / 3}


def _amount(tok: str) -> float | None:
    """Turn '1', '1/2', '1 1/2', '0.5', '2.5' into a number of tablets."""
    tok = tok.strip()
    if not tok:
        return None
    m = re.fullmatch(r"(\d+)\s+(\d/\d)", tok)          # "1 1/2"
    if m:
        return float(m.group(1)) + _FRACTION_WORDS.get(m.group(2), 0.0)
    if tok in _FRACTION_WORDS:
        return _FRACTION_WORDS[tok]
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", tok)         # "1/2"
    if m and float(m.group(2)) != 0:
        return float(m.group(1)) / float(m.group(2))
    try:
        return float(tok)
    except ValueError:
        return None


def parse_dose(x):
    """
    Convert a dose cell into **tablets (or units) per day**.

    "1x1"        -> 1.0        "1*2"     -> 2.0        "2-0-1"  -> 3.0
    "1/2x1"      -> 0.5        "1 1/2x1"   -> 1.5      "2x2"    -> 4.0
    "off" / "0" / "-" / "ไม่มี"  -> 0.0
    blank / "ไม่ทราบ"            -> nan

    Returns ``nan`` when the cell is blank or explicitly unknown, so that
    "not recorded" never masquerades as "not taking the drug".
    """
    s = clean_text(x)
    if s is None:
        return np.nan
    low = s.lower().replace(" ", "")
    if low in {t.replace(" ", "") for t in _NO_DRUG_TOKENS}:
        return 0.0
    if low.startswith("off") or low.startswith("หยุด"):
        return 0.0
    if clean_text(s).lower() in _MISSING_TOKENS:
        return np.nan
    if is_missing_token(s):
        return np.nan

    body = s.lower()
    # strip administration route / timing suffixes
    body = re.sub(r"\b(po|pc|ac|hs|od|bid|tid|sc|unit[s]?|u|tab[s]?|เม็ด|"
                  r"ก่อนอาหาร|หลังอาหาร|เช้า|เย็น|ก่อนนอน)\b", " ", body)
    body = re.sub(r"(hs|sc)$", " ", body)
    body = body.replace("×", "x").replace("＊", "*")

    # "2-0-1"  /  "18-0-12"  -> morning-noon-evening schedule, sum the parts
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*",
                     body)
    if m:
        return sum(float(g) for g in m.groups())

    # "1x2" / "1*2" / "1 1/2 x 1"  -> amount x frequency
    m = re.search(r"([\d\s/½.]+?)\s*[x*]\s*([\d.]+)", body)
    if m:
        amt, freq = _amount(m.group(1)), _amount(m.group(2))
        if amt is not None and freq is not None:
            return amt * freq
    # bare "1x" / "1xhs" -> once daily
    m = re.search(r"([\d\s/½.]+?)\s*[x*]\s*$", body)
    if m:
        amt = _amount(m.group(1))
        if amt is not None:
            return amt

    # a bare number: the รพ.สต. sheets use it for tablets/day
    m = re.fullmatch(r"\s*([\d\s/½.]+)\s*", body)
    if m:
        amt = _amount(m.group(1))
        if amt is not None:
            return amt

    # something was written, and it is not a "no drug" token -> on the drug,
    # dose not parseable.  Report 1 tablet/day so the on/off flag stays right.
    return 1.0


# --------------------------------------------------------------------------
# free-text regimens  (CRF layout)
# --------------------------------------------------------------------------

# Longest / most specific aliases first so "metformin" is not eaten by "m".
#
# The trailing single-letter alternatives (\bm\s*\d+[x*]\d) exist for รพ.อุ้มผาง,
# which writes its regimens as "M 2*2  P1*1  G 2*2" - one initial followed
# immediately by a dose.  The dose is part of the pattern on purpose: a bare
# letter would match far too much, whereas "letter + dose" does not fire on
# "Metformin", "Mixtard", "eGFR 75" or "GPZ 2x1" (checked against all of them).
DRUG_PATTERNS = [
    # NB: \b fails where a token is glued to Thai letters or digits
    # ("ลดยาMFM(500)", "MFM500"), because Thai letters are word characters.
    # (?<![a-z]) / (?![a-z]) is a latin-letter boundary, which allows both.
    # Brand names and one misspelling added 2026-11-11 after an audit of every
    # regimen string: "glucophage" (metformin), "glyxambi" (empagliflozin +
    # linagliptin, so it counts in both classes) and "glpizide".
    ("metformin",     r"metformin|metfor|glucophage|(?<![a-z])mfm(?![a-z])|(?<![a-z])met(?![a-z])"
                      r"|เมทฟอร์มิน|(?<![a-z])mf(?![a-z])"
                      r"|(?<![a-z])m\s*\d+(?:\s*[x*/]\s*\d)"),
    ("glipizide",     r"glipi\s*-?\s*zide|glipizide|glpizide|(?<![a-z])gpz(?![a-z])"
                      r"|(?<![a-z])gp(?![a-z])\s*\d"
                      r"|(?<![a-z])g\s*\d+(?:\s*[x*/]\s*\d)"),
    ("glibenclamide", r"gliben|glyburide"),
    ("gliclazide",    r"gliclazide|diamicron"),
    ("glimepiride",   r"glimepiride|amaryl"),
    ("pioglitazone",  r"pioglitazone|(?<![a-z])pio(?![a-z])|actos"
                      r"|(?<![a-z])p\s*\d+(?:\s*[x*/]\s*\d)"),
    ("sglt2",         r"empagliflozin|jardiance|dapagliflozin|forxiga|canagliflozin|glyxambi"),
    ("dpp4",          r"linagliptin|sitagliptin|vildagliptin|galvus|januvia|trajenta|glyxambi"),
    ("glp1",          r"liraglutide|dulaglutide|semaglutide|victoza|trulicity|ozempic"),
    ("acarbose",      r"acarbose|glucobay"),
    ("insulin",       r"insulin|mixtard|\bnph\b|\bri\b|lantus|levemir|novomix|"
                      r"humulin|actrapid|อินซูลิน|ยาฉีด"),
]

INSULIN_CLASSES = {"insulin"}
ORAL_CLASSES = {c for c, _ in DRUG_PATTERNS} - INSULIN_CLASSES

# Segment-level markers that a drug was stopped, e.g. "OFF Glipizide(5)2X2".
# No trailing \b: sites write "OFFMFM(850)" with no space.  "ลด"/"ลดยา"
# (dose reduced) is deliberately NOT here - that patient is still on the drug.
_OFF_RE = re.compile(r"\boff|หยุด|\bd/?c\b|discontinu", re.I)

# A dose such as "1x2", "2*2" or "1 1/2 x 1": evidence the drug is being taken.
_DOSE_RE = re.compile(r"\d\s*[x*]\s*\d")

# Words that may sit beside "off" without naming a drug ("off ยา dm", "off all").
_NOT_A_DRUG_WORDS = {"off", "all", "diet", "control", "conttrol", "drug", "drugs",
                     "med", "meds", "dm", "case", "remission"}


def _segment_drugs(seg: str) -> tuple[set[str], bool]:
    """
    Drug classes a patient is ON in one regimen segment, and whether the
    segment named any glucose-lowering drug at all.

    A segment with no OFF marker: every drug named is on.  With an OFF marker
    the drug(s) written after it are stopped, but a drug written before it
    with its own dose stays on: "MFM 850 mg 1x2 off pio" is metformin
    continued and pioglitazone stopped.  Until 2026-11-11 the whole segment was
    dropped, which counted such a patient as off every drug.
    """
    hits = {cls for cls, pat in DRUG_PATTERNS if re.search(pat, seg)}
    if not hits:
        return set(), False
    m = _OFF_RE.search(seg)
    if not m:
        return hits, True
    before = seg[:m.start()]
    if not _DOSE_RE.search(before):
        return set(), True
    return {cls for cls, pat in DRUG_PATTERNS if re.search(pat, before)}, True


def _names_other_drug(low: str) -> bool:
    """True when an OFF note names something that is not a glucose-lowering
    drug, e.g. "off hctz" (a diuretic).  Such a note says nothing about the
    diabetes regimen, so it must not be read as a recorded cessation."""
    for w in re.findall(r"[a-z]{3,}", low):
        w = re.sub(r"^off", "", w)        # "offmfm" is metformin, glued to off
        if not w or w in _NOT_A_DRUG_WORDS:
            continue
        if any(re.search(p, w) for _, p in DRUG_PATTERNS):
            continue
        return True
    return False


def parse_regimen(x) -> dict:
    """
    Read a free-text glucose-lowering regimen.

    Returns
    -------
    dict with
        ``classes``      set of drug classes the patient is *on*
        ``n_classes``    number of distinct glucose-lowering classes
        ``on_any``       1 / 0 / nan  - on any glucose-lowering drug
        ``on_insulin``   1 / 0 / nan
        ``n_oral``       number of distinct oral classes
        ``status``       'no_drug' | 'on_drug' | 'unknown' | 'no_change'
        ``raw``          the cleaned original text

    Segment-level OFF is respected: "MFM 500 1x2 / OFF Glipizide" counts
    metformin only.  A whole-string OFF with no drug named ("OFF ยา") counts
    as no drug.
    """
    s = clean_text(x)
    blank = {"classes": set(), "n_classes": np.nan, "on_any": np.nan,
             "on_insulin": np.nan, "n_oral": np.nan, "status": "unknown",
             "raw": s}
    if s is None:
        return blank

    low = s.lower()

    # explicit "nothing" -------------------------------------------------
    stripped = low.replace(" ", "")
    if (stripped in {t.replace(" ", "") for t in _NO_DRUG_TOKENS}
            or re.fullmatch(r"(off\s*ยา|ไม่มียา\s*dm.*|ไม่มียา.*|off)", low)
            or ("ไม่มียา" in low and not any(re.search(p, low) for _, p in DRUG_PATTERNS))
            or ("diet" in low and not any(re.search(p, low) for _, p in DRUG_PATTERNS))):
        return {"classes": set(), "n_classes": 0, "on_any": 0, "on_insulin": 0,
                "n_oral": 0, "status": "no_drug", "raw": s}

    # "no change yet" - the caller carries the previous value forward -----
    if re.search(r"ยังไม่(ได้)?ปรับ|ไม่ปรับ|ยังไม่จบ|เท่าเดิม", low):
        out = dict(blank)
        out["status"] = "no_change"
        return out

    if is_missing_token(s):
        return blank

    # split into segments so a per-drug OFF can be honoured ---------------
    segments = re.split(r"[,/;+]|\band\b", low)
    on: set[str] = set()
    seen_any_drug = False
    for seg in segments:
        seg_on, named = _segment_drugs(seg)
        seen_any_drug |= named
        on.update(seg_on)

    if not seen_any_drug:
        # "off 01/10/68", "off 15/01/69" - a stop with its date and no drug
        # named.  That is a recorded cessation, not an unreadable cell.
        # "off hctz" names a non-diabetes drug instead, so it stays unknown.
        if _OFF_RE.search(low) and not _names_other_drug(low):
            return {"classes": set(), "n_classes": 0, "on_any": 0, "on_insulin": 0,
                    "n_oral": 0, "status": "no_drug", "raw": s}
        # text present but no recognisable drug (e.g. a free comment)
        return blank

    n_oral = len(on & ORAL_CLASSES)
    return {
        "classes": on,
        "n_classes": len(on),
        "on_any": int(len(on) > 0),
        "on_insulin": int(bool(on & INSULIN_CLASSES)),
        "n_oral": n_oral,
        "status": "on_drug" if on else "no_drug",
        "raw": s,
    }


# --------------------------------------------------------------------------
# small utilities used by the loaders
# --------------------------------------------------------------------------

def looks_like_header(row_values) -> bool:
    """True when a body row is actually a repeated header block."""
    joined = " ".join(clean_text(v) or "" for v in row_values).lower()
    markers = ["ชื่อ-สกุล", "ลำดับ", "ส่วนสูง", "hba1c", "ยา gpz", "ยา mfm",
               "ก่อนเข้าร่วม", "หลังเข้าร่วม", "รอบเอว"]
    return sum(m in joined for m in markers) >= 3


def build_header(df: pd.DataFrame, r_group: int, r_sub: int) -> list[str]:
    """
    Flatten a two-row Excel header into ``"group||sub"`` labels.

    The group row uses merged cells, so it is forward-filled; the sub row is
    taken as-is.  Labels are lower-cased and stripped for matching.
    """
    g = df.iloc[r_group].map(clean_text).ffill()
    s = df.iloc[r_sub].map(clean_text)
    out = []
    for gi, si in zip(g, s):
        gi = (gi or "").strip()
        si = (si or "").strip()
        out.append(f"{gi}||{si}")
    return out
