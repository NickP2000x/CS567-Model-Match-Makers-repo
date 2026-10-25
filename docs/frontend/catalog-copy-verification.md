# Issue #65 — expanded catalogs and mode-aware copy

## Scope

Experimental scenarios A/B each have 18 fictional fixed-price packages: six venues,
six catering options, and six supplies options. Practice retains its eight options.
The four scored constraints remain budget, venue capacity, dietary coverage
(including servings), and wheelchair accessibility. Supplies remain optional;
equipment coverage, travel, and availability are not scored or required.

New options provide cheaper and more expensive feasible choices, near-capacity
and partial-diet distractors, and cumulative budget tradeoffs. Original IDs, prices,
and scored facts remain stable. Search summaries omit capacity, dietary, serving,
and access facts; inspection reveals them. A/B share the same option/distractor
structure but need a pilot to assess difficulty rather than assume equivalence.

`src/mocks/scenarios.ts` remains the source. Regenerate backend fixtures with:

```bash
node backend/scripts/export_fixtures.mjs
```

The existing reference plans remain $350 practice, $800 A, and $1,200 B. Additional
researcher-only examples total $625/$890 for A and $1,025/$1,290 for B; they are
exported to `reference-plans.json`, never catalog/API answers.

The page banner separately labels agent and routing simulation. Consent describes
page-memory versus backend storage and live versus simulated replies accurately.
The guide and workspace explain that the agent advises; participants edit plans.
Before-start v2 warns of losing unsent work without falsely claiming API-mode
refresh restarts. Required acknowledgement IDs and task flow are unchanged; earlier
records retain their saved wording/version. Research notices remain provisional.

## Repeatable checks

1. Run `bash scripts/frontend.sh type-check`, `test`, and `build` from the root,
   and the backend's documented pytest checks in an isolated key-free environment.
2. Standalone mock: consent first, simulated agent/routing labels, memory/refresh
   notice, no provider IDs. Check decline and preparation gates, six tutorial cards,
   no A/B answer leakage, and practice with eight options and no survey.
3. A/B: 18 options, six in each category. Search/inspect new entries; confirm that
   filtering retains the selected plan, costs are package totals, supplies do not
   duplicate, and an unmatched query gives an empty result.
4. Exercise the additional reference plans and new near-capacity/partial-diet
   distractors. Check combined-budget failure with reference venue/catering plus
   the host bundle and original essentials. Remove supplies: no fifth check appears.
5. Walk Automatic and Override checkpoints, including initial concealment and
   final locking, agent reply labels, early/incomplete submission, both workload
   surveys, feedback, and completion. Check laptop layout and 200% enlargement.
6. Backend-connected mock and scripted-real-mode browser fixtures: persistent-storage
   and same-tab resume notices, independent agent/router mode labels, correct guide
   wording, and no claim that real replies are canned. Use temporary databases and
   scripted responses; do not make real provider calls for these checks.

## Verification results

Verified 2026-10-24 on the #65 working branch, WSL Linux, project-local Node
24.14.0/npm 11.9.0, Python 3.12, headless Chromium 156:

- Frontend strict type-check and production build passed. All 75 offline tests
  passed; the six opt-in API tests were initially skipped as expected, then all six
  passed separately with `MM_API_URL` pointing to an isolated mock backend.
  The final offline count includes the subsequent
  [setup/launcher follow-up checks](launcher-setup-verification.md).
- All 95 backend tests passed. The developer environment auto-loaded an unrelated
  ROS plugin missing `lark`; `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` isolates pytest.
  The app's settings configuration was set to ignore `.env` before importing the
  test app, and model/router modes were explicitly mock. No keys were loaded and
  all test databases were temporary.
- The first full backend run found an old agent-test expectation of three venues
  and a missing-package test that assumed RouteLLM was not installed. The venue
  expectation now includes six options; the missing-package test explicitly
  simulates an unavailable import instead of loading the developer's router.
- Actual production-built App in Chromium completed consent, unchanged demographics,
  preparation/tutorial, practice, both tasks, both surveys, feedback, and completion.
  Checked all four Automatic and four Override stages, concealed recommendations,
  retain/change choices, and locked stage models. The practice plan was submitted
  incomplete; the integrated service tests also cover experimental early submission.
- Browser catalog checks exercised six-per-category filters, 18-option results,
  inspection-only capacity details, search/no-results with retained selections,
  selected-item duplicate prevention, new capacity/dietary distractors, and feasible
  $625 A / $1,025 B plans with all four checks passing. A simulated message replied.
- Backend-connected browser checks used actual temporary mock-server sessions and
  scripted public mode flags to cover all four agent/router live/simulated combinations.
  Consent/banner/guide notices matched those flags; server persistence and same-tab
  refresh worked. These are UI flag checks, not live model or RouteLLM inference.
- Workspace screenshots at 1280×800 and 200% enlargement and live-mode consent
  were visually reviewed; no horizontal page overflow or page exceptions occurred.
  Browser tooling/screenshots were kept outside the repository under temporary storage.

Actual Windows-browser/macOS, screen-reader, live-provider quality/latency, and
router calibration checks were not performed. Existing developer study data was
not used or modified by verification. No researcher approval or real-study
readiness is implied.
