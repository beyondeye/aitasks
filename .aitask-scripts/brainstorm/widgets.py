"""Brainstorm TUI: non-modal Textual widgets."""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from pathlib import Path
from numbered_source_view import NumberedSourceView
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container,
    Horizontal,
    VerticalScroll,
)
from textual.widgets import (
    Checkbox,
    Input,
    Label,
    Static,
)
from textual.message import Message
from textual.reactive import reactive
from brainstorm.brainstorm_dag import (
    get_dimension_fields,
    read_node,
    read_proposal,
)
from brainstorm.brainstorm_schemas import group_dimensions_by_prefix
from brainstorm.brainstorm_sections import (
    dimension_matches_tag,
    parse_sections,
)
from brainstorm.brainstorm_dag_display import (
    OP_BADGE_STYLES,
    UNKNOWN_OP_STYLE,
)
from brainstorm.brainstorm_session import (
    crew_worktree,
    resolve_node_group,
)
from launch_modes import DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES
from agentcrew.agentcrew_utils import format_elapsed
from agentcrew.agentcrew_log_utils import format_log_size

from brainstorm.constants import (
    AGENT_STATUS_COLORS,
    _TERMINAL_AGENT_STATES,
)
from brainstorm.utils import (
    _filter_labels,
    _format_progress_bar,
    _next_checkbox_index,
    _read_groups,
)

class _PreviewMinimap:
    """Lazily-built SectionMinimap subclass for the config-step preview pane.

    Rebinds Tab / Shift+Tab to step the app-level preview focus ring
    (``BrainstormApp._cycle_preview_focus``: inputs → minimap → proposal
    markdown → wrap). SectionMinimap's stock ``tab → toggle_focus`` *priority*
    binding cannot simply be cleared (Textual merges BINDINGS across the MRO, so
    a ``BINDINGS = []`` subclass still inherits it), so we override it here with
    our own priority binding. Doing the focus move from a synchronous binding
    *action* (rather than a posted ToggleFocus message) is what makes the new
    focus stick.
    """

    _cache = None

    @classmethod
    def cls(cls):
        if cls._cache is None:
            from section_viewer import SectionMinimap as _Base

            class _PreviewMM(_Base):
                BINDINGS = [
                    Binding("tab", "preview_focus_advance", "Next", priority=True),
                    Binding(
                        "shift+tab", "preview_focus_retreat", "Prev", priority=True
                    ),
                ]

                def action_preview_focus_advance(self) -> None:
                    app = self.app
                    if hasattr(app, "_cycle_preview_focus"):
                        app._cycle_preview_focus(forward=True)

                def action_preview_focus_retreat(self) -> None:
                    app = self.app
                    if hasattr(app, "_cycle_preview_focus"):
                        app._cycle_preview_focus(forward=False)

            cls._cache = _PreviewMM
        return cls._cache


class _NumberedProposal(NumberedSourceView):
    """Scrollable source-line view: syntax-highlighted markdown + a line-number
    gutter.

    The alternate proposal rendering for the explore / module-decompose config
    preview (t954): the proposal source, **markdown-highlighted**, with a
    right-justified line-number gutter so the user can reference specific lines
    ("adapt around line 30").

    A thin adopter of :class:`NumberedSourceView` (t959 extracted the shared base
    that codebrowser's ``CodeViewer`` also uses). The base's defaults already
    match this view exactly — markdown lexer, always-wrap content column, one
    Rich ``Table`` row per source line so numbers track *source* lines across
    reflow, highlight cached once per :meth:`set_text` and only re-laid-out on
    resize — so this subclass only pins the styling and the inner ``Static`` id.

    Mounts only a ``Static`` (never a ``TextArea`` / ``CycleField`` / ``RadioSet``)
    so the recursive ``#actions_content`` collectors in ``_actions_collect_config``
    stay unambiguous — same constraint as :class:`ProposalPreviewPane`.
    """

    DEFAULT_CSS = """
    _NumberedProposal {
        height: 1fr;
        width: 1fr;
        padding: 0 1;
    }
    """

    _INNER_ID = "preview_numbered_inner"


