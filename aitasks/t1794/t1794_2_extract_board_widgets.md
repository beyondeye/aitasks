---
priority: medium
effort: medium
depends: [t1794_1]
issue_type: refactor
status: Ready
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 2 of t1794. First extraction, chosen because it has **zero test patch
sites and zero module-global reads**: the board-generic widgets and helpers
that the trail cards subclass or call. Everything the later
`board_trail_view.py` (child 3) and `trails_app.py` (child 6) need from the
board's widget layer lands here, so the trail code never imports
`aitask_board` (parent contract C1).

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— "Target file map", C1, C2, C3, C5. Anchors at `e2f12c499` (unchanged at
`c78deab36`).

## Key files to modify

- `.aitask-scripts/board/board_widgets.py` — NEW. Move verbatim:
  `_issue_indicator` (`aitask_board.py:706`), `_pr_indicator` (`:718`),
  `ColumnHeader` (`:3181`), `MarkedSelection` (`:3335`), `TaskCard`
  (`:3402–3609`), `_followup_marker` (`:3778`), `_plan_approved_marker`
  (`:3802`), `_status_badge_text` (`:3844`), `_followup_glyph_text` (`:3901`)
  and any helper between `:3778–3915` they call, `PickerItem` (`:4205–4230`),
  `LoadingOverlay` (`:8004–8059`). `InFlightTaskCard` (`:3611`) **stays** in
  the board.
- `.aitask-scripts/board/aitask_board.py` — `import board_widgets` +
  `from board_widgets import (…every moved name…)` so `ab.TaskCard`,
  `ab.PickerItem`, `ab._status_badge_text` etc. keep resolving for tests and
  for the board's own code; delete the moved definitions.
- `tests/test_mark_glyphs_single_source.py:82,117,132` — `board_widgets.py`
  becomes the `mark_markup` consumer (`TaskCard` uses it); update
  `CONSUMERS` / `RE_EXPORTS` / `ALLOWED_LITERALS` so the single-source guard
  still passes and still fails on a stray literal (run it once with a stray
  `"✓"` added to prove it).
- `tests/test_board_reference_doc_literals.py` — pins that point at the badge
  helpers now read `board_widgets`.
- `lib/shortcut_scopes.py` — no row: none of the moved classes carries a
  `_shortcuts_scope` (verify by grep before and after).

## Reference files for patterns

- `aitask_board.py:53–66` — the `import trail_discovery` + `from
  trail_discovery import (…)` pairing this child mirrors (bare import for
  patch targets, flat re-import for names).
- `lib/board_columns.py`, `lib/board_ordering.py` — existing `board_*`
  modules that the board imports flat (`aitask_board.py:1015, 1022–1027`).
- `aitask_board.py:3402–3440` — `TaskCard.__init__` / `_is_marked`: the
  `self.app` surface (`marked` behind `self.markable :3437`; `check_action`,
  `action_toggle_children`, `expanded_tasks`, `action_view_details`
  `:3602–3608`) — document it as a `CardHost` `typing.Protocol` in
  `board_widgets.py`; trail cards are non-markable by construction
  (`:3415–3419`) and override `on_click`.
- `tests/lib/board_fixture.py` docstring "Every fixture task carries at least
  one non-board metadata key" (`TaskManager._is_phantom_stub` is not moved
  here, but `Task`-shaped inputs to `TaskCard` are).

## Implementation plan

1. **Rebase check** as in the parent pre-phase: `git log --oneline -20 --
   .aitask-scripts/board/`; re-read every range above; scan for foreign
   `Implementing` tasks on the board; stop at the checkpoint if one exists.
2. Create `board_widgets.py` with the moved code, its own imports (`textual`,
   `rich`, `mark_glyphs.mark_markup`, `topic_semantics.parse_task_filename`
   — all `lib/` modules, resolved through the existing `lib` `sys.path`
   insert that `aitask_board.py` performs before importing siblings; do NOT
   add a `sys.path` insert to `board_widgets.py`). No `task_dir()` call, none
   of the C2 names (the child-1 guard enforces this).
3. Replace the definitions in `aitask_board.py` with the import pair. Keep the
   names' order of first use intact (`TaskCard` is referenced by
   `InFlightTaskCard(TaskCard)` at `:3611`; the import must precede it).
4. C3 sweep: `grep -n 'patch.object(\(ab\|B\|self.ab\), "\(TaskCard\|PickerItem\|
   MarkedSelection\|_status_badge_text\|_followup_marker\|_plan_approved_marker\|
   _issue_indicator\|_pr_indicator\|LoadingOverlay\|ColumnHeader\)"' tests/`
   — expected empty; record the result. If non-empty, repoint to
   `ab.board_widgets` and prove each with a mutant.
5. Update the two manifest tests; run the child-1 guards.
6. Pilot smoke: `tests/test_board_bytrail_view.py` and
   `tests/test_board_inflight_view.py` (they render `TaskCard` subclasses).

## Verification steps

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `python -m pytest tests/test_board_followup_glyph.py
  tests/test_board_plan_approved_marker.py tests/test_textual_markup_structure.py
  tests/test_board_inflight_view.py tests/test_board_workflow_phase.py
  tests/test_mark_glyphs_single_source.py tests/test_board_reference_doc_literals.py
  tests/test_board_package_contract.py tests/test_board_fixture_harness.py
  tests/test_board_keymap_characterization.py -q` green.
- `grep -n '^class TaskCard\|^class PickerItem\|^class LoadingOverlay'
  .aitask-scripts/board/aitask_board.py` returns nothing.
- `ait board` boots; cards render with badges; `z` By-Trail renders trail
  cards (manual, in tmux).
