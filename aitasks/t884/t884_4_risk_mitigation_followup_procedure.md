---
priority: high
effort: high
depends: [t884_3]
issue_type: enhancement
status: Ready
labels: [task_workflow, task-planning]
created_at: 2026-06-01 00:31
updated_at: 2026-06-01 00:31
---

## Context

Core child of t884 (see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Adds the risk-mitigation procedure that **proposes** before/after follow-up tasks for the risks identified by t884_3, and **creates** the confirmed ones. Depends on t884_3 (the `## Risk` section + `risk_mitigations_planned` flag) and transitively on t884_1 (the `risk_mitigation_tasks` field).

User decision: **propose both before & after, user confirms** (no auto-create). The offer is gated by the `risk_evaluation` profile key (Jinja) and structurally mirrors `manual-verification-followup.md`'s propose-confirm shape.

- **"before" mitigation** = an **independent task the original DEPENDS ON** (NOT a child). Created at Step 7 (post-approval). Wire the blocking edge by **read-modify-write of the original's `depends:`** (because `aitask_update.sh --deps` REPLACES the list — there is no additive flag). Also append its ID to the original's `risk_mitigation_tasks` (drives t884_5's force-reverify).
- **"after" mitigation** = a post-implementation follow-up created at a **new Step 8d** (mirrors `upstream-followup.md` at 8b / `manual-verification-followup.md` at 8c).

Mitigations may target either risk dimension (e.g. a "before" spike/prototype to de-risk goal-achievement; an "after" refactor/test to de-risk code-health).

## Key Files to Modify

- New closure `.claude/skills/task-workflow/risk-mitigation-followup.md` — (1) **design-in-planning**: from the `## Risk` section, propose candidate before/after mitigations (AskUserQuestion, propose+confirm); record chosen ones + before/after timing in the plan; thread a flag. (2) **Step 7 creation** (before): create each "before" mitigation via the Batch Task Creation Procedure, then read-modify-write the original's `depends:` to add the new ID, and append to `risk_mitigation_tasks`. (3) **Step 8d creation** (after): create each "after" follow-up via Batch Task Creation.
- `.claude/skills/task-workflow/SKILL.md` — hook the Step 7 "before" creation (alongside t884_3's risk write, gated by `risk_evaluation`); add a new **Step 8d** (after Step 8c manual-verification-followup) for "after" creation. **Suffix only — do NOT renumber 8b/8c.**
- `.claude/skills/task-workflow/planning.md` — the design-in-planning proposal hook (gated), feeding the `## Risk` section mitigation links.
- Regenerate goldens (`tests/golden/skills/`, `tests/golden/procs/task-workflow/`) + run `aitask_skill_verify.sh` **in the same commit**.

## Reference Files for Patterns

- `upstream-followup.md` (Step 8b) and `manual-verification-followup.md` (Step 8c) — propose-confirm offer + Batch Task Creation seeding + return-to-next-step contract.
- `cross-repo-child-assignment.md` — Step 7 post-approval creation + dependency wiring + flag gating.
- `task-creation-batch.md` — the `aitask_create.sh --batch --commit` heredoc template.
- `aitask_update.sh` `--deps` (REPLACES — confirm; read current `depends:` first, append, write full list).

## Implementation Plan

1. Author `risk-mitigation-followup.md` with the three parts (design proposal, Step 7 before-creation+dep-wiring, Step 8d after-creation).
2. Wire the gated proposal hook in planning.md and the Step 7 / Step 8d hooks in SKILL.md (suffix Step 8d).
3. Implement read-modify-write of `depends:` for "before" mitigations + populate `risk_mitigation_tasks`.
4. Regenerate variants + goldens; run `aitask_skill_verify.sh`.

## Verification Steps

- `aitask_skill_verify.sh` passes; goldens regenerated + committed together.
- Dry-run a plan with `risk_evaluation: true` and ≥1 identified risk → confirm the propose-confirm offer appears, a "before" mitigation creation adds the dep edge (original shows Blocked in `ait ls` until it lands) AND appends to `risk_mitigation_tasks`, and an "after" mitigation is created at Step 8d.
- With `risk_evaluation` absent → no offer, no Step 8d action (rendered variant omits it).
- Confirm 8b/8c numbering unchanged.

## Notes for sibling tasks

`risk_mitigation_tasks` populated here is read by t884_5 (force-reverify). t884_5 adds Step 6.0a (suffix). Keep the design/creation split clean: NO task creation or frontmatter mutation during plan mode.
