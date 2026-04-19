---
Task: t571_5_shared_section_viewer_tui_integration.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_6_update_brainstorm_design_docs.md, aitasks/t571/t571_7_manual_verification_structured_brainstorming.md
Archived Sibling Plans: aiplans/archived/p571/p571_1_section_parser_module.md, aiplans/archived/p571/p571_2_update_agent_templates_emit_sections.md, aiplans/archived/p571/p571_3_section_aware_operation_infrastructure.md, aiplans/archived/p571/p571_4_section_selection_brainstorm_tui_wizard.md
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-04-19 08:45
---

# Plan: t571_5 — Shared Section Viewer Module (Reduced Scope)

<!-- section: context [dimensions: motivation] -->

## Context

The ait brainstorming infrastructure supports "design dimension" DAG exploration. Task t571_1 delivered a section parser (`.aitask-scripts/brainstorm/brainstorm_sections.py`) that parses plans into `ContentSection`s tagged with dimensions. Plans now carry machine-readable structure, but the three TUIs that render plan/proposal markdown (codebrowser, brainstorm, board) still display it as one opaque blob with no section awareness.

The original t571_5 scope covered both the shared library module AND three TUI integrations. During verification the scope was assessed as too broad — each TUI has its own wiring, potential binding conflicts, and manual verification overhead, which is risky to bundle into a single task.

**Scope reduction:** t571_5 now delivers **only the shared section viewer library**. The three TUI integrations are split into new sibling tasks:
- **t571_8** — Codebrowser integration (detail pane minimap + full-screen plan viewer via `p`)
- **t571_9** — Brainstorm `NodeDetailModal` integration (minimaps in Proposal and Plan tabs)
- **t571_10** — Board `TaskDetailScreen` integration (minimap in plan view + full-screen via `shift+v`)

Each depends on t571_5 and can be picked independently once this task is done.

<!-- /section: context -->

<!-- section: verification_notes [dimensions: verify-path] -->

## Verification Notes (vs. original plan)

During verification against the current codebase (t571_1 already landed, t571_4 landed recently):
- `ContentSection` from `brainstorm_sections.py` exposes `.name`, `.dimensions: list[str]`, `.start_line: int` (1-based), `.end_line: int`, `.content: str` — minimap scroll-position math can rely on `.start_line`
- `brainstorm_app.py` already imports `parse_sections` at line 49 (unused so far) — t571_9 reuses it
- `lib/` currently has 7 `.py` files; there is **no `section_viewer.py`** yet
- `codebrowser_app.py:28` adds `parent.parent/"lib"` to sys.path but NOT `parent.parent`; `aitask_board.py:13` is the same. To spare each TUI from changing its sys.path setup, `section_viewer.py` self-inserts `parent.parent` so it can import from `brainstorm.brainstorm_sections` regardless of caller
- Reference focusable-row pattern: `.aitask-scripts/codebrowser/history_list.py` `HistoryTaskItem` (lines 85–147)
- Reference split-modal pattern: `.aitask-scripts/codebrowser/history_screen.py` BINDINGS at 52–70, `action_toggle_focus()` at 428–456

<!-- /section: verification_notes -->

<!-- section: files_to_modify [dimensions: deliverables] -->

## Files to Modify

- **CREATE** `.aitask-scripts/lib/section_viewer.py` — the only deliverable file for t571_5

<!-- /section: files_to_modify -->

