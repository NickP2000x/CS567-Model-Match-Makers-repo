# Backend verification

## README quickstart verification (2026-10-25)

- README now places shell commands, manual equivalents, and default database/CSV/
  calibration locations together before the detailed frontend/backend sections.
- **130 backend tests**, **75 offline frontend tests**, frontend type-check/build,
  and all **six API integration checks** passed. The six API checks were skipped
  in the offline frontend command as intended, then run against the isolated server.
- Executed manual first-time setup in a fresh temporary checkout whose path contains
  spaces: Python 3.12 venv, isolated pip install/check of pinned development
  requirements, Node 24.14.0, `npm ci`, and frontend production build. The shell
  setup readiness check passed against that installation.
- Actual manual Uvicorn and npm/Vite commands passed browser consent-to-practice,
  a simulated message, and separate-terminal shutdown. Verified `stop.sh` did not
  stop those untracked manual servers.
- Actual shared-terminal and two-pane tmux launchers both passed browser/API session
  creation, same-tab resume, and stop-command cleanup of both listening ports.
- Actual shell wrappers and manual Python commands both produced dry calibration
  reports and 13 linked CSVs in the documented default directories. Verified
  manifests/dictionary, zero provider calls, and unchanged source database bytes.
- All services and data lived in temporary storage on alternate local ports.
  No developer `.env` was copied and no working study database was used. The first
  browser-verifier attempt needed an explicit wait for API navigation; a later
  harness log-pipe blockage was fixed by running API checks asynchronously. Neither
  required an application change.
- Optional heavyweight RouteLLM installation was not repeated clean, real provider
  calibration was not run, and actual macOS/native Windows-browser checks remain
  unperformed. Existing setup/install-command tests and prior installed-package
  checks cover the optional setup path; these results do not validate a study cutoff.

## #67–#68 — offline calibration and CSV export (2026-10-25)

- **130 backend tests passed**, including 35 new offline-tool checks. Tests use
  temporary/in-memory databases, scripted clients/scorers, and synthetic data;
  settings were isolated from the developer `.env` and unrelated ROS plugins using
  the key-free pytest invocation documented below.
- CSV coverage: linked sessions/tasks/messages/choices, raw survey/metadata retention,
  original stored scores, development/practice filtering, participant/oracle purpose,
  earlier missing tables/columns, null unvisited placeholders, invalid non-object
  state rejection, empty stable headers, Unicode/quotes/multiline
  text, reversible null escaping, orphan warnings, unique output folders, read-only
  rejection of writes, byte-for-byte source preservation, and a WAL snapshot that
  excludes a concurrent writer's later session.
- Calibration coverage: all 24 A/B stage contexts, immutable in-memory catalog,
  paired identical prompts, alternating evaluation order, both/neither/large-only
  outcomes, absent submitted plans, provider/router failures without mock fallback,
  secret-free metadata, exposed checkpoint identity, score/threshold equality and
  limits, adaptive narrow-band thresholds, holdout isolation, explicit real-mode
  gates, error artifacts, and unchanged configured participant database.
- Both actual CLIs passed on a fresh synthetic database under temporary storage.
  Export produced 13 linked CSVs plus manifest/dictionary and preserved database
  bytes and multiline feedback. Dry calibration evaluated 24 simulated contexts,
  produced a threshold report, and recorded zero provider calls. Invalid provider
  settings in the subprocess environment did not affect export or dry-run mode.
- Default export/calibration output directories were verified ignored by Git.
  No existing developer session/database was exported or modified, and `.env`
  was not inspected or changed during verification. No real model/router calls,
  checkpoint downloads, actual threshold calibration, or study approval are claimed.
- Shell-wrapper follow-up: `scripts/calibrate.sh` and `scripts/export-csv.sh` passed
  Bash syntax checks and six focused backend tests. Verified automatic interpreter
  selection, execution from outside a checkout whose path contains spaces, quoted
  argument forwarding, required explicit calibration modes, help, dependency/setup
  errors, exit-code propagation, default/custom database selection, and unchanged
  synthetic source bytes. Actual dry-run/export CLIs ran through the wrappers;
  an additional direct wrapper smoke check ran from `/tmp` with temporary output.
  No real calibration or export of developer data was performed. Actual macOS
  wrapper execution was not available; syntax remains Bash 3.2 compatible.
