---
Task: t721_brainstorm_dashboard_init_view_dimension_ui_and_inline_minim.md
Worktree: (current branch — no worktree per `fast` profile)
Branch: main
Base branch: main
---

# Plan — t721 Brainstorm dashboard init-view, dimension UI, inline minimap polish

## Context

The brainstorm TUI Dashboard tab's right pane (init-mode detail) renders node
metadata as flat plain text in a single `Label#dash_node_info`, with no visual
hierarchy and dimensions printed with their full prefix repeated on every
line. Dimensions are not focusable, so Enter does nothing. Separately, the
*inline* `SectionMinimap` mounted above plan/proposal Markdown shares a
`VerticalScroll` with the markdown, and once the user scrolls down through
content there is no shortcut back to the minimap. This plan addresses both
papercuts in the dashboard init view and adds a navigable
dimension→sections jump for proposal exploration.

Out of scope (explicit per task): the structured-sections refactor itself
(t571 family), DiffViewer, codebrowser/history_detail, and board minimap
hosts. Only `NodeDetailModal` and `codebrowser/detail_pane.DetailPane` get
the scroll-to-minimap binding.

## Files to change

| File | Change |
|---|---|
| `.aitask-scripts/brainstorm/brainstorm_schemas.py` | Add `PREFIX_TO_LABEL` map and `group_dimensions_by_prefix()` helper |
| `.aitask-scripts/brainstorm/brainstorm_app.py` | New `DimensionRow` widget; restyle metadata; rewrite `_show_node_detail`/`_show_brief_in_detail` to mount widgets; arrow-nav for `DimensionRow`; Enter handler → `SectionViewerScreen`; track current dashboard node; `home`/`m` binding on `NodeDetailModal` |
| `.aitask-scripts/lib/section_viewer.py` | `SectionMinimap.populate(parsed, names=None)`; `SectionViewerScreen(..., section_filter=None)`; small `_filter_sections()` helper for unit-test surface |
| `.aitask-scripts/codebrowser/detail_pane.py` | Add `home`/`m` binding scrolling self to top + focusing `#detail_minimap` |
| `tests/test_brainstorm_schemas.py` *(new)* | Unit tests for `group_dimensions_by_prefix` |
| `tests/test_section_viewer_filter.py` *(new)* | Unit tests for the `_filter_sections` helper backing the `names=` filter |

## Step 1 — Schema helper (`brainstorm_schemas.py`)

Add next to `DIMENSION_PREFIXES`:

```python
PREFIX_TO_LABEL = {
    "requirements_": "Requirements",
    "assumption_":   "Assumptions",
    "component_":    "Components",
    "tradeoff_":     "Tradeoffs",
}


def group_dimensions_by_prefix(
    dims: dict,
) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """Group dimension fields by their type prefix, in DIMENSION_PREFIXES order.

    Returns a list of (prefix, human_label, entries). Each entry is
    (suffix, value, full_key). Empty prefixes are omitted entirely.
    Items not matching any known prefix are silently dropped (callers are
    expected to pass already-validated dimension dicts via
    `extract_dimensions` / `get_dimension_fields`).
    """
    groups = []
    for prefix in DIMENSION_PREFIXES:
        entries = [
            (k[len(prefix):], v, k)
            for k, v in dims.items()
            if k.startswith(prefix)
        ]
        if entries:
            groups.append((prefix, PREFIX_TO_LABEL[prefix], entries))
    return groups
```

Why this signature: keeps the full key (`requirements_perf`) available so
the dimension-row Enter handler can pass it verbatim to
`get_sections_for_dimension(parsed, full_key)`, which expects the prefixed
form (per `<!-- section: foo [dimensions: requirements_perf] -->` markers).

## Step 2 — Dimension row widget (`brainstorm_app.py`, near line 772)

Add a focusable `DimensionRow` next to `NodeRow`:

