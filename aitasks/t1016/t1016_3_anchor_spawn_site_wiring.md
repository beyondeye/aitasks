---
priority: medium
effort: medium
depends: [t1016_2]
issue_type: enhancement
status: Implementing
labels: [child_tasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-17 13:36
updated_at: 2026-06-18 15:14
---

## Context

Spawn-site wiring child of t1016 (anchor task topic grouping). Several places
across the framework spawn a follow-up task but record no provenance. This child
threads `--followup-of <source_id>` (added in t1016_1) into each, so spawned
follow-ups automatically join their source task's topic on the board.

Depends on t1016_1 (the flag must exist) and follows t1016_2 (docs).

## Key Files to Modify

**Shell sites (each gets a test):**
1. `.aitask-scripts/aitask_archive.sh` — `create_carryover_task()` (~L556-612);
   the `create_args` array (~L583-590). It already knows `$orig_id`; add
   `--followup-of "$orig_id"` so the deferred-carryover manual-verification task
   anchors to the original.
2. `.aitask-scripts/aitask_verification_followup.sh` — the bug-task creation
   invocation (~L193-198). It already passes `--deps "$origin"`; add
   `--followup-of "$origin"`.

**Markdown procedures (regenerate goldens after editing):**
3. `.claude/skills/aitask-qa/follow-up-task-creation.md` — the qa follow-up test
   task knows its target task; document passing `--followup-of <target_id>` in
   the Batch Task Creation Procedure call.
4. `.claude/skills/task-workflow/risk-mitigation-followup.md` — Part 2 ("before",
   ~L144-162) and Part 3 ("after", ~L218-236): pass `--followup-of <original
   task_id>` so mitigations anchor to the task they protect.

**Caveat (document, do NOT force):**
5. `.claude/skills/aitask-review/SKILL.md` (creation patterns ~L167-217) —
   `aitask-review` reviews a diff/area with no single source task, so by default
   it must create a ROOT (no `--followup-of`). Only pass `--followup-of` when a
   specific reviewed task is the clear source. Add a one-line caveat; do not wire
   an unconditional anchor.

## Reference Files for Patterns

- `aitask_archive.sh` `create_args` assembly (~L583-590) and the invocation
  `new_file=$(./.aitask-scripts/aitask_create.sh "${create_args[@]}")` (~L593);
  structured output `CARRYOVER_CREATED:<id>:<path>` (~L611).
- `aitask_verification_followup.sh` invocation (~L193-198), output
  `FOLLOWUP_CREATED:<id>:<path>` (~L234).
- Canonical creation contract: `.claude/skills/task-workflow/task-creation-batch.md`
  (the `--followup-of` flag is documented there by t1016_2).
- Goldens regen: `./.aitask-scripts/aitask_skill_rerender.sh`; verify with
  `tests/test_skill_render_task_workflow.sh` + `aitask_skill_verify.sh`.

## Implementation Plan

1. `aitask_archive.sh`: add `--followup-of "$orig_id"` to `create_args`.
2. `aitask_verification_followup.sh`: add `--followup-of "$origin"` to the create
   call.
3. Edit the two markdown procedures (qa, risk-mitigation before+after) to pass
   `--followup-of`.
4. Add the `aitask-review` caveat.
5. Regenerate skill goldens.

## Verification Steps

- `tests/test_archive_carryover_anchor.sh` (new): archive a task with deferred
  manual-verification items → the carryover task file has `anchor: <orig_id>`.
- `tests/test_verification_followup_anchor.sh` (new): drive
  `aitask_verification_followup.sh` for a failed item → the created bug task has
  `anchor: <origin>` (and still `depends: [origin]`).
- `bash tests/test_skill_render_task_workflow.sh` + `aitask_skill_verify.sh` —
  clean after the markdown edits.

## Notes for sibling tasks

- The two shell sites are unit-testable end-to-end; prefer asserting on the
  created task file's `anchor:` line, mirroring how existing archive/verification
  tests assert on output files.
- Review's root-by-default behavior is deliberate (see the t1016 parent caveat) —
  do not "fix" it by forcing an anchor.
