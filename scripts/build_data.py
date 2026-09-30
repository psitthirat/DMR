"""Create the presentation bundle from aggregate notebook outputs only.

Run in the analysis workspace: python3 story/scripts/build_data.py
Or from a standalone clone: python3 scripts/build_data.py --analysis-root /path/to/DMR
No patient records are copied into the web directory.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--analysis-root', type=Path, default=SITE.parent,
                    help='Private analysis workspace containing outputs/tables/')
args = parser.parse_args()
ROOT = args.analysis_root.resolve()
if not (ROOT / 'outputs' / 'tables').is_dir():
    parser.error('Provide --analysis-root pointing to the private analysis workspace. '
                 'The public repository contains the generated aggregate bundle only.')
TABLES = {
    'changes': 'table2_paired_change.csv',
    'outcomes': 'table4_outcome_rates.csv',
    'sites': 'table5_cessation_by_site.csv',
    'models': 'table7_multivariable_gee.csv',
    'costs': 'table14_cost_by_cessation.csv',
    'comparison': 'table16_between_cohort_difference.csv',
    'timing': 'table15_timing_coverage.csv',
    'subgroups': 'table19_subgroup_outcomes.csv',
    'providers': 'table17b_cessation_by_provider_level.csv',
    'providers_crf': 'table17c_provider_level_within_crf.csv',
    'clinical_strata': 'table22_clinical_strata_m6.csv',
    'remission_detail': 'table23_remission_detail_m6.csv',
    'group_metadata': 'table24_presentation_group_metadata.csv',
    'sender_meta': 'table25_sender_metadata.csv',
    'sender_outcomes': 'table26_sender_outcomes_m6.csv',
    'sender_changes': 'table27_sender_clinical_m6.csv',
    'sender_remission': 'table28_sender_remission_m6.csv',
    'sender_group_metadata': 'table29_sender_group_metadata.csv',
}


def value(s):
    if s == '':
        return None
    try:
        return float(s)
    except ValueError:
        return s


bundle = {'tables': {}, 'sources': {}, 'meta': {
    'title': 'DM Remission · Evidence to policy',
    'notebook': 'notebooks/02_analysis_effectiveness.ipynb',
    'policy': 'outputs/reports/(draft) policy recommendation.docx',
    'status': 'Discussion draft',
    'cohorts': {'programme': 995, 'registry': 1461, 'survey': 214},
    'qualitative': {'sites': 9, 'participants': 89, 'staff': 58, 'patients': 31},
    'additional_analysis': {
        'script': 'scripts/derive_additional_tables.py',
        'cohort': 'Programme cohort, n=995; same cleaned master as the notebook',
        'anchor': 'At 6 months, all timing tiers; complete pairs for each clinical measure',
        'clinical_intervals': 'Paired mean change with 95% Student t interval',
        'rate_intervals': 'Wilson 95% interval; missing outcomes excluded, not imputed',
        'baseline_hba1c': 'Two strata: >6.5% versus ≤6.5%; 27 missing baseline HbA1c excluded',
        'g1_revision': 'G1 now requires no baseline glucose-lowering drug AND HbA1c >6.5% (89). Notebook G1 included all 114 drug-naive patients; 21 with HbA1c ≤6.5% and 4 missing are excluded from the revised G1.',
        'g2': 'On glucose-lowering medication at baseline AND HbA1c ≥6.5% (564)',
        'g3': 'On glucose-lowering medication at baseline AND HbA1c <6.5% (229)',
        'subgroup_exclusions': '113 outside the displayed groups or missing baseline data; not all 113 are missing data',
        'insulin_split': 'G2 baseline insulin use: 27 using, 537 not using, 0 missing. Insulin use may include oral medication.',
        'remission': 'Stop dates are unavailable: the HbA1c measurement cannot be verified as at least 3 months after drug cessation. These are joint outcome proxies, not confirmed remission.',
    },
    'sender_analysis': {
        'script': 'scripts/derive_sender_tables.py',
        'mapping': 'data/case_report/_filename_map.csv',
        'mapping_sha256': hashlib.sha256((ROOT / 'data/case_report/_filename_map.csv').read_bytes()).hexdigest(),
        'master': 'data/processed/dmr_master.csv',
        'master_sha256': hashlib.sha256((ROOT / 'data/processed/dmr_master.csv').read_bytes()).hexdigest(),
        'grouping': 'The programme master source_file joins to new_filename or original_filename; aggregate by the mapping sender, not facility or source_family.',
        'scope': 'Programme cohort only, n=995, 21 retained source files, 8 senders; all records mapped. Registry n=1461 and survey n=214 remain excluded.',
        'interpretation': 'Sender may cover several treating facilities. These are descriptive within-programme comparisons; case mix, completeness and timing differ across senders.',
        'anchor': 'At 6 months, all timing tiers; same outcome eligibility and complete-pair definitions as the overall slides.',
        'reconciliation': 'Sender event counts, denominators, group counts and missingness sum to the overall tables. Clinical means and changes reproduce overall estimates when weighted by complete-pair counts.',
        'small_groups': 'n=0: means, rates and intervals are null. n=1: paired means and change are shown without a confidence interval. n≥2: paired 95% Student t interval. Counts and missingness are always retained.',
        'rate_intervals': 'Wilson 95% interval. Missing outcomes are excluded from denominators, not imputed as failures.',
        'remission': 'Joint cessation and HbA1c <6.5% is not confirmed remission: no stop dates establish at least 3 months without medication before HbA1c measurement.',
    },
}}
for key, filename in TABLES.items():
    path = ROOT / 'outputs' / 'tables' / filename
    with path.open(encoding='utf-8-sig', newline='') as f:
        bundle['tables'][key] = [{k: value(v) for k, v in r.items()} for r in csv.DictReader(f)]
    bundle['sources'][key] = {
        'file': 'outputs/tables/' + filename,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    }
dest = SITE / 'data' / 'evidence.json'
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + '\n')
print(f'Wrote {dest.name}: {len(TABLES)} aggregate tables, no patient records.')
