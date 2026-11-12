# Tha Wung G3 by medication status at 6 months, 2026-11-11

Work behind "ผลรันเพิ่ม ท่าวุ้ง G3" in section 7 of the vault note
`01 Project/01 Research/DMR/DMR Open Questions from Repo 2026-11-08.md`
(Percy chose option ข on 11 Nov 20:11).

It reads `~/Desktop/HPSR_QUANTI/DMR` in its state after the final 11 Nov rerun
(master sha256 = `story/data/evidence.json`, all analysis files = `../2026-11-11 rerun/out/sha256_after.txt`)
and writes nothing there: `out/sha256_before.txt` and `out/sha256_after.txt` hash every
`DMR/` file (without `.venv`) around the run and are identical.

Definitions come from the repo itself (imported, not copied):
- sender: `story/scripts/derive_sender_tables.py` `assign_senders`
- G3: `group_masks` (on drug at baseline AND baseline HbA1c < 6.5%)
- stopped / on drug: `drug_stop_m6_eligible` and `drug_stopped_m6`, the report's cessation
  indicator (insulin and other glucose-lowering drugs count as drug use); unknown = baseline
  on drug but no valid 6-month drug status
- change: `paired_change` (complete pairs, paired-t 95% CI); differences between groups
  are Welch 95% CIs on the per-person change

The script first reconciles with the repo tables (G3 229, Tha Wung G3 163 in table29;
Tha Wung cessation 24/252 in table26; Tha Wung G3 changes in table27) and stops if any differ.

Output is aggregate only. Any group or pair count of 1–4 is printed as `<5` with no estimate.

```bash
~/Desktop/HPSR_QUANTI/DMR/.venv/bin/python -B -I scripts/thawung_g3_by_cessation.py ~/Desktop/HPSR_QUANTI/DMR > out/thawung_g3_by_cessation.txt
```
