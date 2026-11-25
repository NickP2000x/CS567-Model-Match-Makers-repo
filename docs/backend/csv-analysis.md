# Local descriptive analysis of exported CSVs

`scripts/analyze_csv.py` reads one private CSV export and writes descriptive
summaries and draft paper tables. It uses only the Python standard library
(Python 3.10 or newer). It does not import the app, load `.env`, open SQLite,
call models, run the oracle, or change routing thresholds.

## Run

From the repository root:

```bash
python3 scripts/analyze_csv.py \
  --input "/absolute/path/to/export-folder" \
  --output "/absolute/path/to/private-analysis-results"
```

Pass the folder containing `sessions.csv` and `tasks.csv`, not a parent containing
several exports. The source files stay unchanged. Each invocation creates a new
`analysis-<UTC timestamp>/` under the output parent. Existing results are preserved.
The output parent must be outside the source export folder.

If `--output` is omitted, results go under the Git-ignored
`backend/data/analysis/`. Keep private exports and results outside Git, including
when using a custom output path.

Development sessions are excluded by default. If actual collection used development
mode, first confirm the inclusion decision, then explicitly run:

```bash
python3 scripts/analyze_csv.py \
  --input "/absolute/path/to/export-folder" \
  --output "/absolute/path/to/private-analysis-results" \
  --include-development
```

The report records that choice. Do not mix test sessions with participant sessions
without reviewing which sessions belong in the dataset. The script does not offer
an interactive exclusion editor: prepare a consistent, separately documented input
snapshot when you need a different session inclusion set.

## Outputs

| File | Contents |
|---|---|
| `condition_summary.csv` | Per-condition sample size, mean, sample SD, median, Q1/Q3, range; binary event counts and rates |
| `paired_comparisons.csv` | Override minus Automatic differences for each participant with both nonmissing measures |
| `routing_summary.csv` | Pooled checkpoint counts, distinct override/change denominators, routing failures and oracle coverage |
| `data_quality_report.json` | Inclusion/exclusion counts, sequence balance, missing files, warnings, definitions, model/router settings and source hashes |
| `paper_tables.tex` | Separate LaTeX tables you can select and paste into Overleaf; no extra LaTeX packages required |
| `results_summary.md` | Neutral draft Results text, the analysis method, observed summaries and remaining review steps |

No participant IDs, Prolific IDs, demographics, message bodies, or feedback text
are copied into these outputs. The script uses identifiers internally for joins
and repeat-session checks. JSON reports retain model names, survey versions and
aggregate study metadata. Small aggregate groups can still be identifying; review
the results before publishing them.

The script creates **tables, not figure files**. A table satisfies the checkpoint
requirement for at least one figure or table. Select the relevant tables; do not
insert every supplemental metric into the paper.

## Inclusion and missing data

- Recorded consent must be true. Development status must be known. Practice,
  explicitly excluded tasks and unknown experimental task IDs are excluded.
- An ended task must be `submitted` or `timed-out` with valid start/end timestamps.
  Unfinished tasks are counted but do not supply final outcomes. A session can
  supply one valid condition without supplying a paired difference.
- Each session can supply at most one task per condition. Repeated participant
  identifiers across included sessions stop analysis. The identity key uses a
  recorded Prolific ID, then participant ID, then session ID. Confirm real unique
  participants independently; IDs cannot prove recruitment or eligibility.
- Required files: `sessions.csv` and `tasks.csv`. Optional files:
  `checkpoint_choices.csv`, `model_calls.csv`, `routing_decisions.csv`, and
  `oracle_results.csv`. Missing optional files are reported, not generated.
  Other files, including message and feedback datasets, are not read.
- A complete `manifest.json`, if present, must agree with the row counts of the
  files used. Source SHA-256 hashes are saved, and input changes during analysis
  cause an error. Use one frozen export, not concatenated snapshots.
- Identical duplicate rows are removed and counted. Conflicting identifiers stop
  analysis. Missing values use the export convention `\N`; zeros stay zeros.
- No eligible ended tasks produces diagnostic outputs and exit status 2. Other
  input errors also return 2. A usable descriptive run returns 0; this does not
  certify data quality. Review all warnings.

## Measures and interpretation

**Task outcomes.** Constraint counts and all-met outcomes use the saved definition.
Four-, five- and six-constraint records remain separate; no historical result is
rescored with the current catalog. Inconsistent saved totals are omitted and
flagged. Binary outcomes show events/total and a proportion (`0..1`) in CSV, with
percentages in the paper table.

**Time.** `elapsed_seconds` is final end minus initial start for submitted and
timed-out tasks. It measures time to task termination, not uncensored time to
successful completion. `submitted_elapsed_seconds` reports submitted tasks only.
Wall time spent between a submission and a later task reopening remains included;
the script does not subtract it. Report the timeout rate alongside task time.

**Workload.** Saved `survey_raw_score` values are used only for submitted surveys
with a recorded version. Different versions are not pooled or paired. When the
six answers and metadata are available, the script checks the scale, increments,
orientation (including performance), and saved mean. Mismatches are omitted.
Missing validation metadata is flagged. The script never guesses a performance
reversal. Describe the actual adapted survey in Method, not an unchanged standard
NASA-TLX instrument.

**Choices.** Rates use committed choices with known fields, not unvisited stages.
`override_recommendation_rate` compares final versus recommended choice.
`initial_choice_change_rate` compares final versus initial choice. These are
different behaviors. Override decision intervals are summarized as each
participant's mean over known, nonnegative intervals, then summarized across
participants. They are timestamp differences, not validated cognitive measures.

**Usage.** Only `purpose=participant` calls linked to included ended tasks supply
task usage measures. Failed and unshown calls are included because they can consume
resources. Oracle and unknown-purpose calls remain separate in the quality report.
Missing token counts make that task's token total unknown, not zero. If the call
file exists and a task has no calls, its call/token totals are zero. A missing call
file does not imply zero usage. Tokens are not converted to money.

**Oracle.** Only successful applied routes with an unambiguous checkpoint context
join to their exact `routing_id`. Checkpoints with neither model passing are
reported but excluded from preferred-size agreement. Missing results and malformed
labels are reported. Preferred-size agreement is not itself a validated measure
of appropriate reliance. Oracle evaluations do not judge conversation quality.

## Statistical method

The tool performs descriptive analysis only. It reports sample means and SDs,
medians, linearly interpolated quartiles (type 7), counts, and percentages.
Sample SD is unknown for fewer than two observations. Paired differences use
Override minus Automatic within the same participant, measure, and version.
Available-case condition summaries and paired sample sizes can therefore differ.

Participants, not checkpoints or tool calls, are the units for condition summaries.
Checkpoint rates are first calculated within each participant. Pooled counts in
`routing_summary.csv` are descriptive coverage counts, not independent samples.

There are no significance tests, p-values, confidence intervals or causal claims.
The generated prose is a draft, not an automatic interpretation. Before submission,
confirm participant counts, recruitment, exclusions, scenario/order balance,
collected model/router settings, survey/catalog versions, oracle coverage and the
actual procedure. Mixed models, thresholds, simulated behavior or versions require
researcher review. Earlier calibration does not validate the collected data.

## Verification

Run the standard-library synthetic checks from the repository root:

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_analyze_csv.py' -v
```

The tests use invented records and temporary folders. They check paired values,
quartiles, exclusions, missing data, timeout handling, version separation, workload
orientation, oracle linkage, usage separation, duplicate detection, source-byte
preservation, private-value omission and the actual CLI. They do not read private
participant files or require providers.
