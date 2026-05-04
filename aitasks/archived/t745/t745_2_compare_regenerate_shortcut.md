---
priority: high
effort: low
depends: [t745_1]
issue_type: enhancement
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-04 22:21
updated_at: 2026-05-04 23:57
completed_at: 2026-05-04 23:57
---

## Context

Sibling of t745. Issue 1 from the parent: once a comparison is shown, the user has no visible way to regenerate it with different nodes — `c` re-opens the modal but the binding is buried in the global tab-switching list. Now that t745_1 has hidden tab-switching shortcuts from the footer and added the `_TAB_SCOPED_ACTIONS` registry, this task adds a discoverable `r` key on the Compare tab that re-opens `CompareNodeSelectModal` and visibly shows in the footer only when the Compare tab is active.

## Dependency

Requires t745_1 (the `_TAB_SCOPED_ACTIONS` registry and `check_action` infrastructure).

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `BrainstormApp.BINDINGS` (lines 1512–1523) — add `Binding("r", "compare_regenerate", "Regenerate")`.
  - `_TAB_SCOPED_ACTIONS` (added in t745_1) — add entry `"compare_regenerate": "tab_compare"`.
  - `compose()` Compare hint Label (line 1602) — update text from `"Press 'c' to select nodes for comparison, 'D' to diff"` to `"Press 'r' to (re)select nodes, 'D' to open full diff"`.
  - Add new method `action_compare_regenerate(self) -> None` that pushes `CompareNodeSelectModal`.
  - Refactor `action_tab_compare` (lines 1926–1941) to share a single helper with `action_compare_regenerate` so both routes call the same `_open_compare_select_modal()` (or similar).

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_app.py:1926-1941` — existing `action_tab_compare` body that opens the modal on second press. Extract the modal-push into a private helper.
- `aiplans/archived/p745/p745_1_*.md` (read once t745_1 lands) — reference for how t745_1 wired `_TAB_SCOPED_ACTIONS` and `check_action`.

## Implementation Plan

1. Read the t745_1 archived plan first to understand the registry shape.
2. Extract the modal-open path from `action_tab_compare` into a new private helper:
   ```python
   def _open_compare_select_modal(self) -> None:
       # existing body that constructs and pushes CompareNodeSelectModal
       ...
   ```
   `action_tab_compare` should call this helper on its second-press branch instead of duplicating the modal construction.
3. Add the new action:
   ```python
   def action_compare_regenerate(self) -> None:
       self._open_compare_select_modal()
   ```
4. Add `Binding("r", "compare_regenerate", "Regenerate")` to `BINDINGS`.
5. Register `"compare_regenerate": "tab_compare"` in `_TAB_SCOPED_ACTIONS`.
6. Update the Compare tab hint Label text.
7. Cache invalidation: no extra work needed — `_build_compare_matrix` already calls `container.remove_children()`, and the modal's callback already updates `_compare_nodes`.

## Verification Steps

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635`.
- Switch to the Compare tab. Footer should show `r Regenerate` (and `D Diff` after t745_4 lands; until then, the old Shift+D from `on_key` remains).
- Pick two nodes via the modal (`c` first press to switch, `c` second press if no comparison exists, OR `r`).
- After comparison renders, press `r`. The `CompareNodeSelectModal` re-opens. Pick different nodes; the table replaces the previous comparison.
- Switch back to Dashboard. Footer no longer shows `r Regenerate`.
- The hint Label inside the empty Compare tab now reads the updated text.

## Notes for sibling tasks

- t745_4 will register `compare_diff` in the same `_TAB_SCOPED_ACTIONS` map.
- The extracted `_open_compare_select_modal` helper may also be reusable by future compare-related actions.
