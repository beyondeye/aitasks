---
Task: t571_8_codebrowser_section_viewer_integration.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_5_*.md, aitasks/t571/t571_6_*.md, aitasks/t571/t571_7_*.md, aitasks/t571/t571_9_*.md, aitasks/t571/t571_10_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-04-19 13:27
---

# Plan: t571_8 — Codebrowser Section Viewer Integration

<!-- section: context [dimensions: motivation, integration] -->

## Context

Integrate the shared `.aitask-scripts/lib/section_viewer.py` module (from t571_5) into the **codebrowser** TUI. Two entry points for users:

1. **Detail pane minimap** — when the current annotation's plan has sections, a minimap appears above the existing `#detail_markdown`
2. **Full-screen plan viewer** — `p` key pushes a `SectionViewerScreen` with a split layout (minimap + markdown)

The plan for t571_5 itself carries section markers, so once this task lands the user can open any task annotated by t571_5 (or any of its siblings) in codebrowser and see a populated minimap.

**Depends on t571_5.** Do NOT start until `.aitask-scripts/lib/section_viewer.py` exists and exports `SectionMinimap`, `SectionViewerScreen`, `estimate_section_y`.

<!-- /section: context -->

<!-- section: files_and_lines [dimensions: deliverables] -->

## Files and Line References

- `.aitask-scripts/codebrowser/detail_pane.py` (99 lines today) — modify `update_content()` lines 53–83; widget IDs `#detail_header`, `#detail_markdown`, `#detail_placeholder`
- `.aitask-scripts/codebrowser/codebrowser_app.py` — add `Binding("p", "view_plan", ...)` to BINDINGS list (lines 235–252); existing sys.path insert at line 28 handles `lib/`
- `.aitask-scripts/codebrowser/annotation_data.py` — extend `TaskDetailContent` (lines 22–28) with `plan_sections: list | None = None`

<!-- /section: files_and_lines -->

<!-- section: detail_pane_changes [dimensions: integration, widget-design] -->

## 1. `detail_pane.py` — Mount minimap above markdown

Extend `DetailPane.update_content()`:

```python
def update_content(self, detail: TaskDetailContent | None) -> None:
    self._current_detail = detail  # NEW: expose on instance
    ...
    if content and detail and detail.has_plan:
        # IMPORTANT: import parse_sections from section_viewer (convenience re-export),
        # NOT from brainstorm.brainstorm_sections. The lib module self-inserts
        # `.aitask-scripts/` into sys.path on first import, so importing
        # `brainstorm.*` directly before `section_viewer` fails with ModuleNotFoundError.
        # See t571_10 Final Implementation Notes for the fix history.
        from section_viewer import SectionMinimap, parse_sections
        parsed = parse_sections(content)
        if parsed.sections:
            self._cached_parsed = parsed
            self._cached_plan_text = content
            # Ensure minimap exists before #detail_markdown
            if not self.query("#detail_minimap"):
                minimap = SectionMinimap(id="detail_minimap")
                self.mount(minimap, before="#detail_markdown")
            self.query_one("#detail_minimap", SectionMinimap).populate(parsed)
        else:
            for w in list(self.query("#detail_minimap")):
                w.remove()
```

Initialize `self._current_detail = None`, `self._cached_parsed = None`, `self._cached_plan_text = ""` in `__init__`.

<!-- /section: detail_pane_changes -->

<!-- section: scroll_handler [dimensions: integration, scroll-estimation] -->

## 2. `detail_pane.py` — Handle `SectionSelected` and `ToggleFocus`

```python
def on_section_minimap_section_selected(self, event) -> None:
    from section_viewer import estimate_section_y
    if self._cached_parsed is None:
        return
    total = self._cached_plan_text.count('\n') + 1
    y = estimate_section_y(
        self._cached_parsed, event.section_name, total, self.virtual_size.height)
    if y is not None:
        self.scroll_to(y=y, animate=False)  # nav, not animation — matches t571_11 fix; see section_viewer.py scroll_to_section
    event.stop()

def on_section_minimap_toggle_focus(self, event) -> None:
    self.query_one("#detail_markdown", Markdown).focus()
    event.stop()
```

