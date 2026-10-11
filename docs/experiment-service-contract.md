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
  → feedback → completion. Preparation substates precede the guide/practice/tasks.
  `beginTask()` is called when requirements become visible after Start; repeated
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
  #16 countdown triggers timeout and planning mutations reject expiry before writes;
  this is still browser/mock timing, not authoritative backend enforcement. At/after
  deadline, `endedAt` is the deadline rather than a delayed callback's clock time.
- `saveSurveyAnswers` permits the current record's discrete values: v2 uses 0/25/50/75/100,
  while earlier v1 metadata retains steps of 5, for the current ended
  experimental task. `submitSurvey` requires all six and advances the flow. Raw
  scoring is the mean of six correctly oriented common-scale values, retained in
  `survey.rawScore`. `survey.metadata` retains the provisional version, wording,
  anchors, scale, and per-item orientation. Practice has no survey/metadata/score.
- `confirmPreparation(id, acknowledgedIds)` confirms all required statement IDs for
  the current before-start/practice/task preparation, retaining version/wording/IDs/time
  in `preparations`. `completeTutorial` requires before-start confirmation; `beginTask`
  requires matching task confirmation. Confirmation alone creates no task/deadline.
- `submitFeedback({ interfaceComments, studyComments })` accepts blank strings only
  at the feedback step after TLX 2, stores session-linked optional text/version/time
  separately from all task/survey records, and advances to completion.
- Methods return promises. Snapshots are frozen and stable until an update;
  `pendingOperations` and typed `error` expose loading/failure. Failed validation
  preserves previous task data. Errors contain code/message, no credentials.
- `reset` creates a fresh synthetic session. No persistence, recovery, exports,
  oracle, token accounting, or reliance analysis. Refresh restarts the demo.

## Provisional decisions — not approved study materials

| Topic | Current mock choice | Researcher decision |
|---|---|---|
| Consent | #5 shows draft demo-only consent; accept advances, decline leaves a stop message on the consent step | Approved consent wording, risks, withdrawal/data-handling and exit copy |
| Demographics | #5 requires a synthetic nonnegative whole-number age, free-text gender (including “Prefer not to say”), and usage selection: never / less than weekly / weekly / daily or more / prefer not to say | Wording, options, optionality, eligible ages; current age validation is not eligibility approval |
| Practice | #7 uses a separate untimed lunch scenario; fixed simulated small model for each stage, no router recommendation or survey | Practice treatment/instructions |
| Catalog | Fictional packages; feasible totals: practice $350, A $800, B $1,200 | Values/vendors/distractors and comparable difficulty |
| Live constraint feedback | #7 shows four live booleans after selection, even before inspection; servings included in dietary coverage. Empty plan is within budget but misses the other three requirements. Supplies completeness is not a fifth constraint. | What to reveal, when; supplies completeness policy |
| Routing | Fixed stage fixtures, identical across A/B; simulated reasons | Recommendation balance/reasons; future router threshold |
| NASA-TLX | #51 uses provisional adapted v2, five labelled choices at 0/25/50/75/100; performance Completely successful → Not successful, higher means more workload. Retain labels/raw answers/orientation/version/mean; v1 retained for earlier records. | Adaptation validity, wording, anchors, increments, orientation and approval |
| Preparation | Before-start refresh/synthetic reminders and untimed/excluded practice or 15-minute/no-refresh/submit-anytime task acknowledgements; explicit Start gates | Wording/requiredness; acknowledgements are not proof of reading |
| Optional feedback | Two final interface/study comment boxes; both may be blank, stored separately from workload | Prompt wording, use/retention policy and researcher approval |

The #51 visual guide retains a standalone fictional $290 plan (a $90 venue, $160 meal,
and $40 supplies package) against a $350 budget for 20 attendees. It illustrates
capacity, vegetarian coverage, and step-free access without showing practice/A/B
answers or checkpoint recommendation fixtures. Completing it changes the service
step to practice preparation. After Start practice, the workspace loads
requirements/catalog summaries through the service and begins the separate task
as its requirements become visible.
Practice has no deadline. Questionnaire inputs are retained on failed attempts;
accepted responses live in service memory. All introduction copy/options are
provisional and must be reviewed before real participant collection.

