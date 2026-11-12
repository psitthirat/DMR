# DMR open questions, 2026-11-08

Scratch checks behind the vault note `DMR Open Questions from Repo 2026-11-08`
(`01 Project/01 Research/DMR/`). They read the frozen 30 Sep 2026 state of
`~/Desktop/HPSR_QUANTI/DMR` and write nothing there. Every output in `out/` is
aggregate: no patient rows, IDs or names, and facility-level cells of 0–4 are
shown as `<5` (complementary cells combined so they cannot be back-calculated).

Run each script with the repo's own Python (it has `xlrd` for the .xls files),
with `-B` so importing `DMR/src/` never writes `.pyc` files under `DMR/`:

```bash
~/Desktop/HPSR_QUANTI/DMR/.venv/bin/python -B -I scripts/dmr_open_questions.py ~/Desktop/HPSR_QUANTI/DMR
```

| Script | Answers | Output |
|---|---|---|
| `dmr_open_questions.py` | Q1–Q9 aggregates, GEE refit, provider-level sensitivity | `out/aggregates.txt` |
| `raw_inventory.py` | rows per workbook sheet, read or not by the loaders (Q1) | `out/raw_inventory.csv` |
| `skipped_rows.py` | what the 30 skipped รพ.สต. rows are (flags only) (Q1) | `out/skipped_rows.txt` |
| `form_headers.py` | column headers of every template layout (Q6) | `out/form_headers.txt` |
| `unread_columns.py` | หนองโน "การปรับยา" block; 2566 survey date fields (Q6, Q9) | `out/unread_columns.txt` |
| `enrol_timing.py` | enrolment window by sender against the 6-month anchor (Q3) | `out/enrol_timing.txt` |
| `cost_pairs.py` | registry cost pairs behind table14 (draft 4.2.7) | `out/cost_pairs.txt` |
| `dump_nb.py` | notebook code cells; outputs only for named cells | — |
| `read_docx.py` | draft text and Heimdall comments, read-only | — |

Check that `DMR/` is untouched: hash every file (excluding `.venv`) before and
after; on 2026-11-08 all 200 files matched.
