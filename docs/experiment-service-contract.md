# Experiment service contract — draft for backend issue #31

Status: **frontend mock draft, not jointly approved**. Review IDs, state transitions,
units, feedback, and payloads with the backend owner before finalizing #31.
No endpoints or backend code are introduced here.

The interface is `frontend/src/services/experiment.types.ts`; its in-memory
implementation is `createMockExperimentService()` in `mockExperiment.ts`.
Create one instance at the app boundary. Components receive that instance and
use `useExperiment(service)` for snapshots; they never import response fixtures.

## Conventions and operations

- Participant IDs are synthetic (`demo-sequence-1` etc.), not globally unique.
- Sequence IDs 1–4 follow the paper Table 1. This mock selects a sequence, not
  real random recruitment allocation. Task IDs: practice/task-1/task-2; scenarios:
  practice/A/B. Preserve task IDs when attaching surveys and messages.
- Money uses integer cents (provisional USD); timestamps/deadlines use milliseconds
  since epoch. Model IDs are small/large roles, not real provider identifiers.
- Consent → demographics → tutorial → practice → task-1 → tlx-1 → task-2 → tlx-2
  → completion. `beginTask()` is called when requirements become visible; repeated
  calls preserve the current task and its 15-minute experimental deadline.
- `getScenario`, `searchCatalog`, `inspectItem` provide requirements, summaries,
  and details respectively. Summaries omit hidden capacity/diet/access facts;
  inspection records the item. Feasible-plan references are test-only.
- `updatePlan` accepts IDs from the current scenario/category, including empty
  selections. Fixed package prices are used; no quantity editor.
- `lockInitialChoice` → `requestRecommendation` → `confirmModel` implements
  override. Automatic calls only `requestRecommendation`, which commits the model.
  `sendMessage` needs a committed stage model; responses are canned and labeled.
- `advanceCheckpoint` creates a fresh decision record; previous records are kept.
- `finishTask` accepts incomplete/invalid plans. Submission at/after deadline is
  recorded as timeout; explicit timeout supports later developer controls. The
  countdown/deadline trigger is UI work in #16, not an authoritative enforcement service.
- `saveSurveyAnswers` permits partial 0–100 demo responses for the current ended
  experimental task. `submitSurvey` requires all six and advances the flow. Raw
  scoring/approved anchors are #15, not implemented here. Practice has no survey.
- Methods return promises. Snapshots are frozen and stable until an update;
  `pendingOperations` and typed `error` expose loading/failure. Failed validation
  preserves previous task data. Errors contain code/message, no credentials.
- `reset` creates a fresh synthetic session. No persistence, recovery, exports,
  oracle, token accounting, or reliance analysis. Refresh restarts the demo.

## Provisional decisions — not approved study materials

| Topic | Current mock choice | Researcher decision |
|---|---|---|
| Consent | No text in service; acceptance gates progression | Approved wording/exit copy in #5 |
| Demographics | Nonnegative integer age; nonempty free-text gender/LLM usage | Options, optionality, eligible ages |
| Practice | Untimed; fixed small model for each stage | Practice treatment/instructions |
| Catalog | Fictional packages; feasible totals: practice $350, A $800, B $1,200 | Values/vendors/distractors and comparable difficulty |
| Feedback | Four live booleans after selection; servings included in dietary coverage | What to reveal, when; supplies completeness policy |
| Routing | Fixed stage fixtures, identical across A/B; simulated reasons | Recommendation balance/reasons; future router threshold |
| NASA-TLX | Store six 0–100 answers; no score yet | Wording, anchors, increments, orientation |

These choices are for a demonstration, not real research findings. Paper §§4–5.4
confirms four checkpoints, stage locking, recommendation ordering, timing, and
counterbalanced sequences. Permissive submission and timeout-to-survey behavior
come from the requested prototype scope. All study materials require review.

Catalog IDs are opaque identifiers, not participant-facing labels. Names and
summaries do not explicitly announce hidden capacity, dietary, or access failures.
Prices remain visible: the premium supplies package fits the budget alone but
exceeds it when combined with the reference venue and catering. Budget is therefore
a combined-plan check, not a concealed price. This presentation and the live
constraint feedback remain provisional for #7/researcher review.

## Synthetic contract walkthroughs for #31 review

These are TypeScript service calls and snapshot examples, **not agreed HTTP routes
or payload envelopes**. A backend adapter may replace the implementation while
keeping these operations available to screens. The examples are exercised by the
focused contract walkthrough test in `frontend/tests/experiment.test.mjs`.

For either example, initialize a synthetic session and finish the separate practice:

