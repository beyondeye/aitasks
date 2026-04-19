---
priority: high
effort: medium
depends: [t571_10, 5]
issue_type: bug
status: Implementing
labels: [brainstorming, ait_brainstorm, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 11:07
updated_at: 2026-04-19 11:31
---

<!-- section: context [dimensions: motivation] -->

## Context

Post-integration fixes for the shared section viewer widget (`.aitask-scripts/lib/section_viewer.py`, landed via t571_5, first consumed by t571_10 for board). Four issues surfaced during manual testing on the board TUI. All are lib-level (or lib-plus-board) and must be fixed BEFORE t571_8 (codebrowser) and t571_9 (brainstorm) consume the widget — otherwise the same bugs repeat in three places.

<!-- /section: context -->

<!-- section: issues [dimensions: defects] -->

## Issues to Fix

### 1. Inline minimap collapses to a single line (board; likely also codebrowser/brainstorm)

**Symptom:** Pressing `v` on a task with a sectioned plan in the board's `TaskDetailScreen` mounts the `SectionMinimap` above the Markdown inside `#md_view`, but only the first row is visible.

**Likely cause:** `SectionMinimap` is a `VerticalScroll` subclass. Its `DEFAULT_CSS` sets `max-width: 35` but no `min-height` / `height`. Inside a `VerticalScroll` (`#md_view`), Textual collapses it to its intrinsic minimum (1 row) because there's no sizing guidance.

**Fix:** Set explicit `height: auto` + `max-height: <N>` (or similar sizing) in `SectionMinimap.DEFAULT_CSS`. Prefer a lib-level CSS fix so the three host TUIs don't duplicate layout logic.

### 2. Dimension list truncates mid-word in fullscreen minimap

**Symptom:** In `SectionViewerScreen` (fullscreen), a row like `Introduction [motivation,` is cut off before the closing `]` — part of the dimension list doesn't fit.

**Likely cause:** `SectionRow.render()` returns `f" {self.section_name}{dim_str}"` where `dim_str = f" [{', '.join(self.dimensions)}]"`. When the text exceeds the minimap column width (`max-width: 35`), Textual silently clips.

**Preferred fix:** Widen minimap to ~50 cols AND apply `text-overflow: ellipsis` so long dim lists show `…]` rather than mid-word cut. Re-measure with t571_5's plan (14 sections) as the stress-test fixture.

### 3. Enter on a minimap row should scroll WITHOUT animation

**Symptom:** Enter-scroll to a section animates — feels laggy for a nav action.

**Fix:** Change `scroll_to(y=y, animate=True)` → `animate=False` in:
- `.aitask-scripts/lib/section_viewer.py` — `SectionAwareMarkdown.scroll_to_section()` and `SectionViewerScreen.on_section_minimap_section_selected()`
- `.aitask-scripts/board/aitask_board.py` — `TaskDetailScreen.on_section_minimap_section_selected()`

Also update t571_8 and t571_9 pending plans so they pass `animate=False` when integrating.

### 4. Tab in fullscreen plan viewer dismisses the modal (BUG)

**Symptom:** Pressing Tab inside `SectionViewerScreen` closes the modal and returns to `TaskDetailScreen`. Per the t571_5 keyboard contract, Tab should cycle focus between `#sv_minimap` and `#sv_content`.

**Root-cause hypothesis:** `SectionViewerScreen.action_focus_minimap` raises `SkipAction` when the guard (`focused inside #sv_content`) fails. The binding is `priority=True`, so SkipAction lets Textual continue dispatch — it reaches `TaskDetailScreen.action_focus_minimap` (just added in t571_10), whose guard also fails, and a second SkipAction propagates up to Textual's default focus-cycling, which walks focus out of the modal and dismisses it.

**Preferred fix:** Remove the SkipAction path from `SectionViewerScreen.action_focus_minimap`. The modal has only two focusable panes (minimap and content); Tab should unconditionally toggle between them. Implement as: if focus is NOT on minimap → focus minimap; else focus content. No SkipAction — the modal owns Tab.

The SkipAction pattern was designed for embedded contexts (board's `TaskDetailScreen` form, codebrowser's `DetailPane`) where Tab must fall through to form/tree navigation. It does NOT apply to a dedicated modal with only two targets.

**Investigation step:** before coding the fix, reproduce with a headless Textual `Pilot` test to confirm the dispatch chain. Log `on_key` in both `SectionViewerScreen` and `TaskDetailScreen` to confirm the hypothesis.

<!-- /section: issues -->

<!-- section: files_to_modify [dimensions: deliverables] -->

## Key Files to Modify

- `.aitask-scripts/lib/section_viewer.py` — fixes 1, 2 (DEFAULT_CSS), 3 (animate), 4 (Tab action logic).
- `.aitask-scripts/board/aitask_board.py` — fix 3 (animate=False in `on_section_minimap_section_selected`).
- `aiplans/p571/p571_8_codebrowser_section_viewer_integration.md` — add `animate=False` note.
- `aiplans/p571/p571_9_brainstorm_node_detail_section_viewer_integration.md` — add `animate=False` note.

<!-- /section: files_to_modify -->

<!-- section: verification [dimensions: testing] -->

## Verification

1. `ait board` → task with sectioned plan → press `v` → inline minimap shows ALL rows (not just 1).
2. Press `V` → fullscreen → rows show full name + full dimension list, or clean `…]` ellipsis when truncated (no mid-word cut).
3. Enter on a row → content scrolls INSTANTLY to section, no animation.
4. Fullscreen: Tab → focus toggles between minimap and content; modal does NOT dismiss. Escape still dismisses.
5. Regression: inline minimap still renders on board; `v`/`V`/`p` bindings unchanged; Tab inside embedded `TaskDetailScreen` (when plan view NOT active) still cycles form fields.
6. Pilot/headless test the Tab behavior in `SectionViewerScreen` to prevent regression.

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->
