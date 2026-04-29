---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [tui, scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-29 09:39
updated_at: 2026-04-29 21:23
---

## Context

Parent t713 adds an `ait syncer` TUI for making remote desync visible and resolvable. This first child establishes the shared, testable data layer that later TUI and monitor/switcher work will consume.

The syncer must track exactly two desync domains:
- `main`: the source-code branch in the main worktree.
- `aitask-data`: the task/plan data branch in `.aitask-data` when branch mode is active.

Do not include `aitask-locks` or `aitask-ids`; those branches are handled by existing infrastructure. Do not add a fallback that reads task files directly from `origin/aitask-data`; the point is to surface stale local state, not hide it.

## Key Files to Modify

- `.aitask-scripts/lib/desync_state.py`: new pure helper and CLI for snapshotting desync state and later action dispatch.
- `.aitask-scripts/aitask_changelog.sh`: replace the local `check_data_desync` implementation with a call into the shared helper for `aitask-data`.
- `tests/test_desync_state.py` or a bash wrapper under `tests/`: focused helper tests using scratch git repos.

## Reference Files for Patterns

- `.aitask-scripts/aitask_changelog.sh`: current `check_data_desync` logic that warns when `.aitask-data` is behind `origin/aitask-data`.
- `.aitask-scripts/aitask_remote_drift_check.sh`: existing remote-ahead detection style and structured output conventions.
- `tests/test_remote_drift_check.sh`: scratch origin/local/other clone fixtures for testing remote ahead/behind behavior.
- `.aitask-scripts/lib/task_utils.sh`: branch-mode detection conventions for `.aitask-data`.

## Implementation Plan

1. Implement `desync_state.py` with a small CLI:
   - `snapshot [--fetch] [--json] [--ref main|aitask-data]`
   - The default snapshot reports both `main` and `aitask-data`.
   - `--ref aitask-data` reports only the data branch and is suitable for changelog warning reuse.
2. For each tracked branch, compute:
   - availability status: `ok`, `missing_local`, `missing_remote`, `no_remote`, or `fetch_error`.
   - `ahead` and `behind` counts using `git rev-list --left-right --count` or equivalent.
   - remote-ahead commit subjects.
   - remote-ahead changed paths.
3. For `main`, run git commands in the repo root and compare local `main` with `origin/main`. If the current branch is not `main`, still report `main` by ref name when it exists.
4. For `aitask-data`, run git commands in `.aitask-data` when that worktree exists; otherwise report unavailable without failing.
5. Replace `aitask_changelog.sh:check_data_desync` with a helper invocation that fetches and warns only when `aitask-data.behind > 0`.
6. Keep output parsing stable for later children: JSON is canonical for Python callers; concise text output is for humans/scripts.

## Verification Steps

- Run the new desync tests.
- Run `bash tests/test_remote_drift_check.sh` to guard related remote-state behavior.
- Run `bash -n .aitask-scripts/aitask_changelog.sh`.
- Run `python3 -m py_compile .aitask-scripts/lib/desync_state.py`.
