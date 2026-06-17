---
Task: t1016_3_anchor_spawn_site_wiring.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Sibling Tasks: aitasks/t1016/t1016_1_*.md, aitasks/t1016/t1016_2_*.md, aitasks/t1016/t1016_4_*.md
Archived Sibling Plans: aiplans/archived/p1016/p1016_*_*.md
Worktree: aiwork/t1016_3_anchor_spawn_site_wiring
Branch: aitask/t1016_3_anchor_spawn_site_wiring
Base branch: main
---

# Plan — t1016_3 Spawn-site wiring (anchor provenance)

Thread `--followup-of <source_id>` (from t1016_1) into framework sites that
spawn follow-up tasks, so spawned follow-ups auto-join their source's topic.
Depends on t1016_1; follows t1016_2.

## Steps

### Shell sites (each gets a test)
1. `aitask_archive.sh` `create_carryover_task()` — add `--followup-of "$orig_id"`
   to the `create_args` array (~L583-590).
2. `aitask_verification_followup.sh` — add `--followup-of "$origin"` to the bug-
   task create call (~L193-198); it already passes `--deps "$origin"`.

### Markdown procedures (regenerate goldens)
3. `.claude/skills/aitask-qa/follow-up-task-creation.md` — pass
   `--followup-of <qa target id>` in the Batch Task Creation call.
4. `.claude/skills/task-workflow/risk-mitigation-followup.md` Part 2 (~L144-162)
   and Part 3 (~L218-236) — pass `--followup-of <original task_id>`.

### Caveat (document, do NOT force)
5. `.claude/skills/aitask-review/SKILL.md` (~L167-217) — review has no single
   source task → creates a ROOT by default. Add a one-line caveat: only pass
   `--followup-of` when a specific reviewed task is the clear source. No
   unconditional wiring.

Regenerate skill goldens: `./.aitask-scripts/aitask_skill_rerender.sh`.

## Verification

- `tests/test_archive_carryover_anchor.sh` (new): carryover task file has
  `anchor: <orig_id>`.
- `tests/test_verification_followup_anchor.sh` (new): created bug task has
  `anchor: <origin>` and still `depends: [origin]`.
- `bash tests/test_skill_render_task_workflow.sh` + `aitask_skill_verify.sh` —
  clean. `shellcheck` the two edited shell scripts.

## Post-Implementation
Step 9 applies on completion. Note in Final Implementation Notes any sites you
found that spawn follow-ups but were intentionally left un-wired (and why).