<!-- section: reference_files [dimensions: patterns] -->

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_sections.py` — `parse_sections`, `ParsedContent`, `ContentSection`
- `.aitask-scripts/codebrowser/history_screen.py` — ModalScreen with horizontal split, focus toggle
- `.aitask-scripts/codebrowser/history_list.py` — focusable rows with `can_focus=True`, arrow-key nav via `on_key()`
- `.aitask-scripts/lib/tui_switcher.py` — lib-module pattern, sys.path self-insert at lines 33–36

<!-- /section: reference_files -->

<!-- section: keyboard_contract [dimensions: keybinding, focus-management, ux-contract] -->

## Keyboard Contract (enforced across ALL future integration points)

This contract is the public keyboard UX of the module. All three sibling tasks (t571_8, t571_9, t571_10) rely on it — the widgets must implement the minimap-side half, and each host TUI implements the content-side half.

| Key | When focus is on… | Effect |
|-----|-------------------|--------|
| `tab` | `SectionMinimap` (or any `SectionRow`) | Move focus to the **companion content widget** (host-provided) |
| `tab` | companion content widget | Host-side binding: move focus back to the `SectionMinimap`, landing on the last-highlighted `SectionRow` (or first row if none) |
| `up` / `down` | a `SectionRow` | Move focus to the previous / next `SectionRow` sibling (no content-pane scroll) |
| `enter` | a `SectionRow` | Emit `SectionRow.Selected(section_name)` — minimap rebroadcasts as `SectionMinimap.SectionSelected`; host scrolls content to that section |
| `escape` | `SectionViewerScreen` modal | Dismiss the full-screen viewer |

The minimap is fully self-contained for `tab`/`up`/`down`/`enter` behaviors. For the content→minimap direction of `tab`, hosts are expected to bind at their screen/modal level and route to `minimap.focus_first_row()` (a helper exposed by the module).

<!-- /section: keyboard_contract -->

<!-- section: module_imports [dimensions: widget-design, implementation] -->

## 1. Top of `.aitask-scripts/lib/section_viewer.py` — imports and sys.path

```python
import sys
from pathlib import Path
_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
from brainstorm.brainstorm_sections import parse_sections, ParsedContent, ContentSection

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Label, Markdown, Static
from textual.actions import SkipAction
```

<!-- /section: module_imports -->

<!-- section: section_row [dimensions: widget-design, keybinding] -->

## 2. `SectionRow(Static)` — focusable minimap row

- `__init__(name: str, dimensions: list[str], **kwargs)` stores `section_name` and `dimensions`, sets `can_focus = True`
- `render()` → `f" {self.section_name}{dim_str}"` where `dim_str = f" [{', '.join(self.dimensions)}]"` when non-empty
- Nested message: `class Selected(Message)` with `section_name: str`
- `on_click()` posts `Selected(self.section_name)`
- `on_key(event)` handles:
  - `enter` → post `Selected(self.section_name)`, `event.stop()`
  - `up` → focus previous sibling `SectionRow` via parent-children index-1 walk, `event.stop()` & `event.prevent_default()`
  - `down` → same with next sibling, same event handling
  - `tab` NOT handled here — allowed to bubble up to the `SectionMinimap`'s binding
- `DEFAULT_CSS = """SectionRow { height: 1; background: $surface; padding: 0 1; } SectionRow:focus { background: $accent; color: $text; }"""`

<!-- /section: section_row -->

<!-- section: section_minimap [dimensions: widget-design, focus-management, keybinding] -->

## 3. `SectionMinimap(VerticalScroll)` — container for rows

- `BINDINGS = [Binding("tab", "toggle_focus", "Content", show=True, priority=True)]`
- Nested messages:
  - `class SectionSelected(Message)` with `section_name: str`
  - `class ToggleFocus(Message)` — emitted when Tab is pressed; host should focus companion content
- `populate(parsed: ParsedContent)` → `self.remove_children()`; iterate `parsed.sections` and mount `SectionRow(s.name, s.dimensions)` each; initialize `self._last_focused_row_index = 0`
- `focus_first_row()` → if any rows exist, focus the one at `self._last_focused_row_index` (clamped to len-1), else no-op
- `on_descendant_focus(event)` → if `event.widget` is a `SectionRow`, update `self._last_focused_row_index` to its position
- `on_section_row_selected(event)` → post `SectionSelected(event.section_name)`; `event.stop()`
- `action_toggle_focus()` → post `ToggleFocus()`
- `DEFAULT_CSS = """SectionMinimap { max-width: 35; border-right: solid $primary; background: $panel; }"""`

<!-- /section: section_minimap -->

<!-- section: section_aware_markdown [dimensions: widget-design, scroll-estimation] -->

## 4. `SectionAwareMarkdown(VerticalScroll)` — markdown with scroll-to-section

- `compose()` → `yield Markdown(id="section_md")`
- Internal: `self._section_positions: dict[str, float] = {}` (ratio in [0,1])
- `update_content(text: str, parsed: ParsedContent | None = None)`:
  - `self.query_one("#section_md", Markdown).update(text)`
  - If `parsed`: compute `total_lines = text.count('\n') + 1`; for each section store `self._section_positions[s.name] = s.start_line / total_lines`
- `scroll_to_section(name: str)`:
  - If `name` in positions: `target_y = self._section_positions[name] * self.virtual_size.height`; `self.scroll_to(y=target_y, animate=True)`
- Module-level helper `estimate_section_y(parsed, name, total_lines, virtual_height) -> float | None` — exposed so hosts that wrap a plain `Markdown` (e.g. codebrowser `DetailPane`) can reuse the line-ratio math

<!-- /section: section_aware_markdown -->

<!-- section: section_viewer_screen [dimensions: widget-design, focus-management, keybinding] -->

## 5. `SectionViewerScreen(ModalScreen)` — full-screen split viewer

- `BINDINGS = [Binding("escape", "close", "Close"), Binding("tab", "focus_minimap", "Minimap", priority=True)]`
- `__init__(content: str, title: str = "Plan Viewer")` stores both
- `compose()`:
  ```python
  with Container(id="section_viewer"):
      yield Label(self._title, id="sv_title")
      with Horizontal(id="sv_split"):
          yield SectionMinimap(id="sv_minimap")
          yield SectionAwareMarkdown(id="sv_content")
  ```
- `on_mount()`:
  - `parsed = parse_sections(self._content)`
  - Populate minimap and markdown; if no sections, hide the minimap (`minimap.display = False`)
  - Initial focus: minimap if sections exist, else markdown
- `on_section_minimap_section_selected(event)` → `scroll_to_section` on the markdown; `event.stop()`
- `on_section_minimap_toggle_focus(event)` → focus `#sv_content`; `event.stop()`
- `action_focus_minimap()`:
  - Guard: check `self.screen.focused` is inside `#sv_content` (scope guards to `self.screen.query_one`, per the Textual priority-binding feedback memory); if not, `raise SkipAction()`
  - Else: call `self.query_one("#sv_minimap", SectionMinimap).focus_first_row()`
