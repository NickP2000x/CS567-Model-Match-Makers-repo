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

Use two terminals.

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
