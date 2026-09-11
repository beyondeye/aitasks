---
priority: medium
effort: high
depends: [t1794_4]
issue_type: refactor
status: Ready
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 5 of t1794. Lift the App half of the By-Trail view — the 34
trail-named `KanbanApp` methods, their state, the launch helper, the trail
branch of `action_view_details` and the trail `Binding` rows — into
`board_trail_screen.py` as `TrailScreenMixin` behind an explicit `TrailHost`
protocol, so that a second App (child 6) can host the same screen. `KanbanApp`
mixes it in; the board's key map, `check_action`, view switching and the
board-only capabilities (move-to-column, sync) stay in the board, and the
child-1 characterization test must remain green **unchanged** — that is the
proof this child changed nothing observable in `ait board`.

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— C1, C3, C10 (TRAIL_BINDINGS and the `T` policy seam), "Scope decisions"
(`run_dialog_command`), child 5 section. Anchors at `e2f12c499` (unchanged at
`c78deab36`).

## Key files to modify

- `.aitask-scripts/board/board_trail_screen.py` — NEW:
  - `TrailHost(typing.Protocol)`: `manager` (with `load_tasks`, `task_datas`,
    `child_task_datas`, `find_task_including_archived`,
    `auto_refresh_minutes`, `settings` — the last two are read by
    `_refresh_subtitle :9568–9573` whenever `active_trail_handle` is empty),
    `tasks_dir`, `refresh_board`, `_refresh_subtitle`, `_focused_card`,
    `_modal_is_active`, `_get_focused_col_id`, `_queue_refocus`,
    `apply_filter`, `refresh_bindings`, `_banner_budget`, `notify`,
    `push_screen`, `pop_screen`, `set_interval`, `call_after_refresh`,
    `call_from_thread`, `sub_title`, `base_filter`, `_after_dialog_command`,
    `_trail_task_target`; class constant `REQUIRED_WIDGETS` = `HeaderTitle`
    (`_banner_budget :9423`), `#trail_summary`, `#trail_summary_body`
    (`:9509–9510`), `#board_container` (`:9614`), `LoadingOverlay`
    (`:11803`), a mountable `TrailColumn` target (`:11778`); a documented
    **optional** capability set (`_review_then`, `_choose_move_destination`,
    `_column_title`, `marked`, `_reject_stale`, `_apply_move_to_column`,
    `_run_sync`) probed by `_has_trail_capability(name)`.
  - `TRAIL_BINDINGS` (C10): the `Binding` rows for `trail_select s`,
    `trail_refresh_local r`, `trail_refresh_drift d`, `trail_refresh_agent R`,
    `trail_sync S`, `trail_summary_expand v`, `trail_task T`,
    `trail_move_wave M`, `view_details enter` — moved verbatim from
    `aitask_board.py:8832–8841, 8854, 8881` (and the existing `view_details`
    row); `KanbanApp.BINDINGS` splices `*TRAIL_BINDINGS` **at the same
    positions** so the characterization golden is unchanged (order matters to
    Textual's footer).
  - `TrailScreenMixin`: `_init_trail_state()` (the attrs from `:8934–8964`),
    `_get_local_project` (`:11733–11737`), the 34 methods (`:9429–9702`,
    `:10342`, `:11060–11136`, `:11739–12199` — list in the parent plan),
    `_open_trail_entry_detail(card)` = the trail branch of
    `action_view_details` (`:11293–11300`), `run_dialog_command`
    (`:12551–12581`) calling `self._after_dialog_command()`, and
    `action_trail_task` reduced to `target = self._trail_task_target(); if
    target is None: return; self._launch_trail([target], target)`.
    `action_trail_move_wave` / `action_trail_sync` guard on
    `_has_trail_capability` first (a remapped key must not reach a host that
    lacks the capability — C10 / Decisions).
- `.aitask-scripts/board/aitask_board.py` — `class KanbanApp(TuiSwitcherMixin,
  ShortcutsMixin, TrailScreenMixin, App)`; `__init__` calls
  `self._init_trail_state()`; `_trail_task_target` = today's
  `action_trail_task` body verbatim (`:12042–12066`, returning the target or
  `None`); `_after_dialog_command` = `self.manager.load_tasks();
  self.refresh_board()`; `action_view_details` calls
  `self._open_trail_entry_detail(focused)` for trail cards then continues to
  the task editor; `tasks_dir` property returning `TASKS_DIR`. **Stays:** the
  non-trail `BINDINGS`, `z` (`:8899`), `check_action` (`:8982–9280` incl.
  `trail_task :9264–9271`), `_set_base_filter` (`:10444–10449`),
  `refresh_board` bytrail branch (`:9750–9764`), `apply_filter` (`:10096`),
  `action_move_to_column` / `_apply_move_to_column` (`:11011`, `:11160`),
  `_run_sync` (`:12342`), `ViewSelector`.
- `tests/test_trail_screen_host_protocol.py` — NEW: every `TrailHost` member
  and `REQUIRED_WIDGETS` entry is present on the fixture-loaded `KanbanApp`
  (attribute/`query_one` check under Pilot); negative control: a stub class
  missing one member fails the same checker. Parametrised so child 6 adds
  `TrailsApp`.
- `tests/test_board_bytrail_view.py` — C3 repoints: `discover_trails`,
  `_trail_versions`, `run_trail_drift`, `load_trail_blob`,
  `resolve_dry_run_command`, `resolve_agent_string`, `AgentCommandScreen`,
  `launch_in_tmux`, `maybe_spawn_minimonitor`, `TmuxLaunchConfig` — their
  callers (`_trail_discovery_worker :11812`, `_trail_baseline_worker :12167`,
  `_start_trail_drift`, `_launch_trail :12083+`) now live in
  `board_trail_screen`, so `patch.object(ab, "<name>")` becomes
  `patch.object(ab.board_trail_screen, "<name>")`; the three
  `ab.trail_discovery` patches are unchanged; the `patch.object(app, …)`
  instance patches are unchanged.
- `tests/test_board_package_contract.py` — bare-import pairing gains
  `board_trail_screen`.

## Reference files for patterns

- `lib/tui_switcher.py:1438–1454` — `TuiSwitcherMixin`, a mixin an App
  composes with class-level bindings (`SWITCHER_BINDINGS`); the shape to
  mirror for `TRAIL_BINDINGS`.
- `lib/shortcuts_mixin.py:76–134` — how `BINDINGS` are registered and
  relinked; the splice must happen at class-definition time.
- `aitask_board.py:53–66` — import pairing.
- `tests/test_board_bytrail_view.py:1330–1360` `BindingContractTests` —
  per-view footer labels via duplicate-key bindings; must stay green.
- `tests/test_board_keymap_characterization.py` (child 1) — the golden.

## Implementation plan

1. **Rebase check** (parent pre-phase) over `:8796–8964`, `:8982–9280`,
   `:9429–9702`, `:10342`, `:10444–10449`, `:11011`, `:11060–11177`,
   `:11289–11302`, `:11733–12199`, `:12342`, `:12551–12581` and
   `tests/test_board_bytrail_view.py`. **t1647_5** (board command inside the
   By-Trail view) and **t1296** (`R` vs `w` key collision) are the known
   pending neighbours; if either landed, its methods are part of the App half
   and move with it — name the corrected premise in the child plan.
2. Write `board_trail_screen.py` (protocol, constants, mixin) — imports from
   `board_trail_view`, `board_widgets`, `trail_discovery`, `lib/` modules
   (`agent_command_screen`, `agent_launch_utils`, `keybinding_registry.resolve_key`,
   `config_utils`); none of the C2 names; no `aitask_board` import.
3. Edit `KanbanApp`: base classes, `__init__`, the splice, the policy/hook
   methods, delete the moved methods.
4. Host-protocol test; C3 repoints with a recorded mutant each (e.g. make
   `_trail_drift_worker` skip `run_trail_drift` → the drift tests go red).
5. Run the characterization golden **unchanged**; if it needs a change, the
   splice position or a binding is wrong — fix the code, not the golden.

## Verification steps

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `python -m pytest tests/test_board_bytrail_view.py
  tests/test_trail_screen_host_protocol.py tests/test_board_keymap_characterization.py
  tests/test_board_package_contract.py tests/test_board_fixture_harness.py
  tests/test_shortcut_scopes.py -q` green; `bash
  tests/test_shortcuts_registry_coverage.sh`, `bash tests/test_no_raw_tmux.sh`
  green (the three raw-tmux sites stay in `aitask_board.py`).
- `grep -c 'def .*trail' .aitask-scripts/board/aitask_board.py` shows only
  `_trail_task_target`, `action_view_bytrail`-free board leftovers listed in
  "Stays" (record the exact residual list in the plan).
- Manual in tmux: `ait board` → `z` → `s`/`r`/`d`/`R`/`v`/`enter`/`M`/`S`/`T`
  behave as before (`T` hidden in By-Trail; `T` on a card in the normal view
  launches the dialog).