```python
class DimensionRow(Static):
    """Focusable row showing a stripped dimension suffix + value."""

    can_focus = True

    DEFAULT_CSS = """
    DimensionRow {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    DimensionRow:focus {
        background: $accent;
        color: $text;
    }
    DimensionRow:hover {
        background: $surface-lighten-1;
    }
    """

    class Activated(Message):
        def __init__(self, dim_key: str) -> None:
            super().__init__()
            self.dim_key = dim_key

    def __init__(self, suffix: str, value: str, dim_key: str, **kwargs):
        super().__init__(**kwargs)
        self.suffix = suffix
        self.value = value
        self.dim_key = dim_key

    def render(self) -> str:
        return f"  [bold]{self.suffix}:[/] {self.value}"

    def on_click(self) -> None:
        self.focus()
        self.post_message(self.Activated(self.dim_key))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Activated(self.dim_key))
            event.stop()
```

## Step 3 — Restructure detail pane to host mounted children

`compose()` (~line 1483-1489) — replace the `Label#dash_node_info` with a
plain `Container#dash_node_info` (it remains a child of the detail-pane
`VerticalScroll`):

```python
yield VerticalScroll(
    Label("Session Status", id="session_status_title"),
    Label("Loading...",     id="session_status_info"),
    Label("",               id="dash_node_title"),
    Container(id="dash_node_info"),  # NEW: dynamic content target
    id="detail_pane",
)
```

CSS additions (~line 1218 area):

```css
#dash_node_info { height: auto; padding: 0; }
.meta_field { padding: 0 0; }
.dim_subheader { padding: 0 1; margin-top: 1; }
```

Existing `#dash_node_title` already gets `text-style: bold`; metadata
labels and the new dim subheaders gain markup-driven accent emphasis.

Add an `import` for `Container` (already imported on line 18) — confirm
the line `from textual.containers import Container, Horizontal,
VerticalScroll` is unchanged.

## Step 4 — Rewrite `_show_node_detail` (~line 2380-2409)

```python
def _show_node_detail(self, node_id: str) -> None:
    try:
        node_data = read_node(self.session_path, node_id)
    except Exception:
        return

    self._current_dashboard_node_id = node_id  # NEW: remember for Enter

    desc    = node_data.get("description", "")
    parents = node_data.get("parents", [])
    created = node_data.get("created_at", "")
    group   = node_data.get("created_by_group", "")

    self.query_one("#dash_node_title", Label).update(f"Node: {node_id}")

    container = self.query_one("#dash_node_info", Container)
    container.remove_children()

    container.mount(Static(
        f"[bold $accent]Description:[/] {desc}", classes="meta_field"))
    container.mount(Static(
        f"[bold $accent]Parents:[/] {', '.join(parents) if parents else 'root'}",
        classes="meta_field"))
    container.mount(Static(
        f"[bold $accent]Created:[/] {created}", classes="meta_field"))
    if group:
        container.mount(Static(
            f"[bold $accent]Group:[/] {group}", classes="meta_field"))

    dims = get_dimension_fields(node_data)
    grouped = group_dimensions_by_prefix(dims)
    if grouped:
        container.mount(Static(""))
        container.mount(Static("[bold $accent]Dimensions:[/]"))
        for _prefix, label, entries in grouped:
            container.mount(Static(
                f"[bold $accent]{label}[/]", classes="dim_subheader"))
            for suffix, value, full_key in entries:
                container.mount(DimensionRow(suffix, value, full_key))
```

`_show_brief_in_detail` (~line 2411-2420) — same container clear/mount:

```python
def _show_brief_in_detail(self, spec: str) -> None:
    self.query_one("#dash_node_title", Label).update("Task Brief")
    self._current_dashboard_node_id = None  # NEW
    container = self.query_one("#dash_node_info", Container)
    container.remove_children()
    lines = spec.splitlines()
    preview = "\n".join(lines[:30]) + (
        "\n\n… (truncated — see n000_init proposal for full text)"
        if len(lines) > 30 else ""
    )
    container.mount(Static(preview))
```

Add `self._current_dashboard_node_id: str | None = None` in
`BrainstormApp.__init__` (or first-touch initializer near other instance
state), and import `group_dimensions_by_prefix` alongside the existing
`extract_dimensions` import:

```python
from brainstorm.brainstorm_schemas import extract_dimensions, group_dimensions_by_prefix
```

