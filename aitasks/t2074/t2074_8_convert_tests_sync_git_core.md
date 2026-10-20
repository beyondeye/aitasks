---
priority: medium
effort: high
depends: []
issue_type: test
status: Ready
labels: [tests, test_infrastructure, sync, git]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:32
updated_at: 2026-10-20 12:32
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

## Shared-file gate (FIRST STEP)

These files may carry uncommitted hunks from t2064, which is in flight:
- `tests/test_task_push.sh`
- `tests/test_task_git.sh`
- `tests/test_ait_git_gateway_pull.sh`

Before editing any of them:
1. Run `git diff --quiet -- <file>` and check that t2064's commit is
   present in `git log`.
2. Re-run that check immediately before the first edit.
3. Do all non-overlapping files first.
4. If the gate still fails after that, stop and ask the user.

t2070 and t2071 landed during planning (02459e5a5 and a2d675a1c). Re-read
their landed versions of `test_sync_failopen_probes.sh`,
`test_txn_snapshot.sh`, `tests/lib/sync_fixture.sh` and
`test_metadata_partial_sync_recovery.sh` before editing.

## Files (heuristic; superseded by the t2074_2 measurement)

- `test_sync.sh`: `setup_sync_repos` (:34) is legacy and is used 16 times.
  T7 "Legacy mode" (:234) goes to quarantine.
- `test_task_push.sh`: about 70 `setup_remote_and_clone` calls are legacy by
  default. `j_setup` (:2808) is a legacy fixture. Turn `setup_branch_mode`
  (:158, which moves a clone to `.aitask-data`) into a **registered
  worktree**. T1, T3, T6 and T26 (labelled "(legacy mode)", with branch twins
  T2, T4, T7 and T27) go to quarantine. There are about 59
  `_AIT_DATA_WORKTREE` presets. Remove the `"."` presets and use real
  layouts.
- `test_sync_failopen_probes.sh` :215-218 and :473-499;
  `test_txn_snapshot.sh` (:303 and the presets).
- `test_task_git.sh`: T1 (:72), T4 passthrough (:116), T6 `ait git` legacy
  (:149), T10 cache-as-legacy (:260), T13e legacy root/subdir (:442) and T15
  nested repo/submodule (:632) are retired. They run detection **in the
  file's own shell**, so under the probe they would kill the whole file.
  Move them verbatim into `tests/test_legacy_retired_sync_git.sh`. T13c and
  T13d (inside `.aitask-data`, unlinked crew worktree) stay. They are
  supported resolutions and must keep passing.
- `test_remote_drift_check.sh`: replace `mark_branch_mode` (:111, a bare
  `mkdir .aitask-data` stub) with a real layout. T1 `LEGACY_MODE_SKIP` (:165)
  and the T8/T8b negative controls (:313, :333) go to quarantine. Convert the
  legacy fixtures in T8, T8b, T8c, T9, T10 and T12a-d. They pass `--unsynced`
  today. Keep the flag in the converted cases; t2074_9 removes the flag
  together with its call sites.
- `test_metadata_commit_seam.sh`: T14 `MODE:legacy` (:382) goes to
  quarantine. Convert the rest.
- `test_plan_approved_marker_drift.sh` :86: replace the `mkdir -p
  .aitask-data/.git` stub with a real layout.
