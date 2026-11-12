"""§10 of `DMR Open Questions from Repo 2026-11-08` (12 Nov 2026): HbA1c < 6.5% at 6 months
by sender, beside the existing HbA1c < 7% column of table26, plus the Ban Ta Khun registry.

Same master, sender mapping, denominator (people with a 6-month HbA1c) and Wilson interval
as tools/derive_sender_tables.py. Aggregate output only.

Usage: .venv/bin/python -B checks/hba1c65_by_sender.py [--analysis-root ROOT]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--analysis-root', type=Path, default=Path(__file__).resolve().parents[1])
root = ap.parse_args().analysis_root.resolve()
sys.path.insert(0, str(root / 'tools'))
from derive_additional_tables import rate  # noqa: E402
from derive_sender_tables import assign_senders  # noqa: E402

master = pd.read_csv(root / 'data' / 'processed' / 'dmr_master.csv', low_memory=False)
prog = master[master.cohort.eq('program')].copy()
assert len(prog) == 995, len(prog)
prog = assign_senders(prog, pd.read_csv(root / 'data' / 'case_report' / '_filename_map.csv'))


def row(label, data):
    out = {'sender': label}
    for column, name in [('a1c_lt65_m6', 'lt65'), ('a1c_lt7_m6', 'lt7')]:
        observed = data[column].dropna()
        r = rate(int(observed.eq(1).sum()), len(observed))
        out.update({f'{name}_events': r['events'], f'{name}_n': r['n'], f'{name}_pct': r['pct'],
                    f'{name}_lo95': r['lo95'], f'{name}_hi95': r['hi95']})
    return out


rows = [row(sender, data) for sender, data in prog.groupby('sender', sort=True)]
rows.append(row('รวมกลุ่มโครงการ', prog))
cohorts = sorted(master.cohort.dropna().unique())
registry = [c for c in cohorts if c != 'program' and 'regist' in str(c).lower()]
for c in registry:
    rows.append(row(f'ทะเบียนบ้านตาขุน ({c})', master[master.cohort.eq(c)]))
table = pd.DataFrame(rows)

# Checks against the published tables (stop on any mismatch)
t4 = pd.read_csv(root / 'outputs' / 'tables' / 'table4_outcome_rates.csv')
t26 = pd.read_csv(root / 'outputs' / 'tables' / 'table26_sender_outcomes_m6.csv')
total = table[table.sender.eq('รวมกลุ่มโครงการ')].iloc[0]
assert (total.lt65_events, total.lt65_n) == (251, 872), (total.lt65_events, total.lt65_n)
assert (total.lt7_events, total.lt7_n) == (399, 872), (total.lt7_events, total.lt7_n)
lt7 = t26[t26.outcome.eq('HbA1c < 7% at 6 months')].set_index('sender')
for r in table[~table.sender.str.startswith(('รวม', 'ทะเบียน'))].itertuples():
    assert (r.lt7_events, r.lt7_n) == (lt7.loc[r.sender, 'events'], lt7.loc[r.sender, 'n']), r.sender
assert table[~table.sender.str.startswith(('รวม', 'ทะเบียน'))].lt65_events.sum() == 251
reg4 = t4[t4.cohort.eq('Registry')].set_index('outcome')
print('cohorts in master:', cohorts)
print('table4 registry: <7%', int(reg4.loc['HbA1c < 7% at 6 months', 'events']), '/',
      int(reg4.loc['HbA1c < 7% at 6 months', 'n']), '; <6.5%',
      int(reg4.loc['HbA1c < 6.5% at 6 months', 'events']), '/', int(reg4.loc['HbA1c < 6.5% at 6 months', 'n']))

pd.set_option('display.width', 250)
for r in table.itertuples():
    print(f"{r.sender} | <6.5%: {r.lt65_events}/{r.lt65_n} = {r.lt65_pct:.1f}% "
          f"({r.lt65_lo95:.1f}–{r.lt65_hi95:.1f}) | <7%: {r.lt7_events}/{r.lt7_n} = {r.lt7_pct:.1f}% "
          f"({r.lt7_lo95:.1f}–{r.lt7_hi95:.1f})")
print('checks passed: total 251/872 and 399/872; <7% by sender equals table26; sender <6.5% sums to 251')
