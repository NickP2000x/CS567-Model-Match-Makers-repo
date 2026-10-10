# Backend documentation handoff

The backend under `backend/` implements backend sprints 1–3 (#31–#41) for review:
mock mode by default, with optional real models, RouteLLM routing, an offline oracle,
and a records summary. Results and open decisions are in [verification](verification.md).
This page identifies the planned work and documentation locations.
Backend work is authorized only for an explicitly selected backend issue, following
root `AGENTS.md` and [`backend/AGENTS.md`](../../backend/AGENTS.md).

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

## Backend documentation

- [Development setup](development-setup.md): Python 3.12, virtual environment,
  pinned dependencies, mock-mode startup, health check, and configuration. Add
  SQLite setup with #33.
- [Verification](verification.md): repeatable checks, actual results, platform/model
  checks not performed, and unresolved decisions, extended as backend issues land.
- [`backend/AGENTS.md`](../../backend/AGENTS.md): backend-specific instructions.
- [Main README](../../README.md): backend quick start linked to the detailed setup.

Update these files from the implemented commands as each issue lands; do not
document behavior in advance. Keep shared protocol rules in root `AGENTS.md` and shared
API decisions in the existing contract. Frontend-specific documentation is under
`docs/frontend/`; standalone frontend mock mode must remain independently runnable.
