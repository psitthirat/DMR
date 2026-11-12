"""Enrolment-date window by sender, against the 6-month anchor. Aggregates only."""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(sys.argv[1]).resolve()
m = pd.read_csv(ROOT / "data/processed/dmr_master.csv", low_memory=False, parse_dates=["enroll_date"])
fmap = pd.read_csv(ROOT / "data/case_report/_filename_map.csv", encoding="utf-8-sig")
s_of = {**dict(zip(fmap.new_filename, fmap.sender)), **dict(zip(fmap.original_filename, fmap.sender))}
p = m[m.cohort == "program"].copy()
p["sender"] = p.source_file.map(s_of)
sup = lambda k: "<5" if 0 < int(k) < 5 else str(int(k))
cut = pd.Timestamp("2026-03-20")
for s, d in p.groupby("sender"):
    e = d.enroll_date
    if e.notna().sum() == 0:
        print(f"{s}: no enrolment date in template (n={len(d)})")
        continue
    late = e > cut
    print(f"{s}: dated {sup(e.notna().sum())}/{len(d)} | median {e.median():%Y-%m} | "
          f"P10 {e.quantile(.1):%Y-%m} P90 {e.quantile(.9):%Y-%m} | after 20 Mar 2026: {sup(late.sum())} "
          f"(with 6-mo HbA1c {sup((late & d.hba1c_m6.notna()).sum())}, 6-mo med {sup((late & d.on_any_m6.notna()).sum())}) | "
          f"after 30 Sep 2026: {sup((e > pd.Timestamp('2026-09-30')).sum())}")
late = p.enroll_date > cut
print("TOTAL after 20 Mar 2026:", int(late.sum()), "| with 6-mo HbA1c", int((late & p.hba1c_m6.notna()).sum()),
      "| in cessation set", int((late & p.drug_stop_m6_eligible.eq(True)).sum()),
      "| dates after 30 Sep 2026:", int((p.enroll_date > pd.Timestamp('2026-09-30')).sum()))
