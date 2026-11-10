"""sitrep_tui_trails.py - which implementation trails a sitrep task item's task
is in, and the picker that chooses one (t2211_10).

The membership comes from ``trail_links.export_project(root)``: one
``trail_links.py export`` subprocess with cwd = the project root, i.e. the same
frontmatter-driven discovery and content-keyed cache the board and ``ait trails``
use (trail discovery is cwd-relative, while this TUI's root is an argument). A
member is this project's task when its canonical ``<project>#<id>`` ref names
``project.name`` -- the board's ``trail_ref_to_local_id`` rule.

Fail-closed states per task (``TaskTrails.state``):

* ``in`` -- in one or more trails. ``reason`` carries a partial-scan note when
  some trail or task file could not be read: the trails that WERE read are
  still positive evidence, so they are shown and usable;
* ``none`` -- a complete scan found it in no trail;
* ``unknown`` -- the export failed, ``project.name`` is not set, or the scan
  was partial and found nothing for it ("unknown", never "in no trail");
* ``looking`` -- no scan result yet;
* ``off`` -- no scanner configured (test apps), nothing is shown.

Trail text (names, handles) is untrusted: it reaches the screen as ``Text``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.content import Content
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from cross_repo_notation import parse_ref
from guarded_dismiss import GuardedModalScreen
from sitrep_tui.sitrep_tui_widgets import SelectOnClickList

#: Seconds between background membership rescans (t2211_10). Measured on this
#: repository (18 trails): a warm export takes ~0.7 s, an uncached one ~3.6 s,
#: all of it in a thread worker.
TRAILS_RESCAN_INTERVAL = 60.0

IN, NONE, UNKNOWN, LOOKING, OFF = "in", "none", "unknown", "looking", "off"


@dataclass(frozen=True)
class TrailRef:
    """One trail a task is in: its handle, display name and wave ordinals."""
    handle: str
    name: str
    waves: tuple = ()

    def _wave_text(self, prefix: str) -> str:
        return ", ".join(f"{prefix}{w}" for w in self.waves)

    def label(self) -> str:
        """The details / picker row: ``Name (art:handle) — wave 1``."""
        text = f"In trail: {self.name} ({self.handle})"
        if self.waves:
            word = "wave" if len(self.waves) == 1 else "waves"
            text += f" — {word} {self._wave_text('')}"
        return text

    def short(self) -> str:
        """The body line's part: ``Name (w1)``."""
        return f"{self.name} ({self._wave_text('w')})" if self.waves else self.name


@dataclass(frozen=True)
class TaskTrails:
    state: str
    trails: tuple = ()
    reason: str = ""

    def handles(self) -> tuple:
        return tuple(t.handle for t in self.trails)

    def find(self, handle: str) -> "TrailRef | None":
        return next((t for t in self.trails if t.handle == handle), None)


TASK_TRAILS_OFF = TaskTrails(OFF)
TASK_TRAILS_LOOKING = TaskTrails(LOOKING)


@dataclass(frozen=True)
class Membership:
    """One scan's result. ``ok`` False: no usable export (``reason`` says why)."""
    ok: bool
    reason: str = ""
    partial: str = ""
    by_task: dict = field(default_factory=dict)

    def lookup(self, task_id: "str | None") -> TaskTrails:
        if not task_id:
            return TaskTrails(UNKNOWN, reason="no local task")
        if not self.ok:
            return TaskTrails(UNKNOWN, reason=self.reason)
        found = self.by_task.get(task_id, ())
        if found:
            return TaskTrails(IN, tuple(found), self.partial)
        if self.partial:
            return TaskTrails(UNKNOWN, reason=self.partial)
        return TaskTrails(NONE)


def _ordinals(value) -> tuple:
    if not isinstance(value, list):
        return ()
    return tuple(v for v in value if isinstance(v, int) and not isinstance(v, bool))