```ts
const service = createMockExperimentService({ sequenceId: 1 });
await service.recordConsent(true);
await service.saveDemographics({
  age: 25, gender: 'synthetic example', priorLlmUsage: 'occasional',
});
await service.completeTutorial();
await service.beginTask(); // practice, excludedFromResults: true, deadline: null
await service.finishTask(); // incomplete practice accepted; step becomes task-1
await service.beginTask(); // requirements-visible event; 900,000 ms deadline
```

### Automatic checkpoint

Sequence 1 assigns task-1 to A/automatic. The reached Venue decision initially has
null choices and phase `awaiting-recommendation`:

```ts
const decision = await service.requestRecommendation();
// phase: 'committed', initialModel: null, recommendedModel: 'small',
// finalModel: 'small', initialLockedAt: null;
// recommendationShownAt and finalCommittedAt are epoch-millisecond timestamps.
// reason: 'Simulated recommendation: start with a catalog comparison.'
await service.sendMessage('Compare venue options');
// Two task-1/Venue messages: user then simulated small-model assistant.
```

There is no initial-choice or confirmation call. A repeat recommendation request
returns the same choices/timestamps; advancing creates a distinct next-stage record.

### Override checkpoint

Start a separate service with `sequenceId: 3` and use the same introduction/practice
calls. Task-1 is A/override:

```ts
await service.lockInitialChoice('large');
const decision = await service.requestRecommendation();
// phase: 'recommended', initialModel: 'large', recommendedModel: 'small',
// finalModel: null; initialLockedAt <= recommendationShownAt.
await service.confirmModel('small'); // change; 'large' would retain initial choice
// phase: 'committed', finalModel: 'small', finalCommittedAt recorded.
```

Requesting the recommendation before locking rejects with `INVALID_ROUTING_PHASE`.
For example, the snapshot exposes:

```json
{"code":"INVALID_ROUTING_PHASE","message":"Lock the independent initial choice before revealing the recommendation."}
```

The promise rejects with the same code/message, pending operations return to zero,
and the prior task data remains intact. The next successful call clears the error.

### Plan, submission/timeout, and survey linkage

For either task-1 example:

```ts
await service.updatePlan({ venue: 'A-venue-good', catering: null, supplies: [] });
await service.finishTask();
// task-1: status 'submitted', endedAt recorded, totalCostCents 30000,
// constraints { budget: true, capacity: true, dietary: false, accessibility: true };
// step 'tlx-1'. Only reached decisions exist; missing choices remain null.
await service.saveSurveyAnswers('task-1', {
  mentalDemand: 20, physicalDemand: 0, temporalDemand: 40,
  performance: 60, effort: 30, frustration: 10,
});
await service.submitSurvey('task-1'); // step 'task-2'; raw values unchanged
```

Instead of submission, `finishTask('timed-out')` preserves the same current work
and advances to the same linked survey with status `timed-out`. Submission at or
after the absolute deadline is also recorded as timeout. Ended task operations
reject; task-2 is not created until its requirements appear. After task-2 ends,
only its survey can be submitted, advancing from `tlx-2` to `completion`.

### Joint review still required

- Confirm IDs, task linkage, cents/millisecond units, and method/error shapes.
- Agree how network payloads map to the service, including session creation and
  subscriptions/refresh. These are not endpoints specified by this frontend draft.
- Agree authoritative requirements-visible/deadline and late-response behavior;
  the mock has no autonomous timeout trigger or server enforcement.
- Review catalog/feedback policy and all provisional materials above. NASA-TLX
  orientation/scoring is intentionally deferred to #15 and joint survey review.
- Record frontend/backend agreement in #31 before finalizing #3. This document
  does not substitute for that approval.

## Offline verification

Run `bash scripts/frontend.sh test` and `bash scripts/frontend.sh build`.
The experiment tests exercise the service directly, inspect pending/error and
task snapshots, verify every sequence and feasible plan, and check concealment,
stage locking, partial submission, and task/survey linkage without any API calls.
No new participant screens are part of this issue. The existing placeholder remains.

### Local verification — 2026-10-08

- Environment: WSL Linux, project-local Node 24.14.0/npm 11.9.0.
- `bash scripts/frontend.sh type-check`: passed.
- `bash scripts/frontend.sh test`: 21 passed (11 offline experiment-service tests
  and 10 setup/launcher tests). No backend, credentials, or provider calls were used.
- `bash scripts/frontend.sh build`: passed.
- Service checks cover four sequences, both routing conditions, feasible plans,
  independent constraint violations, invalid/incomplete submission, termination
  protection, task/survey linkage, frozen snapshots, and loading/error state.
- Browser integration/manual UI checks were not performed: participant screens are
  later issues. Actual macOS verification and joint #31 approval remain pending.
