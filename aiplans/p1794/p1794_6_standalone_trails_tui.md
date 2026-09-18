---
Task: t1794_6_standalone_trails_tui.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_10_website_docs_trails_tui.md, aitasks/t1794/t1794_11_measure_document_retrospective.md, aitasks/t1794/t1794_12_manual_verification_split_board_monofile_and_standalone_trai.md, aitasks/t1794/t1794_7_extract_detail_screen.md, aitasks/t1794/t1794_8_extract_column_dialogs.md, aitasks/t1794/t1794_9_notes_to_affected_tasks.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_1_board_package_contract_and_baseline.md, aiplans/archived/p1794/p1794_2_extract_board_widgets.md, aiplans/archived/p1794/p1794_3_extract_trail_view.md, aiplans/archived/p1794/p1794_4_extract_task_model_manager_and_workflow_phase.md, aiplans/archived/p1794/p1794_5_lift_trail_screen_mixin.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/fable5_1 @ 2026-09-18 08:10
---

# p1794_6 — The stand-alone `ait trails` TUI (verified 2026-09-17 against `2a2a79344`)

## Context

Child 6 of t1794: the user-visible deliverable. `ait trails` hosts
`TrailScreenMixin` (child 5) over `TaskManager` (child 4), `board_trail_view`
(child 3) and `board_widgets` (child 2) **without importing `aitask_board`**,
and is registered with the TUI switcher (`j`→`i` from the board, `j`→`b` back).

Parent plan decisions stay PINNED (`ait trails`, window `trails`, key `i`,
`require_ait_python`, read-only scope, `_shortcuts_scope = "board"`, the shared
`TRAIL_BINDINGS` objects, `T` live for a live local member, `M`/`S`
declared-but-hidden). This verification pass re-derived the plan against the
tree after children 3–5 landed and corrects it in the places below.

### What verification changed (premises corrected)

1. **Host contract as implemented** (`board_trail_screen.py` `TrailHost`):
   `_after_dialog_command(refocus_filename="")` takes the refocus filename; the
   mixin has no `__init__` → `TrailsApp.__init__` calls `self._init_trail_state()`;
   `_refresh_subtitle` is mixin-owned. `_banner_budget`, `_focused_card`,
   `_modal_is_active`, `_get_focused_col_id`, `_queue_refocus`, `apply_filter`
   live in `aitask_board.py`, so `TrailsApp` needs its own (small) versions.
2. **Card navigation was missing from the plan.** Arrow keys are board rows
   (`nav_up/down/left/right`, `priority=True`), not `TRAIL_BINDINGS`, and the
   trail modals' ↑/↓ also depend on the App's `action_nav_up/down` calling
   `screen.focus_previous/next`. Without them the stand-alone cannot focus a
   card, so `enter`/`T` would be unreachable. `TrailsApp` declares the same four
   rows — identical `(action, key, description)` to the board's, so the C10
   identity test still holds and `(board, nav_*)` defaults do not change.
3. **Widget hooks reached through `self.app`**: `ColumnHeader` mounts a
   `CollapseToggleButton` whose click calls `app.toggle_column_collapse` →
   `TrailsApp` gets a no-op; trail cards call `app.action_view_details`.
   `marked` must **not** be defined — it is a `trail_move_wave` capability member.
4. **Widget-layer CSS.** `TRAIL_CSS` deliberately holds only trail-owned rules;
   `.task-title*`, `.task-info`, `.task-followup-glyph`, `.col-header-*`,
   `PickerItem*`, `#loading_*` exist only in `KanbanApp.CSS`
   (`aitask_board.py` ~4742–4975) and `LoadingOverlay` has no `DEFAULT_CSS`.
   → single-source them as **`WIDGET_CSS` in `board_widgets.py`**, **prepended**
   to both Apps' `CSS` (prepend, not append: `PickerItem { height: auto }` must
   stay ahead of the equal-specificity `DepPickerItem { height: 1 }`). The rules
   are *moved* out of the `KanbanApp.CSS` literal, not copied.
