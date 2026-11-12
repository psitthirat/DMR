"""Registry cost pairs behind table14 (notebook 02 cell 99). Aggregates only.

Run: <DMR>/.venv/bin/python -B -I cost_pairs.py <DMR root>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

m = pd.read_csv(Path(sys.argv[1]) / "data/processed/dmr_master.csv", low_memory=False)
reg = m[m.cohort == "registry"]
cs = reg[(reg.drug_stop_eligible == True) & reg.drug_stopped.notna()].copy()  # noqa: E712
cs["group"] = np.where(cs.drug_stopped == 1, "Stopped all drugs", "Still on drugs")
for g, d in cs.groupby("group"):
    print(g, "| n", len(d),
          "| drug cost pairs", int(d[["drugcost_pre", "drugcost_post"]].notna().all(axis=1).sum()),
          "| lab cost pairs", int(d[["labcost_pre", "labcost_post"]].notna().all(axis=1).sum()))
