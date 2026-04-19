---
Task: t571_11_fix_section_viewer_rendering_and_bindings.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_6_*.md, aitasks/t571/t571_7_*.md, aitasks/t571/t571_8_*.md, aitasks/t571/t571_9_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_1_*.md, p571_2_*.md, p571_3_*.md, p571_4_*.md, p571_5_*.md, p571_10_*.md
Worktree: (none — working on current branch per fast profile)
Branch: main
Base branch: main
---

# Fix section viewer rendering and bindings (t571_11)

## Context

The shared `section_viewer` widget (`.aitask-scripts/lib/section_viewer.py`, landed in t571_5, first consumed by t571_10 for the board's `TaskDetailScreen`) has four defects surfaced during manual testing. All are lib-level (or lib-plus-board) and MUST land before t571_8 (codebrowser) and t571_9 (brainstorm) consume the widget — otherwise the same bugs repeat in three places.

All four hypotheses in the task description were verified by direct code inspection. One deviation from the task description: Bug 3 has 2 call sites, not 3 — `SectionViewerScreen.on_section_minimap_section_selected` delegates to `SectionAwareMarkdown.scroll_to_section`, so fixing the latter covers both the fullscreen and board-embedded modal paths.

## Key files to modify

- `.aitask-scripts/lib/section_viewer.py` — CSS fixes (bugs 1, 2), `animate=False` (bug 3), Tab action rewrite (bug 4)
- `.aitask-scripts/board/aitask_board.py` — `animate=False` at one call site (bug 3)
- `aiplans/p571/p571_8_codebrowser_section_viewer_integration.md` — add `animate=False` note for downstream consumers
- `aiplans/p571/p571_9_brainstorm_node_detail_section_viewer_integration.md` — same

## Implementation

### Bug 1 — inline minimap collapse (CSS, section_viewer.py:152-158)

`SectionMinimap.DEFAULT_CSS` currently sets `max-width: 35` with no height directive. Inside a parent `VerticalScroll` (`#md_view` in `TaskDetailScreen`), Textual collapses it to 1 row.

**Change** `SectionMinimap.DEFAULT_CSS` to:
```css
SectionMinimap {
    max-width: 50;            /* widened for bug 2 too */
    height: auto;
    max-height: 12;
    border-right: solid $primary;
    background: $panel;
}
```

- `height: auto` makes the minimap size to its rows when embedded in another VerticalScroll (fixes the collapse).
- `max-height: 12` caps the inline footprint so long plans don't push the plan markdown below the fold; the widget remains its own VerticalScroll, so rows past 12 scroll within the minimap.
- `max-width: 50` up from 35 — gives the dimension tags room (bug 2).

### Bug 2 — dimension list mid-word truncation (CSS, section_viewer.py:93-106)

`SectionRow.render()` emits `" {name} [{dims}]"` with no overflow handling; rows wider than the minimap silently clip.

**Combined with bug 1:** widening to 50 cols handles most t571_5-class plans. For still-too-long tags, add `text-overflow: ellipsis` to `SectionRow.DEFAULT_CSS`:

```css
SectionRow {
    height: 1;
    width: 100%;
    padding: 0 1;
    background: $surface;
    text-overflow: ellipsis;
}
```

`width: 100%` is needed so the row fills the minimap width before clipping; otherwise `text-overflow` has nothing to clip against. No changes to `render()` itself.

### Bug 3 — Enter-scroll should not animate

Two call sites (not three):

1. `section_viewer.py:234` in `SectionAwareMarkdown.scroll_to_section()`:
   ```python
   self.scroll_to(y=target_y, animate=False)
   ```
2. `aitask_board.py:2340` in `TaskDetailScreen.on_section_minimap_section_selected()`:
   ```python
   md_view.scroll_to(y=y, animate=False)
   ```

`SectionViewerScreen.on_section_minimap_section_selected` (section_viewer.py:294) delegates to `scroll_to_section`, so fix #1 covers it transitively.

Also update `aiplans/p571/p571_8_*.md` and `aiplans/p571/p571_9_*.md` (in their `SectionSelected` handler examples) to pass `animate=False` so t571_8 and t571_9 don't regress on integration.

### Bug 4 — Tab in SectionViewerScreen dismisses modal (section_viewer.py:302-311)

**Current** (verified):
```python
def action_focus_minimap(self) -> None:
    content = self.query_one("#sv_content", SectionAwareMarkdown)
    focused = self.screen.focused
    if focused is None or (focused is not content and focused not in content.walk_children()):
        raise SkipAction()
    minimap = self.query_one("#sv_minimap", SectionMinimap)
    if not minimap.display:
        raise SkipAction()
    minimap.focus_first_row()
```

Root cause confirmed: Tab binding is `priority=True`. When focus isn't on `#sv_content`, `SkipAction` propagates; dispatch falls through to the underlying `TaskDetailScreen.action_focus_minimap` (added in t571_10), which also `SkipAction`s (focus isn't on board's `#md_view Markdown` either), and Textual's default focus-cycle walks focus out of the modal — effectively dismissing it.

**Fix:** The modal owns Tab unconditionally — remove SkipAction paths and toggle between the two panes.

```python
def action_focus_minimap(self) -> None:
    """Tab in the modal always toggles focus between minimap and content."""
    minimap = self.query_one("#sv_minimap", SectionMinimap)
    content = self.query_one("#sv_content", SectionAwareMarkdown)
    focused = self.screen.focused
    if focused is minimap or (focused is not None and focused in minimap.walk_children()):
        content.focus()
    else:
        if minimap.display:
            minimap.focus_first_row()
        else:
            content.focus()
```

- No `SkipAction` import needed; simplest possible behavior.
- If `minimap.display` is False (no sections), Tab re-focuses content — a no-op but prevents the dismiss path.
- Existing `on_section_minimap_toggle_focus` handler already moves focus minimap → content; this new action handles content → minimap and any other state.

The `SkipAction` pattern was designed for **embedded** contexts (board's `TaskDetailScreen` form field navigation, codebrowser's tree/detail split) where Tab must fall through. It does not apply to a dedicated modal with only two focus targets.

The board's `TaskDetailScreen.action_focus_minimap` stays as-is — it legitimately needs SkipAction so Tab can still cycle form fields when the plan view isn't active.

## Verification

Manual (primary):

1. `ait board` → open a task whose plan has `<!-- section: ... [dimensions: ...] -->` markers (use `aiplans/archived/p571/p571_5_*.md` or `aiplans/p571/p571_8_*.md` — both are sectioned).
2. Press `v` → inline minimap renders ALL rows (not just 1). Minimap caps at ~12 rows of height; plan markdown stays usable below.
3. Press `V` → fullscreen. Row text shows full name + full dimension list at 50 cols, or a clean `…` ellipsis when a line is longer than that. No mid-word cuts.
4. Enter on a minimap row → content jumps INSTANTLY to the section (no animation).
5. Fullscreen Tab cycle: focus starts on minimap → Tab → focus on content → Tab → focus back on minimap. Modal stays mounted. Escape still dismisses.
6. Regression: from board form (status/priority widgets) press Tab with plan view NOT active → still cycles form fields (TaskDetailScreen's SkipAction path).

Headless (regression guard for bug 4):

Add a Pilot test — or at minimum manually repro twice — that presses Tab repeatedly inside `SectionViewerScreen` and asserts the screen is still on the stack after several presses. The hypothesis is ironclad in theory but the dispatch chain in Textual is worth a mechanical check.

## Consumer plan updates (docs-only, no code)

For t571_8 (`aiplans/p571/p571_8_codebrowser_section_viewer_integration.md`) and t571_9 (`aiplans/p571/p571_9_brainstorm_node_detail_section_viewer_integration.md`):

- Find the `on_section_minimap_section_selected` example snippet and change `animate=True` → `animate=False`.
- Add a one-liner note in each plan's "Integration" section: "Pass `animate=False` to `scroll_to()` — matches t571_11 fix; see `section_viewer.py:234` pattern."

## Step 9: Post-Implementation

Follow Step 9 of the shared task-workflow for commit, archival, merge, and push. No worktree to tear down (fast profile, current branch).