## Step 5 — Arrow navigation across `DimensionRow`

Relax `_navigate_rows` (line 1841) to accept any container widget:

```python
container = self.query_one(f"#{container_id}")
```

(Drop the `, VerticalScroll` type filter — the method already only relies
on `.children`.)

Extend the dashboard arrow-key block (line 1531-1537):

```python
if event.key in ("up", "down") and tabbed.active == "tab_dashboard":
    direction = 1 if event.key == "down" else -1
    focused = self.focused
    if isinstance(focused, DimensionRow):
        if self._navigate_rows(direction, "dash_node_info", (DimensionRow,)):
            event.prevent_default(); event.stop(); return
    elif self._navigate_rows(direction, "node_list_pane", (NodeRow,)):
        event.prevent_default(); event.stop(); return
```

This means: while focus is on a `NodeRow`, ↑/↓ navigate the node list; once
focus is in the detail pane (`DimensionRow`), ↑/↓ navigate dimensions only.
We do NOT auto-overflow from the last NodeRow into the first DimensionRow —
the user moves focus between panes via Tab (Textual default) or by clicking
a dimension row. This keeps two list models cleanly separate; each pane's
↑/↓ stays local.

The tab-bar `down` block (line 1520-1529) is left as-is: pressing Down on
the tab bar focuses the first NodeRow. (No mapping to `DimensionRow` —
those only matter once a node is focused.)

## Step 6 — Enter-on-dimension dispatch (`brainstorm_app.py`)

Add a message handler on `BrainstormApp`:

```python
def on_dimension_row_activated(self, event: "DimensionRow.Activated") -> None:
    node_id = self._current_dashboard_node_id
    if not node_id:
        return
    try:
        proposal = read_proposal(self.session_path, node_id)
    except Exception:
        self.notify("Could not read proposal for this node",
                    severity="warning")
        return
    parsed = parse_sections(proposal)
    matching = get_sections_for_dimension(parsed, event.dim_key)
    if not matching:
        self.notify(
            f"No proposal sections tagged with `{event.dim_key}`",
            severity="warning")
        return
    from section_viewer import SectionViewerScreen
    self.push_screen(SectionViewerScreen(
        proposal,
        title=f"Proposal: {node_id} — {event.dim_key}",
        section_filter=[s.name for s in matching],
    ))
```

Add the import `from brainstorm.brainstorm_sections import (
get_sections_for_dimension, parse_sections,)` — `parse_sections` is already
imported (line 51); add `get_sections_for_dimension` to that import line.

## Step 7 — `SectionMinimap.populate(names=...)` filter

In `lib/section_viewer.py`:

1. Add a tiny pure helper (top-level, makes filter logic unit-testable
   without Textual mounting):

```python
def _filter_sections(
    parsed: ParsedContent, names: list[str] | None
) -> list[ContentSection]:
    """Return sections from *parsed* preserving original order, optionally
    restricted to ``names`` (set membership)."""
    if names is None:
        return list(parsed.sections)
    name_set = set(names)
    return [s for s in parsed.sections if s.name in name_set]
```

2. Update `SectionMinimap.populate` (line 203):

```python
def populate(
    self, parsed: ParsedContent, names: list[str] | None = None,
) -> None:
    """Replace all rows with one per section in *parsed*.

    If *names* is provided, only sections whose name is in that list are
    mounted (preserving original parse order).
    """
    self.remove_children()
    for section in _filter_sections(parsed, names):
        self.mount(SectionRow(
            section.name, section.dimensions, compact=self._compact))
    self._last_focused_row_index = 0
```

3. `SectionViewerScreen.__init__` (line 313) and `on_mount` (line 325):

```python
def __init__(
    self, content: str, title: str = "Plan Viewer",
    section_filter: list[str] | None = None,
) -> None:
    super().__init__()
    self._content = content
    self._title = title
    self._section_filter = section_filter

def on_mount(self) -> None:
    parsed = parse_sections(self._content)
    minimap = self.query_one("#sv_minimap", SectionMinimap)
    content = self.query_one("#sv_content", SectionAwareMarkdown)
    content.update_content(self._content, parsed)
    if parsed.sections:
        minimap.populate(parsed, names=self._section_filter)
        minimap.focus_first_row()
    else:
        minimap.display = False
        content.focus()
```

