# Offline calibration and CSV export (#67–#68)

These are local researcher tools, not participant-facing endpoints or a statistical pipeline.
They preserve the four existing constraints and do not approve participant collection.

## Shell shortcuts (repository root)

After setup, use the backend virtual environment automatically:

```bash
bash scripts/export-csv.sh
bash scripts/calibrate.sh --dry-run
# Explicit real-call opt-in for a small initial check:
bash scripts/calibrate.sh --real --limit 2
```

The CSV wrapper defaults to `backend/data/model-matchmakers.sqlite3`. An explicit
`--database` overrides it, including when your configured `DATABASE_PATH` differs;
the wrapper never sources `.env`. Calibration still requires `--dry-run` or `--real`.
All options, help, and exit statuses are forwarded to the Python commands.

Both scripts work from another directory when invoked by absolute script path and
handle spaces in the checkout/path arguments. Custom relative paths are resolved
from `backend/`; use absolute paths to avoid ambiguity. Missing environments or
core calibration dependencies give setup guidance without installing packages.
The wrappers use Bash 3.2-compatible syntax for WSL/Linux/macOS; native PowerShell
can run the Python commands below directly.

For direct Python commands below, run from `backend/` with Python 3.12 and its
virtual environment active.

## Read the study database as CSV

```bash
python -m app.export_csv --database data/model-matchmakers.sqlite3
# Explicitly exclude development sessions and practice:
python -m app.export_csv --database data/model-matchmakers.sqlite3 --study-only
```

The default destination is a fresh `data/exports/export-<UTC timestamp>/` directory.
Use `--output <parent-directory>` to choose another parent. No prior export is
overwritten. Generated default exports are ignored by Git.

The exporter does **not** load `.env`, infer the configured database, initialize
SQLite, migrate its schema, or recompute stored survey/plan results. Supply the
correct database explicitly. It opens a single read-only transaction so concurrent
commits cannot mix records from different database snapshots.

### Files

| CSV | Row unit |
|---|---|
| `sessions.csv` | Session, with demographics, assignment, feedback, and mode flags |
| `preparations.csv` | Accepted acknowledgement/preparation record |
| `tasks.csv` | Reached task, saved plan/cost/constraints, six raw ratings, metadata and stored score |
| `plan_items.csv` | Selected venue/catering/supply item |
| `messages.csv` | Stored message, in original order |
| `checkpoint_choices.csv` | Reached checkpoint decision, including partial choices |
| `survey_responses.csv` | Actually answered workload dimension and its versioned metadata |
| `task_reopens.csv` | Recorded return to a submitted task |
| `inspections.csv` | Recorded inspected item; no inspection timestamp is invented |
| `routing_decisions.csv` | Routing attempt, including failures/unapplied decisions |
| `model_calls.csv` | Individual call, with recorded participant/oracle purpose |
| `oracle_results.csv` | Offline paired-output result, where present |
| `catalog_items.csv` | Current catalog reference data |

Join on `session_id`, then `(session_id, task_id)` and `checkpoint` as appropriate.
Oracle `routing_id` links to a routing record's `id`. The export also includes:

- `manifest.json`: version, source/export counts, current catalog version, filters,
  and missing-table/orphan-record warnings. `status=complete` is written last.
- `data_dictionary.json`: columns, units, join keys, and missing-value conventions.

CSV encoding is UTF-8 with BOM for spreadsheet compatibility. Quoting preserves
commas, quotes, Unicode and multiline text. **SQL/JSON null is `\N`; empty text
stays empty.** Source text beginning with a backslash gains one extra leading
backslash, so a literal `\N` is distinguishable and reversible. Import free-text
columns as text rather than spreadsheet formulas.

Raw timestamps remain epoch milliseconds; companion `_utc` columns are display
values. Derived elapsed seconds and choice intervals are explicitly named timestamp
differences, not approved reliance/decision-latency definitions. Negative differences
are not silently repaired. Raw ratings, stored workload scores, and stored orientation
are not transformed. Only reached decisions have rows; missing model choices remain null.

Default exports include development/practice and oracle calls, with flags/purpose
for filtering. `--study-only` includes only sessions explicitly marked non-development
and their non-excluded experimental tasks. Unknown session classification is excluded
by that filter. The catalog remains reference data. Earlier absent usage-purpose
columns stay unknown, not guessed; missing optional tables yield header-only files.
Orphan relational records are retained and reported in default exports.

Catalog names/prices describe the catalog currently present in the database, not
a reconstructed historical catalog. Use saved task costs/scores for past outcomes.

## Calibrate the selected model pair

### First check the tool without provider calls

```bash
python -m app.calibrate --dry-run --min-pass-rate 0.7
```

