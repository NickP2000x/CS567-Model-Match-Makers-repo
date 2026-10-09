# Backend documentation handoff

Backend implementation and startup instructions are not present yet. This page
identifies the planned work and documentation locations; it does not authorize
backend code under the current frontend-only root guidance.

## Start Backend Sprint 1

Read [root `AGENTS.md`](../../AGENTS.md), the selected GitHub issue and dependencies,
the [shared service contract draft](../experiment-service-contract.md), and the
[project structure](../project-structure.md). Inspect current code and Git state;
do not assume a draft contract has been jointly approved.

[Sprint tracker #28](https://github.com/NickP2000x/CS567-Model-Match-Makers-repo/issues/28)
orders the work:

1. [#31 — API contract](https://github.com/NickP2000x/CS567-Model-Match-Makers-repo/issues/31):
   jointly review operations, IDs, units, payload/error shapes, and transitions with
   the frontend owner. The shared contract stays at `docs/experiment-service-contract.md`.
2. [#32 — Backend setup and guidance](https://github.com/NickP2000x/CS567-Model-Match-Makers-repo/issues/32):
   update root guidance to authorize explicit backend tasks, add `backend/AGENTS.md`,
   and document pinned Python/FastAPI setup and key-free mock startup.
3. [#33 — SQLite catalog](https://github.com/NickP2000x/CS567-Model-Match-Makers-repo/issues/33):
   coordinate synthetic practice/A/B fixtures and stable item IDs with the frontend.
4. [#34 — Sessions and study state](https://github.com/NickP2000x/CS567-Model-Match-Makers-repo/issues/34):
   persist synthetic sessions and assignments, enforce legal transitions, and verify
   balanced allocation and reopening without reassignment.

## Documentation to add with implementation

- `docs/backend/development-setup.md`: supported Python version, virtual environment,
  dependencies, mock-mode startup, health check, SQLite setup, and verification commands.
- `docs/backend/verification.md`: repeatable checks, actual results, platform/model
  checks not performed, and unresolved decisions as backend issues are completed.
- `backend/AGENTS.md`: backend-specific instructions and links to those documents.
- [Main README](../../README.md): backend quick start linked to the detailed setup.

These setup/verification files should be written from the implemented commands,
not invented in advance. Keep shared protocol rules in root `AGENTS.md` and shared
API decisions in the existing contract. Frontend-specific documentation is under
`docs/frontend/`; standalone frontend mock mode must remain independently runnable.
