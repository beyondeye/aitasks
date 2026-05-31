---
Task: t884_4_risk_mitigation_followup_procedure.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_4_risk_mitigation_followup_procedure
Branch: aitask/t884_4_risk_mitigation_followup_procedure
Base branch: main
---

# Plan: t884_4 — Risk-mitigation procedure (before + after)

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Depends on t884_3 (`## Risk` + `risk_mitigations_planned`); uses t884_1's `risk_mitigation_tasks`.

## Goal

Propose-and-confirm before/after risk-mitigation follow-up tasks, gated by
`risk_evaluation`. **before** = independent task the original DEPENDS ON (created
Step 7); **after** = post-implementation follow-up (created new Step 8d).

## Steps

1. **New closure `.claude/skills/task-workflow/risk-mitigation-followup.md`**:
   - *Design-in-planning*: from `## Risk`, propose candidate before/after mitigations (AskUserQuestion, propose+confirm); record chosen + timing in the plan; thread a flag.
   - *Step 7 (before)*: create each via Batch Task Creation; **read-modify-write** the original's `depends:` to add the new ID (`--deps` REPLACES — read current first); append the ID to `risk_mitigation_tasks`.
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
