---
priority: medium
effort: medium
depends: [t1981_2]
issue_type: feature
status: Ready
labels: [task_relations, task-workflow, skills]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-04 15:39
---

## Context

Child of t1981. Design: `aidocs/framework/task_relations.md`. **Read D4, and the
approval-stamp part of D8.**

This child wires the automatic triggers that enqueue relation analysis: on task
creation, on plan approval, and on fold. It also adds the backfill sweep.

It depends on t1981_2 **on purpose**: no automatic analysis runs before real
candidates exist and the D13.2 offline replay report is in t1981_2's plan.
Analysis stays **off by default** (`relations.enabled: false`). The hooks call
the enqueue helper from t1981_3, which is silent and always exits 0, so a
disabled project sees no change at all.

## Neighbours (Reality check first)

- **t1663_3** also edits `aitask_create.sh`'s batch-commit path
  (premise_baseline seeding at creation). If it has landed, plan against its
  version of the commit sites. If it is in flight, coordinate through
  `./ait note`.
- Re-verify the four commit sites before editing:
  - `finalize_draft`, child and parent;
  - `run_batch_mode --commit`, child and parent.

  Each is followed by `run_auto_merge_if_needed`, and the child sites also by
  `release_child_lock_checked`.

## Scope

1. **Creation hook** in `aitask_create.sh`. One helper call
   (`aitask_relations_enqueue.sh relations created <id>`) after
   `run_auto_merge_if_needed` at each of the four sites, after the child lock is
   released.
   - It is silent: with `--silent`, stdout stays a single path line.
   - It is detached and never fails the create.
   - Every creator goes through these sites: skills, follow-up wrappers,
     issue/PR import, chatlink, brainstorm, board.
2. **Plan-approval hook** in `.claude/skills/task-workflow/SKILL.md` Step 7 and
   in `plan-approved-stop.md`. Both are Jinja sources. The hook calls
   `aitask_relations_enqueue.sh relations plan_approved <id>`, which also writes
   the approval stamp.
   - It goes **outside** the `profile.record_gates` guard, so it runs under
     every profile.
   - Both sites call `ait relations stamp <id>`, not the silent enqueue. It
     writes the stamp synchronously, prints `STAMP:<plan_sha256>`, and detaches
     the publish and the enqueue.
   - Step 7 keeps the digest as the context variable `relations_expected_plan`
     (a new Context Requirements entry, initialized to null).
   - **Re-entry Routing's `IMPLEMENT` route** sets the same variable from `ait
     relations plan-digest <id>`, before work resumes. Step 8e passes it as
     `analysis-state --expect-plan` (D8).
   - In `plan-approved-stop.md` it fires **only for the stop reasons that keep
     the plan approved**: `deferred` and `resource_admission`, the rows that
     stamp `plan_approved_at`. `drift`, `drift_check_failed` and
     `parallel_admission` invalidate the plan and fire nothing.
   - Regenerate the affected goldens in the same commit, and run
     `./.aitask-scripts/aitask_skill_verify.sh`.
3. **Fold hook** at the end of `aitask_fold_mark.sh`, the last step of the fold
   sequence (`aitask_fold_content.sh` → `aitask_update.sh --desc-file` →
   `aitask_fold_mark.sh`), in every `--commit-mode`. The body has already been
   rewritten by then. Enqueue `relations fold <primary>`; the settle window
   absorbs a later commit by the caller.
4. **`ait relations sweep [--budget N] [--stale] [--unanalysed]`**: backfill for
   the existing backlog. It respects the daily cap and reports what it
   enqueued and what it skipped.

## Key files

- `.aitask-scripts/aitask_create.sh`
- `.claude/skills/task-workflow/SKILL.md`
- `.claude/skills/task-workflow/plan-approved-stop.md`
- `.aitask-scripts/aitask_fold_mark.sh`
- `.aitask-scripts/aitask_relations.sh`
- the goldens

## Reference patterns

- How `run_auto_merge_if_needed` is called at each commit site.
- The `{% if profile.record_gates %}` guard boundaries in Step 7: the new call
  goes after the `endif`.
- `aidocs/framework/skill_authoring_conventions.md`: "Regenerate goldens after
  any `.md.j2` or closure edit".

## Implementation plan

See `aiplans/p1981/p1981_4_relations_triggers.md`.

## Verification

- The creation hook fires once per created task, at each of the four sites.
- A `--silent` create still prints one line.
- A failing or disabled enqueue never changes the create's exit status or
  output.
- The plan-approval call renders under every shipped profile (golden diff), and
  writes a stamp.
- The fold hook enqueues the primary.
- `sweep` honours the budget and the cap.

The skill-change ports to the other agent trees are t1981_9.
