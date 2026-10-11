# Backend instructions

Read root `../AGENTS.md` first. It owns shared research invariants, current phase,
data-handling rules, Git workflow, and PR approval/merge control. Do not duplicate
or override those rules here. Work only on an explicitly selected backend issue
(#31–#41) and read it with its dependencies before editing.

## Stack and structure

- Python 3.12 (`.python-version`), FastAPI, Uvicorn, pydantic-settings; pytest for tests.
  Dependencies are fully pinned in `requirements.txt` / `requirements-dev.txt`;
  change a pin deliberately, regenerate from a fresh virtual environment, and run
  `pip check`.
- `app/main.py` builds the app (`create_app`) and owns routes until a feature needs
  its own module. `app/config.py` holds server-only settings. `app/errors.py` holds
  the shared error envelope. Tests live in `tests/`.
- Add modules only when an issue needs them (for example catalog/SQLite in #33,
  sessions/study state in #34). No ORM, background workers, or generic frameworks
  before there is a concrete need.

## API rules

- Follow `../docs/experiment-service-contract.md` for behavior and the #31 HTTP
  draft for transport once it is merged. Proposals there are not agreed until #31
  records agreement; flag deviations instead of inventing protocol.
- Keep every route under `/api`. Return failures only as
  `{"error": {"code", "message"}}` by raising `ApiError` with the contract's codes.
  Messages are participant-safe: no stack traces, settings, keys, or provider details.
- Request models forbid unknown fields (`extra="forbid"`) so malformed requests
  become `400 INVALID_REQUEST`.
- Prices are integer cents; timestamps are epoch milliseconds from the server clock.

## Configuration and secrets

- The backend must start and pass tests with no `.env` and no keys. Mock mode is
  the default and, until #35, the only accepted `MODEL_MODE`. Real mode must be an
  explicit opt-in that fails clearly when misconfigured; never switch silently.
- `OPENAI_API_KEY` is server-only: keep it a `SecretStr`, never return, log, or copy
  it into frontend `VITE_*` variables. `OLLAMA_BASE_URL` and `DATABASE_PATH` are
  non-secret with defaults. Only `backend/.env.example` (placeholders) is committed.
- CI uses mocks only and has no provider secrets. Real-model checks are manual and
  require explicit configuration; record them separately from mock results.

## Commands and verification

From `backend/` with the virtual environment active (see
`../docs/backend/development-setup.md`):

```bash
python -m pytest
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/api/health
```

- Add focused tests for each behavior change and keep them key-free.
- Record repeatable checks and actual results in `../docs/backend/verification.md`;
  never claim unperformed platform, model, or browser checks.
- The standalone frontend mock must remain runnable without the backend.
