---
priority: medium
effort: high
depends: [t713_3]
issue_type: feature
status: Implementing
labels: [tui, scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-29 09:48
updated_at: 2026-04-30 15:08
---

## Context

Parent t713 requires the syncer to be visible from the existing tmux/TUI surfaces. This child integrates the syncer with TUI registration, `ait ide` autostart, the switcher modal, and monitor/minimonitor summary lines.

The syncer must follow the single-session-per-project model and exact tmux target conventions from `CLAUDE.md`.

## Key Files to Modify

- `.aitask-scripts/lib/tui_registry.py`: register `syncer` as a switcher-visible TUI.
- `.aitask-scripts/lib/tui_switcher.py`: add shortcut key `y`, hint text, and desync info line.
- `.aitask-scripts/aitask_ide.sh`: launch/focus singleton `syncer` when `tmux.syncer.autostart` is true.
- `.aitask-scripts/monitor/monitor_app.py`: show compact desync summary.
- `.aitask-scripts/monitor/minimonitor_app.py`: show compact desync summary.
- `.aitask-scripts/lib/agent_launch_utils.py`: extend config/default loading only if needed for `syncer.autostart`.

## Reference Files for Patterns

- `.aitask-scripts/lib/tui_registry.py`: central TUI registration.
- `.aitask-scripts/lib/tui_switcher.py`: existing shortcuts for `b`, `m`, `c`, `s`, `t`, `g`, `x`, and reserved `n` create-task shortcut.
- `CLAUDE.md` TUI conventions: `n` is reserved for create-task; shortcuts act on the selected session; tmux targets must use exact session matching.
- `.aitask-scripts/aitask_ide.sh`: current monitor singleton startup and project registry setup.
- `.aitask-scripts/monitor/monitor_app.py` `_rebuild_session_bar`: full monitor summary line placement.
- `.aitask-scripts/monitor/minimonitor_app.py` `_rebuild_session_bar`: compact summary placement.

## Implementation Plan

1. Add `syncer` to `TUI_REGISTRY` with label `Syncer` and command `ait syncer`.
2. Add switcher shortcut `y` for syncer:
   - Do not use `n`.
   - Update bindings, shortcut map, and footer hint text.
   - Preserve shortcut-on-selected-session semantics.
3. Add a desync info line in the switcher modal:
   - Use the selected session’s project root.
   - Display concise state such as `main: 1 behind · aitask-data: 3 behind`.
   - Handle helper errors with a muted unavailable line.
4. Add `tmux.syncer.autostart: false` support to `ait ide`:
   - If enabled, ensure a singleton `syncer` window exists in the project session.
   - Launch with exact tmux session target and project cwd.
   - Keep monitor startup behavior unchanged.
5. Add monitor/minimonitor desync summaries:
   - Reuse `desync_state.py snapshot --json` without fetch on every refresh tick.
   - Keep the line compact and non-blocking; cache or throttle if needed.
   - Scope multi-session summaries to each session’s project root.

## Verification Steps

- Run `python3 -m pytest tests/test_git_tui_config.py` after extending registry expectations.
- Add or update tests covering `syncer` membership in TUI registry and switcher-visible entries.
- Manually verify `j` switcher shows `y` and launches/focuses syncer.
- Manually verify `ait ide` starts syncer when `tmux.syncer.autostart: true`.
- Manually verify monitor and minimonitor render compact desync summaries without blocking refresh.