This deliberately simulates both model outcomes and router scores. It never loads
provider settings, downloads router checkpoints, or calls models. Its threshold is
an **illustrative test result**, not a usable research threshold. The `.7` target
only demonstrates the report on synthetic outcomes; the default requested target
is `.95`, and a report may legitimately have no qualifying candidate.

### Explicit real evaluation

Configure `MODEL_MODE=real`, `SMALL_MODEL`, `LARGE_MODEL`, `ROUTELLM_ROUTER`, provider
addresses/keys as needed, and install `requirements-routellm.txt`. Then:

```bash
# Small connectivity/evaluation sample first; not a representative calibration:
python -m app.calibrate --real --limit 2
# Full built-in synthetic pilot corpus:
python -m app.calibrate --real --min-pass-rate 0.9
```

Both `--real` and real model configuration are required. Real runs use the existing
OpenAI/Ollama clients and the configured RouteLLM method; no silent mock fallback.
MF/sw_ranking additionally need OpenAI embedding access. BERT does not.

Offline calibration deliberately ignores `ROUTER_MODE` and does not require an
already chosen `ROUTER_THRESHOLD`: it loads the configured `ROUTELLM_ROUTER` scorer
directly. The live application's strict threshold validation remains unchanged.
Settings/keys are never dumped to reports, and `.env` is never modified.

The default corpus has **24 contexts**: A/B × four checkpoints × initial/review/repair
plans. It is a versioned synthetic pilot smoke corpus, not validated task-difficulty
ground truth. Each context is scored once per repeat; **both** models propose plans
using the same context/question and read-only snapshot of the same catalog. Model
evaluation order alternates to reduce a fixed first-model/warmup ordering effect.
The original provisional oracle tool loop is reused; this evaluates proposed plans,
not conversation usefulness or participant performance.

With the default four tool steps, a full repeat can make up to **240 model calls
plus 24 router scorings**; these can consume cloud usage and embedding credits.
`--limit` and `--repeats` control the count. No participant database is opened:
the catalog is loaded into memory, and all artifacts/usage are separate.

### Inputs and outputs

Default output is a new ignored `data/calibration/calibration-<UTC timestamp>/`:

- `catalog.json`, `contexts.json`: frozen inputs, with SHA-256 hashes in the manifest.
- `evaluations.jsonl`: one result per context/repeat, score, prompts, evaluation order,
  both proposed plans and tool/message transcripts, pass/failure status, latency
  and per-call tokens/tool names.
  Transport errors are normalized; raw provider exception bodies are not exported.
- `thresholds.csv`: pilot threshold tradeoffs, large fraction/call counts, selected
  pass rate, always-small/always-large baselines, oracle-label agreement, token and
  timing measures. These are counterfactual selections from paired evaluations.
- `report.json`: the grid, candidate cutoff, actual evaluation usage for **both**
  models (separate from selected-policy usage), holdout results if available, and limitations.
- `manifest.json`: tool/oracle versions, model specs, router method/published config,
  package versions, exposed router checkpoint reference/revision, hashes, limits,
  status and error counts. Unknown immutable model or checkpoint revisions are null; pin/document them before
  research use rather than assuming aliases/package versions freeze the weights.

Provider failures and invalid router scores stay errors, not model-quality failures;
both sides are still recorded where possible. Completed results flush incrementally.
Error runs return exit code 1 and retain artifacts; interruptions retain completed
rows and an interruption marker. Partial manifests never claim completion.

Default thresholds use **pilot-score midpoints plus 0/1**, resolving narrow score
bands. Alternatively pass `--thresholds 0.4,0.45,0.48,0.5,0.55`. The production
comparison is preserved: `score >= threshold` selects large. A score of 1 still
selects large at the maximum allowed threshold of 1.

The provisional recommendation rule first meets the requested pilot pass-rate
target, then minimizes the fraction routed large; ties favor higher pass rate and
then lower threshold. No candidate is recommended after model/router errors. Both
models failing counts as a task failure, but is excluded from oracle size-label
agreement. Missing usage stays unknown. No monetary cost is invented from tokens.

For a custom corpus, use `--cases contexts.json` and optionally `--catalog catalog.json`:

```json
{"version":"my-synthetic-pilot-v1","synthetic":true,"cases":[
  {"id":"A-venue-example","scenario_id":"A","checkpoint":"Venue","split":"pilot",
   "plan":{"venue":null,"catering":null,"supplies":[]},"question":"Compare venue options."}
]}
```

IDs must be unique, plans must reference valid catalog categories, and `split` is
`pilot` or `holdout`. Current A/B reference IDs must remain in custom catalogs.
Holdout scores/outcomes are not used to choose the grid/candidate; its performance
is reported at the pilot-selected candidate. Repeats are not independent participants.
Use independent representative pilot/holdout evidence and researcher review before
manually choosing and fixing a threshold for the main study. A larger model is not
assumed to be better simply because of its size/name.