- `action_close()` → `self.dismiss()`
- CSS: `#section_viewer { width: 100%; height: 100%; } #sv_split { width: 100%; height: 1fr; }`

<!-- /section: section_viewer_screen -->

<!-- section: module_exports [dimensions: api-surface] -->

## 6. Module exports

```python
__all__ = [
    "SectionRow",
    "SectionMinimap",
    "SectionAwareMarkdown",
    "SectionViewerScreen",
    "estimate_section_y",
    "parse_sections",  # convenience re-export so hosts don't need two imports
    "ParsedContent",
    "ContentSection",
]
```

<!-- /section: module_exports -->

<!-- section: verification [dimensions: testing, dogfood] -->

## Verification

**Dogfood note:** this very plan file embeds `<!-- section: ... [dimensions: ...] -->` markers. The TUI integration tasks (t571_8/9/10) will use this plan (and the sibling plans, which also embed markers) as the test fixture to verify the minimap populates correctly with multiple dimensions.

1. **Parser test on this plan file:**
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.aitask-scripts')
   from brainstorm.brainstorm_sections import parse_sections
   with open('aiplans/p571/p571_5_shared_section_viewer_tui_integration.md') as f:
       parsed = parse_sections(f.read())
   assert len(parsed.sections) >= 10, f'expected >=10 sections, got {len(parsed.sections)}'
   names = [s.name for s in parsed.sections]
   assert 'keyboard_contract' in names, 'missing keyboard_contract section'
   print('OK:', names)
   "
   ```
2. **Import sanity:**
   ```bash
   python -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); from section_viewer import SectionMinimap, SectionAwareMarkdown, SectionViewerScreen, parse_sections; print('OK')"
   ```
3. **Headless Textual probe:** write a 30-line stand-alone Textual app in `/tmp/section_viewer_probe.py` that:
   - Loads the archived plan `aiplans/archived/p571/p571_1_section_parser_module.md` if it has markers, or synthesizes a plan with at least 4 sections across 3 different dimensions
   - Launches `SectionViewerScreen` as the root
   - On mount, asserts minimap row count matches section count
   - Driven programmatically (e.g. via Textual `Pilot`): press Tab → confirm focus leaves minimap; Tab again → focus returns; Up/Down → focus moves between rows; Enter → `SectionSelected` message observable via a hook
4. **No-sections fallback:** same probe with content lacking markers — minimap `display` is False; Escape still dismisses.
5. **Sibling-task readiness:** confirm `aitasks/t571/t571_8_*.md`, `t571_9_*.md`, `t571_10_*.md` exist with plans in `aiplans/p571/` that each embed `<!-- section: ... [dimensions: ...] -->` markers, so the user can open each integration-task plan in its respective TUI (once those tasks land) and see the minimap populated.

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push. After archival, hand off to sibling tasks t571_8 / t571_9 / t571_10 for TUI integration.

<!-- /section: post_implementation -->
