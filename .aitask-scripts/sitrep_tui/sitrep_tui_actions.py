"""sitrep_tui_actions.py - the sitrep TUI's actions (t2211_3).

The deterministic work the sitrep agent used to do for the TUI's user, as keys:

* **harvest + refresh** (`r`, and once at startup): `aitask_sitrep_harvest.sh
  all` then `aitask_sitrep_refresh.sh`, one run at a time;
* **dismiss** (`x`): `aitask_sitrep_todo.sh dismiss --expect-rev <the rev the
  user saw>`; `STALE:` re-reads and asks again, never a blind retry;
* **restore** (`R`): `restore <kind> --if-damaged` -- the writer re-checks the
  live file under its lock, so a repair that landed while the confirm dialog
  was open is never rolled back;
* **respawn agent** (`A`): `aitask_sitrep.sh open`, the one spawn path;
* **launches** from an item: `/aitask-pick` (`p`, pick items only), the task in
  the board (`b`), and the push command a push reminder SHOWS (`P`, never run).

Rules: every store write goes through the store's one writer, with
``cwd=<root>`` and without ``AITASK_SITREP_DIR`` (the store this TUI reads).
Store text is plain ``Content``, never markup (t2017). A binding gate is not a
guard: every action re-resolves its item against the CURRENT store and
re-checks its precondition. A details screen is a snapshot, so an item whose
rev moved since it opened is refreshed and launches nothing until the user
presses the key again.
"""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.content import Content
from rich.text import Text
from textual.widgets import Button, Input, SelectionList, Static
from textual.widgets.selection_list import Selection

import agent_launch_utils as alu
import sitrep_cli
import sitrep_todo as st
from agent_command_screen import build_pick_screen
from guarded_dismiss import GuardedModalScreen
from monitor.sitrep_close import (
    HARVEST_ALL_TIMEOUT,
    SITREP_OPEN_TIMEOUT,
    run_owned_group,
)
from sitrep_tui import sitrep_tui_model as model
from tui_clipboard import copy_to_system_clipboard

WRITER_SH = model.SCRIPTS_DIR / "aitask_sitrep_todo.sh"
HARVEST_SH = model.SCRIPTS_DIR / "aitask_sitrep_harvest.sh"
REFRESH_SH = model.SCRIPTS_DIR / "aitask_sitrep_refresh.sh"
SITREP_SH = model.SCRIPTS_DIR / "aitask_sitrep.sh"

#: Hard ceiling on one writer call (it waits for the store mutex itself).
WRITER_TIMEOUT = 60.0

#: Seconds between agent-role probes (one `list-panes -a`, off the event loop).
AGENT_POLL_INTERVAL = 3.0

#: Item actions: shown on the main list and on an item's details.
ITEM_ACTIONS = frozenset({"pick_task", "open_in_board", "show_push", "dismiss_item"})
#: Main-screen actions added by this module.
MAIN_ACTIONS = frozenset({"restore_store", "respawn_agent"})
#: Store-wide actions shown on the main list AND on an item's details (the
#: details' "How" text names the refresh key).
LIST_OR_DETAIL_ACTIONS = frozenset({"harvest_refresh"})

#: (action, default key, footer label); the app's BINDINGS are built from it
#: and the "How" texts name the EFFECTIVE key (`keybinding_registry`).
ACTION_BINDINGS = (
    ("harvest_refresh", "r", "Refresh"),
    ("dismiss_item", "x", "Dismiss"),
    ("pick_task", "p", "Pick"),
    ("open_in_board", "b", "Board"),
    ("show_push", "P", "Push cmd"),
    ("restore_store", "R", "Restore"),
    ("respawn_agent", "A", "Respawn agent"),
)
#: NEXT_STEPS placeholder -> action.
_KEY_PLACEHOLDERS = {"k_pick": "pick_task", "k_board": "open_in_board",
                     "k_push": "show_push", "k_dismiss": "dismiss_item",
                     "k_refresh": "harvest_refresh"}

_ACTION_LABEL = {"pick_task": "Pick", "open_in_board": "Open in board",
                 "show_push": "Push command", "dismiss_item": "Dismiss"}


def writer_env() -> dict:
    env = dict(os.environ)
    env.pop("AITASK_SITREP_DIR", None)
    return env


# -- reading the harvest `all` output ---------------------------------------------

