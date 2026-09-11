---
Task: t1794_7_extract_detail_screen.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md … t1794_6_*.md, t1794_8_*.md … t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_7 — Extract `TaskDetailScreen` into `board_detail_screen.py`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1 injected helpers, C3, C5, "Scope decisions" PINNED).

## Move set (grep-confirm each has only detail-screen callers)

`TaskDetailScreen :6882–7709` (`_shortcuts_scope = "board.detail"`); field
widgets `:4900–5820` (`CycleField` … `PullRequestField`); detail-only pickers
`:6058–6546` (`DepPickerItem` … `FileReferencePickerScreen`). **Stay:**
`_load_task_types :692`, `_get_user_email :730`, `_current_tmux_session :5630`
(raw-tmux allowlist site `:5634`; also called from `:10380, 12205, 12383`) —
injected as `task_types_provider=`, `user_email_provider=`,
`tmux_session_provider=` (kw-only, required) at every `TaskDetailScreen(`
push site; `TaskSelectScreenBase` family `:6613–6734`; `ColumnMultiSelectScreen
:6546` (child 8). Lazy `webbrowser` / `section_viewer` / `SkipAction` imports
stay lazy.

## Manifest

`lib/shortcut_scopes.py:48` board row → `("board",)`; new row
`("board_detail_screen", "board/board_detail_screen.py", ("board.detail",))`.
Raw-tmux allowlist untouched.

## Order

Rebase check (t1521, t583_9 neighbours) → grep-confirm move set (record) →
module with injected-callable constructor → replace + push sites → manifest →
C3 sweep + mutants → `isinstance` grep (record; expected empty) → suite.

## Verification

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`;
  `test_board_detail_gates_section`, `test_settings_shortcuts_tab`,
  `test_shortcut_scopes`, `test_board_reference_doc_literals`,
  `test_board_package_contract`, `test_board_fixture_harness`,
  `test_board_keymap_characterization` green; `bash tests/test_no_raw_tmux.sh`,
  `bash tests/test_shortcuts_registry_coverage.sh` green.
- `grep -n '^class TaskDetailScreen\|^class .*Field(' .aitask-scripts/board/aitask_board.py`
  empty.
- Manual: `enter` on a card; edit every field type; `?` lists `board.detail`;
  Settings → Shortcuts still lists `board.detail`.

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_7`.
