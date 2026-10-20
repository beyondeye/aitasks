---
priority: medium
effort: high
depends: [t2074_1, t2074_2]
issue_type: test
status: Ready
labels: [tests, test_infrastructure, artifacts, task_attachments]
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

Artifacts: test_artifact_cli, test_artifact_dir_backend,
test_artifact_gitbranch_backend, test_artifact_manifest_lib,
test_artifact_fold_transfer, test_artifact_share_resolution.

Attachments: test_attach_archive_gc, test_attach_fold_rebind,
test_attach_gc_manifest_blocking, test_attach_local_backend,
test_attach_lock_callback_contract, test_attach_task_delete_decref,
test_attach_txn_worktree_isolation.

Other: test_gate_record, test_note_append, test_aitask_merge_boardgroup.

Many of these headers say "legacy-mode fixture". In legacy mode the
artifact/attachment resolvers (`lib/artifact_manifest.sh`,
`lib/attachment_meta.sh`, `lib/artifact_backends/local.sh`,
`lib/attachment_lock.sh`, `aitask_artifact.sh:205`) resolve to
`./artifacts`/`./attachments` in the code repo. In branch mode they resolve
under `.aitask-data`. Update path assertions to match.

Send a note to t1708: its premise "every pin runs in a LEGACY-mode fixture"
no longer holds. Quote the committed SHA.