class ProposalPreviewPane(Horizontal):
    """Reusable side-by-side proposal viewer: a fixed minimap pane beside a
    scrollable Markdown.

    Adopts ``SectionViewerScreen``'s layout (minimap left, content right) so the
    minimap stays visible while the proposal scrolls, and delegates
    section-navigation to ``SectionAwareMarkdown.request_scroll_to_section`` —
    which scrolls to the section's actual rendered heading (exact, no overshoot)
    rather than a line-ratio estimate. Built for the explore / module-decompose
    wizard config steps (t945), mounted via
    ``BrainstormApp._mount_config_with_preview``.

    The minimap (``_PreviewMinimap``) rebinds Tab / Shift+Tab to drive the
    app-level focus ring (``_cycle_preview_focus``), cycling inputs → minimap →
    proposal markdown. Inputs and the markdown pane are routed by the app's
    ``on_key``; the minimap's own priority Tab binding hands back to the same
    ring so focus never sticks on the minimap.

    IMPORTANT: the pane mounts only a minimap + a ``SectionAwareMarkdown`` —
    never a ``TextArea`` / ``CycleField`` / ``RadioSet``. The config-step
    collectors in ``_actions_collect_config`` query ``#actions_content``
    recursively with single-match ``query_one(TextArea)`` /
    ``query_one(CycleField)``; adding any such widget here would make those
    queries ambiguous.
    """

    DEFAULT_CSS = """
    ProposalPreviewPane {
        height: 1fr;
        border-left: solid $primary;
    }
    ProposalPreviewPane > .preview_proposal_minimap {
        width: 28;
        max-width: 28;
        height: 1fr;
        max-height: 100%;
    }
    ProposalPreviewPane > #preview_proposal_content {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }
    ProposalPreviewPane > #preview_proposal_numbered {
        width: 1fr;
        height: 1fr;
        display: none;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._parsed = None
        self._text = ""
        self._numbered = False

    def compose(self) -> ComposeResult:
        from section_viewer import SectionAwareMarkdown
        yield _PreviewMinimap.cls()(classes="preview_proposal_minimap")
        yield SectionAwareMarkdown(id="preview_proposal_content")
        yield _NumberedProposal(id="preview_proposal_numbered")

    def _content(self):
        from section_viewer import SectionAwareMarkdown
        return self.query_one("#preview_proposal_content", SectionAwareMarkdown)

    def _minimap(self):
        return self.query_one(".preview_proposal_minimap")

    def populate(self, proposal_text: str) -> None:
        """Render *proposal_text* and (re)build the section minimap."""
        text = proposal_text if proposal_text else "*No proposal found.*"
        self._text = text
        parsed = parse_sections(text)
        self._content().update_content(text, parsed)
        # Feed the alternate numbered view with the raw source (line N == source
        # line N). It stays hidden until toggled via ``toggle_numbered``.
        self._numbered_view().set_text(text)
        minimap = self._minimap()
        # populate() clears any stale rows and adds one per section (none when
        # there are no sections), so this also resets the minimap on re-populate.
        minimap.populate(parsed)
        if parsed.sections:
            self._parsed = parsed
            minimap.display = True
        else:
            self._parsed = None
            # No sections → hide the (now-empty) minimap so the proposal takes
            # the full pane width.
            minimap.display = False
        # populate() always lands in markdown (default) mode — each config step
        # builds a fresh pane, but reset explicitly so a re-populate is clean.
        self._numbered = False
        self._content().display = True
        self._numbered_view().display = False

    def _numbered_view(self) -> "_NumberedProposal":
        return self.query_one("#preview_proposal_numbered", _NumberedProposal)

    def toggle_numbered(self) -> bool:
        """Swap the content pane between Markdown and the numbered source view.

        Markdown mode shows the ``SectionAwareMarkdown`` (and the minimap when the
        proposal has sections); numbered mode shows the ``_NumberedProposal``
        gutter view and hides the minimap (line numbers, not sections, are the
        navigation aid there). Returns the new ``_numbered`` state.
        """
        self._numbered = not self._numbered
        md = self._content()
        num = self._numbered_view()
        minimap = self._minimap()
        if self._numbered:
            md.display = False
            minimap.display = False
            num.display = True
        else:
            num.display = False
            md.display = True
            # Restore the minimap only when the proposal actually has sections.
            minimap.display = self._parsed is not None
        return self._numbered

    def scroll_to_section(self, section_name: str) -> None:
        """Scroll the proposal so *section_name*'s heading sits at the top.

        Delegates to ``SectionAwareMarkdown.request_scroll_to_section``, which
        targets the section's actual rendered heading (exact, no overshoot)
        and defers until the markdown has finished its async render.
        """
        if self._parsed is None:
            return
        self._content().request_scroll_to_section(section_name)

    def on_ratio_change(self) -> None:
        """Keep the currently-top source line at the top across a width reflow.

        Operates on the inner ``SectionAwareMarkdown`` scroll (the markdown is
        what scrolls now that the minimap is a fixed sibling). Capture the top
        line *before* the width class swaps — ``scroll_offset.y`` still reflects
        the pre-reflow geometry — then re-apply after re-layout
        (``call_after_refresh``).
        """
        content = self._content()
        total = self._text.count("\n") + 1
        max_scroll = float(getattr(content, "max_scroll_y", 0) or 0)
        if total <= 0 or max_scroll <= 0:
            return
        top_line = round(content.scroll_offset.y / max_scroll * total)

        def _restore() -> None:
            new_max = float(getattr(content, "max_scroll_y", 0) or 0)
            if new_max <= 0:
                return
            content.scroll_to(y=(top_line / total) * new_max, animate=False)

        content.call_after_refresh(_restore)


class FuzzyCheckList(Container):
    """Filter box + scrolling multi-select checkbox list.

    A self-contained wizard control group: an `Input` fuzzy-filter box on top
    and a `VerticalScroll` of native `Checkbox` rows. Rows keep the
    caller-supplied CSS class, so existing `query("Checkbox.<class>")`-based
    collection code finds them unchanged.

    Filtering toggles `display` only. A checked row always stays visible —
    even when it does not match the current filter — so the active selection
    is never hidden; `.value` is preserved regardless. `↑`/`↓` move focus
    within this group (the filter box + visible rows); `Tab` group-switching
    is handled by the parent app.
    """

    def __init__(self, items, *, item_class: str, default_checked: bool = False,
                 placeholder: str = "Type to filter…", id: str | None = None):
        super().__init__(id=id)
        self._items = [str(it) for it in items]
        self._item_class = item_class
        self._default_checked = default_checked
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self._placeholder, classes="fcl_filter")
        with VerticalScroll(classes="fcl_list"):
            for label in self._items:
                yield Checkbox(label, value=self._default_checked,
                               classes=f"{self._item_class} fcl_item")

    def on_input_changed(self, event: Input.Changed) -> None:
        matched = set(_filter_labels(event.value, self._items))
        for cb in self.query(Checkbox):
            # A checked row stays visible even when it does not match the
            # filter, so the current selection is never hidden from view.
            cb.display = str(cb.label) in matched or bool(cb.value)
        focused = self.app.focused
        if isinstance(focused, Checkbox) and not focused.display:
            self.query_one(Input).focus()

    def on_key(self, event) -> None:
        if event.key in ("up", "down"):
            if self._navigate(1 if event.key == "down" else -1):
                event.prevent_default()
                event.stop()

    def _navigate(self, direction: int) -> bool:
        chain = [self.query_one(Input)]
        chain += [cb for cb in self.query(Checkbox) if cb.display]
        focused = self.app.focused
        current = chain.index(focused) if focused in chain else None
        new_idx = _next_checkbox_index(current, len(chain), direction)
        if new_idx is None:
            return True  # boundary: consume, no move
        chain[new_idx].focus()
        chain[new_idx].scroll_visible()
        return True

    def set_grouped_items(self, groups) -> None:
        """Replace rows with grouped, subheadered items.

        ``groups``: list of ``(subheader_text, [(label, checked), ...])``.
        Re-mounts the inner ``.fcl_list`` scroll with a non-focusable ``Static``
        subheader per group followed by its ``Checkbox`` rows, and resyncs
        ``self._items`` so the fuzzy filter stays correct. Safe to call
        repeatedly (e.g. on node-selection change), mirroring
        ``_refresh_compare_sections``'s remount. Subheaders are ``Static`` (not
        ``Checkbox``), so ``_navigate`` skips them and the filter leaves them
        visible.
        """
        try:
            listview = self.query_one(".fcl_list", VerticalScroll)
        except Exception:
            return
        listview.remove_children()
        items: list[str] = []
        for subheader, rows in groups:
            listview.mount(Static(
                f"[bold $accent]{subheader}[/]", classes="fcl_subheader"))
            for label, checked in rows:
                listview.mount(Checkbox(
                    label, value=checked,
                    classes=f"{self._item_class} fcl_item"))
                items.append(label)
        self._items = items


class NodeRow(Static):
    """Focusable row representing a brainstorm node in the dashboard list."""

    BINDINGS = [
        Binding("o", "open_operation", "Operation", show=True),
    ]

    # Space-marked state (t983_3): reflects membership in the Browse
    # NodeSelection.marked set. Reactive so toggling it re-renders the checkbox
    # glyph (☑/☐, shared with the graph-view DAG boxes — t1004).
    marked = reactive(False)

    class OperationOpened(Message):
        """Emitted when 'o' is pressed on a focused NodeRow."""

        def __init__(self, group_name: str) -> None:
            super().__init__()
            self.group_name = group_name

    def __init__(self, node_id: str, description: str, is_head: bool = False):
        super().__init__()
        self.node_id = node_id
        self.node_description = description
        self.is_head = is_head
        self.can_focus = True

    def render(self) -> str:
        head_marker = " [bold green]HEAD[/]" if self.is_head else ""
        mark = "[bold yellow]☑[/] " if self.marked else "[#6272A4]☐[/] "
        return (
            f"{mark}[bold]{self.node_id}[/]{head_marker}  "
            f"{self.node_description}"
        )

    def action_open_operation(self) -> None:
        """Post OperationOpened for this row's generating group (o key)."""
        session_path = getattr(self.app, "session_path", None)
        if session_path is None:
            return
        data = read_node(session_path, self.node_id)
        group = data.get("created_by_group", "")
        if not group:
            self.app.notify(
                "No group recorded for this node",
                severity="warning",
            )
            return
        # Apply the same defensive resolution used by the graph-tab
        # detail pane so the operation modal can open even when the
        # stored ``created_by_group`` is a pre-t792 drifted value
        # (e.g. ``op_explore_001``).
        groups = _read_groups(session_path)
        resolved_group, _ginfo = resolve_node_group(
            self.node_id, group, groups
        )
        self.post_message(self.OperationOpened(resolved_group))


