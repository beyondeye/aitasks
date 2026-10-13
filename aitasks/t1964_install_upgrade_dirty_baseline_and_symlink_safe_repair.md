---
priority: medium
effort: medium
depends: [1959]
issue_type: bug
status: Implementing
labels: [install, worktree]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1711
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-13 08:32
updated_at: 2026-10-13 11:46
---

## Origin

Spawned from t1959 during Step 8b review (originally raised in t1711's Step 8b, carried in t1959's task body).

## Upstream defect

- `install.sh:1167` — `commit_installed_files` has no pre-install dirty baseline. It commits framework paths as they stand after extraction, so a user's uncommitted edit under a framework path (e.g. `.gitignore`) can be swept into the upgrade commit.
- `install.sh` — `ait upgrade` never runs setup, so `setup_data_gitignore_symlink_safe` (t1711) reaches existing installs only through `ait setup`. An upgrade alone leaves the legacy trailing-slash `.aitask-data/` / `aitasks/` / `aiplans/` lines, and linked task worktrees keep showing `?? .aitask-data` (worktree cleanup then keeps them).

## Diagnostic context

install.sh already sources `aitask_setup.sh --source-only`, so the repair could be called before `commit_installed_files`. But without baseline protection that call would let a dirty `.gitignore` ride into the upgrade commit together with the repair. That is why the wiring must follow a baseline, not precede it. Setup's own baseline (`snapshot_pre_setup_dirty` / `commit_framework_files`) is the model. Since t1959 it scans absent paths too (`_ait_framework_paths <dir> 1`), so staged and unstaged deletions count as pre-existing changes. Note that `_ait_framework_paths`' list is duplicated in `commit_installed_files` (install.sh runs stand-alone via curl|bash, so it cannot source a shared helper before extraction).

## Suggested fix

1. Snapshot the dirty framework-path set (untracked + modified + staged, absent paths included) **before** extraction, then in `commit_installed_files` commit only (changed − baseline), path-scoped, and report the rest, mirroring `commit_framework_files`.
2. Then call `setup_data_gitignore_symlink_safe` after extraction and before `commit_installed_files`. Its `.gitignore` rewrite lands in the upgrade commit only when `.gitignore` was clean before the upgrade.
3. Tests: dirty `.gitignore` plus legacy line → repair on disk and not committed; clean → committed; foreign staged file never swept.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-13T08:46:44Z status=pass attempt=1 type=human
