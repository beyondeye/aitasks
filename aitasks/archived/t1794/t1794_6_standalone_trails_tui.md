---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1794_5]
issue_type: refactor
status: Done
labels: [aitask_board, tui, trails, python, refactor, tui_switcher]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1794
implemented_with: claudecode/fable5_1
created_at: 2026-09-11 15:08
updated_at: 2026-09-18 12:49
completed_at: 2026-09-18 12:49
---

## Context

Child 6 of t1794 — the user-visible deliverable: the stand-alone **`ait
trails`** TUI, hosting `TrailScreenMixin` (child 5) with `TaskManager`
(child 4), `board_trail_view` (child 3) and `board_widgets` (child 2), without
importing `aitask_board` or the Kanban render paths, and registered with the
TUI switcher so it is reachable from the board (`j` → `i`) and can return
(`j` → `b`).

**Decisions (PINNED, from the parent plan — do not re-decide):** subcommand
`ait trails`, tmux window / registry name `trails`, label "Trails"; launcher
`.aitask-scripts/aitask_trails.sh` → `.aitask-scripts/board/trails_app.py`;
switcher quick-jump key `i`; interpreter `require_ait_python` (CPython —
`aidocs/framework/tui_conventions.md:23–26` forbids adding the PyPy fast path
without a per-TUI benchmark; child 11 benchmarks); **read-only scope**
(select / detail / summary / local refresh / drift / artifact watch / agent
launch); **shortcut ownership** — the trails TUI uses the board's customizable
keys: `_shortcuts_scope = "board"`, the same `TRAIL_BINDINGS` objects, no
`trails` scope; **`T` is bound and live** for the focused live local member;
`M`/`S` **stay declared but hidden and non-dispatching**.

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— "Decisions", C1, C2, C5, C7, C8, C10, child 6 section;
`aidocs/framework/tui_conventions.md` "Registering a switcher-visible TUI is
a four-part atomic change" (`:583–603`) and "New TUIs / dialogs must register
in the global shortcut manifest" (`:867–925`);
`aidocs/framework/aitasks_extension_points.md` (new helper script).

## Key files to modify

