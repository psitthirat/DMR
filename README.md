# DM Remission — interactive policy story

Discussion draft: 15 Thai storytelling slides in dark and light pink-coral themes, drawing on
the analysis notebook and `outputs/reports/(draft) policy recommendation.docx`.
Page geometry, typography and navigation follow the author's HRH-model site:
the same 68 px header and pill-shaped modes, scrolling reading layout, large
unframed figures, and a presentation evidence ribbon. The UI accent is coral.

## Repository

Since 12 Nov 2026 this one repository holds both the analysis and the website,
so a rerun and its published figures stay in step without syncing two repos.

| Path | Content |
|---|---|
| `src/` | ETL and parsers that combine the 24 site workbooks into one coded dataset |
| `notebooks/` | `01_combine_data` and `02_analysis_effectiveness` (committed without outputs) |
| `tools/` | pipeline runner, website bundle builders, reproducibility and data-safety checks |
| `checks/` | one-off aggregate analyses cited in the HSRI report (open questions of 8 Nov, Tha Wung G3, HbA1c < 6.5% by sender) |
| `reproducibility/` | SHA-256 baselines of inputs and outputs for each machine that reran the analysis |
| `docs/` | the published website; `docs/data/evidence.json` is the only data it reads |
| `ANALYSIS.md` | analysis notes: data sources, loaders, definitions and the decisions behind them |
| `data/` | **not in git**: a symlink to `../DMR-data`, the coded case-report files |
| `outputs/` | **not in git**: tables, figures and executed notebooks written by a run |

## Data

The analysis uses case-report workbooks submitted by the participating sites
(ethics approval COA. MURA2026/200, Mahidol University Faculty of Medicine
Ramathibodi Hospital). They are patient records and are not shared: they stay
outside this repository with the research team. Identifiers were replaced by
codes before the analysis moved machines on 12 Nov 2026 (names kept only as a
courtesy title + code so sex can still be derived; HN, ID and participant codes
tokenised; phone and address blanked; all other cells unchanged). The key to the
codes is held separately. Only aggregate tables leave the analysis, through
`tools/build_data.py` into `docs/data/evidence.json`.

## Reproduce the analysis

With the coded data in `../DMR-data/` (`case_report/` and `corrections/`):

```sh
ln -s ../DMR-data data                      # once per clone; git ignores it
uv python install 3.13.2
uv venv --python 3.13.2 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt
python3 tools/check_baseline.py --inputs    # the data files match the baseline
zsh tools/run_pipeline.sh                   # ETL → notebooks 01, 02 → derive → build_data (~80 s)
.venv/bin/python tools/check_baseline.py    # expect ALL MATCH
sh tools/install_hooks.sh                   # pre-commit data-safety check, once per clone
```

`reproducibility/baseline.json` was recorded on the rama-hpsr Mac (Apple Silicon,
Python 3.13.2, packages in `requirements.lock.txt`); two runs there were identical
byte for byte. `reproducibility/baseline_p.sitthirat_20261112.json` is the run on
the machine that held the data before: the run here matched 32 of its 39 output
files byte for byte; the six model tables (GEE, LMM, sensitivity) and the bundle
that hashes them differed only in the 13th significant digit (relative difference
at most 3.9e-13). Since then table26 gained HbA1c < 6.5% rows by sender (12 Nov
2026, level 3 of report section 7.2), so it and the bundle differ from that older
baseline by design. On 13 Nov 2026 G2/G3 moved to the >6.5% / ≤6.5% split
(27 patients on medication with baseline HbA1c exactly 6.5% moved from G2 to
G3), which changed tables 18–22, 24, 27 and 29; `baseline.json` was re-recorded
after that run.
Multiple imputation is seeded (`np.random.seed(20261112)` in notebook 02).
Compare two runs number by number with `tools/compare_runs.py`.

## Preview

