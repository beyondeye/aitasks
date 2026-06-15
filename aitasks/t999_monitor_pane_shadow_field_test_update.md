---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [aitask_monitor, tmux, tests]
implemented_with: claudecode/opus4_8
created_at: 2026-06-15 14:48
updated_at: 2026-06-15 14:48
---

## Summary

Retroactively wrapped change updating `tests/test_multi_session_monitor.sh` to
match three prior monitor refactors, plus a one-line parser fix in
`monitor_core.py`:

1. **Module relocation** — imports moved from the old flat modules
   (`tmux_monitor`, `monitor_shared`, `monitor_app`) to the `monitor.*`
   package (`monitor.monitor_core`, `monitor.monitor_app`). A consolidated
   `PYPATH` (lib:monitor:board:scripts) replaces the per-test
   `LIB_DIR:MONITOR_DIR`.
2. **tmux gateway** — test mocks switched from patching
   `tm.subprocess.run` (MagicMock with `.returncode`/`.stdout`, subcommand at
   `cmd[1]`) to patching `TmuxMonitor.tmux_run` (returns `(rc, stdout)`,
   subcommand at `cmd[0]`), reflecting the sanctioned tmux gateway.
3. **9-field pane format** — every synthetic `make_row` helper now emits a
   trailing empty 9th field, the `@aitask_shadow_target` marker.

The accompanying `monitor_core.py` fix: `_parse_list_panes` previously called
`stdout.strip().splitlines()`, which stripped the trailing tab + empty field
off the **last** pane row, dropping its empty shadow-target marker. Changed to
`stdout.splitlines()` so the empty final field is preserved.

## Verification

`bash tests/test_multi_session_monitor.sh` → 43/43 passed.
