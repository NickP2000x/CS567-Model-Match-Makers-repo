# Frontend instructions

Read root `../AGENTS.md` first. It owns shared research invariants, current phase,
data-handling rules, Git workflow, and PR approval/merge control. Do not duplicate
or override those rules here. These instructions also apply to root `scripts/`
and documentation when a change affects frontend development.

## Stack and structure

- Use React, TypeScript, and Vite with plain components and strict TypeScript.
- Browser source lives in `frontend/src/`; dependencies, configuration, tests, and
  generated output stay in `frontend/`.
- Add feature-specific UI under `src/features/`, genuinely shared controls under
  `src/components/`, experiment interfaces/implementations under `src/services/`,
  and synthetic fixtures under `src/mocks/` when actual work needs those files.
- Keep `App.tsx` focused on composing screens. Do not build a design-system
  showcase, mobile redesign, or generic framework.
- Components access mock behavior through the replaceable experiment service,
  never by importing router/agent response fixtures directly. Keep mocks in
  ordinary version-controlled files.

## Local development

- Support WSL2 Ubuntu, native Linux, and macOS. OS detection belongs only in setup
  tooling; browser behavior and generated static assets remain OS-independent.
- From the repository root, run `bash scripts/setup.sh`, then
  `bash scripts/frontend.sh dev`. See `../docs/frontend/development-setup.md` for details.
- Setup selects pinned native Node/npm or prepares them under ignored `.tools/`.
  The launcher selects that runtime each time; never rely on Windows npm in WSL.
- Do not install system packages or modify shell profiles through project tooling.
- Require no `.env` or keys. All browser configuration, including `VITE_*`, is
  public. Add `.env.example` only if safe non-secret configuration is necessary.
- Keep dependencies, generated builds, local runtime downloads, and environment
  files ignored by Git. Preserve the lockfile for reproducible installation.

## UI and verification

- Before continuing frontend work, read the relevant handoffs in
  `../docs/frontend/introduction-verification.md`,
  `../docs/frontend/workspace-verification.md`,
  `../docs/frontend/routing-verification.md`,
  `../docs/frontend/workload-verification.md`, and
  `../docs/frontend/study-flow-verification.md`, plus the shared
  `../docs/experiment-service-contract.md` and `../docs/project-structure.md`.
  Verify the current issue/code/Git state; recorded results describe the tested
  version, not automatic approval of subsequent changes.

- Apply the root research invariants to every screen and state transition.
- Use semantic controls, labels, visible focus, keyboard access, and readable
  laptop layouts. Clearly label simulated behavior and provisional research copy.
- Keep loading/error handling simple; avoid duplicate actions or lost current work.
- From the repository root, run:

  ```bash
  bash scripts/frontend.sh type-check
  bash scripts/frontend.sh test
  bash scripts/frontend.sh build
  ```

- Use focused tests for behavioral changes; documentation-only edits need link/path
  and diff checks rather than new tests or a full build.
- For meaningful UI changes, run the relevant manual checks and use
  `bash scripts/frontend.sh preview` when checking production output.
- Final complete-flow smoke checks belong to issue #22. Report actual platform and
  browser results separately from simulated checks; never claim unperformed testing.
