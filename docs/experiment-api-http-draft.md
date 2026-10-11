# Experiment HTTP API — draft for issue #31

Status: **backend proposal, not jointly approved**. This maps the frontend
`ExperimentService` onto HTTP so that a backend adapter (#39) can replace
`createMockExperimentService()` without changing study screens.

Behavior is defined by [`experiment-service-contract.md`](experiment-service-contract.md),
`frontend/src/services/experiment.types.ts`, and `mockExperiment.ts` as of the
#51 refinements. This page adds only transport details (paths, bodies, status
codes, session handling) and marks where a server must go **beyond the mock**.
Those items need explicit agreement before backend implementation relies on them.
No backend code exists yet.

## Conventions

- Base path `/api`. JSON request and response bodies.
- Identifiers are the mock's: sequence `1`–`4` (paper Table 1); task
  `practice | task-1 | task-2`; preparation `before-start | practice | task-1 | task-2`;
  scenario `practice | A | B`; category `venue | catering | supplies`; checkpoint
  `Venue | Catering | Supplies | Final constraint check`; model `small | large`.
  Model values are roles, never provider model names. Catalog item IDs are the
  stable fixture IDs (for example `A-venue-good`).
- Money is integer cents (provisional USD). Timestamps and deadlines are integer
  milliseconds since the Unix epoch, taken from the **server** clock.
- `sessionId` is an opaque, server-generated synthetic identifier. It is the only
  handle a client holds; there are no accounts or authentication in this prototype.
