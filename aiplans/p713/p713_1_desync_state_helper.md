---
Task: t713_1_desync_state_helper.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_2_syncer_entrypoint_and_tui.md, aitasks/t713/t713_3_sync_actions_failure_handling.md, aitasks/t713/t713_4_tmux_switcher_monitor_integration.md, aitasks/t713/t713_5_permissions_and_config.md, aitasks/t713/t713_6_website_syncer_docs.md
Archived Sibling Plans: aiplans/archived/p713/p713_*_*.md
Worktree: .
Branch: main
Base branch: main
---

## Summary

Create the shared desync state helper that reports remote drift for exactly two domains: `main` source code and `aitask-data` task/plan data. This helper is the data contract for the later syncer TUI, switcher, monitor, and minimonitor work.

## Implementation Steps

1. Add `.aitask-scripts/lib/desync_state.py`.
   - Provide `snapshot [--fetch] [--json] [--ref main|aitask-data]`.
   - Default `snapshot` reports both refs.
   - JSON is the stable interface for Python callers.
   - Text output is concise and human-readable for shell callers.
2. For `main`, run git in the repo root and compare local `main` with `origin/main`.
   - If `main` or `origin/main` is missing, report a non-fatal unavailable state.
   - If the current checkout is not `main`, still inspect the `main` ref by name.
3. For `aitask-data`, run git in `.aitask-data` only when the data worktree exists.
   - If `.aitask-data` is absent, report unavailable without failing.
   - Compare local `aitask-data` with `origin/aitask-data`.
4. For each available ref, compute ahead/behind counts, remote-ahead commit subjects, and changed paths from the remote-ahead range.
5. Replace `aitask_changelog.sh:check_data_desync` with a call into `desync_state.py --ref aitask-data --fetch --json`.
   - Preserve the current warning behavior when local `aitask-data` is behind.
   - Do not add any resolver fallback that reads task files directly from `origin/aitask-data`.

## Verification

- `python3 -m py_compile .aitask-scripts/lib/desync_state.py`
- New desync helper tests covering missing remote, missing `.aitask-data`, ahead/behind, fetch failure, changed paths, and commit subjects.
- `bash tests/test_remote_drift_check.sh`
- `bash -n .aitask-scripts/aitask_changelog.sh`