def summarize_harvest_all(rc: int, out: str) -> tuple:
    """``(ok, verdict, detail lines)`` for `aitask_sitrep_harvest.sh all`.

    `all` prints one final line PER RECORD (`HARVESTED:` / `HARVEST_NONE:` /
    `HARVEST_FAILED:`), so the counts are summed over every final line -- the
    single-run parser (`parse_harvest_output`) keeps only the last one. Not ok
    on a non-zero exit, a runner ``ERROR:`` line or any failed record."""
    added = existing = harvested = 0
    failed, lines = [], []
    runner_error = ""
    for raw in (out or "").splitlines():
        line = raw.strip()
        if line.startswith("ERROR:"):
            runner_error = line[len("ERROR:"):]
            continue
        head, sep, rest = line.partition(":")
        if not sep:
            continue
        parts = rest.split("|")
        if head == "HARVESTED":
            harvested += 1
            fields = dict(p.partition("=")[::2] for p in parts[1:])
            added += _int(fields.get("added"))
            existing += _int(fields.get("existing"))
        elif head == "HARVEST_FAILED":
            failed.append(rest)
            lines.append(f"harvest failed: {rest}")
        elif head == "HARVEST_WARN":
            lines.append(f"harvest warning: {rest}")
        elif head == "HARVEST_REVIEW":
            cid = parts[1] if len(parts) > 1 else "?"
            lines.append(f"kept for review: {cid} (the full output is in the store)")
        elif head == "HARVEST_ITEM" and len(parts) >= 3 and parts[2] == "added":
            lines.append(f"harvested: {parts[1]} {parts[3] if len(parts) > 3 else ''}".rstrip())
    if runner_error:
        lines.append(f"harvest: {runner_error}")
    ok = rc == 0 and not failed and not runner_error
    if not ok:
        why = runner_error or (f"{len(failed)} record(s) failed" if failed else f"exit {rc}")
        return False, f"Harvest failed: {why}", lines
    if harvested:
        return True, f"Harvested: {added} added, {existing} existing", lines
    return True, "Nothing new to harvest", lines


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def refresh_lines(report: "model.RefreshReport") -> list:
    lines = [f"refresh warning: {w}" for w in report.warns]
    for row in report.items:
        cid, _, rest = row.partition("|")
        lines.append(f"refreshed {cid}: {rest}")
    return lines


def _last_line(out: str, *heads: str) -> str:
    for line in reversed((out or "").splitlines()):
        line = line.strip()
        if line.split(":", 1)[0] in heads:
            return line
    return ""


def _tail(out: str, n: int = 4) -> str:
    rows = [ln for ln in (out or "").splitlines() if ln.strip()]
    return "\n".join(rows[-n:])


# -- dialogs -------------------------------------------------------------------------

_DIALOG_CSS = """
{cls} {{ align: center middle; }}
{cls} > Container {{
    width: 90%; max-width: 90; min-width: 24; height: auto; max-height: 90%;
    background: $surface; border: thick $accent; padding: 1 2;
}}
{cls} .dlg-title {{ text-style: bold; color: $accent; margin: 0 0 1 0; }}
{cls} .dlg-notice {{ color: $warning; margin: 0 0 1 0; height: auto; }}
{cls} .dlg-notice.hidden {{ display: none; }}
{cls} .dlg-body {{ height: auto; max-height: 24; margin: 0 0 1 0; }}
{cls} .dlg-buttons {{ width: 100%; height: auto; layout: horizontal; align: center middle; }}
{cls} .dlg-buttons Button {{ width: auto; min-width: 10; margin: 0 1; }}
"""


