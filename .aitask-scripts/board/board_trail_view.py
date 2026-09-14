"""The By-Trail view's pure rendering half (t1794_3).

Extracted verbatim from ``aitask_board.py``: the trail projection model
(constants, ``TrailEntryView`` / ``TrailWaveLane``, ``build_trail_lanes`` and its
helpers, ``run_trail_drift``), the wave cards and columns, and the three trail
modals (select / detail / summary), plus ``TRAIL_CSS``. The stand-alone trails
app renders with this module (parent plan t1794), and its model half runs
headless — see ``HeadlessTrailModelTests`` in tests/test_board_bytrail_view.py.

``aitask_board.py`` re-exports every name, so ``ab.build_trail_lanes`` /
``ab.TrailDetailScreen`` keep resolving. Inside this module the helpers call
each other through THIS namespace, so a stub of one of them must target
``board_trail_view`` (reachable as ``ab.board_trail_view``), not the board.

This is the board's RENDERING half of implementation trails (RFC §9 in
aidocs/implementation_trail_design.md). Discovery, dedup, overlap and blob
loading live in lib/trail_discovery.py (t1647_1). Trail projections are
rendered READ-ONLY: the only verbs ever spawned are the read verbs (trail_gather
drift, artifact get/versions) — every trail write happens in the launched
/aitask-trail skill after its own confirmation (RFC §9.3).

Contracts (see ``board/__init__.py`` and the parent plan):

* C1 — imported by bare name; imports ``board_widgets`` and no other board
  module, never ``aitask_board``, and adds nothing to ``sys.path``: every
  importer has already put ``.aitask-scripts/lib`` there.
* C2 — resolves no task directory, neither at import nor at runtime:
  ``load_local_project_name`` takes the resolved ``tasks_dir`` from its caller.

The view state, workers, key handling and trail launch stay in ``KanbanApp``.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from board_widgets import (
    ColumnHeader, PickerItem, TaskCard,
    _followup_glyph_text, _followup_marker, _plan_approved_marker,
    _status_badge_text,
)
from cross_repo_notation import parse_ref as parse_cross_repo_ref
from topic_semantics import task_own_id
from trail_discovery import TrailInfo, trail_entry_refs


# Artifact-version watch cadence (t1268): how often to poll `artifact
# versions` for the active trail after an agent refresh was launched, and how
# many polls before giving up (~30 min at 20s).
TRAIL_WATCH_INTERVAL = 20
TRAIL_WATCH_MAX_TICKS = 90
TRAIL_GATHER_SCRIPT = Path(".aitask-scripts") / "aitask_trail_gather.sh"

# Classification glyphs (RFC §15 wireframe pins ◆ hard prereq / ● core; the
# remaining enum members get distinct glyphs here). Landed entries additionally
# render ✔ + strike-through. Pinned by tests/test_board_bytrail_view.py.
TRAIL_CLASSIFICATION_GLYPHS = {
    "hard_prerequisite": "◆",
    "preferred_predecessor": "▲",
    "core": "●",
    "coordination_only": "⇄",
    "optional": "○",
}

_TRAIL_GHOST_LABELS = {
    "cross_repo": "cross-repo member",
    "archived": "archived",
    "missing": "missing",
}


# The CSS the By-Trail view owns (t1794_3; parent contract C7). Every App that
# renders the view appends this to its own `CSS` — `KanbanApp.CSS` ends with
# `+ TRAIL_CSS`, and the stand-alone trails app must do the same.
# Deliberately NOT here: the rules for the board_widgets widgets these cards
# and modals build on (`.task-title`, `.task-info`, `.col-header-*`,
# `PickerItem*`, `#loading_*`). They belong to the widget layer and stay with
# the host App's own CSS, so a second App must supply them itself.
TRAIL_CSS = """
    /* Drift marker on trail cards. Two classes, not `.trail-drift` alone: the
       label also carries `.task-info` (colour $text-muted, owned by the host
       App's card rules), and a two-class selector wins whichever stylesheet
       the host puts first. */
    .task-info.trail-drift { color: #FFB86C; }
    /* By-Trail summary pane (t1505_1). The explicit height is LOAD-BEARING,
       not cosmetic: VerticalScroll inherits `height: 1fr` from
       ScrollableContainer, so without it this pane and #board_container would
       split the vertical space evenly instead of the pane taking six rows.
       NEVER add `dock: bottom` — see the compose() comment and t1278. */
    #trail_summary { height: 6; border-top: hkey $secondary-background; padding: 0 1; }
"""


@dataclass
class TrailEntryView:
    """A wave entry resolved against live board state."""
    entry: dict
    task: "Task | None"      # live local task, when active
    ghost_kind: str          # "" | "cross_repo" | "archived" | "missing"
    landed: bool             # live/archived status == Done → strike-through
    # Drift reasons owned by THIS entry's task ref (t1268). Keyed on the raw
    # entry ref, so ghosts carry their own reasons too.
    drift_reasons: list = field(default_factory=list)


@dataclass
class TrailWaveLane:
    wave: dict
    entries: list


def load_local_project_name(tasks_dir: Path,
                            config_path: Path | None = None) -> str:
    """Read ``project.name`` from project_config.yaml ('' when unavailable).

    A missing name never crashes the view — refs just resolve as
    unresolvable (cross-repo) ghosts and the banner notes the problem.

    ``tasks_dir`` is the caller's resolved task directory. This module never
    resolves one itself (t1794 C2): under the fixture harness only
    ``aitask_board.py`` is re-executed against the fixture tree, so a lookup
    here would read the live tree or the already-restored env."""
    path = config_path or (tasks_dir / "metadata" / "project_config.yaml")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ""
    project = data.get("project") if isinstance(data, dict) else None
    if isinstance(project, dict) and project.get("name"):
        return str(project["name"])
    return ""


def trail_ref_to_local_id(ref, local_project: str):
    """Map a canonical ``<project>#<id>`` task ref to a bare local id, or None
    when the ref is foreign / unparseable / the local project name is unknown."""
    parsed = parse_cross_repo_ref(str(ref or ""))
    if not parsed:
        return None
    project, task_id = parsed
    if not local_project or project != local_project:
        return None
    return task_id


def canonical_trail_ref(ref) -> str:
    """Normalize a task ref to the ``<project>#<id>`` form drift reasons use.

    The stored trail may spell a member ``aitasks#t42`` (the ``t`` prefix is
    accepted notation), but trail_gather always emits drift reasons against
    the canonical ``aitasks#42``. Keying both sides through here is what makes
    the per-card lookup hit regardless of which spelling the trail stored
    (t1268). Unparseable refs fall back to their raw text so nothing is lost."""
    parsed = parse_cross_repo_ref(str(ref or ""))
    if not parsed:
        return str(ref or "")
    project, task_id = parsed
    return f"{project}#{task_id}"


def build_trail_lanes(doc, tasks_by_id, local_project, archived_lookup,
                      drift_by_ref=None):
    """Project a validated trail document onto live board state.

    Returns ``TrailWaveLane``s with waves in ``ordinal`` order and entries in
    ``position`` order (RFC §9.1). Each entry resolves to a live task, or to a
    ghost (``cross_repo`` / ``archived`` / ``missing``); ``landed`` is derived
    from live/archived status == Done — the trail snapshot is never trusted
    over the task file (schema: "the task file remains the source of truth").

    ``drift_by_ref`` (t1268) maps a CANONICAL entry task ref to its drift
    reasons (see ``trail_drift_by_ref``). Looked up on the ref rather than the
    resolved local id, so archived / cross-repo ghosts carry their reasons
    too, and through ``canonical_trail_ref`` so a stored ``aitasks#t42``
    still matches the gatherer's ``aitasks#42``."""
    lanes = []
    by_ref = drift_by_ref or {}
    for wave in sorted(doc.get("waves") or [],
                       key=lambda w: w.get("ordinal", 0)):
        views = []
        for entry in sorted(wave.get("entries") or [],
                            key=lambda e: e.get("position", 0)):
            drift = by_ref.get(canonical_trail_ref(entry.get("task")), [])
            local_id = trail_ref_to_local_id(entry.get("task"), local_project)
            if local_id is None:
                views.append(TrailEntryView(entry, None, "cross_repo", False,
                                            drift))
                continue
            task = tasks_by_id.get(local_id)
            if task is not None:
                landed = task.metadata.get("status") == "Done"
                views.append(TrailEntryView(entry, task, "", landed, drift))
                continue
            archived_task = archived_lookup(local_id)
            if archived_task is not None:
                landed = archived_task.metadata.get("status") == "Done"
                views.append(TrailEntryView(entry, None, "archived", landed,
                                            drift))
            else:
                views.append(TrailEntryView(entry, None, "missing", False,
                                            drift))
        lanes.append(TrailWaveLane(wave, views))
    return lanes


