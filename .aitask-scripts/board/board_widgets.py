"""Board-generic widgets and render helpers (t1794_2).

Extracted verbatim from ``aitask_board.py`` so that code which renders task
cards — the By-Trail view and the stand-alone trails app — can reuse them
without importing the Kanban app (parent plan t1794, contract C1).
``aitask_board.py`` re-exports every name, so ``ab.TaskCard`` /
``ab._status_badge_text`` keep resolving; inside this module the helpers call
each other through THIS namespace, so a stub must target ``board_widgets``,
not the board.

Contracts (see ``board/__init__.py`` and the parent plan):

* C1 — imported by bare name; imports no board module and adds nothing to
  ``sys.path``: every importer (``aitask_board.py``, the fixture harness, the
  tests) has already put ``.aitask-scripts/lib`` there.
* C2 — resolves no task directory, neither at import nor at runtime. Nothing
  here reads a path; ``TaskCard`` renders the ``Task`` and manager it is handed.

The widgets' CSS stays with the App that hosts them (``KanbanApp.CSS``); a
second App that mounts these widgets must carry the same rules.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Protocol

from rich.text import Text
from textual.app import ComposeResult
from textual.color import Color as TextualColor, ColorParseError
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Label, LoadingIndicator, Static

from followup_kinds import marker_for
from mark_glyphs import mark_markup
from topic_semantics import parse_task_filename


# --- Host surfaces (documentation; asserted in tests/test_board_widgets.py) ---


class CardHost(Protocol):
    """The App surface ``TaskCard`` reads through ``self.app``.

    ``KanbanApp`` is the reference host. ``marked`` is read only behind
    ``self.markable`` (``_is_marked``), and only a Kanban-column parent card is
    constructed markable; ``action_toggle_children`` is reached only from
    ``TaskCard.on_click``, which the trail cards override. A host that mounts
    only non-markable cards overriding ``on_click`` therefore never touches
    those two — but it must still answer the rest.
    """

    marked: MarkedSelection
    expanded_tasks: set

    def check_action(self, action: str, parameters: tuple) -> bool | None: ...

    def action_toggle_children(self) -> None: ...

    def action_view_details(self) -> None: ...


class ColumnHeaderHost(Protocol):
    """The App surface the column-header buttons call through ``self.app``."""

    def toggle_column_collapse(self, col_id: str) -> None: ...

    def open_column_edit(self, col_id: str) -> None: ...


# --- Card badges ---


def _issue_indicator(url: str) -> str:
    """Return a short colored indicator based on issue URL platform."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if "github" in host:
        return "[blue]GH[/blue]"
    elif "gitlab" in host:
        return "[#e24329]GL[/]"
    elif "bitbucket" in host:
        return "[blue]BB[/blue]"
    return "[blue]Issue[/blue]"


