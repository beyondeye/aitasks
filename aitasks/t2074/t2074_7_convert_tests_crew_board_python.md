---
priority: medium
effort: high
depends: []
issue_type: test
status: Ready
labels: [tests, test_infrastructure, python, board]
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

## Files (heuristic; superseded by the t2074_2 measurement)

- Crew/brainstorm/codeagent: test_crew_* (addwork_output_instructions,
  branch_delete_bounded, cleanup, groups, init, publish_upstream,
  pull_no_autostash, report, runner, runner_config_delivery, setmode, status,
  template_includes), test_brainstorm_cli, test_brainstorm_addwork_deadline,
  test_codeagent, test_codeagent_discuss, test_codeagent_op_wiring,
  test_codeagent_trail, test_codeagent_work_report.
- Board/ls/misc: test_boardcol_update, test_ls_boardcol_filter,
  test_shadow_scope, test_shadow_spinoff_create_contract,
  test_aitask_projects_doctor, test_chatlink_flow, test_change_surface,
  test_web_merge.
- Registry/install: test_verified_update, test_verified_update_flags,
  test_usage_update. Their header at :637 says "Every assertion above runs in
  LEGACY mode". t2074_2 converts their builders. Also
  test_install_superseded_models, test_install_superseded_prompt_pty.py,
  test_prune_retired_skills, test_install_engine_binary.
- Python: test_history_data.py, test_trail_links.py,
  test_task_declared_parity.py, test_settings_superseded_models.py,
  test_codebrowser_startup_focus_live.py (a serial carve-out module; run it on
  its own), and test_model_supersession.py (6 tests on its local
  `make_legacy_repo` copy at :558; convert them with
  `convert_to_branch_mode`).
- test_board_movement.py (`test_bench_baseline` :1608) and
  test_board_gate_digest_budget.py (:84) use `board_fixture`
  `branch_mode=False`. Drop the legacy comparison half, or move it to the
  Python quarantine module, and keep every branch-mode assertion and budget.

`board_fixture.py` itself is converted by t2074_2. Check that its registered
worktree layout still meets the board git-cost budgets in these tests.
