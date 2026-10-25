# Running Model Matchmakers

A short guide to getting the app running. For background and contributor
details, see the main [README](README.md) and the setup docs under [`docs/`](docs/).

The project has two parts:

| Part | Stack | Needed? |
|---|---|---|
| `frontend/` | React + TypeScript + Vite (Node **24.14.0**) | Always |
| `backend/` | Python **3.12** + FastAPI + SQLite | Optional. The frontend has a built-in mock. |

You can run it in either of two ways:

1. **Frontend only (mock mode).** This is the simplest. Everything is simulated in the browser, and refreshing restarts the study.
2. **Frontend + backend (API mode).** Sessions are stored in SQLite, so refreshing resumes. It still uses simulated models by default and needs no API keys.

---

## 1. Frontend only (mock mode)

### macOS / Linux / WSL2

From the repository root:

```bash
bash scripts/setup.sh          # first time only: fetches Node 24.14.0 locally, installs deps, builds
bash scripts/frontend.sh dev
```

### Windows (PowerShell, no WSL)

Install [Node.js 24.14.0](https://nodejs.org/) first (`node --version` should print `v24.14.0`). Then:

```powershell
cd frontend
npm ci          # first time only
npm run dev
```

Open **http://localhost:5173**. Stop with **Ctrl+C**.

---

## 2. Frontend + backend (API mode)

### One-command start (macOS / Linux / WSL2)

Install Python **3.12** first using the [backend setup guide](docs/backend/development-setup.md#install-python-312).
Then, from the repository root, prepare both parts once:

```bash
bash scripts/setup-all.sh               # frontend + backend, mock-ready
# For your RouteLLM/BERT setup, use this instead:
bash scripts/setup-all.sh --routellm    # also installs PyTorch/transformers/RouteLLM
```

The script reuses the frontend's pinned native/project-local Node installer,
installs frontend dependencies and builds, creates/reuses `backend/.venv`, installs
the pinned backend requirements, and checks dependencies. It does not install OS
packages or modify configuration/data. Re-running setup is supported; incompatible
or incomplete existing Python environments require manual repair.

To check an existing setup without installing dependencies:

```bash
bash scripts/setup-all.sh --check --routellm
```

For subsequent launches:

```bash
bash scripts/run.sh
```

This uses `backend/.venv` without activation, starts the backend, waits for its
health check, and starts the API-connected frontend. Open **http://localhost:5173**.
Both servers log in the same terminal; **Ctrl+C stops both**, including reload workers.
It enables development sessions and sets local CORS origins to the frontend port.

For separate log panes, install tmux (`sudo apt install tmux` on Ubuntu/WSL, or
`brew install tmux` on macOS), then use:

```bash
bash scripts/run.sh --tmux
```

The backend runs in the left pane; the frontend opens in the right pane once the
backend is ready. **Ctrl+C in either pane stops both servers.** Press **Ctrl+B,
then D** to detach while keeping them running. When launched from an existing
tmux session or a noninteractive terminal, the script prints an attach command.
Each launch uses its own tmux server so existing tmux sessions are unaffected.

To stop a normal or tmux launch from another terminal:

```bash
bash scripts/stop.sh
```

The launcher records its PID and process identity under ignored `.tools/`; stop
checks that identity before signaling it. Linux/WSL uses kernel start ticks and
boot ID, which remain stable when the wall clock changes; macOS uses a UTC process
start timestamp. It does not kill arbitrary processes on ports
8000/5173, manually started servers, or Windows Ollama. Only one tracked launch
per checkout is supported. Stop works during backend loading as well.
`tmux ls` lists the default tmux server, not this private server; use the printed
`tmux -L model-matchmakers-… attach-session -t model-matchmakers-…` command to attach.
If upgrading a running launcher from the older wall-clock identity format, stop it
once with Ctrl+C in its original pane before restarting with the updated scripts.

The backend loads its existing `backend/.env` settings normally, so your configured
Ollama models and router are used. Keep Windows Ollama running and signed in if you
use its cloud models; this script starts the two project servers, not Windows Ollama.
No dependencies are installed or model smoke requests sent by the launcher.

Stop separately running project servers first, or choose free ports:

```bash
MM_BACKEND_PORT=8001 MM_FRONTEND_PORT=5174 bash scripts/run.sh
```

If initial router loading takes longer than three minutes, set
`MM_START_TIMEOUT_SECONDS=300`. Missing dependencies and occupied ports produce an
error before startup; servers started elsewhere are never stopped by the launcher.
Recently closed connections do not block restart: the preflight socket check
allows address reuse, matching Vite/Uvicorn, while rejecting active listeners.
Both Bash scripts target WSL2/Ubuntu, native Linux, and macOS (Intel/Apple Silicon),
using Bash 3.2-compatible syntax. WSL checks and simulated platform fixtures are
recorded in [launcher/setup verification](docs/frontend/launcher-setup-verification.md);
actual macOS verification remains outstanding. Native PowerShell uses the
two-terminal commands below.

### First-time setup / separate terminals

Use two terminals if you prefer separate logs or are running native Windows.

### Terminal 1: backend

macOS / Linux / WSL2:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt     # first time only
DEV_CONTROLS=true python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv                              # must be Python 3.12
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt     # first time only
$env:DEV_CONTROLS = "true"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks `Activate.ps1`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

To check that it's up, open http://127.0.0.1:8000/api/health. It should return
`{"status":"ok","mode":"mock",...}`. The API docs are at http://127.0.0.1:8000/api/docs.

> `DEV_CONTROLS=true` is required when the frontend runs with `dev`. Without it,
> the frontend shows "could not start a study session".

### Terminal 2: frontend

macOS / Linux / WSL2:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 bash scripts/frontend.sh dev
```

Windows (PowerShell):

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Instead of setting the variable each time, you can copy `frontend/.env.example`
to `frontend/.env.local` and uncomment `VITE_API_BASE_URL`.

Open **http://localhost:5173**.

---

## Running the tests

| What | macOS / Linux / WSL2 | Windows (in `frontend/` or `backend/`) |
|---|---|---|
| Frontend type-check | `bash scripts/frontend.sh type-check` | `npm run type-check` |
| Frontend tests | `bash scripts/frontend.sh test` | `npm test` |
| Production build | `bash scripts/frontend.sh build` | `npm run build` |
| Preview the build (port 4173) | `bash scripts/frontend.sh preview` | `npm run preview` |
| Backend tests (venv active) | `cd backend && python -m pytest` | `python -m pytest` |

The backend tests need no keys and make no network calls.

---

## Optional: real models and RouteLLM

By default the backend uses **mock** model replies and **mock** routing. To use
real models, copy `backend/.env.example` to `backend/.env` and set:

```bash
MODEL_MODE=real
SMALL_MODEL=ollama:mixtral:8x7b     # or openai:<model>
LARGE_MODEL=openai:gpt-4-turbo
OPENAI_API_KEY=<your key>           # needed if either model uses openai:
```

Restart the backend, then check the configuration with `python -m app.smoke_models`.
For the RouteLLM router (`pip install -r requirements-routellm.txt`, plus
`ROUTER_MODE=routellm` and `ROUTER_THRESHOLD`), the offline oracle
(`python -m app.oracle`), and the records summary (`python -m app.records`), see
[Backend development setup](docs/backend/development-setup.md).

**Never put API keys in `frontend/` or any `VITE_*` variable.** Those values end up in the browser.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Frontend dependencies are missing` | Run `bash scripts/setup.sh` (or `npm ci` in `frontend/`). |
| `node` / `npm` not found on Windows | Install Node 24.14.0 and reopen the terminal. |
| `python3.12: command not found` | Install Python 3.12 (`brew install python@3.12`, or `sudo apt install python3.12 python3.12-venv`). |
| `ModuleNotFoundError: app` | Run backend commands from `backend/` with `.venv` activated. |
| `Address already in use` | Another process is using the port. Pass `--port 8001` and update `VITE_API_BASE_URL` to match. |
| Want fresh sessions / allocation slots | Stop the backend and delete `backend/data/model-matchmakers.sqlite3`. |
| Startup error mentioning `OPENAI_API_KEY` or `MODEL_MODE` | Fix the values in `backend/.env`, or delete it to go back to mock mode. |
