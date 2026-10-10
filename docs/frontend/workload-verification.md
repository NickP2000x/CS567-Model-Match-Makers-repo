# Issue #15 workload survey and #16 handoff

## Presentation and scoring

`WorkloadSurvey` is one reusable service-backed survey for task-1/task-2. Each
new task uses #51's five fully labelled choices with no preselection; values map
to 0/25/50/75/100. The earlier 21-point definition is retained for earlier records.
Native required radio groups enforce
explicit answers; keyboard Space/arrow keys work without autosave stealing focus.

The definition is `frontend/src/services/workloadSurvey.ts`, version
`provisional-adapted-nasa-tlx-5-v2` (earlier `provisional-nasa-tlx-21-v1` preserved).
Wording, anchors, increments, and presentation are
**provisional, pending researcher approval**, not approved study materials.

- Mental/physical/temporal demand, effort, frustration: Very low → Very high.
- Performance: Completely successful → Not successful. Higher stored values mean more
  workload for this explicitly chosen presentation, so performance is not reversed.
- The service computes the unweighted mean of six correctly oriented common-scale
  values on submission. Orientation comes from stored metadata, not the dimension
  name. Raw values are never transformed/overwritten; the mean is not rounded.
- Each experimental task retains the wording/anchor version, scale, and per-item
  orientation in `survey.metadata`. `survey.rawScore` remains null until submission.
  Practice has null metadata/score and no survey.
- Draft saves follow the record's increment (25 for v2, 5 for v1). Missing, nonfinite, out-of-range,
  or off-point values are rejected atomically.

## Integration in #16

Mount `WorkloadSurvey` only for the current ended experimental task at tlx-1/tlx-2.
Pass `service`, the explicit task ID, the parent action `pending` flag, and the same
guarded `perform` callback used by `App` (`Promise<boolean>`, errors exposed and
pending cleared in finally). The component also checks service task/step identity.
Its draft is scoped to task identity; reuse cannot carry Task 1 selections into Task 2.

Selections save the latest draft through the service, serialized by the parent
guard. Radio controls remain usable during draft saves for continuous keyboard
rating; Continue waits for pending saves. Submission disables editing and saves the
entire visible draft before submitting. Failed saves/submission retain current
selections; a subsequent edit or Continue can retry. A failed save does not loop.
Accepted partial responses survive a component remount within the service session;
refresh still restarts the demonstration. Unsaved local drafts are not recovery.

No score/results dashboard is displayed. #16 now mounts both task-linked surveys
in the normal flow. See [study-flow verification](study-flow-verification.md) for
current integrated results; the component checks below also used isolated fixtures.

## Repeatable focused checks

1. Fresh task survey: six rows, five labelled choices each, zero checked. Empty/partial Continue
   must not advance or create a score. Explicit zero answers count as real responses.
2. Tab/Space/arrow-key a rating and verify focus remains on the selected radio while
   autosaving. Remount after an accepted partial save: only those choices restore.
3. Complete v2 raw answers `[25, 0, 50, 75, 25, 0]` in dimension order. Expected score
   is `175 / 6` (29.166…); performance remains raw 75. All-left gives 0; all-right 100.
4. Submit twice rapidly: one accepted survey, correct Task 2 transition, immutable
   submitted answers/metadata/score. Reuse for Task 2: all choices initially blank;
   complete it and verify its score and final feedback transition without changing
   Task 1's record; optional feedback Finish then reaches completion.
5. Fail one draft save and one submission: selected circles remain, no retry loop,
   no fabricated score/advance; Continue retries the full visible draft successfully.
6. Practice/current active/wrong-task survey must be unavailable. Inspect laptop
   rendering and 200% enlargement: word anchors readable, circles clickable, no
   horizontal page overflow. Check the normal introduction/practice flow too.

## Recorded results — 2026-10-09

These #15 results describe the component-only build; current full-flow results
are recorded in [study-flow verification](study-flow-verification.md).

- WSL Linux, project-local Node 24.14.0/npm 11.9.0.
- Type-check, production build, and all 30 tests passed (15 existing service,
  5 workload/scoring, 10 setup tests). Known scores, declared reversed-anchor
  metadata, invalid/missing values, frozen metadata, atomic failure, both task
  identities, and duplicate protection passed.
- Production-built isolated survey checked with headless Chromium 156: 126 radios,
  no defaults, empty/partial validation, keyboard arrows during delayed saves,
  accepted-answer remount, known score, duplicate submission, same-component Task 2
  reuse, save/submission failures and retry, and no practice survey passed.
- Screenshots at 1280×800 and 200% enlargement were visually reviewed. The browser
  check waited for the final autosave before activating Continue; no page errors.
- Real participant production app regression passed for consent/decline, required
  demographics, tutorial concealment, fixed-small practice/four stages, and incomplete
  practice submission to Task 1. No experimental/survey bypass or external requests.
- Temporary browser tooling/fixtures stayed outside the repository. Actual
  Windows-browser/macOS and screen-reader checks were not performed; full experimental
  navigation/timing remains #16. These results do not approve real data collection.
