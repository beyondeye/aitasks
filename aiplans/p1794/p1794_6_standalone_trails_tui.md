---
Task: t1794_6_standalone_trails_tui.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md … t1794_5_*.md, t1794_7_*.md … t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_6 — The stand-alone `ait trails` TUI

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— Decisions (all PINNED: `ait trails`, window `trails`, key `i`,
`require_ait_python`, read-only scope, shortcut ownership under scope
`board`, `T` live for a live local member, `M`/`S` declared-but-hidden),
C1, C2, C5, C7, C8, C10.

## `board/trails_app.py`

`class TrailsApp(TuiSwitcherMixin, ShortcutsMixin, TrailScreenMixin, App)`;
`_shortcuts_scope = "board"`; `current_tui_name = "trails"`;
`BINDINGS = [*TRAIL_BINDINGS, Binding("q", "quit", "Quit"),
*TuiSwitcherMixin.SWITCHER_BINDINGS]`; `CSS` = chrome + `TRAIL_CSS`;
`__init__(*, tasks_dir, metadata_file, gates_registry_file)` — `main()`
resolves them from `config_utils.task_dir()`; `manager = TaskManager(…)`
read-only; `compose()` provides `REQUIRED_WIDGETS`; `base_filter = "bytrail"`;
`refresh_board()` re-renders lanes; `_after_dialog_command()` reloads;
`_trail_task_target()` → focused live local `TrailTaskCard`'s task id, else
`notify("T needs a live local task under focus")` + `None`;
`check_action`: `False` for `trail_move_wave`/`trail_sync`, `True` for
`trail_task` iff a card is focused; no board-only capabilities; opens the
selector on mount; own-dir `sys.path` insert; no `aitask_board` import.

## Launcher, dispatcher, registry, switcher, manifest

- `.aitask-scripts/aitask_trails.sh` = `aitask_board.sh` with
  `require_ait_python`; `ait` row after `board)` (`:206`) + `TUI:` help line.
- `lib/tui_registry.py`: `("trails", "Trails", "ait trails", True)` after
  `board`.
- `lib/tui_switcher.py`: `_TUI_SHORTCUTS["trails"] = "i"`; `Binding("i",
  "shortcut_trails", "Trails", show=False)`; `action_shortcut_trails`;
  `_HINT_ITEMS` only if the `:243–250` width one-liner still fits (record).
- `lib/shortcut_scopes.py`: `("trails_app", "board/trails_app.py", ("board",))`.
- `tests/test_shortcuts_registry_coverage.sh:31,38–40,52–85`: `board` on the
  path; `trails_app` in `TUIS`.
- `CLAUDE.md:431–435`: `trails` in the documented-TUI list.
- Read `aidocs/framework/aitasks_extension_points.md` (new helper script).

## Tests — `tests/test_trails_app.py` (fixture tree, cwd = tree)

Boot → selector; lanes; `enter` detail; `v` summary; `r`; `d` (patched drift).
`T` live member → one launch with `op_args == ["<id>"]`; `T` ghost → no launch
+ one `notify`; `T` unfocused → no launch. C10 binding identity vs the
fixture-loaded `KanbanApp`. Override propagation: fixture `shortcuts: {board:
{trail_select: x}}` rebinds in **both** Apps; negative control under a
`trails` scope changes nothing. Declared-but-hidden: `trail_move_wave` and
`trail_sync` present in `BINDINGS`, `check_action` False, absent from
`active_bindings`, spy records zero calls after `M`/`S` and after a remapped
key (`shortcuts: {board: {trail_move_wave: k}}`); `m` and `z` absent.
`TRAIL_CSS in TrailsApp.CSS`. `"aitask_board" not in sys.modules`.
Host-protocol test parametrised with `TrailsApp`. Extend:
`test_shortcut_scopes`, `test_keybinding_registry.sh`,
`test_settings_shortcuts_tab`, `test_tui_switcher_footer_fit.sh`,
`test_session_key_collision`, `test_framework_version` (busy set has
`trails`), `test_tui_switcher_agent_launch`.

## Measurement (C8)

`tests/perf/board_footprint.sh trails_app <interp>` both interpreters;
signed margins vs child-1 baseline and ceiling recorded here and in
`python_tui_performance.md`.

## Order

Rebase check → app + launcher + dispatcher (boot in tmux) → registry/switcher
four-part + manifest + coverage path + CLAUDE.md → tests → measurement →
extension-points line.

## Verification

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; the listed
  bash tests and `shellcheck .aitask-scripts/aitask_trails.sh` green;
  child-1 guards and golden unchanged.
- Manual: `ait trails` boots; `j`→`i` from the board and `j`→`b` back;
  `ait monitor` classifies the window as a TUI; no minimonitor auto-spawn;
  Settings → Shortcuts lists trail actions once under `board`.

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_6`.
