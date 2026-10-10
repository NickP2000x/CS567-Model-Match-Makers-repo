# Project structure

The repository contains the frontend prototype and a minimal mock-mode backend
scaffold. Keep both small, with a clear boundary between them.

```text
AGENTS.md                 Shared project/research rules and local-guidance pointers
CLAUDE.md                 Single Claude Code pointer to applicable instructions
frontend/
  AGENTS.md               Frontend stack, structure, commands, and checks
  package.json            Frontend dependency and command definitions
  package-lock.json       Reproducible frontend dependencies
  .nvmrc                  Pinned frontend Node version
  index.html              Vite browser entry
  vite.config.ts          Frontend build configuration
  tsconfig.json           Frontend TypeScript configuration
  src/
    main.tsx              Browser bootstrap
    App.tsx               Complete study screen composition and action/termination guards
    styles.css            Basic shared styles
    features/introduction/ Consent, demographics, acknowledgement/start pages, visual guide
    features/planning/    Catalog/details, stage/conversation, plan and practice
    features/routing/     Simulated automatic/override checkpoint interactions
    features/workload/    Reusable word-anchored NASA-TLX survey
    features/study/       Progress, optional feedback, countdown, development-only controls
    services/             Experiment service contract, in-memory mock, API adapter (#39), React subscription
    mocks/                Synthetic scenario/catalog and simulated response fixtures
  tests/
    setup.test.mjs        Focused setup verification
    experiment.test.mjs   Offline mock service and contract verification
    workload.test.mjs     Survey scoring, metadata, validation, and task linkage
    timing.test.mjs       Deadline/termination and stale-operation checks
    refinements.test.mjs  Acknowledgement/start gates and optional feedback checks
    api-adapter.test.mjs  Offline API adapter checks with a scripted fetch
    api-integration.test.mjs Opt-in adapter run against a live backend (MM_API_URL)
  node_modules/           Installed dependencies, ignored by Git
  dist/                   Generated static assets, ignored by Git
scripts/
  setup.sh                Local Node bootstrap and frontend setup
  runtime.sh              Shared native/local Node and bundled npm selection
  frontend.sh             Dev/check/build launcher using the selected runtime
.tools/                   Local runtimes/downloads, ignored by Git
docs/
  project-structure.md     Repository boundaries
  experiment-service-contract.md Shared frontend/backend contract and decisions
  frontend/
    development-setup.md   Frontend installation and preview instructions
    introduction-verification.md Introduction checks and recorded results
    workspace-verification.md Practice/Sprint 1 checks and recorded results
    routing-verification.md Routing checks and #16 integration handoff
    workload-verification.md Survey/scoring checks and #16 integration handoff
    study-flow-verification.md Complete flow/results and #22 handoff
    study-refinements-verification.md #51 gates/visual guide/scale/feedback and #22 handoff
  backend/
    README.md              Backend work/documentation handoff
    development-setup.md   Python environment, mock-mode startup, and configuration
    verification.md        Backend checks and recorded results
backend/
  AGENTS.md               Backend stack, API/secret rules, commands, and checks
  .python-version         Pinned Python version (3.12)
  requirements.txt        Pinned runtime dependencies
  requirements-dev.txt    Pinned test dependencies
  .env.example            Safe placeholders; real .env files are ignored by Git
  pytest.ini              Test configuration
  app/
    main.py               FastAPI app factory and health check
    routes.py             /api routes from the #31 HTTP draft
    study.py              Study rules ported from the frontend mock service
    store.py              Session allocation and per-request JSON state persistence
    catalog.py            Catalog queries and the four constraint checks
    db.py                 SQLite schema, catalog seeding, allocation slots
    definitions.py        Sequences, checkpoints, and provisional materials
    config.py             Server-only settings with mock-mode defaults
    errors.py             Shared {"error": {code, message}} envelope
    fixtures/             Catalog/definitions exported from the frontend mock
  scripts/export_fixtures.mjs  Regenerates fixtures from frontend sources
  tests/                  Focused key-free backend tests
  .venv/                  Local virtual environment, ignored by Git
```

