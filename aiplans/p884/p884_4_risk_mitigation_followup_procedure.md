---
Task: t884_4_risk_mitigation_followup_procedure.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_4_risk_mitigation_followup_procedure
Branch: aitask/t884_4_risk_mitigation_followup_procedure
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 18:14
---

# Plan: t884_4 — Risk-mitigation procedure (before + after)

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Depends on t884_3 (`## Risk` + `risk_mitigations_planned`); uses t884_1's `risk_mitigation_tasks`.

## Verify-pass findings (2026-06-01, anchors confirmed against current tree)

- **t884_3 landed** — `risk-evaluation.md` exists, is profile-agnostic (in
  `WRAPPED_FILES_INVARIANT`), authors the two-subsection `## Risk` section with
  per-risk bullets `<description> · severity: <…> · → mitigation: <link or "TBD">`,
  and threads `risk_level_code_health` / `risk_level_goal_achievement` /
  `risk_mitigations_planned`. The `→ mitigation` placeholder is exactly the seam
  this task fills. ✅
- **planning.md §6.1** risk dispatch is at lines 272–273 (zero-footprint
  `{%- if profile.risk_evaluation is defined and profile.risk_evaluation %}`). The
  mitigation-proposal hook goes immediately after it (still inside the same gate),
  feeding `→ mitigation` links into the `## Risk` section just authored. ✅
- **SKILL.md Step 7** risk-field write hook is at lines 282–293 (same gate),
  right after the cross-repo-child-assignment hook (line 281). The "before"
  creation + dep-wiring hook slots alongside it, inside the same gate. ✅
- **SKILL.md Step 8c** (line 425) is the last sub-step before Step 9 (line 435);
  **Step 8d** suffixes cleanly with no renumber of 8b/8c. ✅
- **`aitask_update.sh`** exposes `--deps DEPS` (line 138: "replaces all"),
  `--risk-code-health` / `--risk-goal-achievement` (lines 250–251), and
  `--risk-mitigation-tasks IDS` (line 252). **Both `--deps` AND
  `--risk-mitigation-tasks` REPLACE the full list** — neither is additive — so the
  "before"-creation step must read-modify-write *both* the original's `depends:`
  and its `risk_mitigation_tasks:` (read current, append the new ID, write the
  full list back). ✅
- **Render test** (`tests/test_skill_render_task_workflow.sh`): `Test 5` already
  proves the `risk_evaluation: true` gate fires at the two t884_3 dispatch sites;
  extend it to also assert the new before/8d hooks. The new closure is
  profile-agnostic (no `{{ profile.* }}` — the propose-confirm always runs; only
  the dispatch sites are gated) → add it to `WRAPPED_FILES_INVARIANT` with one
  canonical golden, mirroring `risk-evaluation.md`. ✅

## Goal

Propose-and-confirm before/after risk-mitigation follow-up tasks, gated by
`risk_evaluation`. **before** = independent task the original DEPENDS ON (created
Step 7); **after** = post-implementation follow-up (created new Step 8d).

## Steps

1. **New closure `.claude/skills/task-workflow/risk-mitigation-followup.md`**:
   - *Design-in-planning*: from `## Risk`, propose candidate before/after mitigations (AskUserQuestion, propose+confirm); record chosen + timing in the plan; thread a flag.
   - *Step 7 (before)*: create each via Batch Task Creation; **read-modify-write** the original's `depends:` to add the new ID (`--deps` REPLACES — read current first); **also read-modify-write** `risk_mitigation_tasks` (`--risk-mitigation-tasks` ALSO REPLACES — read current, append the new ID, write full list). Both can be set in one `aitask_update.sh --batch` call.
   - *Step 8d (after)*: create each via Batch Task Creation.
2. **`planning.md`** — gated design proposal hook feeding `## Risk` mitigation links.
3. **`SKILL.md`** — Step 7 "before" creation (gated, alongside t884_3 write); new **Step 8d** after 8c (SUFFIX — do not renumber 8b/8c).
4. **Regenerate** variants + goldens; run `aitask_skill_verify.sh` — same commit.

## Reference patterns

- `upstream-followup.md` (8b) + `manual-verification-followup.md` (8c) — propose-confirm + seeding + return contract.
- `cross-repo-child-assignment.md` — Step 7 creation + dep wiring + gating.
- `task-creation-batch.md` — create heredoc template.

## Verification

- `aitask_skill_verify.sh` passes; goldens committed together.
- Dry-run plan w/ `risk_evaluation: true` + a risk: offer appears; "before" creation adds dep edge (original Blocked in `ait ls`) + appends `risk_mitigation_tasks`; "after" created at 8d. Key absent ⇒ no offer.
- 8b/8c numbering unchanged.

## Notes for sibling tasks

`risk_mitigation_tasks` populated here is read by t884_5. Keep design/creation split clean — NO creation/mutation in plan mode.