Update the `SectionViewerScreen` class docstring to note: when
`section_filter` is set, the **minimap row list** is filtered while the
full markdown body remains intact in `SectionAwareMarkdown`. Navigation
via the minimap is naturally restricted to the filtered set (since only
those rows exist); the underlying `scroll_to_section()` lookup table
(`_section_positions`) is unchanged and can still resolve any section
name in the document — no explicit clamp needed because the minimap
itself is the only producer of `SectionSelected` messages.

Add `_filter_sections` to `__all__`.

## Step 8 — Inline minimap "scroll-to-top" binding

### 8a — `NodeDetailModal` (brainstorm_app.py ~line 378-548)

Extend `BINDINGS`:

```python
BINDINGS = [
    Binding("escape", "close", "Close", show=False),
    Binding("tab",    "focus_minimap", "Minimap"),
    Binding("V",      "fullscreen_plan", "Fullscreen plan"),
    Binding("home",   "scroll_to_minimap", "Top",  show=True),
    Binding("m",      "scroll_to_minimap", None,   show=False),
]

def action_scroll_to_minimap(self) -> None:
    tabbed = self.query_one(TabbedContent)
    if tabbed.active == "tab_proposal":
        scroll_id, mm_id = "#proposal_scroll", "#proposal_minimap"
    elif tabbed.active == "tab_plan":
        scroll_id, mm_id = "#plan_scroll", "#plan_minimap"
    else:
        return
    try:
        scroll = self.query_one(scroll_id, VerticalScroll)
    except Exception:
        return
    scroll.scroll_to(y=0, animate=False)
    minimaps = self.query(mm_id)
    if minimaps:
        minimaps.first().focus_first_row()
```

The Metadata tab has no inline minimap, so the action no-ops there.
`home` is bound at the modal level so it intercepts before the focused
Markdown's default `home` (scroll-home) — when there is no minimap to
focus, the call still scrolls the relevant scroll to the top, matching
user expectation.

### 8b — `codebrowser/detail_pane.py` `DetailPane`

```python
BINDINGS = [
    Binding("tab",  "focus_minimap", "Minimap"),
    Binding("home", "scroll_to_minimap_top", "Top",  show=True),
    Binding("m",    "scroll_to_minimap_top", None,   show=False),
]

def action_scroll_to_minimap_top(self) -> None:
    self.scroll_to(y=0, animate=False)
    minimaps = self.query("#detail_minimap")
    if minimaps:
        minimaps.first().focus_first_row()
```

(Distinct action name from the modal version to avoid any priority-binding
ambiguity per CLAUDE.md TUI conventions.)

## Step 9 — Tests

### `tests/test_brainstorm_schemas.py` (new)

```python
from brainstorm.brainstorm_schemas import (
    DIMENSION_PREFIXES, PREFIX_TO_LABEL, group_dimensions_by_prefix,
)

class GroupDimensionsTests(unittest.TestCase):
    def test_groups_in_prefix_order_and_strips_prefix(self):
        dims = {
            "tradeoff_cost": "low",
            "requirements_perf": "fast",
            "assumption_concurrency": "single",
            "component_storage": "sqlite",
            "requirements_security": "tls",
        }
        out = group_dimensions_by_prefix(dims)
        labels = [g[1] for g in out]
        self.assertEqual(labels, ["Requirements", "Assumptions", "Components", "Tradeoffs"])
        req_entries = out[0][2]
        self.assertEqual(
            sorted([(s, v, k) for s, v, k in req_entries]),
            sorted([("perf", "fast", "requirements_perf"),
                    ("security", "tls", "requirements_security")]),
        )

    def test_empty_groups_omitted(self):
        out = group_dimensions_by_prefix({"requirements_x": "y"})
        self.assertEqual([g[0] for g in out], ["requirements_"])

    def test_empty_input(self):
        self.assertEqual(group_dimensions_by_prefix({}), [])

    def test_unknown_prefix_dropped(self):
        # extract_dimensions guarantees only known prefixes, but defensive:
        out = group_dimensions_by_prefix({"weird_x": 1, "requirements_a": 2})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][2][0], ("a", 2, "requirements_a"))
```

