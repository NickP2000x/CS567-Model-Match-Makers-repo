# Issue #7 / Sprint 1 workspace verification

## Scope and reference

Issue #7 introduced the practice workspace; #16 now connects the complete flow
described in [study-flow verification](study-flow-verification.md).
Practice is distinct, excluded from experimental records, untimed, and
uses a fixed simulated small model in each of its four stages. Its treatment,
catalog, prices, and live feedback are provisional, pending researcher approval.

Layout reference: `event-planning-mockup-small.png` in the
[Overleaf paper project](https://www.overleaf.com/read/yjwtghwfqtqp#635087): dark
three-panel Catalog / AI planning agent / Current event plan, with requirements
and time information above and Submit Plan at the bottom right. Narrow or enlarged
views can stack the panels without dropping controls or state.

All data/operations use `ExperimentService`. There is no backend request, database,
real model call, participant allocation selector, or research export. Refresh
restarts the demonstration. The #12 routing controls and integration requirements
are documented in [`routing-verification.md`](routing-verification.md); full
two-task timing, survey connections, and completion are connected by #16.

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
   both proceed to the assigned Task 1 without requiring repair. Repeated Submit must
   not create another task or survey.
8. Check keyboard controls/focus, laptop readability, 200% enlargement, and no
   horizontal overflow or clipped item details. Submit remains accessible. Refresh
   returns to consent and clears the demo session.

Service tests verify the preserved practice plan, inspected IDs, per-stage model
records/messages, lack of practice survey, unvisited decisions, and absent Task 1
deadline before its requirements appear; the browser checklist verifies rendered behavior.

## Recorded results — 2026-10-08

These #7 results describe the practice-only build; current integration checks and
results are in [study-flow verification](study-flow-verification.md).

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

## #73 agent activity indicator

While a participant's message request is pending, the conversation panel shows a
stable `role="status"` label ("Agent is working on your message...") and an
`aria-hidden` secondary phrase from `agentStatusMessages.ts`, rotating every 4 s from
the first phrase. Only `sendMessage` starts it, from inside the operation `perform`
runs, so the duplicate-send guard is unchanged. It clears when the request settles,
and it is hidden (unmounting its timer) when the task ends or times out or the
checkpoint or task changes. Each request has an id, so a late response cannot
restart it. Services, backend, messages, prompts, and CSV are unchanged.

### Recorded results — 2026-11-05

- `frontend/tests/agent-activity.test.mjs` (fake timers): immediate first phrase,
  4 s rotation and wrap-around, restart from the first phrase, no updates after stop,
  no timer for one or zero phrases (label fallback), plain-text pass-through, and no
  activity text in stored messages.
- Frontend: type-check and build passed. Tests: 75 passed, 11 skipped, 1 failed
  (`launcher platform selection …`, which also fails on unmodified `origin/main`). The
  React render conditions (success, failure, timeout, checkpoint change, unmount) have
  no DOM test harness in this repository and were checked by code review only.
- Not done: manual browser and screen-reader checks with a delayed response.
