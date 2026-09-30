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