These choices are for a demonstration, not real research findings. Paper §§4–5.4
confirms four checkpoints, stage locking, recommendation ordering, timing, and
counterbalanced sequences. Permissive submission and timeout-to-survey behavior
come from the requested prototype scope. All study materials require review.

Catalog IDs are opaque identifiers, not participant-facing labels. Names and
summaries do not explicitly announce hidden capacity, dietary, or access failures.
Prices remain visible: the premium supplies package fits the budget alone but
exceeds it when combined with the reference venue and catering. Budget is therefore
a combined-plan check, not a concealed price. This presentation and the live
constraint feedback remain provisional for researcher review. Practice/A/B now use
distinct fictional vendor labels, with stable item IDs and unchanged feasible totals.

## Workspace behavior in #7

- The mockup-aligned three-panel workspace uses only the experiment service.
  Initial catalog summaries populate both search results and selected-item labels;
  hidden details are loaded only by `inspectItem`. Reopening cached details does
  not duplicate the service's inspected-item record.
- A submitted search uses `searchCatalog`; an empty query shows the selected
  category's full list. Filtering never removes selected items from the plan.
- Venue/catering selections replace the previous item. Supplies selections add
  distinct packages. Remove actions retain other selections; the service recomputes
  integer-cent costs and the same four constraints used at submission.
- Next-stage controls use `advanceCheckpoint`; conversation uses `sendMessage`.
  Stage-linked history and inspected items remain in service memory. Mutations are
  guarded while an operation is pending; failed messages keep the current draft.
- Practice submission at any checkpoint uses `finishTask`, preserving incomplete
   or invalid work and unvisited checkpoints. It proceeds to Task 1 preparation
   with no practice survey. Task 1's deadline is created only when its
  requirements header is rendered, not by practice submission itself.
- `PlanningWorkspace` accepts a task ID and derives its scenario from service
  assignments. #12 adds the routing UI to the reusable workspace; experimental
  countdown, survey connections, and two-task orchestration are now connected by
  #16. The app mounts each workspace/survey with a task-specific key.

## Full-flow behavior in #16

The app follows the complete consent-through-completion flow using the four
service assignments. Developer-only sequence/reset/timeout controls do not exist
in the participant production UI. Standalone default assignment is still mock
sequence 1, not real randomized recruitment allocation.

`beginTask` runs after requirements are rendered; repeated calls retain the existing
deadline. Termination bypasses the parent action lock for timeout but rejects
duplicates. Queued planning operations are checked against their original task,
checkpoint, and session generation. New errors include `TASK_EXPIRED` (work preserved,
timeout-to-survey) and `STALE_OPERATION` (old checkpoint/reset session); obsolete
operations do not overwrite current-screen error state. The public methods/record
shape remain unchanged. System-clock/browser throttling and refresh-restarts-demo
limitations remain; authoritative enforcement is future backend work.

See [study-flow verification](frontend/study-flow-verification.md) for current
developer commands, integration checks/results, and #22 handoff.

## #51 current refinement / backend coordination

New `StudyState` fields are `preparations` and `feedback`; `StudyStep` now includes
feedback. Preparation IDs are before-start/practice/task-1/task-2. Each accepted
record contains definition version, statement wording, acknowledged IDs and
`confirmedAt`. Repeated confirmation preserves the original timestamp. This is
acknowledgement, not evidence of reading. Reset clears these records.

New tasks capture `provisional-adapted-nasa-tlx-5-v2`, increment 25, and per-item
`labels`. The previous v1 definition is exported unchanged; scoring/validation use
the stored metadata, not a global replacement. This adaptation changes precision
and presentation and still needs researcher approval.