5. **`HOSTS` in `tests/test_trail_screen_host_protocol.py`** constructs hosts
   with no arguments and asserts *every* capability is present. `TrailsApp`
   needs keyword paths and has *no* capabilities → the row shape becomes
   `(label, factory(ab) -> zero-arg callable, expected_capabilities: set)`.
6. **`_HINT_ITEMS`: omitted.** Measured today: the hint row renders **122**
   columns (> 120) before any addition — the comment's rule excludes a new item.
7. `aitask_trails.sh` is user-launched, never skill-invoked →
   `aitasks_extension_points.md` "Adding a new helper script" requires **zero**
   allow-list entries.
8. Rebase check done: last commits on the regions are t1794_3/4/5 (+ t1811/t1825
   in lib, unrelated rows); no foreign `Implementing` task touches
   `board/`, `tui_switcher.py`, `tui_registry.py`, `shortcut_scopes.py` or `ait`.
9. **Constructing `TaskManager` writes.** `__init__` runs `_ensure_paths()`
   (mkdir of `tasks_dir` and `metadata/`) and `load_metadata()`, whose
   first-ship branch calls `save_metadata(commit=False)` when
   `board_config.json` is absent (`board_task_manager.py:304–351`) — creating
   `board_config.json` and `board_config.local.json`. A read-only viewer must
   not do that → new keyword `persist_on_init: bool = True` on `TaskManager`
   (step 1b); the board's behaviour is unchanged.
10. **Focus does not land on a card by itself.** `HorizontalScroll` and
   `TrailColumn` (`VerticalScroll`) are focusable, so after the selector modal
   is dismissed Textual restores focus to the container; a "nothing focused"
   rescue never fires, `enter`/`T` stay gated off and arrows have no origin
   card. The rescue condition is therefore "**no `TaskCard` is focused**", and
   it runs on every base-screen resume as well as after each render (step 2).
11. Most "tests to extend" do not enumerate registry rows (grep: only
   `test_shortcut_scopes.py`, `test_framework_version.py`,
   `test_shortcuts_registry_coverage.sh` do). The rest are **run**, and edited
   only if the new row makes them fail.

## Implementation

### Pre-phase (risk mitigations)
1. [pin_board_css_before_widget_css_move] **Before moving any CSS**, add
   `WidgetCssPinTests` (in `tests/test_board_widgets.py`): boot the
   fixture-loaded `KanbanApp` under Pilot and record computed styles of
   representative widgets — `.task-title` (bold, `1fr`), `.task-info` colour,
   `.col-header-title-expanded`, `PickerItem` height `auto` vs `DepPickerItem`
   height `1`, `#loading_dialog` / `#loading_message` — as literal expectations.
   Run it green on the untouched tree, then perform step 1; it must stay green
   unchanged. Negative control: `WIDGET_CSS` appended instead of prepended flips
   the `DepPickerItem` height assertion.

### 1. `board_widgets.py` — `WIDGET_CSS`
Move the widget-layer rules listed in (4) into a module constant; in
`aitask_board.py` change `CSS = """…""" + TRAIL_CSS` to
`CSS = WIDGET_CSS + """…""" + TRAIL_CSS` and delete the moved lines (comments
travel with their rules). Update the "Deliberately NOT here" comment in
`board_trail_view.py` to point at `WIDGET_CSS`.

### 1b. `board_task_manager.py` — non-persisting initialization
`TaskManager.__init__(..., on_warning=None, persist_on_init: bool = True)`.
When `False`: skip `_ensure_paths()` and pass the flag to `load_metadata()` so
the `if not self.metadata_file.exists(): self.save_metadata(commit=False)`
first-ship is skipped (defaults stay in memory only). `load_tasks()` must
tolerate a missing `tasks_dir` (verify; guard if it does not). Default `True`
keeps `make_task_manager` / the board and every existing test byte-identical.
`TrailsApp` never calls a manager writer (`save_*`, `move_*`, `update_*`).

