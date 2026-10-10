# Issue #51 refinements and #22 verification handoff

## Current presentation

Consent (Model Matchmakers branding) → Demographics → Before you start →
Visual guide → Practice preparation / Start → Practice → Task 1 preparation /
Start → Task 1 → Ratings 1 → Task 2 preparation / Start → Task 2 → Ratings 2 →
Optional additional feedback → Completion.

Before-start and task preparation are substates of tutorial/practice/task phases,
not new experimental tasks. Branding appears only on consent; later pages have
section headings, compact provisional/simulated notices, and read-only study
progress. Planning shows Stage N of 4. Checkpoints progress forward, while plan
items remain editable until submission and prior stage-model choices stay locked.

The SVG tutorial illustrates the Overleaf three-panel layout with a distinct
fictional 20-guest/$350 example and six highlighted sections. It uses no A/B
reference-plan or router-response fixtures. Back/Next navigates only the guide.
The service does not claim that guide navigation or checkboxes prove reading.

## Preparation and contract changes

`confirmPreparation(id, acknowledgedIds)` validates all required statement IDs
for the current phase, retaining version, wording, IDs, and `confirmedAt` in
`StudyState.preparations`. IDs: before-start, practice, task-1, task-2. Statements
are defined in `services/studyPreparation.ts`. Confirmation is explicit, starts
no task, and duplicate confirmation preserves the original record. Partial local
checkbox drafts are not recovery; accepted acknowledgements survive a remount.

Before-start acknowledgement is required before `completeTutorial`; the matching
task preparation is required before `beginTask`. A Start click confirms that gate
and mounts the workspace; requirements are not rendered or requested beforehand.
The existing requirements-visible `beginTask` boundary then creates the task and
deadline. Waiting on preparation screens cannot consume experimental time.

`submitSurvey(task-2)` now advances to feedback. `submitFeedback({ interfaceComments,
studyComments })` accepts blank strings, stores the session-linked optional text,
version/submission time, and advances to completion. No task/survey scores are
changed. Feedback prompts are the two agreed interface/study questions. Duplicate
Finish, wrong-step submission, and invalid payloads cannot overwrite the record.

These additions and changed transitions are a frontend contract draft for #31 /
backend state/record owners to review; implementation is not joint approval.

## Five-point workload adaptation

New tasks use `provisional-adapted-nasa-tlx-5-v2`: 0/25/50/75/100 and five labels
per dimension, retained in `survey.metadata.items[dimension].labels`. Demand,
effort, and frustration use Very low / Low / Moderate / High / Very high.
Performance uses Completely / Mostly / Moderately / Slightly / Not successful.
Higher values mean greater workload/worse performance, so this definition is not
reversed. No defaults; six explicit responses and the oriented unweighted mean.

The earlier `provisional-nasa-tlx-21-v1` definition remains exported as
`workloadSurveyDefinitionV1`; scoring follows each record's own metadata, not the
current definition. The reduction changes precision/presentation and is explicitly
a provisional adapted NASA-TLX, not an unchanged standard measure. All new wording,
acknowledgements, preparation, tutorial, scale, and feedback need researcher review.

## Repeatable #22 checks

1. Consent first, branding only there. Later headings/progress match the section;
   progress has no navigation controls. Complete demographics: Before you start.
2. All acknowledgement boxes initially unchecked; Continue/Start disabled until all
   required boxes are checked. Fail confirmation once: preserve checked boxes and
   allow retry. Reset clears accepted preparations and feedback.
3. Guide Back disabled on first card; Next/Back changes highlighted region/caption.
   Complete six sections. No experimental task, requirement, deadline, recommendation,
   or A/B reference answer is created/revealed during the guide or ready screens.
4. Start practice, then both experimental tasks explicitly. Spend time on every
   preparation screen: no deadline. After Start/requirements, each task has 15:00.
   Verify all four A/B/condition sequences, locking, agreement and retain/change labels.
5. Each ratings page has six rows/five labelled choices, none preselected. Empty or
   partial Continue cannot advance. Raw `[25,0,50,75,25,0]` yields `175/6`; all-left 0,
   all-right 100. Keyboard arrows work; remount preserves accepted answers.
6. Feedback appears only after Ratings 2. Blank and filled boxes both finish; fail
   once and verify text retained, retry, duplicate protection, and unchanged scores.
7. Check early/invalid submission, timeout during independent/locked choice or pending
   responses, unchanged deadline on remount, preserved records, and correct survey.
8. Check laptop/200% layouts, labels/focus/keyboard, production-hidden developer
   controls, development sequence/reset/timeout controls, and refresh to consent.

## Recorded results — 2026-10-09

- WSL Linux, Node 24.14.0/npm 11.9.0; type-check, production build, and all 37 tests
  passed (existing sequence/routing/timing coverage plus acknowledgement/feedback
  guards, versioned scale/known scores, and legacy-v1 retention).
- Headless Chromium 156: real App production-built fixtures passed all four sequences,
  all preparation gates and six guide cards/Back/Next, requirements-visible start
  probes, ten-minute preparation waits without deadlines, four checkpoints per task,
  initial-choice concealment, agreement/retain/change, five-point scores, blank/filled
  feedback, confirmation/feedback failures and duplicate Finish.
- Pending recommendation timeout preserved locked choices and rejected late updates
  without a stale survey error. Actual participant build passed hidden controls,
  keyboard labelled choices, workspace/ratings 200% enlargement, and refresh reset.
  Actual development reset/sequence control remained available and timeout was
  disabled before task start. No page errors in successful checks.
- Laptop and enlarged tutorial/ratings/workspace screenshots were visually reviewed.
  Temporary fixtures/tooling stayed outside the repository. Actual Windows-browser,
  macOS, screen-reader and broader #22 smoke checks are unperformed. Approval of the
  adapted measure/materials and joint backend contract agreement remain pending.
