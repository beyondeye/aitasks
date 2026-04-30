---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [brainstorming, ait_brainstorm, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-30 10:33
updated_at: 2026-04-30 12:09
boardidx: 60
---

Polish the brainstorm TUI dashboard "init mode" detail pane (right pane of the
Dashboard tab when a node like `n000_init` is focused) and improve the inline
SectionMinimap UX.

## Current state

`brainstorm_app.py:_show_node_detail()` (~line 2380-2409) renders the right
pane via a single `Label#dash_node_info` whose body is plain `\n`-joined text:

```
Description: ...
Parents: ...
Created: ...
Group: ...

Dimensions:
  requirements_perf: ...
  assumption_concurrency: ...
  component_storage: ...
  ...
```

Issues:
- All metadata labels share the same flat default style — no visual hierarchy.
- Dimensions are printed in a flat list with the full prefix
  (`requirements_`, `assumption_`, `component_`, `tradeoff_`) duplicated on
  every line.
- Dimension lines are not focusable; pressing Enter does nothing.

The `SectionMinimap` from `lib/section_viewer.py` is mounted **inline** above
the Markdown in `NodeDetailModal.on_mount()` (`brainstorm_app.py:460-464`) and
in `codebrowser/detail_pane.py:108`. Minimap and content share the same
`VerticalScroll`, so after picking a section the user scrolls down through the
content and there is no shortcut to scroll back to the minimap (which lives
at the very top of the scroll container). The full-screen `SectionViewerScreen`
has the minimap on the side and is unaffected.

## Proposed changes

### 1. Restyle metadata labels in dashboard detail pane

In `brainstorm_app.py` `_show_node_detail()` and the surrounding CSS
(`#detail_pane`, ~line 1204-1222), give the metadata field labels
("Description:", "Parents:", "Created:", "Group:") a clear accent style
(e.g., bold + `$accent` color via Rich `[bold $accent]…[/]` markup) so they
stand out from the values. Same treatment for the "Dimensions:" header and
the new per-type subheaders introduced below.

### 2. Group dimensions by type and strip prefixes

Replace the flat plaintext block with a structured rendering:

- One subheader per dimension type that has at least one entry, in the order
  defined by `DIMENSION_PREFIXES` in `brainstorm/brainstorm_schemas.py`
  (`requirements_`, `assumption_`, `component_`, `tradeoff_`). Use the
  singular human label: "Requirements", "Assumptions", "Components",
  "Tradeoffs". Skip empty groups.
- Each entry in a group shows only the suffix — strip the type prefix
  (e.g., `requirements_perf` → `perf`).

This requires a small helper (e.g., `group_dimensions_by_prefix(dims) ->
dict[str, list[(suffix, value)]]`) likely living next to
`get_dimension_fields` in `brainstorm/brainstorm_dag.py` or
`brainstorm/brainstorm_schemas.py`.

### 3. Render each dimension as a focusable widget

Today `#dash_node_info` is a single `Label`. Replace its content rendering
with mounted child widgets inside the right pane's `VerticalScroll`:

- A new `DimensionRow(Static, can_focus=True)` widget that renders the
  suffix + value and accepts focus.
- On Enter, `DimensionRow` posts a message (e.g., `DimensionRow.Activated`)
  that the host (`BrainstormApp`) catches.
- Up/down arrow keys must navigate between `DimensionRow` widgets in the
  detail pane (mirroring `NodeRow` arrow-key handling at
  `brainstorm_app.py:1531-1537` — likely add a tab-keyed focus group or
  extend `_navigate_rows`).
- The dashboard's existing tab-bar Down behavior at line 1520 may need an
  update so focus can flow into the detail pane after the `NodeRow` list.

### 4. Enter on dimension → open proposal viewer at section(s)

When a `DimensionRow` is activated, look up the focused node's proposal
(`read_proposal(self.session_path, node_id)`) and call
`get_sections_for_dimension(parsed, dimension_key)` from
`brainstorm/brainstorm_sections.py` (already exists at line 170) to find
matching sections.

Behavior:
- 0 matches: notify("No proposal sections tagged with `<key>`",
  severity="warning").
- 1+ matches: push `SectionViewerScreen(content, title=...)` from
  `lib/section_viewer.py`, **with the minimap pre-filtered to only the
  matching sections**. The dimension key passed in must be the full prefixed
  key (`requirements_perf`), since that is what
  `<!-- section: foo [dimensions: requirements_perf] -->` markers use.

### 5. Filter SectionMinimap to a subset of sections

In `lib/section_viewer.py`:

- Extend `SectionMinimap.populate(parsed)` to accept an optional
  `names: list[str] | None` argument; when provided, only sections whose
  `.name` is in `names` (preserving original order) are mounted as rows.
- `SectionViewerScreen.__init__` should accept an optional
  `section_filter: list[str] | None = None`. When set, populate the minimap
  with the filter and ALSO clamp `scroll_to_section()` behavior so that
  navigation jumps within the original full markdown but is restricted to
  the filtered set when navigating via the minimap.

The full markdown content is still shown in full in `SectionAwareMarkdown`
— only the minimap row list is filtered (the user still sees the whole
document, but the minimap nav surface is scoped). Document this in the
class docstring.

### 6. Inline minimap: shortcut to jump back to the minimap

For inline-minimap hosts (`NodeDetailModal` in `brainstorm_app.py` and
`codebrowser/detail_pane.py`), the minimap and markdown share the same
`VerticalScroll`. Add a binding (suggested: `home`, with a fallback like
`m`) on `SectionAwareMarkdown` / on the host modal that scrolls the parent
`VerticalScroll` back to `y=0` (the top, where the minimap lives) and
focuses `SectionMinimap.focus_first_row()`.

The `SectionViewerScreen` (full-screen, side minimap) does NOT need this
binding — its minimap is always visible.

Footer hint: the binding should appear in the contextual footer when an
inline minimap is present. Use `show=True` on the binding for inline-minimap
hosts only (the side-minimap variant can `show=False` since the minimap is
already visible).

## Touchpoints summary

| File | Approx. site | Change |
|---|---|---|
| `brainstorm/brainstorm_app.py` | CSS @1209-1222, `_show_node_detail` @2380-2409 | Restyle, replace Label with mounted DimensionRow widgets, dispatch Enter |
| `brainstorm/brainstorm_app.py` | new `DimensionRow` class near `NodeRow` @772 | Focusable widget + Activated message |
| `brainstorm/brainstorm_app.py` | `on_key` @1509-1545 | Wire arrow-key navigation across DimensionRow |
| `brainstorm/brainstorm_schemas.py` or `brainstorm_dag.py` | next to `get_dimension_fields` | Add `group_dimensions_by_prefix` helper |
| `lib/section_viewer.py` | `SectionMinimap.populate` @203, `SectionViewerScreen.__init__` @313, on_mount @325 | `names` filter + `section_filter` ctor arg |
| `lib/section_viewer.py` | `SectionAwareMarkdown` or `SectionViewerScreen` BINDINGS | (only relevant for inline hosts) helper to scroll-to-top + focus minimap |
| `brainstorm/brainstorm_app.py` `NodeDetailModal` | @380-548 | Add a binding (e.g., `home`) that scrolls #proposal_scroll/#plan_scroll to y=0 and focuses the inline minimap |
| `codebrowser/detail_pane.py` | @108-122 | Same scroll-to-minimap binding for the codebrowser inline minimap |

## Out of scope

- The structured-sections refactor itself (`t571_more_structured_brainstorming_created_plan.md`) is a separate parent task; this task assumes the existing `parse_sections` infrastructure and only adds UI on top of it.
- DiffViewer and other inline-minimap surfaces beyond NodeDetailModal and codebrowser detail pane are not required (mention only — do not modify unless equivalent inline minimap exists there).

## Acceptance

- Dashboard right pane: focused node shows metadata labels with accent styling; dimensions shown in grouped sections with prefix stripped.
- Up/Down navigates DimensionRows in the dashboard right pane; Enter on a DimensionRow opens `SectionViewerScreen` with the minimap filtered to matching sections (or notifies "No matching sections" when none).
- In `NodeDetailModal` Proposal/Plan tabs and codebrowser detail pane, a documented binding scrolls the inline scroll container back to the top and focuses the minimap.
- Existing tests for SectionMinimap / NodeDetailModal continue to pass; new behavior covered by unit-style tests where feasible (`tests/test_brainstorm_*.py`).
