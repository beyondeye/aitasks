---
Task: t571_5_shared_section_viewer_tui_integration.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_1_*.md, aitasks/t571/t571_2_*.md, aitasks/t571/t571_3_*.md, aitasks/t571/t571_4_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_5 — Shared Section Viewer + TUI Integration

## Overview

Create a shared Textual widget module in `.aitask-scripts/lib/section_viewer.py` with reusable section-aware viewer components, then integrate into all three TUIs: codebrowser (enhanced detail pane + full-screen viewer), brainstorm (NodeDetailModal), and board (TaskDetailScreen).

## Part 1: Shared Module

### Step 1: Create `.aitask-scripts/lib/section_viewer.py`

#### 1.1 `SectionRow(Static)` — Individual minimap row

Focusable static widget displaying one section name with dimension tags.
- Emits `SectionRow.Selected(section_name)` on click or Enter
- Render: `section_name [dim1, dim2]` with dim tags in a muted color
- CSS: height 1, horizontal padding 1, highlight on focus

#### 1.2 `SectionMinimap(VerticalScroll)` — Minimap container

Manages a list of `SectionRow` widgets.
- `populate(parsed: ParsedContent)` — clear children, mount rows for each section
- Bubbles `SectionRow.Selected` up as `SectionMinimap.SectionSelected(section_name)`
- CSS: max-width 35, border-right, surface background

#### 1.3 `SectionAwareMarkdown(VerticalScroll)` — Scrollable markdown with section nav

Wraps a `Markdown` widget.
- `update_content(text, parsed=None)` — update markdown, compute section scroll positions
- `scroll_to_section(name)` — scroll to estimated Y position based on line ratios
- Section position estimation: `section.start_line / total_lines * virtual_size.height`

#### 1.4 `SectionViewerScreen(ModalScreen)` — Full-screen modal

Split layout: `SectionMinimap` on left, `SectionAwareMarkdown` on right.
- Constructor: `(content: str, title: str = "Plan Viewer")`
- On mount: parse content, populate minimap, set markdown
- Handle `SectionMinimap.SectionSelected` → scroll right pane
- Bindings: Escape to dismiss, Tab to switch focus between panes
- CSS: full screen, horizontal split layout

### Step 2: Imports

The module imports `parse_sections` from `brainstorm.brainstorm_sections`. Set up sys.path:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from brainstorm.brainstorm_sections import parse_sections, ParsedContent
```

## Part 2: Codebrowser Integration

### Step 3: Enhanced DetailPane

**File:** `.aitask-scripts/codebrowser/detail_pane.py`

In `update_content()`, after setting markdown content:
- Import and parse: `from brainstorm.brainstorm_sections import parse_sections`
- If sections exist, mount/update a `SectionMinimap` widget (id `detail_minimap`) above `#detail_markdown`
- Handle `SectionMinimap.SectionSelected` → approximate scroll the markdown widget
- If no sections, hide/remove the minimap

Add sys.path inserts for lib and brainstorm modules (follow existing pattern in `codebrowser_app.py` line 28).

### Step 4: Plan Viewer Keybinding

**File:** `.aitask-scripts/codebrowser/codebrowser_app.py`

- Add `Binding("p", "view_plan", "Plan viewer")` to BINDINGS
- Add `action_view_plan()`:
  ```python
  def action_view_plan(self) -> None:
      if self._current_detail and self._current_detail.has_plan:
          from section_viewer import SectionViewerScreen
          self.push_screen(SectionViewerScreen(
              self._current_detail.plan_content,
              title=f"Plan for t{self._current_detail.task_id}"))
      else:
          self.notify("No plan available", severity="warning")
  ```
- Add sys.path insert for lib/ directory

### Step 5: TaskDetailContent Extension

**File:** `.aitask-scripts/codebrowser/annotation_data.py`

Add field to `TaskDetailContent`:
```python
plan_sections: list | None = None
```

## Part 3: Brainstorm TUI Integration

### Step 6: NodeDetailModal Enhancement

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py` (NodeDetailModal, line 233)

In `on_mount()`:
- After loading proposal content (~line 305): parse sections, if present, mount `SectionMinimap` in the proposal tab above the `Markdown` widget
- After loading plan content (~line 311): same treatment for plan tab
- Handle `SectionMinimap.SectionSelected` → scroll the corresponding `VerticalScroll` container

Add imports for `SectionMinimap` from `section_viewer` and `parse_sections` from `brainstorm_sections`.

## Part 4: Board TUI Integration

### Step 7: TaskDetailScreen Enhancement

**File:** `.aitask-scripts/board/aitask_board.py` (TaskDetailScreen, line 1895)

In `_toggle_plan_view()` (~line 2186), when showing plan content:
- Parse sections from the plan content
- If sections present, mount/update a `SectionMinimap` in the `#md_view` container above the Markdown widget
- Handle `SectionMinimap.SectionSelected` → scroll to section

When toggling back to task view, hide/remove the minimap.

Optional: add a keybinding (e.g., `F` for fullscreen) to open `SectionViewerScreen` for the current plan.

Add sys.path inserts for lib/ and brainstorm modules.

## Verification

1. **Codebrowser detail pane**: Navigate to annotated file, verify minimap appears for sectioned plans
2. **Codebrowser minimap click**: Click section → plan scrolls to section
3. **Codebrowser full viewer**: Press `p` → split-layout modal with minimap + content
4. **Codebrowser no sections**: Plan without sections → no minimap, normal rendering
5. **Brainstorm NodeDetailModal**: View node with sectioned proposal/plan → minimap in tabs
6. **Board TaskDetailScreen**: Toggle to plan view → minimap appears for sectioned plans
7. **Graceful fallback**: All integrations work normally without sections
8. **Import test**: All three TUIs can import `section_viewer` without errors

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for archival and cleanup.
