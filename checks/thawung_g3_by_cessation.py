"""Tha Wung G3: 6-month clinical change split by medication status at 6 months.

Reads the DMR analysis root after the 2026-11-11 rerun; writes nothing there.
Reuses the repo's own definitions so the numbers reconcile with the report:
  - sender      = derive_sender_tables.assign_senders (private filename map)
  - G3          = derive_sender_tables.group_masks (on drug at baseline AND HbA1c ≤ 6.5%; < 6.5% before 13 Nov 2026)
  - stopped     = drug_stop_m6_eligible & drug_stopped_m6 == 1 (the report's cessation
                  indicator; insulin and other glucose-lowering drugs count as drug use)
  - on drug     = drug_stop_m6_eligible & drug_stopped_m6 == 0
  - unknown     = baseline-medicated but not cessation-eligible (no 6-month drug status)
  - change      = derive_sender_tables.paired_change (complete pairs, paired-t 95% CI)
Prints aggregates only. Any group or pair count of 1-4 is shown as "<5" with no estimate.

Run: <DMR>/.venv/bin/python -B -I thawung_g3_by_cessation.py <DMR root>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "tools"))
from derive_sender_tables import assign_senders, group_masks, paired_change  # noqa: E402
from derive_additional_tables import MEASURES, rate  # noqa: E402

TW = "รพ.ท่าวุ้ง"
TAB = ROOT / "outputs" / "tables"
SHORT = {"HbA1c": "HbA1c (%)", "Fasting blood sugar": "FBS (mg/dL)",
         "BMI": "BMI (kg/m²)", "Waist circumference": "Waist (cm)"}


def small(k):
    return 0 < int(k) < 5


def cnt(k):
    return "<5" if small(k) else str(int(k))


def fmt_rate(k, n):
    if small(k) or small(n):
        return f"{cnt(k)}/{cnt(n)}"
    r = rate(int(k), int(n))
    return f"{k}/{n} = {r['pct']:.1f}% ({r['lo95']:.1f}–{r['hi95']:.1f})"


def change_lines(d):
    out = []
    for spec in MEASURES:
        r = paired_change(d, *spec)
        nm = SHORT[spec[2]]
        if r["n_pairs"] == 0:
            out.append(f"    {nm:<13} pairs 0")
        elif small(r["n_pairs"]):
            out.append(f"    {nm:<13} pairs <5 (no estimate)")
        else:
            out.append(f"    {nm:<13} pairs {r['n_pairs']:>3}  {r['pre_mean']:7.2f} -> {r['post_mean']:7.2f}"
                       f"  change {r['mean_change']:+6.2f} ({r['lo95']:+.2f} to {r['hi95']:+.2f})"
                       f"  tiers: {r['tiers']}")
    return out


def show(label, d):
    print(f"  {label}: n {cnt(len(d))}")
    if small(len(d)) or len(d) == 0:
        return
    print("\n".join(change_lines(d)))


def welch_diff(a, b, pre, post):
    """Mean change in a minus mean change in b (Welch 95% CI)."""
    x = (a[post] - a[pre]).dropna().to_numpy(float)
    y = (b[post] - b[pre]).dropna().to_numpy(float)
    if min(len(x), len(y)) < 5:
        return None
    va, vb = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    se = np.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (len(x) - 1) + vb ** 2 / (len(y) - 1))
    diff = x.mean() - y.mean()
    half = stats.t.ppf(0.975, df) * se
    p = 2 * stats.t.sf(abs(diff / se), df)
    return len(x), len(y), diff, diff - half, diff + half, p


def show_diff(label, a, b):
    print(f"  {label}")
    for pre, post, nm, _ in MEASURES:
        r = welch_diff(a, b, pre, post)
        if r is None:
            print(f"    {SHORT[nm]:<13} a pair count is under 5 (no estimate)")
        else:
            print(f"    {SHORT[nm]:<13} pairs {r[0]} vs {r[1]}  difference {r[2]:+.2f}"
                  f" ({r[3]:+.2f} to {r[4]:+.2f}) Welch p {r[5]:.3f}")


def split_status(d):
    elig = d.drug_stop_m6_eligible.eq(True)
    return {
        "on drug at 6 mo": d[elig & d.drug_stopped_m6.eq(0)],
        "stopped at 6 mo": d[elig & d.drug_stopped_m6.eq(1)],
        "status unknown": d[~elig],
    }


master = pd.read_csv(ROOT / "data" / "processed" / "dmr_master.csv", low_memory=False)
prog = master[master.cohort.eq("program")].copy()
prog = assign_senders(prog, pd.read_csv(ROOT / "data" / "case_report" / "_filename_map.csv"))
clinical, _ = group_masks(prog)
g3_mask = dict(((dim, grp), m) for dim, grp, m, _ in clinical)[("subgroup", "g3")]
prog["g3"] = g3_mask
tw = prog.sender.eq(TW)

# ------------------------------------------------------------ reconciliation
t29 = pd.read_csv(TAB / "table29_sender_group_metadata.csv")
t26 = pd.read_csv(TAB / "table26_sender_outcomes_m6.csv")
t27 = pd.read_csv(TAB / "table27_sender_clinical_m6.csv")
g3_all = int(t29[(t29.dimension == "subgroup") & (t29.group == "g3")].n_group.sum())
g3_tw = int(t29[(t29.dimension == "subgroup") & (t29.group == "g3") & (t29.sender == TW)].n_group.iloc[0])
assert int(prog.g3.sum()) == g3_all and int((prog.g3 & tw).sum()) == g3_tw
ces = t26[(t26.sender == TW) & t26.outcome.str.startswith("Drug cessation")].iloc[0]
twe = prog[tw & prog.drug_stop_m6_eligible.eq(True)]
assert (int(twe.drug_stopped_m6.sum()), len(twe)) == (int(ces.events), int(ces.n))
for spec in MEASURES:
    mine = paired_change(prog[tw & prog.g3], *spec)
    ref = t27[(t27.sender == TW) & (t27.dimension == "subgroup") & (t27.group == "g3")
              & (t27.measure == spec[2])].iloc[0]
    assert mine["n_pairs"] == ref.n_pairs and np.isclose(mine["mean_change"], ref.mean_change)
for k in ["on_any_pre", "on_any_m6"]:
    assert set(prog[k].dropna().unique()) <= {0, 1}
print("=== 0. RECONCILIATION (all passed)")
print(f"  programme n {len(prog)} | G3 {g3_all} | Tha Wung G3 {g3_tw} (table29)")
print(f"  Tha Wung cessation {int(ces.events)}/{int(ces.n)} (table26)")
print("  Tha Wung G3 paired changes match table27 for all 4 measures")
print("  drug_stop_m6_eligible == baseline on drug & on_any_m6 known & med_outcome_valid:",
      bool((prog.drug_stop_m6_eligible.eq(True)
            == (prog.on_any_pre.eq(1) & prog.on_any_m6.notna() & prog.med_outcome_valid.eq(True))).all()))

# ------------------------------------------------------------ 1-2. Tha Wung G3
print("\n=== 1-2. THA WUNG G3 BY MEDICATION STATUS AT 6 MONTHS")
d = prog[tw & prog.g3]
print(f"  Tha Wung G3 total: n {len(d)}; cessation {fmt_rate(int(d.drug_stopped_m6.eq(1).sum()), int(d.drug_stop_m6_eligible.eq(True).sum()))}")
print("  6-month drug-status tier:", d.loc[d.on_any_m6.notna(), "on_any_m6_tier"].value_counts().to_dict())
show("ALL Tha Wung G3", d)
for k, v in split_status(d).items():
    show(k, v)
s = split_status(d)
show_diff("difference in change, stopped minus on drug (Tha Wung G3)", s["stopped at 6 mo"], s["on drug at 6 mo"])

on = s["on drug at 6 mo"]
nc = on.n_class_m6 - on.n_class_pre
print("\n  Secondary: Tha Wung G3 still on drug, by change in number of drug classes (m6 minus baseline)")
print("   ", {"fewer classes": cnt((nc < 0).sum()), "same": cnt((nc == 0).sum()),
             "more classes": cnt((nc > 0).sum()), "class count missing": cnt(nc.isna().sum())})
show("on drug, fewer classes", on[nc < 0])
show("on drug, same or more classes", on[nc >= 0])
show_diff("difference in change, fewer classes minus same or more (Tha Wung G3 on drug)", on[nc < 0], on[nc >= 0])

# ------------------------------------------------------------ 3a. G3 other senders
print("\n=== 3a. G3 OUTSIDE THA WUNG BY MEDICATION STATUS AT 6 MONTHS")
d = prog[~tw & prog.g3]
print(f"  G3 other senders total: n {len(d)}; cessation {fmt_rate(int(d.drug_stopped_m6.eq(1).sum()), int(d.drug_stop_m6_eligible.eq(True).sum()))}"
      f"; senders {d.sender.nunique()}")
show("ALL G3 other senders", d)
for k, v in split_status(d).items():
    show(k, v)
s3 = split_status(d)
show_diff("difference in change, stopped minus on drug (G3 other senders)", s3["stopped at 6 mo"], s3["on drug at 6 mo"])

# ------------------------------------------------------------ 3b. Tha Wung non-G3
print("\n=== 3b. THA WUNG PATIENTS NOT IN G3")
d = prog[tw & ~prog.g3]
print(f"  Tha Wung non-G3 total: n {len(d)}")
show("ALL Tha Wung non-G3", d)
med = d[d.on_any_pre.eq(1)]
print(f"  baseline on drug (G2 or HbA1c missing): n {len(med)}; G2 {cnt(med.hba1c_pre.gt(6.5).sum())},"
      f" baseline HbA1c missing {cnt(med.hba1c_pre.isna().sum())};"
      f" cessation {fmt_rate(int(med.drug_stopped_m6.eq(1).sum()), int(med.drug_stop_m6_eligible.eq(True).sum()))}")
for k, v in split_status(med).items():
    show("baseline on drug, " + k, v)
sn = split_status(med)
show_diff("difference in change, stopped minus on drug (Tha Wung non-G3 on drug)", sn["stopped at 6 mo"], sn["on drug at 6 mo"])
show("baseline no drug", d[d.on_any_pre.eq(0)])
show("baseline drug status missing", d[d.on_any_pre.isna()])

# ------------------------------------------------------------ pooled check
print("\n=== 4. CONTEXT: ALL G3 (every sender), stopped minus on drug")
sa = split_status(prog[prog.g3])
for k, v in sa.items():
    show(k, v)
show_diff("difference in change, stopped minus on drug (all G3)", sa["stopped at 6 mo"], sa["on drug at 6 mo"])
