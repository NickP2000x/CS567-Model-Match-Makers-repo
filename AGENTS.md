# Model Matchmakers agent guidance

## Scope and workflow

This is a basic **frontend research demonstration**, not the final experiment.
Read the selected GitHub issue, its dependencies, and relevant code before editing.
Use the nine active tasks in sprint trackers #24–#26; Sprint 3 orders #51 before #22. Closed superseded issues are
historical, and `later-experiment` issues are deferred. Keep changes scoped and plain.
This file owns shared project and research rules. Before editing frontend code,
configuration, tests, or related setup tooling, also read `frontend/AGENTS.md`.
Tools do not all discover nested instructions automatically; read that file
explicitly. Local instructions supplement these rules, not replace them.
See `docs/project-structure.md` for layout and
`docs/frontend/development-setup.md` for frontend setup. Shared documents stay in
`docs/`; frontend setup/verification handoffs live in `docs/frontend/`. The planned
backend documentation handoff is `docs/backend/README.md`; backend issue #32 owns
backend authorization, `backend/AGENTS.md`, and setup/verification documentation.
Preserve unrelated work. The repository owner approves PRs and handles merges;
never approve or merge a PR. Only commit, push, or create a PR when requested.

There is no backend, database, authentication, real router/model call, deployment,
oracle evaluator, token accounting, statistical analysis, or research-data export
in this phase. Use synthetic participant information and clearly label simulated
router/agent behavior. Implementation details and frontend verification commands
belong in `frontend/AGENTS.md`; keep shared research rules here rather than duplicating them.

## Research invariants

- Flow: Consent → Demographics → Tutorial → Practice → Task 1 → NASA-TLX 1 →
  Task 2 → NASA-TLX 2 → Optional feedback → Completion. Consent is the first participant screen.
  #51 adds provisional before-start acknowledgements, visual tutorial and explicit
  practice/task preparation starts within those phases. No requirements or task
  deadlines before Start; record acknowledgements without claiming proof of reading.
- Demographics cover age, gender, and prior LLM usage. Consent and other unapproved
  materials must be clearly marked provisional and pending researcher approval.
- Practice uses a distinct scenario and is excluded from experimental records.
  There is no survey after practice. Document its provisional demonstration treatment.
- The four constraints are budget, venue capacity, dietary coverage, and wheelchair
  accessibility. A/B need feasible reference plans and detail-only distractors.
- Checkpoints: Venue → Catering → Supplies → Final constraint check. Route at every
  reached experimental checkpoint and fix the selected model throughout its stage.
- Automatic: show simulated recommendation/reason and apply directly, without a
  participant model-choice or confirmation button.
- Override: independently choose small/large → lock initial choice → reveal router
  recommendation/reason → retain/change → confirm final choice. Never reveal or
  request a recommendation before initial lock. Preserve separate per-checkpoint
  initial/recommended/final choices and basic decision timestamps.
- Support A Automatic/B Override, B Automatic/A Override, A Override/B Automatic,
  and B Override/A Automatic. Participants never choose assignments. The paper plans
  12 participants, three per randomly allocated sequence; this frontend only mocks it.
- Experimental timing starts when requirements appear, lasts up to 15 minutes,
  and stops at submission/timeout. Allow invalid/incomplete submission. Preserve
  current work at timeout and proceed to the correct task survey. No fabricated
  choices for unvisited checkpoints or late responses mutating ended tasks.
- Reuse one six-response NASA-TLX survey: mental, physical, temporal demand,
  performance, effort, frustration. Keep consistent approved or explicitly
  provisional wording/anchors. Retain raw responses and compute the unweighted
  mean using correctly oriented values; do not guess performance reversal.
  #51's five-point fully labelled presentation is a provisional adapted NASA-TLX,
  not an unchanged standard measure. Version labels/anchors/orientation and retain
  earlier definitions for earlier records. Optional feedback is session-linked,
  separate from workload scoring, and remains provisional pending researcher review.
- Development sequence/reset/timeout controls must be hidden in participant builds.
- Refresh may restart the demonstration; recovery and detailed measurements are
  deferred. Document this limitation, and do not claim real-study readiness.

The paper §§4–5.4 confirms stage locking, checkpoint interactions, constraints,
timing, sequences, and workload measures. Separate these from additional prototype
requirements such as permissive submission and timeout-to-survey behavior.
Flag unresolved consent/demographics, practice, scenario values, live feedback,
router reasons, and survey presentation instead of inventing approved protocol.
The short decisions list planned in #3 owns those provisional details.

## Shared development rules

- Never read, search, expose, or modify likely secrets unless the user explicitly
  requests access to a named file. Never commit credentials or real participant data.
- Run the relevant component's documented checks. Verify visible behavior manually
  for meaningful UI changes. Report unavailable or unperformed checks honestly.
- Keep this prototype plain and task-focused; do not add speculative infrastructure.
- Do not delete or move files or overwrite unrelated changes. If removal is needed,
  explain what the developer should remove manually.

## Optional AI skills

Use these if available; otherwise follow the same workflow directly:

- `coding-build`: implement approved scope, inspect patterns, verify focused changes.
- `coding-research`: investigate read-only and cite evidence.
- `coding-debug`: reproduce an observed failure, isolate cause, verify a minimal fix.
- `customize-opencode`: only for OpenCode configuration, agents, or skills.

No custom skills or per-issue skill mappings are required. Refresh/restart agent
sessions after this file changes if the tool caches repository instructions.
