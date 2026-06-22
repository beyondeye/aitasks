---
Task: t1038_fix_brainstorm_running_row_focus_hover.md
Worktree: .
Branch: main
Base branch: main
---

# Implementation Plan: t1038 Fix Brainstorm Running Row Focus Hover

## Context

The brainstorm TUI already has a `GroupRow:focus:hover` rule that keeps a row in
the accent color family when it is focused and hovered. Several peer row types
had the same equal-specificity `:focus` and later `:hover` pattern but no
combined selector, so hover could override the focused accent state.

## Implementation Steps

1. Update `.aitask-scripts/brainstorm/styles.py`.
   - Add `:focus:hover` rules for `AgentStatusRow`, `ProcessRow`,
     `OperationRow`, and `NodeRow`.
   - Use `background: $accent-lighten-1; color: $text;`, matching the existing
     `GroupRow:focus:hover` behavior.

2. Update `.aitask-scripts/brainstorm/widgets.py`.
   - Add the same `DimensionRow:focus:hover` rule inside
     `DimensionRow.DEFAULT_CSS`.

3. Add regression coverage.
   - Create `tests/test_brainstorm_row_focus_hover_css.py`.
   - Assert the app-level selectors and `DimensionRow.DEFAULT_CSS` all include
     the accent-family focus-hover rule.
   - Include `GroupRow` in the test so the precedent remains protected.

4. Run focused verification.
   - `python -m unittest tests.test_brainstorm_row_focus_hover_css`
   - `python -m unittest tests.test_brainstorm_group_dblclick_focus tests.test_brainstorm_session_tab tests.test_brainstorm_dimension_row_expand tests.test_brainstorm_browse_view`

5. Follow Step 9 after review.
   - Commit code separately from task/plan files.
   - Archive t1038 through `aitask_archive.sh` after review approval.

## Verification

- `python -m unittest tests.test_brainstorm_row_focus_hover_css`
- `python -m unittest tests.test_brainstorm_group_dblclick_focus tests.test_brainstorm_session_tab tests.test_brainstorm_dimension_row_expand tests.test_brainstorm_browse_view`

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes

- **Actual work done:** Added accent-family `:focus:hover` rules for
  `AgentStatusRow`, `ProcessRow`, `OperationRow`, `NodeRow`, and `DimensionRow`,
  and added a focused regression test for those selectors.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Left `StatusLogRow` unchanged because it does not define a
  hover rule and therefore does not have the same focus-hover override problem.
- **Upstream defects identified:** None.
