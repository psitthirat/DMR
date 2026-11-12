"""Aggregate answers to the DMR final-report open questions, from the frozen
30 Sep 2026 repo state. Reads DMR/ only; writes nothing there. Prints
aggregates only: no rows, IDs or names. Facility-level cells under 5 are
suppressed as "<5".

Run: <DMR>/.venv/bin/python -B -I dmr_open_questions.py <DMR root>
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

ROOT = Path(sys.argv[1]).resolve()
PROC = ROOT / "data" / "processed"
TAB = ROOT / "outputs" / "tables"
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 200)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sup(k):
    """Suppress facility-level counts under 5."""
    k = int(k)
    return "<5" if 0 < k < 5 else str(k)


def wilson(k, n):
    if n == 0:
        return (np.nan, np.nan, np.nan)
    z = stats.norm.ppf(0.975)
    p = k / n
    den = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return 100 * p, 100 * max(0, c - h), 100 * min(1, c + h)


def fmt_rate(k, n):
    p, lo, hi = wilson(k, n)
    return f"{k}/{n} = {p:.1f}% ({lo:.1f}–{hi:.1f})"


def paired(d, pre, post):
    x = d[[pre, post]].dropna()
    n = len(x)
    if n < 2:
        return {"n": n}
    diff = x[post] - x[pre]
    sd = diff.std(ddof=1)
    half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    return {"n": n, "pre": x[pre].mean(), "post": x[post].mean(),
            "chg": diff.mean(), "lo": diff.mean() - half, "hi": diff.mean() + half}


def show_paired(label, d):
    out = []
    for pre, post, nm in [("hba1c_pre", "hba1c_m6", "HbA1c"), ("fbs_pre", "fbs_m6", "FBS"),
                          ("bmi_pre", "bmi_m6", "BMI"), ("waist_pre", "waist_m6", "waist")]:
        r = paired(d, pre, post)
        if r["n"] < 2:
            out.append(f"  {nm}: n={r['n']}")
        else:
            out.append(f"  {nm}: n={r['n']} {r['pre']:.2f} -> {r['post']:.2f} "
                       f"change {r['chg']:+.2f} ({r['lo']:+.2f} to {r['hi']:+.2f})")
    print(f"{label}\n" + "\n".join(out))


master = pd.read_csv(PROC / "dmr_master.csv", low_memory=False)
dropped = pd.read_csv(PROC / "dmr_dropped_duplicates.csv", low_memory=False)
audit = pd.read_csv(PROC / "dmr_source_audit.csv")
fmap = pd.read_csv(ROOT / "data" / "case_report" / "_filename_map.csv", encoding="utf-8-sig")
ev = json.load(open(ROOT / "docs" / "data" / "evidence.json", encoding="utf-8"))

print("=== 0. PROVENANCE")
print("master sha256 matches evidence.json:",
      sha(PROC / "dmr_master.csv") == ev["meta"]["sender_analysis"]["master_sha256"])
bad = [k for k, v in ev["sources"].items() if sha(ROOT / v["file"]) != v["sha256"]]
print("evidence.json tables whose local CSV differs:", bad or "none")
print("master rows by cohort:", master["cohort"].value_counts().to_dict())

prog = master[master["cohort"] == "program"].copy()
sender_of = {}
for r in fmap.to_dict("records"):
    sender_of[r["new_filename"]] = r["sender"]
    sender_of[r["original_filename"]] = r["sender"]
prog["sender"] = prog["source_file"].map(sender_of)
assert prog["sender"].notna().all()

# ---------------------------------------------------------------- Q1
print("\n=== Q1. RECORDS FLOW")
fam_of_loader = {"crf": "crf", "bangrakam": "crf", "pcc": "crf_pcc", "rphc": "rphc",
                 "relational": "relational", "survey": "survey"}
audit["cohort"] = audit["loader"].map(fam_of_loader).map(
    {"crf": "program", "crf_pcc": "program", "rphc": "program",
     "relational": "registry", "survey": "survey_2023"})
print(audit.groupby("cohort").agg(files=("file", "size"), rows_loaded=("n_rows", "sum")).to_string())
print("programme files by loader:", audit[audit.cohort == "program"].groupby("loader")
      .agg(files=("file", "size"), rows=("n_rows", "sum")).to_dict("index"))
dropped["cohort"] = dropped["source_family"].map(
    {"crf": "program", "crf_pcc": "program", "rphc": "program",
     "relational": "registry", "survey": "survey_2023"})
print("duplicates dropped by cohort:", dropped["cohort"].value_counts().to_dict())
print("duplicates dropped by file:", dropped["source_file"].value_counts().to_dict())
kept_by_file = master["source_file"].value_counts()
hr = audit[audit.file.str.contains("หูแร่")][["file", "n_rows"]].copy()
hr["kept"] = hr["file"].map(kept_by_file).fillna(0).astype(int)
hr["dropped"] = hr["file"].map(dropped["source_file"].value_counts()).fillna(0).astype(int)
print("Hu Rae: rows loaded", int(hr.n_rows.sum()), "| kept", int(hr.kept.sum()),
      "| dropped", int(hr.dropped.sum()), "| file kept as base:", hr.loc[hr.n_rows.idxmax(), "file"])
print("programme source files with >=1 retained row:", prog["source_file"].nunique())
# rows that the de-duplication cannot match (too little baseline data) are always kept
inf = master[["age", "bmi_pre", "fbs_pre", "hba1c_pre"]].notna().sum(axis=1) >= 2
print("programme rows too sparse to de-duplicate (kept by rule):",
      int((~inf[master.cohort == "program"]).sum()))

print("\n-- analysis sets, programme cohort (n=995)")
on = prog["on_any_pre"]
print("baseline medication: on", int((on == 1).sum()), "| not on", int((on == 0).sum()),
      "| unknown", int(on.isna().sum()))
med = prog[on == 1]
print("on drug at baseline, 6-mo medication status present:", int(med["on_any_m6"].notna().sum()),
      "missing:", int(med["on_any_m6"].isna().sum()))
print("cessation set (drug_stop_m6_eligible):", int(prog["drug_stop_m6_eligible"].sum()),
      "events:", int(prog["drug_stopped_m6"].sum()))
print("HbA1c at 6 months present:", int(prog["hba1c_m6"].notna().sum()),
      "| FBS:", int(prog["fbs_m6"].notna().sum()), "| BMI:", int(prog["bmi_m6"].notna().sum()),
      "| waist:", int(prog["waist_m6"].notna().sum()))
for nm, pre, post in [("HbA1c", "hba1c_pre", "hba1c_m6"), ("FBS", "fbs_pre", "fbs_m6"),
                      ("BMI", "bmi_pre", "bmi_m6"), ("waist", "waist_pre", "waist_m6")]:
    print(f"complete pairs {nm}:", int(prog[[pre, post]].notna().all(axis=1).sum()))
joint = med["on_any_m6"].notna() & med["hba1c_m6"].notna()
print("joint outcome denominator (on drug, both 6-mo values):", int(joint.sum()))

# ---------------------------------------------------------------- Q2
print("\n=== Q2. BASELINE (programme, n=995)")
a = prog["age"]
print(f"age: n={a.notna().sum()} mean {a.mean():.1f} SD {a.std():.1f} median {a.median():.0f} "
      f"IQR {a.quantile(.25):.0f}-{a.quantile(.75):.0f} min {a.min():.0f} max {a.max():.0f}; "
      f"age<18: {int((a < 18).sum())}")
print("sex:", prog["sex"].value_counts(dropna=False).to_dict(),
      "| sex inferred from name title (rphc):", int(prog.source_family.eq("rphc").sum()))
d = prog["dm_duration_y"]
print(f"DM duration: n={d.notna().sum()} mean {d.mean():.1f} SD {d.std():.1f} median {d.median():.1f} "
      f"IQR {d.quantile(.25):.1f}-{d.quantile(.75):.1f}; set to 0 because dx after enrolment: "
      f"{int(prog['dm_incident_after_index'].eq(1).sum())}; dx_date present {int(prog['dx_date'].notna().sum())}, "
      f"enroll_date present {int(prog['enroll_date'].notna().sum())}")
print("DM duration available by layout:", prog.groupby("source_family")["dm_duration_y"]
      .apply(lambda s: f"{s.notna().sum()}/{len(s)}").to_dict())
print("scheme:", prog["scheme"].value_counts(dropna=False).to_dict())
print("scheme available by layout:", prog.groupby("source_family")["scheme"]
      .apply(lambda s: f"{s.notna().sum()}/{len(s)}").to_dict())
for c in ["hypertension", "dyslipidaemia", "ckd", "cvd", "gout", "copd_asthma"]:
    s = prog[c].dropna()
    print(f"{c}: {int(s.sum())}/{len(s)} = {100*s.mean():.1f}%")
nc = prog["n_comorbid"]
print(f"n_comorbid: n={nc.notna().sum()} mean {nc.mean():.2f}; dist {nc.value_counts().sort_index().to_dict()}")
print("comorbid_raw present by layout:", prog.groupby("source_family")["comorbid_raw"]
      .apply(lambda s: f"{s.notna().sum()}/{len(s)}").to_dict())
print("hypertension known by sender:", prog.groupby("sender")["hypertension"]
      .apply(lambda s: f"{s.notna().sum()}/{len(s)}").to_dict())
for c in ["bmi_pre", "waist_pre", "fbs_pre", "hba1c_pre"]:
    s = prog[c]
    print(f"{c}: n={s.notna().sum()} mean {s.mean():.2f} SD {s.std():.2f}")
print("insulin at baseline:", int(prog["on_insulin_pre"].eq(1).sum()), "/", int(prog["on_insulin_pre"].notna().sum()))
print("drug classes at baseline (n, mean):", int(prog["n_class_pre"].notna().sum()), round(prog["n_class_pre"].mean(), 2))

print("\n-- GEE models (notebook 02 cells 67/71)")
e6 = prog[prog["drug_stop_m6_eligible"] == True].copy()  # noqa: E712
e6 = e6.assign(female=(e6["sex"] == "Female").astype(float), age10=e6["age"] / 10,
               insulin=e6["on_insulin_pre"], outcome=e6["drug_stopped_m6"],
               fbs10=e6["fbs_pre"] / 10)
varsA = ["outcome", "age10", "female", "hba1c_pre", "bmi_pre", "fbs10", "n_class_pre", "insulin", "facility"]
varsB = varsA + ["d_bmi_m6", "d_waist_m6"]
dA, dB = e6.dropna(subset=varsA), e6.dropna(subset=varsB)
print("Model A: n", len(dA), "events", int(dA.outcome.sum()), "facilities", dA.facility.nunique())
print("Model B: n", len(dB), "events", int(dB.outcome.sum()), "facilities", dB.facility.nunique())
print("cessation set 718 -> Model A: missing by variable among the 718:",
      {v: int(e6[v].isna().sum()) for v in varsA if e6[v].isna().any()})
print("sex missing in cessation set (coded as male by female=0):", int(e6["sex"].isna().sum()))
fA = "outcome ~ age10 + female + hba1c_pre + bmi_pre + fbs10 + n_class_pre + insulin"
gA = smf.gee(fA, groups="facility", data=dA, family=sm.families.Binomial(),
             cov_struct=sm.cov_struct.Exchangeable()).fit()
t7 = pd.read_csv(TAB / "table7_multivariable_gee.csv")
or_hba1c = float(np.exp(gA.params["hba1c_pre"]))
print(f"refit Model A aOR HbA1c {or_hba1c:.4f} vs table7 {t7.iloc[2]['OR']:.4f}; "
      f"drug classes {np.exp(gA.params['n_class_pre']):.4f} vs {t7.iloc[5]['OR']:.4f}")
print("Model A patients by sender:", dA.groupby("sender").size().map(sup).to_dict())

# ---------------------------------------------------------------- Q3
print("\n=== Q3. SIX-MONTH ANCHOR")
for c in ["hba1c_m6", "fbs_m6", "bmi_m6", "waist_m6", "on_any_m6"]:
    print(c, prog.loc[prog[c].notna(), c + "_tier"].value_counts().to_dict())
print("source of 6-mo value by layout (from M6_SOURCE): crf hba1c=hba1c_mid, med=on_any_mid, "
      "bmi/waist=*_post, fbs=fbs_m6_raw|fbs_6m; rphc = 'หลัง' block; crf_pcc = '6 mo.' columns")
en = pd.to_datetime(prog["enroll_date"], errors="coerce")
print("enrolment dates present:", int(en.notna().sum()), "range", en.min(), "to", en.max())
print("enrolment year-quarter:", en.dt.to_period("Q").value_counts().sort_index().to_dict())
late = en > pd.Timestamp("2026-03-20")
print("enrolled after 2026-03-20 (<6 months before the 20 Sep 2026 file date):", int(late.sum()),
      "| of those with a 6-mo HbA1c:", int((late & prog["hba1c_m6"].notna()).sum()),
      "| with 6-mo medication:", int((late & prog["on_any_m6"].notna()).sum()))
print("enrolment present by layout:", prog.groupby("source_family")["enroll_date"]
      .apply(lambda s: f"{s.notna().sum()}/{len(s)}").to_dict())
crf = prog[prog["source_family"] == "crf"]
print("CRF rows with end-of-programme HbA1c (hba1c_post):", int(crf["hba1c_post"].notna().sum()),
      "| with end-of-programme medication (on_any_post):", int(crf["on_any_post"].notna().sum()),
      "| CRF rows:", len(crf))

# ---------------------------------------------------------------- Q4
print("\n=== Q4. PROVIDER LEVEL")
fac = prog.groupby(["sender", "facility", "provider_level", "source_family"]).size().rename("n").reset_index()
print(fac.to_string(index=False))
print("level totals:", prog.groupby("provider_level").agg(sites=("facility", "nunique"), n=("facility", "size")).to_dict("index"))
ks = e6[e6["facility"] == "PCC คลองศาลา"]
k_ev, k_n = int(ks.outcome.sum()), len(ks)
pc, ch = e6[e6.provider_level == "primary_care"], e6[e6.provider_level == "community_hospital"]
print("as coded:   PC", fmt_rate(int(pc.outcome.sum()), len(pc)), "| CH", fmt_rate(int(ch.outcome.sum()), len(ch)))
print("Khlong Sala in cessation set:", k_ev, "/", k_n)
print("if Khlong Sala = primary care (Table 3.1): PC", fmt_rate(int(pc.outcome.sum()) + k_ev, len(pc) + k_n),
      "| CH", fmt_rate(int(ch.outcome.sum()) - k_ev, len(ch) - k_n))
crf_e = e6[e6.source_family.isin(["crf", "crf_pcc"])]
pc_c, ch_c = crf_e[crf_e.provider_level == "primary_care"], crf_e[crf_e.provider_level == "community_hospital"]
print("CRF-only as coded: PC", fmt_rate(int(pc_c.outcome.sum()), len(pc_c)), "| CH", fmt_rate(int(ch_c.outcome.sum()), len(ch_c)),
      "| Fisher p", round(stats.fisher_exact([[int(pc_c.outcome.sum()), len(pc_c) - int(pc_c.outcome.sum())],
                                               [int(ch_c.outcome.sum()), len(ch_c) - int(ch_c.outcome.sum())]])[1], 3))
pk, pn = int(pc_c.outcome.sum()) + k_ev, len(pc_c) + k_n
ck, cn = int(ch_c.outcome.sum()) - k_ev, len(ch_c) - k_n
print("CRF-only if Khlong Sala = PC: PC", fmt_rate(pk, pn), "| CH", fmt_rate(ck, cn),
      "| Fisher p", round(stats.fisher_exact([[pk, pn - pk], [ck, cn - ck]])[1], 3))
print("primary-care cessation set by sender:", pc.groupby("sender").size().to_dict())

# ---------------------------------------------------------------- Q5
print("\n=== Q5. G1 MEDICATION DURING FOLLOW-UP")
g1 = prog[(prog.on_any_pre == 0) & (prog.hba1c_pre > 6.5)]
naive = prog[prog.on_any_pre == 0]
for nm, d in [("G1 (revised, n=%d)" % len(g1), g1), ("all drug-naive (n=%d)" % len(naive), naive)]:
    print(nm, "| on_any_m6:", d["on_any_m6"].value_counts(dropna=False).to_dict(),
          "| tiers:", d.loc[d.on_any_m6.notna(), "on_any_m6_tier"].value_counts().to_dict(),
          "| on_any_last:", d["on_any_last"].value_counts(dropna=False).to_dict(),
          "| insulin at 6mo-equivalent (on_insulin_mid/post):",
          int(d["on_insulin_mid"].eq(1).sum()), int(d["on_insulin_post"].eq(1).sum()))
print("G1: n / started (on_any_m6=1) / stayed off (=0) / missing; Bang Rakam vs other senders combined")
for lab, d in [("Bang Rakam", g1[g1.sender == "รพ.บางระกำ"]), ("others combined", g1[g1.sender != "รพ.บางระกำ"])]:
    print(f"  {lab}: {len(d)} / {sup(d.on_any_m6.eq(1).sum())} / {sup(d.on_any_m6.eq(0).sum())} / {sup(d.on_any_m6.isna().sum())}")
started = g1[g1.on_any_m6 == 1]
stayed = g1[g1.on_any_m6 == 0]
show_paired("G1 HbA1c change, started drug at 6 mo:", started)
show_paired("G1 HbA1c change, stayed off drugs at 6 mo:", stayed)
show_paired("G1 all:", g1)

# ---------------------------------------------------------------- Q7
print("\n=== Q7. THA WUNG")
g3 = prog[(prog.on_any_pre == 1) & (prog.hba1c_pre < 6.5)]
print("G3 n", len(g3), "| from Tha Wung", int(g3.sender.eq("รพ.ท่าวุ้ง").sum()),
      "| other senders combined", int(g3.sender.ne("รพ.ท่าวุ้ง").sum()))
tw = prog[prog.sender == "รพ.ท่าวุ้ง"]
print("Tha Wung n", len(tw), "| layout", tw.source_family.unique().tolist(),
      "| tiers hba1c", tw.loc[tw.hba1c_m6.notna(), "hba1c_m6_tier"].value_counts().to_dict(),
      "| fbs", tw.loc[tw.fbs_m6.notna(), "fbs_m6_tier"].value_counts().to_dict())
show_paired("Tha Wung overall (6 mo):", tw)
show_paired("Tha Wung G3:", g3[g3.sender == "รพ.ท่าวุ้ง"])
show_paired("G3 excluding Tha Wung:", g3[g3.sender != "รพ.ท่าวุ้ง"])
show_paired("G3 all:", g3)
show_paired("Tha Wung non-G3:", tw[~tw.index.isin(g3.index)])
twe = e6[e6.sender == "รพ.ท่าวุ้ง"]
print("Tha Wung cessation:", fmt_rate(int(twe.outcome.sum()), len(twe)))
print("Tha Wung baseline med:", {str(k): sup(v) for k, v in tw.on_any_pre.value_counts(dropna=False).items()},
      "| baseline HbA1c<6.5:", int((tw.hba1c_pre < 6.5).sum()), "of", int(tw.hba1c_pre.notna().sum()))
print("Tha Wung G3 medication at 6 mo:", {str(k): sup(v) for k, v in g3[g3.sender == "รพ.ท่าวุ้ง"].on_any_m6.value_counts(dropna=False).items()},
      "| n_class change (mid-pre) mean:",
      round((g3[g3.sender == "รพ.ท่าวุ้ง"].n_class_m6 - g3[g3.sender == "รพ.ท่าวุ้ง"].n_class_pre).mean(), 2))
print("Tha Wung facility strings:", tw.facility.value_counts().map(sup).to_dict())

# ---------------------------------------------------------------- Q8
print("\n=== Q8. 73/790 vs 50/680")
rem = prog[prog.remission_m6.notna()]
print("73/790 denominator by baseline med:", rem.on_any_pre.value_counts(dropna=False).to_dict())
print("73/790 events by baseline med:", rem[rem.remission_m6 == 1].on_any_pre.value_counts(dropna=False).to_dict())
ev_naive = rem[(rem.remission_m6 == 1) & (rem.on_any_pre == 0)]
print("drug-naive events by baseline HbA1c: >6.5", int((ev_naive.hba1c_pre > 6.5).sum()),
      "| <=6.5", int((ev_naive.hba1c_pre <= 6.5).sum()), "| missing", int(ev_naive.hba1c_pre.isna().sum()))
print("drug-naive events: senders contributing", ev_naive.sender.nunique())
t4 = pd.read_csv(TAB / "table4_outcome_rates.csv")
t23 = pd.read_csv(TAB / "table23_remission_detail_m6.csv")
print("table4 remission row:", t4[t4.outcome.str.startswith("Remission AT")][["n", "events", "pct"]].to_dict("records"))
print("table23 rows:", t23[["group", "events", "n", "pct"]].to_dict("records"))

# ---------------------------------------------------------------- Q9
print("\n=== Q9. KRANUAN")
kr = prog[prog.sender == "รพ.กระนวน"]
print("Kranuan n", len(kr), "| units", kr.facility.nunique(), "| layouts", kr.source_family.unique().tolist())
print("baseline med:", kr.on_any_pre.value_counts(dropna=False).to_dict())
print("6-mo ('หลัง') med status:", kr.on_any_m6.value_counts(dropna=False).to_dict())
off6 = kr.on_any_m6.eq(0)
print("off at 6 mo:", int(off6.sum()), "| of whom on drug at baseline:", int((off6 & kr.on_any_pre.eq(1)).sum()),
      "| not on drug or unknown at baseline:", int((off6 & kr.on_any_pre.ne(1)).sum()))
print("on drug at baseline without 'หลัง' medication:", int((kr.on_any_pre.eq(1) & kr.on_any_m6.isna()).sum()))
ke = kr[kr.drug_stop_m6_eligible == True]  # noqa: E712
print("eligible", len(ke), "stopped", int(ke.drug_stopped_m6.sum()))
print("off all drugs at 6 mo, any baseline status:", int(kr.on_any_m6.eq(0).sum()))
red = ke[(ke.on_any_m6 == 1) & ke.tabs_pre.notna() & ke.tabs_post.notna() & (ke.tabs_post < ke.tabs_pre)]
fewer_cls = ke[(ke.on_any_m6 == 1) & (ke.n_class_m6 < ke.n_class_pre)]
print("still on drug but fewer tablets:", len(red), "| fewer classes:", len(fewer_cls))
print("stopped & HbA1c<6.5 at 6 mo:", int(((ke.on_any_m6 == 0) & (ke.hba1c_m6 < 6.5)).sum()),
      "of", int(((ke.on_any_m6.notna()) & ke.hba1c_m6.notna()).sum()))
print("baseline med status 'unknown' raw:", kr.med_status_pre.value_counts(dropna=False).to_dict())
print("6-mo med status raw:", kr.med_status_post.value_counts(dropna=False).to_dict())
print("insulin at baseline / after:", int(kr.on_insulin_pre.eq(1).sum()), int(kr.on_insulin_post.eq(1).sum()))
print("by unit: n / eligible / stopped / off at 6 mo (any baseline); 0-4 shown as <5")
s0 = lambda k: "<5" if int(k) < 5 else str(int(k))
for f, d in kr.groupby("facility"):
    e = d[d.drug_stop_m6_eligible == True]  # noqa: E712
    print(f"  {f}: {len(d)} / {s0(len(e))} / {s0(e.drug_stopped_m6.sum())} / {s0(d.on_any_m6.eq(0).sum())}")
srv = master[master.cohort == "survey_2023"]
se = srv[srv.drug_stop_m3_eligible == True]  # noqa: E712
print("survey 2566 (Kranuan network, separate round): n", len(srv), "| 3-mo cessation",
      fmt_rate(int(se.drug_stopped_m3.sum()), len(se)))
print("Kranuan share of programme:", len(kr), "/", len(prog), "| of 6-mo stoppers:",
      int(ke.drug_stopped_m6.sum()), "/", int(e6.outcome.sum()))
print("programme cessation excluding Kranuan:",
      fmt_rate(int(e6[e6.sender != "รพ.กระนวน"].outcome.sum()), int((e6.sender != "รพ.กระนวน").sum())))
for extra in (11, 21):
    print(f"if Kranuan had +{extra} stoppers in the same denominator: overall",
          fmt_rate(int(e6.outcome.sum()) + extra, len(e6)), "| Kranuan",
          fmt_rate(int(ke.drug_stopped_m6.sum()) + extra, len(ke)))
