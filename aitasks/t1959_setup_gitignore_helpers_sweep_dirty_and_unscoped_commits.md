---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [worktree, aitask_pick]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1711
followup_kind: upstream_defect
created_at: 2026-10-12 21:44
updated_at: 2026-10-12 22:03
---

## Origin

Spawned from t1711 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:2724` — `setup_worktree_dirs_gitignore` commits with an unscoped `git commit -m` (no `-- .gitignore`). That is a whole-index sweep: whatever a concurrent session has staged in this shared checkout rides into the setup commit.
- `.aitask-scripts/aitask_setup.sh` — the self-committing `.gitignore` helpers (`setup_draft_directory`, `setup_python_cache_gitignore`, `setup_gate_logs_gitignore`, `setup_testmap_gitignore`, `setup_shadow_store_gitignore`, `setup_worktree_dirs_gitignore`) ignore `AIT_SETUP_DIRTY_BASELINE`. When their own rule is missing, they commit `.gitignore` as it stands, sweeping a user's pre-existing uncommitted `.gitignore` edit into a setup commit.
- `install.sh:1623` — `ait upgrade` (install.sh) never runs setup. `setup_data_gitignore_symlink_safe` (added by t1711) therefore reaches existing installs only through `ait setup`; an upgrade alone leaves the legacy `.aitask-data/` line in place. A call before `commit_installed_files` is possible (install.sh already sources `aitask_setup.sh --source-only`), but `commit_installed_files` has no dirty-baseline protection, so that should follow the fix above rather than precede it.
- `tests/test_cd_guard_lint.sh` — already failing on main, independent of t1711:
  - `tests/test_add_model.sh` has no `enter_scratch_cwd` (first cd at line 134; last touched by t1940);
  - four `unconfined-andchain` cd sites: `tests/test_aitasks_home.sh:319`, `tests/test_install_engine_binary.sh:224`, `tests/test_setup_hooks_only.sh:74`, `tests/test_upgrade_prunes_retired_scripts.sh:73`.

## Diagnostic context

t1711 added a re-run `.gitignore` repair (`setup_data_gitignore_symlink_safe`). Review found that placing it right after `setup_data_branch` let the later self-committing helpers carry both the repair and a user's dirty `.gitignore` into a setup commit. Reproduction: record `.gitignore` dirty in the baseline, remove the `.aitask-testmap/` rule, run the repair, then `setup_testmap_gitignore`. HEAD then contains the user's edit and the repair, and `.gitignore` is clean.

t1711 sidestepped this only for its own repair, by running it last, directly before the baseline-protected `commit_framework_files`. `tests/test_data_branch_setup.sh` Test 35 pins that placement, and Test 34 replays the sequence. The helpers themselves are unchanged and still sweep when their own rule is missing.

The cd-guard lint failures turned up while running the related suites. They sit in files t1711 did not touch.

## Suggested fix

Route every `.gitignore` helper through one baseline-aware path: write only, and let `commit_framework_files` commit, or path-scope each commit and skip it when `.gitignore` is in `AIT_SETUP_DIRTY_BASELINE`. Then consider calling `setup_data_gitignore_symlink_safe` from install.sh behind the same protection. Fix the cd-guard sites per `aidocs/framework/testing_conventions.md` (or split them into their own task).
