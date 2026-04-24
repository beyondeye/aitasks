---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [tmux, aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-24 10:21
updated_at: 2026-04-24 17:38
---

## Context

t634_2 added multi-session awareness to the main monitor (`TmuxMonitor.multi_session` attribute, `M` runtime toggle, session tag prefix on every agent row, cross-session focus via `switch_to_pane_anywhere`). The per-window minimonitor companion at `.aitask-scripts/monitor/minimonitor_app.py` is still session-local and loses that cross-session view.

This task teaches the minimonitor the same multi-session behavior so both TUIs show the same "all active code agents on the box" view.

## Core requirement (matches t634_2)

When multi_session is active, the minimonitor MUST show every active code agent across every aitasks session **in a single unified list** — not a counter, not an "expand to view" affordance, not a per-session sub-section. Same at-a-glance invariant as the main monitor; the minimonitor is just the more compact, per-window incarnation of the same view.

Session tag prefix on each row distinguishes which project each agent belongs to (use the `_build_session_tags` helper added to `MonitorApp` in t634_2 — extract to `monitor_shared.py` if both TUIs need it).

## Required `M` keyboard shortcut

Mirror the main-monitor `M` binding:

- Textual `Binding("M", "toggle_multi_session", "Multi")` in the minimonitor app's `BINDINGS`.
- Action flips `self._monitor.multi_session`, invalidates `self._monitor._sessions_cache`, calls `self.notify("Multi-session ON"/"OFF")`, schedules a refresh.
- In-memory only; no config write (per CLAUDE.md TUI auto-commit restriction).

No config key (matches t634_2); the `MonitorApp`-equivalent default in minimonitor is `multi_session=True`.

## Key files

- `.aitask-scripts/monitor/minimonitor_app.py` — route discovery through the same multi-session `TmuxMonitor` path added in t634_2; format rows with the session tag prefix; register the `M` binding and toggle action.
- Possibly `.aitask-scripts/monitor/monitor_shared.py` — promote `_build_session_tags()` from `MonitorApp` to a shared helper if both TUIs use it.
- `tests/test_multi_session_monitor.sh` or a new test file — cover the minimonitor-specific paths (at minimum: the M binding + toggle action behavior).

## Reference patterns

- `.aitask-scripts/monitor/monitor_app.py:action_toggle_multi_session` — exact shape of the toggle action to mirror.
- `.aitask-scripts/monitor/monitor_app.py:_rebuild_pane_list` — single-list rendering with tag prefix.
- t634_2's plan file at `aiplans/archived/p634/p634_2_*.md` (once archived) documents every hook and its rationale.

## Open implementation question (decide during planning)

Does pressing `M` in minimonitor → switching to the main monitor implicitly enable `multi_session` on the main monitor instance if currently off, or only switch focus? **Recommend:** only switch focus. The main-monitor toggle is its own action; the user can flip it there separately. This keeps the two TUI states independent and avoids surprising state changes on navigation.

## Dependency

Blocked on t634_2 (needs `TmuxPaneInfo.session_name`, the cached `discover_aitasks_sessions()` accessor, and the `TmuxMonitor.multi_session` attribute).

## Verification

- Automated: new test(s) mirroring the Tier 1 mocks from t634_2 covering the minimonitor-specific action and binding.
- Manual: run `ait minimonitor` with two aitasks sessions active → see agents from both; `M` toggles; handoff to main monitor still works.

## Post-implementation

Standard workflow: Step 8 commit (`feature: Add multi-session support to minimonitor (t634_4)`), Step 9 archive.
