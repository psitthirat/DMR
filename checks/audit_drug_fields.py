"""Audit how every template's drug fields are read (task 6 and the หนองโน fix).

Prints, without names, HNs or IDs:
  1. รพ.สต.: per file, the sub-headers of the ก่อน / หลัง blocks the loader does
     NOT map, and the distinct values in the "ยาอื่น" columns with counts.
  2. CRF-family free text (pre / mid / post), and the registry dispensing list:
     tokens with no recognised drug, and segments where an OFF marker sits in
     the same segment as a second, different drug (the switcher pattern).
  3. PCC คลองศาลา: the drug columns present.

Run: <DMR>/.venv/bin/python -B -I audit_drug_fields.py <DMR root>
"""
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
from src import dmr_etl as E  # noqa: E402
from src.dmr_parse import (DRUG_PATTERNS, _OFF_RE, build_header, clean_text,  # noqa: E402
                           looks_like_header, parse_regimen)

RAW = ROOT / "data" / "case_report"
files = sorted(RAW.glob("*.xls*"))
kind = {f: E.classify_file(str(f)) for f in files}

print("=" * 70, "\n1. รพ.สต. drug sub-headers and 'ยาอื่น' contents\n")
other_vals = Counter()
for f in files:
    if kind[f] != "rphc":
        continue
    xl = E.open_workbook(f)
    for sheet in xl.sheet_names:
        if E._EXCLUDE_SHEET_RE.search(sheet) or not E._DM_SHEET_RE.search(sheet):
            continue
        raw = xl.parse(sheet, header=None)
        cols = [c.lower() for c in build_header(raw, 1, 2)]
        body = raw.iloc[3:].reset_index(drop=True)
        unmapped, other_j, groups = [], [], set()
        for j, c in enumerate(cols):
            g, _, s = c.partition("||")
            g, s = g.strip(), s.strip()
            if not s:
                continue
            period = "pre" if "ก่อน" in g else "post" if "หลัง" in g else None
            if period is None:
                groups.add(g)
                continue
            key = s.rstrip()
            mapped = key in E._RPHC_DRUGS or any(key.startswith(l) for l in E._RPHC_LABS)
            if not mapped:
                unmapped.append(f"{period}:{key}")
            if "อื่น" in key:
                other_j.append(j)
        print(f"{f.name}: unmapped {unmapped}" + (f" | non-period groups {sorted(groups)}" if groups else ""))
        for _, r in body.iterrows():
            if looks_like_header(r):
                continue
            for j in other_j:
                v = clean_text(r.iloc[j])
                if v:
                    other_vals[v.lower()] += 1

print("\n'ยาอื่น' distinct values (all รพ.สต. files):")
dm_hits = []
for v, n in other_vals.most_common():
    hit = [c for c, p in DRUG_PATTERNS if re.search(p, v)]
    print(f"  {n:3d}  {v}" + (f"   <-- glucose-lowering pattern: {hit}" if hit else ""))
    if hit:
        dm_hits.append(v)
print("values matching a glucose-lowering pattern:", len(dm_hits))

print("\n" + "=" * 70, "\n2. free-text regimens (CRF, บางระกำ, registry)\n")
parts = []
for f in files:
    if kind[f] in {"crf", "bangrakam", "relational"}:
        parts.append(E.LOADERS[kind[f]](str(f)))
df = pd.concat(parts, ignore_index=True)
for fam, sub in df.groupby("source_family"):
    for col in ("med_pre_raw", "med_mid_raw", "med_post_raw"):
        vals = sub[col].dropna().astype(str)
        unrec, switch = Counter(), Counter()
        for v in vals:
            low = v.lower()
            segs = re.split(r"[,/;+]|\band\b", low)
            for seg in segs:
                hits = [c for c, p in DRUG_PATTERNS if re.search(p, seg)]
                if _OFF_RE.search(seg) and len(set(hits)) >= 2:
                    switch[seg.strip()] += 1
            pr = parse_regimen(v)
            if pr["status"] == "unknown" and re.search(r"[a-z]{3,}", low):
                unrec[low] += 1
        print(f"[{fam}] {col}: {len(vals)} filled")
        if switch:
            print("   OFF + another drug in one segment:")
            for s, n in switch.most_common():
                print(f"     {n:3d}  {s}")
        if unrec:
            print("   text present, no drug recognised (status unknown):")
            for s, n in unrec.most_common(40):
                print(f"     {n:3d}  {s}")

# words that look like drug names but match no pattern
print("\nlatin words in regimen text that match no drug pattern (top 80):")
words = Counter()
for col in ("med_pre_raw", "med_mid_raw", "med_post_raw"):
    for v in df[col].dropna().astype(str):
        for w in re.findall(r"[a-z][a-z\-]{3,}", v.lower()):
            if not any(re.search(p, w) for _, p in DRUG_PATTERNS):
                words[w] += 1
for w, n in words.most_common(80):
    print(f"  {n:4d}  {w}")

print("\n" + "=" * 70, "\n3. PCC คลองศาลา drug columns\n")
for f in files:
    if kind[f] == "pcc":
        xl = E.open_workbook(f)
        raw = xl.parse(xl.sheet_names[0], header=None)
        cols = [c.lower() for c in build_header(raw, 1, 2)]
        print([c for c in cols if "ยา" in c])
