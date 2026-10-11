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

## #39 — frontend API adapter

`frontend/src/services/apiExperiment.ts` implements the same `ExperimentService` the
screens already use, over the #31 routes. `VITE_API_BASE_URL` selects it explicitly;
unset keeps the in-memory mock. The backend allows the local Vite origins via CORS.

### Repeatable checks

1. `bash scripts/frontend.sh test`: offline adapter tests (scripted fetch) for
   create/resume/replace session, connection errors, task and checkpoint in planning
   requests, error mapping, `TASK_EXPIRED` state handoff, local guards, reset.
2. Start the backend with `DEV_CONTROLS=true`, then
   `MM_API_URL=http://127.0.0.1:8000 bash scripts/frontend.sh test`: all four
   sequences consent → completion through the adapter, override concealment and
   backend errors, refresh resume with an unchanged deadline.
3. Backend `pytest`: CORS allows local dev/preview origins (also on error responses)
   and rejects others.
4. Browser: production build with `VITE_API_BASE_URL`, backend without
   `DEV_CONTROLS`, fresh database. Complete one participant from consent to
   completion, refreshing in the middle of Task 1.

### Recorded results — 2026-10-09

- macOS, Node 24.14.0 (project-local), Python 3.12.15. Frontend type-check and
  build passed; 46 frontend tests passed with 6 integration tests skipped by default,
  and 52 passed with `MM_API_URL` set against a live mock-mode backend. Backend: 41 tests passed.
- Headless Chromium (Playwright, kept outside the repository), production preview:
  allocation gave `P03` (sequence 1); intro, guide, practice (search, inspect, add,
  simulated reply, submit), Task 1 automatic and Task 2 override across all four
  checkpoints, ratings, feedback, completion. A refresh at Task 1 Catering resumed
  the same checkpoint and messages. Development controls were absent. No browser
  console errors and no backend errors. The backend record had both surveys and four
  decisions per task.
- Development server: with a backend lacking `DEV_CONTROLS`, the server-unavailable
  screen explained the fix; with it, a `dev-…` session was created and the UI reset
  to sequence 3 created a new backend session.
- Not done: Safari/Firefox, WSL2/Windows browser, screen reader.
- For Nick (copy): the before-start acknowledgement still says refreshing restarts the
  demo, which is only true in mock mode. The footer now follows the mode.

## #35/#36 — real model clients and planning agent

