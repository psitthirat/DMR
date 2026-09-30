"""Derive aggregate programme outcomes by the sender in the private filename map.

  .venv/bin/python story/scripts/derive_sender_tables.py
  python3 story/scripts/build_data.py

Pass --analysis-root /path/to/private/DMR from a standalone website clone.
The input master remains private. Only aggregate tables are written; neither
patient identifiers nor source filenames are included in the web bundle.
Sender is a submission/network grouping, not a reassignment of the treating
facility. All measures retain the notebook's 6-month anchor and timing tiers.
"""
import argparse
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from derive_additional_tables import MEASURES, metadata, rate, tier_mix


OUTCOMES = [
    ('drug_stopped_m6', 'Drug cessation AT 6 MONTHS (primary)'),
    ('remission_m6', 'Remission AT 6 MONTHS - upper bound'),
    ('a1c_lt7_m6', 'HbA1c < 7% at 6 months'),
]


def filename_key(name):
    return unicodedata.normalize('NFC', Path(str(name).strip()).name)


def assign_senders(programme, filename_map):
    """Accept either recorded filename; never guess from the facility label."""
    aliases = {}
    required = ['original_filename', 'new_filename', 'loader', 'sender']
    if filename_map[required].isna().any().any():
        raise ValueError('Filename mapping contains a missing filename, loader or sender.')
    for row in filename_map.to_dict('records'):
        sender = str(row['sender']).strip()
        loader = str(row['loader']).strip()
        for column in ['original_filename', 'new_filename']:
            key = filename_key(row[column])
            if not key or not sender or not loader:
                raise ValueError('Filename mapping contains an empty key or sender.')
            pair = (sender, loader)
            if key in aliases and aliases[key] != pair:
                raise ValueError(f'Conflicting sender/loader mappings for {key}')
            aliases[key] = pair
    keys = programme.source_file.map(filename_key)
    unmatched = sorted(set(keys) - aliases.keys())
    if unmatched:
        raise ValueError(f'Programme files missing from filename map: {unmatched}')
    mapped = keys.map(aliases)
    bad_loaders = {pair[1] for pair in mapped} - {'crf', 'rphc', 'bangrakam', 'pcc'}
    if bad_loaders:
        raise ValueError(f'Non-programme loader in programme mapping: {bad_loaders}')
    result = programme.copy()
    result['sender'] = mapped.map(lambda pair: pair[0])
    return result


def paired_change(data, pre, post, measure, unit):
    """Complete-pair estimate, keeping empty/singleton groups explicitly missing."""
    pairs = data[[pre, post]].dropna()
    n = len(pairs)
    row = {
        'measure': measure, 'unit': unit, 'n_group': len(data), 'n_pairs': n,
        'missing_pair': len(data) - n,
        'missing_pre_n': int(data[pre].isna().sum()),
        'missing_post_n': int(data[post].isna().sum()),
        'missing_both_n': int((data[pre].isna() & data[post].isna()).sum()),
        'definition': 'At 6 months', 'tiers': tier_mix(data.loc[pairs.index], post),
        'pre_mean': None, 'pre_sd': None, 'post_mean': None, 'post_sd': None,
        'mean_change': None, 'lo95': None, 'hi95': None, 'cohen_dz': None,
    }
    if not n:
        return row
    a, b = pairs[pre].to_numpy(float), pairs[post].to_numpy(float)
    diff = b - a
    row.update(pre_mean=a.mean(), post_mean=b.mean(), mean_change=diff.mean())
    if n > 1:
        sd = diff.std(ddof=1)
        half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
        row.update(pre_sd=a.std(ddof=1), post_sd=b.std(ddof=1),
                   lo95=diff.mean() - half, hi95=diff.mean() + half,
                   cohen_dz=diff.mean() / sd if sd else None)
    return row