<!-- /section: scroll_handler -->

<!-- section: focus_routing [dimensions: focus-management, keybinding] -->

## 3. `detail_pane.py` — Tab on markdown returns focus to minimap

Add screen-level Tab binding on `DetailPane`:

```python
BINDINGS = [Binding("tab", "focus_minimap", "Minimap")]

def action_focus_minimap(self) -> None:
    from textual.actions import SkipAction
    focused = self.screen.focused
    markdown = self.query_one("#detail_markdown", Markdown)
    if focused is not markdown:
        raise SkipAction()
    minimaps = self.query("#detail_minimap")
    if not minimaps:
        raise SkipAction()
    minimaps.first().focus_first_row()
```

Guard: only fires when `#detail_markdown` is focused AND `#detail_minimap` exists. Otherwise `SkipAction` lets Textual's default Tab-nav proceed (important because codebrowser has other focus targets).

<!-- /section: focus_routing -->

<!-- section: app_binding [dimensions: keybinding, integration] -->

## 4. `codebrowser_app.py` — `V` key opens `SectionViewerScreen`

**Cross-TUI alignment:** `V` (uppercase / `shift+v`) is the shared fullscreen-viewer key across board (t571_10), codebrowser (this task), and brainstorm (t571_9). See p571_10's "Cross-TUI Keybinding Alignment" section.

Add to BINDINGS list:
```python
Binding("V", "view_plan", "Fullscreen plan"),
```

Add method:
```python
def action_view_plan(self) -> None:
    detail_pane = self.query_one("#detail_pane", DetailPane)
    detail = getattr(detail_pane, "_current_detail", None)
    if detail and detail.has_plan and detail.plan_content:
        from section_viewer import SectionViewerScreen
        self.push_screen(SectionViewerScreen(
            detail.plan_content,
            title=f"Plan for t{detail.task_id}"))
    else:
        self.notify("No plan available for current task", severity="warning")
```

<!-- /section: app_binding -->

<!-- section: annotation_data_change [dimensions: data-model] -->

## 5. `annotation_data.py` — Add optional `plan_sections` field

```python
@dataclass
class TaskDetailContent:
    task_id: str
    plan_content: str = ""
    task_content: str = ""
    has_plan: bool = False
    has_task: bool = False
    plan_sections: list | None = None  # NEW — reserved for callers that want to avoid re-parsing
```

No behavioral change in this task — the field is added for future use. The detail pane currently re-parses plans itself.

<!-- /section: annotation_data_change -->

<!-- section: verification [dimensions: testing] -->

## Verification

Test against real fixture content in the repo:

1. `ait codebrowser` → navigate to `.aitask-scripts/lib/section_viewer.py` (created by t571_5). Its annotation references t571_5's plan, which has sections
2. Press `d` → detail pane shows with minimap. Rows = section names from the plan + their dimension tags
3. Tab → focus moves to plan markdown. Tab again → focus returns to the last-highlighted row in the minimap
4. Up/Down on minimap → focus cycles between rows without scrolling
5. Enter on a row → plan scrolls to that section
6. Press `V` (uppercase / `shift+v`) → `SectionViewerScreen` opens as a modal with left minimap + right markdown. Contract holds. Escape closes
7. Navigate to a file annotated by a task with NO section markers in its plan → detail pane renders without a minimap; Tab behavior falls through to Textual default
8. Press `V` when no plan is available → warning notification, no crash

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->

<!-- section: final_implementation_notes [dimensions: workflow, lessons] -->

## Final Implementation Notes

