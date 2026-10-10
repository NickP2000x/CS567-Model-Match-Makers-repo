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

See [Frontend development setup](docs/frontend/development-setup.md) for full prerequisites,
platform instructions, and troubleshooting.

### Current demonstration

The frontend supports:

Consent → Demographics → Before-start reminders / Visual guide → Practice →
Task 1 → Workload ratings 1 → Task 2 → Workload ratings 2 → Optional feedback → Completion

Practice and each experimental task have an acknowledgement/preparation page and
an explicit Start button. Requirements and experimental deadlines appear only after
Start. Later pages show the current section and read-only study progress.

Practice includes catalog inspection, plan editing, four constraint checks,
four stages, and simulated conversation. Both experimental tasks include simulated
automatic/override routing, a 15-minute countdown, permissive submission/timeout,
and the reusable provisional five-point, fully labelled NASA-TLX adaptation.

In development (`dev`), expand **Development controls** below the screen to choose
one of the four A/B sequences, apply it with a reset, or trigger an experimental
timeout. These controls are absent from the normal production build/preview.
The standalone mock defaults to sequence 1; real randomized, balanced assignment
and persistence are planned backend work.

By default the frontend uses an in-memory mock service: no backend, database, API
keys, or `.env` file are required, and refreshing restarts the demonstration. With
`VITE_API_BASE_URL` set it uses the backend instead, and a refresh resumes the session.

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
- [Introduction verification](docs/frontend/introduction-verification.md)
- [Practice workspace verification](docs/frontend/workspace-verification.md)
- [Routing verification and integration handoff](docs/frontend/routing-verification.md)
- [Workload survey verification and integration handoff](docs/frontend/workload-verification.md)
- [Complete study flow verification and Sprint 3 handoff](docs/frontend/study-flow-verification.md)
- [Study refinements and current #22 handoff](docs/frontend/study-refinements-verification.md)

## Frontend and backend setup

Frontend and backend development use separate runtimes and dependencies:

| Component | Stack | Purpose |
|---|---|---|
| Frontend | React, TypeScript, Vite, Node/npm | Browser interface |
| Backend | Python 3.12, FastAPI, Uvicorn, SQLite | API, sessions, catalog, routing, agent, and research records |

The `scripts/` setup prepares the frontend only. The backend runs the complete study
flow in mock mode (catalog, sessions with balanced allocation, routing, timing,
surveys, feedback) using the same simulated responses as the frontend mock. Set
`VITE_API_BASE_URL=http://127.0.0.1:8000` to run the frontend against it; see
[Backend (API) mode](docs/frontend/development-setup.md#backend-api-mode). It needs
Python 3.12 but no `.env` or keys. Optional real models (OpenAI/Ollama) are configured
in `backend/.env`; see [Real models](docs/backend/development-setup.md#real-models-3536).
From the repository root:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open **http://127.0.0.1:8000/api/health**. See
[Backend development setup](docs/backend/development-setup.md) for platform notes
and configuration, and the [backend documentation handoff](docs/backend/README.md)
for the planned work.

Backend mode needs the frontend and backend servers running in separate terminals;
standalone frontend mock mode remains available. Real models (#35/#36), the RouteLLM
router (#37), the offline oracle (#40), and the records report (#41) are optional and
described in [Backend development setup](docs/backend/development-setup.md).

See [Project structure](docs/project-structure.md) and the
[experiment service contract draft](docs/experiment-service-contract.md)
for component boundaries.

## Research references

- Checkpoint 2 methodology video: https://youtu.be/mGcKdjsUJu4
- Overleaf project: https://www.overleaf.com/read/yjwtghwfqtqp#635087
- [Prototype sprint board](https://github.com/users/NickP2000x/projects/7)
