# Frontend development setup

The prototype uses React, TypeScript, and Vite. From the repository root:

```bash
bash scripts/setup.sh
bash scripts/frontend.sh dev
```

You do not need to install Node or nvm first. Setup selects a compatible native
Node **24.14.0** with bundled npm, or downloads the official pinned runtime into
ignored `.tools/`. It verifies the archive's SHA-256 before extraction, installs
frontend dependencies from the lockfile, type-checks, and builds. Subsequent runs
reuse the local runtime. Windows Node/npm is never selected for a Linux build.

Git is required; first-time runtime download also needs curl, tar, mktemp, and
sha256sum or shasum. These tools are normally present on Ubuntu/macOS. Missing
system tools get manual installation guidance. Internet access is needed for
first-time Node/dependency downloads. Setup does not use sudo, install system
packages, modify shell profiles, or create `.env`. No keys/backend are required.

## WSL2 Ubuntu

Use an Ubuntu terminal inside WSL2 and keep the checkout in its Linux filesystem,
for example `~/projects/model-matchmakers`. Windows Node/npm is not a replacement
for Linux Node inside WSL.

If Git is missing, manually run `sudo apt update` and `sudo apt install git`.
If download tools are missing, manually install them with
`sudo apt install curl tar coreutils`. Then rerun setup; Node/npm are prepared
locally without requiring Ubuntu's Node package or a Windows installation.

## Native Linux

Install Git with your distribution's package manager (on Ubuntu: `sudo apt update`
and `sudo apt install git`). On Ubuntu, missing download tools can be installed
with `sudo apt install curl tar coreutils`. Other distributions use their package
manager. Setup handles Node/npm locally on supported x64/arm64 Linux systems.

## macOS

Run `git --version`; if Git is missing, manually run `xcode-select --install` and
finish Apple's installer. curl, tar, mktemp, and shasum normally ship with macOS.
Setup handles Node/npm locally for Intel and Apple Silicon; Homebrew is not
required. The scripts use Bash 3.2-compatible syntax. Actual macOS testing must
still be recorded separately from simulated platform checks.

## Prepare the workspace

Clone this repository, open its root directory, and run:

```bash
git --version
bash scripts/setup.sh
```

Setup reports the environment and selected Node/npm versions. The pin remains in
`frontend/.nvmrc` and `frontend/package.json`. Re-running setup is supported.
It can also be invoked from another directory with its absolute path.
Use `bash scripts/setup.sh --check` to check readiness without any download or
dependency installation. If it reports no ready runtime, run normal setup.

```bash
bash scripts/frontend.sh dev
```

Open the displayed URL, normally <http://localhost:5173>, in your browser. On WSL2,
open it in a **Windows browser**; WSL2 normally forwards localhost automatically.
If forwarding is unavailable, inspect your WSL networking settings first. For a
network-accessible preview you can explicitly run
`bash scripts/frontend.sh dev --host 0.0.0.0`
and use your WSL address. Linux and macOS use their local browser.

## Checks and static preview

```bash
bash scripts/frontend.sh type-check
bash scripts/frontend.sh test
bash scripts/frontend.sh build
bash scripts/frontend.sh preview
```

Preview normally uses <http://localhost:4173>. `frontend/dist/` holds the portable static
assets, with relative asset URLs. A standard static server can serve this directory;
neither setup tooling nor the developer OS is needed at runtime. Actual internet
deployment is outside this issue and prototype phase.

All commands above run from the repository root. The launcher selects the runtime
and bundled npm each time; it works even if your terminal still cannot find
`node`. Setup cannot change its parent terminal's PATH, and does not try to.
Existing native Node users may also use normal npm commands inside `frontend/`.
The launcher accepts dev/build/preview/type-check/test and forwards extra arguments.
It never installs/downloads on launch; run setup first if anything is missing.

Download attempts are retained under ignored `.tools/downloads/`; failed downloads
are not reused. An incomplete extracted runtime is reported rather than silently
overwritten; move the indicated directory aside manually before retrying. A Node
binary that cannot run may indicate an unsupported Linux distribution or OS version.

Shared setup tooling stays in root `scripts/`; frontend dependencies, tests,
configuration, and build output stay in `frontend/`. `.tools/` is local developer
tooling only: hosting uses `frontend/package.json` and `frontend/dist/`, not these
downloads. No backend or deployment configuration is introduced.

The tests exercise platform detection, native/local runtime selection, checksum
failure, download failure, check-only behavior, runtime reuse, and launcher arguments
with isolated fixtures. They do **not** substitute for a
real macOS/browser smoke check. Keep actual platform verification results explicit.

For the current consent/demographics/tutorial screens, see
[`introduction-verification.md`](introduction-verification.md) for the focused
browser checklist and recorded results. For the three-panel practice workspace and
Sprint 1 flow, see [`workspace-verification.md`](workspace-verification.md).
For automatic/override routing checks and the full-flow integration handoff, see
[`routing-verification.md`](routing-verification.md).
For the word-anchored NASA-TLX component and scoring, see
[`workload-verification.md`](workload-verification.md).
For the now-connected two-task flow, timers, development-only sequence/reset/timeout
controls, production guard, and Sprint 3 handoff, see
[`study-flow-verification.md`](study-flow-verification.md).
For the current #51 preparation/start gates, visual guide, five-point ratings,
optional feedback and #22 checks, see
[`study-refinements-verification.md`](study-refinements-verification.md).

## Backend (API) mode

By default the frontend uses the in-memory mock and needs no backend. To run it
against the backend instead (#39), start the backend first (see
[backend setup](../backend/development-setup.md)), then set `VITE_API_BASE_URL`:

```bash
# Terminal 1 (from backend/, .venv active). DEV_CONTROLS is needed for the dev server.
DEV_CONTROLS=true python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# Terminal 2 (repository root)
VITE_API_BASE_URL=http://127.0.0.1:8000 bash scripts/frontend.sh dev
```

Or copy `frontend/.env.example` to `frontend/.env.local` (ignored by Git) and uncomment
the variable. In API mode:

- The development server creates development sessions (sequence 1, `dev-…` IDs) and
  the Development controls reset through the backend. The backend must run with
  `DEV_CONTROLS=true`, otherwise a "could not start a study session" screen explains it.
- A production build (`VITE_API_BASE_URL=… bash scripts/frontend.sh build`, then
  `preview`) takes one of the twelve balanced allocation slots per new browser
  session and hides the development controls. Delete the backend database file to
  reset the slots.
- The session ID is kept in `sessionStorage`, so a refresh resumes the same session
  and deadline; closing the tab starts a new one.
- `VITE_*` values are public. Never put keys there; model keys stay in `backend/.env`.

Optional contract check against a running backend (mock mode, `DEV_CONTROLS=true`):
`MM_API_URL=http://127.0.0.1:8000 bash scripts/frontend.sh test`. Without
`MM_API_URL` those integration tests are skipped.

## AI-assisted work

Read [root `AGENTS.md`](../../AGENTS.md),
[`frontend/AGENTS.md`](../../frontend/AGENTS.md), and the selected GitHub issue and
dependencies before editing. [Root `CLAUDE.md`](../../CLAUDE.md) points Claude Code
to the same instructions. General skills are optional, not required dependencies.
Restart/refresh agent sessions when instruction files change if your tool caches
them. The repository owner approves PRs and handles merges.
