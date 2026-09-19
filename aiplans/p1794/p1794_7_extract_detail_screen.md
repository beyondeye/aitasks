---
Task: t1794_7_extract_detail_screen.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_8_*.md … t1794_12_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-19 22:15
---

# p1794_7 — Extract `TaskDetailScreen` into `board_detail_screen.py` (verified)

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1 injected helpers, C2, C3, C5, "Scope decisions" PINNED).

## Context

Child 7 of t1794. Move the task editor — `TaskDetailScreen`, its field widgets
and the modals only it opens — out of the 9,545-line `aitask_board.py` into
`board/board_detail_screen.py`, with the `board.detail` shortcut scope
following it, without an import-back (C1) and without import-time task-dir
reads (C2). The board keeps behaving identically.

## Verification of the original plan (2026-09-19, HEAD `dec8a3a12`)

- **Rebase check.** Since `e2f12c499` only t1794_1…6 and t1839 (By-Trail
  focus rescue, not this region) touched `board/`. Every line anchor in the
  task file is stale (children 2–6 removed ~4,500 lines); current anchors are
  below. No foreign `Implementing` task on board code (7 Implementing tasks,
  none edits `board/`; `inflight` → `NO_INFLIGHT`). Neighbours t1521
  (AnchorField reload discards pending edits) and t583_9 are `Ready` — read,
  not pre-implemented; t1521's `aitask_board.py:4899` anchor goes stale here
  (left to t1794_9, the notes child).
- **Move set, grep-confirmed by an AST caller graph** (all top-level defs in
  the region, who references them). Three corrections to the original plan:
  1. **`CycleField` is also used by `SettingsScreen`** and
     **`CrossRepoRefPickerScreen` / `CrossRepoRefItem` also by `KanbanApp`**.
     "Anything with a board caller stays" cannot hold for them: the detail
     screen needs them and C1 forbids importing them back. They **move**, and
     the board re-imports them (board → sibling is the allowed direction).
  2. Detail-only helpers/modals the task list missed also move:
     `_remove_dep_from_task`, `_remove_verify_from_task`,
     `_reload_detail_screen`, `AnchorEditScreen`, `RemoveDepConfirmScreen`,
     `LockEmailScreen`, `UnlockConfirmScreen`, `ResetTaskConfirmScreen`.
  3. `TaskDetailScreen` also reads **`TASKS_DIR`** (`:3287`, parent-field
     branch) — a C2 violation if moved verbatim. It becomes
     `self.manager.tasks_dir` (the branch already requires `self.manager`,
     and `TaskManager.tasks_dir` exists since t1794_4) — equivalent, no fourth
     injected value.
- **Stay in the board:** `_load_task_types :269`, `_get_user_email :283`,
  `_current_tmux_session :1836` (raw-tmux allowlist site; also used by
  `KanbanApp`), `DeleteConfirmScreen :2062` (no caller at all — not touched),
  `DeleteArchiveConfirmScreen`, `OrphanParentArchiveScreen`,
  `_read_cross_repo_task_content` / `_resolve_cross_repo_task` /
  `CrossRepoTaskScreen` (KanbanApp only), `IssueTypeFilterScreen`,
  `ColumnMultiSelectScreen` (child 8), `TaskSelectScreenBase` family,
  `RenameTaskScreen` / `CommitMessageScreen` (KanbanApp).
- **`isinstance` grep** for every moved class over `.aitask-scripts` +
  `tests`: only `settings_app.py:2080,2084,3380` (`isinstance(…, CycleField)`),
  which is Settings' **own** `CycleField` (imported at `settings_app.py:124`
  from its own module) — not the board class. Test `assertIsInstance(app.screen,
  self.TaskDetailScreen)` uses the canonical class re-exported by the board,
  which is the same object. So the probe-name second identity introduces no
  new `isinstance` hazard (recorded, per "Scope decisions").

## Move set (35 names, current anchors in `aitask_board.py`)

Field widgets `:1106–2027`: `CycleField`, `ReadOnlyField`, `DependsField`,
`_remove_dep_from_task`, `VerifiesField`, `_remove_verify_from_task`,
`CrossRepoDepsField`, `_reload_detail_screen`, `ChildrenField`,
`FoldedTasksField`, `AnchorEditScreen`, `AnchorField`,
`FollowupKindPickerItem`, `FollowupKindPickerScreen`, `FollowupKindField`,
`FileReferencesField`, `FoldedIntoField`, `ParentField`, `IssueField`,
`PullRequestField`, `RemoveDepConfirmScreen` (everything in `:1106–2062`
except `_current_tmux_session :1836–1850`).
Pickers: `DepPickerItem`, `DependencyPickerScreen` (`:2264–2327`);
`CrossRepoRefItem`, `CrossRepoRefPickerScreen` (`:2398–2470`);
`ChildPickerItem` … `FileReferencePickerScreen` (`:2555–2695`).
Modals: `LockEmailScreen`, `UnlockConfirmScreen`, `ResetTaskConfirmScreen`,
`TaskDetailScreen` (`:2962–3915`).