The website lives in `docs/`. Serve that folder only:

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory docs
```

Open **http://localhost:4173**. No build step, npm packages, or external runtime
requests are required. Never serve the repository root: in a working clone,
`data/` links to the coded analysis data.

## Publication

Website: <https://psitthirat.github.io/DMR/>

Repository: <https://github.com/psitthirat/DMR>

GitHub Actions (`.github/workflows/pages.yml`) publishes only `docs/` to GitHub
Pages on every push to `main`, after `tools/precommit_check.py` passes again on
GitHub; `check.yml` runs the same check on other branches and pull requests.
Every commit also passes the check locally as a git pre-commit hook. No patient
records are in this repository: data stay outside it, and only aggregate tables
reach `docs/data/evidence.json`. Source paths in figures name the analysis files.

## Interaction

- Reading mode opens with an introduction, followed by scrolling narrative and
  a sticky figure. On mobile, each scene has its own inline figure.
- Presentation mode puts the figure on the left and the interpretation and
  summary table on the right. Use arrow keys / Space to navigate, F for
  fullscreen, E to explore, or the question-mark menu for the contents.
- Exploration mode exposes each figure's controls and source rows. Return to
  presentation or reading with those selections preserved. The URL preserves
  the active scene, controls, mode, display theme, and export background.
- The sun/moon button switches the display theme in all three modes. Downloads
  follow the display theme by default; the export drawer can override it.
- The clinical figure has group buttons directly above it in reading and
  presentation modes: overall, compare both baseline HbA1c strata, >6.5%, and
  ≤6.5%. These update the chart, interpretation, URL and downloaded image;
  the same selection appears when opening exploration mode.
- The subgroup figure also has inline buttons for G1–G3 or splitting G2 by
  baseline insulin use. G1's 89 patients are stated in the slide text; paired
  counts still depend on the selected clinical measure.
- The outcomes slide links directly to the following joint-outcome slide
  (7.2%), so it can be found without opening the contents menu.
- Outcomes, joint outcome, clinical change, and subgroup slides have a visible
  sender selector in every mode. A sender selection carries between these four
  slides and survives reloads. Other slides explicitly remain overall analyses.
  The comparison-by-site slide defaults to sender grouping, with a button to
  return to the original facility grouping.
- Every slide exports a 2,400-pixel-wide PNG or a vector SVG. Both include the
  current settings, chart title, caveats, source filenames, and embedded Prompt
  fonts. Dark and light export backgrounds are available.
- “ที่มาและวิธีคำนวณ” opens a side drawer with source rows and a CSV download.
- “ดาวน์โหลดภาพ” saves a PNG directly. The adjacent “⋯” button opens SVG export
  and background options.
- The expand icon beside the chart badge opens a larger figure; on phones the
  expanded figure scrolls horizontally so small labels remain readable.
- Responsive layout; keyboard access; reduced-motion support.

## Data and provenance

Rebuild the aggregate bundle after refreshing the notebook output tables in
`outputs/tables/`. First derive the added clinical strata and joint outcome
tables using the analysis environment (pandas, NumPy and SciPy), then rebuild
the public aggregate bundle:

```sh
.venv/bin/python tools/derive_additional_tables.py
.venv/bin/python tools/derive_sender_tables.py
python3 tools/build_data.py
```

`docs/data/evidence.json` records source table paths and SHA-256 hashes. No patient
records are copied into this directory. Cohort counts and qualitative context
are transcribed from the notebook, repository README, and policy draft, and
should be reviewed when those sources change. Narrative text, policy summaries,
and suggested implementation sequencing are maintained in `slides.js` and
`charts.js`; the final two diagrams are explicitly labelled as synthesis.

The prototype does not recompute fitted models or treat display choices as new
analyses. It preserves the original denominators, timing tiers, and distinctions
between cessation, the remission upper bound, and HbA1c control. Cost means use
available observations in each period; paired changes come from the separate
change columns and cannot be replaced by subtracting the period means.

The additional outcome slide distinguishes **50/692 (7.2%)** who stopped all
glucose-lowering drugs and had HbA1c <6.5% from the historical **74/803 (9.2%)**
off-drug proxy, which includes people untreated at baseline. A conditional
view shows **50/96 (52.1%)** among stoppers with follow-up HbA1c; one of the 97
stoppers has no follow-up HbA1c. None confirms remission because the cessation
date needed to verify at least three months off medication is unavailable.

Clinical views retain the overall paired results and add baseline HbA1c
**>6.5% / ≤6.5%** strata (660/308 patients; 27 missing baseline HbA1c), with
metric-specific complete pairs and paired t 95% intervals. The comparison uses
one vertical scale and reports the unadjusted difference in mean changes.

At the author's request, G1 now requires no medication at baseline **and HbA1c
>6.5%** (89 patients). G2 is medication use and HbA1c **>6.5%** (537); G3 is
medication use and HbA1c **≤6.5%** (256), the same split at exactly 6.5% as the
clinical HbA1c strata (author's decision, 13 Nov 2026; before that, exactly 6.5%
belonged to G2: 564 and 229). The remaining 113 patients
are outside the displayed definitions or lack classification data. G2 can be
split into no baseline insulin (511) and baseline insulin (26), with no unknown
insulin status within G2. Labels expose definitions by hover, keyboard focus or
tap. Original notebook subgroup tables remain unchanged; the revised groups
are recomputed in the extension script and included as new aggregate tables.

Sender breakdowns join the cleaned master's `source_file` to `new_filename`
(with original-name fallback) in `data/case_report/_filename_map.csv`, then
use its `sender` column. Ambiguous or unmatched mappings fail the build. The
995-person programme cohort maps to eight senders; กระนวน includes 13 facilities,
เพชรบูรณ์ includes PCC คลองศาลา, and หูแร่ uses records retained after deduplication.
บ้านตาขุน is registry-only and the กระนวน survey is a separate cohort, so neither
is mixed into the programme sender estimates. The map has nine senders across
all source cohorts. Only aggregate tables and source hashes enter the website.

All sender results retain the original six-month outcome definitions and
metric-specific complete-pair denominators. Estimates with no eligible patients
or no complete pairs are shown as unavailable, never as zero. A single complete
pair has a descriptive mean change but no confidence interval; two or more
pairs use the paired t interval. Group tooltip counts and export annotations
follow the selected sender. The derivation reconciles counts and weighted
estimates against the original overall results before writing the tables.

Fonts: Prompt Regular, Medium and SemiBold, distributed under the SIL Open Font License
in `assets/fonts/OFL.txt`. Downloaded from the author's HRH-model site.

## Files

Website (`docs/`):
`index.html`, `styles.css`, `app.js`: layout, navigation, controls, source dialog.
`slides.js`, `charts.js`: narrative and SVG figures.
`presentation.js`: current-result headlines, summary tables and evidence metadata.
`cover.js`: the cover and its matching downloadable SVG composition.
`export.js`: self-contained SVG and PNG export with Thai text.
`data/evidence.json`: the aggregate bundle the site reads.

Tools (`tools/`):
`build_data.py`: aggregate data bundle generation.
`derive_additional_tables.py`: reproduce the clinical strata, revised
groups, and joint medication/HbA1c outcomes from the private cleaned master;
validate against published overall notebook results before writing aggregates.
`derive_sender_tables.py`: map and aggregate programme results by sender,
including missing-data accounting and reconciliation with overall results.
`precommit_check.py`: blocks data files, data folders, notebooks with outputs and
bare 13-digit numbers; runs as a git pre-commit hook (`sh tools/install_hooks.sh`)
and in GitHub Actions before every publish.
