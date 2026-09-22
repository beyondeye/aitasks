---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [bug, tui]
gates: [risk_evaluated]
anchor: 1210
followup_kind: upstream_defect
created_at: 2026-07-28 15:24
updated_at: 2026-08-13 23:06
boardidx: 67584
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:18Z.fc11b7cb2a2daa33bf804bfd from=t1794_9 from_verified=yes at=2026-09-22T06:08:18Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1296_agent_command_dialog_key_collisions.md) cites stale line anchors: aitask_board.py:7159, aitask_board.py:7261, aitask_board.py:8064.
> | 
> | Specific to t1296: the By-Trail `R` agent-refresh binding is now a row in TRAIL_BINDINGS (board_trail_screen.py), shared by object identity between KanbanApp.BINDINGS and the new stand-alone `ait trails` TrailsApp.BINDINGS, under override scope `board`. A key change there changes both TUIs; a collision fix must be checked in `ait trails` too.