class DismissDialog(GuardedModalScreen):
    """Dismiss one item, with a reason. Returns the reason, or None (cancel).

    Cancel writes nothing; the caller runs the writer with the rev passed in --
    the one the user saw -- so a change in between comes back `STALE:`."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="DismissDialog")
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, item: "st.Item", notice: str = "", reason: str = "") -> None:
        super().__init__()
        self.item = item
        self._notice = notice
        self._reason = reason

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(Content(f"Dismiss {self.item.cid} · {self.item.title}"),
                         classes="dlg-title")
            yield Static(Content(self._notice), id="dd-notice",
                         classes="dlg-notice" + ("" if self._notice else " hidden"))
            yield Static(Content("Reason (recorded as the item's outcome):"))
            yield Input(value=self._reason, placeholder="e.g. done by hand, no longer needed",
                        id="dd-reason")
            with Container(classes="dlg-buttons"):
                yield Button("Dismiss", variant="error", id="dd-confirm")
                yield Button("Cancel", variant="default", id="dd-cancel")

    def on_mount(self) -> None:
        self.query_one("#dd-reason", Input).focus()

    def _confirm(self) -> None:
        reason = self.query_one("#dd-reason", Input).value.strip()
        if not reason:
            notice = self.query_one("#dd-notice", Static)
            notice.update(Content("A reason is required."))
            notice.remove_class("hidden")
            return
        self.dismiss(reason)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dd-confirm":
            self._confirm()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmDialog(GuardedModalScreen):
    """A yes/no question. Returns True only for the confirm button."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="ConfirmDialog")
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, title: str, question: str, confirm: str = "Confirm") -> None:
        super().__init__()
        self._title = title
        self._question = question
        self._confirm = confirm

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(Content(self._title), classes="dlg-title")
            yield Static(Content(self._question), classes="dlg-body")
            with Container(classes="dlg-buttons"):
                yield Button(self._confirm, variant="warning", id="cd-confirm")
                yield Button("Cancel", variant="default", id="cd-cancel")

    def on_mount(self) -> None:
        self.query_one("#cd-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "cd-confirm")

    def action_cancel(self) -> None:
        self.dismiss(False)


class ResultDialog(GuardedModalScreen):
    """What an action did: a verdict per step plus the detail lines."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="ResultDialog") + """
    ResultDialog.-failed > Container { border: thick $error; }
    """
    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    def __init__(self, title: str, verdicts: list, lines: list, failed: bool = False) -> None:
        super().__init__()
        self._title = title
        self.verdicts = list(verdicts)
        self.lines = list(lines)
        if failed:
            self.add_class("-failed")

    def body_text(self) -> str:
        return "\n".join([*self.verdicts, *([""] if self.lines else []), *self.lines])

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(Content(self._title), classes="dlg-title")
            with VerticalScroll(classes="dlg-body"):
                yield Static(Content(self.body_text()), id="rd-body")
            with Container(classes="dlg-buttons"):
                yield Button("Close", variant="default", id="rd-close")

    def on_mount(self) -> None:
        self.query_one("#rd-close", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class PushCommandDialog(GuardedModalScreen):
    """The command that pushes a branch -- SHOWN and copyable, never run.

    There is no run path here at all: the only buttons copy and close."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="PushCommandDialog") + """
    PushCommandDialog #pc-command { background: $boost; padding: 0 1; margin: 0 0 1 0; }
    """
    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    def __init__(self, item: "st.Item", command: str, note: str) -> None:
        super().__init__()
        self.item = item
        self.command = command
        self.note = note

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(Content(f"Push for {self.item.cid} · {self.item.title}"),
                         classes="dlg-title")
            yield Static(Content("Run this yourself (the TUI never pushes):"))
            yield Static(Content(self.command), id="pc-command")
            yield Static(Content(self.note), classes="dlg-notice" + ("" if self.note else " hidden"))
            with Container(classes="dlg-buttons"):
                yield Button("Copy", variant="primary", id="pc-copy")
                yield Button("Close", variant="default", id="pc-close")

    def on_mount(self) -> None:
        self.query_one("#pc-copy", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pc-copy":
            copy_to_system_clipboard(self.app, self.command)
            self.app.notify("Push command copied", markup=False)
            return
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class LabelFilterDialog(GuardedModalScreen):
    """Pick the labels the main list is filtered by (t2211_9).

    Returns the checked labels in display order, ``[]`` for Clear, or None for
    Cancel. Space toggles (the SelectionList owns it), Enter applies. Labels
    come from task files -- untrusted text -- so each prompt is a ``Text``,
    never parsed as markup. An active label no longer on any item is still
    listed (count 0) so it can be unchecked. The filter is per-session UI
    state: this dialog writes nothing."""

    # The controls must stay reachable in a short pane and with many labels:
    # the buttons are DOCKED at the bottom, the chrome is one row each, and the
    # list is capped (`_fit_list`) to what the screen leaves after the dialog's
    # border and its other rows, so it scrolls inside itself instead of running
    # under the buttons or off the screen. Pinned by real clicks and region
    # checks at several pane sizes and label counts (t2211_9 review).
    DEFAULT_CSS = _DIALOG_CSS.format(cls="LabelFilterDialog") + """
    LabelFilterDialog > Container { max-height: 100%; padding: 0 1; }
    LabelFilterDialog .dlg-title { margin: 0; }
    LabelFilterDialog #lf-help { height: 1; text-wrap: nowrap; text-overflow: ellipsis; }
    LabelFilterDialog .dlg-buttons { dock: bottom; height: 3; }
    LabelFilterDialog #lf-list { height: auto; margin: 0; }
    """
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, counts: list, active: frozenset) -> None:
        super().__init__()
        known = dict(counts)
        for label in active:
            known.setdefault(label, 0)
        #: ``[(label, n)]`` in display order (sorted by label).
        self.rows = sorted(known.items())
        self.active = frozenset(active)

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(Content("Filter by task labels"), classes="dlg-title")
            # One line: a short pane must still fit the list and the buttons.
            yield Static(Content("Space toggles · Enter applies · task items with ANY "
                                 "checked label"), id="lf-help")
            yield SelectionList[str](
                *(Selection(Text(f"{model.label_display(label)} ({n})"), label,
                            label in self.active)
                  for label, n in self.rows),
                id="lf-list")
            with Container(classes="dlg-buttons"):
                yield Button("Apply", variant="primary", id="lf-apply")
                yield Button("Clear", variant="default", id="lf-clear")
                yield Button("Cancel", variant="default", id="lf-cancel")

    def on_mount(self) -> None:
        self._fit_list()
        self.query_one("#lf-list", SelectionList).focus()

    def on_resize(self, event) -> None:
        self._fit_list()

    def _fit_list(self) -> None:
        """Cap the list at the rows the screen leaves for it: the screen height
        minus the dialog's own border/padding and its title, help and button
        rows (their CSS heights, so this does not wait for a layout pass).
        Never below 3 rows (one label row inside the list's border)."""
        box = self.query_one(Container)
        chrome = box.styles.gutter.height
        for selector in (".dlg-title", "#lf-help", ".dlg-buttons"):
            height = self.query_one(selector).styles.height
            chrome += int(height.value) if height is not None and height.is_cells else 1
        lst = self.query_one("#lf-list", SelectionList)
        lst.styles.max_height = max(3, self.size.height - chrome)
        # A shrink leaves the scroll offset where it was, so the highlighted
        # label can end up outside the smaller viewport (and Space would toggle
        # a row the user cannot see). Once the new layout is in, bring the
        # existing highlight back into view; the selection is unchanged.
        self.call_after_refresh(lst.scroll_to_highlight)

    def selected(self) -> list:
        checked = set(self.query_one("#lf-list", SelectionList).selected)
        return [label for label, _n in self.rows if label in checked]

    def on_key(self, event) -> None:
        # SelectionList consumes space; Enter is free there, so it applies.
        if event.key == "enter" and isinstance(self.focused, SelectionList):
            event.stop()
            self.dismiss(self.selected())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "lf-apply":
            self.dismiss(self.selected())
        elif event.button.id == "lf-clear":
            self.dismiss([])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# -- the actions ---------------------------------------------------------------------

class SitrepActionsMixin:
    """The action flows of ``SitrepTuiApp``. Host contract: ``root``,
    ``store``, ``todo_error``, ``qa_error``, ``_checks``, ``_poll_store()``,
    ``_selected_cid()``, ``_is_main_screen(screen)``, ``open_item(num)``,
    ``_render_header()``, ``_render_banner()``."""

    def _init_actions(self, runner=None, roles_probe=None, own_session=None,
                      startup_harvest: bool = False) -> None:
        #: async (argv, timeout) -> (rc, out); the default runs the script in
        #: its own process group (killed with the app).
        self._runner = runner or self._default_runner
        #: sync () -> (ok, agent_pane, tui_pane); None: not in tmux.
        self._roles_probe = roles_probe
        #: sync () -> session name or None.
        self._own_session = own_session
        self._startup_harvest = startup_harvest
        self._harvest_inflight = False
        self._agent_poll_busy = False
        #: unknown | running | absent
        self.agent_state = "unknown"
        #: (HH:MM, ok) of the last harvest + refresh run, or None.
        self._last_refresh = None

    async def _default_runner(self, argv, timeout: float):
        return await run_owned_group([str(a) for a in argv], timeout=timeout,
                                     cwd=self.root, env=writer_env())

    def _start_actions(self) -> None:
        """Called from the host's on_mount."""
        if self._roles_probe is not None:
            self.call_after_refresh(self._kick_agent_poll)
            self.set_interval(AGENT_POLL_INTERVAL, self._kick_agent_poll)
        if self._startup_harvest:
            self.run_worker(self._harvest_refresh(show_panel=False),
                            group="sitrep-harvest", exit_on_error=False)

    # -- keys ------------------------------------------------------------------

    def action_keys(self) -> dict:
        """The effective keys for the NEXT_STEPS placeholders (user overrides
        included), so the "How" text names the key that really works."""
        import keybinding_registry
        defaults = {a: k for a, k, _ in ACTION_BINDINGS}
        keys = {}
        for ph, action in _KEY_PLACEHOLDERS.items():
            try:
                keys[ph] = keybinding_registry.resolve_key(
                    self._shortcuts_scope, action, defaults[action]) or defaults[action]
            except Exception:  # noqa: BLE001 - a hint, never fatal
                keys[ph] = defaults[action]
        return keys

    def key_for(self, action: str) -> str:
        placeholder = {v: k for k, v in _KEY_PLACEHOLDERS.items()}.get(action)
        if placeholder:
            return self.action_keys()[placeholder]
        default = {a: k for a, k, _ in ACTION_BINDINGS}[action]
        try:
            import keybinding_registry
            return keybinding_registry.resolve_key(self._shortcuts_scope, action,
                                                   default) or default
        except Exception:  # noqa: BLE001
            return default

    # -- item resolution (freshness) -----------------------------------------------

    def _item_action_ok(self, action: str, item: "st.Item | None") -> bool:
        if item is None or self.store is None or self.todo_error:
            return False
        if action == "pick_task":
            return (model.classify(item, self._checks.get(item.num)) == "pick"
                    and model.task_ref_id(item) is not None)
        if action == "open_in_board":
            return model.task_ref_id(item) is not None
        if action == "show_push":
            return st.parse_push_ref(item.ref) is not None
        if action == "dismiss_item":
            return item.state in ("open", "unknown")
        return False

    def _current_action_item(self) -> "st.Item | None":
        """The item an item action would act on, resolved against the CURRENT
        store (bindings only -- the action itself uses _resolve_action_item)."""
        screen = self._top_screen()
        if self.store is None or screen is None:
            return None
        num = getattr(screen, "item_num", None)
        if num is not None:
            return self.store.items.get(num)
        if self._is_main_screen(screen):
            cid = self._selected_cid()
            return self.store.items.get(int(cid[1:])) if cid else None
        return None

    def _resolve_action_item(self, action: str) -> "st.Item | None":
        """The item ``action`` may act on NOW, or None (refused, with a toast).

        From a details screen the snapshot's item is re-resolved by id (ids
        are never reused) and compared by rev (revs are store-wide and never
        reused): a moved rev means the item may mean something else, so the
        details are refreshed and nothing runs until the key is pressed
        again."""
        if self.store is None or self.todo_error:
            self.notify(f"The store is unusable — press {self.key_for('restore_store')} "
                        "to restore it", severity="warning", markup=False)
            return None
        screen = self.screen
        num = getattr(screen, "item_num", None)
        if num is not None:
            cur = self.store.items.get(num)
            if cur is None:
                self.call_later(self._close_details, screen)
                self.notify(f"c{num} is no longer in the store", severity="warning",
                            markup=False)
                return None
            if cur.rev != screen.item_rev:
                self.call_later(self._replace_details, screen, num)
                self.notify(f"c{num} changed since these details were opened — details "
                            f"refreshed; press {self.key_for(action)} again",
                            severity="warning", markup=False)
                return None
            item = cur
        elif self._is_main_screen(screen):
            cid = self._selected_cid()
            item = self.store.items.get(int(cid[1:])) if cid else None
        else:
            return None
        if not self._item_action_ok(action, item):
            what = item.cid if item is not None else "this row"
            self.notify(f"{_ACTION_LABEL[action]} does not apply to {what}",
                        severity="warning", markup=False)
            return None
        return item

    async def _close_details(self, screen) -> None:
        if self.screen is screen:
            await screen.dismiss()

    async def _replace_details(self, screen, num: int) -> None:
        if self.screen is screen:
            await screen.dismiss()
        self.open_item(num)

    # -- harvest + refresh ---------------------------------------------------------

    def action_harvest_refresh(self) -> None:
        screen = self._top_screen()
        if not (self._is_main_screen(screen) or getattr(screen, "item_num", None) is not None):
            return
        if self._harvest_inflight:
            self.notify("A harvest + refresh is already running", severity="warning")
            return
        self.run_worker(self._harvest_refresh(show_panel=True), group="sitrep-harvest",
                        exit_on_error=False)

    async def _harvest_refresh(self, show_panel: bool) -> None:
        if self._harvest_inflight:
            return
        self._harvest_inflight = True
        self.refresh_bindings()
        try:
            rc, out = await self._runner([HARVEST_SH, "all", "--root", self.root],
                                         HARVEST_ALL_TIMEOUT)
            h_ok, h_verdict, h_lines = summarize_harvest_all(rc, out)
            # Refresh runs even after a failed harvest: it re-checks the items
            # already in the store and needs nothing from this harvest.
            rc2, out2 = await self._runner(
                [REFRESH_SH, "--root", self.root, "--budget", f"{model.REFRESH_BUDGET:g}"],
                model.REFRESH_TIMEOUT)
            report = model.parse_refresh_output(rc2, out2)
        finally:
            self._harvest_inflight = False
        ok = h_ok and report.ok
        self._last_refresh = (_dt.datetime.now().strftime("%H:%M"), ok)
        await self._poll_store()
        self._render_header()
        self.refresh_bindings()
        verdicts = [h_verdict, report.verdict()]
        if show_panel:
            self.push_screen(ResultDialog("Harvest + refresh", verdicts,
                                          h_lines + refresh_lines(report), failed=not ok))
        else:
            self.notify(" · ".join(verdicts), severity="information" if ok else "warning",
                        markup=False)

    # -- dismiss -------------------------------------------------------------------

    def action_dismiss_item(self) -> None:
        item = self._resolve_action_item("dismiss_item")
        if item is not None:
            self.run_worker(self._dismiss_flow(item), group="sitrep-dismiss",
                            exclusive=True, exit_on_error=False)

    async def _dismiss_flow(self, item: "st.Item", notice: str = "", reason: str = "") -> None:
        while True:
            reason = await self.push_screen_wait(DismissDialog(item, notice, reason))
            if not reason:
                return                          # cancel: nothing written
            rc, out = await self._runner(
                [WRITER_SH, "dismiss", item.cid, "--outcome", f"user: {reason}",
                 "--expect-rev", str(item.rev)], WRITER_TIMEOUT)
            line = _last_line(out, "STATE", "STALE")
            if rc == 0 and line.startswith("STATE:"):
                await self._poll_store()
                self._close_details_of(item.num)
                self.notify(f"{item.cid} dismissed", markup=False)
                return
            if rc == 0 and line.startswith("STALE:"):
                await self._poll_store()
                cur = self.store.items.get(item.num) if self.store is not None else None
                if cur is None or cur.state not in ("open", "unknown"):
                    state = cur.state if cur is not None else "gone"
                    self.notify(f"{item.cid} changed meanwhile and is now {state} — "
                                "nothing dismissed", severity="warning", markup=False)
                    return
                notice = (f"{item.cid} changed since you looked (rev {item.rev}→{cur.rev}); "
                          "check it and confirm again.")
                item = cur
                continue
            if rc == 3:
                notice = "The store is busy (another writer holds it) — confirm to retry."
                continue
            hint = (f" Press {self.key_for('restore_store')} to restore it."
                    if rc == 4 else "")
            self.push_screen(ResultDialog(
                f"Dismiss {item.cid} failed", [f"Nothing was dismissed (exit {rc}).{hint}"],
                [_tail(out)], failed=True))
            return

    def _close_details_of(self, num: int) -> None:
        screen = self.screen
        if getattr(screen, "item_num", None) == num:
            self.call_later(self._close_details, screen)

    # -- restore -------------------------------------------------------------------

    def action_restore_store(self) -> None:
        if not self._is_main_screen(self.screen):
            return
        if not (self.todo_error or self.qa_error):
            self.notify("The store reads fine — nothing to restore", markup=False)
            return
        self.run_worker(self._restore_flow(), group="sitrep-restore", exclusive=True,
                        exit_on_error=False)

    async def _restore_flow(self) -> None:
        kinds = [k for k, err in (("todo", self.todo_error), ("qa", self.qa_error)) if err]
        if not kinds:
            return
        names = " and ".join(f"{k}.md" for k in kinds)
        yes = await self.push_screen_wait(ConfirmDialog(
            "Restore the sitrep store",
            f"Restore {names} from the last good generation? A damaged file is kept "
            "under recovered/. If it was repaired meanwhile, nothing is restored.",
            confirm="Restore"))
        if not yes:
            return
        lines, failed = [], False
        for kind in kinds:
            # --if-damaged: the writer decides under its lock (a repair plus a
            # newer write since this dialog opened must never be rolled back).
            rc, out = await self._runner([WRITER_SH, "restore", kind, "--if-damaged"],
                                         WRITER_TIMEOUT)
            line = _last_line(out, "RESTORED", "RESTORE_NOT_NEEDED")
            if rc == 0 and line.startswith("RESTORED:"):
                fname, _, kept = line[len("RESTORED:"):].partition("|")
                lines.append(f"{fname}: restored the last good generation"
                             + ("" if kept == "no-damaged-copy" else f" (damaged copy: {kept})"))
            elif rc == 0 and line.startswith("RESTORE_NOT_NEEDED:"):
                lines.append(f"{kind}.md is healthy again — nothing restored")
            elif rc == 3:
                failed = True
                lines.append(f"{kind}.md: the store is busy — try again")
            else:
                failed = True
                lines.append(f"{kind}.md: restore failed (exit {rc}) {_tail(out, 2)}".rstrip())
        await self._poll_store()
        self.push_screen(ResultDialog("Restore", lines, [], failed=failed))

    # -- agent status + respawn -----------------------------------------------------

    def _kick_agent_poll(self) -> None:
        if self._roles_probe is None or self._agent_poll_busy:
            return
        self._agent_poll_busy = True
        self.run_worker(self._poll_agent(), group="sitrep-agent", exit_on_error=False)

    async def _poll_agent(self) -> None:
        import asyncio
        try:
            ok, agent, _tui = await asyncio.to_thread(self._roles_probe)
        except Exception:  # noqa: BLE001 - an unknown state, never a crash
            ok, agent = False, None
        finally:
            self._agent_poll_busy = False
        state = "unknown" if not ok else ("running" if agent else "absent")
        if state != self.agent_state:
            self.agent_state = state
            self._render_header()
            self.refresh_bindings()

    def agent_header(self) -> str:
        if self.agent_state == "running":
            return "agent: running"
        if self.agent_state == "absent":
            return f"agent: not running — press {self.key_for('respawn_agent')}"
        return "agent: unknown"

    def action_respawn_agent(self) -> None:
        if not self._is_main_screen(self.screen):
            return
        if self._roles_probe is None:
            self.notify("Not in tmux — run: ait sitrep", severity="warning", markup=False)
            return
        self.run_worker(self._respawn_flow(), group="sitrep-respawn", exclusive=True,
                        exit_on_error=False)

    async def _respawn_flow(self) -> None:
        import asyncio
        try:
            ok, agent, _tui = await asyncio.to_thread(self._roles_probe)
        except Exception:  # noqa: BLE001
            ok, agent = False, None
        if not ok:
            self.notify("Could not check the sitrep agent (tmux query failed)",
                        severity="error", markup=False)
            return
        if agent:
            self.agent_state = "running"
            self._render_header()
            self.refresh_bindings()
            self.notify("The sitrep agent is running", markup=False)
            return
        session = None
        if self._own_session is not None:
            try:
                session = await asyncio.to_thread(self._own_session)
            except Exception:  # noqa: BLE001
                session = None
        if not session:
            self.notify("Could not tell which tmux session this TUI is in",
                        severity="error", markup=False)
            return
        yes = await self.push_screen_wait(ConfirmDialog(
            "Restart the sitrep agent",
            "Start the sitrep agent again beside this TUI?", confirm="Restart"))
        if not yes:
            return
        rc, out = await self._runner(
            [SITREP_SH, "open", "--root", self.root, "--session", session],
            SITREP_OPEN_TIMEOUT)
        msg, severity = sitrep_cli.sitrep_open_message(rc, out)
        self.notify(msg, severity=severity, markup=False)
        self._kick_agent_poll()

    # -- launches --------------------------------------------------------------------

    def action_pick_task(self) -> None:
        item = self._resolve_action_item("pick_task")
        if item is None:
            return
        task_id = model.task_ref_id(item)
        root = Path(self.root)
        if alu.focus_existing_agent_window(task_id, root):
            self.notify(f"Switched to the running agent window for t{task_id}", markup=False)
            return
        screen = build_pick_screen(root, task_id, narrow=True)
        if screen is None:
            self.notify(f"Could not resolve the pick command for t{task_id}",
                        severity="error", markup=False)
            return
        num = item.num

        def on_result(result) -> None:
            if result is None:
                return
            # Re-resolve: the store may have moved while the dialog was open.
            cur = self.store.items.get(num) if self.store is not None else None
            if (cur is None or self.todo_error
                    or not self._item_action_ok("pick_task", cur)
                    or model.task_ref_id(cur) != task_id):
                self.notify(f"c{num} changed while the dialog was open — not launched",
                            severity="warning", markup=False)
                return
            if isinstance(result, alu.TmuxLaunchConfig):
                _pid, err = alu.launch_in_tmux(screen.full_command, result)
                if err:
                    self.notify(f"Launch failed: {err}", severity="error", markup=False)
                    return
                if result.new_window:
                    alu.maybe_spawn_minimonitor(result.session, result.window)
                self.notify(f"Launched /aitask-pick {task_id}", markup=False)
            elif result == "run":
                self.notify("This pane cannot run the agent — choose a tmux window",
                            severity="warning", markup=False)

        self.push_screen(screen, on_result)

    def action_open_in_board(self) -> None:
        item = self._resolve_action_item("open_in_board")
        if item is not None:
            self._board_worker(model.task_ref_id(item))

    @work(thread=True, group="sitrep-board", exclusive=True, exit_on_error=False)
    def _board_worker(self, task_id: str) -> None:
        for msg, severity in open_in_board(self.root, task_id):
            self.call_from_thread(self.notify, msg, severity=severity, markup=False)

    def action_show_push(self) -> None:
        item = self._resolve_action_item("show_push")
        if item is not None:
            self._push_worker(item)

    @work(thread=True, group="sitrep-push", exclusive=True, exit_on_error=False)
    def _push_worker(self, item: "st.Item") -> None:
        branch, _sha = st.parse_push_ref(item.ref)
        command, note = model.push_command(self.root, branch)
        self.call_from_thread(self.push_screen, PushCommandDialog(item, command, note))


def open_in_board(root: str, task_id: str) -> list:
    """Show ``t<task_id>`` in this project's board, moving the client there.

    Blocking (tmux): thread workers only. Returns ``(message, severity)``
    notices -- none after a successful switch to another session (nobody is
    looking at this pane then).

    The destination is this TUI's own session when it belongs to ``root``,
    else the project's live session; it is re-checked right before the launch
    (a session name can be reused -- `finish_linked_trail_jump`'s rule). A
    different session needs `switch-client`, which only reaches this client
    when this process is a pane of the gateway server."""
    project = Path(root)
    own = alu.current_tmux_session()
    if own is None:
        return [(f"Not in an aitasks tmux session — run: ./ait board --focus {task_id}",
                 "warning")]
    dest = own if alu.session_owned_by(own, project) else alu.live_project_session(project)
    if not dest:
        return [("No tmux session runs this project — start one with: ait ide", "error")]
    if not alu.session_owned_by(dest, project):
        return [(f"The tmux session '{dest}' changed before the jump — try again", "error")]
    ok, msg = alu.launch_or_focus_board(dest, project, task_id)
    if not ok:
        return [(f"Could not open t{task_id} in the board: {msg}", "error")]
    if dest != own:
        if not alu.switch_client_to(dest):
            return [(f"The board opened in session '{dest}' but switching there failed — "
                     f"switch with: tmux switch-client -t ={dest}", "error")]
        return []
    if msg:
        return [(msg, "warning")]
    return [(f"Showing t{task_id} in the board", "information")]