- Commands, artifacts, provisional criteria, and coverage limits are documented in
  [offline tools](offline-tools.md). A synthetic dry-run cutoff is not a research
  result; main-study selection still requires representative pilot/holdout evidence.

## #65 — expanded catalogs and participant copy (2026-10-24)

- Regenerated catalog-v2, reference plans (including additional feasible examples),
  and before-start v2 definitions from the frontend sources. Practice has eight
  items; A/B each have 18 (six per category). The four constraints and original
  item IDs/prices/scored facts are preserved.
- Focused catalog/session checks passed, followed by all **95 backend tests**.
  New coverage includes alternative feasible costs, new distractors, summary/detail
  boundaries, and reseeding an old-format temporary catalog without changing saved
  session JSON/timestamps or original item facts.
- An existing missing-RouteLLM test assumed the optional package was absent; it
  now explicitly simulates import failure, so installed RouteLLM cannot trigger
  checkpoint downloads during the test. Agent-tool expectations include six venues.
- All **six API integration tests**, including all four sequences and refresh/deadline
  preservation, passed against a separate mock backend and temporary database.
- Pytest was isolated from unrelated ROS plugin autoload and the developer `.env`:

  ```bash
  # From backend/, using its Python environment; no .env or real providers loaded.
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 MODEL_MODE=mock ROUTER_MODE=mock python -c \
    'from app.config import Settings; Settings.model_config["env_file"] = None; import pytest; raise SystemExit(pytest.main([]))'
  ```

- Browser/copy checks and coverage boundaries are recorded in
  [catalog/copy verification](../frontend/catalog-copy-verification.md).
  Existing developer session data was not used or modified. No live provider/router
  checks, threshold calibration, or researcher approval are claimed.

### User-run small-model timeout diagnostic (2026-10-24)

- Read-only inspection found a practice Qwen3.5 request failing on its first call
  with `ollama unreachable (TimeoutError)` at 60.07 seconds; earlier errors were
  `URLError`. These failed call records were preserved.
- Windows Ollama was reachable from WSL at the user's established host address;
  `/api/version` reported 0.40.3 and `/api/ps` initially listed no loaded models.
- An explicit local-only `ChatClient` call to `qwen3.5:9b` succeeded in 18.61 seconds
  with 17 prompt / 129 completion tokens and final reply `OK`. A subsequent
  practice-agent venue question succeeded in 5.94 seconds with two calls and
  `search_catalog`, using an isolated temporary database.
- No `.env` was inspected, no cloud model calls were made, and no participant
  session was changed by these diagnostics. They establish current local-model/
  agent availability at that explicit endpoint, not the effective configuration
  of the previously stopped server or completion of a new browser trial.

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

## Back to Task from the ratings page (provisional)

Requested during review: after Submit Plan, a "Back to Task N" button on the ratings page
reopens the submitted task. It is a change to the study rule that submission is final, so
it is marked provisional pending researcher approval (root `AGENTS.md`).

- Allowed only for a submitted experimental task whose ratings are not yet submitted and
  whose original deadline has not passed. The deadline and timer are unchanged; plan,
  decisions, messages, and partial ratings are kept; each return is recorded in
  `task.reopens` and counted by `python -m app.records`.
- Same rule in the frontend mock (`reopenTask`) and the backend
  (`POST /api/sessions/{sid}/tasks/{taskId}/reopen`).

### Recorded results — 2026-10-10

- Backend: 93 tests passed (3 new). Frontend: 49 passed with 6 skipped by default (3 new),
  and 55 passed against a live mock-mode backend (the four-sequence runs now go back to
  each task once and submit again).
- Headless browser, production build: Submit Task 1 → ratings showed "Back to Task 1" →
  Task 1 returned with the timer running and the plan item and stage model kept →
  Submit Plan → ratings → Task 2 preparation; the backend recorded one return. No errors.
