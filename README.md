# Model Matchmakers

A frontend research demonstration for **Human Override in Automatic LLM Routing:
A User Study**. The study compares automatic model routing with participant
override of router recommendations during an event-planning task. This prototype
uses simulated router and model behavior and synthetic information only; it is
not ready for real participant data collection.

## Run the frontend

Run these commands from the repository root:

```bash
bash scripts/setup.sh
bash scripts/frontend.sh dev
```

Open the URL shown in the terminal, normally **http://localhost:5173**.
Stop the server with **Ctrl+C**.

### First-time setup

- Supported environments: WSL2 Ubuntu, native Linux, and macOS.
- Git is required. Setup checks prerequisites and provides guidance when something
  is missing.
- You do not need to install Node or nvm first. Setup selects or prepares the pinned
  Node 24.14.0 runtime, installs frontend dependencies, type-checks, and builds.
- On WSL2, run the commands in an Ubuntu terminal and open the URL in a Windows
  browser. Keep the checkout in the WSL Linux filesystem.
- Setup can be rerun. For subsequent development sessions, use
  `bash scripts/frontend.sh dev`.

See [Development setup](docs/development-setup.md) for full prerequisites,
platform instructions, and troubleshooting.

### Current demonstration

The frontend supports:

Consent → Demographics → Tutorial → Practice → Task 1 handoff

Practice includes catalog inspection, plan editing, four constraint checks,
four stages, and simulated conversation. Experimental routing and the complete
two-task workflow follow in Sprint 2.

The frontend currently uses an in-memory mock service. No backend, database,
API keys, or `.env` file are required. Refreshing restarts the demonstration.

## Check and preview the frontend

Run from the repository root:

```bash
bash scripts/frontend.sh type-check
bash scripts/frontend.sh test
bash scripts/frontend.sh build
bash scripts/frontend.sh preview
```

Build before previewing. Preview normally uses **http://localhost:4173** and serves
the production assets generated in `frontend/dist/`.

For browser checklists and recorded results, see:
- [Introduction verification](docs/introduction-verification.md)
- [Practice workspace verification](docs/workspace-verification.md)

## Frontend and backend setup

Frontend and backend development use separate runtimes and dependencies:

| Component | Stack | Purpose |
|---|---|---|
| Frontend | React, TypeScript, Vite, Node/npm | Browser interface |
| Planned backend | Python, FastAPI, SQLite | API, sessions, catalogs, and stored study state |

The current setup scripts prepare the frontend only. Backend setup and startup
commands will be documented when backend issue #32 is implemented.

After API integration, local backend mode will normally require the frontend
and backend servers running in separate terminals. Standalone frontend mock mode
will remain available.

See [Project structure](docs/project-structure.md) and the
[experiment service contract draft](docs/experiment-service-contract.md)
for component boundaries.

## Research references

- Checkpoint 2 methodology video: https://youtu.be/mGcKdjsUJu4
- Overleaf project: https://www.overleaf.com/read/yjwtghwfqtqp#635087
- [Prototype sprint board](https://github.com/users/NickP2000x/projects/7)
