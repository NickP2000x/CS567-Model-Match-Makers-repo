# Model Matchmakers

A frontend research demonstration for **Human Override in Automatic LLM Routing:
A User Study**. The study compares automatic model routing with participant
override of router recommendations during an event-planning task. This prototype
defaults to simulated router and model behavior and uses synthetic information
only; it is not ready for real participant data collection.

## Quickstart: setup, run, calibrate, export

Run these commands from the **repository root** in WSL2/Ubuntu, native Linux, or
macOS. Install **Python 3.12** and Git first. The scripts select the backend virtual
environment automatically; no manual activation is needed.

[Shell quickstart](#1-set-up-once) · [Manual commands](#manual-commands-without-helper-scripts) ·
[Data and output locations](#where-your-data-and-reports-are-saved)

### 1. Set up once

```bash
bash scripts/setup-all.sh --routellm
```

This prepares both frontend and backend, including optional RouteLLM dependencies.
Omit `--routellm` for mock-only routing. Real models use your server-side
`backend/.env` configuration; see [backend setup](docs/backend/development-setup.md).
For Windows-hosted Ollama, keep Ollama running and signed in for cloud models.

### 2. Run the app

```bash
bash scripts/run.sh --tmux
```

Open **http://localhost:5173**. Tmux shows backend/frontend logs in separate panes;
install it first or use `bash scripts/run.sh` for a shared terminal. Ctrl+C in
either pane stops both servers. To stop from another terminal:

```bash
bash scripts/stop.sh
```

### 3. Check and run calibration

```bash
# Simulated tool check: no model calls or router downloads
bash scripts/calibrate.sh --dry-run

# Small real-model check using the configured model pair and router
bash scripts/calibrate.sh --real --limit 2
```

For the full built-in corpus, remove `--limit 2`. Real evaluation requires
`MODEL_MODE=real` and consumes model/cloud usage. Dry-run cutoffs are illustrative;
real reports require pilot review, and neither command changes the live threshold.
Results go to timestamped folders under **`backend/data/calibration/`**.

### 4. Export a run to CSV

```bash
bash scripts/export-csv.sh
```

This reads **`backend/data/model-matchmakers.sqlite3`** without modifying it and
writes linked CSVs, a manifest, and a data dictionary under
**`backend/data/exports/`**. Development/practice records are included by default;
add `--study-only` to filter them out. If your database is elsewhere, pass
`--database /absolute/path/to/study.sqlite3`; the exporter does not load `.env`.

Calibration and export run independently of the app servers. Both wrappers forward
Python CLI options, including `--help`; custom relative paths are resolved from
`backend/`, or use absolute paths. Default generated reports/exports are ignored by Git.

See [RUNNING.md](RUNNING.md) for detailed startup/native Windows instructions and
[offline tools](docs/backend/offline-tools.md) for calibration criteria, filters,
and CSV formats. These shell scripts target WSL/Linux/macOS; native PowerShell can
use the documented Python commands directly.

## Manual commands (without helper scripts)

These are the WSL/Linux/macOS equivalents. Python 3.12 and **native Node 24.14.0
with npm on your PATH** are required; the shell setup above can instead prepare
the project-local Node runtime. See [frontend prerequisites](docs/frontend/development-setup.md)
and [backend prerequisites](docs/backend/development-setup.md). Native Windows
PowerShell activation/environment syntax is in [RUNNING.md](RUNNING.md).

### First-time backend setup — repository root

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -I -m pip install -r requirements-dev.txt
python -I -m pip check
```

For real RouteLLM routing/calibration, also run **from `backend/`**:

```bash
python -I -m pip install -r requirements-routellm.txt
python -I -m pip check
```

### First-time frontend setup — new terminal at repository root

```bash
cd frontend
node --version                 # must be v24.14.0
npm ci
npm run build
```

### Start the backend — terminal 1, starting at repository root

```bash
cd backend
source .venv/bin/activate
DEV_CONTROLS=true python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Start the frontend — terminal 2, starting at repository root

```bash
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --port 5173 --strictPort
```

Open **http://localhost:5173**. The backend health check is
**http://127.0.0.1:8000/api/health**, and API docs are at
**http://127.0.0.1:8000/api/docs**. Stop each manually started server with Ctrl+C
in its own terminal; `scripts/stop.sh` manages only launcher-started servers.

### Calibration and CSV export — new terminal at repository root

```bash
cd backend
source .venv/bin/activate
python -m app.calibrate --dry-run
python -m app.export_csv --database data/model-matchmakers.sqlite3
```

For a small real-model evaluation, use this **from `backend/` with the environment
active**, after configuring real models and installing the router dependencies:

```bash
python -m app.calibrate --real --limit 2
```

Both manual and shell commands use the same Python tools, output folders, and
explicit real-call opt-in. Real evaluation consumes provider usage; it is separate
from the simulated dry run. To filter CSVs, add `--study-only`; to choose another
source or output parent, add `--database`/`--output` with the appropriate paths.

## Where your data and reports are saved

Paths below are relative to the repository root and show the **defaults**:

| Data | Location | When it appears |
|---|---|---|
| Saved backend study records | `backend/data/model-matchmakers.sqlite3` | When an API-connected frontend session is created; frontend-only mock mode does not create it |
| CSV export folder | `backend/data/exports/export-<timestamp>/` | After either export command succeeds |
| Calibration result folder | `backend/data/calibration/calibration-<timestamp>/` | After a dry-run or real calibration command writes its artifacts |

Each command prints its actual output folder. Timestamps are UTC; each run gets a
new folder rather than overwriting earlier results. A custom `DATABASE_PATH` can
move backend storage; explicitly pass that file to export because the exporter
does not read `.env`. `--output` changes the output parent directory.

**Useful CSVs inside an export folder:**

| File | Contents |
|---|---|
| `sessions.csv` | Session/sequence, demographics, feedback, and development/mode flags |
| `tasks.csv` | Saved task status, times, cost, constraints, raw ratings, and stored workload score |
| `messages.csv` | Conversation text, role, stage, selected model role, and timestamps |
| `checkpoint_choices.csv` | Initial/recommended/final choices and decision timestamps |
| `routing_decisions.csv` | Router scores, thresholds, recommendations, errors, and applied status |
| `model_calls.csv` | Actual model identifiers, latency, tokens, errors, and participant/oracle purpose |
| `survey_responses.csv` | Raw individual ratings and their versioned wording/orientation |
| `manifest.json` / `data_dictionary.json` | Export counts, source schema, filters, column units, joins, and null conventions |

The remaining CSVs contain selected plan items, inspections, acknowledgements,
task reopens, catalog reference data, and any oracle results. Development/practice
records are included unless filtered. See [all 13 datasets](docs/backend/offline-tools.md#files).

**Inside a calibration folder:** `report.json` summarizes the candidate threshold
and limitations; `thresholds.csv` compares candidate policies; `evaluations.jsonl`
contains paired outcomes/usage. `contexts.json`, `catalog.json`, and `manifest.json`
retain frozen inputs and version metadata. Dry-run reports are labelled simulated
and must not be used as actual model-pair calibration.

The default database and generated output folders are ignored by Git. Refresh the
editor file explorer after creating an export if the new folder is not visible.

## Run the frontend

Run these commands from the repository root:

```bash
bash scripts/setup.sh
bash scripts/frontend.sh dev
```

Open the URL shown in the terminal, normally **http://localhost:5173**.
Stop the server with **Ctrl+C**.

### First-time setup

- Supported environments: WSL2 Ubuntu, native Linux, and macOS.
- Git is required. Setup checks prerequisites and provides guidance when something
  is missing.
- You do not need to install Node or nvm first. Setup selects or prepares the pinned
  Node 24.14.0 runtime, installs frontend dependencies, type-checks, and builds.
- On WSL2, run the commands in an Ubuntu terminal and open the URL in a Windows
  browser. Keep the checkout in the WSL Linux filesystem.
- Setup can be rerun. For subsequent development sessions, use
  `bash scripts/frontend.sh dev`.

See [Frontend development setup](docs/frontend/development-setup.md) for full prerequisites,
platform instructions, and troubleshooting.

### Current demonstration

The frontend supports:

Consent → Demographics → Before-start reminders / Visual guide → Practice →
Task 1 → Workload ratings 1 → Task 2 → Workload ratings 2 → Optional feedback → Completion

Practice and each experimental task have an acknowledgement/preparation page and
an explicit Start button. Requirements and experimental deadlines appear only after
Start. Later pages show the current section and read-only study progress.

Practice includes catalog inspection, plan editing, four constraint checks,
four stages, and simulated conversation. Both experimental tasks include simulated
automatic/override routing, a 15-minute countdown, permissive submission/timeout,
and the reusable provisional five-point, fully labelled NASA-TLX adaptation.

In development (`dev`), expand **Development controls** below the screen to choose
one of the four A/B sequences, apply it with a reset, or trigger an experimental
timeout. These controls are absent from the normal production build/preview.
The standalone mock defaults to sequence 1; backend API mode supports randomized,
balanced assignment and persistent sessions.

By default the frontend uses an in-memory mock service: no backend, database, API
keys, or `.env` file are required, and refreshing restarts the demonstration. With
`VITE_API_BASE_URL` set it uses the backend instead, and a refresh resumes the session.

## Check and preview the frontend

Run from the repository root:

```bash
bash scripts/frontend.sh type-check
bash scripts/frontend.sh test
bash scripts/frontend.sh build
bash scripts/frontend.sh preview
```

Build before previewing. Preview normally uses **http://localhost:4173** and serves
the production assets generated in `frontend/dist/`.

For browser checklists and recorded results, see:
- [Final prototype smoke checklist and coverage](docs/frontend/prototype-smoke-checks.md)
- [Introduction verification](docs/frontend/introduction-verification.md)
- [Practice workspace verification](docs/frontend/workspace-verification.md)
- [Routing verification and integration handoff](docs/frontend/routing-verification.md)
- [Workload survey verification and integration handoff](docs/frontend/workload-verification.md)
- [Complete study flow verification and Sprint 3 handoff](docs/frontend/study-flow-verification.md)
- [Study refinements and current #22 handoff](docs/frontend/study-refinements-verification.md)

## Frontend and backend setup

Frontend and backend development use separate runtimes and dependencies:

| Component | Stack | Purpose |
|---|---|---|
| Frontend | React, TypeScript, Vite, Node/npm | Browser interface |
| Backend | Python 3.12, FastAPI, Uvicorn, SQLite | API, sessions, catalog, routing, agent, and research records |

`scripts/setup.sh` prepares the frontend only; `scripts/setup-all.sh` prepares both
components. The backend runs the complete study
flow in mock mode (catalog, sessions with balanced allocation, routing, timing,
surveys, feedback) using the same simulated responses as the frontend mock. Set
`VITE_API_BASE_URL=http://127.0.0.1:8000` to run the frontend against it; see
[Backend (API) mode](docs/frontend/development-setup.md#backend-api-mode). It needs
Python 3.12 but no `.env` or keys. Optional real models (OpenAI/Ollama) are configured
in `backend/.env`; see [Real models](docs/backend/development-setup.md#real-models-3536).
From the repository root:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open **http://127.0.0.1:8000/api/health**. See
[Backend development setup](docs/backend/development-setup.md) for platform notes
and configuration, and the [backend documentation handoff](docs/backend/README.md)
for the planned work.

Backend mode runs frontend and backend servers, together through `scripts/run.sh`
or with the separate-terminal commands in the setup guide;
standalone frontend mock mode remains available. Real models (#35/#36), the RouteLLM
router (#37), the offline oracle (#40), and the records report (#41) are optional and
described in [Backend development setup](docs/backend/development-setup.md).
For read-only SQLite-to-CSV exports and offline paired-model routing calibration,
see [Offline tools](docs/backend/offline-tools.md). Calibration starts with an
explicit synthetic dry run; real model calls require separate opt-in.

See [Project structure](docs/project-structure.md) and the
[experiment service contract draft](docs/experiment-service-contract.md)
for component boundaries.

## Research references

- Checkpoint 2 methodology video: https://youtu.be/mGcKdjsUJu4
- Overleaf project: https://www.overleaf.com/read/yjwtghwfqtqp#635087
- [Prototype sprint board](https://github.com/users/NickP2000x/projects/7)
