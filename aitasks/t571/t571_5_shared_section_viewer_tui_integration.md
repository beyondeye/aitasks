---
priority: high
effort: medium
depends: [1]
issue_type: refactor
status: Implementing
labels: [brainstorming, ait_brainstorm, ui, codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-16 12:00
updated_at: 2026-04-19 12:00
---

<!-- section: context [dimensions: motivation] -->

## Context

This is child task 5 of t571 (Structured Brainstorming Sections). It creates a shared, reusable section-aware viewer module in `.aitask-scripts/lib/`.

**Original scope** included integrating the module into three TUIs (codebrowser, brainstorm, board). **Reduced scope** (as of 2026-04-19): this task delivers only the **shared library module**. The three TUI integrations are split into new sibling tasks:

- **t571_8** — Codebrowser integration
- **t571_9** — Brainstorm `NodeDetailModal` integration
- **t571_10** — Board `TaskDetailScreen` integration

Each of the new siblings depends on t571_5 and can be picked independently once this task is done.

**Depends on**: t571_1 (section parser module)

<!-- /section: context -->

<!-- section: deliverables [dimensions: deliverables] -->

## Key File to Create

- **CREATE** `.aitask-scripts/lib/section_viewer.py` — shared module with reusable Textual widgets:
  - `SectionRow(Static)` — focusable minimap row
  - `SectionMinimap(VerticalScroll)` — container for rows with Tab-focus emission
  - `SectionAwareMarkdown(VerticalScroll)` — markdown with scroll-to-section
  - `SectionViewerScreen(ModalScreen)` — full-screen split viewer
  - Module-level helper `estimate_section_y()` for host integrations that wrap a plain `Markdown` widget

<!-- /section: deliverables -->

<!-- section: reference_files [dimensions: patterns] -->

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_sections.py` (t571_1) — `parse_sections()`, `ParsedContent`, `ContentSection`
- `.aitask-scripts/lib/tui_switcher.py` — lib-module pattern: reusable Textual widgets/mixins imported by multiple TUIs, sys.path self-insert pattern at lines 33–36
- `.aitask-scripts/codebrowser/history_screen.py` — `HistoryScreen` (ModalScreen) with horizontal split layout, focus switching via `action_toggle_focus()` at lines 428–456, escape-to-dismiss — architectural reference for `SectionViewerScreen`
- `.aitask-scripts/codebrowser/history_list.py` `HistoryTaskItem` at lines 85–147 — focusable rows with `can_focus=True` and `on_key()` for up/down — pattern for `SectionRow`

<!-- /section: reference_files -->

<!-- section: keyboard_contract [dimensions: keybinding, focus-management, ux-contract] -->

## Keyboard Contract (library-provided UX)

The library provides a consistent keyboard contract that all TUI integrations (t571_8/9/10) inherit:

| Key | Focus context | Effect |
|-----|---------------|--------|
| `tab` | `SectionMinimap`/`SectionRow` | Emit `ToggleFocus` message → host focuses companion content |
| `tab` | companion content | (Host responsibility) — focus returns to minimap's last-highlighted row |
| `up`/`down` | `SectionRow` | Move focus to prev/next sibling row |
| `enter` | `SectionRow` | Emit `SectionSelected` → host scrolls content |
| `escape` | `SectionViewerScreen` | Dismiss the modal |

<!-- /section: keyboard_contract -->

<!-- section: verification [dimensions: testing] -->

## Verification

See `aiplans/p571/p571_5_shared_section_viewer_tui_integration.md` for the full implementation plan and verification steps.

The plan itself embeds `<!-- section: ... [dimensions: ...] -->` markers throughout — acting as a dogfood test fixture for the TUI integration tasks to exercise the minimap/dimension rendering with real content.

<!-- /section: verification -->