`MODEL_MODE=real` sends participant messages to the stage's locked model through one
OpenAI-compatible client (OpenAI, or Ollama's `/v1` API). The agent is a bounded
tool-calling loop (search, inspect, check plan) that never edits the plan. Mock mode is
unchanged and remains the default. Routing recommendations stay simulated until #37.

### Repeatable checks

1. `python -m pytest` (no keys, no network beyond localhost):
   - **Config:** real mode needs `OPENAI_API_KEY` only when a model uses openai;
     invalid model specs and limits are rejected at startup.
   - **Client:** a local fake OpenAI-compatible server checks the request (model,
     messages, tools, `Authorization` only for openai), tool-call and token parsing, and
     HTTP errors, invalid JSON, timeouts, and unreachable hosts becoming safe errors
     (no key or response body in the message).
   - **Agent:** tool use then answer with the locked model, failed checks fed back for
     revision, tool errors returned to the model, bounded loop with a forced final
     answer, empty-answer fallback, prompt contents and history limit, no plan changes.
   - **API:** real replies shown (`simulated: false`) and recorded in `model_calls`
     without leaking model names or tokens; large model used when the stage locks it;
     provider failure → `502 PROVIDER_ERROR` with state unchanged and retry working;
     replies arriving after the deadline (`TASK_EXPIRED`), a checkpoint change
     (`STALE_OPERATION`), or submission (`NO_ACTIVE_TASK`) discarded but recorded
     (`shown = 0`); practice uses the real small model; end-to-end over HTTP with
     settings-built clients.
2. With real credentials in `backend/.env`: `python -m app.smoke_models`.

### Recorded results — 2026-10-09

- macOS, Python 3.12.15: 68 backend tests passed (27 new for #35/#36).
- Mutation check: saving late replies without re-checking, ignoring the locked stage
  model, an unbounded tool loop, or not recording failed calls each made tests fail;
  sources restored.
- Live run with a standalone fake OpenAI-compatible server (no real provider): backend
  in real mode reported `mode: real`; `smoke_models` passed for both sizes plus an agent
  turn with `check_plan`; the frontend adapter integration tests passed (52/52) through
  the real-mode backend; the headless-browser walkthrough of the production build
  passed with replies labelled `small model`/`large model` (not "Simulated"). 82 model
  calls were recorded (all shown, tokens stored); every request carried the key; no
  backend or browser errors.
- **Not done:** no real OpenAI or Ollama call was made (no key or Ollama on this
  machine). Run `python -m app.smoke_models` with real credentials and record the result.
- **Decisions to confirm:** #36 names LangGraph; this uses a plain bounded loop with
  the same tools (simpler, no extra dependencies). The agent suggests and checks
  but does not edit the plan. Default models follow the paper; Mixtral 8x7B needs
  about 32 GB of memory, and any substitute needs researcher approval.

## #37 — RouteLLM router and checkpoint locking

`ROUTER_MODE=routellm` replaces the fixed recommendations with RouteLLM's strong-model
win rate (`score >= ROUTER_THRESHOLD` → large). The phase and concealment checks run
before scoring; scoring runs outside the database lock; a recommendation is applied only
if the participant is still at that checkpoint. Mock routing stays the default.

### Repeatable checks

1. `python -m pytest` (RouteLLM not installed; tests inject a scorer): settings require an
   explicit threshold (and a key for embedding routers); `>=` threshold boundary; invalid
   scores and router exceptions never fall back; missing package gives an install hint;
   prompt contents; automatic uses the score and repeats do not rescore; override never
   scores before the initial lock; router failure → `502 PROVIDER_ERROR` then retry;
   recommendations ready after the deadline or submission are not applied; every
   decision (including mock) is stored in `routing_decisions`.
2. With `requirements-routellm.txt` installed: start with `ROUTER_MODE=routellm`,
   `ROUTELLM_ROUTER=bert`, an explicit threshold, and route the four checkpoints.

### Recorded results — 2026-10-10

- 82 backend tests passed (14 new); 46 frontend tests passed (routing labels follow
  `routerSimulated`). Mutation check: applying late recommendations, `>` instead of
  `>=`, scoring before the concealment check, and falling back on failure each failed tests.
- Real RouteLLM 0.2.0 (torch 2.14.1, transformers 5.19.0) in a separate environment,
  `bert` router with its published checkpoint (first load ~2 minutes): the backend
  started in routellm mode, `/api/health` reported it, and the four Task 1 checkpoints
  scored 0.492 / 0.499 / 0.484 / 0.474. With threshold 0.48 that gave large, large,
  large, small, applied and recorded, with no errors.
- **Finding for the pilot:** scores for these stage prompts sit in a narrow band
  (≈0.47–0.50), so the threshold decides almost everything; calibrate it in the pilot.
  The `mf` router (trained on the paper's GPT-4/Mixtral pair) needs an OpenAI key and was
  not run here.

## #40 — paired-output oracle

### Repeatable checks

`python -m pytest` (scripted clients): label rule (small preferred when it passes);
provisional stage pass rule; proposals via tools then `submit_plan`, no proposal when the
model never submits, bounded loop with submit-only last step, malformed submissions;
the four fixture cases small-pass / large-only / both / neither; results and calls stored
separately (`purpose = 'oracle'`, never shown) with session state byte-for-byte unchanged;
no re-evaluation; a failed checkpoint stays pending, records both sizes' calls, and is
retried; older databases gain the `purpose` column.

### Recorded results — 2026-10-10

- 90 backend tests passed (8 new for #40/#41). Mutation check: preferring large when
  both pass, counting oracle calls as participant usage, judging Venue on all four
  constraints, and re-evaluating finished checkpoints each failed tests.

## #41 — integrated verification

### Repeatable run

1. Backend in real mode (`MODEL_MODE=real`) with `ROUTER_MODE=routellm`; the frontend
   production build with `VITE_API_BASE_URL`; `DEV_CONTROLS=true` for the adapter tests.
2. `MM_API_URL=… bash scripts/frontend.sh test` (all four sequences through the adapter).
3. Browser walkthroughs of the production build (participants take allocation slots).
4. `python -m app.oracle`, then `python -m app.records`.

### Recorded results — 2026-10-10

Mac (Darwin 25.5), Python 3.12.15, Node 24.14.0, headless Chromium (Playwright, outside
the repository). Real RouteLLM 0.2.0 `bert` router (threshold 0.48 for this run only);
models were a local fake OpenAI-compatible server (`fake-small` / `fake-large`), not real
providers.

- Health reported `mode: real`, `router: routellm`. Adapter integration: 52/52 passed.
- Three browser participants were allocated P01–P03 (sequences 3, 4, 1) and each completed
  consent → completion with a refresh mid-Task 1 (same checkpoint and messages), both
  conditions over four checkpoints, ratings, and feedback. No browser console errors.
- 57 routing decisions (scores 0.383–0.496; 15 large) were applied and recorded. The oracle
  evaluated all 57 (0 failures) and stored 114 oracle calls separately from 118 participant
  calls (all participant replies shown, no oracle output shown).
- The records report showed allocation {1: 1, 3: 1, 4: 1} with 9 slots free; 3 study and 6
  development sessions (excluded); per-task status, elapsed time, constraints, checkpoints,
  messages, and workload; oracle labels small 12 / large 12; final choice matched the
  oracle label at 9 of 24 checkpoints.
- No backend errors; every model request carried the key.
- **Not done:** real OpenAI/Ollama calls, the `mf` RouteLLM router (needs a key),
  WSL2/Linux and Windows-browser runs, screen readers, a timeout reached in real time
  (covered by tests with a controlled clock), concurrent real participants.

## Open decisions and approvals (for Nick and the researchers)

This is technical readiness for a pilot, not approval for participant collection or a
substitute for IRB approval.

- **Contract (#31):** agree the HTTP draft, especially the task in the path, server-side
  deadlines, `ALLOCATION_FULL` after 12 sessions (or a new block), and `DEV_CONTROLS`.
- **Models (#35):** GPT-4 Turbo availability; Mixtral 8x7B needs ~32 GB of memory. Any
  substitution needs approval and must be recorded.
- **Agent (#36):** a plain bounded tool loop is used instead of LangGraph; the agent
  suggests but never edits the plan.
- **Router (#37):** which RouteLLM router (`mf` matches the paper's model pair) and the
  threshold (scores clustered in 0.38–0.50 here, so calibrate in the pilot); wording of
  the "Router estimate" reasons.
- **Oracle (#40):** the per-stage pass rule, the `neither` case, and any reliance formula.
- **Records (#38):** latency and token-accounting definitions; raw events are kept.
- **Materials:** consent, demographics, practice treatment, catalog values, live
  constraint feedback, adapted NASA-TLX, feedback prompts, and the before-start
  "refreshing restarts" acknowledgement (true only in mock mode).
