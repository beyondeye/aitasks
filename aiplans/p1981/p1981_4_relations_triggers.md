---
Task: t1981_4_relations_triggers.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_4 — Relations triggers

## Context

Wires the automatic enqueue points of `aidocs/framework/task_relations.md` D4:
creation, plan approval, fold, and the backfill sweep. It waits for t1981_2 on
purpose: there is no automatic analysis before real candidates exist and the
D13.2 report is in. Analysis stays off by default, so a disabled project sees
no behaviour change.

## Steps

0. **Reality check.**
   - Re-verify the four `aitask_create.sh` commit sites: `finalize_draft`
     child and parent, `run_batch_mode --commit` child and parent. Each is
     followed by `run_auto_merge_if_needed`, and the child sites also by
     `release_child_lock_checked`.
   - **Check whether t1663_3 has landed.** It edits the batch-commit path for
     `premise_baseline` seeding. Plan against the landed shape. If it is in
     flight, coordinate through `./ait note`.
   - Re-verify the `profile.record_gates` guard boundaries in
     `.claude/skills/task-workflow/SKILL.md` Step 7 and in `plan-approved-stop.md`.
   - Re-verify the commit point in `aitask_fold_mark.sh`.
1. **Creation hook.**
   - Add a function `_relations_enqueue_created <id>` in `aitask_create.sh`. It
     runs `aitask_relations_enqueue.sh relations created <id>` with stdout and
     stderr redirected, and `|| true`.
   - Call it at the four sites, after auto-merge and after the child lock is
     released.
   - Stdout stays a single path line under `--silent`.
2. **Plan-approval hook.**
   - In `SKILL.md` Step 7, **after** the `record_gates` `endif` of the "Record
     plan-approved gate" block, run
     `./.aitask-scripts/aitask_relations.sh stamp <task_id>`. It writes the stamp
     synchronously and prints `STAMP:<plan_sha256>` or `STAMP:disabled`.
     - Keep the digest as the context variable `relations_expected_plan`. Add
       it to the Context Requirements table, initialized to null.
     - Step 8e (t1981_5) passes it as `analysis-state --expect-plan`.
   - In **Re-entry Routing's `IMPLEMENT` route**, before work resumes, set
     `relations_expected_plan` from `aitask_relations.sh plan-digest <task_id>`.
   - Add the same `stamp` call in `plan-approved-stop.md`, outside its guard, inside
     the branch for the `deferred` / `resource_admission` stop reasons: the ones
     that stamp `plan_approved_at`. The `drift`, `drift_check_failed` and
     `parallel_admission` branches invalidate the plan, and must not fire it.
   - Regenerate the goldens and run `aitask_skill_verify.sh`.
3. **Fold hook.** At the end of `aitask_fold_mark.sh`, the last step of the
   fold sequence, in every `--commit-mode` (including `none`), enqueue
   `relations fold <primary>`. The body was rewritten earlier in the sequence.
4. **`ait relations sweep [--budget N] [--stale] [--unanalysed]`.**
   - Enqueue `sweep` jobs for pending tasks: with no record, with stale inputs,
     or both.
   - Respect the daily cap.
   - Print `ENQUEUED:` and `SKIPPED:<reason>` lines.

## Verification

- `tests/test_relations_triggers.sh`, with a stub enqueue that records its
  calls:
  - one call per create, at each of the four sites;
  - `--silent` output unchanged;
  - a disabled or failing enqueue changes neither the create's exit status nor
    its output;
  - the fold hook enqueues the primary.
- Golden diffs show the Step 7 line under every profile. In
  `plan-approved-stop.md`, the line appears only in the `deferred` /
  `resource_admission` branch.
- `sweep` honours the budget and the cap.
- `shellcheck`.

## Step 9

Post-implementation per task-workflow Step 9. Porting the skill change to the
other agent trees is t1981_9.
