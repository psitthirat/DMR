"""Column headers of each source workbook layout (template labels only, never
body rows), grouped into distinct header layouts, with every date-, stop- or
timing-related header flagged.

Run: <DMR>/.venv/bin/python -B -I form_headers.py <DMR root>
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
from src import dmr_etl as E  # noqa: E402
from src.dmr_parse import build_header, clean_text  # noqa: E402

DATEISH = re.compile(r"วันที่|วัน|date|เดือน|\bmo\b|mo\.|หยุด|stop|ตรวจ|ครั้ง|ระยะเวลา|ปี", re.I)


def headers_for(path, kind):
    xl = E.open_workbook(path)
    if kind == "crf":
        raw = xl.parse(xl.sheet_names[0], header=None)
        for i in range(min(5, len(raw))):
            joined = " ".join(clean_text(v) or "" for v in raw.iloc[i])
            if "หน่วยบริการ" in joined and "เพศ" in joined:
                return [clean_text(v) or "" for v in raw.iloc[i]]
        return []
    if kind in ("bangrakam", "pcc"):
        raw = xl.parse(xl.sheet_names[0], header=None)
        return build_header(raw, 1, 2)
    if kind == "rphc":
        for sheet in xl.sheet_names:
            if E._EXCLUDE_SHEET_RE.search(sheet) or not E._DM_SHEET_RE.search(sheet):
                continue
            raw = xl.parse(sheet, header=None)
            return build_header(raw, 1, 2)
        return []
    if kind in ("relational", "survey"):
        out = []
        for sheet in xl.sheet_names:
            raw = xl.parse(sheet, header=None, nrows=1)
            out += [f"[{sheet}] " + (clean_text(v) or "") for v in raw.iloc[0]]
        return out
    return []


groups = defaultdict(list)
for path in sorted((ROOT / "data" / "case_report").glob("*.xls*")):
    kind = E.classify_file(str(path))
    hdr = tuple(h for h in headers_for(path, kind) if h)
    if kind == "rphc":
        # normalise trivial spelling variants so one template counts once
        norm = tuple(re.sub(r"\s+", " ", h.lower()).strip() for h in hdr)
        groups[(kind, norm)].append((path.name, norm))
    else:
        groups[(kind, hdr)].append((path.name, hdr))

for key, members in groups.items():
    kind = key[0]
    hdr = members[0][1]
    print("=" * 100)
    print(f"LAYOUT loader={kind} | files={len(members)} | n_headers={len(hdr)}")
    print("files:", ", ".join(m[0] for m in members))
    if kind in ("relational", "survey"):
        flagged = [h for h in hdr if DATEISH.search(h)]
        print("date/timing-related headers:", flagged)
        print("n headers:", len(hdr))
        continue
    for h in hdr:
        mark = "  <== date/timing" if DATEISH.search(h) else ""
        print(f"  - {h}{mark}")
