# DM Remission — combining and analysing the site case-report files

Twenty-four Excel workbooks submitted by participating sites, in five different
layouts, combined into one patient-level dataset and analysed for programme
effectiveness.

## Run it

See "Reproduce the analysis" in `README.md` (locked Python 3.13.2 environment,
`tools/run_pipeline.sh` and the baseline check). The data are not in this repository.

## Layout

The interactive Thai policy story is in `docs/` (see `README.md`): adjustable
figures and PNG/SVG/CSV downloads. Preview it with
`python3 -m http.server 4173 --bind 127.0.0.1 --directory docs`, then open
<http://localhost:4173>. The web directory contains aggregate data only.
`data/` below is outside git (a symlink to `../DMR-data`).

```
data/case_report/      24 source workbooks, renamed to their facility name
                       (_filename_map.csv records the originals)
data/corrections/      date_corrections.csv: hand-checked date decisions with reasons
data/processed/        dmr_master.csv + audit trail   ← generated
src/dmr_parse.py       field-level parsers: dates, numbers, drug regimens
src/dmr_etl.py         one loader per file layout, de-duplication, derived variables
src/dmr_viz.py         matplotlib theme
notebooks/01_combine_data.ipynb            how the files are combined, and why
notebooks/02_analysis_effectiveness.ipynb  the analysis
outputs/tables/        23 result tables (CSV)          ← generated
outputs/figures/       11 figures (PNG)                ← generated
```

## Provider levels

The programme ran at two kinds of facility, analysed as subgroups throughout:

| Level | Meaning | Sites | Patients |
|---|---|---|---|
| `community_hospital` | โรงพยาบาลชุมชน — district hospital with beds, own pharmacy and lab | 5 | 613 |
| `primary_care` | โรงพยาบาลส่งเสริมสุขภาพตำบล (รพ.สต.) | 15 | 382 |

Two assignments are not what their name suggests: **PCC คลองศาลา** counts as
`community_hospital`, as the project team agreed, because it was split off from
รพ.เพชรบูรณ์ into a new building of its own with dedicated doctors and nurses,
so its capacity is that of a community hospital (reason recorded 11 Nov 2026);
and the
workbook labelled **โรงพยาบาลกงหรา** is in fact from **รพ.สต.บ้านโล๊ะจังกะ**
and is renamed accordingly. The mapping lives in `FACILITY_INFO` in
`dmr_etl.py`, which also normalises the raw workbook strings to canonical
facility names.

Source files were renamed to their facility name for legibility.
`classify_file` routes workbooks to loaders **by inspecting their contents**,
never by filename, so renaming cannot silently change the analysis —
`data/case_report/_filename_map.csv` records every original name.

## The five source layouts

| Layout | Files | Shape |
|---|---|---|
| Case Record Form | พิมาย, ท่าวุ้ง, กงหรา, หูแร่ ×3, อุ้มผาง | one row per patient, 22–24 fixed columns, medication as free text |
| CRF site variants | บางระกำ, PCC คลองศาลา | grouped two-row headers; PCC has one column per drug per visit |
| รพ.สต. summary | 13 sub-district health centres | `ก่อน`/`หลัง` column blocks, one column per drug holding a dose string |
| Relational HIS export | รพ.บ้านตาขุน | four sheets keyed on participant ID, follow-up packed as `date \| value \| …` |
| Google-Forms export | "for edit ข้อมูลคนไข้โครงการ 2" | baseline + 3-month HbA1c, tablet counts |

## Four decisions worth knowing about

**Outcomes are anchored at 6 months after enrolment**, not at each patient's
last recorded value — "last observed" conflates a patient measured at 3 months
with one measured at 12. Because the workbooks support that anchor unevenly,
every 6-month value carries a **timing tier**:

| Tier | Meaning | Source |
|---|---|---|
| `measured` | a real measurement date, within ±3 months of the target | รพ.บ้านตาขุน — the only workbook with dates |
| `labelled` | a column explicitly labelled *N months since enrolment* | CRF `FBS ระหว่างเข้าร่วมโครงการ 6 เดือน`, บางระกำ, PCC `6 mo.` |
| `assumed` | a single unlabelled follow-up column, taken to be ≈6 months | รพ.สต. `หลัง` block; CRF mid-programme columns |

Two traps this catches: the CRF's `หลังจบโครงการ 6 เดือน` is anchored to
programme *end*, a different clock (so it is not used); and รพ.พิมาย's
22-column CRF has an *unlabelled* mid-programme FBS column where the 24-column
files have an explicit one. Both definitions are kept in the master table
(`*_m6` and `*_post`/`*_last`) so the effect of the choice is visible.

**Three cohorts, analysed in parallel and never pooled.**

