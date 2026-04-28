---
priority: high
effort: low
depends: []
issue_type: bug
status: Done
labels: [brainstorming, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-28 00:21
updated_at: 2026-04-28 10:17
completed_at: 2026-04-28 10:17
boardidx: 90
---

## Symptom

Running `./.aitask-scripts/aitask_brainstorm_tui.sh <node>` and then clicking a section row (e.g. "Introduction") in the proposal-tab minimap inside `NodeDetailModal` crashes the TUI with:

```
File ".aitask-scripts/brainstorm/brainstorm_app.py", line 484,
  in on_section_minimap_section_selected
    minimap_id = event.control.id
                 ^^^^^^^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'id'
```

## Root cause

In Textual 8.1.1 the base `Message.control` property returns `None` by default. The custom messages `SectionMinimap.SectionSelected` and `SectionMinimap.ToggleFocus` (`.aitask-scripts/lib/section_viewer.py:180, 187`) inherit that default — they never override `control`, so any consumer reading `event.control` always gets `None`.

`NodeDetailModal` is the only consumer that mounts two minimaps in the same screen (`#proposal_minimap` and `#plan_minimap`) and disambiguates via `event.control.id`, so it is the only place this trips today. The same defect is also latent at `.aitask-scripts/brainstorm/brainstorm_app.py:512` in `on_section_minimap_toggle_focus` — pressing Tab from either minimap will crash with the same `AttributeError`.

Other consumers don't trip it today because they host a single minimap and don't read `event.control`:
- `.aitask-scripts/board/aitask_board.py` (`#board_minimap`)
- `.aitask-scripts/codebrowser/detail_pane.py` (`#detail_minimap`)
- `.aitask-scripts/codebrowser/history_detail.py` (`#history_detail_minimap`)
- `.aitask-scripts/lib/section_viewer.py` `SectionViewerScreen` (`#sv_minimap`)

## Fix

Add a one-line `control` property to both message classes in `.aitask-scripts/lib/section_viewer.py` returning the posting widget (`self._sender`). This is the cleanest fix — it future-proofs the API for any later consumer that hosts multiple minimaps and disambiguates by `event.control.id`, and `NodeDetailModal` then works without further changes.

Sketch (in `SectionMinimap`):

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

`MessagePump.post_message` sets `_sender` automatically when `SectionMinimap.on_section_row_selected` calls `self.post_message(self.SectionSelected(...))` (line 222) and when `action_toggle_focus` posts `ToggleFocus` (line 226), so no constructor changes are needed at call sites.

## Verification

1. `./.aitask-scripts/aitask_brainstorm_tui.sh <node-id>` → open a node detail with a proposal that has multiple sections.
2. Click each section row in the proposal-tab minimap → markdown scrolls to that section, no crash.
3. Switch to the plan tab, click a section → markdown scrolls, no crash.
4. From the proposal/plan markdown, press Tab to focus the minimap, then Tab again from the minimap → focus returns to markdown, no crash (covers `on_section_minimap_toggle_focus`).
5. Sanity check the four single-minimap consumers (board, codebrowser detail pane, codebrowser history detail, `SectionViewerScreen`) — they don't read `event.control`, so behavior should be unchanged; click a section in each and confirm no regressions.