class DimensionRow(Static):
    """Focusable row showing a stripped dimension suffix + value.

    Mounted by the dashboard right pane under the appropriate dimension-type
    subheader. Pressing Enter posts an :class:`Activated` message carrying the
    full prefixed dimension key (e.g. ``requirements_perf``) so the host can
    look up matching proposal sections via
    :func:`brainstorm.brainstorm_sections.get_sections_for_dimension`.
    """

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
    DimensionRow:focus:hover {
        background: $accent-lighten-1;
        color: $text;
    }
    """

    class Activated(Message):
        def __init__(self, dim_key: str) -> None:
            super().__init__()
            self.dim_key = dim_key

    def __init__(
        self, suffix: str, value: str, dim_key: str,
        section_count: int = 0, **kwargs,
    ):
        super().__init__(**kwargs)
        self.suffix = suffix
        self.value = value
        self.dim_key = dim_key
        self.section_count = section_count
        # When collapsed (default) the row is clipped to a single line by the
        # ``height: 1`` CSS; ``space`` toggles it to ``height: auto`` so the
        # full (often paragraph-length) value wraps and becomes readable.
        self.expanded = False

    def render(self) -> str:
        if self.section_count == 0:
            badge = "[dim][0 §][/]"
        else:
            badge = f"[bold cyan][{self.section_count} §][/]"
        caret = "[dim]▾[/]" if self.expanded else "[dim]▸[/]"
        return f"  {caret} {badge} [bold]{self.suffix}:[/] {self.value}"

    def on_click(self) -> None:
        self.focus()
        self.post_message(self.Activated(self.dim_key))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Activated(self.dim_key))
            event.stop()
        elif event.key == "space":
            # Toggle full-text expansion in place. The value is always present
            # in render(); only the row height gates how much is visible.
            self.expanded = not self.expanded
            self.styles.height = "auto" if self.expanded else 1
            self.refresh(layout=True)
            event.stop()


def render_node_detail_widgets(
    session_path: Path, node_id: str,
) -> tuple[str, list]:
    """Return (title_text, widgets) for the node-detail pane.

    Shared by the Dashboard, Graph, and NodeDetailModal node-detail views via
    :class:`NodeDetailPanel`. Widgets are unmounted instances ready for mount()
    into the caller's container.
    """
    try:
        node_data = read_node(session_path, node_id)
    except Exception:
        return (f"Node: {node_id}", [Static("(node not readable)")])

    desc = node_data.get("description", "")
    parents = node_data.get("parents", [])
    created = node_data.get("created_at", "")
    group = node_data.get("created_by_group", "")

    widgets: list = []
    widgets.append(Static(
        f"[bold $accent]Description:[/] {desc}", classes="meta_field"))
    widgets.append(Static(
        f"[bold $accent]Parents:[/] "
        f"{', '.join(parents) if parents else 'root'}",
        classes="meta_field"))
    widgets.append(Static(
        f"[bold $accent]Created:[/] {created}", classes="meta_field"))
    if group:
        groups = _read_groups(session_path)
        group, ginfo = resolve_node_group(node_id, group, groups)
        op = ginfo.get("operation", "?")
        agents = ginfo.get("agents") or []
        when = ginfo.get("created_at", "")

        op_style = OP_BADGE_STYLES.get(op, UNKNOWN_OP_STYLE)
        op_color = op_style.color
        color_hex = op_color.name if op_color else "#888"

        widgets.append(Static(
            f"[bold $accent]Generated by:[/] [{color_hex} bold]{op}[/]"
            f"  [dim](group {group})[/]",
            classes="meta_field"))
        if agents:
            widgets.append(Static(
                f"[bold $accent]Agents:[/] {', '.join(agents)}",
                classes="meta_field"))
        if when:
            widgets.append(Static(
                f"[bold $accent]When:[/] {when}",
                classes="meta_field"))
        widgets.append(Static(
            "[dim]Press 'o' for operation details[/]",
            classes="meta_field"))

    dims = get_dimension_fields(node_data)
    grouped = group_dimensions_by_prefix(dims)
    if grouped:
        section_counts: dict[str, int] = {}
        try:
            proposal = read_proposal(session_path, node_id)
            parsed_proposal = parse_sections(proposal)
            for sec in parsed_proposal.sections:
                # Expand each tag (exact or glob) against the node's real
                # dimension keys, counting each section once per real key.
                linked = {
                    k
                    for k in dims
                    for t in sec.dimensions
                    if dimension_matches_tag(k, t)
                }
                for k in linked:
                    section_counts[k] = section_counts.get(k, 0) + 1
        except Exception:
            pass

        widgets.append(Static(""))
        widgets.append(Static("[bold $accent]Dimensions:[/]"))
        widgets.append(Static(
            "[dim]space: expand/collapse · enter: jump to proposal[/]",
            classes="meta_field"))
        for _prefix, label, entries in grouped:
            widgets.append(Static(
                f"[bold $accent]{label}[/]", classes="dim_subheader"))
            for suffix, value, full_key in entries:
                widgets.append(DimensionRow(
                    suffix, str(value), full_key,
                    section_count=section_counts.get(full_key, 0),
                ))

    return (f"Node: {node_id}", widgets)


class NodeDetailPanel(Container):
    """Reusable node-detail pane: a title Label + a content Container, driven
    by the shared :func:`render_node_detail_widgets` renderer.

    Used by the Dashboard, Graph, and NodeDetailModal so all three node-detail
    views share one rendering. The title/content child IDs are supplied by the
    caller so existing CSS, keyboard navigation, and the dashboard "Task Brief"
    path keep targeting the same IDs after the extraction.
    """

    def __init__(
        self, session_path: Path, *, title_id: str, info_id: str, **kwargs,
    ):
        super().__init__(**kwargs)
        self._session_path = session_path
        self._title_id = title_id
        self._info_id = info_id

    def compose(self) -> ComposeResult:
        yield Label("", id=self._title_id)
        yield Container(id=self._info_id)

    def show_content(self, title_text: str, widgets: list) -> None:
        """Set the panel title and replace its content with ``widgets``.

        The public entry point for driving the pane: ``update`` uses it for the
        shared node-detail rendering, and the dashboard "Task Brief" toggle uses
        it to show arbitrary content without reaching into the panel internals.
        """
        self.query_one(f"#{self._title_id}", Label).update(title_text)
        container = self.query_one(f"#{self._info_id}", Container)
        container.remove_children()
        for w in widgets:
            container.mount(w)

    def update(self, node_id: str) -> None:
        """Render ``node_id`` into the panel via the shared renderer."""
        self.show_content(
            *render_node_detail_widgets(self._session_path, node_id))


class OperationRow(Static):
    """Focusable row representing an operation in the Actions wizard."""

    selected = reactive(False)

    class Activated(Message):
        """Emitted when an OperationRow is clicked (mouse activation)."""

        def __init__(self, row: OperationRow) -> None:
            super().__init__()
            self.row = row

    def __init__(self, op_key: str, label: str, description: str, disabled: bool = False):
        super().__init__()
        self.op_key = op_key
        self.op_label = label
        self.op_description = description
        self.op_disabled = disabled
        self.can_focus = not disabled

    def render(self) -> str:
        if self.op_disabled:
            return f"[dim strikethrough]{self.op_label}[/]  [dim]{self.op_description}[/]"
        marker = "[bold cyan]> [/]" if self.selected else "  "
        return f"{marker}[bold]{self.op_label}[/]  {self.op_description}"

    def on_click(self) -> None:
        """Focus and activate this row when clicked."""
        if not self.op_disabled:
            self.focus()
            self.post_message(self.Activated(self))


class CycleField(Static):
    """Minimal cycle widget for numeric option selection (left/right keys)."""

    def __init__(self, label: str, options: list[str], initial: str = "", *, id: str | None = None):
        super().__init__(id=id)
        self.label = label
        self.options = options
        self.current_index = options.index(initial) if initial in options else 0
        self.can_focus = True

    @property
    def current_value(self) -> str:
        return self.options[self.current_index]

    def render(self) -> str:
        parts = []
        for i, opt in enumerate(self.options):
            if i == self.current_index:
                parts.append(f"[bold reverse] {opt} [/]")
            else:
                parts.append(f" {opt} ")
        return f"  {self.label}:  [dim]\u25c0[/] {'|'.join(parts)} [dim]\u25b6[/]"

    def on_key(self, event) -> None:
        if event.key == "left":
            self.current_index = (self.current_index - 1) % len(self.options)
            self.refresh()
            event.prevent_default()
            event.stop()
        elif event.key == "right":
            self.current_index = (self.current_index + 1) % len(self.options)
            self.refresh()
            event.prevent_default()
            event.stop()


class GroupRow(Static, can_focus=True):
    """Expandable group row in the Status tab."""

    class ToggleRequested(Message):
        """Emitted when a GroupRow is double-clicked to expand/collapse it."""

        def __init__(self, group_name: str) -> None:
            super().__init__()
            self.group_name = group_name

    def __init__(
        self,
        name: str,
        info: dict,
        expanded: bool = False,
        aggregate_progress: int | None = None,
        has_failed_agent: bool = False,
        has_completed_agent: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.group_name = name
        self.group_info = info
        self.expanded = expanded
        self.aggregate_progress = aggregate_progress
        # Recovery-action eligibility, computed once at mount from the group's
        # on-disk agent statuses (t1018_2). `n` (re-run fresh) needs a failed
        # agent; `i` (retry-apply) needs a completed agent to re-ingest.
        self.has_failed_agent = has_failed_agent
        self.has_completed_agent = has_completed_agent

    def render(self) -> str:
        arrow = "\u25bc" if self.expanded else "\u25b6"
        op = self.group_info.get("operation", "?")
        status = self.group_info.get("status", "?")
        color = AGENT_STATUS_COLORS.get(status, "#888888")
        agents = self.group_info.get("agents", [])
        created = self.group_info.get("created_at", "")
        progress_str = ""
        # Hide the bar for already-Completed groups (would always read 100%)
        # and when no agent has progress > 0 yet.
        if status != "Completed" and self.aggregate_progress:
            bar = _format_progress_bar(self.aggregate_progress)
            if bar:
                progress_str = f"  {bar}"
        line = (
            f"{arrow} [bold]{self.group_name}[/bold]  {op}  "
            f"[{color}]{status}[/{color}]  agents: {len(agents)}"
            f"{progress_str}  {created}"
        )
        if self.has_focus:
            hints = []
            if self.has_failed_agent:
                hints.append("n: re-run fresh")
            if self.has_completed_agent and op in (
                "explore", "synthesize", "compare"
            ):
                hints.append("i: retry-apply")
            if self.has_completed_agent:
                hints.append("o: open output")
            if hints:
                line += "  [dim](" + " | ".join(hints) + ")[/dim]"
        return line

    def on_click(self, event) -> None:
        # Single-click focuses; double-click toggles expand/collapse (mirrors
        # Enter). Pattern from board/aitask_board.py TaskCard.on_click (t1018_3).
        self.focus()
        if event.chain == 2:
            self.post_message(self.ToggleRequested(self.group_name))

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()


class StatusLogRow(Static, can_focus=True):
    """Focusable row displaying an agent log file entry in the Status tab."""

    def __init__(self, log_info: dict, **kwargs):
        super().__init__(**kwargs)
        self.log_info = log_info

    def render(self) -> str:
        name = self.log_info["name"]
        size = format_log_size(self.log_info["size"])
        mtime = self.log_info["mtime_str"]
        return f"  {name}  [{size}]  Last updated: {mtime}"

    def on_click(self) -> None:
        self.focus()


class AgentStatusRow(Static, can_focus=True):
    """Focusable agent status row in the Status tab. Supports reset via 'w' key."""

    def __init__(self, name: str, status: str, display_line: str, crew_id: str, **kwargs):
        super().__init__(**kwargs)
        self.agent_name = name
        self.agent_status = status
        self.crew_id = crew_id
        self._display_line = display_line

    def render(self) -> str:
        line = self._display_line
        if self.has_focus:
            hints = []
            if self.agent_status == "Error":
                hints.append("w: reset")
                hints.append("R: retry")
            elif self.agent_status == "Waiting":
                hints.append("e: edit mode")
            if self.agent_status in _TERMINAL_AGENT_STATES:
                hints.append("x: cleanup")
            log_path = Path(crew_worktree(self.crew_id)) / f"{self.agent_name}_log.txt"
            if log_path.exists():
                hints.append("L: log")
            if hints:
                line += "  [dim](" + " | ".join(hints) + ")[/dim]"
        return line

    def on_click(self) -> None:
        self.focus()

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()


class ProcessRow(Static, can_focus=True):
    """Focusable process row in the Status tab. Supports p/k/K actions."""

    def __init__(self, proc_data: dict, crew_id: str, **kwargs):
        super().__init__(**kwargs)
        self.proc_data = proc_data
        self.crew_id = crew_id
        self.agent_name = proc_data["agent_name"]

    def render(self) -> str:
        d = self.proc_data
        alive = d.get("process_alive", False)
        status = d.get("status", "")

        if alive and status == "Running":
            dot = "[green]\u25cf[/]"
        elif status == "Paused":
            dot = "[yellow]\u25cf[/]"
        elif not alive:
            dot = "[red]\u25cf[/]"
        else:
            dot = "[dim]\u25cf[/]"

        pid_str = str(d.get("pid", "?"))
        wall = format_elapsed(d["wall_time"]) if d.get("wall_time") is not None else "?"
        cpu = f'{d["cpu_time"]:.1f}s' if d.get("cpu_time") is not None else "?"
        rss = f'{d["memory_rss_mb"]:.0f}MB' if d.get("memory_rss_mb") is not None else "?"
        hb = d.get("heartbeat_age", "?")

        line = f"{dot} {d['agent_name']}  PID:{pid_str}  Wall:{wall}  CPU:{cpu}  RSS:{rss}  HB:{hb}"
        if not alive:
            line += "  [red]DEAD[/]"
        if self.has_focus:
            keys = "p:pause  k:kill  K:hard kill" if alive else "x:cleanup"
            line += f"  [dim]({keys})[/dim]"
        return line

    def on_click(self) -> None:
        self.focus()

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()
