# Combined setup and development launcher

Follow-up requested during #65 implementation. These scripts are local developer
conveniences, not participant deployment tooling or a calibration pipeline.

## Commands

From the repository root (or use the script's absolute path):

```bash
bash scripts/setup-all.sh --routellm
bash scripts/setup-all.sh --check --routellm
bash scripts/run.sh
bash scripts/run.sh --tmux
bash scripts/stop.sh
```

Python 3.12 is an existing prerequisite. Full setup reuses `scripts/setup.sh`
for pinned Node/npm, `npm ci`, type-check/build; prepares `backend/.venv`; installs
`requirements-dev.txt` and optionally `requirements-routellm.txt`; checks installed
packages and runs `pip check`. Isolated Python mode ignores inherited Python paths
and user packages. `--check` performs no installs or app/SQLite initialization.
No `.env` is sourced, printed, created, or changed by setup. Existing incompatible
or incomplete virtual environments are not overwritten. OS prerequisites and
Ollama/model downloads/cloud sign-in remain manual on the appropriate machine.

The launcher uses the existing backend configuration through normal app startup,
sets `DEV_CONTROLS=true`, sets local CORS origins for the chosen frontend port,
and forces the frontend's API URL to the backend. Servers bind only to localhost.
Logs share the terminal. Separate process groups allow Ctrl+C/termination and
unexpected server exit to stop both services, including reload workers, without
stopping unrelated servers. Ports are checked before startup; Vite uses strictPort.
The port probe uses SO_REUSEADDR so TIME_WAIT from recently closed connections
does not falsely reject a free port. Active listeners still block launch.

One launch per checkout is tracked in ignored `.tools/dev-run.state` using the
launcher PID and process identity. Linux/WSL uses `/proc` start ticks plus boot ID,
not `ps lstart`, whose derived timestamp can shift after clock synchronization.
macOS uses `ps` start time in UTC to avoid caller timezone differences. The helper
is `scripts/process-identity.sh`. `stop.sh` verifies identity, sends TERM to the
launcher, and waits for cleanup. Stale/mismatched identities are not signaled.
Cleanup clears its own record, signals the frontend group and backend supervisor,
then escalates only its own remaining groups if graceful shutdown stalls.
Short readiness probes let a stop interrupt initial router loading promptly.

Optional `--tmux` requires an existing tmux installation. A private tmux server
inherits this launch's environment; backend logs are on the left and Vite runs
as the foreground process in a right-hand pane after backend readiness. Ctrl+C
in either pane stops the pair. Ctrl+B then D detaches without stopping; `stop.sh`
can stop it later. Other tmux sessions are untouched. Existing tmux/non-TTY callers
receive an attach command. Windows Ollama and separately started servers are not
managed by stop. Python/model-library shutdown warnings are not suppressed.
The default `tmux ls` does not list this private server; the printed `-L` socket
name is required. Older unprefixed wall-clock records need one manual Ctrl+C stop
before restarting; stop never relaxes PID-reuse checks to accept a mismatched time.

Overrides:

```bash
MM_BACKEND_PORT=8001 MM_FRONTEND_PORT=5174 bash scripts/run.sh
MM_START_TIMEOUT_SECONDS=300 bash scripts/run.sh
```

The default readiness timeout is 180 seconds, allowing initial router loading.
Stop previously launched servers or choose free ports. Both scripts use Bash
3.2-compatible syntax and the existing Linux/WSL/macOS runtime detection. Native
Windows PowerShell still uses the separate instructions in `RUNNING.md`.

## Recorded verification — 2026-10-24

- `bash -n` passed for both scripts.
- Final frontend suite: 74 passed, with six API tests skipped in the offline run;
  those six had passed separately against the isolated backend. Type-check/build
  and all 95 backend tests also passed during #65 verification.
- Setup/launcher focused tests passed: missing prerequisites, create/reuse Python
  environment, pinned install commands with/without RouteLLM, install failure,
  incomplete/incompatible environments, noninstalling checks, invalid/conflicting
  ports, readiness timeout, backend/frontend failure, and SIGINT/SIGTERM shutdown
  of both server groups plus a simulated reload worker. Paths with spaces and
  invocation outside the checkout are exercised.
- Simulated Ubuntu, WSL2, and macOS Intel/Apple Silicon platform paths passed.
  These fixtures run on Linux and do not establish native macOS process/wheel support.
- Actual WSL `setup-all.sh --check --routellm` passed against installed dependencies.
  An initial check exposed unrelated ROS packages via inherited `PYTHONPATH`;
  isolated Python package checking fixed this without altering the environment.
- Actual clean base setup passed in a temporary checkout: real `npm ci`, frontend
  strict type-check/Vite build, new Python 3.12 venv, pinned backend development
  dependency installation, import availability, `pip check`, then `--check`.
  The heavyweight optional RouteLLM clean install was not repeated: its install
  commands are fixture-tested and installed-package checks passed.
- Actual `run.sh` launched real FastAPI/Uvicorn with reload and Vite against a
  temporary mock backend and database. Health, browser session creation, CORS,
  same-tab refresh/resume, and Ctrl+C cleanup of both listening ports passed.
  No developer `.env` was copied and no provider calls were made.
- Shutdown follow-up: reproduced the old preflight failure with a recently closed
  socket before fixing it; immediate restart now passes. Stop/restart, duplicate
  launch refusal, stale PID safety, and stopping during a 180-second readiness wait
  passed. Actual tmux tests verified two panes and cleanup by stop command and
  Ctrl+C in either pane. Both real normal-mode and real tmux-mode Uvicorn/Vite
  browser session/health/CORS/resume/shutdown checks passed on temporary data.
- WSL identity follow-up: a real launch's saved `ps lstart` and later `ps` result
  differed by ten seconds for the same verified tmux pane/launcher PID. Replaced
  Linux wall-clock identity with boot ID/kernel start ticks and added a regression
  that changes the apparent `ps` time while stop remains valid. All 17 launcher
  checks passed, including simulated macOS paths.
- Browser fixtures/tooling and clean-install dependencies remained under temporary
  storage outside the repository. Existing developer dependencies/configuration/
  database were not changed by these checks.

Actual macOS/native desktop Ubuntu and Windows-browser checks were not performed;
WSL browser checks used headless Chromium. Launcher verification used mock models;
separate local Qwen timeout diagnostics are recorded in
[backend verification](../backend/verification.md). Cloud-provider calls and routing
calibration were not run. No calibration script was built.
