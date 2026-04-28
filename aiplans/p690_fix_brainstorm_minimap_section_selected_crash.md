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
