---
priority: medium
effort: high
depends: [t1794_6]
issue_type: refactor
status: Ready
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 7 of t1794. Extract the task editor — `TaskDetailScreen`, its field
widgets and the pickers only it opens — into `board_detail_screen.py`. This
is the second-largest block in the mono-file (~1,750 lines) and carries its
own shortcut scope (`board.detail`, `aitask_board.py:6885`), so the shortcut
manifest must follow it. Three helpers it calls are also called by code that
stays in the board; parent contract C1 forbids an import-back, so they are
injected as callables.

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— C1 (import-back prohibition and injected helpers), C3, C5, "Scope
decisions" (the probe-name second-identity limitation). Anchors at
`e2f12c499` (unchanged at `c78deab36`).

## Key files to modify

- `.aitask-scripts/board/board_detail_screen.py` — NEW: `TaskDetailScreen`
  (`:6882–7709`, `_shortcuts_scope = "board.detail"`); the field widgets
  `CycleField :4900`, `ReadOnlyField :4993`, `DependsField :5005`,
  `VerifiesField :5078`, `CrossRepoDepsField :5151`, `ChildrenField :5203`,
  `FoldedTasksField :5256`, `AnchorField :5348`, `FollowupKindPickerItem :5409`,
  `FollowupKindPickerScreen :5447`, `FollowupKindField :5509`,
  `FileReferencesField :5645`, `FoldedIntoField :5705`, `ParentField :5737`,
  `IssueField :5768`, `PullRequestField :5794`; the detail-only pickers
  `DepPickerItem :6058`, `DependencyPickerScreen :6094`, `CrossRepoRefItem
  :6192`, `CrossRepoRefPickerScreen :6220`, `ChildPickerItem :6349`,
  `ChildPickerScreen :6370`, `FoldedTaskPickerItem :6397`,
  `FoldedTaskPickerScreen :6418`, `FileReferenceItem :6446`,
  `FileReferencePickerScreen :6463`. **Confirm each is referenced only from
  the detail screen by grep before moving**; anything with a board caller
  stays. `TaskSelectScreenBase` / `WorkReportTaskSelectScreen` /
  `MoveTaskSelectScreen` (`:6613–6734`) and `ColumnMultiSelectScreen`
  (`:6546`, child 8) stay.
- `.aitask-scripts/board/aitask_board.py` — `import board_detail_screen` +
  flat re-imports; `TaskDetailScreen(…, task_types_provider=_load_task_types,
  user_email_provider=_get_user_email, tmux_session_provider=
  _current_tmux_session)` at every push site (`:11302+` and any other —
  grep `TaskDetailScreen(`); `_load_task_types` (`:692`), `_get_user_email`
  (`:730`), `_current_tmux_session` (`:5630` — inside the field-widget block,
  keep it in the board; it holds a raw-`tmux` call at `:5634` on the
  `tests/test_no_raw_tmux.sh:56` allowlist) **stay** — they also serve
  `:10380, 12205, 12383`.
- `.aitask-scripts/lib/shortcut_scopes.py:48` — board row scopes become
  `("board",)`; new row `("board_detail_screen",
  "board/board_detail_screen.py", ("board.detail",))`.
- `tests/test_board_reference_doc_literals.py` — detail-screen pins read the
  new module.
- `tests/test_board_package_contract.py` — bare-import pairing gains
  `board_detail_screen` if any patched name lives there (grep).

## Reference files for patterns

- `aidocs/framework/tui_conventions.md:867–925` — manifest rules; the sweep
  re-execs each manifest module under a probe name and registers classes
  whose `__module__` is the probe (`lib/shortcut_scopes.py:124–160`), which is
  why the row is mandatory once the scope moves.
- `tests/test_shortcut_scopes.py:45–80, 111–127` — drift guard and the
  board-scope filtered sweep (`board.detail` must still register from the
  board editor's `?`).
- `aitask_board.py:7448, 7476, 7505, 5782, 5809, 7516` — the lazy imports
  (`section_viewer`, `webbrowser`, `SkipAction`) that must stay lazy.
- `tests/test_board_detail_gates_section.py`, `tests/test_settings_shortcuts_tab.py`.
- `aitask_board.py:53–66` — import pairing.

## Implementation plan

1. **Rebase check** (parent pre-phase) over `:4900–5820`, `:6058–6546`,
   `:6882–7709`, `:11289–11310`; pending neighbours **t1521** (AnchorField
   persistence), **t1603_4** landed already (gates section), **t583_9** —
   read, do not pre-implement; foreign `Implementing` → stop at the checkpoint.
2. Grep-confirm the move set (each class's callers); record the list.
3. Create the module with the injected-callable constructor parameters
   (keyword-only, required); replace definitions; update every push site.
4. Manifest rows; run the drift guard and the filtered-sweep tests.
5. C3 sweep on the moved names (`grep -n 'patch.object(\(ab\|B\|self.ab\), "'
   tests/ | grep -i 'field\|picker\|detail'`); repoint + mutant each.
6. Record the `isinstance` grep for every moved class
   (`grep -rn 'isinstance(.*\(TaskDetailScreen\|Field\|PickerScreen\)'
   .aitask-scripts tests`) in the child plan — expected empty.

## Verification steps

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `python -m pytest tests/test_board_detail_gates_section.py
  tests/test_settings_shortcuts_tab.py tests/test_shortcut_scopes.py
  tests/test_board_reference_doc_literals.py tests/test_board_package_contract.py
  tests/test_board_fixture_harness.py tests/test_board_keymap_characterization.py -q`
  green; `bash tests/test_no_raw_tmux.sh`, `bash
  tests/test_shortcuts_registry_coverage.sh` green with the allowlist
  untouched.
- `grep -n '^class TaskDetailScreen\|^class .*Field(' .aitask-scripts/board/aitask_board.py`
  returns nothing.
- Manual in tmux: `ait board` → `enter` on a card → edit every field type
  (cycle, depends picker, issue URL open, file references, anchor), `?` in the
  detail screen lists `board.detail` keys, `esc` returns; Settings →
  Shortcuts still lists `board.detail`.