### 2. `.aitask-scripts/board/trails_app.py` (NEW)
- `sys.path` inserts for `../lib` and own dir (C1); imports only
  `board_widgets`, `board_trail_view`, `board_trail_screen`,
  `board_task_manager`, lib modules. `config_utils.task_dir()` is called only
  inside `main()` (C2).
- `class TrailsApp(TuiSwitcherMixin, ShortcutsMixin, TrailScreenMixin, App)`;
  `_shortcuts_scope = "board"`; `TITLE = "aitasks trails"`;
  `CSS = WIDGET_CSS + <chrome: Screen, #board_container, .trail-empty/.trail-error> + TRAIL_CSS`.
- `BINDINGS = [*SWITCHER_BINDINGS, *SHORTCUTS_MIXIN_BINDINGS, Binding("q","quit","Quit"),
  the four nav rows (board-identical), *TRAIL_BINDINGS]`.
- `__init__(*, tasks_dir, metadata_file, gates_registry_file)`:
  `current_tui_name = "trails"`, `self._tasks_dir`, `base_filter = "bytrail"`,
  `manager = TaskManager(..., on_warning=self.notify, persist_on_init=False)`, `_init_trail_state()`.
  `tasks_dir` property.
- `compose()`: non-focusable `Header`, `HorizontalScroll(id="board_container")`,
  the hidden non-focusable `#trail_summary > #trail_summary_body`
  (`markup=False`, flow child — never `dock: bottom`), `MultiRowFooter`.
- Default screen `TrailsScreen(Screen)` with `AUTO_FOCUS = ""` (board's
  `BoardScreen` idiom) whose `on_screen_resume` schedules
  `app.call_after_refresh(app.apply_filter)` — this is what re-anchors focus
  after the selector / detail / summary / agent dialog closes and Textual has
  restored focus to a scroll container. `#board_container` and the summary
  pane get `can_focus = False`.
- `on_mount`: `refresh_board()`, then `call_after_refresh(self._open_trail_select)`.
  `on_resize` → `_refresh_subtitle()`.
