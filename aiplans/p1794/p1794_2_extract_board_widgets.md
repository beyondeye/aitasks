---
Task: t1794_2_extract_board_widgets.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md, aitasks/t1794/t1794_3_*.md … t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_2 — Extract the board-generic widgets into `board_widgets.py`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1, C2, C3, C5 PINNED). Zero patch sites, zero module-global reads — the
pattern-proving move.

## Move set (verbatim, anchors at e2f12c499)

`_issue_indicator :706`, `_pr_indicator :718`, `ColumnHeader :3181`,
`MarkedSelection :3335`, `TaskCard :3402–3609`, `_followup_marker :3778`,
`_plan_approved_marker :3802`, `_status_badge_text :3844`,
`_followup_glyph_text :3901` (+ helpers in `:3778–3915` they call),
`PickerItem :4205–4230`, `LoadingOverlay :8004–8059`. `InFlightTaskCard :3611`
stays.

## Invariants

- `board_widgets.py` imports only `textual`, `rich`, `lib/` modules
  (`mark_glyphs`, `topic_semantics`); no `sys.path` insert of its own; none of
  the C2 names; no `aitask_board` import.
- `aitask_board.py`: `import board_widgets` + `from board_widgets import
  (…all moved names…)`, placed before `InFlightTaskCard(TaskCard)`.
- `CardHost` `Protocol` documents `TaskCard`'s app surface (`check_action`,
  `action_toggle_children`, `action_view_details`, `expanded_tasks`; `marked`
  only behind `self.markable`).
- `tests/test_mark_glyphs_single_source.py` lists name `board/board_widgets.py`
  as the `mark_markup` consumer; proven still falsifiable by a stray `"✓"`.

## Order

Rebase check → module → import pair → C3 sweep (expected empty; record) →
manifest tests → suite.

## Verification

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `test_board_followup_glyph`, `test_board_plan_approved_marker`,
  `test_textual_markup_structure`, `test_board_inflight_view`,
  `test_board_workflow_phase`, `test_mark_glyphs_single_source`,
  `test_board_reference_doc_literals`, `test_board_package_contract`,
  `test_board_fixture_harness`, `test_board_keymap_characterization` green.
- `grep -n '^class TaskCard\|^class PickerItem\|^class LoadingOverlay'
  .aitask-scripts/board/aitask_board.py` empty.
- Manual: `ait board` cards render with badges; `z` renders trail cards.

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_2`.