def _pr_indicator(url: str) -> str:
    """Return a short colored indicator based on pull request URL platform."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if "github" in host:
        return "[green]PR:GH[/green]"
    elif "gitlab" in host:
        return "[#e24329]MR:GL[/]"
    elif "bitbucket" in host:
        return "[blue]PR:BB[/blue]"
    return "[green]PR[/green]"


# --- Column header ---


class CollapseToggleButton(Static):
    """A small button to toggle column collapse/expand."""

    can_focus = False

    def __init__(self, col_id: str, is_collapsed: bool):
        indicator = "\u25b6" if is_collapsed else "\u25bc"  # ▶ or ▼
        super().__init__(indicator, classes="col-header-btn")
        self.col_id = col_id

    def on_click(self, event):
        event.stop()
        self.app.toggle_column_collapse(self.col_id)


class ColumnEditButton(Static):
    """A small button to open the column edit dialog."""

    can_focus = False

    def __init__(self, col_id: str):
        super().__init__("\u270e", classes="col-header-edit-btn")  # ✎
        self.col_id = col_id

    def on_click(self, event):
        event.stop()
        self.app.open_column_edit(self.col_id)


class ColumnHeader(Static):
    """A composite column header with title, collapse toggle, and edit button."""

    def __init__(self, col_id: str, title: str, task_count: int, is_collapsed: bool, editable: bool = True):
        super().__init__()
        self.col_id = col_id
        self.col_title = title
        self.task_count = task_count
        self.is_collapsed = is_collapsed
        self.editable = editable

    def compose(self):
        if self.is_collapsed:
            yield Label(self.col_title, classes="col-header-title")
            yield Label(f"({self.task_count})", classes="col-header-count")
            yield CollapseToggleButton(self.col_id, is_collapsed=True)
        else:
            with Horizontal(classes="col-header-row"):
                yield CollapseToggleButton(self.col_id, is_collapsed=False)
                yield Label(f"{self.col_title} ({self.task_count})", classes="col-header-title-expanded")
                if self.editable:
                    yield ColumnEditButton(self.col_id)


# --- Multi-select marking (t1243_6) ---
# The glyph and its colours are owned by lib/mark_glyphs.py (t1638) —
# aitask_board.py re-exports MARK_CHECKED/MARK_UNCHECKED for callers and tests,
# and TaskCard below renders via mark_markup() so the colour travels with the
# glyph. Do NOT restate either here: four independent copies of this pair is
# what t1638 was fixing, and tests/test_mark_glyphs_single_source.py now fails
# on a re-fork.
#
# The mark keeps meaning "selected for this action", the sense
# monitor/monitor_shared.py records. Rendered as a CSS-classed Label because that
# is how .task-number / .task-modified already work in the same title row — but
# the class carries LAYOUT and STATE only, never the colour; see `.task-mark` in
# KanbanApp.CSS.


class MarkedSelection:
    """Board multi-select state: the set of marked task filenames.

    Mirrors ``brainstorm/utils.py::NodeSelection``'s documented rule —
    SINGLE-item operations act on the cursor, MULTI-item operations act on the
    marked set. The board already *has* a cursor (the focused ``TaskCard``), so
    this holds only the marked set and :meth:`effective` takes the cursor as an
    argument.

    Keyed by ``Task.filename``, the board's durable card identity — the same key
    ``expanded_tasks`` and ``_refocus_card`` already use. A filename key is what
    survives the widget churn that ``_transplant_block``, ``_recompose_column``
    and ``refresh_board`` inflict on card objects: a transplanted card is a NEW
    widget, so per-widget mark state would be destroyed.
    """

    def __init__(self, marked=None):
        self.marked: set = set(marked) if marked else set()

    def __contains__(self, filename) -> bool:
        return filename in self.marked

    def __len__(self) -> int:
        return len(self.marked)

    def toggle(self, filename) -> bool:
        """Flip ``filename``; return its NEW marked state."""
        if filename in self.marked:
            self.marked.discard(filename)
            return False
        self.marked.add(filename)
        return True

    def clear(self) -> None:
        self.marked.clear()

    def retain(self, filenames) -> set:
        """Drop every mark not in ``filenames``; return the dropped set.

        Returns *which* marks were dropped rather than a bare count so the
        caller can report them. ``refresh_board`` uses it to survive a task
        archived by another session without discarding the rest of the
        selection — and to tell the user it happened, since an unattended
        auto-refresh must never silently shrink a selection.
        """
        keep = set(filenames)
        dropped = self.marked - keep
        self.marked &= keep
        return dropped

    @property
    def cardinality(self) -> int:
        return len(self.marked)

    def effective(self, focused_filename=None) -> list:
        """Targets an operation runs on: the marked set, else the focused card.

        Sorted for determinism. Callers needing *board* order (t1243_7's
        ``move_tasks_to_column`` preserves input order) must re-sort by
        ``(board_col, board_idx)`` themselves — this class knows nothing about
        board geometry.
        """
        if self.marked:
            return sorted(self.marked)
        return [focused_filename] if focused_filename else []


# --- Task card ---


class TaskCard(Static):
    """A widget representing a single task."""

    def __init__(self, task: Task, manager: "TaskManager" = None, is_child: bool = False,
                 column_id: str = "", markable: bool = False):
        super().__init__()
        self.task_data = task
        self.manager = manager
        self.is_child = is_child
        self.column_id = column_id
        self.can_focus = True
        # Whether `space` can mark this card (t1243_6). A constructor flag, not a
        # runtime lookup, so the exclusions are structural: only
        # KanbanColumn.task_block passes True, and only for the parent card.
        # `markable` is last with a default precisely so InFlightTaskCard,
        # TrailTaskCard and TrailGhostCard stay non-markable without edits.
        self.markable = markable
        if markable:
            # The hover rules in KanbanApp.CSS select `.markable-card`, not the
            # `TaskCard` type — a Textual type selector matches the whole MRO and
            # would restyle the In-Flight / By-Trail cards too. Set only when
            # True so every other card kind stays class-free.
            self.add_class("markable-card")

    # Shared with lib/topic_semantics.py (t1210_2) — same parser everywhere.
    _parse_filename = staticmethod(parse_task_filename)

    def _is_marked(self) -> bool:
        """Live read of the app's marked set — never a build-time freeze.

        `compose` derives the glyph from app state on every (re)build, so a card
        remounted by `_transplant_block` / `_recompose_column` / `refresh_board`
        paints the correct glyph for free. `KanbanApp._repaint_card_mark` handles
        the other direction: a toggle on an already-mounted card.
        """
        return self.markable and self.task_data.filename in self.app.marked

    def compose(self):
        meta = self.task_data.metadata
        effort = meta.get('effort', '')
        labels = meta.get('labels', [])
        status = meta.get('status', '')
        assigned_to = meta.get('assigned_to', '')

        task_num, task_name = self._parse_filename(self.task_data.filename)
        is_modified = self.manager.is_modified(self.task_data) if self.manager else False
        with Horizontal(classes="task-title-row"):
            if self.markable:
                marked = self._is_marked()
                yield Label(mark_markup(marked),
                            classes="task-mark task-marked" if marked else "task-mark")
            # Follow-up provenance gutter (t1468_3). Deliberately NOT hung off
            # the mark above: `markable=True` is set only in
            # `KanbanColumn.task_block`, so TopicColumn cards and child cards
            # have no mark and must still show the glyph.
            followup = _followup_marker(meta)
            if followup:
                yield Label(_followup_glyph_text(followup),
                            classes="task-followup-glyph")
            if task_num:
                display_num = f"{task_num} *" if is_modified else task_num
                num_classes = "task-number task-modified" if is_modified else "task-number"
                yield Label(display_num, classes=num_classes)
            yield Label(task_name, classes="task-title")

        info = []
        if effort: info.append(f"💪 {effort}")
        if labels: info.append(f"🏷️ {','.join(labels)}")
        issue = meta.get('issue', '')
        if issue:
            info.append(_issue_indicator(issue))
        pr_url = meta.get('pull_request', '')
        if pr_url:
            info.append(_pr_indicator(pr_url))
        contributor = meta.get('contributor', '')
        if contributor:
            info.append(f"[dim]@{contributor}[/dim]")

        if info:
            yield Label(" | ".join(info), classes="task-info")

        # Lock indicator on its own line
        if self.manager:
            lock_id = task_num.lstrip("t")
            if lock_id in self.manager.lock_map:
                lock_info = self.manager.lock_map[lock_id]
                yield Label(f"\U0001f512 {lock_info['locked_by']}", classes="task-info")

        unresolved_deps = []
        if self.manager:
            unresolved_deps = self.manager.unresolved_local_deps(self.task_data)

        # Cross-repo dependencies (xdeps + xdeprepo, t832_8). Build a per-ref
        # display string with live status; xdep_blocked drives the distinct
        # "blocked by cross-repo" indicator. Both fields must be present
        # (both-or-neither invariant from t832_3). xdeps values are NOT
        # normalized by task_yaml, so coerce/strip the leading 't' here.
        xdep_display = []
        xdep_blocked = False
        xdeprepo = meta.get('xdeprepo')
        xdeps = meta.get('xdeps', []) or []
        if self.manager and xdeprepo and xdeps:
            xdep_display, xdep_blocked = self.manager.cross_repo_dep_display(self.task_data)

        # Determine implementing children for parent tasks
        implementing_children = []
        total_children = 0
        if self.manager and not self.is_child:
            task_num_for_children, _ = self._parse_filename(self.task_data.filename)
            children = self.manager.get_child_tasks_for_parent(task_num_for_children)
            total_children = len(children)
            implementing_children = [
                c for c in children if c.metadata.get('status') == 'Implementing'
            ]

        is_blocked = bool(unresolved_deps) or xdep_blocked
        status_parts = []
        if unresolved_deps:
            status_parts.append("🚫 blocked")
        if xdep_blocked:
            status_parts.append("🌐 blocked (cross-repo)")
        # Deferred-plan qualifier (t1603_1). The badge is suppressed on three
        # conditions -- blocked, empty status, implementing children -- and the
        # qualifier must survive all of them: a `Ready` task can legitimately be
        # blocked *and* marked, because the risk-mitigation "before" stop
        # deliberately keeps the marker (task-workflow/SKILL.md:553). Both
        # branches route through `_status_badge_text` so the wording lives in
        # exactly one place.
        plan_marker = _plan_approved_marker(meta)
        if not is_blocked and status and not implementing_children:
            status_parts.append(_status_badge_text(status, plan_marker))
        elif plan_marker:
            status_parts.append(_status_badge_text("", plan_marker))
        if assigned_to: status_parts.append(f"👤 {assigned_to}")
        if status_parts:
            yield Label(" | ".join(status_parts), classes="task-info")

        if unresolved_deps:
            yield Label(f"🔗 {', '.join(unresolved_deps)}", classes="task-info")
        if xdep_display:
            yield Label(f"↗ {', '.join(xdep_display)}", classes="task-info")

        folded_into = meta.get('folded_into')
        if folded_into:
            yield Label(f"\U0001f4ce folded into t{folded_into}", classes="task-info")

        if self.manager and not self.is_child:
            if implementing_children:
                for child in implementing_children:
                    child_num, _ = self._parse_filename(child.filename)
                    child_email = child.metadata.get('assigned_to', '')
                    child_label = f"\u26a1 {child_num}"
                    if child_email:
                        child_label += f" \U0001f464 {child_email}"
                    yield Label(child_label, classes="task-info")
                remaining = total_children - len(implementing_children)
                if remaining > 0:
                    yield Label(f"\U0001f476 {remaining} more children", classes="task-info")
            elif total_children > 0:
                yield Label(f"\U0001f476 {total_children} children", classes="task-info")

    def _priority_border_color(self):
        priority = self.task_data.metadata.get('priority', 'normal')
        if priority == "high": return "red"
        if priority == "medium": return "yellow"
        return "gray"

    def _idle_border_style(self):
        return "dashed" if self.is_child else "solid"

    def on_mount(self):
        self.styles.border = (self._idle_border_style(), self._priority_border_color())
        self.styles.padding = (0, 1)
        if self.is_child:
            self.styles.margin = (0, 0, 1, 0)
        else:
            self.styles.margin = (0, 0, 1, 0)

    def on_focus(self):
        self.styles.border = ("double", "cyan")
        # Synchronous and unanimated on purpose (t1248). Textual's defaults
        # (animate=True, immediate=False) defer this through call_after_refresh
        # and animate it, so it can land *behind* wheel events the user has
        # already produced and leave scroll_target_y pointing somewhere
        # scroll_y is not. The wheel handler computes its next position from
        # scroll_target_y, so that divergence rewinds the column.
        self.scroll_visible(animate=False, immediate=True)

    def on_blur(self):
        self.styles.border = (self._idle_border_style(), self._priority_border_color())

    def on_click(self, event):
        self.focus()
        if event.chain == 2:
            # Collapsed parent with children → expand instead of opening
            # details, but only where toggle_children is actually available:
            # check_action hides it in the derived views (In-Flight / By-Topic /
            # By-Trail render children directly), and the mouse path must honor
            # the same gate. Gated off → fall through to the detail modal.
            if not self.is_child and \
                    self.app.check_action("toggle_children", None) is True:
                task_num, _ = TaskCard._parse_filename(self.task_data.filename)
                children = self.manager.get_child_tasks_for_parent(task_num)
                if children and self.task_data.filename not in self.app.expanded_tasks:
                    self.app.action_toggle_children()
                    return
            self.app.action_view_details()


# --- Metadata render boundaries ---


def _followup_marker(metadata):
    """`(glyph, colour)` for a task's `followup_kind`, or `None` when it is not
    an auto-spawned follow-up (t1468_3).

    The board's metadata-shaped adapter over the shared render boundary
    `followup_kinds.marker_for` (extracted in t1468_5 when the minimonitor
    sibling picker needed the same three-way rule — absent vs recognised vs
    unrecognised — and a second copy would have been free to drift). This
    function keeps the metadata-dict signature every board call site uses;
    `marker_for` owns the semantics, including the deliberate divergence from
    `glyph_for` / `colour_for` for an *absent* kind.

    `lib/task_yaml.py` deliberately leaves frontmatter values type-honest, so a
    hand-edited or foreign field arrives as `None`, a list, a dict, an int or a
    bool — `marker_for` normalizes every one of those to "no marker". Never
    read the raw value in a `compose`.

    Returning a tuple-or-``None`` rather than a bare glyph string is what keeps
    "no marker" structurally distinct from "a marker that happens to be `·`",
    so every call site is a single `if marker:`.
    """
    return marker_for((metadata or {}).get("followup_kind"))


def _plan_approved_marker(metadata):
    """The approval timestamp for a task whose plan was approved and whose
    implementation was deliberately deferred, or `None` when there is none
    (t1603_1).

    The render boundary over `plan_approved_at` (t1595), in the same shape as
    `_followup_marker` above: `lib/task_yaml.py` deliberately leaves frontmatter
    values type-honest, so a hand-edited or foreign field arrives as `None`, a
    list, a dict, an int, a bool — or, because the loader resolves YAML
    timestamps, as a `datetime` (`2026-02-01 14:30:05`) or a `date`
    (`2026-02-01`). The workflow's own writer emits the seconds-less
    `2026-02-01 14:30` (`aitask_update.sh:822`), which stays a `str`. Never read
    the raw value in a `compose`.

    A value that cannot be read renders as a fixed literal rather than
    vanishing: following `_followup_marker`'s rule, a bad value that silently
    disappears is indistinguishable from a task that never had a marker.

    Returning a string-or-``None`` rather than always a string is what keeps "no
    marker" structurally distinct from "a marker that happens to look odd", so
    every call site is a single `if marker:`.

    **Not** `_normalize_opaque_scalar` (`board/aitask_merge.py:151`), despite
    the overlapping input space. That one answers `""` for *every* non-`str`,
    which is right for **comparison** — a merge must not treat a hand-edited
    list as a distinguishing value — and wrong for **rendering**: it would hide
    a `datetime`-parsed marker that `ait ls` (a line-oriented bash frontmatter
    parse, which never sees a YAML type) still displays. The two boundaries
    diverge on purpose; do not unify them.
    """
    raw = (metadata or {}).get("plan_approved_at")
    if isinstance(raw, str):
        return raw if raw.strip() else None
    if raw is None:
        return None
    # `datetime` is a subclass of `date` and both format identically here, so
    # one branch covers the seconds-bearing and bare-date spellings alike.
    if isinstance(raw, date):
        return raw.strftime("%Y-%m-%d %H:%M")
    return "set (unreadable)"


def _status_badge_text(status, plan_marker) -> str:
    """The one authority for a card's status badge text (t1603_1).

    Both call-site forms come from here: the ordinary badge and the
    qualifier-only badge a *suppressed* card falls back to. A second literal at
    the suppression site would let `· Planned` and `Planned` drift apart on the
    next wording change, so that site calls this with an empty status rather
    than spelling its own string.

    `status` is a raw frontmatter value, **not** a `str` — `lib/task_yaml.py`
    leaves values type-honest, so a hand-edited file yields `[Ready]`, `42`,
    `True` or a `date`. The `str()` is load-bearing: `join` raises `TypeError`
    on any of those, where the f-string it replaces was total, and a crash in
    `compose` takes the whole board down. `f"{x}"` is `format(x, "")`, which
    equals `str(x)` for every type reachable here, so the rendered bytes are
    unchanged. Truthiness is tested on the RAW value, so falsey shapes (`""`,
    `None`, `0`, `[]`) suppress exactly as the previous `if status:` did.
    """
    parts = [str(p) for p in (status, "Planned" if plan_marker else None) if p]
    return f"📋 {' · '.join(parts)}" if parts else ""


@lru_cache(maxsize=32)
def _followup_colour_hex(colour: str) -> str:
    """A vocabulary colour pinned to an explicit truecolor hex (t1468_8).

    `FOLLOWUP_KINDS` names most colours (`yellow`, `cyan`, …), and a NAME does
    not composite to one value — it depends on how the style reaches the
    compositor:

    * as a Rich **base** style — `Text(glyph, style=colour)` handed straight to
      a `Label`, which is what every card surface does — Textual resolves it
      through its CSS palette: `yellow` -> `#ffff00`;
    * as a Rich **span** — `Text.append(glyph, style=colour)`, which is what a
      single-line row built from one multi-span `Text` must use — it resolves
      through the theme's ANSI palette instead: `yellow` -> `#fd971f`.

    Same kind, two different yellows, on two surfaces that promise to match.
    A hex composites identically on BOTH paths, so pinning it here removes the
    divergence at the one boundary every surface already shares.

    Resolved through `textual.color.Color`, **never** Rich's
    `Color.get_truecolor()`: the latter answers `#808000` for `yellow` and
    `#008080` for `cyan`, which would silently restyle every existing card.
    Textual's values are byte-identical to what the cards already paint, so
    this is a no-op for them and a fix for the row.

    Falls back to the raw name when Textual cannot parse it — the pre-t1468_8
    behaviour, and never worse than it. `FollowupVocabularyTests` already fails
    the build for an unparseable entry, so this is defence, not a policy.
    """
    try:
        return TextualColor.parse(colour).hex
    except ColorParseError:
        return colour


def _followup_glyph_text(marker) -> Text:
    """The glyph as a Rich `Text`, carrying its colour as a literal style.

    A literal Rich style resolves in `render().spans` AND in the composited
    strips; an unresolved CSS colour name resolves in neither, which is exactly
    what the colour verification reads.

    The style is pinned to a hex by `_followup_colour_hex` so that a card
    (which applies this `Text` as a base style) and the task-detail row (which
    appends it as a span into a longer line) paint the SAME colour — a bare
    name does not survive both paths identically.
    """
    glyph, colour = marker
    return Text(glyph, style=_followup_colour_hex(colour)) if colour else Text(glyph)


# --- Picker rows and overlays ---


class PickerItem(Static):
    """Focusable row inside a ``#dep_picker_dialog`` modal.

    Owns the focus-visibility contract for every picker row, so a new row type
    cannot ship without a highlight. Before t1366 each of the seven row classes
    re-declared ``can_focus`` / ``on_focus`` / ``on_blur`` independently and the
    App CSS styled only two of them: the other five added ``dep-item-focused``
    against a class no rule matched, and arrow keys moved focus with **zero**
    visible change. Subclasses keep their own ``__init__`` / ``render`` /
    ``on_key`` / ``on_click`` — only the focus contract lives here, and a
    subclass must NOT re-define ``on_focus`` / ``on_blur`` (Textual dispatches
    handlers down the MRO, so both would fire).

    ``CrossRepoRefItem`` is deliberately NOT a subclass: its styling lives in
    ``CrossRepoRefPickerScreen.DEFAULT_CSS``, and App-level CSS outranks widget
    ``DEFAULT_CSS``, so reparenting it would make the ``PickerItem`` rules
    silently beat its own.
    """

    can_focus = True

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")


class LoadingOverlay(ModalScreen):
    """Modal overlay showing a LoadingIndicator with a message."""

    def __init__(self, message: str = "Working..."):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="loading_dialog"):
            yield Label(self._message, id="loading_message")
            yield LoadingIndicator()
