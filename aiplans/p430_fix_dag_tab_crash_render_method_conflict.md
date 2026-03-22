---
Task: t430_fix_dag_tab_crash_render_method_conflict.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The brainstorm TUI crashes when switching to the DAG tab. `DAGDisplay._render()` (a private helper that rebuilds the ASCII art display) accidentally overrides Textual's internal `Widget._render()` which must return a `Visual` object. Since `DAGDisplay._render()` returns `None`, Textual crashes with `AttributeError: 'NoneType' object has no attribute 'render_strips'`.

## Plan

Rename `_render` → `_render_dag` in `.aitask-scripts/brainstorm/brainstorm_dag_display.py`:

1. **Line 420:** Method definition `def _render(self) -> None:` → `def _render_dag(self) -> None:`
2. **Line 418:** Call in `load_dag()`: `self._render()` → `self._render_dag()`
3. **Line 489:** Call in `action_next_node()`: `self._render()` → `self._render_dag()`
4. **Line 495:** Call in `action_prev_node()`: `self._render()` → `self._render_dag()`

## Verification

Run headless Textual test to confirm no crash when switching to DAG tab.

## Final Implementation Notes
- **Actual work done:** Renamed `_render` → `_render_dag` in 4 locations (1 definition + 3 call sites) in `brainstorm_dag_display.py`, exactly as planned
- **Deviations from plan:** None
- **Issues encountered:** None — straightforward rename
- **Key decisions:** Chose `_render_dag` as the new name to be descriptive and avoid future Textual internal method conflicts
