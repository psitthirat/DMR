# DM Remission — interactive policy story

Discussion draft: 15 Thai storytelling slides in dark and light pink-coral themes, drawing on
the analysis notebook and `outputs/reports/(draft) policy recommendation.docx`.
Page geometry, typography and navigation follow the author's HRH-model site:
the same 68 px header and pill-shaped modes, scrolling reading layout, large
unframed figures, and a presentation evidence ribbon. The UI accent is coral.

## Preview

From this repository's root (the `story/` directory in the private analysis workspace):

```sh
python3 -m http.server 4173 --bind 127.0.0.1
```

Open **http://localhost:4173**. No build step, npm packages, or external runtime
requests are required. When working in the private analysis workspace, serve
only `story/`; its parent contains patient records and should not be the web root.

## Publication

Website: <https://psitthirat.github.io/DMR/>

Repository: <https://github.com/psitthirat/DMR>

GitHub Pages publishes the root of the `main` branch. `.nojekyll` keeps the
static files unchanged. Pushes to `main` update the website automatically.
This repository contains the presentation and aggregate data only; the source
notebooks, patient records, and policy Word document remain in the private
analysis workspace. Source paths in figures identify that workspace's files.

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

Rebuild the aggregate bundle after refreshing the notebook output tables in the
private analysis workspace. First derive the added clinical strata and joint
outcome tables using the analysis environment (pandas, NumPy and SciPy), then
rebuild the public aggregate bundle:

```sh
/path/to/private/DMR/.venv/bin/python scripts/derive_additional_tables.py --analysis-root /path/to/private/DMR
python3 scripts/build_data.py --analysis-root /path/to/private/DMR
```

`data/evidence.json` records source table paths and SHA-256 hashes. No patient
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

The additional outcome slide distinguishes **50/680 (7.4%)** who stopped all
glucose-lowering drugs and had HbA1c <6.5% from the historical **73/790 (9.2%)**
off-drug proxy, which includes people untreated at baseline. A conditional
view shows **50/95 (52.6%)** among stoppers with follow-up HbA1c; one of the 96
stoppers has no follow-up HbA1c. None confirms remission because the cessation
date needed to verify at least three months off medication is unavailable.

Clinical views retain the overall paired results and add baseline HbA1c
**>6.5% / ≤6.5%** strata (660/308 patients; 27 missing baseline HbA1c), with
metric-specific complete pairs and paired t 95% intervals. The comparison uses
one vertical scale and reports the unadjusted difference in mean changes.

At the author's request, G1 now requires no medication at baseline **and HbA1c
>6.5%** (89 patients). G2 retains medication use and HbA1c **≥6.5%** (564); G3
retains medication use and HbA1c **<6.5%** (229). These definitions differ from
the separate clinical HbA1c strata at exactly 6.5%. The remaining 113 patients
are outside the displayed definitions or lack classification data. G2 can be
split into no baseline insulin (537) and baseline insulin (27), with no unknown
insulin status within G2. Labels expose definitions by hover, keyboard focus or
tap. Original notebook subgroup tables remain unchanged; the revised groups
are recomputed in the extension script and included as new aggregate tables.

Fonts: Prompt Regular, Medium and SemiBold, distributed under the SIL Open Font License
in `assets/fonts/OFL.txt`. Downloaded from the author's HRH-model site.

## Files

`index.html`, `styles.css`, `app.js`: layout, navigation, controls, source dialog.
`slides.js`, `charts.js`: narrative and SVG figures.
`presentation.js`: current-result headlines, summary tables and evidence metadata.
`cover.js`: the cover and its matching downloadable SVG composition.
`export.js`: self-contained SVG and PNG export with Thai text.
`scripts/build_data.py`: aggregate data bundle generation.
`scripts/derive_additional_tables.py`: reproduce the clinical strata, revised
groups, and joint medication/HbA1c outcomes from the private cleaned master;
validate against published overall notebook results before writing aggregates.
