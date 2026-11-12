"""Scan analysis code for patient identifiers and raw values.

Reports only file, line number and finding type. Never prints the matched text.
Usage: python -I scan_code.py <DMR root> <checks root> <out json>
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from inventory_data import header_rows, flatten_headers, txt  # noqa: E402

DMR = Path(sys.argv[1])
CHECKS = Path(sys.argv[2])
OUT = Path(sys.argv[3])

TITLE_RE = re.compile(r"^\s*(นาย|นางสาว|นาง|น\.ส\.|นส\.|ด\.ช\.|ด\.ญ\.|เด็กชาย|เด็กหญิง|พระ|ว่าที่\S*)\s*")
COLTYPE = [
    ("national_id", re.compile(r"เลขบัตรปชช|เลขประชาชน|เลขบัตร")),
    ("hn", re.compile(r"^hn$", re.I)),
    ("participant_code", re.compile(r"รหัสประจำตัว")),
    ("name", re.compile(r"ชื่อ-สกุล|^ชื่อ$|^สกุล$")),
    ("phone", re.compile(r"โทร")),
]


def collect_identifiers():
    ids = defaultdict(set)
    sys.path.insert(0, str(DMR))
    from src.dmr_etl import open_workbook
    for p in sorted((DMR / "data" / "case_report").glob("*.xls*")):
        xl = open_workbook(p)
        for s in xl.sheet_names:
            raw = xl.parse(s, header=None)
            rows = header_rows(raw)
            labels = flatten_headers(raw, rows)
            start = (max(rows) + 1) if rows else 0
            body = raw.iloc[start:]
            for j, lab in enumerate(labels):
                last = lab.split("||")[-1].strip()
                for kind, rx in COLTYPE:
                    if rx.search(last):
                        for v in body.iloc[:, j].map(txt):
                            if v:
                                ids[kind].add(v)
                        break
            # national IDs anywhere (unlabelled columns)
            for v in body.map(txt).values.ravel():
                d = re.sub(r"[\s-]", "", v)
                if re.fullmatch(r"\d{13}", d):
                    ids["national_id"].add(d)
    return ids


def build_matchers(ids):
    m = []  # (kind, compiled regex)
    digits = defaultdict(set)
    for v in ids["national_id"]:
        d = re.sub(r"\D", "", v)
        if len(d) == 13:
            digits["national_id"].add(d)
    for v in ids["hn"]:
        d = re.sub(r"\s", "", v)
        if re.fullmatch(r"\d+(\.0)?", d):
            d = d.split(".")[0]
        if len(d) >= 5:
            digits["hn"].add(d)
    for v in ids["participant_code"]:
        d = re.sub(r"\s", "", v).split(".0")[0]
        if len(d) >= 5 or (re.search(r"[A-Za-zก-๙]", d) and len(d) >= 4):
            digits["participant_code"].add(d)
    for v in ids["phone"]:
        d = re.sub(r"\D", "", v)
        if len(d) >= 9:
            digits["phone"].add(d)
    names_full, surnames = set(), set()
    for v in ids["name"]:
        n = TITLE_RE.sub("", v).strip()
        parts = n.split()
        if len(parts) >= 2 and len(parts[0]) >= 2:
            names_full.add((parts[0], parts[-1]))
            if len(parts[-1]) >= 5:
                surnames.add(parts[-1])
        elif len(n) >= 4:
            names_full.add((n, ""))
    return digits, names_full, surnames


def code_units(path):
    """Yield (line_no, text, where) for code; notebooks give source and outputs separately."""
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text(encoding="utf-8"))
        for ci, c in enumerate(nb["cells"]):
            for li, line in enumerate("".join(c.get("source", [])).splitlines(), 1):
                yield f"cell{ci}:{li}", line, "source"
            for o in c.get("outputs", []) or []:
                blobs = []
                if "text" in o:
                    blobs.append("".join(o["text"]))
                for k, v in (o.get("data") or {}).items():
                    if k.startswith("text/"):
                        blobs.append("".join(v) if isinstance(v, list) else str(v))
                for b in blobs:
                    for li, line in enumerate(b.splitlines(), 1):
                        yield f"cell{ci}:out{li}", line, "output"
    else:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            yield str(i), line, "source"


PATTERNS = [
    ("13digit_number", re.compile(r"(?<!\d)\d{13}(?!\d)")),
    ("thai_title_name", re.compile(r"(?:นาย|นางสาว|นาง|น\.ส\.|ด\.ช\.|ด\.ญ\.)\s*[ก-๙]{2,}\s+[ก-๙]{2,}")),
    ("sheet_row_reference", re.compile(r"(?:\brow\s*\d{1,4}\b|แถว(?:ที่)?\s*\d{1,4})", re.I)),
    ("date_literal", re.compile(r"\b\d{1,2}/\d{1,2}/(?:25|20|19)?\d{2}\b|\b(?:19|20|25)\d{2}-\d{2}-\d{2}\b")),
]


def scan(files, digits, names_full, surnames):
    res = []
    for f in files:
        hits = defaultdict(list)
        for ln, line, where in code_units(f):
            dl = re.sub(r"[\s-]", "", line)
            tag = "" if where == "source" else "[output] "
            for kind, vals in digits.items():
                for d in re.findall(r"\d{5,}|[A-Za-z]*\d{3,}[A-Za-z0-9]*", dl):
                    if d in vals:
                        hits[f"{tag}ID:{kind}"].append(ln)
            for first, last in names_full:
                if first in line and (not last or last in line):
                    hits[f"{tag}ID:name"].append(ln)
            for s in surnames:
                if s in line:
                    hits[f"{tag}possible_surname"].append(ln)
            if where == "source":
                for kind, rx in PATTERNS:
                    if rx.search(line):
                        hits[kind].append(ln)
            else:
                if PATTERNS[0][1].search(line):
                    hits["[output] 13digit_number"].append(ln)
                if PATTERNS[1][1].search(line):
                    hits["[output] thai_title_name"].append(ln)
        res.append({"file": str(f), "findings": {k: sorted(set(v), key=str) for k, v in hits.items()}})
    return res


if __name__ == "__main__":
    ids = collect_identifiers()
    digits, names_full, surnames = build_matchers(ids)
    files = sorted(DMR.glob("src/*.py")) + sorted(DMR.glob("notebooks/*.ipynb")) + \
        sorted(DMR.glob("tools/*.py")) + sorted(DMR.glob("docs/*.js")) + \
        [DMR / "docs" / "index.html", DMR / "docs" / "data" / "evidence.json",
         DMR / "README.md", DMR / "ANALYSIS.md"]
    for sub in ["2026-11-08 open questions/scripts", "2026-11-11 rerun/scripts",
                "2026-11-11 thawung g3 by cessation/scripts"]:
        files += sorted((CHECKS / sub).glob("*.py")) + sorted((CHECKS / sub).glob("*.sh"))
    out = {"identifier_counts": {k: len(v) for k, v in digits.items()} | {"name_pairs": len(names_full), "surnames>=5": len(surnames)},
           "results": scan(files, digits, names_full, surnames)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["identifier_counts"], ensure_ascii=False))
    for r in out["results"]:
        f = r["file"].replace(str(DMR) + "/", "DMR/").replace(str(CHECKS) + "/", "_DMR_checks/")
        summ = {k: (len(v), v[:12]) for k, v in r["findings"].items()}
        print(f, "->", summ if summ else "clean")
