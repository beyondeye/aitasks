---
priority: medium
effort: high
depends: [t2074_1, t2074_2]
issue_type: test
status: Ready
labels: [tests, test_infrastructure, gates]
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

- Gates/verification: test_gate_active_gates, test_gate_frontmatter_roundtrip,
  test_gate_guarded_archival, test_gate_orchestrator, test_gate_pass,
  test_gate_plan_approval_transitions, test_gate_stale_witness_parity,
  test_verification_followup, test_verification_followup_anchor,
  test_verification_stale, test_plan_externalize,
  test_ledger_block_append_integrity, test_note_read_receipts,
  test_note_section_order, test_note_with_live_composition.
- Locks/pick: test_task_lock, test_lock_diag, test_lock_force,
  test_lock_reclaim, test_lock_live_holder_gate, test_lock_anchor_tmux_live,
  test_crash_recovery_pid_anchor, test_pick_own_scoped_commit,
  test_anchor_create, test_anchor_update, test_claim_id,
  test_live_endpoint_degradation, test_live_endpoint_tmux_live,
  test_resource_admission_stop.
- Retired cases this batch quarantines (in
  `tests/test_legacy_retired_init_guard.sh`, or the name t2074_2 fixes):
  test_init_data.sh T1 and T21 (LEGACY_MODE); and
  test_task_data_writer_guard.sh section A (legacy wedged repo, lines
  137-160). test_init_data.sh T9 (help text mentions LEGACY_MODE) and T23
  (bare run inside `.aitask-data`) stay where they are; t2074_9 edits them.

Note: `aitask_lock.sh` uses the `aitask-locks` branch and plain git. That is
**not** legacy-related, so only its task-file fixtures need converting.
