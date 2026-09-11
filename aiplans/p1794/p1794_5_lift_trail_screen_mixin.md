---
Task: t1794_5_lift_trail_screen_mixin.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md … t1794_4_*.md, t1794_6_*.md … t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_5 — Lift the App half of By-Trail into `TrailScreenMixin`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1, C3, C10 PINNED; "Scope decisions" for `run_dialog_command`).

## `board_trail_screen.py` contents

- `TrailHost(Protocol)`: `manager` (`load_tasks`, `task_datas`,
  `child_task_datas`, `find_task_including_archived`, `auto_refresh_minutes`,
  `settings`), `tasks_dir`, `refresh_board`, `_refresh_subtitle`,
  `_focused_card`, `_modal_is_active`, `_get_focused_col_id`, `_queue_refocus`,
  `apply_filter`, `refresh_bindings`, `_banner_budget`, `notify`,
  `push_screen`, `pop_screen`, `set_interval`, `call_after_refresh`,
  `call_from_thread`, `sub_title`, `base_filter`, `_after_dialog_command`,
  `_trail_task_target`; `REQUIRED_WIDGETS` = `HeaderTitle`, `#trail_summary`,
  `#trail_summary_body`, `#board_container`, `LoadingOverlay`, `TrailColumn`
  mount target; optional capabilities (`_review_then`,
  `_choose_move_destination`, `_column_title`, `marked`, `_reject_stale`,
  `_apply_move_to_column`, `_run_sync`) probed by `_has_trail_capability`.
- `TRAIL_BINDINGS`: the rows from `:8832–8841, 8854, 8881` + `view_details`
  (`enter`), moved verbatim; `KanbanApp.BINDINGS` splices them **at the same
  positions**.
- `TrailScreenMixin`: `_init_trail_state()` (`:8934–8964`),
  `_get_local_project`, the 34 trail methods (`:9429–9702, :10342,
  :11060–11136, :11739–12199`), `_open_trail_entry_detail(card)`
  (`:11293–11300`), `run_dialog_command` (`:12551–12581`) →
  `self._after_dialog_command()`, `action_trail_task` = policy seam
  (`target = self._trail_task_target()`), `action_trail_move_wave` /
  `action_trail_sync` guarded by `_has_trail_capability` first.

## Stays in `KanbanApp`

Non-trail `BINDINGS` + `z :8899`; `check_action :8982–9280` (incl.
`trail_task :9264–9271`); `_set_base_filter :10444–10449`; `refresh_board`
bytrail branch `:9750–9764`; `apply_filter :10096`; `action_move_to_column
:11011` / `_apply_move_to_column :11160`; `_run_sync :12342`; `ViewSelector`.
New in the board: `_trail_task_target` = today's `action_trail_task` body
verbatim (`:12042–12066`); `_after_dialog_command` = `load_tasks` +
`refresh_board`; `tasks_dir` property; `action_view_details` calls
`_open_trail_entry_detail` for trail cards; base class order
`(TuiSwitcherMixin, ShortcutsMixin, TrailScreenMixin, App)`.

## Tests

- `tests/test_trail_screen_host_protocol.py` (parametrised over hosts;
  `KanbanApp` now, `TrailsApp` in child 6): every member + widget present;
  negative control stub fails.
- C3 repoints in `tests/test_board_bytrail_view.py`: `discover_trails`,
  `_trail_versions`, `run_trail_drift`, `load_trail_blob`,
  `resolve_dry_run_command`, `resolve_agent_string`, `AgentCommandScreen`,
  `launch_in_tmux`, `maybe_spawn_minimonitor`, `TmuxLaunchConfig` →
  `ab.board_trail_screen`; mutant per repoint; `ab.trail_discovery` and
  instance patches unchanged.
- Characterization golden (child 1) green **unchanged** — fix code, never
  the golden.

## Order

Rebase check (t1647_5, t1296 neighbours) → module → `KanbanApp` edits →
host-protocol test → repoints + mutants → golden → suite.

## Verification

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`;
  `test_board_bytrail_view`, `test_trail_screen_host_protocol`,
  `test_board_keymap_characterization`, `test_board_package_contract`,
  `test_board_fixture_harness`, `test_shortcut_scopes` green;
  `bash tests/test_shortcuts_registry_coverage.sh`, `bash tests/test_no_raw_tmux.sh`
  green.
- Residual `def *trail*` list in `aitask_board.py` recorded here.
- Manual: `ait board` → `z` → `s r d R v enter M S` as before; `T` hidden in
  By-Trail, live on a card in the normal view.

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_5`.
