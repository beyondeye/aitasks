# t927: Autorefresh Disable By Default In Board

## Summary
Change board auto-refresh defaults from 5 minutes to 0 minutes so a new or missing board setting starts disabled. Existing explicit project or local settings continue to override the default.

## Implementation Plan
- Update board runtime fallback defaults in `.aitask-scripts/board/aitask_board.py` so missing settings produce `auto_refresh_minutes = 0` and no timer starts.
- Update settings TUI fallback defaults in `.aitask-scripts/settings/settings_app.py` so the Board tab shows `0` when no valid saved value exists.
- Update the config helper example, board docs, and board config split tests to match the new disabled default.
- Verify with focused board config and config utility tests.

## Verification
- `python3 tests/test_board_config_split.py`
- `python3 tests/test_config_utils.py`

## Final Implementation Notes
- **Actual work done:** Updated board and settings runtime defaults from `5` to `0`, aligned the config helper example, refreshed board documentation, and adjusted board config split test defaults.
- **Deviations from plan:** Used direct `unittest` entrypoints instead of `pytest` because `pytest` is not installed in the active `.aitask` virtualenv.
- **Issues encountered:** `python3 -m pytest tests/test_board_config_split.py -v` and `python3 -m pytest tests/test_config_utils.py -v` failed with `No module named pytest`; direct test execution passed.
- **Key decisions:** Existing explicit `auto_refresh_minutes` values in project/local config and migration fixtures were preserved so user preferences are not reset.
- **Upstream defects identified:** None