| Cohort | n | Medication basis | Anchor |
|---|---|---|---|
| `program` | 995, 20 sites | `regimen` — the drug prescribed at each visit | 6 months |
| `registry` | 1,461, รพ.บ้านตาขุน | `dispensing` + attendance evidence | no dates → none |
| `survey_2023` | 214, "โครงการ 2" | `count` of tablets and injections | 3 months |

Pooling is not possible: the registry is a **single facility**, so a cohort
term and a site term are mathematically indistinguishable (notebook `02` §7.9
demonstrates the model failing) — and the three measure medication three
different ways at two different timepoints. `med_outcome_basis` carries that
in the data so a count-based rate is never silently compared with a
regimen-based one.

The registry contains 115 patients recorded as deceased and 78 lost to
follow-up — it is a register, not a programme roster. The 2566 survey covers
the same Kranuan network as the 13 รพ.สต. workbooks but is a **separate
round**: matching on HN and on name both give about 8 % overlap.

**Recovering cessation from a dispensing list.** The registry's medication
column lists drugs *dispensed*, not the current regimen, so a blank cell means
either "stopped" or "never followed up". The other three sheets settle it: a
patient with post-index lab results or visits demonstrably kept attending, so a
blank drug list for them means no drug was dispensed. Validated against
pharmacy cost — that group averages 97฿ of drug spend per visit against 910฿
for those still on treatment. It has **no dates**, though, so the registry has
no 6-month cessation figure.

**Zero is not missing.** In the dose columns, `off`/`0`/`-`/`ไม่มี` mean *not on
the drug*; a blank cell means *not recorded*.

**Dates carry an Excel trap.** A cell typed `9/10/68` (meaning 9 Oct **2568** BE)
is stored by Excel as **1968**. Years 1940–1999 are read as truncated two-digit
Buddhist years and shifted by +57; years ≥ 2400 have 543 subtracted.

One workbook (อุ้มผาง) has a corrupted zip header and will not open in Excel or
pandas. `dmr_etl.open_workbook` regenerates the damaged boilerplate member in
memory; no cell data is touched. Without it, 40 patients are lost.

## Headline results

### Programme cohort — 995 patients, 20 sites, outcomes at 6 months

| | at 6 months | last observed (old definition) |
|---|---|---|
| HbA1c | **−0.27 %** (−0.37 to −0.18), n = 861 | −0.41 %, n = 922 |
| Fasting blood sugar | **−11.9 mg/dL** (−15.0 to −8.7), n = 812 | −16.0 mg/dL, n = 858 |
| BMI | **−0.47 kg/m²** (−0.68 to −0.26), n = 883 | −0.47 kg/m² |
| Waist circumference | **−2.25 cm** (−2.80 to −1.71), n = 874 | −2.21 cm |
| **Off all glucose-lowering drugs** | **13.3 %** (11.0–15.9), n = 731 | 16.0 %, n = 758 |
| Remission (HbA1c < 6.5 % and drug-free) | 9.2 % (7.4–11.4) — **upper bound** | 11.2 % |

Adjusted determinants of cessation at 6 months (GEE logistic, clustered by
facility; n = 707, 95 events, 20 sites): baseline HbA1c aOR **0.60** per 1 %
(0.42–0.87), baseline drug classes aOR **0.18** per class (0.10–0.34); baseline
BMI 0.974 (0.947–1.001), p = 0.06. Exchangeable within-site correlation 0.08;
per-site rates span a wide range. Baseline insulin is no longer a covariate:
none of the 28 baseline insulin users stopped all drugs, so the term is not
estimable (complete separation); insulin still counts in the drug-class count.

*Rerun 11 Nov 2026.* Numbers above follow four loader fixes: รพ.สต.หนองโน's
`ยาmfm` column and its `การปรับยา: หยุด` ticks are now read (cessation set
+17, events +7); a CRF regimen such as `MFM 850 mg 1x2 off pio` now keeps
metformin on instead of counting the patient off every drug (events −2);
`off hctz` (a non-diabetes drug) is no longer read as a diabetes-drug stop; and
a รพ.สต. หลัง block recorded as 0 is a stop only if every baseline drug has a
recorded หลัง value, otherwise unknown (set −4, events −4). Nine implausible
dates are set missing by `data/corrections/date_corrections.csv`.
Before the rerun: 13.4 % (96/718), remission proxy 9.2 % (73/790), HbA1c aOR
0.60, drug classes aOR 0.25.

### Registry cohort — 1,461 patients, รพ.บ้านตาขุน

Comparison series and replication set, not programme results.

| at the same 6-month anchor | |
|---|---|
| HbA1c | −0.17 % (−0.28 to −0.07), n = 611 |
| Fasting blood sugar | **+16.1 mg/dL** (+12.4 to +19.8), n = 639 |
| Off all glucose-lowering drugs at 6 months | **not measurable** — no dated medication data |

