# Issue #16 / Sprint 2 integration handoff

## Current flow

Consent → Demographics → Tutorial → Practice → Task 1 → NASA-TLX 1 →
Task 2 → NASA-TLX 2 → Optional feedback → Completion. #51 adds acknowledgement /
explicit-start preparation substates and a visual guide, described in the
[current refinement handoff](study-refinements-verification.md).

Practice is separate, untimed, excluded from experimental records, and has no
survey. Its fixed-small-model treatment remains provisional. Experimental
workspaces use the existing routing controls, and both surveys use the same
word-anchored component and versioned scoring definition. All materials and
router/agent behavior remain provisional/simulated; refresh restarts the demo.

The mock service provides one of four sequences:

| Sequence | Task 1 | Task 2 |
|---|---|---|
| 1 | A Automatic | B Override |
| 2 | B Automatic | A Override |
| 3 | A Override | B Automatic |
| 4 | B Override | A Automatic |

Default standalone participant mode uses sequence 1. This is not random balanced
recruitment allocation; backend #34 owns that future behavior and persistence.

## Development and participant builds

- `bash scripts/frontend.sh dev`: expand **Development controls** below the screen.
  Select a sequence, then **Apply sequence and reset demo**. Selecting an option
  alone does not reassign the current session. Reset discards in-memory work and
  returns to consent. **Trigger timeout** interrupts only an active experimental
  task, including a pending routing/agent operation; it is disabled in practice,
  introduction, surveys, and completion.
- `bash scripts/frontend.sh build`, then `bash scripts/frontend.sh preview`:
  participant production build. Controls are guarded by `import.meta.env.DEV` and
  their UI/labels are removed from the production bundle. No URL or keyboard
  shortcut enables them. Use a normal production build, not a deliberately
  overridden development `NODE_ENV` build, for participant-facing checks.

## Timing, submission, and late operations

After the explicit Start gate is confirmed, requirements/catalog data load. `beginTask` runs after the requirements
header is rendered, setting one absolute 15-minute deadline. Remounts/repeated
start calls preserve it. `TaskCountdown` derives remaining time from the deadline,
checks every second and on focus/visibility changes, and avoids continuous live
announcements. There is no countdown or deadline for practice or surveys.

Submission accepts any plan at any checkpoint, including incomplete/invalid work
and unconfirmed choices. Submission/timeout goes to that task's survey; practice
goes to Task 1 preparation. Termination can bypass a pending action lock and is guarded
against duplicate calls. At/after deadline, submission is timeout and `endedAt`
is clamped to the deadline. An early developer-triggered timeout records its actual
trigger time; it is a simulation, not a changed experiment duration.

The service validates queued planning operations against their original task,
checkpoint, and reset generation. Expired operations terminate before mutation;
stale work cannot change ended records or a new session. Unvisited decisions are
not created. Plans, costs, constraints, inspected IDs, messages, and partial locked
choices are preserved. App errors are scoped to the initiating screen, preventing
old operation failures from appearing as survey errors. Completed tasks are not
editable; each survey's responses/metadata/score become immutable on submission.

This is browser/system-clock timing, not authoritative study enforcement. Browser
throttling may delay visible navigation; the deadline and mutation checks preserve
the boundary. Clock changes and refresh recovery remain limitations; backend #38
owns authoritative deadline/persistence behavior in its phase.

## Repeatable integration checks / #22 handoff

1. Walk all four sequences from consent through completion. Complete all practice
   and experimental checkpoints. Verify assigned A/B/conditions, model locking,
   override concealment/retain/change, automatic no-choice, and two separate surveys.
2. Inspect the first requirements appearance: the task starts there with 15:00,
   not during consent/tutorial/data loading. Wait/advance time; remount within the
   session and confirm the same deadline. Practice remains untimed.
3. Submit empty/invalid plans early, including Override before initial lock. Verify
   correct survey, unchanged partial decisions, and no invented unvisited choices.
4. Expire during independent choice, pending recommendation, and pending message.
   Verify deadline-clamped end time, preserved work, survey navigation, and no
   later task mutation or stale error on the survey. Repeat Submit/timeout rapidly.
5. Answer both surveys explicitly; verify known scores and Task 2's initially blank
   responses. Completion follows TLX 2. No practice survey or participant selector.
6. In development, test all sequence/reset options and experimental-only timeout.
   Build/preview normally and confirm controls/labels are absent from DOM/bundle,
   including with URL parameters. Refresh must return to fresh consent.

## Recorded results — 2026-10-09

These #16 results describe the original integration build. Current #51 results,
including start gates, adapted ratings and optional feedback, are in the
[refinement handoff](study-refinements-verification.md).

- WSL Linux, project-local Node 24.14.0/npm 11.9.0; type-check, production build,
  and all 34 tests passed (15 service, 4 timing/race, 5 workload, 10 setup).
- Headless Chromium 156: production-built real App fixtures completed all four
  sequences, practice/four checkpoints, both experimental tasks/four checkpoints,
  both surveys, known scores, and completion. Start-call probes confirmed headers
  were rendered. Deadline remount, early empty/invalid submission, explicit zeros,
  duplicate actions, and all three pending/choice timeout cases passed.
- Actual participant production entry passed navigation and natural timeout with
  a simulated browser clock. Default assignment remained unchanged by URL parameters;
  developer DOM controls and bundle label strings were absent. No bypass was added.
- Actual separate Vite development process passed all four reset/assignment options,
  cleared demographic inputs, experimental-only manual timeout, and StrictMode.
  Screenshots of workspace and both production/development survey states were
  visually reviewed at a laptop viewport; no page errors in the successful checks.
- Actual participant 200% workspace enlargement had no horizontal page overflow.
  Early submissions through both surveys reached completion with heading focus
  and no editable task controls; refresh returned to fresh consent.
- Temporary fixtures/tooling stayed outside the repository. Time was advanced by
  a browser clock for timeout checks, not by waiting 15 real minutes. Actual
  Windows-browser/macOS, screen-reader, broader keyboard/error smoke checks
  remain #22 where available. This verifies demo integration, not real-study approval.