def trail_drift_by_ref(reasons) -> dict:
    """Group drift reasons ``(code, task_ref, detail)`` by owning task ref.

    Keys are canonicalized (``canonical_trail_ref``) so they match however the
    trail document spelled the member.

    Trail-level reasons (``task_ref`` == "-", e.g. ``input_missing``) and
    reasons naming a task that is not a trail member (``new_related_task``)
    have no owning card; they are dropped here and stay visible in the
    subtitle count and the trail detail modal."""
    by_ref: dict = {}
    for code, task_ref, detail in reasons or []:
        if not task_ref or task_ref == "-":
            continue
        key = canonical_trail_ref(task_ref)
        by_ref.setdefault(key, []).append((code, task_ref, detail))
    return by_ref


def trail_summary_text(doc) -> str:
    """The trail's free-form summary for the By-Trail pane (t1505_1).

    Prefers ``narrative.overview`` — t1505_3's advisory prose field — and falls
    back to the always-required ``narrative.recommendation_summary``, so a trail
    written before that field existed still shows something useful. `overview`
    is optional in the schema, so the fallback stays a live path for every trail
    that does not carry one.

    Returns "" when neither carries text; the caller hides the pane rather than
    showing an empty frame. Whitespace-only counts as empty at every level, so a
    summary of spaces cannot mount a blank six-row pane.

    Advisory only: nothing here may feed lane construction, ordering or
    classification — waves and entries remain the binding structure."""
    narrative = (doc or {}).get("narrative")
    if not isinstance(narrative, dict):
        return ""
    for field in ("overview", "recommendation_summary"):
        value = narrative.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def run_trail_drift(handle: str):
    """Run the read-only drift verb; returns ``(verdict, reasons)``.

    ``verdict``: first stdout token — ``CURRENT`` / ``STALE`` /
    ``ERROR:<kind>:<id>`` — or ``UNAVAILABLE:<why>`` for infra failures.
    ``reasons``: parsed ``DRIFT:<code>|<task_ref or ->|<detail>`` triples.
    Passive observation (RFC §8.2): results update rendered badges only;
    the artifact is never written."""
    try:
        result = subprocess.run(
            [str(TRAIL_GATHER_SCRIPT), "drift", "--trail", handle],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return f"UNAVAILABLE:{type(exc).__name__}", []
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if result.returncode != 0 or not lines:
        return "UNAVAILABLE:infra", []
    verdict = lines[0].strip()
    reasons = []
    for ln in lines[1:]:
        if ln.startswith("DRIFT:"):
            parts = ln[len("DRIFT:"):].split("|", 2)
            while len(parts) < 3:
                parts.append("")
            reasons.append((parts[0], parts[1], parts[2]))
    return verdict, reasons


class _GhostTaskStub:
    """Minimal Task stand-in carried by TrailGhostCard.

    Satisfies every accessor the board's focus/refocus/search seams touch
    (filename, filepath, metadata, archived) without ever matching a real
    task. Defensive completeness only — the primary safety is the explicit
    check_action ghost guard that hides all task-only actions."""

    def __init__(self, ref: str):
        slug = re.sub(r"[^0-9A-Za-z._#-]+", "-", str(ref)) or "unknown"
        self.filename = f"trail-ghost-{slug}.md"
        self.filepath = Path(self.filename)
        self.metadata: dict = {}
        self.content = ""
        self.archived = False


def _trail_badge_text(entry: dict) -> str:
    """Literal badge line for a trail entry card: glyph, classification,
    confidence. Rendered with markup=False (literal UI text)."""
    classification = str(entry.get("classification") or "?")
    glyph = TRAIL_CLASSIFICATION_GLYPHS.get(classification, "·")
    confidence = str(entry.get("confidence") or "?")
    return f"{glyph} {classification} · conf: {confidence}"


def _trail_drift_text(reasons, max_shown: int = 2,
                      max_detail: int = 48) -> str:
    """Literal per-card drift marker (rendered with markup=False).

    The *detail* is what makes the marker actionable ("status 'Ready' ->
    'Implementing'"), so it is rendered alongside the code rather than the code
    alone. Bounded by ``max_shown`` reasons and a truncated detail to fit a
    card; the complete list stays in TrailDetailScreen."""
    if not reasons:
        return ""
    parts = []
    for code, _ref, detail in reasons[:max_shown]:
        detail = " ".join(str(detail or "").split())
        if len(detail) > max_detail:
            detail = detail[:max_detail - 1].rstrip() + "…"
        parts.append(f"{code}: {detail}" if detail else str(code))
    extra = len(reasons) - max_shown
    if extra > 0:
        parts.append(f"(+{extra} more)")
    return "⚠ " + " · ".join(parts)


class TrailTaskCard(TaskCard):
    """Card for a live local task inside a By-Trail wave column (RFC §9.1)."""

    def __init__(self, view: TrailEntryView, wave: dict,
                 manager: "TaskManager", column_id: str):
        super().__init__(view.task, manager,
                         is_child=("_" in (task_own_id(view.task) or "")),
                         column_id=column_id)
        self.trail_entry = view.entry
        self.trail_view = view
        self.trail_wave = wave
        self.is_ghost = False

    def compose(self):
        task_num, task_name = self._parse_filename(self.task_data.filename)
        title = Text()
        # There is no `.task-title-row` Horizontal on this card — the title is
        # one Rich Text — so the follow-up glyph is prepended into it rather
        # than yielded as a gutter Label. It goes BEFORE the landed `✔ `, so the
        # leading column is the provenance marker on every By-Trail card.
        # Source is frontmatter, NOT `self.trail_entry`: the trail snapshot
        # serves the trail document, which is what keeps this independent of
        # t1468_5.
        followup = _followup_marker(self.task_data.metadata)
        if followup:
            title.append_text(_followup_glyph_text(followup))
            title.append(" ")
        if self.trail_view.landed:
            title.append("✔ ")
            title.append(f"{task_num} {task_name}".strip(), style="strike")
        else:
            title.append(f"{task_num} {task_name}".strip())
        yield Label(title, classes="task-title")
        yield Label(_trail_badge_text(self.trail_entry),
                    classes="task-info trail-badges", markup=False)
        # Deferred-plan qualifier (t1603_1). The guard is `status or
        # plan_marker`, not `status` -- a hand-edited task with a marker and no
        # `status:` key must still surface `📋 Planned` here, exactly as
        # TaskCard's suppressed-badge branch does. `_status_badge_text` returns
        # "" iff both are falsey, so this condition is precisely "the helper has
        # something to say": guard and helper agree by construction rather than
        # by two separately-maintained truth tables.
        status = self.task_data.metadata.get("status", "")
        plan_marker = _plan_approved_marker(self.task_data.metadata)
        if status or plan_marker:
            yield Label(_status_badge_text(status, plan_marker),
                        classes="task-info")
        drift = _trail_drift_text(self.trail_view.drift_reasons)
        if drift:
            yield Label(drift, classes="task-info trail-drift", markup=False)
        # markup=False: bracketed shortcut hints are literal UI text.
        # Card-scoped actions ONLY (t1268): `r`/`s` are view-scoped and now
        # carry truthful By-Trail labels in the footer, so naming them here
        # duplicated — and for `s` contradicted — the footer.
        yield Label("[enter details]",
                    classes="task-info trail-ops", markup=False)

    def on_click(self, event):
        # No expand-children double-click in By-Trail. The base handler now
        # consults check_action (which hides toggle_children here), so this
        # override only states that behavior explicitly.
        self.focus()
        if event.chain == 2:
            self.app.action_view_details()


class TrailGhostCard(TaskCard):
    """Read-only ghost card for archived / missing / cross-repo trail members
    (RFC §9.1: no move actions; §9.2 ghost rows).

    Subclasses TaskCard so every focus/nav/refocus seam (which queries
    TaskCard) reaches ghosts unchanged; carries a synthetic task stub whose
    filename is the stable refocus key. check_action hides all task-only
    actions when a ghost is focused."""

    def __init__(self, view: TrailEntryView, wave: dict, column_id: str):
        stub = _GhostTaskStub(view.entry.get("task", ""))
        super().__init__(stub, None, is_child=False, column_id=column_id)
        self.trail_entry = view.entry
        self.trail_view = view
        self.trail_wave = wave
        self.is_ghost = True

    def compose(self):
        # No follow-up glyph here, BY DESIGN (t1468_3) — not an omission. A
        # ghost is a referenced task with no local file, so `_GhostTaskStub`
        # carries `metadata = {}`: there is nothing to classify and nothing to
        # pick. `_followup_marker({})` would return None anyway; not calling it
        # states the decision rather than leaving it to fall out.
        ref = str(self.trail_entry.get("task") or "?")
        title = Text()
        if self.trail_view.landed:
            title.append("✔ ")
            title.append(ref, style="strike")
        else:
            title.append(ref)
        yield Label(title, classes="task-title")
        kind = _TRAIL_GHOST_LABELS.get(self.trail_view.ghost_kind,
                                       self.trail_view.ghost_kind)
        yield Label(f"👻 {kind} — read-only", classes="task-info")
        yield Label(_trail_badge_text(self.trail_entry),
                    classes="task-info trail-badges", markup=False)
        drift = _trail_drift_text(self.trail_view.drift_reasons)
        if drift:
            yield Label(drift, classes="task-info trail-drift", markup=False)

    def _priority_border_color(self):
        return "gray"

    def _idle_border_style(self):
        return "dashed"

    def on_click(self, event):
        self.focus()
        if event.chain == 2:
            self.app.action_view_details()


class TrailColumn(VerticalScroll):
    """A wave column in the By-Trail view (RFC §9.1): ``W<ordinal> · <title>``
    header over TrailTaskCards / TrailGhostCards in position order.

    Non-reorderable. Carries ``self.wave`` and per-card ``trail_entry`` /
    ``is_ghost`` as the seams for the t1210_5 move commands."""

    def __init__(self, lane: TrailWaveLane, manager: "TaskManager"):
        super().__init__()
        self.lane = lane
        self.wave = lane.wave
        self.manager = manager
        self.col_id = f"trail-w{self.wave.get('ordinal', 0)}"

    def wave_entries(self) -> list:
        """This wave's `TrailEntryView`s in `position` order (t1210_5).

        The authoritative order — `compose` mounts the cards from this same
        list — so the wave move reads it rather than walking the DOM.
        """
        return self.lane.entries

    def compose(self):
        title = f"W{self.wave.get('ordinal', '?')} · {self.wave.get('title', '')}"
        header = ColumnHeader(self.col_id, title, len(self.lane.entries),
                              is_collapsed=False, editable=False)
        header.styles.width = "100%"
        header.styles.text_align = "center"
        yield header
        for view in self.lane.entries:
            if view.task is not None:
                yield TrailTaskCard(view, self.wave, self.manager,
                                    column_id=self.col_id)
            else:
                yield TrailGhostCard(view, self.wave, column_id=self.col_id)

    def on_mount(self):
        self.styles.width = 44
        self.styles.min_width = 34
        self.styles.border = ("round", "#8BE9FD")
        self.styles.margin = (0, 1)


def _trail_stored_freshness(info: TrailInfo) -> str:
    """Selection-modal freshness badge from the trail's *stored* verdict (the
    live drift check runs only for the active trail).

    Labelled "(recorded)" (t1268): ``freshness`` records what was true when the
    trail was last written, so a trail a live drift run calls STALE can still
    carry ``state: current`` here. Without the qualifier the badge reads as a
    live verdict and is actively misleading. Running drift per discovered trail
    would cost one ~0.5s subprocess each on the discovery path — deliberately
    not done; the active trail gets the live check."""
    if info.load_error:
        return "✗ unreadable"
    doc = info.doc or {}
    freshness = doc.get("freshness") or {}
    state = str(freshness.get("state") or "unknown")
    if state == "stale":
        n = len(freshness.get('drift_reasons') or [])
        return f"⚠ stale ({n}, recorded)"
    if state == "current":
        return "✓ current (recorded)"
    return "? unknown"


class TrailSelectItem(PickerItem):
    """Focusable row for one discovered trail (title · owner · scope ·
    freshness · updated, with "also in" overlap sub-lines per §9.2)."""

    def __init__(self, info: TrailInfo, overlap_notes: list):
        doc = info.doc or {}
        title = str(doc.get("title") or info.name or info.handle)
        owner = f"owner t{info.owner_id}" if info.owner_id else "owner ?"
        if info.owner_archived:
            owner += " (archived)"
        scope = str((doc.get("scope") or {}).get("kind") or "?")
        updated = str((doc.get("generation") or {}).get("generated_at") or "?")
        text = Text()
        text.append(f"{title}   ")
        text.append(f"{owner} · {scope} · {_trail_stored_freshness(info)} "
                    f"· {updated}", style="dim")
        for ref, other_title in overlap_notes:
            text.append(f"\n  └ also references: {ref} ({other_title})",
                        style="dim italic")
        super().__init__(text)
        self.info = info

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.info.handle)
            event.prevent_default()
            event.stop()

    def on_click(self, event):
        self.screen.dismiss(self.info.handle)


