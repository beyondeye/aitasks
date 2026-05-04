---
Task: t745_2_compare_regenerate_shortcut.md
Parent Task: aitasks/t745_improve_node_comparator.md
Sibling Tasks: aitasks/t745/t745_1_context_aware_footer.md, aitasks/t745/t745_3_compact_equal_and_inline_diff.md, aitasks/t745/t745_4_diffviewer_screen_integration.md
Archived Sibling Plans: aiplans/archived/p745/p745_*_*.md
Worktree: aiwork/t745_2_compare_regenerate_shortcut
Branch: aitask/t745_2_compare_regenerate_shortcut
Base branch: main
---

# Plan — t745_2: Compare tab regenerate shortcut

## Context

Issue 1 from the parent: once a comparison is shown, users have no visible way to regenerate it with different nodes. With t745_1's context-aware footer in place, this task adds an `r` key visible only on the Compare tab that re-opens `CompareNodeSelectModal` to pick fresh nodes.

User-confirmed design decision: regenerate **always re-opens the modal** (not "refresh same nodes").

## Critical files

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `BINDINGS` — add `Binding("r", "compare_regenerate", "Regenerate")`.
  - `_TAB_SCOPED_ACTIONS` — add `"compare_regenerate": "tab_compare"`.
  - `compose()` line 1602 — update the Compare hint Label text.
  - `action_tab_compare` (lines 1926–1941) — refactor to share a private helper.
  - New: `_open_compare_select_modal()` private helper, `action_compare_regenerate()`.

## Implementation steps

1. **Read t745_1's archived plan** (`aiplans/archived/p745/p745_1_context_aware_footer.md`) to confirm the exact `_TAB_SCOPED_ACTIONS` shape.

2. **Extract modal-open into a helper.** Find the body inside `action_tab_compare` that constructs and pushes `CompareNodeSelectModal`. Move it to:
   ```python
   def _open_compare_select_modal(self) -> None:
       # … original body that builds CompareNodeSelectModal and push_screen() …
   ```
   Replace the second-press branch in `action_tab_compare` with a call to `self._open_compare_select_modal()`.

3. **Add new action**:
   ```python
   def action_compare_regenerate(self) -> None:
       self._open_compare_select_modal()
   ```

4. **Add binding** (after the four tab bindings, before `ctrl+r`):
   ```python
   Binding("r", "compare_regenerate", "Regenerate"),
   ```

5. **Register in registry**:
   ```python
   _TAB_SCOPED_ACTIONS: dict[str, str] = {
       "compare_regenerate": "tab_compare",
   }
   ```

6. **Update hint Label** at `compose()` line 1602:
   ```python
   "Press 'r' to (re)select nodes, 'D' to open full diff"
   ```

## Verification

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635`.
- Switch to Compare tab. Footer shows `r Regenerate`.
- Pick two nodes via the modal (use `r` or `c`-twice). Comparison renders.
- Press `r` — modal reopens. Pick different nodes — comparison replaces.
- Switch to Dashboard — `r Regenerate` no longer in footer.
- Verify the empty-state hint Label matches the new text on first entry to the Compare tab.

## Out of scope

- Caching / refresh-without-modal behavior. Always opens the modal per user decision.

## Final Implementation Notes

(to be filled in at Step 8)
