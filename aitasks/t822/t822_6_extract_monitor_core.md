---
priority: high
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 10:40
updated_at: 2026-06-14 09:51
---

Extract the headless monitor core into `.aitask-scripts/monitor/monitor_core.py` so both the Textual TUIs (`ait monitor`, `ait minimonitor`) and the future applink WebSocket listener drive the same capture/control pipeline.

## Context

t822_3 produced the design doc `aidocs/applink/monitor_port_design.md`. Its §"Headless-core extraction" defines the exact symbol set that moves and the two hard rules from the t952 tmux-gateway track. This task is the first §"Deferred follow-up tasks" bullet and unblocks the applink listener (next sibling).

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_core.py` (new) — receives the symbols listed in the design doc's extraction table: `TmuxPaneInfo`/`PaneSnapshot`, `TmuxMonitor` (discovery, capture, send/kill/switch/spawn verbs, control-client lifecycle, `cycle_compare_mode`, `kill_agent_pane_smart`, `find_companion_pane_id`), `TmuxControlClient`/`TmuxControlBackend`, `TaskInfoCache`.
- `.aitask-scripts/monitor/tmux_monitor.py`, `tmux_control.py`, `monitor_shared.py` — leave thin import shims for backwards compatibility (existing import sites keep working).
- The physical relocation of `TmuxControlClient`/`TmuxControlBackend` out of `monitor/tmux_control.py` was **deliberately deferred from t952_3 to ride with this extraction** — monitor_core is their natural home.

## Hard rules (from t952_3 / design doc)

- monitor_core **delegates** tmux exec to `lib/tmux_exec.py` (`TmuxClient.run_via_control` / `run_async_via_control`) — it must NOT re-own the control-client-when-alive / subprocess-fallback dispatcher. The delegation seam already exists in `TmuxMonitor.tmux_run` / `_tmux_async`.
- No Textual imports in monitor_core.

## Reference Files

- `aidocs/applink/monitor_port_design.md` — §Headless-core extraction (authoritative symbol table + what stays UI-bound)
- `.aitask-scripts/lib/tmux_exec.py` — the gateway substrate (do not duplicate)
- `.aitask-scripts/monitor/minimonitor_app.py` — second consumer; the seam must serve both TUIs
- `aiplans/archived/p822/p822_3_monitor_port_design.md` — Final Implementation Notes (warns line refs may drift; re-verify symbols at pick time — monitor files were under active churn from the t952 track)

## Implementation Plan

1. Re-verify the design doc's extraction-table line refs against current files (symbol names are stable anchors).
2. Create `monitor_core.py`; move the table's symbols; keep `monitor/` package-relative imports consistent with the existing defer-import patterns (`tmux_control` is TYPE_CHECKING-only in `tmux_monitor`).
3. Replace moved code in `tmux_monitor.py`/`tmux_control.py`/`monitor_shared.py` with re-export shims.
4. Run the existing monitor/tmux test files (`tests/test_tmux_exec.py`, `tests/test_no_raw_tmux.sh`, pane/launch tests) and fix fallout.

## Verification Steps

- `ait monitor` and `ait minimonitor` both launch and render panes.
- `python -c "import monitor_core"` style import check passes from the monitor package context.
- `grep` confirms no Textual import in `monitor_core.py`.
- Existing tests pass: `tests/test_tmux_exec.py`, `tests/test_no_raw_tmux.sh`.