### `tests/test_section_viewer_filter.py` (new)

```python
from section_viewer import _filter_sections, parse_sections

class FilterSectionsTests(unittest.TestCase):
    SAMPLE = (
        "<!-- section: a [dimensions: requirements_perf] -->\nA\n"
        "<!-- /section: a -->\n"
        "<!-- section: b [dimensions: assumption_x] -->\nB\n"
        "<!-- /section: b -->\n"
        "<!-- section: c [dimensions: requirements_perf] -->\nC\n"
        "<!-- /section: c -->\n"
    )

    def test_no_filter_returns_all(self):
        parsed = parse_sections(self.SAMPLE)
        out = _filter_sections(parsed, None)
        self.assertEqual([s.name for s in out], ["a", "b", "c"])

    def test_filter_preserves_parse_order(self):
        parsed = parse_sections(self.SAMPLE)
        out = _filter_sections(parsed, ["c", "a"])
        self.assertEqual([s.name for s in out], ["a", "c"])  # parse order, not arg order

    def test_unknown_names_silently_skipped(self):
        parsed = parse_sections(self.SAMPLE)
        out = _filter_sections(parsed, ["zzz"])
        self.assertEqual(out, [])
```

Run:
```bash
bash tests/test_brainstorm_schemas.py 2>/dev/null || \
  python tests/test_brainstorm_schemas.py
python -m unittest tests.test_brainstorm_schemas tests.test_section_viewer_filter
python -m unittest tests.test_brainstorm_sections tests.test_brainstorm_init_failure_modal
```

(Existing tests for sections and the InitFailureModal are the smoke
suite — they must keep passing.)

## Verification

Manual / TUI behaviors (cannot be unit-tested at the framework level —
flag for `/aitask-qa` follow-up if needed):

1. Launch a brainstorm session that already has a node with at least one
   dimension per prefix (e.g. an existing session under
   `~/.aitask-data/brainstorm/`).
2. Open Dashboard tab. Focus a `NodeRow` — the right pane shows metadata
   labels in accent style, then a `Dimensions:` header, then per-type
   subheaders ("Requirements", "Assumptions", "Components", "Tradeoffs"),
   then suffix-only entries with focus-able rows.
3. Tab into the detail pane (or click a dimension). Use ↑/↓ — focus
   moves only among `DimensionRow` widgets. Press Enter on a dimension
   that matches a proposal section → `SectionViewerScreen` pushes with the
   minimap pre-filtered to those sections. The full proposal markdown is
   still scrollable on the right.
4. Press Enter on a dimension with no matching section → toast
   "No proposal sections tagged with `requirements_perf`".
5. Open `NodeDetailModal` (Enter on a NodeRow). On Proposal/Plan tab,
   scroll down through markdown, then press `home` (or `m`) → scroll
   returns to top and the inline minimap regains focus.
6. In codebrowser (`ait codebrowser`), navigate to an annotated line with
   a structured plan, press `home` (or `m`) on the detail pane → top of
   pane + minimap focused.
7. Confirm DiffViewer and other inline-minimap surfaces are untouched
   (no regression from `populate(parsed, names=None)` — default arg
   matches previous behavior).

## Step 10 — Post-implementation (Step 9 of task-workflow)

- Commit code changes with `enhancement: ... (t721)` subject.
- Commit plan file under `aiplans/p721_*.md` via `./ait git`.
- Run archival via `./.aitask-scripts/aitask_archive.sh 721`.
- Push.

## Post-Review Changes

### Change Request 1 (2026-04-30 14:00)
- **Requested by user:**
  1. When the filtered SectionViewerScreen opens (via Enter on a
     dimension row), automatically scroll the markdown to the first
     section in the filtered minimap — currently the user has to press
     Enter on a minimap row to land at the relevant content.
  2. Tab should toggle focus between the Dashboard's left pane (NodeRow
     list) and right pane (DimensionRow list).
  3. Each `DimensionRow` should display a count of proposal sections
     that reference that dimension key (visual indicator).
