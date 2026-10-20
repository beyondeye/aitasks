---
priority: medium
effort: high
depends: [t2074_1, t2074_2]
issue_type: test
status: Ready
labels: [tests, test_infrastructure]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:32
updated_at: 2026-10-20 12:34
---

## Context

This is part of t2074 (remove legacy repository mode). Today about 125 test
files build legacy fixtures (`git init`, then a real `aitasks/`, then a plain
commit) and drive task writers. Once t2074_9 enforces the data-branch layout,
these fixtures will be refused. This batch converts its files to real
branch-mode fixtures **before** the flip, so they pass both before and after.

Binding rules: read the "Probe definition" (quarantine files, completion
evidence) and C0/C1 in
`aiplans/p2074_remove_legacy_repository_mode_support.md`. Read t2074_2's
plan for this batch's **authoritative file and case list**. The measurement
note in this task's `## Inbox` supersedes the heuristic list below. Also
read t2074_2's pre-conversion baseline (summary/`TOTAL` per file, Python
test ids).

## Method (every file)

- Build fixtures with `ait_fixture_to_branch_mode` / `fixture_data_git`
  (`tests/lib/data_branch_fixture.sh`) or `convert_to_branch_mode`
  (`tests/lib/branch_mode_repo.py`), all from t2074_2.
- Rewrite assertions that read task or plan commits on the code branch
  (`git log`, `git show`, `git status` in the repo root) to use the data
  branch. Keep every original behavioural assertion: same claim, now against
  the data branch.
- Do not delete suites. Do not weaken unrelated assertions.
- A case whose **sole** purpose is legacy behaviour is moved verbatim into this
  batch's quarantine file (named in t2074_2's plan, header naming
  t2074_9 as its deleter). It is never left in place to "expected-fail".
- Bash files whose bodies run in `( … )` subshells must use the file-backed
  counters (`assert_counters_init` / `assert_counters_load`, CLAUDE.md
  "Testing").

## Acceptance (Probe definition)

Every non-quarantined file in the batch must:
- exit 0 on the current tree;
- exit 0 under the t2074_2 probe, applied as a throwaway patch in an isolated
  worktree and never committed;
- print its summary line under the probe;
- reach `TOTAL` ≥ baseline minus the assertions moved to quarantine. For
  Python, every retained test id must pass in the junit output.

Record the per-file evidence table in Final Implementation Notes.

## Files (heuristic; superseded by the t2074_2 measurement)

- Create/update: test_create_email_lock, test_create_id_claim_abort,
  test_create_manual_verification, test_create_manual_verification_gates,
  test_create_project_flag, test_create_silent_stdout,
  test_parallel_child_create, test_draft_finalize,
  test_update_label_staging, test_update_risk,
  test_characterize_batch_label_frontmatter, test_atomic_task_file_writes,
  test_launch_mode_field, test_verifies_field, test_followup_kind_roundtrip,
  test_followup_backfill_recovery, test_file_references, test_label_autoadd.
- Archive/fold/zip: test_archive_* (carryover, carryover_anchor, folded,
  no_overbroad_add, rearm_exit_trap, related_issues, shadow_prune,
  verification_gate), test_fold_mark, test_fold_file_refs_union,
  test_fold_risk_mitigation_drop, test_zip_old, test_auto_merge_file_ref,
  test_migrate_archives.
- Import/contribute/revert: test_issue_import_contributor,
  test_issue_import_amend_guard, test_pr_contributor_metadata,
  test_contribute, test_revert_analyze, test_revert_analyze_batch,
  test_t167_integration, test_deps_unblock_batch.

Many of these use `setup_fake_aitask_repo` (`tests/lib/test_scaffold.sh:13`),
then build a legacy repo on top. Converting right after the fixture is built
usually needs a single call. test_fold_mark has the heaviest git use, so check
every commit assertion there.
