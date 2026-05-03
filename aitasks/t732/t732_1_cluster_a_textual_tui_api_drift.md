---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [testing, tui, textual]
created_at: 2026-05-03 16:29
updated_at: 2026-05-03 16:29
---

## Context

Child 1 of t732 (triage parent for 13 failing tests on `main`). Cluster A: Textual / Python 3.14 TUI API drift.

Two test files fail with Textual API-related errors. The framework's TUIs work in normal use, but the multi-session test harnesses trigger code paths that hit drift between the Textual version installed in `~/.aitask/venv` and the version assumed by the code.

## Failing tests (verified on `main` @ `74c59788` today)

### tests/test_multi_session_minimonitor.sh
```
AttributeError: 'MiniMonitorApp' object has no attribute '_thread_id'. Did you mean: '_thread_init'?
  at textual/dom.py:525 (run_worker)
RuntimeWarning: coroutine 'MiniMonitorApp._start_monitoring.<locals>._connect_control_client' was never awaited
```
Likely Textual API drift between versions, or an unmounted-app race.

### tests/test_tui_switcher_multi_session.sh
```
textual.css.query.NoMatches: No nodes match '#switcher_desync' on TuiSwitcherOverlay()
  at .aitask-scripts/lib/tui_switcher.py:483 (_render_desync_line)
```
The `#switcher_desync` Label query fires before mount in `_cycle_session` → `_render_desync_line`. Add a mount-guard or `query` (zero-or-more) instead of `query_one`.

## Root cause hypothesis

Textual upgraded internals between the version this code was written against and the version `ait setup` now installs. Two sub-issues:

1. **`_thread_id` removal** — `MiniMonitorApp` (or Textual base classes) likely set `_thread_id` historically. Recent Textual either renamed it (`_thread_init`) or removed the attribute. The unawaited coroutine warning is a downstream symptom: the failed `run_worker` left the connect coroutine dangling.

2. **`query_one('#switcher_desync')` race** — `_render_desync_line` is called from `_cycle_session` before `TuiSwitcherOverlay`'s mount completes in the multi-session harness. Single-session harnesses don't trip it because the overlay is already mounted by the time cycling occurs.

## Key files to modify

- `.aitask-scripts/lib/tui_switcher.py:483` — `_render_desync_line` `query_one` → `query` (zero-or-more) + early-return when empty, OR mount-guard via `if self.is_mounted:`. Whichever is idiomatic in the existing codebase.
- `.aitask-scripts/aitask_minimonitor.py` (or wherever `MiniMonitorApp` lives — grep for class) — replace `_thread_id` reference with the modern Textual API; ensure the `_connect_control_client` coroutine is awaited via `asyncio.create_task` or similar.
- Possibly `tests/test_multi_session_minimonitor.sh` and `tests/test_tui_switcher_multi_session.sh` if their setup is the trigger and the production code is fine.

## Reference patterns

- `CLAUDE.md` "Priority bindings + `App.query_one` gotcha" entry — describes a related `query_one` pitfall and the `self.screen.query_one` workaround. Same query-against-wrong-tree class of bug.
- `pip show textual` (in `~/.aitask/venv`) to learn the installed version.
- Other TUIs in `.aitask-scripts/board/aitask_board.py` and `.aitask-scripts/aitask_codebrowser.py` for `query` vs `query_one` patterns.

## Implementation plan

1. Confirm the Textual version: `~/.aitask/venv/bin/python -m pip show textual`.
2. Read Textual changelog (if a major version bump happened around `_thread_id` removal). Identify the new API.
3. Patch `tui_switcher.py:483` to mount-guard or `query`-based zero-or-more.
4. Find and patch the `_thread_id` reference (likely in `aitask_minimonitor.py`); fix the unawaited coroutine.
5. `bash tests/test_multi_session_minimonitor.sh` passes.
6. `bash tests/test_tui_switcher_multi_session.sh` passes.
7. Smoke-test the live TUIs (`./ait minimonitor`, `./ait switch` if applicable) to ensure no production regression.

## Verification

- Both failing tests pass: `bash tests/test_multi_session_minimonitor.sh && bash tests/test_tui_switcher_multi_session.sh`.
- Live `./ait minimonitor` opens without error in a real tmux session.
- No new failures in adjacent TUI tests: `for t in tests/test_*tui*.sh tests/test_*monitor*.sh; do bash "$t" >/dev/null 2>&1 || echo "FAIL: $t"; done`.
