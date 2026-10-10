# Issue #22 — final prototype smoke checks

Baseline: merged #51 / Git safeguards, commit `3c7a64a`. Verified 2026-10-10.
Outcome: **the standalone simulated frontend passed the scoped demonstration
checks below**. No essential application defect was found during this pass.
This is not approval or readiness for real participant collection.

## Repeatable checklist

From the repository root:

```bash
bash scripts/setup.sh --check
bash scripts/frontend.sh type-check
bash scripts/frontend.sh test
bash scripts/frontend.sh build
bash scripts/frontend.sh preview
```

For sequence selection, use `bash scripts/frontend.sh dev`, expand Development
controls, choose a sequence, and Apply sequence and reset demo. Use invented
demographics/messages/feedback only. Participant production preview has no selector.

| Check | Expected behavior |
|---|---|
| Entry and gates | Consent first; decline stops entry. Required demographics validate. Before-start and preparation boxes are unchecked; Continue/Start requires acknowledgement. No task/deadline/requirements before Start. |
| Tutorial/progress | Six highlighted guide sections, Back/Next, distinct example; no assigned recommendation/A/B answer. Progress is read-only; headings show current section. |
| Practice | Separate scenario, untimed, fixed simulated small model, editable catalog/plan/conversation, no survey; submission leads to Task 1 preparation. |
| Four sequences | A Automatic/B Override; B Automatic/A Override; A Override/B Automatic; B Override/A Automatic. Tasks/scenarios/conditions match assignments. |
| Routing/stages | Four checkpoints in order. Automatic has no choice/confirmation; Override locks an independent choice before revealing recommendation, supports both initial models and retain/change, then locks the final model. Re-renders/duplicate actions do not alter decisions or skip stages. |
| Planning | Search/inspect/add/remove, known feasible costs/four checks, detail-only facts, retained selections after search. Invalid/incomplete submission is allowed at any checkpoint. |
| Timing/termination | 15-minute absolute deadline at requirements visibility; no remount extension. Submission/timeout preserves service-backed work and partial choices, creates no unvisited decisions, and reaches the correct survey. Late results cannot mutate ended work or appear as a stale survey error. |
| Workload | Six explicit five-point labelled answers, no defaults. Missing/partial answers block progression. Raw `[25,0,50,75,25,0]` gives `175/6`; all 0 gives 0, all 50 gives 50, all 100 gives 100. Raw performance and labels/version/orientation are retained. Task 2 starts blank. |
| Feedback/completion | Optional blank/filled final feedback both finish; text is session-linked, separate from workload scoring, retained on failure. Duplicate Finish cannot overwrite records. Completion follows feedback. |
| Basic usability | Keyboard Tab, Space, arrow keys, Enter; visible focus and named controls. Recommendation/commit/stage transitions focus the relevant heading. Laptop/zoom content remains readable without horizontal page overflow. |
| Errors/refresh/build | Failed load/start/search/routing/message/ratings/feedback retains current work and permits retry, without retry loops. Refresh restarts at consent. Build/preview works independently of backend/keys; production controls cannot be enabled by URL. |

## Recorded verification

- Environment: WSL Linux, project-local Node 24.14.0/npm 11.9.0, headless Chromium
  156. Setup readiness, strict type-check, all **37 existing focused tests**, and
  production build passed. The test suite includes all sequences, frozen records,
  deadline/stale-operation protection, acknowledgement gates, five-point known
  scores/orientation, earlier-v1 retention, optional feedback and duplicate guards.
- Production-built real App fixtures completed all four sequences through both
  tasks/four checkpoints, both surveys, blank/filled feedback and completion.
  Checked both initial models, retain/change, recommendation concealment, fixed
  message models, catalogue details/feasible costs, duplicate Lock/Send/Next/Submit/
  Finish, separate metadata, known 50 scores, and unchanged task records after feedback.
- One-shot synthetic failures outside the repository exercised load, task start,
  search, recommendation, message, ratings save and feedback. Retry succeeded;
  query/message/rating/text state remained available. No production failure
  controls or generic injection framework were added.
- Browser-clock expiry during independent choice, pending recommendation and pending
  message preserved the original plan/choices/messages, clamped end time to deadline,
  reached Ratings 1, and rejected later mutation/stale UI errors. Additional checks
  covered ten-minute preparation waits without a task, five-minute elapsed time with
  unchanged remount deadline, early invalid Override plan, null/unvisited choices,
  and the mixed `175/6` score with raw performance 75 unchanged.
- A complete practice walk-through used its feasible $350 plan and all four stages,
  producing eight labelled user/simulated-small messages without a router choice,
  recommendation, timer or practice survey. Early incomplete practice submission
  was also covered in the sequence walks.
- Actual participant production entry passed a keyboard-only early-submit walk
  through every phase to completion; native keyboard Override selection, lock,
  change, confirmation and next-stage focus passed separately. Native validation
  blocked negative/fractional ages and partial ratings; failed demographics retained
  input. Consent decline blocked progression.
- Viewports 1280×800, 1024×768, and 200% workspace enlargement had no horizontal page
  overflow. Workspace/zoom screenshots were visually reviewed. Sampled consent
  heading/body/enabled-button text contrast passed 4.5:1, with minimum **7.50:1**.
  This is a basic sample, not a comprehensive accessibility/contrast audit.
- Actual development server passed all four sequence/reset options and disabled
  timeout before experimental task start. Participant production entry hid developer
  controls, including with `?dev=true&sequence=4`. Refresh returned to fresh consent.
- Successful browser checks reported no page exceptions. Browser fixtures/tooling
  stayed under temporary storage, with no new repository browser dependencies.

## Coverage boundaries

| Platform/check | Result |
|---|---|
| WSL Linux + headless Chromium | Performed as recorded above |
| Real Windows browser through WSL localhost | Not performed |
| Actual macOS / native desktop Linux browser | Not performed; setup platform fixtures are simulations |
| Screen reader / comprehensive accessibility audit | Not performed; deferred broader audit is outside #22 |
| Full 15-minute real-time sessions | Not performed; timeout time was advanced with a browser clock |
| Backend persistence, balanced random allocation, real router/models | Not implemented/tested in standalone frontend |

## Provisional decisions and limitations

Researcher review remains necessary for consent/exit copy, demographic options and
eligibility, acknowledgement requiredness/wording, tutorial/preparation materials,
untimed fixed-small practice, catalog values/difficulty/distractors, live constraint
feedback and supplies policy, simulated recommendation reasons, the **adapted
five-point NASA-TLX** labels/orientation/validity, and optional feedback prompts/use.
The adaptation is not the unchanged standard measure. Raw labels/versions are
retained; checkboxes record acknowledgement, not proof of reading.

Refresh restarts in-memory state; recovery, detailed measurements/logging, exports,
oracle/usage/reliance analysis, deployment and real-study enforcement remain deferred.
Standalone default sequence 1 is not random balanced participant allocation; backend
#34/#38 own allocation/persistence/deadline authority. Joint API agreement remains
tracked in #31. See [shared contract/decisions](../experiment-service-contract.md),
[current refinement handoff](study-refinements-verification.md), and
[setup](development-setup.md) for implementation details.
