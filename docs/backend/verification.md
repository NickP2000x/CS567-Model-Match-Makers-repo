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