- No credentials, provider keys, or provider/model names appear in any request or
  response. Real model and router calls stay server-side (#35–#37).

## Responses

- **State snapshot.** Every successful mutation returns the participant-visible
  `StudyState`, so the adapter replaces its snapshot in one step.
- The server snapshot is the mock `StudyState` **without** the client-only
  `pendingOperations`, `error`, and `refreshRestartsDemo` fields (the adapter adds
  them locally), **plus** `sessionId`. It includes `preparations`, `feedback`, and
  each task's `survey.metadata` / `survey.rawScore`, exactly as the mock does.
- `inspectItem` returns `{ "item": CatalogItem, "state": StudyState }`.
- `requestRecommendation` returns the snapshot; the adapter returns
  `state.tasks[taskId].decisions[checkpoint]` to keep the existing method signature.
- Catalog reads (`getScenario`, `searchCatalog`) return their own shapes.
- The snapshot never contains research-only data: reference plans, oracle results
  or unselected model outputs (#40), token/call usage, or raw event logs (#38).
  Those are stored separately and are not served to the participant client.

### Errors

Failures return `{ "error": { "code": string, "message": string } }` with
participant-safe messages: no stack traces, credentials, or provider details.
A failed request does not change stored state, except `TASK_EXPIRED` (below).
The adapter branches on `code`; the HTTP status is advisory.

| HTTP | Codes (mock codes unless marked **new**) |
|---|---|
| 400 | `INVALID_REQUEST` **new** (malformed body, unknown field; replaces FastAPI's default 422 shape), `INVALID_SEQUENCE`, `INVALID_DEMOGRAPHICS`, `INVALID_PREPARATION`¹, `INVALID_MODEL`, `INVALID_PLAN`, `EMPTY_MESSAGE`, `INVALID_SURVEY`, `INCOMPLETE_SURVEY`, `INVALID_FEEDBACK` |
| 404 | `SESSION_NOT_FOUND` **new**, `NOT_FOUND` (scenario or item) |
| 409 | `INVALID_STEP`, `INVALID_PREPARATION`¹, `NO_ACTIVE_TASK`, `STALE_OPERATION`, `TASK_EXPIRED`, `INVALID_ROUTING_PHASE`, `MODEL_REQUIRED`, `FINAL_CHECKPOINT`, `ALLOCATION_FULL` **new** |
| 500 | `INTERNAL_ERROR` **new** (server counterpart of the mock's catch-all `MOCK_ERROR`) |
| 502 | `PROVIDER_ERROR` **new** (Sprint 2 model/router failure; never returned in mock mode) |

¹ The mock uses `INVALID_PREPARATION` both for an incomplete acknowledgement list
(400) and for a missing required preparation before the tutorial or a task (409).

`TASK_EXPIRED` responses also carry `"state": StudyState`, because the server
ends the task as part of rejecting the request (see Timing).

## Operations

`{sid}` = `sessionId`; `{taskId}` = `practice | task-1 | task-2`;
`{prepId}` = `before-start | practice | task-1 | task-2`.

| Mock method | HTTP | Request body | Success |
|---|---|---|---|
| — | `GET /api/health` | — | `{ "status": "ok", "mode": "mock" }` |
| (session creation) | `POST /api/sessions` | `{}` | 201 `StudyState` |
| `getSnapshot` / resume | `GET /api/sessions/{sid}` | — | `StudyState` |
| `reset` | `POST /api/sessions/{sid}/reset` | `{ "sequenceId"?: 1-4 }` | 201 `StudyState` (new session) — **development only** |
| `recordConsent` | `POST /api/sessions/{sid}/consent` | `{ "accepted": boolean }` | `StudyState` |
| `saveDemographics` | `POST /api/sessions/{sid}/demographics` | `{ "age", "gender", "priorLlmUsage" }` | `StudyState` |
| `confirmPreparation` | `POST /api/sessions/{sid}/preparations/{prepId}` | `{ "acknowledgedIds": string[] }` | `StudyState` |
| `completeTutorial` | `POST /api/sessions/{sid}/tutorial/complete` | `{}` | `StudyState` |
| `getScenario` | `GET /api/scenarios/{scenarioId}` | — | `Scenario` |
| `searchCatalog` | `GET /api/scenarios/{scenarioId}/catalog?query=&category=` | — | `CatalogSummary[]` |
| `beginTask` | `POST /api/sessions/{sid}/tasks/{taskId}/begin` | `{}` | `StudyState` |
| `inspectItem` | `POST /api/sessions/{sid}/tasks/{taskId}/inspect` | `{ "checkpoint", "itemId" }` | `{ item, state }` |
| `updatePlan` | `PUT /api/sessions/{sid}/tasks/{taskId}/plan` | `{ "checkpoint", "plan": Plan }` | `StudyState` |
| `lockInitialChoice` | `POST /api/sessions/{sid}/tasks/{taskId}/routing/initial` | `{ "checkpoint", "model" }` | `StudyState` |
| `requestRecommendation` | `POST /api/sessions/{sid}/tasks/{taskId}/routing/recommendation` | `{ "checkpoint" }` | `StudyState` |
| `confirmModel` | `POST /api/sessions/{sid}/tasks/{taskId}/routing/confirm` | `{ "checkpoint", "model" }` | `StudyState` |
| `sendMessage` | `POST /api/sessions/{sid}/tasks/{taskId}/messages` | `{ "checkpoint", "text" }` | `StudyState` |
| `advanceCheckpoint` | `POST /api/sessions/{sid}/tasks/{taskId}/checkpoint/advance` | `{ "checkpoint" }` | `StudyState` |
| `finishTask` | `POST /api/sessions/{sid}/tasks/{taskId}/finish` | `{ "reason": "submitted" \| "timed-out" }` | `StudyState` |
| `saveSurveyAnswers` | `PUT /api/sessions/{sid}/surveys/{taskId}` | `{ "answers": SurveyAnswers }` | `StudyState` |
| `submitSurvey` | `POST /api/sessions/{sid}/surveys/{taskId}/submit` | `{}` | `StudyState` |
| `submitFeedback` | `POST /api/sessions/{sid}/feedback` | `{ "interfaceComments", "studyComments" }` | `StudyState` |

### Stale and ended requests

The mock records the task and checkpoint at call time and rejects work that no
longer applies. Over HTTP the client states them explicitly:

- `{taskId}` in the path must be the current, active task; otherwise
  `409 NO_ACTIVE_TASK` (task ended) or `409 INVALID_STEP` (`begin` for a step that
  is not current).
- Every planning request (`inspect`, `plan`, `routing/*`, `messages`,
  `checkpoint/advance`) sends the `checkpoint` the client is acting on. If the task
  has moved on, the server answers `409 STALE_OPERATION` without changes.
- Requests to a session replaced by a development reset return `409 STALE_OPERATION`
  (the mock's session-generation check).

### Transition rules

Identical to the mock:

1. `consent` → `demographics` → `tutorial`. Declining consent stays on `consent`.
2. At `tutorial`: confirm preparation `before-start`, then `tutorial/complete` →
   `practice`.
3. At each planning step (`practice`, `task-1`, `task-2`): confirm that step's
   preparation, then `begin`. Confirmation alone creates no task or deadline.
   Repeated confirmation keeps the original record and time; repeated `begin` keeps
   the existing task and deadline.
4. `finish` accepts incomplete/invalid plans. Practice → `task-1` (no survey);
   `task-1` → `tlx-1`; `task-2` → `tlx-2`.
5. `tlx-1` submit → `task-2`; `tlx-2` submit → `feedback`; feedback submit →
   `completion`.

Required acknowledgement IDs (current versions): `before-start`
`["no-refresh", "synthetic-only"]`; `practice` `["untimed", "excluded"]`;
`task-1`/`task-2` `["time-limit", "no-refresh", "submit-anytime"]`. The
acknowledgement list must contain each statement ID exactly once.

### Timing

- `begin` sets `startedAt` from the server clock. Experimental tasks get
  `deadline = startedAt + 900000`; practice has `deadline: null`. Resume and
  repeated `begin` never move the deadline.
- A planning request at or after the deadline ends the task as `timed-out` with
  `endedAt = deadline`, keeps the plan and choices as they were, recomputes cost
  and constraints, advances to the linked survey step, and answers
  `409 TASK_EXPIRED` with the updated `state`. This matches the mock.
- `finish` at or after the deadline succeeds with `status: "timed-out"` and
  `endedAt = deadline`, whatever `reason` was sent. This matches the mock.
- **Beyond the mock:** any request for the session, including `GET`, first applies
  the same expiry. There is no background timer; the client countdown still calls
  `finish` with `"timed-out"`.

### Surveys

- At `begin`, the server attaches its current workload definition
  (`provisional-adapted-nasa-tlx-5-v2`: min 0, max 100, increment 25, per-item
  labels, anchors and orientation) to the experimental task as `survey.metadata`.
  Practice keeps `metadata` and `rawScore` null.
- The server keeps every definition version (including
  `provisional-nasa-tlx-21-v1`). Validation and scoring always use the task's
  stored metadata, never a newer global definition.
- `PUT` accepts partial answers; each value must fit the stored min, max, and
  increment. `submit` requires all six. The server computes `rawScore`, the mean
  of the six correctly oriented common-scale values. The client never sends a score.

### Preparations and feedback

- The server holds versioned preparation definitions identical to
  `frontend/src/services/studyPreparation.ts` and stores each accepted record as
  `{ version, statements, acknowledgedIds, confirmedAt }`. A record is an
  acknowledgement, not proof of reading.
- Feedback is accepted only at the `feedback` step, once. Both strings may be
  blank. It is stored as `{ interfaceComments, studyComments,
  version: "provisional-feedback-v1", submittedAt }`, linked to the session and
  separate from workload scores.

### Sessions, allocation, development controls

- `POST /api/sessions` takes the next unused slot from 12 pre-shuffled slots (three
  per sequence), allocated inside a database transaction. Participants never choose.
  `participantId` is a synthetic slot label (`P01`–`P12`).
- `GET /api/sessions/{sid}` resumes the same session. It never reallocates and never
  moves a deadline.
- With an explicit server flag (`DEV_CONTROLS=true`), `POST /api/sessions` and
  `reset` accept `sequenceId`. Development sessions use `participantId` values like
  `dev-…`, never consume allocation slots, and are excluded from study records.
  `reset` creates a new session (new `sessionId`) and retires the old one. Without
  the flag, `reset` returns 404 and `sequenceId` is rejected with `INVALID_REQUEST`.

## Proposed beyond the mock — needs agreement

1. **Explicit task and checkpoint in requests** (the "Stale and ended requests"
   section), so that late replies cannot change an ended task or a later checkpoint.
2. **Server clock and expiry on every request**, including `GET`.
3. **`TASK_EXPIRED` carries `state`**, so the client can move to the survey
   without a second request.
4. **Late model replies (Sprint 2).** A reply is shown only if its task is still
   active and at the same checkpoint when it arrives. Otherwise it is not added to
   messages (the request returns `TASK_EXPIRED`, `NO_ACTIVE_TASK`, or
   `STALE_OPERATION`). The call is still recorded for usage accounting (#38).
5. **Allocation after 12 sessions.** Proposed: `409 ALLOCATION_FULL`.
   *Open question: reject, or start another balanced block of 12?*
6. **Development flag and development sessions** as described above.
7. **Feedback length limit.** Proposed: at most 5000 characters per box
   (`INVALID_FEEDBACK` otherwise). The mock has no limit.
8. **One source for definitions.** The frontend renders preparation statements from
   its own `studyPreparation.ts`; the server needs the same text. Options: keep two
   copies matched by version string, or add `GET /api/definitions` so the
   frontend renders the server's version. *Open question.*
9. **`simulated` in real mode.** The frontend type has `simulated: true`. When real
   models are enabled the server reports `false`; #39 widens the type.
10. **Frontend configuration.** The adapter is chosen explicitly (mock or API, never
    mixed) and reads a public `VITE_API_BASE_URL`. The backend allows the local
    dev/preview origins (`localhost:5173`, `localhost:4173`) via CORS.
11. **Resume in the browser.** #39 requires resuming the same backend session
    without resetting deadlines. How the browser keeps `sessionId` across refresh is
    decided there (and in #17); standalone mock mode still restarts on refresh.

## Shapes

`Task`, `Decision`, `Message`, `Plan`, `Constraints`, `Scenario`, `CatalogSummary`,
`CatalogItem`, `PreparationRecord`, and `SurveyMetadata` are unchanged from
`experiment.types.ts`. Search results never include hidden capacity, dietary, or
accessibility details; only `inspect` returns them.

```jsonc
// StudyState (server form)
{
  "sessionId": "9f2c…",
  "participantId": "P07",
  "sequenceId": 1,
  "assignments": [
    { "scenarioId": "A", "condition": "automatic" },
    { "scenarioId": "B", "condition": "override" }
  ],
  "step": "task-1",
  "consent": true,
  "demographics": { "age": 25, "gender": "synthetic example", "priorLlmUsage": "weekly" },
  "preparations": {
    "before-start": {
      "version": "provisional-before-start-v1",
      "statements": [{ "id": "no-refresh", "text": "…" }, { "id": "synthetic-only", "text": "…" }],
      "acknowledgedIds": ["no-refresh", "synthetic-only"],
      "confirmedAt": 1791504000000
    }
    // practice, task-1, … as they are confirmed
  },
  "tasks": { "practice": { /* Task */ }, "task-1": { /* Task */ } },
  "feedback": null,
  "simulated": true
}
```

## Walkthrough examples

Synthetic values. Timestamps start at `1791504000000` (2026-10-09T00:00:00Z).
After the first snapshot, only changed fields are shown.

### Session, introduction, practice

```http
POST /api/sessions
{}
→ 201 { "sessionId": "9f2c…", "participantId": "P07", "sequenceId": 1,
        "assignments": [{ "scenarioId": "A", "condition": "automatic" },
                        { "scenarioId": "B", "condition": "override" }],
        "step": "consent", "consent": null, "demographics": null,
        "preparations": {}, "tasks": {}, "feedback": null, "simulated": true }

POST /api/sessions/9f2c…/consent          { "accepted": true }        → step "demographics"
POST /api/sessions/9f2c…/demographics     { "age": 25, "gender": "synthetic example",
                                            "priorLlmUsage": "weekly" } → step "tutorial"
POST /api/sessions/9f2c…/preparations/before-start
     { "acknowledgedIds": ["no-refresh", "synthetic-only"] }          → preparations["before-start"]
POST /api/sessions/9f2c…/tutorial/complete {}                         → step "practice"
POST /api/sessions/9f2c…/preparations/practice
     { "acknowledgedIds": ["untimed", "excluded"] }
POST /api/sessions/9f2c…/tasks/practice/begin {}
  → tasks.practice: { "condition": "practice", "excludedFromResults": true,
                      "deadline": null, "survey": { "metadata": null, "rawScore": null, … } }
POST /api/sessions/9f2c…/tasks/practice/finish { "reason": "submitted" } → step "task-1"
```

Skipping a step is rejected without changing state:

```http
POST /api/sessions/9f2c…/tutorial/complete {}      (before-start not confirmed)
→ 409 { "error": { "code": "INVALID_PREPARATION",
        "message": "Acknowledge the before-start instructions first." } }
```

### Automatic checkpoint (sequence 1, task-1 = A/automatic)

```http
POST /api/sessions/9f2c…/preparations/task-1
     { "acknowledgedIds": ["time-limit", "no-refresh", "submit-anytime"] }
POST /api/sessions/9f2c…/tasks/task-1/begin {}
→ tasks["task-1"]: { "status": "active", "startedAt": 1791504000000,
    "deadline": 1791504900000, "checkpoint": "Venue",
    "survey": { "answers": {}, "metadata": { "version": "provisional-adapted-nasa-tlx-5-v2", … },
                "rawScore": null, "submittedAt": null },
    "decisions": { "Venue": { "phase": "awaiting-recommendation",
      "initialModel": null, "recommendedModel": null, "finalModel": null,
      "reason": null, "shownAt": 1791504000000, "initialLockedAt": null,
      "recommendationShownAt": null, "finalCommittedAt": null } } }

POST /api/sessions/9f2c…/tasks/task-1/routing/recommendation { "checkpoint": "Venue" }
→ decisions.Venue: { "phase": "committed", "initialModel": null,
    "recommendedModel": "small", "finalModel": "small",
    "reason": "Simulated recommendation: start with a catalog comparison.",
    "initialLockedAt": null, "recommendationShownAt": 1791504002000,
    "finalCommittedAt": 1791504002000 }

POST /api/sessions/9f2c…/tasks/task-1/messages
     { "checkpoint": "Venue", "text": "Compare venue options" }
→ messages: [
    { "id": "task-1-message-0", "role": "user", "text": "Compare venue options",
      "checkpoint": "Venue", "model": null, "createdAt": 1791504010000, "simulated": false },
    { "id": "task-1-message-1", "role": "assistant",
      "text": "[Simulated small model] Venue: inspect the catalog details before choosing.",
      "checkpoint": "Venue", "model": "small", "createdAt": 1791504010000, "simulated": true } ]
```

Automatic tasks have no initial-choice or confirm call; either returns
`409 INVALID_ROUTING_PHASE`. A repeated recommendation request returns the same
decision and timestamps.

### Override checkpoint (sequence 3, task-1 = A/override)

```http
POST /api/sessions/{sid}/tasks/task-1/routing/recommendation { "checkpoint": "Venue" }
→ 409 { "error": { "code": "INVALID_ROUTING_PHASE",
        "message": "Lock the independent initial choice before revealing the recommendation." } }

POST /api/sessions/{sid}/tasks/task-1/routing/initial { "checkpoint": "Venue", "model": "large" }
→ decisions.Venue: { "phase": "locked", "initialModel": "large",
                     "initialLockedAt": 1791504003000, "recommendedModel": null }

POST /api/sessions/{sid}/tasks/task-1/routing/recommendation { "checkpoint": "Venue" }
→ decisions.Venue: { "phase": "recommended", "initialModel": "large",
    "recommendedModel": "small", "finalModel": null,
    "reason": "Simulated recommendation: start with a catalog comparison.",
    "recommendationShownAt": 1791504005000 }

POST /api/sessions/{sid}/tasks/task-1/routing/confirm { "checkpoint": "Venue", "model": "small" }
→ decisions.Venue: { "phase": "committed", "finalModel": "small",
                     "finalCommittedAt": 1791504009000 }
```

Confirming `"large"` instead would retain the initial choice. After commit the
stage model is fixed: further `initial` or `confirm` calls for this checkpoint
return `409 INVALID_ROUTING_PHASE`, and a repeated `recommendation` request returns
the same decision.

A request for an earlier checkpoint is rejected:

```http
POST /api/sessions/{sid}/tasks/task-1/messages { "checkpoint": "Venue", "text": "…" }
     (task is now at Catering)
→ 409 { "error": { "code": "STALE_OPERATION", "message": "The original checkpoint has ended." } }
```

### Plan, submission, timeout, survey, feedback

```http
PUT /api/sessions/9f2c…/tasks/task-1/plan
{ "checkpoint": "Venue", "plan": { "venue": "A-venue-good", "catering": null, "supplies": [] } }
→ tasks["task-1"]: { "totalCostCents": 30000,
    "constraints": { "budget": true, "capacity": true, "dietary": false, "accessibility": true } }

POST /api/sessions/9f2c…/tasks/task-1/finish { "reason": "submitted" }
→ tasks["task-1"]: { "status": "submitted", "endedAt": 1791504300000 }, step "tlx-1"
  (only reached checkpoints have decisions; nothing is fabricated)
```

If instead a planning request arrives after the deadline:

```http
PUT /api/sessions/9f2c…/tasks/task-1/plan { "checkpoint": "Supplies", "plan": { … } }
     (server time ≥ 1791504900000)
→ 409 { "error": { "code": "TASK_EXPIRED", "message": "The task deadline has passed." },
        "state": { …, "step": "tlx-1",
                   "tasks": { "task-1": { "status": "timed-out", "endedAt": 1791504900000, … } } } }
```

Survey and feedback (v2 accepts only 0, 25, 50, 75, 100):

```http
PUT /api/sessions/9f2c…/surveys/task-1
{ "answers": { "mentalDemand": 25, "physicalDemand": 0, "temporalDemand": 50,
               "performance": 75, "effort": 25, "frustration": 0 } }
→ tasks["task-1"].survey.answers: { …same six values… }

PUT /api/sessions/9f2c…/surveys/task-1 { "answers": { "effort": 30 } }
→ 400 { "error": { "code": "INVALID_SURVEY",
        "message": "Choose a response from 0 to 100 in steps of 25." } }

POST /api/sessions/9f2c…/surveys/task-1/submit {}
→ tasks["task-1"].survey: { "rawScore": 29.166666666666668, "submittedAt": 1791504360000 },
  step "task-2"

… task-2 and tlx-2 follow the same pattern; tlx-2 submit → step "feedback" …

POST /api/sessions/9f2c…/feedback { "interfaceComments": "", "studyComments": "" }
→ feedback: { "interfaceComments": "", "studyComments": "",
              "version": "provisional-feedback-v1", "submittedAt": 1791506000000 },
  step "completion"
```

## Scope by backend sprint

All operations are specified now so the frontend can rely on one contract.

- **Sprint 1 (#32–#34):** health, error envelope, sessions/allocation/resume,
  development reset, consent, demographics, preparations, tutorial, scenarios and
  catalog search, `begin`/`inspect`/`plan`/`finish`, and persisted step transitions.
- **Sprint 2 (#35–#38):** routing, messages (mock first, then real models), checkpoint
  advance, server deadline enforcement, surveys, feedback, and research records.
- **Sprint 3 (#39–#41):** frontend API adapter, oracle validation, integrated checks.

## Review checklist for #31

- [ ] Endpoint list, and every mutation returning the snapshot
- [ ] IDs, cents, epoch milliseconds, server clock
- [ ] Error envelope, status mapping, and the new codes
- [ ] Task in the path and checkpoint in planning bodies (`STALE_OPERATION`)
- [ ] Deadline expiry on every request; `TASK_EXPIRED` carrying `state`
- [ ] Late model replies discarded but recorded
- [ ] Allocation after 12 sessions
- [ ] Development flag, development sessions, reset creating a new session
- [ ] Feedback length limit
- [ ] One source for preparation/survey/feedback definitions
- [ ] `simulated` in real mode; adapter selection and CORS
- [ ] Agreement recorded on issue #31 before #39 relies on it
