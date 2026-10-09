# Issue #7 / Sprint 1 workspace verification

## Scope and reference

The current demo runs Consent → Demographics → Tutorial → Practice → Task 1
handoff. Practice is distinct, excluded from experimental records, untimed, and
uses a fixed simulated small model in each of its four stages. Its treatment,
catalog, prices, and live feedback are provisional, pending researcher approval.

Layout reference: `event-planning-mockup-small.png` in the
[Overleaf paper project](https://www.overleaf.com/read/yjwtghwfqtqp#635087): dark
three-panel Catalog / AI planning agent / Current event plan, with requirements
and time information above and Submit Plan at the bottom right. Narrow or enlarged
views can stack the panels without dropping controls or state.

All data/operations use `ExperimentService`. There is no backend request, database,
real model call, participant allocation selector, or research export. Refresh
restarts the demonstration. Experimental routing is #12; full two-task timing,
surveys, and completion are #16. Task 1 is a handoff, not a started experimental task.

## Repeatable browser checklist

Run the documented type-check/tests/build, then `bash scripts/frontend.sh preview`.
Use invented demographic responses only.

1. Check consent accept/decline and demographic required/age validation using
   [`introduction-verification.md`](introduction-verification.md). Complete the
   tutorial. Confirm practice requirements: 15 guests, $500 budget, vegetarian
   coverage, wheelchair access required, untimed. The three panels should be
   ordered left to right at a laptop viewport.
2. Search for Meadow in Venues: one result. Inspect Meadow Hall: capacity 15 and
   wheelchair access available. Details are not displayed before inspection.
   Select it: venue cost $100. Search/category changes must retain the selection.
3. Select Garden Room: capacity fails. Select Cedar Room: wheelchair access fails.
   Return to Meadow Hall. Inspect/select Classic Kitchen: required dietary coverage
   fails; Riverside Kitchen has too few servings. Harvest Kitchen meets both.
4. Add Basic Supplies: the reference total is $350 and all four constraints pass.
   Add Premium Supplies too: the total becomes $650 and budget fails. Remove Premium
   Supplies: $350 and budget passes. Remove Harvest Kitchen: $150 and dietary fails.
   Add Harvest Kitchen again. Repeated addition of an already selected package must
   not duplicate costs. Search for an unmatched name: empty results, plan unchanged.
5. Send a whitespace-only message: a service error appears and the draft is retained.
   Send a real synthetic message: one user message and one clearly simulated
   small-model response appear. Rapid repeated Send must not duplicate them.
6. Advance Venue → Catering → Supplies → Final constraint check. Model remains
   simulated small; no recommendation or model-choice buttons appear in practice.
   Plans, inspection state, and labeled conversation history remain available.
   Stage changes move focus to the stage heading; repeated Next must not skip a stage.
7. Submit the valid plan: go directly to Task 1 with no practice survey. In separate
   refreshed runs, submit an empty plan at Venue and an invalid Cedar Room plan:
   both proceed to the same handoff without requiring repair. Repeated Submit must
   not create another task or survey.
8. Check keyboard controls/focus, laptop readability, 200% enlargement, and no
   horizontal overflow or clipped item details. Submit remains accessible. Refresh
   returns to consent and clears the demo session.

Service tests verify the preserved practice plan, inspected IDs, per-stage model
records/messages, lack of practice survey, unvisited decisions, and absent Task 1
deadline at the handoff; the browser checklist verifies rendered behavior.

## Recorded results — 2026-10-08

- Environment: WSL Linux, project-local Node 24.14.0/npm 11.9.0.
- `bash scripts/frontend.sh type-check`: passed.
- `bash scripts/frontend.sh test`: all 23 passed (13 experiment-service tests and
  10 setup/launcher tests), including every sequence and the full practice lifecycle.
- `bash scripts/frontend.sh build`: passed.
- Production preview exercised with temporary Playwright tooling outside the
  repository and headless Chromium 156. The consent/decline and demographics
  checks were rerun, then the full practice checklist above passed.
- Browser checks covered search/empty results, inspection concealment, replacement
  and removal, known costs, all four constraint violations, retained failed-message
  drafts, fixed model/stage history, duplicate actions, and valid/empty/invalid
  submission directly to Task 1 without a practice survey.
- Visually reviewed screenshots at 1440×900, 1280×800, and 200% enlargement.
  Three panels align at laptop widths and stack when enlarged; no horizontal page
  overflow or clipped expanded details were found in the final build. Keyboard
  activation and stage/handoff focus passed. No page errors or external app requests.
- Actual Windows-browser/macOS and screen-reader checks were not performed. No
  backend integration or real model behavior was tested. Technical demo readiness
  does not approve the provisional study materials for participant collection.
