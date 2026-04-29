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

Create the shared desync state helper that reports remote drift for exactly two domains: `main` source code and `aitask-data` task/plan data. This helper is the data contract for later syncer TUI, switcher, monitor, and minimonitor work, with output modes matched to caller needs.

## Implementation Steps

1. Add `.aitask-scripts/lib/desync_state.py`.
   - Provide `snapshot [--fetch] [--ref main|aitask-data] [--format json|text|lines]`.
   - Keep `--json` as an alias for `--format json`.
   - Default `snapshot` reports both refs.
   - Default output is concise human-readable text.
   - JSON is the richest stable interface for Python/TUI callers.
   - Lines output is the robust shell-facing interface.
2. For `main`, run git in the repo root and compare local `main` with `origin/main`.
   - If `main` or `origin/main` is missing, report a non-fatal unavailable state.
   - If the current checkout is not `main`, still inspect the `main` ref by name.
3. For `aitask-data`, run git in `.aitask-data` only when the data worktree exists.
   - If `.aitask-data` is absent, report unavailable without failing.
   - Compare local `aitask-data` with `origin/aitask-data`.
4. For each available ref, compute ahead/behind counts, remote-ahead commit subjects, and changed paths from the remote-ahead range.
5. Replace `aitask_changelog.sh:check_data_desync` with a call into `desync_state.py snapshot --ref aitask-data --fetch --format lines`.
   - Preserve the current warning behavior when local `aitask-data` is behind.
   - Parse only simple scalar lines (`STATUS:` and `BEHIND:`) in the shell script.
   - If helper execution or output parsing fails, skip the warning rather than failing changelog gathering.
   - Do not add any resolver fallback that reads task files directly from `origin/aitask-data`.

## Output Contracts

- JSON output is canonical for full state:
  - Top-level object contains `refs`.
  - Each ref includes `name`, `worktree`, `local_ref`, `remote_ref`, `status`, `ahead`, `behind`, `remote_commits`, `remote_changed_paths`, and `error`.
  - Status values: `ok`, `missing_local`, `missing_remote`, `no_remote`, `fetch_error`, `missing_worktree`.
- Lines output is for shell callers and may expose only robust scalar fields:
  - `REF:<name>`
  - `STATUS:<status>`
  - `AHEAD:<n>`
  - `BEHIND:<n>`
  - Optional repeated `REMOTE_COMMIT:<subject>` and `REMOTE_CHANGED_PATH:<path>` lines.
- Text output is human-oriented and not intended for parsing.

## Verification

- `python3 -m py_compile .aitask-scripts/lib/desync_state.py`
- New desync helper tests covering JSON, text, and lines output modes.
- New desync helper tests covering missing remote, missing `.aitask-data`, missing local/remote refs, ahead/behind, fetch failure, changed paths, and commit subjects.
- Changelog integration test proving a behind `aitask-data` still emits the existing warning and unexpected helper output does not fail `--gather`.
- `bash tests/test_remote_drift_check.sh`
- `bash -n .aitask-scripts/aitask_changelog.sh`

## plan_verified

- codex/gpt5_5 @ 2026-04-29 21:23