- `.aitask-scripts/board/trails_app.py` — NEW:
  `class TrailsApp(TuiSwitcherMixin, ShortcutsMixin, TrailScreenMixin, App)`;
  `_shortcuts_scope = "board"`; `current_tui_name = "trails"` in `__init__`
  (`lib/tui_switcher.py:1438–1454`); `BINDINGS = [*TRAIL_BINDINGS,
  Binding("q", "quit", "Quit"), *TuiSwitcherMixin.SWITCHER_BINDINGS]` (the
  `?` editor row comes from `ShortcutsMixin`); `CSS` = own chrome +
  `TRAIL_CSS`; `__init__(self, *, tasks_dir: Path, metadata_file: Path,
  gates_registry_file: Path)` (C2: no `task_dir()` at import; the launcher
  path resolves them from `config_utils.task_dir()` inside `main()`);
  `self.manager = TaskManager(tasks_dir=…, metadata_file=…,
  gates_registry_file=…)` used read-only; `compose()` provides the
  `REQUIRED_WIDGETS` (`HeaderTitle`, `#board_container`, `#trail_summary` /
  `#trail_summary_body`, footer); `base_filter = "bytrail"` (constant);
  `refresh_board()` = re-render lanes into `#board_container`;
  `_after_dialog_command()` = reload tasks + re-render; `_trail_task_target()`
  = focused `TrailTaskCard` with a resolved live local `trail_entry.task` and
  not `is_ghost` → its task id, else `self.notify("T needs a live local task
  under focus")` and `None`; `check_action(action, params)` → `False` for
  `trail_move_wave` and `trail_sync`, `True` for `trail_task` iff a card is
  focused, default otherwise; **no** `_review_then` /
  `_choose_move_destination` / `_column_title` / `marked` / `_reject_stale` /
  `_apply_move_to_column` / `_run_sync`. On mount: open the trail selector
  as the board does on `z` entry (`_set_base_filter :10444–10449`). Own-dir
  `sys.path` insert (C1) beside the `lib` insert; `main()` with no arguments
  (mirror `aitask_board.py`'s tail).
- `.aitask-scripts/aitask_trails.sh` — NEW; copy `aitask_board.sh` with
  `PYTHON="$(require_ait_python)"`, the same three probes (`textual`, `yaml`,
  `linkify_it`), `ait_warn_if_incapable_terminal`, `exec "$PYTHON"
  "$SCRIPT_DIR/board/trails_app.py" "$@"`. Top level ⇒ `install.sh:1066–1071`
  gives it the exec bit.
- `ait` — `trails)        shift; exec "$SCRIPTS_DIR/aitask_trails.sh" "$@" ;;`
  next to `board)` (`:206`); `TUI:` help line after `board` (`:28–39`).
- `.aitask-scripts/lib/tui_registry.py:17–30` — row
  `("trails", "Trails", "ait trails", True)` immediately after `board` (order
  by related functionality, not alphabetically — `tui_conventions.md:589–591`).
- `.aitask-scripts/lib/tui_switcher.py` — `_TUI_SHORTCUTS["trails"] = "i"`
  (`:216–227`); `Binding("i", "shortcut_trails", "Trails", show=False)` in
  `_QUICK_JUMP_BINDINGS` (`:400–416`); `def action_shortcut_trails(self):
  self._shortcut_switch("trails")` beside `action_shortcut_board` (`:1100`);
  `_HINT_ITEMS` (`:251–264`) only if the width one-liner in the comment at
  `:243–250` still fits at 120 columns — run it, record the number, and omit
  the hint if it does not.
- `.aitask-scripts/lib/shortcut_scopes.py:47–65` — row
  `("trails_app", "board/trails_app.py", ("board",))`.
- `tests/test_shortcuts_registry_coverage.sh:31, 38–40, 52–85` — add
  `.aitask-scripts/board` to `PYTHONPATH`/`sys.path` and `trails_app` to
  `TUIS`.
- `CLAUDE.md:431–435` — the documented-TUI list gains `trails`.
- `tests/test_trails_app.py` — NEW (see Verification).
- `tests/test_trail_screen_host_protocol.py` — add `TrailsApp` to the
  parametrisation.
- Switcher/registry tests to extend for the new row:
  `tests/test_shortcut_scopes.py:111–127` (board scope sweep now also loads
  `trails_app`), `tests/test_keybinding_registry.sh`,
  `tests/test_settings_shortcuts_tab.py`, `tests/test_tui_switcher_footer_fit.sh`,
  `tests/test_session_key_collision.py`, `tests/test_framework_version.py`
  (`detect_target_activity` busy set contains `trails`),
  `tests/test_tui_switcher_agent_launch.py`.
- `aidocs/framework/python_tui_performance.md` — append the `trails_app`
  footprint lines (C8) under "t1794 baseline".

## Reference files for patterns

- `.aitask-scripts/aitask_board.sh` (launcher), `.aitask-scripts/aitask_minimonitor.sh`
  (a second App carved from a bigger one; note it uses `require_ait_python`).
- `.aitask-scripts/monitor/minimonitor_app.py:26–60` — sibling-package
  composition; `codebrowser/codebrowser_app.py:1616–1630` — `main()` /
  argparse shape (the trails App takes no arguments in this child).
- `lib/tui_switcher.py:703–728` — `_spawn_in_session` sets the tmux `-n`
  window name from the registry row; `lib/agent_launch_utils.py:1699` and
  `lib/framework_version.py:185` consume `TUI_NAMES`, so the registry row is
  what makes monitor classify the window and keeps minimonitor from
  auto-spawning beside it.
- `lib/keybinding_registry.py:102–141` — `register_app_bindings` overwrites
  `_DEFAULTS[(scope, action)]` with the last registrant's default; identity of
  the `Binding` objects is what makes the second registration a no-op.
- `tests/test_board_bytrail_view.py` — Pilot idiom (`app.run_test(size=…)`),
  fixture tree with `project_config.yaml` + a trail artifact
  (`board_fixture` helpers), the patches on `ab.board_trail_screen` after
  child 5.
- `aidocs/framework/testing_conventions.md` — no `@work` worker may be in
  flight when a `run_test` block exits.

## Implementation plan

1. **Rebase check** (parent pre-phase) over `board_trail_screen.py`,
   `board_trail_view.py`, `tui_switcher.py:216–264, 400–416, 1094–1112`,
   `tui_registry.py`, `shortcut_scopes.py:47–65`, `ait:190–215`; foreign
   `Implementing` task on any → stop at the checkpoint.
2. `trails_app.py` + launcher + `ait` row + help line; boot it in tmux.
3. Registry / switcher four-part change + manifest row + coverage-script
   path; `CLAUDE.md` list.
4. `tests/test_trails_app.py` (below); extend the listed tests; run the
   host-protocol test against `TrailsApp`.
5. C8 measurement: `tests/perf/board_footprint.sh trails_app <interp>` for
   both interpreters; record signed margins vs the child-1 baseline and
   ceiling in the child plan and the aidoc.
6. Read `aidocs/framework/aitasks_extension_points.md` and add the line it
   asks for about the new helper script, if any.

## Verification steps

`tests/test_trails_app.py` (Pilot under the fixture tree, cwd = tree,
`TrailsApp(tasks_dir=Path("aitasks"), …)` — no synthetic loader needed):
- boot → selector opens; choosing the fixture trail renders lanes with
  `TrailTaskCard`s; `enter` → `TrailDetailScreen`; `v` → `TrailSummaryScreen`;
  `r` local refresh; `d` drift with `run_trail_drift` patched on
  `board_trail_screen`.
- **`T` on a focused live local member** with `resolve_dry_run_command` /
  `AgentCommandScreen` patched on `board_trail_screen` → exactly one launch
  with `op_args == ["<id>"]`; `T` on a focused ghost card → no launch and one
  `notify`; `T` with nothing focused → no launch.
- **C10 binding identity**: every `(action, key, description)` in
  `TrailsApp.BINDINGS` minus `{tui_switcher, open_shortcuts_editor}` equals
  the corresponding `KanbanApp` row (fixture-loaded board module).
- **Override propagation**: a fixture `userconfig.yaml` with
  `shortcuts: {board: {trail_select: x}}` (reset `keybinding_registry` between
  cases) makes `x` open the selector in **both** `TrailsApp` and `KanbanApp`
  under Pilot; negative control: `shortcuts: {trails: {trail_select: x}}`
  changes nothing.
- **Declared-but-hidden contract**: `trail_move_wave` and `trail_sync` are
  present in `TrailsApp.BINDINGS` (assert presence), `check_action` returns
  `False` for both, neither is in `app.screen.active_bindings`, and a spy on
  `action_trail_move_wave` / `action_trail_sync` records zero calls after
  pressing `M` / `S` **and** after pressing a remapped key from a fixture
  `shortcuts: {board: {trail_move_wave: k}}`; `m` and `z` are not declared at
  all (assert absence).
- `TRAIL_CSS in TrailsApp.CSS` (C7).
- No `aitask_board` in `sys.modules` after importing `trails_app` (assert).
Suite-level: `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`;
`bash tests/test_shortcuts_registry_coverage.sh`, `bash
tests/test_keybinding_registry.sh`, `bash tests/test_tui_switcher_footer_fit.sh`,
`bash tests/test_no_raw_tmux.sh`, `bash tests/test_no_lib_to_tui_import.sh`,
`shellcheck .aitask-scripts/aitask_trails.sh` green; child-1 guards and the
characterization golden unchanged.
Manual in tmux: `ait trails` boots; `j` → `i` from `ait board` opens/focuses
the `trails` window; `j` → `b` returns; `ait monitor` lists the window under
TUIs; no minimonitor pane appears beside it; Settings → Shortcuts shows the
trail actions once, under `board`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_3** id=2026-09-14T20:40:24Z.78431901942a339c7bc8d453 from=t1794_3 from_verified=yes at=2026-09-14T20:40:24Z base=d146a440c13afcadd3b7f72c4f338f542c8b74a0 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1794_3 (pure trail view extraction, code commit 5d518c967). Tree-relative claims below are dated by that commit; re-derive against your tree before acting. Nothing here is an instruction.
> | 
> | 1. TRAIL_CSS (.aitask-scripts/board/board_trail_view.py) carries only the trail-owned rules: `.task-info.trail-drift` and `#trail_summary`. The widget-layer rules a second App mounting trail cards needs were, at 5d518c967, only in KanbanApp.CSS: `.task-title-row`, `.task-title`, `.task-info`, `.task-number`, `.task-mark`, `.col-header-*`, `PickerItem` / `PickerItem.dep-item-focused`, `#loading_dialog` / `#loading_message` / `#loading_dialog LoadingIndicator`. The drift colour no longer depends on stylesheet order (two-class selector), so TRAIL_CSS can go anywhere in TrailsApp.CSS.
> | 2. The three trail modals lay out without the board's CSS: TrailSelectScreen gained its own DEFAULT_CSS (pinned by `ModalDefaultCssTests` in tests/test_board_trail_view.py). `LoadingOverlay` (board_widgets) has no DEFAULT_CSS yet, and the trail discovery flow pushes it.
> | 3. `TrailCssTests` asserts `TRAIL_CSS in KanbanApp.CSS` (each rule exactly once); the parent's C7 also wants the `TrailsApp.CSS` half.
> | 4. tmux smoke tips from t1794_3: focus starts in the board's search box (Escape = priority `focus_board`); the trail detail modal's first heading is `Entry <ref>` ("Trail totals:" scrolls out of view); capture after the screen settles. In a linked worktree the drift banner reads "drift unavailable: ref_outside_project" — upstream defect t1809, not an App bug.

> **✉ note:t1794_4** id=2026-09-17T08:51:11Z.e08a7057f52ee22b70ce99ac from=t1794_4 from_verified=yes at=2026-09-17T08:51:10Z base=a3e08bd1baf3be487d3d543bdccd8b2cab923b76 base_branch=main dirty=yes host=omg16
>
> | t1794_4 landed (code commit a3e08bd1b): Task/MoveResult/MergeResult -> board/board_task_model.py; derive_workflow_phase + in-flight row model -> board/board_workflow_phase.py; TaskManager, _task_git_cmd, topic-grouping build, MetadataWriteError, _DIGEST_UNSET -> board/board_task_manager.py. aitask_board.py re-exports all of them.
> | 
> | What this means for you:
> | - TaskManager now REQUIRES keyword paths: TaskManager(tasks_dir=..., metadata_file=..., gates_registry_file=..., on_warning=None). A bare TaskManager() raises TypeError. Inside the board use make_task_manager(**kw), which binds the board's own constants. A second App (TrailsApp) must pass its paths explicitly and must never import aitask_board (C1).
> | - A stub/spy of any name the MANAGER calls (save_local_config, save_project_config, project_columns_at, _build_topic_lanes, _resolve_plan_path_for_task) must target ab.board_task_manager; `datetime` for Task timestamps targets ab.board_task_model. A patch on the board's re-export is inert.
> | - Inert-patch sweeps must cover direct assignment (module.name = spy) and addCleanup(setattr, ...), not only patch.object — two such stubs were found only by the widened sweep.
> | - Source guards should scan bf.board_module_paths() / bf.board_modules_tree() (tests/lib/board_fixture.py) with per-file anti-vacuity, not aitask_board.py alone.
> | - Line numbers in your task/plan that cite aitask_board.py are stale by ~2,400 lines; re-derive against the current tree. Details: aiplans/archived/p1794/p1794_4_*.md "Notes for sibling tasks" (after archival).

> **✉ note:t1794_5** id=2026-09-17T12:43:46Z.1b1baf0a3180dabb34316b1b from=t1794_5 from_verified=yes at=2026-09-17T12:43:46Z base=13818b52ff2f3bd4db48602000d6f8c6dc65d907 base_branch=main dirty=yes host=omg16
>
> | t1794_5 landed (code commit 13818b52f): the By-Trail App half is `TrailScreenMixin` in .aitask-scripts/board/board_trail_screen.py. Tree-relative claims below are dated by that commit; re-derive before acting. Advisory only.
> | 
> | Host contract as implemented (differs from your task/plan text in places):
> | - `_after_dialog_command(refocus_filename="")` takes the refocus filename (run_dialog_command's suspend path passes it). Your plan says `_after_dialog_command()`.
> | - `_refresh_subtitle` is OWNED BY THE MIXIN (not a host member). Its non-trail fallback writes "Auto-refresh: …" from `manager.auto_refresh_minutes` / `manager.settings`; override it in TrailsApp if that text is wrong for a stand-alone app.
> | - The mixin has no __init__: call `self._init_trail_state()` from TrailsApp.__init__.
> | - TrailHost members (pinned in tests/test_trail_screen_host_protocol.py EXPECTED_MEMBERS): manager, tasks_dir, base_filter, sub_title, title, refresh_board, _focused_card, _modal_is_active, _get_focused_col_id, _queue_refocus, apply_filter, refresh_bindings, _banner_budget, _after_dialog_command, _trail_task_target, notify, push_screen, pop_screen, set_interval, call_after_refresh, query_one, query, suspend. `_banner_budget`, `_focused_card`, `_modal_is_active`, `_get_focused_col_id`, `_queue_refocus`, `apply_filter` stay in aitask_board.py, so TrailsApp needs its own.
> | - REQUIRED_WIDGETS: HeaderTitle (a Header), #trail_summary > #trail_summary_body, #board_container. MANAGER_MEMBERS: load_tasks, task_datas, child_task_datas, find_task_including_archived, auto_refresh_minutes, settings.
> | - `M`/`S` refusal: `_has_trail_capability(action)` is `hasattr` over TRAIL_ACTION_CAPABILITIES (trail_move_wave: _review_then, _choose_move_destination, _column_title, marked, _reject_stale, _apply_move_to_column; trail_sync: _run_sync). Defining none of them makes both actions return early; your check_action gate is still needed for the footer.
> | - `TRAIL_BINDINGS` (9 objects incl. `enter view_details`) and a `TRAIL_BINDING` action map are exported; the board places each object individually, and `*TRAIL_BINDINGS` works as-is for TrailsApp.
> | - Extension point: add TrailsApp to `HOSTS` in tests/test_trail_screen_host_protocol.py.
> | - Patch targets: `resolve_key` (used by action_trail_refresh_agent), `find_terminal`, `spawn_in_terminal`, `discover_trails`, `_trail_versions`, `load_trail_blob`, `run_trail_drift`, `resolve_dry_run_command`, `AgentCommandScreen`, `launch_in_tmux` are read from board_trail_screen. Details: aiplans/archived/p1794/p1794_5_*.md "Notes for sibling tasks" (after archival).

> **👁 note:read** id=2026-09-17T20:12:50Z.e0b328532a46d49810e653e4 by=t1794_6 at=2026-09-17T20:12:50Z mode=explicit ids=2026-09-14T20:40:24Z.78431901942a339c7bc8d453,2026-09-17T08:51:11Z.e08a7057f52ee22b70ce99ac,2026-09-17T12:43:46Z.1b1baf0a3180dabb34316b1b

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-18T05:12:29Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-18T09:44:47Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-18T09:49:09Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:0354145f528dedca

> **✅ gate:risk_evaluated** run=2026-09-18T09:49:09Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1794_6/risk_evaluated_2026-09-18T09:49:09Z-risk_evaluated-a1.log`