- Host members: `refresh_board(refocus_filename="", *a, **kw)` (clear +
  `_render_bytrail` + deferred `apply_filter` + `_queue_refocus`);
  `apply_filter(cols=None)` = **card-focus rescue**: no modal active and
  `_focused_card() is None` (a focused `HorizontalScroll`/`TrailColumn` counts
  as *no card*) → focus the first card of the first lane; never touches focus
  while a modal is up; `_focused_card` (`screen.focused` if `TaskCard`); `_modal_is_active`;
  `_get_focused_col_id`; `_queue_refocus` (by filename, else first card of the
  column); `_banner_budget` (board's body); `_after_dialog_command(refocus_filename="")`
  = `manager.load_tasks()` + `refresh_board(refocus_filename)`;
  `toggle_column_collapse` no-op; `action_view_details` → `_open_trail_entry_detail`.
- `_refresh_subtitle` override: no active trail → refresh the summary pane and
  set `sub_title = "no trail selected"` (the mixin's fallback would print the
  board's `Auto-refresh: …`); otherwise `super()`.
- `_trail_task_target()`: modal → `None` silently; focused `TrailTaskCard`,
  not `is_ghost`, parseable id → id; else
  `notify("T needs a live local task under focus")` + `None`.
- Nav actions: under a modal `focus_previous/next`; with **no focused card** any arrow focuses the first card (board's `action_focus_board` fallback); else ↑/↓ within the
  focused card's `TrailColumn`, ←/→ to the neighbouring column at the same index.
- `check_action`: `False` for `trail_move_wave`, `trail_sync`; the refresh trio
  needs `active_trail_handle` (and `R` not `_trail_launch_pending`);
  `trail_summary_expand` needs summary text; `trail_task` / `view_details` need a
  focused card; `nav_*` → `False` when the switcher overlay is up or an
  `Input`/`DataTable`/`SelectionList`/`SelectOverlay` is focused, and ←/→ whenever
  a modal is up (board's rules). Defines none of `TRAIL_ACTION_CAPABILITIES`.
- `main()` (no args): resolve the three paths from `task_dir()`, run.

### 3. Launcher, dispatcher
`.aitask-scripts/aitask_trails.sh` = `aitask_board.sh` with
`require_ait_python` (exec bit set); `ait`: `trails)` row after `board)` + `TUI:`
help line. Check `tests/test_terminal_compat.sh:232` launcher list.

### 4. Registry / switcher four-part change + manifest
`tui_registry.py` row after `board`; `tui_switcher.py`: `_TUI_SHORTCUTS["trails"]="i"`,
`Binding("i","shortcut_trails","Trails",show=False)`, `action_shortcut_trails`,
and the `_HINT_ITEMS` comment updated with the measured 122 (no item added);
`shortcut_scopes.py` row `("trails_app","board/trails_app.py",("board",))`;
`tests/test_shortcuts_registry_coverage.sh` path + `TUIS`; `CLAUDE.md`
documented-TUI list gains `trails`.

### 5. Tests
- `tests/test_trails_app.py` (NEW, fixture tree, cwd = tree, trail seeded by
  patching `discover_trails` on `board_trail_screen` with `TrailInfo`s as
  `test_board_bytrail_view.py` does; no `@work` worker left in flight —
  `block_app_worker_starts` / await workers): boot → selector; lanes; arrow nav
  moves focus; `enter` detail — **all driven by key presses only: no test-side
  `card.focus()`** (a helper asserts `isinstance(app.screen.focused, TaskCard)`
  right after the selector is dismissed with `enter`, and again after the detail
  and summary modals close). **Predicate discrimination test** (its own precondition, independent of
  the startup path): after a trail is active, explicitly `focus()` a
  `TrailColumn` (a `VerticalScroll`, still focusable) and assert
  `isinstance(app.screen.focused, TrailColumn)`; then call `apply_filter()`
  directly. Correct predicate → focus moves to a `TaskCard`; negative control
  = the same call with the predicate patched to the original "`screen.focused
  is None`" → the `TrailColumn` stays focused. Does not assume any
  container-focus precondition survives the startup fixes (auto-focus off,
  `#board_container` non-focusable) — it creates the precondition itself.
  **Resume-hook scenario** (positive): open the summary modal,
  replace the lanes underneath it via `refresh_board()` (the shape of a
  drift/reload callback landing while a dialog is up), dismiss with `escape`,
  assert a card is focused without any key press; control: with the hook
  stubbed out **and** the post-render rescue bypassed for that render, no
  `TaskCard` is focused (whatever Textual left focused — a column or nothing);
  **read-only boot**: a fixture tree with `board_config.json` and
  `board_config.local.json` removed boots `TrailsApp`, selects a trail, and both
  files are still absent and `snapshot(tree)` is unchanged; control: a default
  `TaskManager(...)` on the same tree does create them; `v` summary; `r`; `d` (patched `run_trail_drift`);
  `T` live → one launch `op_args == ["<id>"]`, ghost → no launch + one notify,
  unfocused → no launch; C10 identity vs fixture-loaded `KanbanApp`; override
  propagation (`board` scope rebinds both Apps; `trails` scope is inert;
  registry reset between cases); declared-but-hidden `M`/`S` (present,
  `check_action` False, absent from `active_bindings`, spies record zero calls
  for default and remapped key); `m`/`z` absent; `TRAIL_CSS` and `WIDGET_CSS` in
  both Apps' CSS, each `WIDGET_CSS` rule exactly once in `KanbanApp.CSS`;
  subprocess probe: `import trails_app` leaves `aitask_board` out of `sys.modules`.
- `test_trail_screen_host_protocol.py`: new `HOSTS` shape + `TrailsApp` row with
  `expected_capabilities = set()`; negative control that a host wrongly claiming
  a capability is reported.
- Extend `test_shortcut_scopes.py`, `test_framework_version.py` (busy set has
  `trails`), coverage script; run the remaining listed tests.

### 6. Measurement (C8) and docs
`tests/perf/board_footprint.sh trails_app <interp>` for CPython and PyPy;
signed margins vs the child-1 baseline/ceiling recorded in this plan's Final
Implementation Notes and under "t1794 baseline" in
`aidocs/framework/python_tui_performance.md`.

### Post-phase (risk mitigations)
1. [mixin_self_attribute_sweep] Add an AST test (host-protocol test file): collect
   every `self.<name>` **read** in `TrailScreenMixin` that the mixin does not
   itself define/assign; assert each is answered by `TrailsApp` (class or
   instance after `__init__`) **or** is listed in `TRAIL_ACTION_CAPABILITIES`
   and only read behind `_has_trail_capability`. Anti-vacuity: the computed set
   contains `manager`, `_banner_budget`, `_trail_task_target`. Negative control:
   an injected `self._unlisted_thing` read in a source copy is reported.

## Verification
- `set -o pipefail; bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`.
- `bash tests/test_shortcuts_registry_coverage.sh`, `test_keybinding_registry.sh`,
  `test_tui_switcher_footer_fit.sh`, `test_no_raw_tmux.sh`,
  `test_no_lib_to_tui_import.sh`, `test_terminal_compat.sh`;
  `shellcheck .aitask-scripts/aitask_trails.sh`;
  child-1 guards + the keymap characterization golden **unchanged**.
- tmux smoke: `./ait trails` boots, selector opens, lanes + arrows + `enter` work;
  board `j`→`i` opens the `trails` window, `j`→`b` returns. (Full manual list
  belongs to sibling t1794_12.)

## Post-implementation
Task-workflow Step 9: path-scoped commit (`refactor: … (t1794_6)`), gates,
archive `t1794_6`; Final Implementation Notes incl. "Notes for sibling tasks"
(t1794_10 docs, t1794_11 measurements, t1794_12 manual checks).

## Risk

### Code-health risk: medium
- Moving widget CSS out of the `KanbanApp.CSS` literal into a prepended `WIDGET_CSS` could change board styling through rule order · severity: medium · → mitigation: inline pre-phase pin_board_css_before_widget_css_move
- `TrailsApp` re-implements small host members (nav, focus, refocus, banner budget) that also exist in the board; the two can drift · severity: low · → mitigation: inline post-phase mixin_self_attribute_sweep
- A new registry row / quick-jump key `i` touches every TUI's switcher · severity: low · → mitigation: none (covered by the four-part-change tests)
- `TaskManager` gains a `persist_on_init` keyword on a load-bearing constructor; default `True` keeps every existing caller unchanged · severity: low · → mitigation: none (read-only-boot test plus its default-path control)

### Goal-achievement risk: medium
- The mixin was only ever exercised inside `KanbanApp`; an unlisted `self.`/`self.app.` dependency may surface only at runtime in the stand-alone host · severity: medium · → mitigation: inline post-phase mixin_self_attribute_sweep

Levels re-assessed after inlining both mitigations: unchanged (medium / medium)
— the pin bounds the CSS move and the sweep bounds static host drift, but
runtime-only behaviour in the new host still rests on the Pilot tests.

### Planned mitigations
- timing: pre-phase | name: pin_board_css_before_widget_css_move | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: board styling change through CSS rule order | desc: pin computed styles of representative board widgets before moving widget CSS into WIDGET_CSS
- timing: post-phase | name: mixin_self_attribute_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: unlisted mixin host dependencies and host-member drift | desc: AST sweep asserting every self-read of TrailScreenMixin is answered by TrailsApp or capability-guarded