- **Changes made:**
  1. `SectionViewerScreen.on_mount` (lib/section_viewer.py): when a
     `section_filter` is set, call
     `content.scroll_to_section(first_filtered.name)` via
     `call_after_refresh()` so the markdown jumps to the first filtered
     section once layout has settled.
  2. `BrainstormApp.on_key` handles `tab` and `shift+tab` on the
     Dashboard tab via a new `_dashboard_toggle_pane_focus()` helper.
     From a `NodeRow`, Tab focuses the first `DimensionRow` (no-op if
     the right pane has no dimensions). From a `DimensionRow`, Tab
     returns to the currently-displayed node's row in the left pane
     (or the first `NodeRow` if not found).
  3. `DimensionRow.__init__` accepts `section_count: int = 0` and
     `render()` appends `[N §]` (cyan) or `[0 §]` (dim) at the end of
     the row. `_show_node_detail` parses the focused node's proposal,
     counts sections per dimension key, and passes the count when
     mounting each `DimensionRow`. Failure to read the proposal is
     caught silently — rows render with count 0 (the dim visual
     treatment accurately conveys "no sections" to the user).
- **Files affected:**
  - `.aitask-scripts/lib/section_viewer.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`

### Change Request 2 (2026-04-30 14:30)
- **Requested by user:**
  1. The `[N §]` section-count badge on each `DimensionRow` should be at
     the START of the row, not the end.
  2. Auto-scroll on filtered SectionViewerScreen open is not working —
     the markdown does not actually move to the first filtered section.
  3. When selecting a section in the (full-screen) proposal viewer the
     markdown scrolls "several lines down more than it should" — as if
     the inline minimap height were being added even though we are in
     the side-minimap full-screen variant.
- **Changes made:**
  1. `DimensionRow.render()` — badge now precedes the suffix:
     `  [N §] suffix: value`. Cyan for >0, dim for 0.
  2. `SectionViewerScreen.on_mount` — replaced `call_after_refresh`
     with `set_timer(0.15, ...)`. `Markdown.update()` parses async, so
     `virtual_size` only stabilizes after several refreshes; the small
     timer waits past parsing before scrolling.
  3. `SectionAwareMarkdown.scroll_to_section` — switched from
     `ratio * virtual_size.height` to `ratio * max_scroll_y`. The old
     formula over-shoots by approximately `viewport_height * ratio`
     because `virtual_size.height` is the total content height while
     `max_scroll_y` is the scrollable distance. Falls back to a
     manually-computed `max(0, virtual_size.height - size.height)` when
     `max_scroll_y` is unavailable.
