---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [shadow, skills, review_loop, concurrency]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1877]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-09-24 09:20
updated_at: 2026-09-24 15:44
completed_at: 2026-09-24 15:44
---

## Problem

The shadow must review only changes associated with the coding agent it follows. Sharing a checkout does not make another session's changes part of that review. The current skill explicitly instructs the opposite.

Authoritative source: `.claude/skills/aitask-shadow/impl-challenge.md`, Review-state assessment step 3 (around lines 139–148), tells the shadow to cross-check the plan, "review everything", label other paths as "possibly unrelated", and invite the user to narrow scope. This is propagated to rendered agent/profile variants, including `.agents/skills/aitask-shadow-fast-codex-/impl-challenge.md`. `tests/test_skill_render_aitask_shadow.sh` currently pins parts of this behavior.

Observed while shadowing pane %138 for t1852_2: the task's 28 new files were under `goengines/`. Shared-worktree changes from t1869 (cross-repository notes/resolver), t1847 (frozen-agent reopening), and other tasks were repeatedly reviewed and emitted as actionable concerns. Even after the Go implementation passed review, subsequent rounds kept producing other tasks' concerns, prompting handoffs and another approval loop. The user explicitly rejected this scope and requested this follow-up on 2026-09-24.

## Required behavior

1. Make followed-agent ownership the default review boundary in the authoritative shadow instructions and every implementation-review tier/recheck path. Repository dirtiness is discovery input, not proof of ownership. Users should not have to request a narrow review to get the correct default.
2. Establish scope from the bound followed agent, its task and plan/implementation notes, task-associated commits, and evidence of the files/changes it actually made. Resolve its actual checkout/worktree rather than assuming the shadow's cwd is the same. A plan's file list is evidence, not a rigid allowlist: legitimate implementation additions, tests, renames and documented deviations must still be reviewed.
3. Preserve coverage of committed, staged, unstaged and untracked changes AFTER attribution. Preserve NUL-safe path handling and support pre-commit tasks whose entire implementation is untracked. Do not stop at the first nonempty channel or review only historical commits when newer associated edits exist.
4. Explicitly exclude changes attributable to other sessions/tasks from the followed task's review snapshot, findings, structured concern block, recommendation and recheck carry-forward. Relevant unchanged dependency/caller code may still be read as context; a defect caused by the followed change remains in scope. Do not turn that context read into an independent review of someone else's work.
5. Define handling for ambiguous attribution, including mixed ownership within one file, missing task/plan evidence, and an unidentifiable checkout. Use available evidence and state limits; request a targeted clarification only when necessary. Never silently fall back to reviewing the whole workspace or treating ambiguity as ownership. Do not claim complete coverage when relevant changes cannot be attributed.
6. Keep the ownership boundary stable across manual `>r` and automated rechecks, refreshing it when the followed agent/task actually changes. Prior concerns discovered only through the old overbroad scope must be identified as outside scope and omitted from the active task's actionable block, without requiring rejection or fixes in another task. New unrelated workspace changes must not expand the review or prevent it from converging.
7. Whole-workspace or another task's review requires an explicit user request. A short scope disclosure is sufficient; no recurring scope-choice prompt when the followed agent is already known.

## Implementation surfaces

- `.claude/skills/aitask-shadow/impl-challenge.md` (source of the faulty composite/attribution contract).
- `.claude/skills/aitask-shadow/SKILL.md.j2`, `impl-review-angles.md`, `round-preamble.md`, and `concern-format.md` as needed to keep review entry, snapshots, context tracing and concern carry-forward consistent.
- Rendered Claude/Codex/OpenCode profile variants and `tests/golden/procs/aitask-shadow/` through the normal generation workflow, not isolated edits to generated copies.
- `tests/test_skill_render_aitask_shadow.sh` and focused scope/regression checks; any helper introduced should have behavior tests rather than only prose assertions.

## Acceptance and verification

- Reproduce the shared checkout scenario with followed-task untracked Go files plus another task's tracked and untracked changes: only the followed task's associated changes become review subjects or actionable concerns.
- Cover followed-task commits plus newer staged/unstaged/untracked changes, filenames containing spaces, legitimate unplanned files, a separate followed worktree, and ambiguous shared-file ownership.
- On recheck, unrelated new work and previously misattributed concerns do not re-enter the task's concern block or block its approval. Genuine unresolved/regressed concerns in the followed task remain visible.
- Missing ownership evidence produces an honest limitation/targeted clarification, not a full-workspace fallback or false clean result.
- Verify the contract across tiers, profiles and supported code agents; run the shadow render/golden tests and skill verification.

## Relationship to existing work

Related t1650 concerns delta-scoped automatic rechecks. This task fixes WHOSE changes any review covers, including a first/full review; it must not depend on t1650 or absorb its round-record/protocol redesign. t1852_2 is the discovery context, not an implementation dependency. Fixes to t1869/t1847 themselves are outside this task.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-24T08:41:16Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-24T12:27:59Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-24T12:43:59Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:27f435339e6e4b33

> **✅ gate:risk_evaluated** run=2026-09-24T12:43:59Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1873/risk_evaluated_2026-09-24T12:43:59Z-risk_evaluated-a1.log`
