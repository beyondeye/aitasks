---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [brainstorm, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-22 12:46
updated_at: 2026-03-22 12:51
---

## Problem

The brainstorm TUI crashes when switching to the DAG tab. The error is:
```
AttributeError: 'NoneType' object has no attribute 'render_strips'
```

## Root Cause

`DAGDisplay._render()` (line 420 in `brainstorm_dag_display.py`) accidentally overrides
Textual's internal `Widget._render()` method. `Widget._render()` is expected to return a
`Visual` object, but `DAGDisplay._render()` returns `None` (it was meant as a private helper
to rebuild and update the ASCII art in the Static widget).

When Textual's rendering pipeline tries to render the DAG tab, it calls `_render()` on the
`DAGDisplay` widget and gets `None`, which then crashes at `Visual.to_strips()`.

## Fix

Rename `DAGDisplay._render()` to `_render_dag()` (or `_update_dag_display()`) and update
the 3 call sites:

1. `load_dag()` at line 418: `self._render()` → `self._render_dag()`
2. `action_next_node()` at line 489: `self._render()` → `self._render_dag()`
3. `action_prev_node()` at line 495: `self._render()` → `self._render_dag()`

## Verification

Run the brainstorm TUI with `ait brainstorming 426` and switch to the DAG tab — it should
display "No nodes in session" without crashing. Also test with a session that has nodes
to verify the DAG renders correctly.