## Documentation ownership

Use `docs/frontend/` for frontend setup and verification handoffs and
`docs/backend/` for backend-specific documentation. Keep the shared repository
layout and experiment service contract directly in `docs/` so neither component
maintains a duplicate protocol/API contract. The main README links to both areas.

Frontend entry points: [setup](frontend/development-setup.md),
[introduction checks](frontend/introduction-verification.md), and
[workspace checks](frontend/workspace-verification.md), and
[routing checks/integration handoff](frontend/routing-verification.md), and
[workload survey handoff](frontend/workload-verification.md), and
[full study flow](frontend/study-flow-verification.md), and
[current refinements / #22 handoff](frontend/study-refinements-verification.md).
Backend entry points: [handoff](backend/README.md),
[setup](backend/development-setup.md), and [verification](backend/verification.md). Component `AGENTS.md` files should point to their own
documentation and the shared contract; root research rules remain canonical.

The three earlier root-level frontend documents remain as legacy copies pending
manual cleanup. Their canonical versions are now under `docs/frontend/`.

## As frontend issues are implemented

Read root `AGENTS.md` for shared rules and `frontend/AGENTS.md` for local guidance.
The single root `CLAUDE.md` directs Claude Code to read both; a frontend-specific
`CLAUDE.md` is unnecessary. Keep shared protocol rules only in the root file.

Add directories only when actual code needs them:

- `frontend/src/features/`: participant introduction, planning, routing, workload survey,
  and study-flow UI. Keep feature-specific components with their feature.
- `frontend/src/components/`: small controls genuinely shared between features.
- `frontend/src/services/`: the experiment service contract and implementations.
- `frontend/src/mocks/`: synthetic catalogs, scenarios, assignments, and agent responses.
  Only the mock service imports response fixtures; UI uses the service interface.
- `frontend/tests/`: focused tests and the eventual smoke checklist. Feature tests may also
  live alongside the feature they verify.

Do not add empty directory trees, barrel-file frameworks, or a generic utilities
layer before there is a concrete need. The root app composes screens; it should
not grow into the mock service or contain catalog/response fixtures.

## Interface visual reference

The intended planning interface is `event-planning-mockup-small.png` in the
[Overleaf paper project](https://www.overleaf.com/read/yjwtghwfqtqp#635087).
Use its dark neutral panels, restrained blue highlights, and bordered controls.
The workspace in #7 follows its three-column arrangement: Catalog on the
left, AI planning agent in the middle, Current event plan on the right; requirements
and time remaining across the top, Submit at the bottom right. Introduction screens
use the same palette with a plain single-column form/tutorial layout. Apply the
root research rules to interactions; the visual mockup does not override initial
choice concealment, the four checkpoints, or the four research constraints.

## Backend boundary

Backend work for an explicitly selected backend issue stays under `backend/` with its
own dependencies, configuration, tests, and `backend/AGENTS.md`. Add backend modules
only when an issue needs them (catalog/SQLite in #33, sessions in #34). Frontend npm commands live
in `frontend/package.json`; from the repository root use `bash scripts/frontend.sh`
with dev/build/preview/type-check/test. Backend dependencies must not be needed to start the mock
prototype. Do not place server code, private configuration, or credentials in
`frontend/src/`, browser assets, or `VITE_*` variables.

The experiment service contract draft from issue #3 lives in
`docs/experiment-service-contract.md`; joint API review is #31. A future network
adapter can implement that contract without making UI components aware of Python,
database tables, or provider credentials. Mock and real modes must be explicit,
not silently mixed. Authoritative assignment, deadlines, persistence, real model
calls, and study measurements belong to that future phase, not this scaffold.

The development OS affects tooling only. The browser build must not branch on WSL,
Linux, or macOS, and its generated `frontend/dist/` assets remain portable.
