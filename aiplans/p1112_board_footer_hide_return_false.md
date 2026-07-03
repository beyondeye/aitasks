---
Task: t1112_board_footer_hide_return_false.md
Worktree: .
Branch: main
Base branch: main
---

# Implementation Plan

## Summary

Fix Board TUI footer actions that are meant to be hidden when inapplicable but
currently return `None` from `KanbanApp.check_action`, which Textual 8.2.7
renders as disabled/greyed instead of absent.

## Steps

1. Update `.aitask-scripts/board/aitask_board.py` in
   `KanbanApp.check_action`.
   - Add a short method-level comment documenting that `False` hides a footer
     binding while `None` leaves it visible but disabled.
   - Change hide-intent branches for `commit_selected`, `commit_all`,
     `pick_task`, `brainstorm_task`, and `open_cross_repo` to return `False`
     when inapplicable.
   - Include the same-shaped `toggle_children` cases found during audit: no
     focused card and focused parent without children should return `False`.
   - Leave unrelated `return None` sites outside `check_action` unchanged.

2. Add `tests/test_board_footer_visibility.py`.
   - Use a real `KanbanApp` under Textual `run_test`.
   - Assert footer absence through `screen.active_bindings`, not only the raw
     action return value.
   - Include focused inapplicable cases for `commit_selected`,
     `open_cross_repo`, and `toggle_children`.
   - Include global/no-focus cases for `commit_all`, `pick_task`, and
     `brainstorm_task`.

3. Verify.
   - Run the focused regression test.
   - Run the full Python test suite if practical.
   - Step 9 post-implementation should run the gate orchestrator for `t1112`
     before archival.

## Risk

### Code-health risk

Low. The change is confined to conditional footer visibility decisions in one
method and does not alter action handlers.

### Goal-achievement risk

Low. The regression test checks Textual's footer surface directly via
`active_bindings`, covering the exact `None` versus `False` behavior.

### Planned mitigations

None.

## Final Implementation Notes

- **Actual work done:** Updated `KanbanApp.check_action` so inapplicable board
  footer actions return `False` and are removed from Textual
  `screen.active_bindings`. Added focused and no-focus regression coverage for
  Commit, Commit All, Pick, Brainstorm, Cross-repo, and Toggle Children.
- **Deviations from plan:** None.
- **Issues encountered:** The focused regression test passed with `unittest`.
  The full Python suite completed with unrelated existing failures in
  `test_gate_orchestrator_registry` and `test_tui_switcher_agent_launch`; the
  new board footer test passed inside that run.
- **Key decisions:** Included `toggle_children` because the audit found the same
  hide-intent `None` behavior for no focus and focused parent-without-children.
- **Upstream defects identified:** None.