def group_masks(data):
    gt = data.hba1c_pre.gt(6.5)
    le = data.hba1c_pre.le(6.5)
    untreated = data.on_any_pre.eq(0)
    g1 = untreated & gt
    g2 = data.on_any_pre.eq(1) & data.hba1c_pre.ge(6.5)
    g3 = data.on_any_pre.eq(1) & data.hba1c_pre.lt(6.5)
    clinical = [
        ('overall', 'all', pd.Series(True, index=data.index), 'Programme cohort'),
        ('baseline_hba1c', 'gt65', gt, 'Baseline HbA1c > 6.5%'),
        ('baseline_hba1c', 'le65', le, 'Baseline HbA1c ≤ 6.5%'),
        ('subgroup', 'g1', g1, 'No glucose-lowering drug at baseline AND baseline HbA1c > 6.5%'),
        ('subgroup', 'g2', g2, 'On glucose-lowering medication at baseline AND baseline HbA1c ≥ 6.5%'),
        ('subgroup', 'g3', g3, 'On glucose-lowering medication at baseline AND baseline HbA1c < 6.5%'),
        ('g2_insulin', 'insulin', g2 & data.on_insulin_pre.eq(1), 'G2 using insulin at baseline, with or without oral medication'),
        ('g2_insulin', 'non_insulin', g2 & data.on_insulin_pre.eq(0), 'G2 not using insulin at baseline'),
    ]
    missing = [
        ('baseline_hba1c', 'missing', data.hba1c_pre.isna(), 'Baseline HbA1c missing; excluded from the two HbA1c strata'),
        ('g2_insulin', 'missing', g2 & data.on_insulin_pre.isna(), 'G2 baseline insulin status missing; not assigned to non-insulin'),
        ('subgroup', 'unclassified', ~(g1 | g2 | g3), 'Outside the displayed group definitions or missing baseline data'),
        ('subgroup_exclusions', 'missing_medication', data.on_any_pre.isna(), 'Baseline medication unknown'),
        ('subgroup_exclusions', 'treated_missing_hba1c', data.on_any_pre.eq(1) & data.hba1c_pre.isna(), 'On medication but baseline HbA1c missing'),
        ('subgroup_exclusions', 'untreated_le65', untreated & le, 'Baseline drug-naive with HbA1c ≤ 6.5%; excluded from revised G1'),
        ('subgroup_exclusions', 'untreated_missing_hba1c', untreated & data.hba1c_pre.isna(), 'Baseline drug-naive with HbA1c missing; excluded from revised G1'),
    ]
    return clinical, missing


def remission_rows(data):
    valid = data.med_outcome_valid.eq(True)
    treated = data.on_any_pre.eq(1)
    med_eligible = treated & data.on_any_m6.notna() & valid
    if not med_eligible.equals(data.drug_stop_m6_eligible):
        raise ValueError('Cessation eligibility differs from the notebook.')
    stoppers = med_eligible & data.on_any_m6.eq(0)
    all_paired = data.on_any_m6.notna() & data.hba1c_m6.notna() & valid
    if not all_paired.equals(data.remission_m6.notna()):
        raise ValueError('Historical remission eligibility differs from the notebook.')
    controlled_off = data.on_any_m6.eq(0) & data.hba1c_m6.lt(6.5)
    definitions = [
        ('stopped_controlled', med_eligible & data.hba1c_m6.notna(), treated,
         'Baseline-medicated patients who stopped all glucose-lowering drugs and had HbA1c < 6.5% at 6 months; denominator has both follow-up values'),
        ('among_stoppers', stoppers & data.hba1c_m6.notna(), stoppers,
         'HbA1c < 6.5% among baseline-medicated patients who stopped all drugs at 6 months and had follow-up HbA1c'),
        ('all_off_drug_proxy', all_paired, pd.Series(True, index=data.index),
         'Historical notebook proxy: off all drugs and HbA1c < 6.5% at 6 months, irrespective of baseline medication use'),
    ]
    rows = []
    for group, denominator, population, definition in definitions:
        rows.append({
            'group': group, 'definition': definition,
            **rate(int((denominator & controlled_off).sum()), int(denominator.sum())),
            'n_population': int(population.sum()),
            'n_missing': int((population & ~denominator).sum()),
            'n_baseline_medicated': int(treated.sum()),
            'eligible_medication_n': int((population & data.on_any_m6.notna() & valid).sum()),
            'missing_hba1c_n': int((population & data.on_any_m6.notna() & valid & data.hba1c_m6.isna()).sum()),
            'missing_medication_n': int((population & ~(data.on_any_m6.notna() & valid)).sum()),
            'stopped_total_n': int(stoppers.sum()),
            'stopped_missing_hba1c_n': int((stoppers & data.hba1c_m6.isna()).sum()),
            'tiers_hba1c': tier_mix(data[denominator], 'hba1c_m6'),
            'tiers_medication': tier_mix(data[denominator], 'on_any_m6'),
        })
    return rows