### The 2566 survey cohort, at 3 months

| | |
|---|---|
| Off all glucose-lowering drugs at 3 months | **44.1 %** (37.1–51.5), n = 179 |
| The one programme site with a 3-month regimen column (PCC) | 42.5 % (28.5–57.8), n = 40 |

Those two agreeing matters: the high 3-month rate is **not** an artefact of
counting tablets. But it is **not** a time trend either — the 3-month and
6-month analysis sets are almost disjoint (3-month is PCC alone; 6-month is
dominated by low-cessation รพ.ท่าวุ้ง and รพ.พิมาย). Within the same 15 PCC
patients measured at both anchors, cessation *falls* from 47 % to 33 %: some
restart. Durability, not the 3-month snapshot, is the thing to measure.

**A regression-to-the-mean demonstration.** The survey's HbA1c fell −0.94
points, against −0.03 in the registry over the same window — apparently a
strong result. Its baseline HbA1c is a full point higher (8.23 vs 7.23), and
adjusting for that reduces the difference from **−0.92 to −0.02** (p = 0.89).
The same mechanism operates in every single-arm figure in this repo; it simply
cannot be isolated as cleanly without a comparison group.

### The comparison, and a correction

At a **common 6-month anchor**, only fasting glucose separates the cohorts:

| | programme − registry | p |
|---|---|---|
| Fasting blood sugar | **−28.0 mg/dL** (−32.8 to −23.2) | <0.001 |
| HbA1c | −0.10 % (−0.24 to +0.04) | 0.17 |
| BMI | +0.11 kg/m² | 0.38 |
| Waist | −0.57 cm | 0.14 |

Under the earlier **last-observed** definition the HbA1c gap looked like
−0.52 % — five times larger. That was an artefact of comparing the programme's
~6–12-month change against the register's ~28-month change. **The time anchor
overturned that conclusion**, and the narrower statement is the correct one:
the programme cohort's *fasting glucose* improved substantially more; their
*HbA1c* improvements were similar.

### Provider level — a finding that does not survive scrutiny

Cessation at 6 months looks twice as high in primary care (**19.3 %** vs
**8.9 %**, p < 0.001). **It should not be reported that way** — but the reason
is confounding, not a clean test that refutes it.

Provider level is almost perfectly confounded with the data template —
community hospitals submitted the CRF, primary care the รพ.สต. workbook.
Restricting to the two primary-care sites that used the CRF holds the template
fixed. The gap **narrows but does not close**: 8.9 % vs 17.1 %, Fisher
*p* = 0.098 — with only 41 patients and 7 events on the primary-care side, that
test is **inconclusive, not exculpatory**.

The dataset cannot separate provider level from data template, in either
direction. See notebook `02` §5.2.

**The two key determinants still replicate** in the register (drug classes
aOR 0.64, HbA1c aOR 0.74), though that comparison runs on the last-observed
outcome because the register has no dated medication.

**Cost.** Patients who stopped their drugs saw pharmacy spending fall
366 → 97฿ per visit while lab spending rose 279 → 563฿. Deprescribing shifts
cost rather than simply saving it.

## Caveats that belong with any of these numbers

- **Timing tiers are part of the result.** HbA1c in the programme cohort is
  `assumed` almost throughout — the CRF never labels its HbA1c follow-up
  against enrolment. Anyone quoting the 6-month HbA1c change should say the
  timing is inferred from the template, not recorded.
- **Drug cessation at 6 months exists only in the programme cohort**, and
  mostly at the `assumed` tier.
- **No randomised control.** The registry is a crude comparison series — a
  different hospital, period and measurement schedule — not a control arm. These
  are associations, not causal effects.
- **The registry's cessation flag is an inference**, validated against pharmacy
  cost but not a recorded field, and `ค่ายา` is total drug spend rather than
  diabetes-specific.
- **Remission is an upper bound.** ADA/EASD 2021 needs HbA1c measured ≥ 3 months
  *after* drugs stop; the stop date is not recorded anywhere.
- **Follow-up dates exist only in the registry.** Everywhere else the 6-month
  anchor rests on a template label or an assumption, which is what the timing
  tier records.
- **Benefit scheme and comorbidity are absent from the รพ.สต. template**, and
  diabetes duration from both the รพ.สต. and survey templates, so the main model
  runs on the fields every layout carries.
- **Provider level cannot be separated from data template.** The most
  interesting service-delivery question in the dataset is unanswerable until
  the two facility types use one template.
- **No cross-file patient identifiers** — de-duplication is within-facility and
  measurement-based, so a patient seen at both a health centre and its parent
  hospital would be counted twice.