## Implementation

1. **Build the module by script from AST line ranges** (the child-2/5
   technique): copy each block verbatim into
   `.aitask-scripts/board/board_detail_screen.py`, in source order, under a
   docstring stating the C1/C2 contract (flat imports, never `aitask_board`,
   no task-dir constants; the three providers are injected). Imports: exactly
   the names the AST scan found (Textual widgets/containers/screens, `Binding`,
   `on`/`work`, `Message`, `Text`, `escape`, `subprocess`, `datetime`,
   `ShortcutsMixin`, `followup_kinds`, `task_levels.LEVELS_ASCENDING`,
   `topic_semantics._bare_topic_id`, `agent_launch_utils.
   launch_or_focus_codebrowser`, `board_widgets` (`PickerItem`, `TaskCard`,
   `LoadingOverlay`, marker helpers), `board_task_model.Task`,
   `board_task_manager` (`TaskManager`, `_task_git_cmd`),
   `board_workflow_phase` (`derive_workflow_phase`, `phase_chip_text`,
   `_failed_active_gates`, `_gate_progress`, `_pending_procedure_gates`,
   `_resolve_plan_path_for_task`)). Lazy `section_viewer` / `webbrowser` /
   `SkipAction` imports stay lazy (they move inside their bodies verbatim).
   Verify mechanically that every unedited block is a verbatim substring of
   the new module before touching the board (catches the `\uXXXX`-escape
   rewrite child 2 hit).
2. **The only edits in moved code** (injection, C1/C2):
   - `TaskDetailScreen.__init__(self, task, manager=None, read_only=False, *,
     task_types_provider, user_email_provider, tmux_session_provider)` —
     keyword-only and **required**; stored on `self`; `_load_task_types()` →
     `self._task_types_provider()` (`:3435`), `_get_user_email()` →
     `self._user_email_provider()` (`:3753, :3799`).
   - `FileReferencesField.__init__(…, *, tmux_session_provider, **kwargs)`
     (required); `_current_tmux_session()` → `self._tmux_session_provider()`;
     the screen passes its provider at `:3373`.
   - `:3287` `self.task_data.filepath.parent != TASKS_DIR and self.manager` →
     `self.manager and self.task_data.filepath.parent != self.manager.tasks_dir`.