- **Actual work done:**
  - `annotation_data.py` — added `plan_sections: list | None = None` to `TaskDetailContent`.
  - `detail_pane.py` — added `SectionMinimap` mount/populate in `update_content()` via `_sync_minimap()`; `SectionSelected` handler uses `estimate_section_y` + `scroll_to(animate=False)`; `ToggleFocus` handler focuses `#detail_markdown`; `Tab → action_focus_minimap` binding with `SkipAction` guard; `show_multiple_tasks()` also clears minimap state to avoid stale UI.
  - `codebrowser_app.py` — added `V → action_view_plan` binding; `action_toggle_focus` emits `SkipAction` when focus is on `#detail_markdown` AND a `#detail_minimap` exists so DetailPane's own Tab binding can run (without this the App's `priority=True` Tab always wins).
- **Deviations from plan:**
  - **Scope extended to `history_detail.py`** after review feedback. The original plan only covered the main codebrowser detail pane, but the history screen uses a separate `HistoryDetailPane` widget. User reported no minimap and a misleading "No plan available" notification when testing from the history screen. Fixes:
    1. `HistoryDetailPane` now mounts `SectionMinimap(id="history_detail_minimap")` above the body markdown whenever `_showing_plan` is true and the plan has parsable sections. Toggles correctly on `v` (lowercase). Added `get_current_plan()` helper for external callers.
    2. `action_view_plan` detects the active screen: if `HistoryScreen` is active, it uses `HistoryDetailPane.get_current_plan()` instead of the main `DetailPane`.
    3. Replaced the single generic "No plan available" notification with three specific messages: "Toggle to plan view first" (history screen, not on plan), "No task selected" (main screen, no cursor annotation), "Task tN has no plan file" (main screen, task with no plan).
    4. Narrowed `except Exception` to `except NoMatches` in `action_view_plan` so import errors surface instead of being swallowed.
    5. Removed redundant uppercase `V → toggle_view` binding on `HistoryDetailPane` so V falls through to the fullscreen viewer (cross-TUI alignment).
- **Issues encountered:**
  - App-level `Binding("tab", ..., priority=True)` intercepts Tab before widget-level bindings on `DetailPane` can fire. Resolved by teaching `action_toggle_focus` to `SkipAction` when the markdown-with-minimap case applies.
  - `Markdown` widget is not focusable (`can_focus = False`), so Tab-from-markdown-to-minimap focus round-trip is visually a no-op. This is inherited from the t571_5 keyboard contract and documented here for siblings rather than fixed. Up/Down/Enter on minimap rows work independently.
  - Mount order gotcha in `HistoryDetailPane.action_toggle_view`: after toggling, the minimap is re-mounted while `_body_md` already exists, so we pass `before=self._body_md` to keep minimap above the body.
- **Key decisions:**
  - Lazy imports for `section_viewer` symbols (inside methods, not at module top) to keep diffs small and avoid import-order coupling at module-load time.
  - Kept the Tab binding on `DetailPane` (not on App) per the plan's keyboard contract, even though Markdown's non-focusability makes the binding effectively inactive today — it becomes live if Markdown gains focus in a future refactor.
  - Removed uppercase V from `HistoryDetailPane` rather than trying to chain behaviors, since `v`/`V` doing the same thing was an original redundancy and `V` now has a distinct cross-TUI meaning.
- **Notes for sibling tasks:**
  - **Import rule (inherited from p571_10):** always import `parse_sections` via `section_viewer` re-export, never directly from `brainstorm.brainstorm_sections`. The lib's sys.path self-insert is load-bearing.
  - **`animate=False` rule (inherited from p571_11):** all `scroll_to` calls driven by `SectionSelected` must pass `animate=False` — it's navigation, not UX animation.
  - **History-screen integration pattern** (new): sibling TUIs that host a secondary detail pane alongside a primary one should route fullscreen-viewer actions via active-screen detection, not blind queries of the primary pane ID. The `action_view_plan` routing pattern here is the reference.
  - **Notification discipline:** differentiated messages ("toggle first" vs "no task" vs "no plan file") prevent the "it failed, why?" UX trap. Siblings should enumerate failure modes before composing one generic warning.

<!-- /section: final_implementation_notes -->