def membership_from_export(data, errors) -> Membership:
    """``trail_links.export_project``'s ``(export, errors)`` -> a Membership.

    Pure. ``data`` is the export dict (or None); ``errors`` the typed
    ``ProjectScanError`` rows (``.kind`` / ``.detail``)."""
    details = "; ".join(str(getattr(e, "detail", "") or getattr(e, "kind", ""))
                        for e in errors or [])
    if not isinstance(data, dict):
        return Membership(False, details or "the trail scan printed no result")
    local = str(data.get("local_project") or "")
    if not local:
        return Membership(False, "project.name is not set — trail members "
                                 "cannot be matched to this project's tasks")
    by_task: dict = {}
    partial = []
    for trail in data.get("trails") or []:
        if not isinstance(trail, dict) or not isinstance(trail.get("handle"), str):
            continue
        handle = trail["handle"]
        if trail.get("load_error"):
            partial.append(f"{handle} did not load")
            continue
        name = str(trail.get("name") or handle)
        waves = trail.get("waves") if isinstance(trail.get("waves"), dict) else {}
        per_task: dict = {}
        for ref in trail.get("members") or []:
            parsed = parse_ref(str(ref or ""))
            if not parsed or parsed[0] != local:
                continue
            ords = per_task.setdefault(parsed[1], [])
            for o in _ordinals(waves.get(ref)):
                if o not in ords:
                    ords.append(o)
        for task_id, ords in per_task.items():
            by_task.setdefault(task_id, []).append(
                TrailRef(handle, name, tuple(sorted(ords))))
    if data.get("unreadable") or data.get("scan_errors"):
        partial.append("some task files could not be read")
    # A PARTIAL error row restates the per-trail failures above in its own
    # words; keep one note per cause.
    note = "; ".join(dict.fromkeys(partial))
    if errors and not note:
        note = details
    return Membership(True, partial=note,
                      by_task={k: tuple(sorted(v, key=lambda t: (t.name, t.handle)))
                               for k, v in by_task.items()})


def scan_membership(root: str) -> Membership:
    """The membership of every local task of ``root``. Blocking (one export
    subprocess): thread workers only. Never raises."""
    try:
        import trail_links
        export, errors = trail_links.export_project(str(root))
        return membership_from_export(export.data if export else None, errors)
    except Exception as e:  # noqa: BLE001 - a scan failure is "unknown", never fatal
        return Membership(False, f"trail scan failed: {e}")


# -- the picker ----------------------------------------------------------------

class TrailPickerDialog(GuardedModalScreen):
    """Choose which of a task's trails to show it in. Returns the handle, or
    None (Cancel / Esc). A click only selects a row; Enter opens it.

    Geometry as ``LabelFilterDialog``: docked buttons, the list fitted to the
    rows the screen leaves, the highlight kept in view after a resize."""

    DEFAULT_CSS = """
    TrailPickerDialog { align: center middle; }
    TrailPickerDialog > Container {
        width: 90%; max-width: 100; min-width: 24; height: auto; max-height: 100%;
        background: $surface; border: thick $accent; padding: 0 1;
    }
    TrailPickerDialog .dlg-title { text-style: bold; color: $accent; height: 1;
                                   text-wrap: nowrap; text-overflow: ellipsis; }
    TrailPickerDialog #tp-list { height: auto; margin: 0; }
    TrailPickerDialog .dlg-buttons { dock: bottom; height: 3; width: 100%;
                                     layout: horizontal; align: center middle; }
    TrailPickerDialog .dlg-buttons Button { width: auto; min-width: 10; margin: 0 1; }
    """
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, task_id: str, trails) -> None:
        super().__init__()
        self.task_id = task_id
        self.trails = tuple(trails)

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(Content(f"Show t{self.task_id} in which trail?"),
                         classes="dlg-title")
            yield SelectOnClickList(
                *(Option(Text(t.label()), id=f"trail:{t.handle}") for t in self.trails),
                id="tp-list")
            with Container(classes="dlg-buttons"):
                yield Button("Cancel", variant="default", id="tp-cancel")

    def on_mount(self) -> None:
        self._fit_list()
        lst = self.query_one("#tp-list", OptionList)
        lst.highlighted = 0 if self.trails else None
        lst.focus()

    def on_resize(self, event) -> None:
        self._fit_list()

    def _fit_list(self) -> None:
        box = self.query_one(Container)
        chrome = box.styles.gutter.height
        for selector in (".dlg-title", ".dlg-buttons"):
            height = self.query_one(selector).styles.height
            chrome += int(height.value) if height is not None and height.is_cells else 1
        lst = self.query_one("#tp-list", OptionList)
        lst.styles.max_height = max(3, self.size.height - chrome)
        self.call_after_refresh(lst.scroll_to_highlight)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        _kind, _, handle = (event.option.id or "").partition(":")
        self.dismiss(handle or None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
