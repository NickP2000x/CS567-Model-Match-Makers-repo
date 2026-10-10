# Issue #12 routing verification and integration handoff

## Implemented boundary

`frontend/src/features/routing/RoutingPanel.tsx` renders inside the center
AI planning agent panel of `PlanningWorkspace`. The service owns the recorded
initial/recommended/final models and timestamps; radio selections are local until
the participant explicitly locks/confirms them. Components do not import router
response fixtures. Recommendations/reasons and agent responses remain simulated;
reason wording is provisional, pending researcher approval.

- Automatic: a reached active checkpoint requests its recommendation, displays the
  model/reason, and commits directly. No participant choice or confirmation control.
- Override: independent small/large choice → lock → recommendation reveal → explicit
  retain/change selection → final confirmation. No request or displayed recommendation
  before initial lock. After confirmation the model cannot change within the stage.
- Agent messaging and Next remain disabled until the service has a committed model.
  Early incomplete/invalid submission is still permitted; missing choices are not
  fabricated. Cached committed decisions survive workspace remounts.
- A request failure retains choices and requires Retry recommendation; it does not
  silently retry or substitute a model. Retry is an operational action, not an
  Automatic model-choice/confirmation step.
- Practice retains its untimed, fixed-small-model provisional treatment. It does
  not request/display a router recommendation.

The normal app now mounts the experimental workspaces, timers, surveys, and
completion through #16. See [study-flow verification](study-flow-verification.md)
for integrated checks/results. Participant builds have no developer assignment
selector or testing bypass.
The #51 heading/progress/preparation and clearer agreement/choice labels preserve
these routing rules; see [current refinement checks](study-refinements-verification.md).

## Integration requirements for #16

- Mount `PlanningWorkspace` with the current task ID and a fresh React key per task.
  It derives scenario/condition from service assignments; participants do not choose.
- Pass the parent action's `pending` flag along with the existing `perform` callback.
  The workspace combines it with service `pendingOperations`. This prevents a
  recommendation effect from racing the parent lock/advance operation's completion.
- `perform` must return `Promise<boolean>`: true on success, false when guarded or
  failed, while exposing errors and clearing pending in `finally`. It must prevent
  concurrent actions, as the existing `App` implementation does.
- Keep the routing panel keyed by task/checkpoint (already wired). Each reached
  checkpoint starts with fresh local radio selections; service decisions persist.
- Preserve the existing requirements-visible task-start boundary and add the actual
  timer/timeout trigger in #16. Ended tasks must not accept late responses. Do not
  treat a remount/re-render as a new decision, task start, or extended deadline.

## Focused checks

Run the documented type-check/tests/build. When experimental tasks are connected,
verify all four assigned sequences; until then use an isolated component/workspace
fixture outside the participant app with the same service and parent action guard.

1. A/B Automatic, every checkpoint: recommendation/reason displays and the model
   applies without Lock/Confirm controls. Initial choice/timestamp stay null.
2. A/B Override, every checkpoint: no radios selected by default; no recommendation
   request or reason before Lock. Try both initial models and both retain/change paths.
   Confirm the initial choice is immutable once locked and distinct final choices
   are not recorded until confirmation.
3. Check initial-lock ≤ recommendation-shown ≤ final-commit timestamps; repeat
   renders/remounts must preserve them and not re-request committed recommendations.
   Rapid repeated Lock, Confirm, Send, or Next must not duplicate records or skip stages.
4. Send remains disabled before commitment; after commitment messages use that model
   and checkpoint. Advance through all four stages, retaining history and old decisions.
5. Fail one recommendation: no automatic retry loop, no fabricated model, locked
   initial choice retained. Retry succeeds without changing initial-choice timing.
6. Submit during independent choice: keep only reached/partial decisions. End during
   a delayed recommendation: ended work must remain unchanged by the late result.
7. Check keyboard radio/confirmation controls, focus on recommendation/committed
   status, dark center-panel styling, laptop layout, and 200% enlargement.
8. Recheck the normal consent-through-practice flow: no experimental recommendation
   leaks into the tutorial/practice, and practice still goes to Task 1 without a survey.

## Recorded results — 2026-10-09

These #12 results describe the earlier component-only build; current integrated
results are in [study-flow verification](study-flow-verification.md).

- Environment: WSL Linux, project-local Node 24.14.0/npm 11.9.0.
- Documented type-check, tests (25 passed: 15 service tests and 10 setup tests),
  and production build passed. Added service guards/concurrent-request checks
  complement the existing four-sequence and retain/change coverage.
- Headless Chromium 156 exercised production-built isolated workspaces for all
  four A/B × Automatic/Override combinations and every checkpoint. Verified both
  initial models, retain/change, agreement/disagreement, no pre-lock requests or
  reason display, disabled pre-commit agent work, immutable committed choices and
  timestamps, labeled messages, and repeated action/render/remount protection.
- Synthetic recommendation failures stopped automatic retries; explicit retry
  retained the initial model/timestamp. Early incomplete override submission kept
  partial decisions. A delayed result did not mutate an ended task.
- A lock/parent-action scheduling race found during failure checks was fixed by
  forwarding the parent's pending state; the failure/retry reproduction and full
  checkpoint checks passed afterward. Development React StrictMode effect replay
  and remount retained one automatic request.
- Keyboard Space selected initial/final radio options; Enter confirmed the final
  choice. Recommendation and committed-status focus passed. Screenshots at
  1280×800 and 200% enlargement were visually reviewed; no page overflow was found.
- The real production app was separately checked: consent/decline, demographic
  validation, tutorial concealment, fixed-small practice conversation/four stages,
  and incomplete submission to the Task 1 handoff still work. No experimental
  bypass was added. No page errors; no external requests from that participant app.
- Isolated fixtures, Playwright, and failure/delay controls stayed outside the
  repository/participant build. Actual Windows-browser/macOS and screen-reader
  checks were not performed. Full two-task timer/survey integration is untested
  until #15/#16. These results are not researcher approval or real-study readiness.
