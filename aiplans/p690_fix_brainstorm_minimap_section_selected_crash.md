---
Task: t690_fix_brainstorm_minimap_section_selected_crash.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Context

Clicking a section row in the proposal-tab (or plan-tab) minimap of the brainstorm `NodeDetailModal` crashes the TUI:

```
File ".aitask-scripts/brainstorm/brainstorm_app.py", line 484,
  in on_section_minimap_section_selected
    minimap_id = event.control.id
                 ^^^^^^^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'id'
```

In Textual 8.1.1, `Message.control` defaults to `None`. `SectionMinimap.SectionSelected` and `SectionMinimap.ToggleFocus` (`.aitask-scripts/lib/section_viewer.py:180, 187`) never override that default, so any consumer that reads `event.control` always gets `None`. `NodeDetailModal` is the only consumer hosting two minimaps in the same screen (`#proposal_minimap` + `#plan_minimap`), so it is the only place this crashes today. The same defect is latent on `on_section_minimap_toggle_focus` at `brainstorm_app.py:512` — Tab from either minimap would crash with the same `AttributeError`.

`MessagePump.post_message` already sets `_sender` on every posted message, so the cleanest fix is to expose `_sender` via a `control` property on both message classes. This future-proofs the API for any later consumer that hosts multiple minimaps and disambiguates by `event.control.id`. No call-site changes needed.

## File to Modify

**`.aitask-scripts/lib/section_viewer.py`** — add a `control` property to both `SectionMinimap.SectionSelected` and `SectionMinimap.ToggleFocus` (around lines 180–188).

## Implementation

Inside class `SectionMinimap`, augment the two nested message classes:

```python
class SectionSelected(Message):
    """Rebroadcast of :class:`SectionRow.Selected` so hosts listen at the minimap level."""

    def __init__(self, section_name: str) -> None:
        self.section_name = section_name
        super().__init__()

    @property
    def control(self) -> "SectionMinimap | None":
        return self._sender  # type: ignore[return-value]

class ToggleFocus(Message):
    """Emitted when Tab is pressed while the minimap (or a row) has focus."""

    @property
    def control(self) -> "SectionMinimap | None":
        return self._sender  # type: ignore[return-value]
```

Notes:
- `self._sender` is set by `MessagePump.post_message`, which is invoked by `SectionMinimap.on_section_row_selected` (line 222) and `action_toggle_focus` (line 226). No constructor changes required.
- Single-minimap consumers (`board`, `codebrowser/detail_pane.py`, `codebrowser/history_detail.py`, `SectionViewerScreen`) do not read `event.control`, so they are unaffected.

## Verification

1. Run `./.aitask-scripts/aitask_brainstorm_tui.sh <node-id>` and open a node detail with a proposal that has multiple sections.
2. Click each section row in the proposal-tab minimap → markdown scrolls to that section, no crash.
3. Switch to the plan tab, click a section → markdown scrolls, no crash.
4. From the proposal/plan markdown, press Tab to focus the minimap, then Tab again from the minimap → focus returns to markdown, no crash (covers `on_section_minimap_toggle_focus`).
5. Sanity-check the four single-minimap consumers (board, codebrowser detail pane, codebrowser history detail, `SectionViewerScreen`) — click a section in each, confirm no regressions.

## Step 9 — Post-Implementation

Follow the standard post-implementation flow in `task-workflow/SKILL.md` Step 9 (commit, archive `t690`, push). No worktree to remove (working on current branch).

## Post-Review Changes

### Change Request 1 (2026-04-28 00:55)
- **Requested by user:** While testing the AttributeError fix, the user reported a related defect in the same NodeDetailModal: clicking a section row in the proposal-tab minimap scrolls *near* the target but overshoots/undershoots by a few rows. They asked whether sharing the scroll container between minimap and markdown could be the cause.
- **Investigation:** Confirmed. In `on_section_minimap_section_selected` (`brainstorm_app.py:481`), the y target was computed as `(start_line / total_lines) * scroll.virtual_size.height` against `#proposal_scroll`. But `#proposal_scroll` contains BOTH the minimap (`max-height: 12`) and the markdown — its `virtual_size.height = minimap_h + markdown_h`. The line-ratio is the position within the markdown, so multiplying by the combined height gives `(L/T) * (minimap_h + markdown_h)` instead of the correct `minimap_h + (L/T) * markdown_h`. Off by `minimap_h * (1 - L/T)` — largest at top, ~0 at bottom.
- **Changes made:** Refactored `on_section_minimap_section_selected` to (a) compute y in markdown-local coordinates using the markdown widget's own `virtual_size.height`, (b) add the minimap's `outer_size.height` as the start-of-markdown offset within the scroll container. Used `event.control` (now reliable thanks to Change 1's `control` property on `SectionSelected`) for the minimap reference — no extra `query_one` needed. Both `proposal_minimap` and `plan_minimap` branches updated. `on_section_minimap_toggle_focus` was unaffected (no scroll math).
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`

## Final Implementation Notes

- **Actual work done:**
  1. `.aitask-scripts/lib/section_viewer.py` — added `control` property to `SectionMinimap.SectionSelected` and `SectionMinimap.ToggleFocus` returning `self._sender`. Fixes the `AttributeError: 'NoneType' object has no attribute 'id'` crash on minimap clicks/Tab in `NodeDetailModal`.
  2. `.aitask-scripts/brainstorm/brainstorm_app.py` — refactored `on_section_minimap_section_selected` to compute y from the markdown widget's own `virtual_size.height` plus the minimap's `outer_size.height` offset, instead of from the shared scroll container's combined height. Fixes the section-row jump overshoot reported during user review.
- **Deviations from plan:** The original plan covered only the `control` property fix. A second defect (scroll-offset miscalculation) was discovered and fixed during user review at the user's request — see Post-Review Changes above. Same minimap interaction in the same NodeDetailModal screen, so bundled into the same task per user direction.
- **Issues encountered:** None during implementation. The pre-existing uncommitted changes in `aitask_lock.sh`, `aitask_pick_own.sh`, `agent_command_screen.py`, and `task-workflow/SKILL.md` were unrelated to this task and were intentionally NOT staged.
- **Key decisions:**
  - Used `event.control.outer_size.height` (the SectionMinimap widget) directly instead of querying for the minimap by id — `event.control` is now reliable thanks to the property added in Fix 1.
  - Single-minimap consumers (`board`, `codebrowser/detail_pane.py`, `codebrowser/history_detail.py`, `SectionViewerScreen`) were left untouched; they don't read `event.control` and `SectionViewerScreen` puts its minimap in a sibling Horizontal, not inside the scroll container, so no offset bug there.
- **Upstream defects identified:** None.