class TrailSelectScreen(ModalScreen):
    """Trail selection modal (RFC §9.1): dismisses the chosen handle or None."""

    # Mirrors the KanbanApp.CSS rules this modal used to borrow (t1794_3) so it
    # lays out the same when pushed by an App without them (tui_conventions.md
    # "Modals pushed by multiple Apps"). Textual scopes these rules to this
    # screen; the values equal the board's own, so the board renders the same
    # whichever rule wins.
    DEFAULT_CSS = """
    TrailSelectScreen {
        align: center middle;
    }
    #dep_picker_dialog {
        width: 60%;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #dep_picker_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #dep_picker_dialog.picker-dialog { overflow-y: auto; }
    .picker-dialog #dep_picker_title { width: 100%; dock: top; }
    PickerItem { height: auto; width: 100%; padding: 0 1; }
    PickerItem.dep-item-focused { background: $primary 20%; outline-left: thick $accent; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, infos: list, overlaps: dict):
        super().__init__()
        self.infos = infos
        self.overlaps = overlaps

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label(
                "Select trail — [dim]↑/↓ move · Enter open · Esc cancel[/]",
                id="dep_picker_title",
            )
            for info in self.infos:
                yield TrailSelectItem(info, self.overlaps.get(info.handle, []))
            yield Button("Cancel", id="btn_dep_cancel")

    def on_mount(self):
        items = list(self.query(TrailSelectItem))
        if items:
            items[0].focus()

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel_button(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class TrailDetailScreen(ModalScreen):
    """Entry-first projection of a trail (RFC §9.1 detail modal): the focused
    entry, its wave, the drift and observations that concern it, the evidence
    backing everything shown, the trail narrative, and exclusions. Read-only
    prose, not tooltips.

    Until t1505_2 this rendered the WHOLE document on every card — all 19
    observations, all 56 evidence records and every drift reason of the live
    gate-framework trail — so two cards' text was ~95% identical and the part
    that distinguished them scrolled off the top. `_scope` now partitions the
    document against the focused entry and `a` reveals what was withheld."""

    DEFAULT_CSS = """
    TrailDetailScreen {
        align: center middle;
    }
    #trail_detail_dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #trail_detail_body {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        # No modal in this app mounts a Footer, so `show=True` would surface
        # nowhere; the in-body hint line is the discoverability surface and it
        # renders exactly when something is withheld. `a` is also bound at App
        # level (`view_all`) WITHOUT priority, so this screen binding shadows
        # it while the modal is up — pinned by a negative control asserting
        # `base_filter` does not change.
        Binding("a", "toggle_all", "Show all", show=False),
    ]

    def __init__(self, doc: dict, drift_reasons: list,
                 entry: dict | None = None, wave: dict | None = None):
        super().__init__()
        self.doc = doc or {}
        self.drift_reasons = drift_reasons or []
        self.entry = entry
        self.wave = wave
        self.show_all = False

    def _scope(self) -> dict:
        """Partition the document three ways against the focused entry: owned
        by it, owned by ANOTHER member, and UNOWNED.

        Only the middle bucket is ever withheld. Unowned material — a
        trail-level or non-member drift reason (both categories
        ``trail_drift_by_ref`` drops), an observation affecting no member, an
        evidence record nothing cites — has no owning card, so filing it under
        "other" would hide it on EVERY card instead of duplicating it on every
        card: strictly worse than the defect this scoping removes.

        Displayed evidence follows what is DISPLAYED, not just the entry: an
        observation shown here without the record it cites is an unsupported
        claim in an evidence-backed artifact. A record cited by nothing at all
        is unowned like the rest — and that is the whole of a lite trail's
        evidence, since the lite writer omits per-entry ``evidence_refs``
        while the schema still requires >= 1 record.

        Read by ``_sections``, ``check_action`` and ``action_toggle_all``
        alike; a second computation could let the hint line offer a reveal
        that reveals nothing. With no focused entry there is no anchor to
        scope against, so nothing is withheld and the full document renders.

        Every ref comparison goes through ``canonical_trail_ref`` on BOTH
        sides: a trail may spell a member ``aitasks#t42`` while drift reasons
        and ``affects`` use ``aitasks#42``, and raw string comparison would
        silently drop the match."""
        members = {canonical_trail_ref(ref)
                   for ref in trail_entry_refs(self.doc)}
        entry_ref = (canonical_trail_ref(self.entry.get("task"))
                     if self.entry is not None else "")
        records = self.doc.get("evidence") or []
        by_id = {str(rec.get("evidence_id")): rec for rec in records}

        # THE EVIDENCE UNIVERSE — computed once, above the no-anchor branch,
        # because both projections must agree on what "everything" is. A cited
        # ref that resolves to NO record is still document content: it exists
        # only in the citation, never in `evidence`, so any projection built
        # from the records alone silently drops it. `cited_anywhere` keeps
        # discovery order so the universe is deterministic.
        cited_anywhere, cited_seen = [], set()

        def _cite(ref):
            ref = str(ref)
            if ref not in cited_seen:
                cited_seen.add(ref)
                cited_anywhere.append(ref)

        for wave in self.doc.get("waves") or []:
            for item in wave.get("entries") or []:
                for ref in item.get("evidence_refs") or []:
                    _cite(ref)
        for obs in self.doc.get("observations") or []:
            for ref in obs.get("evidence_refs") or []:
                _cite(ref)
        universe = [str(rec.get("evidence_id")) for rec in records]
        universe += [ref for ref in cited_anywhere if ref not in by_id]

        totals = (len(self.doc.get("observations") or []),
                  len(self.doc.get("exclusions") or []),
                  len(records), len(self.drift_reasons))

        if not entry_ref:
            # No anchor: everything is in scope, nothing is withheld. Resolved
            # here rather than compensated for in `_sections` so the one
            # partition stays the single truth its consumers rely on — and
            # built from `universe`, so "Showing the full trail." is true of
            # unresolved refs too.
            return {
                "entry_drift": list(self.drift_reasons),
                "unowned_drift": [], "other_drift": [],
                "entry_obs": list(self.doc.get("observations") or []),
                "unowned_obs": [], "other_obs": [],
                "shown_evidence": [(ref, by_id.get(ref), "")
                                   for ref in universe],
                "other_evidence": [],
                "exclusions": self.doc.get("exclusions") or [],
                "totals": totals,
                "withheld": 0,
            }

        by_ref = trail_drift_by_ref(self.drift_reasons)
        entry_drift = list(by_ref.get(entry_ref, []))
        unowned_drift, other_drift = [], []
        for reason in self.drift_reasons:
            _code, task_ref, _detail = reason
            if not task_ref or task_ref == "-":
                unowned_drift.append(reason)
                continue
            key = canonical_trail_ref(task_ref)
            if key == entry_ref:
                continue                      # already in entry_drift
            (other_drift if key in members else unowned_drift).append(reason)

        entry_obs, unowned_obs, other_obs = [], [], []
        for obs in self.doc.get("observations") or []:
            affects = obs.get("affects") or []
            if isinstance(affects, str):
                affects = [affects]
            refs = {canonical_trail_ref(ref) for ref in affects}
            if entry_ref in refs:
                entry_obs.append(obs)
            elif refs & members:
                other_obs.append(obs)
            else:
                unowned_obs.append(obs)

        # (ref, record-or-None, provenance) in a stable order: the entry's own
        # citations first, then what the displayed observations pull in, then
        # the uncited records.
        shown_evidence, seen = [], set()

        def _show(ref, provenance):
            ref = str(ref)
            if ref in seen:
                return
            seen.add(ref)
            shown_evidence.append((ref, by_id.get(ref), provenance))

        for ref in self.entry.get("evidence_refs") or []:
            _show(ref, "")
        for obs in entry_obs + unowned_obs:
            for ref in obs.get("evidence_refs") or []:
                _show(ref, f"cited by {obs.get('observation_id', '?')}")
        for rec in records:
            if str(rec.get("evidence_id")) not in cited_seen:
                _show(rec.get("evidence_id"), "trail-level (uncited)")
        # Drawn from `universe`, so an unresolved ref owned by another entry is
        # counted and revealed like any other withheld record. Same
        # (ref, record, provenance) shape as `shown_evidence`, so the reveal
        # renders both through one path.
        other_evidence = [(ref, by_id.get(ref), "")
                          for ref in universe if ref not in seen]

        return {
            "entry_drift": entry_drift,
            "unowned_drift": unowned_drift,
            "other_drift": other_drift,
            "entry_obs": entry_obs,
            "unowned_obs": unowned_obs,
            "other_obs": other_obs,
            "shown_evidence": shown_evidence,
            "other_evidence": other_evidence,
            "exclusions": self.doc.get("exclusions") or [],
            "totals": totals,
            "withheld": (len(other_drift) + len(other_obs)
                         + len(other_evidence)),
        }

    def _sections(self) -> Text:
        text = Text()

        def head(label):
            if text.plain:
                text.append("\n\n")
            text.append(label, style="bold underline")
            text.append("\n")

        def line(label, value):
            if value in (None, "", [], {}):
                return
            text.append(f"{label}: ", style="bold")
            if isinstance(value, list):
                value = "; ".join(str(v) for v in value)
            text.append(f"{value}\n")

        def drift_bullet(reason, suffix=""):
            code, task_ref, detail = reason
            where = f" {task_ref}" if task_ref and task_ref != "-" else ""
            text.append(f"• {code}{where}: {detail}{suffix}\n")

        def more(count, noun):
            if count:
                plural = "" if count == 1 else "s"
                text.append(f"… {count} more {noun}{plural}\n")

        scope = self._scope()
        full = self.show_all or self.entry is None

        if self.entry is not None:
            head(f"Entry {self.entry.get('task', '?')}")
            line("classification", self.entry.get("classification"))
            line("confidence", self.entry.get("confidence"))
            line("rationale", self.entry.get("rationale"))
            line("expected outcome", self.entry.get("expected_outcome"))
            line("why order matters", self.entry.get("why_order_matters"))
            line("caveats", self.entry.get("caveats"))
        if self.wave is not None:
            head(f"Wave W{self.wave.get('ordinal', '?')} · "
                 f"{self.wave.get('title', '')}")
            line("purpose", self.wave.get("purpose"))
            line("why now", self.wave.get("why_now"))
            line("consequence of delay", self.wave.get("consequence_of_delay"))

        drift = (scope["entry_drift"] + scope["unowned_drift"]
                 + (scope["other_drift"] if full else []))
        if drift:
            label = ("Drift reasons" if full
                     else "Drift affecting this entry")
            head(f"{label} ({len(drift)})")
            for reason in scope["entry_drift"]:
                drift_bullet(reason)
            for reason in scope["unowned_drift"]:
                drift_bullet(reason, "  [trail-level]")
            for reason in (scope["other_drift"] if full else []):
                drift_bullet(reason)
            if not full:
                more(len(scope["other_drift"]), "reason for other entries")

        narrative = self.doc.get("narrative") or {}
        head(f"Trail: {self.doc.get('title', '?')}")
        line("problem", narrative.get("problem_statement"))
        line("recommendation", narrative.get("recommendation_summary"))
        # `overview` (t1505_3) is rendered as its own field rather than through
        # `trail_summary_text`: that resolver picks ONE of the two for the
        # single-slot summary pane, and using it here would hide the required
        # `recommendation_summary` whenever an overview exists.
        line("overview", narrative.get("overview"))
        line("method note", narrative.get("method_note"))
        line("caveats", narrative.get("caveats"))

        unowned_ids = {id(obs) for obs in scope["unowned_obs"]}
        for obs in (scope["entry_obs"] + scope["unowned_obs"]
                    + (scope["other_obs"] if full else [])):
            mark = " [trail-level]" if id(obs) in unowned_ids else ""
            head(f"Observation: {obs.get('kind', '?')}{mark}")
            line("statement", obs.get("statement"))
            line("affects", obs.get("affects"))
        if not full:
            more(len(scope["other_obs"]),
                 "observation not affecting this entry")

        # Withheld records are appended AFTER the shown ones rather than
        # re-sorted into document order, so toggling `a` never reshuffles what
        # is already on screen — same reason the observation buckets keep
        # their order above.
        shown = list(scope["shown_evidence"])
        if full:
            shown += list(scope["other_evidence"])
        if shown:
            head("Evidence")
            for ref, rec, provenance in shown:
                suffix = f" — {provenance}" if provenance else ""
                if rec is None:
                    text.append(f"• {ref} (unresolved){suffix}\n")
                    continue
                text.append(f"• {rec.get('evidence_id', '?')} "
                            f"({rec.get('source_type', '?')}): "
                            f"{rec.get('summary', '')}{suffix}\n")
            if not full:
                more(len(scope["other_evidence"]), "evidence record")

        if scope["exclusions"]:
            head("Exclusions")
            for exc in scope["exclusions"]:
                text.append(f"• {exc.get('task', '?')} "
                            f"[{exc.get('reason_code', '?')}] "
                            f"{exc.get('reason', '')}\n")

        # ALWAYS rendered. An omitted section and a failed render look
        # identical to a reader — a lite trail legitimately has no
        # observations, exclusions or relations — so the totals state the
        # zeroes explicitly and the mode line says which projection is on
        # screen (t1505_2).
        obs_n, exc_n, ev_n, drift_n = scope["totals"]
        if text.plain:
            text.append("\n\n")
        text.append(f"Trail totals: {obs_n} observations · {exc_n} "
                    f"exclusions · {ev_n} evidence · {drift_n} drift "
                    f"reasons\n")
        if self.show_all:
            text.append("Showing the full document — press a to scope back "
                        "to this entry.\n")
        elif self.entry is None:
            text.append("Showing the full trail.\n")
        elif scope["withheld"]:
            text.append("Showing what concerns this entry — press a for the "
                        "full document.\n")
        else:
            text.append("Showing the full trail.\n")
        return text

    def compose(self):
        with Container(id="trail_detail_dialog"):
            with VerticalScroll(id="trail_detail_body"):
                yield Static(self._sections(), id="trail_detail_text")
            yield Button("Close", id="btn_trail_detail_close")

    def check_action(self, action: str, parameters):
        if action == "toggle_all":
            # Live while revealed too, so the user can scope back.
            return self.show_all or bool(self._scope()["withheld"])
        return True

    def action_toggle_all(self):
        # Re-checked here, not only in check_action: a binding gate is not an
        # action guard — the action stays reachable through the command
        # palette and a remap.
        if not self.show_all and not self._scope()["withheld"]:
            return
        self.show_all = not self.show_all
        self.query_one("#trail_detail_text", Static).update(self._sections())
        self.refresh_bindings()

    @on(Button.Pressed, "#btn_trail_detail_close")
    def close_button(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class TrailSummaryScreen(ModalScreen):
    """The By-Trail summary, full and scrollable (t1505_1).

    The bottom pane shows a fixed six rows of the same prose; this is the
    read-it-all surface behind `v`. It is constructed with the **already
    resolved** text rather than a trail document, so it cannot disagree with
    the pane about which trail's summary is on screen — `_refresh_trail_summary`
    resolves once and both surfaces render that one value.

    Modeled on TrailDetailScreen: own DEFAULT_CSS (it is pushed by an App whose
    CSS it cannot rely on), a plain `escape` binding, and no `_shortcuts_scope`,
    so `lib/shortcut_scopes.py` needs no manifest entry."""

    DEFAULT_CSS = """
    TrailSummaryScreen {
        align: center middle;
    }
    #trail_summary_dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #trail_summary_modal_body {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
    ]

    def __init__(self, summary: str, title: str = ""):
        super().__init__()
        self.summary = summary or ""
        self.trail_title = title or ""

    def compose(self):
        with Container(id="trail_summary_dialog"):
            header = (f"Trail summary — {self.trail_title}"
                      if self.trail_title else "Trail summary")
            yield Static(Text(header, style="bold"))
            with VerticalScroll(id="trail_summary_modal_body"):
                yield Static(Text(self.summary))
            yield Button("Close", id="btn_trail_summary_close")

    @on(Button.Pressed, "#btn_trail_summary_close")
    def close_button(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)
