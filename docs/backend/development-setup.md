# Backend development setup

The backend is a Python 3.12 FastAPI service under `backend/`. It runs in **mock
mode** by default: no `.env`, API keys, database, or model provider is needed.
Its dependencies are separate from the frontend's; the frontend still runs on its
own with the in-memory mock and does not call the backend yet (#39).

## Install Python 3.12

Check with `python3.12 --version`. If it is missing:

- **macOS:** `brew install python@3.12` (or the python.org installer). The Apple
  system `python3` is older and is not used.
- **WSL2 Ubuntu / native Ubuntu 24.04:** `sudo apt update` and
  `sudo apt install python3.12 python3.12-venv`.
- **Ubuntu 22.04 and other distributions:** the default Python is older. Install
  3.12 from your distribution's packages, the deadsnakes PPA, or `uv python install 3.12`.

On WSL2, use Python inside the Ubuntu terminal and keep the checkout in the Linux
filesystem; Windows Python is not a replacement.

## Create the environment and run checks

From the repository root:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest
```

`.venv/` is ignored by Git. Re-running the install is safe. Later sessions only
need `cd backend` and `source .venv/bin/activate`.

## Start the server

With the environment active, from `backend/`:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check it from another terminal or a browser:

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok","mode":"mock"}
```

Interactive API docs are at <http://127.0.0.1:8000/api/docs>. On WSL2, open these
URLs in a Windows browser; localhost is normally forwarded. Stop with **Ctrl+C**.

## Configuration

Every setting has a safe default. To override one, copy `backend/.env.example` to
`backend/.env` (ignored by Git) or set the environment variable. Blank values keep
the default.

| Variable | Default | Notes |
|---|---|---|
| `MODEL_MODE` | `mock` | `mock` or `real`. Other values, or real mode without a needed key, stop startup. |
| `SMALL_MODEL` / `LARGE_MODEL` | `ollama:mixtral:8x7b` / `openai:gpt-4-turbo` | `provider:model` with provider `openai` or `ollama`. |
| `OPENAI_API_KEY` | unset | Server-only secret, required in real mode when a model uses `openai`. Never put it in frontend `VITE_*` variables. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Non-secret local model address; the client uses its `/v1` API. |
| `MODEL_TIMEOUT_SECONDS` / `AGENT_MAX_STEPS` | `60` / `4` | Per-call timeout; tool-using calls per participant message. |
| `DATABASE_PATH` | `data/model-matchmakers.sqlite3` | Relative to `backend/`. Created and seeded on first request; database files are ignored by Git. Delete the file to start over with fresh allocation slots. |
| `DEV_CONTROLS` | `false` | Development only: `POST /api/sessions` accepts `sequenceId`, and `/reset` starts a new session. Such sessions use `dev-…` IDs and never consume the 12 allocation slots. |

## Real models (#35/#36)

Mock mode needs nothing. To use real models, put these in `backend/.env` (never in
frontend `VITE_*` variables) and restart the server:

```bash
MODEL_MODE=real
SMALL_MODEL=ollama:mixtral:8x7b      # paper default; or openai:<model>
LARGE_MODEL=openai:gpt-4-turbo       # paper default
OPENAI_API_KEY=<your key>            # needed when either model is openai:
```

- Ollama: install it, run `ollama pull mixtral:8x7b` (about 26 GB; needs a machine with
  roughly 32 GB of memory), and keep `ollama serve` running. Without that hardware, a
  smaller or hosted substitute is a researcher decision; record it in verification.
- Check the configuration before a session: `python -m app.smoke_models` sends one
  prompt to each model and one agent turn with tools, printing latency and tokens.
- In real mode the agent replies with the stage's locked model. It can search,
  inspect, and check plans (at most `AGENT_MAX_STEPS` tool-using calls plus one final
  answer) but never edits the plan. Recommendations are still simulated until #37.
- Each model call is stored in the `model_calls` table (research-only). A provider
  failure returns `502 PROVIDER_ERROR` and the participant can retry. A reply that
  arrives after the deadline, a checkpoint change, or submission is not shown.

## Troubleshooting

- `Input should be 'mock' or 'real'` or `needs OPENAI_API_KEY` at startup: fix
  `MODEL_MODE` / the key in your shell or `backend/.env`.
- `python3.12: command not found`: install Python 3.12 as above.
- `Address already in use`: another process uses port 8000; pass `--port 8001`.
- `ModuleNotFoundError: app`: run commands from `backend/` with `.venv` active.

CI (`.github/workflows/backend-checks.yml`) installs the same pinned files on
Python 3.12, runs `pytest`, and starts the server without `.env` or secrets to
confirm the health check. See [verification](verification.md) for recorded results.
