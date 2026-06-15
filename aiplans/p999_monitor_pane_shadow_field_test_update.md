---
Task: t999_monitor_pane_shadow_field_test_update.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Updated `tests/test_multi_session_monitor.sh` to track three prior monitor-stack
refactors, plus a one-line parser fix in `.aitask-scripts/monitor/monitor_core.py`
that the test now exercises.

## Files Modified

- **`.aitask-scripts/monitor/monitor_core.py`** — `TmuxMonitor._parse_list_panes`
  changed from `stdout.strip().splitlines()` to `stdout.splitlines()`. The
  `.strip()` removed the trailing tab + empty field from the **last** pane row,
  dropping its empty `@aitask_shadow_target` (9th) field; dropping `.strip()`
  preserves it so non-shadow panes keep an empty final field.
- **`tests/test_multi_session_monitor.sh`** — suite-wide modernization:
  - **Module relocation:** `import tmux_monitor` / `from monitor_shared import …`
    / `import monitor_app` → `monitor.monitor_core` / `monitor.monitor_app`.
  - **Path:** added `BOARD_DIR` and a consolidated `PYPATH`
    (`lib:monitor:board:scripts`) replacing per-test `LIB_DIR:MONITOR_DIR`.
  - **tmux gateway:** mocks switched from `patch.object(tm.subprocess, "run", …)`
    returning a `MagicMock` (`.returncode`/`.stdout`, subcommand at `cmd[1]`) to
    `patch.object(tm.TmuxMonitor, "tmux_run", …)` returning `(rc, stdout)` tuples
    (subcommand at `cmd[0]`).
  - **9-field rows:** every `make_row` helper now appends an empty trailing field
    (the `@aitask_shadow_target` marker); kill-path stub stdout uses
    `"%99\t1234\t\n%9\t999\t\n"`.

## Probable User Intent

Keep the multi-session monitor test suite green after the monitor code moved into
the `monitor.*` package, after tmux calls were routed through the sanctioned
`TmuxMonitor.tmux_run` gateway (per `tmux_gateway.md`), and after pane listing
gained the trailing `@aitask_shadow_target` field. The `monitor_core.py` one-liner
is the real behavior fix the updated rows assert against — without it the last
pane's empty shadow marker is silently stripped.

## Final Implementation Notes

- **Actual work done:** Module-path, PYPATH, tmux_run-gateway, and 9-field-row
  updates across all tiers of `test_multi_session_monitor.sh`; `monitor_core.py`
  parser fix to preserve the empty trailing shadow-target field.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).
- **Issues encountered:** N/A (changes were already made before wrapping).
- **Key decisions:** Classified as `test` since the overwhelming majority of the
  diff is test maintenance; the `monitor_core.py` fix ships alongside because the
  rewritten rows directly assert the preserved 9th field.
- **Verification:** `bash tests/test_multi_session_monitor.sh` → 43/43 passed.
