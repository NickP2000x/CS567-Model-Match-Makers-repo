# Issue #5 introduction verification

## Scope and reference

Consent → synthetic demographics → tutorial → practice. Screens use one
app-boundary experiment service, with no direct response-fixture imports. The
original #5 handoff is now the #7 practice workspace; #51 adds before-start
acknowledgements, the visual guide and explicit preparation starts. See the
[current refinement checks](study-refinements-verification.md) and
[`workspace-verification.md`](workspace-verification.md) for Sprint 1 completion checks.

Visual reference: `event-planning-mockup-small.png` in the
[Overleaf project](https://www.overleaf.com/read/yjwtghwfqtqp#635087). The introduction
uses the mockup's dark neutral/blue palette; the three-panel workspace is documented
in [`project-structure.md`](../project-structure.md). Copy, questionnaire options,
practice treatment, and tutorial example remain provisional in
[`experiment-service-contract.md`](../experiment-service-contract.md).

## Repeatable browser checklist

Run `bash scripts/frontend.sh build`, then `bash scripts/frontend.sh preview`.
Use synthetic answers only.

1. On a fresh load, confirm consent appears first with the pending-approval notice
   and no demographics or task requirements. Decline: a stop message appears, with
   no path into demographics. Refresh: consent returns.
2. Tab to Accept and continue; check the focus outline and press Enter. The
   demographics heading receives focus. Rapid repeated acceptance must not skip it.
3. Submit empty fields: native required-field validation blocks progression. Check
   a negative/fractional age is blocked; blank gender and unselected usage are blocked.
4. Enter age 25, a whitespace-only gender, and an example usage selection. Submit:
   the service error is visible and age/usage remain filled. Replace gender with
   “Prefer not to say”; use Tab/Enter to submit. The tutorial receives heading focus
   and the error disappears after the Before you start acknowledgements.
5. Use Back/Next to review the fictional $290 illustrated guide, four constraints,
   checkpoints, automatic/override ordering, stage locking, and submission/timing.
   No actual A/B recommendation, reason, or reference plan is displayed.
6. At a laptop viewport and 200% zoom, verify readable guide content, visible focus,
   no horizontal page overflow, and access to Finish instructions.
7. Finish instructions, acknowledge practice preparation, and use Start practice:
   the workspace loads, labeled untimed and provisional. Refresh returns to consent
   and clears the previously entered demographic answers.

## Recorded results — 2026-10-08

These #5 results refer to the original introduction-only build. The #7 results
include rechecking these introduction behaviors against the working workspace.

- WSL Linux, project-local Node 24.14.0/npm 11.9.0.
- Type-check, all 21 existing service/setup tests, and production build passed.
- Production preview exercised with temporary Playwright tooling outside the
  repository, using headless Chromium 156. Checklist behaviors above passed at
  1280×800 and 200% zoom. Screenshots were visually reviewed.
- No page exceptions or external application requests occurred. Failed form
  submission retained current inputs; repeated acceptance did not skip screens.
- This is automated browser/visual verification, not a Windows-browser or actual
  macOS smoke check. Screen-reader verification was not performed.
- #31 joint contract approval remains pending. These results verify the standalone
  frontend demonstration, not researcher approval or real-study readiness.