def assert_close(actual, expected, label):
    if not np.isclose(actual, expected, rtol=1e-10, atol=1e-10, equal_nan=True):
        raise ValueError(f'Reconciliation failed: {label}: {actual} != {expected}')


def validate_totals(prog, tables, outputs):
    """The sender partition must exactly recover each existing global analysis."""
    changes = pd.DataFrame(outputs['table27_sender_clinical_m6.csv'])
    strata = pd.read_csv(tables / 'table22_clinical_strata_m6.csv')
    overall = pd.read_csv(tables / 'table2_paired_change.csv')
    overall = overall[overall.definition.eq('At 6 months')].assign(dimension='overall', group='all')
    global_masks = {(dimension, group): mask
                    for dimension, group, mask, _ in group_masks(prog)[0]}
    measure_specs = {spec[2]: spec for spec in MEASURES}
    for row in pd.concat([overall, strata]).to_dict('records'):
        recalculated = paired_change(prog[global_masks[(row['dimension'], row['group'])]],
                                     *measure_specs[row['measure']])
        for key in ['n_pairs', 'pre_mean', 'post_mean', 'mean_change', 'lo95', 'hi95']:
            assert_close(recalculated[key], row[key], f'Global {row["group"]}/{row["measure"]} {key}')
        subset = changes[(changes.dimension == row['dimension'])
                         & (changes.group == row['group'])
                         & (changes.measure == row['measure'])]
        n = subset.n_pairs.sum()
        assert_close(n, row['n_pairs'], f'{row["dimension"]}/{row["group"]}/{row["measure"]} pairs')
        for key in ['pre_mean', 'post_mean', 'mean_change']:
            assert_close((subset[key] * subset.n_pairs).sum() / n, row[key], key)
        # All strata also carry exact missingness; no denominators are lost.
        if row['dimension'] != 'overall':
            for key in ['n_group', 'missing_pair', 'missing_pre_n', 'missing_post_n', 'missing_both_n']:
                assert_close(subset[key].sum(), row[key], key)

    outcomes = pd.DataFrame(outputs['table26_sender_outcomes_m6.csv'])
    original = pd.read_csv(tables / 'table4_outcome_rates.csv')
    for _, name in OUTCOMES:
        expected = original[(original.cohort == 'Programme') & (original.outcome == name)].iloc[0]
        selected = outcomes[outcomes.outcome == name]
        for key in ['n', 'events']:
            assert_close(selected[key].sum(), expected[key], name + ' ' + key)

    remission = pd.DataFrame(outputs['table28_sender_remission_m6.csv'])
    for row in pd.read_csv(tables / 'table23_remission_detail_m6.csv').to_dict('records'):
        selected = remission[remission.group == row['group']]
        for key in ['events', 'n', 'n_population', 'n_missing', 'n_baseline_medicated',
                    'eligible_medication_n', 'missing_hba1c_n', 'missing_medication_n',
                    'stopped_total_n', 'stopped_missing_hba1c_n']:
            assert_close(selected[key].sum(), row[key], row['group'] + ' ' + key)

    meta = pd.DataFrame(outputs['table29_sender_group_metadata.csv'])
    for row in pd.read_csv(tables / 'table24_presentation_group_metadata.csv').to_dict('records'):
        selected = meta[(meta.dimension == row['dimension']) & (meta.group == row['group'])]
        for key in ['n_group', 'hba1c_gt65_n', 'hba1c_eq65_n', 'hba1c_lt65_n',
                    'hba1c_missing_n', 'insulin_n', 'non_insulin_n', 'insulin_missing_n']:
            assert_close(selected[key].sum(), row[key], row['group'] + ' ' + key)
    assert_close(sum(row['n_group'] for row in outputs['table25_sender_metadata.csv']), len(prog), 'programme cohort')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis-root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.analysis_root.resolve()
    tables = root / 'outputs' / 'tables'
    master = pd.read_csv(root / 'data' / 'processed' / 'dmr_master.csv', low_memory=False)
    prog = master[master.cohort.eq('program')].copy()
    if len(prog) != 995:
        raise ValueError('Programme cohort differs from notebook n=995; review before rebuilding.')
    for column in ['on_any_pre', 'on_any_m6', 'on_insulin_pre']:
        if not set(prog[column].dropna().unique()).issubset({0, 1}):
            raise ValueError(f'Unexpected coding in {column}')
    prog = assign_senders(prog, pd.read_csv(root / 'data' / 'case_report' / '_filename_map.csv'))
    outputs = {name: [] for name in [
        'table25_sender_metadata.csv', 'table26_sender_outcomes_m6.csv',
        'table27_sender_clinical_m6.csv', 'table28_sender_remission_m6.csv',
        'table29_sender_group_metadata.csv',
    ]}
    for sender, data in prog.groupby('sender', sort=True):
        overall_meta = metadata(data, 'overall', 'all', 'Programme cohort grouped by file sender')
        outputs['table25_sender_metadata.csv'].append({
            'sender': sender, **overall_meta,
            'facility_count': int(data.facility.nunique()),
            'source_file_count': int(data.source_file.nunique()),
            'baseline_medicated_n': int(data.on_any_pre.eq(1).sum()),
            'baseline_untreated_n': int(data.on_any_pre.eq(0).sum()),
            'baseline_medication_missing_n': int(data.on_any_pre.isna().sum()),
        })
        for column, label in OUTCOMES:
            observed = data[column].dropna()
            population = int(data.on_any_pre.eq(1).sum()) if column == 'drug_stopped_m6' else len(data)
            outputs['table26_sender_outcomes_m6.csv'].append({
                'sender': sender, 'cohort': 'Programme', 'outcome': label,
                **rate(int(observed.eq(1).sum()), len(observed)),
                'n_population': population, 'n_missing': population - len(observed),
            })
        clinical, missing = group_masks(data)
        for dimension, group, mask, definition in clinical + missing:
            outputs['table29_sender_group_metadata.csv'].append({
                'sender': sender, **metadata(data[mask], dimension, group, definition),
            })
        for dimension, group, mask, _ in clinical:
            for spec in MEASURES:
                outputs['table27_sender_clinical_m6.csv'].append({
                    'sender': sender, 'dimension': dimension, 'group': group,
                    **paired_change(data[mask], *spec),
                })
        for row in remission_rows(data):
            outputs['table28_sender_remission_m6.csv'].append({'sender': sender, **row})
    validate_totals(prog, tables, outputs)
    for filename, rows in outputs.items():
        pd.DataFrame(rows).to_csv(tables / filename, index=False)
        print(f'Wrote {filename}: {len(rows)} aggregate rows.')
    print(f'Mapped all {len(prog)} programme participants and {prog.source_file.nunique()} files to {prog.sender.nunique()} senders.')
    print('Reconciled all existing outcome counts, clinical strata and group missingness; no individual records exported.')


if __name__ == '__main__':
    main()
