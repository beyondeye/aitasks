# Plan: Fix preview pane width issue in monitor TUI (t491)

## Context

The monitor TUI live preview pane shows fewer characters per line than the original tmux pane, causing formatting issues. Root causes: padding steals width, border changes on focus add side borders, VerticalScroll doesn't support horizontal scrolling, and content renders without wrap control.

## Changes (single file: `.aitask-scripts/monitor/monitor_app.py`)

### 1. Add imports
- `ScrollableContainer` from textual.containers
- `Text` from rich.text

### 2. CSS fixes
- `#content-section`: Keep `border-top: solid` only; zone-active changes color, not border geometry
- New `#preview-scroll`: `height: 1fr; max-height: 22`
- `PreviewPane`: Remove `padding: 0 1`, keep `max-height: 22`

### 3. Restructure compose
- Replace `VerticalScroll(header, preview)` with `Container(header, ScrollableContainer(preview))`
- Header stays outside scroll area; ScrollableContainer enables H+V scrolling

### 4. Content update (`_update_content_preview`)
- Use `Text(no_wrap=True)` instead of plain string
- Set `preview.styles.min_width = snap.pane.width` dynamically
- Reset min_width when no pane selected

### 5. Size cycling (`action_cycle_preview_size`)
- Apply max_height to both `#preview-scroll` and `#content-preview`

## Verification
1. Preview matches original pane formatting (no line wrapping)
2. Focus/unfocus doesn't change content width
3. Size cycling (z key) works
4. Keystroke forwarding in PREVIEW zone works
5. Horizontal scrollbar appears when source pane is wider than monitor

## Final Implementation Notes
- **Actual work done:** All 5 planned changes implemented as designed — imports, CSS, compose restructure, content update with Rich Text no_wrap, and size cycling update.
- **Deviations from plan:** None. Plan was refined during review (removed ellipsis overflow, kept max-height on PreviewPane, removed side borders entirely instead of making them consistent, dropped width:auto).
- **Issues encountered:** None — all changes applied cleanly with no syntax or import issues.
- **Key decisions:** Used `border-top` only (no side borders) to signal focus via color change + existing LIVE indicator + background highlight, maximizing horizontal space for content.
