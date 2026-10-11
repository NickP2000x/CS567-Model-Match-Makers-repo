# Backend verification

Repeatable backend checks and the results actually recorded. Results describe the
tested version only. Mock-mode results do not cover real models, the frontend
integration (#39), or approval of provisional study materials.

## #32 — setup, guidance, and CI

### Repeatable checks

From `backend/`, following [development setup](development-setup.md):

1. Create a fresh `.venv` with Python 3.12, install `requirements-dev.txt`, and run
   `python -m pip check`: no broken requirements.
2. `python -m pytest`: all tests pass without `.env` or keys. They cover:
   - health response `{"status": "ok", "mode": "mock"}` and docs under `/api`;
   - error envelope for unknown routes, wrong methods, invalid/extra request
     fields (`400 INVALID_REQUEST`), contract errors, and unexpected errors
     (`500 INTERNAL_ERROR` with no internal message in the response or log);
   - safe defaults, a copied `.env.example`, rejection of `MODEL_MODE=real`, and
     the API key never appearing in settings output or the health response.
3. With no `backend/.env`, start Uvicorn and request `/api/health`: mock mode.
   Request an unknown `/api/...` path: `404` with `{"error": {"code": "NOT_FOUND", …}}`.
4. Start with `MODEL_MODE=real`: startup fails with a validation error naming
   `model_mode` (no silent fallback).
5. `git check-ignore`: `.env`, `.env.*`, `.venv/`, `__pycache__/`, and `*.sqlite3`
   are ignored; `backend/.env.example` is tracked.

### Recorded results — 2026-10-09

- Environment: macOS (Darwin 25.5, Apple Silicon), Homebrew Python 3.12.15.
- Checks 1–5 passed: fresh install from the pinned files, `pip check` clean,
  13 tests passed with no warnings, health returned mock mode with no `.env`,
  unknown path returned the error envelope, real mode was rejected at startup,
  and the ignore rules matched as listed.
- GitHub Actions on the `issue-32-backend-setup` push (ubuntu-latest, Python 3.12):
  Backend checks passed (install, `pip check`, pytest, key-free startup/health);
  Frontend checks also passed. WSL2/Linux backend setup was not tested locally.
- Frontend checks were not rerun: no frontend source, configuration, or scripts changed.

## #34 with #33 catalog and mock parts of #37/#38 — study flow in mock mode

The backend ports the frontend mock (`mockExperiment.ts`) so the full study runs
over HTTP: seeded catalog, balanced allocation, intro/preparation gates, practice,
both tasks with automatic/override routing at all four checkpoints, server-side
deadlines, NASA-TLX surveys, and optional feedback. Recommendations and agent
replies are the same simulated fixtures; no real models or router yet.

### Repeatable checks

From `backend/` with `.venv` active: `python -m pytest` (key-free, temporary
databases, controllable clock). The tests cover:

- **Catalog:** summaries hide details; search by name/category; seeding twice is
  safe; each reference plan meets all four constraints and each distractor breaks
  exactly the one it targets; inspection records an item once.
- **Sessions:** 12 sessions → 3 per sequence, the 13th gets `ALLOCATION_FULL`;
  concurrent creation never shares a slot; resume returns the same state after an
  app restart; consent-first and preparation gates reject skips; development
  sequence selection/reset only with `DEV_CONTROLS`.
- **Flow:** all four sequences from consent to completion (no practice survey);
  automatic applies the recommendation with no choice; override hides the
  recommendation until lock and records initial/recommended/final for keep and
  change; stale checkpoint requests are rejected; invalid/incomplete plans submit.
- **Timing:** a late planning request ends the task as timed-out at the deadline,
  keeps the plan, moves to the survey, and returns `TASK_EXPIRED` with the state;
  submitting after the deadline records a timeout; repeated begin keeps the deadline.
- **Surveys:** v2 increments, unknown/out-of-range/boolean answers rejected,
  incomplete submit rejected, `rawScore` = 175/6 for `[25,0,50,75,25,0]`.

### Recorded results — 2026-10-09

- macOS, Python 3.12.15: 37 tests passed.
- Mutation check: deliberately breaking recommendation concealment, the deadline
  check, the practice → Task 1 handoff, the stale-checkpoint check, or survey
  increments each made a test fail; the original code was restored.
- Live Uvicorn smoke run (temporary database, `DEV_CONTROLS=true`, sequence 3):
  intro → practice → Task 1 override checkpoint over HTTP; early reveal rejected,
  `large → small → small` recorded, 900000 ms deadline, resume by `sessionId`,
  no server errors logged.
- Not done: the frontend does not call the backend yet (#39); real models/router
  (#35–#37) and research event logging (#38) are not implemented; WSL2/Linux local
  run not tested.
