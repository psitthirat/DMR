"""Derive aggregate presentation additions from the private analysis master.

Run with the analysis environment (pandas, numpy and scipy are required):
  .venv/bin/python story/scripts/derive_additional_tables.py
  python3 story/scripts/build_data.py

A standalone clone can pass --analysis-root /path/to/private/DMR. This script
only writes aggregate CSVs to that workspace's outputs/tables/. It never
writes individual records to the public website. Existing notebook outputs
are validated and left unchanged.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


MEASURES = [
    ('hba1c_pre', 'hba1c_m6', 'HbA1c', '%'),
    ('fbs_pre', 'fbs_m6', 'Fasting blood sugar', 'mg/dL'),
    ('bmi_pre', 'bmi_m6', 'BMI', 'kg/m²'),
    ('waist_pre', 'waist_m6', 'Waist circumference', 'cm'),
]


def tier_mix(data, column):
    counts = data.loc[data[column].notna(), column + '_tier'].value_counts()
    return ', '.join(f'{tier} {n}' for tier, n in counts.items()) or '-'


def paired_change(data, pre, post, measure, unit):
    """Notebook §0.1 estimator: complete pairs, paired t 95% interval."""
    pairs = data[[pre, post]].dropna()
    a, b = pairs[pre].to_numpy(float), pairs[post].to_numpy(float)
    n = len(pairs)
    row = {
        'measure': measure, 'unit': unit, 'n_group': len(data), 'n_pairs': n,
        'missing_pair': len(data) - n,
        'missing_pre_n': int(data[pre].isna().sum()),
        'missing_post_n': int(data[post].isna().sum()),
        'missing_both_n': int((data[pre].isna() & data[post].isna()).sum()),
        'definition': 'At 6 months',
        'tiers': tier_mix(data.loc[pairs.index], post),
    }
    if n < 3:
        raise ValueError(f'Insufficient pairs for requested aggregate: {measure}, n={n}')
    diff = b - a
    sd = diff.std(ddof=1)
    half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    row.update({
        'pre_mean': a.mean(), 'pre_sd': a.std(ddof=1),
        'post_mean': b.mean(), 'post_sd': b.std(ddof=1),
        'mean_change': diff.mean(),
        'lo95': diff.mean() - half, 'hi95': diff.mean() + half,
        'cohen_dz': diff.mean() / sd if sd else np.nan,
    })
    return row


def rate(events, n):
    """Notebook §0.1 Wilson score interval, expressed in percentage points."""
    if not n:
        return {'events': events, 'n': n, 'pct': None, 'lo95': None, 'hi95': None}
    z = stats.norm.ppf(0.975)
    p = events / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {'events': events, 'n': n, 'pct': 100 * p,
            'lo95': 100 * max(0, centre - half),
            'hi95': 100 * min(1, centre + half)}


def metadata(data, dimension, group, definition):
    return {
        'dimension': dimension, 'group': group, 'definition': definition,
        'n_group': len(data),
        'hba1c_gt65_n': int(data.hba1c_pre.gt(6.5).sum()),
        'hba1c_eq65_n': int(data.hba1c_pre.eq(6.5).sum()),
        'hba1c_lt65_n': int(data.hba1c_pre.lt(6.5).sum()),
        'hba1c_missing_n': int(data.hba1c_pre.isna().sum()),
        'insulin_n': int(data.on_insulin_pre.eq(1).sum()),
        'non_insulin_n': int(data.on_insulin_pre.eq(0).sum()),
        'insulin_missing_n': int(data.on_insulin_pre.isna().sum()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis-root', type=Path,
                        default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.analysis_root.resolve()
    source = root / 'data' / 'processed' / 'dmr_master.csv'
    tables = root / 'outputs' / 'tables'
    df = pd.read_csv(source, low_memory=False)
    prog = df[df.cohort.eq('program')].copy()
    if len(prog) != 995:
        raise ValueError('Programme cohort differs from the 995-person notebook; review before rebuilding.')
    for column in ['on_any_pre', 'on_any_m6', 'on_insulin_pre']:
        if not set(prog[column].dropna().unique()).issubset({0, 1}):
            raise ValueError(f'Unexpected coding in {column}')

    # Ensure this extension uses the exact same cleaned master and 6-month
    # anchor as the already-published notebook. No timing tier is excluded.
    original = pd.read_csv(tables / 'table2_paired_change.csv')
    for spec in MEASURES:
        result = paired_change(prog, *spec)
        existing = original[(original.definition == 'At 6 months')
                            & (original.measure == result['measure'])].iloc[0]
        for key in ['n_pairs', 'pre_mean', 'post_mean', 'mean_change', 'lo95', 'hi95']:
            if not np.isclose(result[key], existing[key], rtol=1e-10, atol=1e-10):
                raise ValueError(f'Notebook reconciliation failed: {result["measure"]} {key}')

    baseline_gt = prog.hba1c_pre.gt(6.5)
    baseline_le = prog.hba1c_pre.le(6.5)
    # G1 is intentionally revised for this presentation at the user's request.
    # G2/G3 retain the notebook boundaries; exactly 6.5 belongs to G2.
    g1 = prog.on_any_pre.eq(0) & baseline_gt
    g2 = prog.on_any_pre.eq(1) & prog.hba1c_pre.ge(6.5)
    g3 = prog.on_any_pre.eq(1) & prog.hba1c_pre.lt(6.5)
    groups = [
        ('baseline_hba1c', 'gt65', baseline_gt, 'Baseline HbA1c > 6.5%'),
        ('baseline_hba1c', 'le65', baseline_le, 'Baseline HbA1c ≤ 6.5%'),
        ('subgroup', 'g1', g1, 'No glucose-lowering drug at baseline AND baseline HbA1c > 6.5%'),
        ('subgroup', 'g2', g2, 'On glucose-lowering medication at baseline AND baseline HbA1c ≥ 6.5%'),
        ('subgroup', 'g3', g3, 'On glucose-lowering medication at baseline AND baseline HbA1c < 6.5%'),
        ('g2_insulin', 'insulin', g2 & prog.on_insulin_pre.eq(1), 'G2 using insulin at baseline, with or without oral medication'),
        ('g2_insulin', 'non_insulin', g2 & prog.on_insulin_pre.eq(0), 'G2 not using insulin at baseline'),
    ]
    clinical, group_meta = [], []
    for dimension, group, mask, definition in groups:
        data = prog[mask]
        group_meta.append(metadata(data, dimension, group, definition))
        for spec in MEASURES:
            clinical.append({'dimension': dimension, 'group': group,
                             **paired_change(data, *spec)})

    original_g1 = prog.on_any_pre.eq(0)
    additional_meta = [
        ('baseline_hba1c', 'missing', prog.hba1c_pre.isna(), 'Baseline HbA1c missing; excluded from the two HbA1c strata'),
        ('g2_insulin', 'missing', g2 & prog.on_insulin_pre.isna(), 'G2 baseline insulin status missing; not assigned to non-insulin'),
        ('subgroup', 'unclassified', ~(g1 | g2 | g3), 'Outside the displayed group definitions or missing baseline data'),
        ('subgroup_exclusions', 'missing_medication', prog.on_any_pre.isna(), 'Baseline medication unknown'),
        ('subgroup_exclusions', 'treated_missing_hba1c', prog.on_any_pre.eq(1) & prog.hba1c_pre.isna(), 'On medication but baseline HbA1c missing'),
        ('subgroup_exclusions', 'untreated_le65', original_g1 & baseline_le, 'Baseline drug-naive with HbA1c ≤ 6.5%; excluded from revised G1'),
        ('subgroup_exclusions', 'untreated_missing_hba1c', original_g1 & prog.hba1c_pre.isna(), 'Baseline drug-naive with HbA1c missing; excluded from revised G1'),
    ]
    for dimension, group, mask, definition in additional_meta:
        group_meta.append(metadata(prog[mask], dimension, group, definition))
    if int(g1.sum() + g2.sum() + g3.sum()) != 882:
        raise ValueError('Unexpected revised subgroup counts; review the cohort before publication.')

    # Medication outcomes require the same med_outcome_valid flag as the ETL.
    # Missing results are excluded from denominators, never imputed as failure.
    medication_valid = prog.med_outcome_valid.eq(True)
    treated = prog.on_any_pre.eq(1)
    med_eligible = treated & prog.on_any_m6.notna() & medication_valid
    if not med_eligible.equals(prog.drug_stop_m6_eligible):
        raise ValueError('Cessation eligibility differs from the notebook.')
    paired_outcome = med_eligible & prog.hba1c_m6.notna()
    stoppers = med_eligible & prog.on_any_m6.eq(0)
    all_paired = prog.on_any_m6.notna() & prog.hba1c_m6.notna() & medication_valid
    controlled_off = prog.on_any_m6.eq(0) & prog.hba1c_m6.lt(6.5)
    if not all_paired.equals(prog.remission_m6.notna()):
        raise ValueError('Historical proxy eligibility differs from the notebook.')
    populations = [
        ('stopped_controlled', paired_outcome, treated,
         'Baseline-medicated patients who stopped all glucose-lowering drugs and had HbA1c < 6.5% at 6 months; denominator has both follow-up values'),
        ('among_stoppers', stoppers & prog.hba1c_m6.notna(), stoppers,
         'HbA1c < 6.5% among baseline-medicated patients who stopped all drugs at 6 months and had follow-up HbA1c'),
        ('all_off_drug_proxy', all_paired, pd.Series(True, index=prog.index),
         'Historical notebook proxy: off all drugs and HbA1c < 6.5% at 6 months, irrespective of baseline medication use'),
    ]
    remission = []
    for group, denominator, population, definition in populations:
        sub = prog[denominator]
        row = {
            'group': group, 'definition': definition,
            **rate(int((denominator & controlled_off).sum()), int(denominator.sum())),
            'n_population': int(population.sum()),
            'n_missing': int((population & ~denominator).sum()),
            'n_baseline_medicated': int(treated.sum()),
            'eligible_medication_n': int((population & prog.on_any_m6.notna() & medication_valid).sum()),
            'missing_hba1c_n': int((population & prog.on_any_m6.notna() & medication_valid & prog.hba1c_m6.isna()).sum()),
            'missing_medication_n': int((population & ~(prog.on_any_m6.notna() & medication_valid)).sum()),
            'stopped_total_n': int(stoppers.sum()),
            'stopped_missing_hba1c_n': int((stoppers & prog.hba1c_m6.isna()).sum()),
            'tiers_hba1c': tier_mix(sub, 'hba1c_m6'),
            'tiers_medication': tier_mix(sub, 'on_any_m6'),
        }
        remission.append(row)
    outcomes = pd.read_csv(tables / 'table4_outcome_rates.csv')
    old_proxy = outcomes[(outcomes.cohort == 'Programme')
                         & (outcomes.outcome == 'Remission AT 6 MONTHS - upper bound')].iloc[0]
    for key in ['events', 'n', 'pct', 'lo95', 'hi95']:
        if not np.isclose(remission[-1][key], old_proxy[key]):
            raise ValueError(f'Historical remission proxy reconciliation failed: {key}')
    if int(med_eligible.sum()) != 718 or int(stoppers.sum()) != 96:
        raise ValueError('Cessation totals differ from the published analysis.')

    tables.mkdir(parents=True, exist_ok=True)
    for filename, rows in [
        ('table22_clinical_strata_m6.csv', clinical),
        ('table23_remission_detail_m6.csv', remission),
        ('table24_presentation_group_metadata.csv', group_meta),
    ]:
        pd.DataFrame(rows).to_csv(tables / filename, index=False)
        print(f'Wrote {filename}: {len(rows)} aggregate rows.')
    print('Validated existing overall clinical changes, cessation totals and historical remission proxy; no individual records exported.')


if __name__ == '__main__':
    main()