`submitSurvey(task-2)` advances to feedback instead of completion. `submitFeedback`
stores `interfaceComments`, `studyComments`, version `provisional-feedback-v1` and
`submittedAt`; data remains linked through the synthetic session and is not scored.
Blank/filled submissions both finish. The new methods, gate prerequisites, fields,
values and transitions require #31/backend state/record-owner review before joint
agreement is claimed. See [current refinements](frontend/study-refinements-verification.md).

## Routing UI in #12

The center panel renders service-owned decisions through `RoutingPanel`, keyed by
task/checkpoint. Automatic requests/reveals/applies directly. Override has no
preselected initial model and never requests/displays a recommendation before lock;
after reveal, explicit retain/change and confirmation commit the final model.
The stage model then stays fixed and enables agent work/Next. Practice bypasses
recommendations and retains the existing fixed-small-model treatment.

The parent passes its action `pending` flag to `PlanningWorkspace`, which combines
it with service pending operations. A per-panel request guard prevents effect replay
from duplicating a request; failures wait for explicit retry. These are UI guards,
not a replacement for service transition validation or future server enforcement.
The API/service interface and record fields are unchanged. See the
[frontend routing handoff](frontend/routing-verification.md) for #16 integration,
focused browser checks, and actual results.

## Synthetic contract walkthroughs for #31 review

The #15 survey record adds `metadata` and `rawScore` to the prior `answers` /
`submittedAt` fields. Experimental tasks capture the provisional definition at
creation; practice keeps metadata/score null. The mean is null before submission.
Joint #31/backend review must account for these fields and discrete allowed values;
method names/arguments remain unchanged. See the
[workload handoff](frontend/workload-verification.md) for presentation, scoring,
failure behavior, and #16 integration.

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
await service.confirmPreparation('before-start', ['no-refresh', 'synthetic-only']);
await service.completeTutorial();
await service.confirmPreparation('practice', ['untimed', 'excluded']);
await service.beginTask(); // practice, excludedFromResults: true, deadline: null
await service.finishTask(); // incomplete practice accepted; step becomes task-1
await service.confirmPreparation('task-1', ['time-limit', 'no-refresh', 'submit-anytime']);
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
  mentalDemand: 25, physicalDemand: 0, temporalDemand: 50,
  performance: 75, effort: 25, frustration: 0,
});
await service.submitSurvey('task-1'); // step 'task-2'; raw values unchanged
// survey.rawScore: 175 / 6; v2 metadata retains successful-to-unsuccessful labels.
```

Instead of submission, `finishTask('timed-out')` preserves the same current work
and advances to the same linked survey with status `timed-out`. Submission at or
after the absolute deadline is also recorded as timeout. Ended task operations
reject; task-2 is not created until its requirements appear. After task-2 ends,
only its survey can be submitted, advancing from `tlx-2` to `feedback`. Optional
`submitFeedback` then advances to completion without changing task scores.

### Joint review still required

- Confirm IDs, task linkage, cents/millisecond units, and method/error shapes.
- Agree how network payloads map to the service, including session creation and
  subscriptions/refresh. These are not endpoints specified by this frontend draft.
  The backend HTTP proposal for this review is
  [`experiment-api-http-draft.md`](experiment-api-http-draft.md).
- Agree authoritative requirements-visible/deadline and late-response behavior;
  the mock has no autonomous timeout trigger or server enforcement.
- Review catalog/feedback policy and all provisional materials above. NASA-TLX
  presentation/orientation/scoring in #15 are provisional and still require joint survey review.
- Record frontend/backend agreement in #31 before finalizing #3. This document
  does not substitute for that approval.

## Offline verification

Run `bash scripts/frontend.sh test` and `bash scripts/frontend.sh build`.
The experiment tests exercise the service directly, inspect pending/error and
task snapshots, verify every sequence and feasible plan, and check concealment,
stage locking, partial submission, and task/survey linkage without any API calls.
The #3 service verification is independent of UI. Issue #5 now connects the
consent/demographics/tutorial screens; #7 connects practice, #12/#15 provide routing
and workload components, and #16 connects both experimental tasks through completion.

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
