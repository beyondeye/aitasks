---
priority: medium
effort: high
depends: [t1794_5]
issue_type: refactor
status: Ready
labels: [aitask_board, tui, trails, python, refactor, tui_switcher]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
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
