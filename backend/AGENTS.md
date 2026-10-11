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
- `app/main.py` builds the app; `app/routes.py` holds the `/api` routes;
  `app/study.py` holds the study rules, ported one-to-one from the frontend
  `mockExperiment.ts`; `app/store.py` loads/saves one JSON state per session in a
  single SQLite transaction; `app/catalog.py` and `app/db.py` hold the seeded catalog
  and schema; `app/definitions.py` holds sequences and provisional materials.
  `app/models.py` is the OpenAI-compatible small/large client (OpenAI and Ollama),
  `app/agent.py` the bounded tool-calling planning agent and the mock agent, and
  `app/smoke_models.py` a manual real-model check.
- `app/fixtures/*.json` are exported from the frontend mock with
  `node backend/scripts/export_fixtures.mjs`. Rerun it when the frontend catalog,
  survey, preparation, or recommendation definitions change; never edit them by hand.
- Keep it simple: plain `sqlite3`, no ORM, background workers, or generic frameworks.
  Match the frontend mock's behavior and error codes instead of inventing new rules.

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
- Never hold the database transaction during a model call. Validate, release, call,
  then re-check the task/checkpoint/deadline before saving; discard late replies.
- The `model_calls` table is research-only (provider, model, tokens, latency, shown).
  Never return it, provider names, or token counts in participant responses.

## Configuration and secrets

- The backend must start and pass tests with no `.env` and no keys. Mock mode is the
  default. `MODEL_MODE=real` is an explicit opt-in that fails at startup when
  misconfigured; never fall back to mock silently. Tests use scripted clients and a
  local fake OpenAI-compatible server, never real providers.
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
