"""Counts for template columns the loaders do not read: the "การปรับยา" block in
the รพ.สต.หนองโน workbook, and the stop-date / test-date fields in the 2566
survey form. Aggregates only; facility cells under 5 shown as "<5".

Run: <DMR>/.venv/bin/python -B -I unread_columns.py <DMR root>
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
from src import dmr_etl as E  # noqa: E402
from src.dmr_parse import build_header, clean_text, looks_like_header  # noqa: E402

RAW = ROOT / "data" / "case_report"


def filled(v):
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    return str(v).strip() != ""


def sup(k):
    k = int(k)
    return "<5" if 0 < k < 5 else str(k)


# --- รพ.สต.หนองโน: การปรับยา block, aligned with the loader's own rows -------
path = RAW / "รพ.สต.หนองโน.xlsx"
xl = E.open_workbook(path)
sheet = next(s for s in xl.sheet_names
             if not E._EXCLUDE_SHEET_RE.search(s) and E._DM_SHEET_RE.search(s))
raw = xl.parse(sheet, header=None)
cols = [c.lower() for c in build_header(raw, 1, 2)]
body = raw.iloc[3:].reset_index(drop=True)
name_j = next(j for j, c in enumerate(cols) if not c.partition("||")[2].strip() and re.search(r"ชื่อ", c))
adj = {c.partition("||")[2].strip(): j for j, c in enumerate(cols) if c.startswith("การปรับยา")}
print("Nong No adjustment columns:", list(adj))
flags = []
for _, r in body.iterrows():
    if looks_like_header(r) or clean_text(r.iloc[name_j]) is None:
        continue
    flags.append({k: filled(r.iloc[j]) for k, j in adj.items()})
flags = pd.DataFrame(flags)
loaded = E.load_rphc(str(path)).reset_index(drop=True)
assert len(flags) == len(loaded), (len(flags), len(loaded))
both = pd.concat([flags, loaded[["on_any_pre", "on_any_post"]]], axis=1)
print("rows", len(both))
for k in ("หยุด", "ลดยา"):
    print(f"  marked '{k}':", sup(both[k].sum()))
other = [k for k in adj if k not in ("หยุด", "ลดยา")]
print("  marked another option (combined):", sup(both[other].any(axis=1).sum()))
print("rows marked 'หยุด' by derived status: on_any_pre / on_any_post (NaN = not recorded)")
s = both[both.get("หยุด", pd.Series(False, index=both.index))]
print("  on_any_pre:", {str(k): sup(v) for k, v in s["on_any_pre"].value_counts(dropna=False).items()})
print("  on_any_post:", {str(k): sup(v) for k, v in s["on_any_post"].value_counts(dropna=False).items()})
base_on = both["on_any_pre"].eq(1)
print("on drug at baseline:", sup(base_on.sum()),
      "| of these, 'หลัง' dose block not recorded:", sup((base_on & both.on_any_post.isna()).sum()),
      "| of those unrecorded, marked 'หยุด':", sup((base_on & both.on_any_post.isna() & both.get("หยุด", False)).sum()),
      "| marked any adjustment:", sup((base_on & both.on_any_post.isna() & flags.any(axis=1)).sum()))

# --- 2566 survey form: stop-date and blood-test-date fields --------------------
path = RAW / "แบบสำรวจ 2566 เครือข่ายกระนวน.xlsx"
xl = E.open_workbook(path)
for sheet in xl.sheet_names:
    raw = xl.parse(sheet, header=None)
    hdr = [clean_text(v) or "" for v in raw.iloc[0]]
    body = raw.iloc[1:]
    for j, h in enumerate(hdr):
        if re.search(r"วันที่ off|ผลเลือดวันที่", h):
            print(f"survey [{sheet}] '{h}': filled {int(body.iloc[:, j].map(filled).sum())} of {len(body)} rows")