3. **Board side** (`aitask_board.py`): delete the moved regions with an
   asserting script (first line + following neighbour checked); add
   `import board_detail_screen` + a flat re-import of all 35 names next to the
   other `board_*` re-imports (re-export comment as in child 2); add, next to
   `make_task_manager`, the factory
   `make_task_detail_screen(task, manager=None, read_only=False)` →
   `TaskDetailScreen(task, manager, read_only=read_only,
   task_types_provider=_load_task_types, user_email_provider=_get_user_email,
   tmux_session_provider=_current_tmux_session)` — the board's single binding
   of its helpers (same precedent as t1794_4's `make_task_manager`). The one
   push site (`open_task_detail`, `:7223`) calls the factory. Remove imports
   that became dead (checked with pyflakes / the child-2 `_unresolved_globals`
   guard both ways).
4. **Manifest / scope (C5).** `lib/shortcut_scopes.py:48` board row →
   `("board",)`; new row `("board_detail_screen",
   "board/board_detail_screen.py", ("board.detail",))`. `TrailsApp.
   _shortcuts_exclude_sources` → `("aitask_board", "board_detail_screen")`:
   the trails App never pushes the detail screen, so its `?` editor keeps
   listing exactly what it listed before (no `board.detail`) and does not
   execute the detail module. Raw-tmux allowlist untouched.
   **CSS stays in `KanbanApp.CSS`** (the `#detail_*`, `CycleField`, `.meta-ro`,
   `DepPickerItem`/`ChildPickerItem { height: 1 }` rules): only the board pushes
   these screens, several rules are shared with modals that stay
   (`#btn_save:disabled`, `#dep_picker_dialog`), and the picker-item rules must
   stay after `WIDGET_CSS`'s `PickerItem` rule (`WidgetCssPinTests`).
   `CrossRepoRefPickerScreen.DEFAULT_CSS` moves with its class.
   **Dead-import rule:** an import that only moved code used is removed from
   the board **unless** a test reads it as `ab.<name>` (e.g.
   `_plan_approved_marker`, `_pr_indicator`, `_gate_progress`,
   `_failed_active_gates`, `derive_workflow_phase`) — grep decides each one.
5. **Tests** (from the source-text survey of every board test):
   - `test_board_gate_digest_budget.py:374–385`: `homes =
     {"_build_gate_fields": "aitask_board.py"}` → `"board_detail_screen.py"`.
   - `test_mark_glyphs_single_source.py:81–87, 135–145`: add
     `board/board_detail_screen.py` to `CONSUMERS` and move the `✓` waiver
     that covers `FollowupKindPickerItem` / `_build_gate_fields` to it (the
     board keeps its own waiver only if it still has a `✓` literal).
   - `test_board_fixture_harness.py:1353–1356` fresh-sibling list gains
     `board_detail_screen`.
   - construction sites `self.TaskDetailScreen(` / `ab.TaskDetailScreen(` in
     `test_board_detail_{arrow_nav,collapsible,followup_kind,gates_section}`,
     `test_board_reference_doc_literals`, `test_board_dialog_subprocess_degrade`
     → `…ab.make_task_detail_screen(`; `isinstance` / `patch.object(
     ab.TaskDetailScreen, "app")` / `__new__` uses keep the class.
   - `test_board_detail_nested_actions.py:194–212` (source scan for the single
     push inside `open_task_detail`) → scan for `make_task_detail_screen(` in
     the board and assert the class is instantiated only inside the factory.
   - **C3 repoints** (+ one in-process mutant each, the t1794_4/5 technique):
     `test_board_detail_followup_kind.py:962` `patch.object(self.ab,
     "subprocess")` and `:963, 1177, 1230` `"_reload_detail_screen"` →
     `self.ab.board_detail_screen`. The `_current_tmux_session` patches
     (`test_board_inflight_view.py:245`, `test_board_dialog_run_dispatch.py:195`)
     target KanbanApp callers and stay.
   - `tests/test_shortcut_scopes.py`: the eager test additionally asserts
     `board.detail` comes from the `board_detail_screen` probe; the exclusion
     test excludes both modules (with a control that excluding only
     `aitask_board` now still registers `board.detail`).
   - `test_board_package_contract.py`: `HeadlessImportTests` gains
     `board_detail_screen` (it must import without loading the board);
     `test_tree_is_paired` is satisfied by the bare `import board_detail_screen`
     (step 3); `ImportBackTests`, unresolved-globals and the C2
     `_BOARD_PATH_CONSTANTS` scan already cover the new file (they are the
     proof that step 2 removed every board-global read).
   - Already safe (scan all board modules via `bf.board_module_paths()`, which
     already lists `board_detail_screen`): archived-relation lookup,
     inflight-planned-lane, plan-approved-marker, trail-gather, marking,
     persistence/columns seams, scoped-task-commit, markup-colours.
   - New `tests/test_board_detail_screen.py`: re-export identity for all 35
     names (`ab.X is ab.board_detail_screen.X`); the providers are required
     keyword-only (constructing without them raises `TypeError`); the factory
     binds the board's three helpers (spy each → the screen calls it);
     `FileReferencesField` codebrowser launch uses the injected provider.
6. Docs: `board_fixture.py` inventory / `__init__.py` docstring file list if
   they enumerate modules; `aidocs/framework/tui_conventions.md` only if it
   names the detail screen's file.

## Verification

- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`
  (known pre-existing failures, if any, named).
- Targeted: `test_board_detail_*`, `test_settings_shortcuts_tab`,
  `test_shortcut_scopes`, `test_board_reference_doc_literals`,
  `test_board_package_contract`, `test_board_fixture_harness`,
  `test_board_keymap_characterization` (golden unchanged), `test_trails_app`,
  `test_board_detail_screen`.
- Bash guards: `test_no_raw_tmux.sh`, `test_shortcuts_registry_coverage.sh`,
  `test_keybinding_registry.sh`, `test_no_lib_to_tui_import.sh` (allowlists
  untouched).
- `grep -n '^class TaskDetailScreen\|^class .*Field(' .aitask-scripts/board/aitask_board.py`
  → empty.
- Manual in a private tmux server: `ait board` → `enter` on a card → cycle a
  field, open the depends picker, file-refs row, anchor edit, `?` lists
  `board.detail` keys, `esc` back; Settings (board `S`… settings screen)
  still cycles; `ait trails` → `?` shows no `board.detail`.

## Post-implementation

Task-workflow Step 9: path-scoped commits, gates, archive `t1794_7`.

## Risk

### Code-health risk: medium
- ~1,800-line mechanical move across a module boundary: a lost import or a
  global the moved code still expects on the board surfaces only at runtime in
  a rarely opened picker · severity: medium · → mitigation: none (covered in
  plan: the verbatim-substring check, the unresolved-globals / C2 / import-back
  guards over every board module, the detail-screen test files, manual smoke)
- Silent patch inertness (t1613 class): the four `patch.object(self.ab, …)`
  sites stay green while patching nothing once the lookup moves · severity:
  medium · → mitigation: none (covered in plan: C3 repoint + one mutant each)
- Shortcut-scope drift: `board.detail` stops registering, or the trails `?`
  editor starts listing/executing the detail module · severity: low ·
  → mitigation: none (covered in plan: manifest row + exclusion + the updated
  `test_shortcut_scopes` / `test_trails_app` probes)

### Goal-achievement risk: low
None identified. The move set is grep/AST-confirmed, and the three corrections
to the original plan (two shared classes move, `TASKS_DIR` via the manager,
eight extra detail-only helpers) are covered by existing guards.
