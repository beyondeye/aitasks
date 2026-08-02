---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [bug, tui]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-07-28 15:24
updated_at: 2026-07-28 15:24
boardidx: 430
---

## Origin

Spawned from t1279 during Step 8b review. t1279 fixed one instance of this
defect (the board's By-Trail `R` agent refresh) and deliberately scoped the
rest out; the mechanism it shipped is reusable here.

## Upstream defect

`AgentCommandScreen` (`.aitask-scripts/lib/agent_command_screen.py`) binds
`c/C p/P r/R d/D e/E` and additionally handles `a/A u/U e/E` plus the tmux
keys `t s n w m` in its `on_key` (`:1104`). Because it is a `ModalScreen`,
those bindings win over the host App's, so **any host that opens the dialog
with a key the dialog itself claims will have a repeat press consumed by the
dialog rather than reaching the host guard**. Remaining sites:

- `.aitask-scripts/codebrowser/codebrowser_app.py:1397` — `e`
  (`action_launch_agent`) opens the dialog, which also handles `e`/`E`; a
  double-tap opens the profile editor over the dialog.
- `.aitask-scripts/monitor/monitor_app.py:1935` — `R` (`action_restart_task`
  → `_on_restart_confirmed`) reaches the dialog, which binds `R -> run`. Same
  launch-without-review class as t1279; an intervening `RestartDialog`
  absorbs one press, which mitigates but does not remove it.
- `.aitask-scripts/monitor/minimonitor_app.py:1135` — `E`
  (`action_launch_shadow_pick`) vs the dialog's `e`/`E`.
- `.aitask-scripts/codebrowser/history_screen.py:428` — `a`
  (`action_launch_qa`) vs the dialog's `a`/`A`; a double-tap opens the
  agent/model picker.
- `.aitask-scripts/syncer/syncer_app.py:2335` — `a` →
  `_launch_resolution_agent` vs the dialog's `a`/`A` (behind
  `SyncFailureScreen`).
- `.aitask-scripts/lib/tui_switcher.py:1260` — `e`
  (`action_shortcut_agent`) vs the dialog's `e`/`E`.
- `.aitask-scripts/board/aitask_board.py:8064` and
  `.aitask-scripts/codebrowser/codebrowser_app.py:1471` — `n` (create task)
  vs the dialog's `on_key` `n`, which focuses `#tmux_new_session_input`; the
  repeat then types into that field.
- `.aitask-scripts/board/aitask_board.py:7159` (and `:6987` via the detail
  screen) — `p` (`action_pick_task`) vs `p`/`P` → copy-prompt: a spurious
  clipboard write plus a notification.
- `.aitask-scripts/board/aitask_board.py:7261` — `w` (work report) vs the
  dialog's `on_key` `w`, which focuses `#tmux_window_select`.

Severity varies: `R` (monitor) is launch-without-review like the original;
`e`/`E` and `a`/`A` open a nested modal; `n`/`w`/`p` are focus-steal and
spurious-copy nuisances.

## Diagnostic context

From t1279's plan (`aiplans/archived/p1279_*.md`) — verified against Textual
8.2.7:

- A screen-level `on_key` runs strictly **before** binding dispatch: the key
  bubbles focused-widget → screen → App, and only `App._on_key`
  (`app.py:4341`) calls `_check_bindings`. `prevent_default()` sets
  `_no_default_action`, which makes `_get_dispatch_methods` skip that private
  handler.
- `Screen._modal_binding_chain` (`screen.py:449`) truncates at the modal, so
  a suppressed key does not fall through to the host App's binding — the
  hosts' own `_modal_is_active()` guards are never consulted.
- A guard must sit **above** the `isinstance(focused, (Input, Select,
  SelectOverlay))` early-return: a collapsed `Select` defines neither
  `_on_key` nor `check_consume_key`, so with the tmux Select focused the key
  bubbles on and fires the binding anyway.
- Keys are user-remappable, so the opening key must be resolved via
  `resolve_key(scope, action, default)` and normalised with
  `_character_to_key` (`resolve_key` returns `#`, `event.key` is
  `number_sign`).

## Suggested fix

The mechanism already exists and is opt-in per host: pass
`debounce_key=<resolved opening key>` to `AgentCommandScreen`, exactly as
`aitask_board.py`'s `action_trail_refresh_agent` → `_launch_trail` does.
Each site needs one keyword (and, where a builder serves several openers —
`_launch_brainstorm`, `_launch_work_report`, `_launch_resolution_agent` — one
extra parameter threaded through). Note two resolution traps recorded in
t1279: `action_gate_resume` has no binding of its own (it is reached from
`action_view_git`, key `g`), and `HistoryScreen` / `TuiSwitcherOverlay` have
no `_shortcuts_scope`, so they pass a literal instead of calling
`resolve_key`.

Worth deciding as part of this task: whether the per-site opt-in should
become a required argument (with a structural test asserting every
`AgentCommandScreen(...)` construction passes it) so a future push site
cannot silently regress. That whole-surface option was considered and
deliberately deferred in t1279.