- **Files affected:**
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/lib/section_viewer.py`

### Change Request 3 (2026-04-30 14:50)
- **Requested by user:** Auto-scroll on filtered SectionViewerScreen
  open is still not working with the 0.15s `set_timer`.
- **Changes made:** Replaced the single-shot `set_timer(0.15, ...)` with
  a polling `set_interval(0.1, _poll_auto_scroll)` on
  `SectionViewerScreen`. The poll fires every 100ms and only triggers
  the scroll once `content.virtual_size.height > content.size.height`
  (i.e., the Markdown has rendered enough content to actually be
  scrollable). Bails out after ~2s (20 attempts) and stops the timer.
  Root cause: `Markdown.update()` returns an unawaited
  `AwaitComplete` — parsing happens in a worker after `on_mount`
  returns, so any fixed-delay scroll attempt is racing the renderer.
  Polling on `virtual_size.height` is the right termination condition.
- **Files affected:**
  - `.aitask-scripts/lib/section_viewer.py`

## Final Implementation Notes

- **Actual work done:**
  - `brainstorm_schemas.py` — Added `PREFIX_TO_LABEL` and
    `group_dimensions_by_prefix()` helper.
  - `brainstorm_app.py` — Added `DimensionRow(Static)` with
    `Activated` message; replaced `Label#dash_node_info` with
    `Container#dash_node_info` and dynamically-mounted Static
    metadata + per-prefix subheaders + focusable `DimensionRow`s
    (with leading `[N §]` proposal-section-count badge); added
    `_dashboard_toggle_pane_focus()` for Tab/Shift+Tab between left
    NodeRow list and right DimensionRow list; relaxed
    `_navigate_rows` container type so Container works alongside
    VerticalScroll; added `on_dimension_row_activated` to push
    `SectionViewerScreen` filtered to matching proposal sections;
    added `home`/`m` priority binding on `NodeDetailModal` to
    scroll active tab to top + focus inline minimap.
  - `lib/section_viewer.py` — Added `_filter_sections` pure
    helper; extended `SectionMinimap.populate(parsed, names=None)`;
    extended `SectionViewerScreen(__init__, on_mount)` with
    `section_filter` arg and polling auto-scroll on open;
    rewrote `SectionAwareMarkdown.scroll_to_section` to use
    `max_scroll_y` instead of `virtual_size.height`.
  - `codebrowser/detail_pane.py` — Added `home`/`m` priority
    binding scrolling self to top + focusing `#detail_minimap`.
  - `tests/test_brainstorm_schemas.py` (new, 5 tests) — covers
    `group_dimensions_by_prefix`.
  - `tests/test_section_viewer_filter.py` (new, 5 tests) — covers
    `_filter_sections`.
- **Deviations from plan:** The original plan deferred any
  changes to the existing `scroll_to_section` math, but Change
  Request 2 surfaced an over-scroll bug that pre-existed this task
  (visible whenever a section row was selected from the minimap in
  the full-screen viewer). Fixed in `lib/section_viewer.py` —
  simple two-line change, kept in scope because it became part of
  the user's review feedback.
- **Issues encountered:**
  - Auto-scroll on SectionViewerScreen open did not work with
    `call_after_refresh` or `set_timer(0.15)` — `Markdown.update()`
    parses in an unawaited worker, so `virtual_size.height` is 0
    until the next several refresh cycles. Resolved by polling
    `virtual_size.height > size.height` every 100ms (timeout 2s).
  - `SectionAwareMarkdown.scroll_to_section` over-scrolled by
    `viewport_height * ratio` because it multiplied the source-line
    ratio by the *total* virtual height instead of `max_scroll_y`
    (the scrollable distance). Fixed.
  - `_navigate_rows` was typed to `VerticalScroll` and would have
    failed silently when called with the new `Container#dash_node_info`.
    Type filter relaxed.
- **Key decisions:**
  - Used a `Container` (not `VerticalScroll`) for `dash_node_info`
    to avoid nested scroll containers — the parent `#detail_pane`
    already provides scrolling.
  - Tab between panes is implemented as a binary toggle (no
    overflow from arrow nav) to keep two list models cleanly
    separate. `_dashboard_toggle_pane_focus` returns `False` when
    the target pane has no rows so default Textual focus
    traversal can take over.
  - Section count badge placed at the START of each `DimensionRow`
    (per user request) with cyan styling for non-zero counts and
    dim styling for zero — visually flags dimensions with no
    matching proposal sections.
  - The polling-with-timeout pattern in
    `SectionViewerScreen._poll_auto_scroll` is preferable to a
    single longer fixed delay: it fires as soon as the Markdown is
    actually ready (no wasted wait) and gives up gracefully if the
    document never grows past the viewport (no infinite loop).
  - `home`/`m` bindings use `priority=True` on both
    `NodeDetailModal` and `DetailPane` so they intercept before the
    focused Markdown widget's default `home` (scroll-home) binding
    fires.
- **Upstream defects identified:** None.

  Separately (NOT a code defect — flagged by the user during
  review as a data observation worth investigating in a follow-up
  on brainstorm session 635): many dimensions in that session have
  zero matching proposal sections. The new section-count badge now
  surfaces this clearly. Whether it indicates a brainstorm crew
  bug (sections not tagged with the right dimension keys) or
  intentional data shape requires session-specific investigation —
  not in scope for this task and not a script-level defect.
