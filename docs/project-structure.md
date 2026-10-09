# Project structure

The repository currently contains the frontend prototype only. Keep its structure
small and leave a clear boundary for a backend later.

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
    App.tsx               Service-backed introduction screen composition
    styles.css            Basic shared styles
    features/introduction/ Consent, synthetic demographics, and tutorial screens
    services/             Typed in-memory experiment service and React subscription
    mocks/                Synthetic scenario/catalog and simulated response fixtures
  tests/
    setup.test.mjs        Focused setup verification
    experiment.test.mjs   Offline mock service and contract verification
  node_modules/           Installed dependencies, ignored by Git
  dist/                   Generated static assets, ignored by Git
scripts/
  setup.sh                Local Node bootstrap and frontend setup
  runtime.sh              Shared native/local Node and bundled npm selection
  frontend.sh             Dev/check/build launcher using the selected runtime
.tools/                   Local runtimes/downloads, ignored by Git
docs/
  development-setup.md     Installation and preview instructions
  project-structure.md     Repository boundaries
backend/                  Reserved location for future backend work; not created yet
```

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
The workspace in #7 should follow its three-column arrangement: Catalog on the
left, AI planning agent in the middle, Current event plan on the right; requirements
and time remaining across the top, Submit at the bottom right. Introduction screens
use the same palette with a plain single-column form/tutorial layout. Apply the
root research rules to interactions; the visual mockup does not override initial
choice concealment, the four checkpoints, or the four research constraints.

## Future backend boundary

When backend work is separately authorized, place it under `backend/` with its own
dependencies, configuration, tests, and documentation. Frontend npm commands live
in `frontend/package.json`; from the repository root use `bash scripts/frontend.sh`
with dev/build/preview/type-check/test. Backend dependencies must not be needed to start the mock
prototype. Do not place server code, private configuration, or credentials in
`frontend/src/`, browser assets, or `VITE_*` variables.

The experiment service contract will be defined in issue #3. A future network
adapter can implement that contract without making UI components aware of Python,
database tables, or provider credentials. Mock and real modes must be explicit,
not silently mixed. Authoritative assignment, deadlines, persistence, real model
calls, and study measurements belong to that future phase, not this scaffold.

The development OS affects tooling only. The browser build must not branch on WSL,
Linux, or macOS, and its generated `frontend/dist/` assets remain portable.
