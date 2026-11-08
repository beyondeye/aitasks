#!/usr/bin/env python3
"""`ait sitrep tui` — the sitrep store in readable form (t2211_1).

The read-only half of the sitrep TUI: the repository's persisted todo list
grouped Pick now / Next / Waiting (Recently done and Dismissed on `d`), the
situation text per theme, an item's details with its context map, read-only
pointer following, and the Q&A log. Writes, harvest/refresh, the agent requests
and the window placement are later children of t2211 (t2211_2..4).

Rules this module keeps:

* **Read only.** Nothing here writes the store; the store is read lock-free,
  the way the store's own read verbs read it (the writer's atomic rename gives
  a whole-old-or-whole-new view).
* **Store text is untrusted.** Every store string reaches the screen as plain
  text (``rich.text.Text`` option prompts, ``Static(Content(...))``,
  ``TextArea``), never parsed as markup (t2017), and every pointer is
  re-validated by ``sitrep_tui_model.follow_pointer`` before it is followed.
* **Readable, not internal.** Rows and details say what to do about an item
  and how (``sitrep_tui_model.NEXT_STEPS``, the one mapping), never the
  store's kind/state words; sources carry plain labels, KEY receipts hidden.
  A click only selects a row; Enter opens it (``SelectOnClickList``).
* **Reload by content.** An interval timer hashes ``todo.md`` / ``qa.md`` off
  the event loop; only a changed digest reparses. An unchanged tick still
  refreshes the time-dependent age labels, without reparsing. A store that
  stops parsing keeps the last good view under a banner.

The store is ``<canonical root>/.aitask-sitrep`` (see ``sitrep_tui_model``).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HERE.parent
for _p in (str(_SCRIPTS_DIR), str(_SCRIPTS_DIR / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rich.text import Text  # noqa: E402
from textual import events  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402
from textual.content import Content  # noqa: E402
from textual.screen import Screen  # noqa: E402
from textual.widgets import Markdown, OptionList, Static, TextArea  # noqa: E402
from textual.widgets.option_list import Option  # noqa: E402

import sitrep_cli  # noqa: E402
import sitrep_harvest as sh  # noqa: E402
import sitrep_todo as st  # noqa: E402
from guarded_dismiss import GuardedDismissMixin, is_active_screen  # noqa: E402
from multirow_footer import MultiRowFooter  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402
from sitrep_tui import sitrep_tui_model as model  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402

#: Seconds between store polls (a hash of two small files, off the event loop).
RELOAD_INTERVAL = 2.0

#: Main-screen actions; hidden (and inert) while a sub-screen is on top.
_MAIN_ACTIONS = frozenset({"open_item", "toggle_closed", "qa_log", "toggle_situation"})


def _footer() -> MultiRowFooter:
    footer = MultiRowFooter(hint_action="open_shortcuts_editor")
    footer.can_focus = False
    return footer


def _row(label: str) -> Text:
    """A list row as plain text (the one-line cut is `#st-list`'s CSS)."""
    return Text(label)


def _text(value: str) -> Content:
    """Plain store text as a Static renderable — never parsed as markup."""
    return Content(value)


class SelectOnClickList(OptionList):
    """An OptionList where a mouse click only SELECTS (highlights) a row.

    Opening is Enter's job -- the footer-visible "Details" / "Open" binding,
    which fires the list's own ``action_select`` -- so ``OptionSelected``
    stays the one open path and a stray click never opens anything.
    ``OptionList._on_click`` highlights AND selects; ``prevent_default`` stops
    Textual's MRO walk before it runs (t2211_8)."""

    async def _on_click(self, event: events.Click) -> None:
        event.prevent_default()
        idx = event.style.meta.get("option")
        if idx is None or not 0 <= idx < self.option_count:
            return
        if not self.get_option_at_index(idx).disabled:
            self.highlighted = idx


#: Width of a details label column ("What to do  ").
_LABEL_W = 12


def _section(name: str) -> Content:
    return Content.assemble((name, "bold underline"))


def _field(label: str, value: str, indent: str = "") -> Content:
    """``label`` styled, ``value`` plain: store text is a plain-text part of
    ``Content.assemble``, never markup (t2017)."""
    if not value:
        return Content.assemble((f"{indent}{label}", "bold"))
    return Content.assemble((f"{indent}{label}".ljust(_LABEL_W), "bold"), value)


#: The browsing screens' Enter. `priority`: the focused list's own `enter`
#: (action `select`, hidden) would otherwise shadow it in the footer. Active only
#: while the links list has focus and a selectable option -- elsewhere it falls
#: through untouched -- and it fires the list's own `select`, so the screen's
#: OptionSelected handler stays the one path.
_OPEN_BINDING = Binding("enter", "open_link", "Open", priority=True)

_SPLIT_BINDINGS = [
    _OPEN_BINDING,
    Binding("escape", "close", "Back"),
    Binding("tab", "app.focus_next", "Text/links"),
    Binding("shift+tab", "app.focus_previous", "", show=False),
]

_SPLIT_CSS = """
{cls} .sp-title {{ background: $boost; padding: 0 1; height: auto; }}
{cls} .sp-text {{ height: 1fr; padding: 0 1; }}
{cls} .sp-text:focus {{ background: $boost 40%; }}
{cls} .sp-links {{ height: auto; max-height: 50%; }}
"""


class _OpenLinkMixin:
    """A footer-visible Enter over the screen's links list (see _OPEN_BINDING)."""

    _links_id = ""

    def _links(self) -> OptionList:
        return self.query_one(f"#{self._links_id}", OptionList)

    def _link_ready(self) -> bool:
        try:
            ol = self._links()
        except Exception:  # noqa: BLE001 - not composed yet / closing
            return False
        opt = ol.highlighted_option
        return self.app.focused is ol and opt is not None and not opt.disabled

    def check_action(self, action: str, parameters: tuple) -> "bool | None":
        if action == "open_link":
            return self._link_ready()
        return super().check_action(action, parameters)

    def action_open_link(self) -> None:
        if self._link_ready():
            self._links().action_select()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self.refresh_bindings()

    def on_descendant_focus(self, event) -> None:
        self.refresh_bindings()


# -- the item details ------------------------------------------------------------

class ItemDetailScreen(_OpenLinkMixin, ShortcutsMixin, GuardedDismissMixin, Screen):
    """One item: fields, outcome age, context map, and its sources and links.

    Split layout: the text scrolls in its own focusable pane above the links
    list, so a long context never hides the links and focusing the list never
    scrolls the text away (`tab` moves between them). The screen shows the
    snapshot taken when it opened; only the age line follows the clock.
    """

    _shortcuts_scope = "sitrep_tui.detail"
    _links_id = "sd-links"
    DEFAULT_CSS = _SPLIT_CSS.format(cls="ItemDetailScreen")
    BINDINGS = list(_SPLIT_BINDINGS)

    def __init__(self, store: st.TodoStore, qa: "st.QaLog | None", num: int,
                 root: str, store_dir: str, refresh_check: "str | None" = None) -> None:
        super().__init__()
        self._store = store
        self._qa = qa
        self._num = num
        self._root = root
        self._store_dir = store_dir
        self._item = store.items[num]
        self._ctx = store.contexts.get(num)
        # The app's refresh-check map of the SAME store generation (both are
        # set together in `_apply`), passed in rather than re-scanned per open.
        self._step = model.next_step(self._item, refresh_check)

    # composition -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(_text(f"{self._item.cid} · {self._item.title}"),
                     classes="sp-title", id="sd-title")
        with VerticalScroll(classes="sp-text", id="sd-text"):
            yield Static(self.body_content(model.resolve_now()), id="sd-body")
        yield SelectOnClickList(*self._link_options(), classes="sp-links", id="sd-links")
        yield _footer()

    def on_mount(self) -> None:
        self.query_one("#sd-links", OptionList).focus()

    def body_content(self, now: _dt.datetime) -> Content:
        """The item in labelled sections: styled labels, plain values."""
        it, step = self._item, self._step
        lines = [_section("Item"),
                 _field("What to do", step.what),
                 _field("How", step.how)]
        about = model.about_text(it.ref)
        if about:
            lines.append(_field("About", about))
        lines.append(_field("Checked", "never" if it.checked_at in ("", "never") else
                            f"{it.checked_at} ({model.age_text(it.checked_at, now)})"))
        lines.append(_field("Outcome", it.outcome or "—"))
        lines.append(Content(""))
        ctx = self._ctx
        if ctx is None:
            lines.append(Content("No context entry."))
        else:
            lines.append(_section("Context"))
            lines.append(_field("Background", ctx.background or "—"))
            if ctx.origin:
                lines.append(_field("Origin", ""))
                for key, value in ctx.origin:
                    lines.append(_field(model.ORIGIN_LABELS.get(key, key), value, "  "))
            if ctx.theme:
                lines.append(_field("Theme", ctx.theme))
            review = model.review_line(self._store_dir, ctx)
            if review:
                lines.append(Content(review))
        return Content("\n").join(lines)

    def body_text(self, now: _dt.datetime) -> str:
        return self.body_content(now).plain

    def _link_options(self) -> list:
        opts = []
        ctx = self._ctx
        if ctx is not None:
            for i, (stype, ptr) in enumerate(ctx.sources):
                label = model.source_label(self._store_dir, stype, ptr)
                if label is None:   # a KEY receipt: store bookkeeping, hidden
                    continue
                opts.append(Option(Text(label), id=f"src:{i}"))
                if stype == "capture" and model.case_extras(self._store_dir, ptr):
                    opts.append(Option(Text("  Raw input (review case)"), id=f"raw:{i}"))
            for n in ctx.related:
                other = self._store.items.get(n)
                if other is None:
                    opts.append(Option(Text(f"Related: item c{n} (no longer in the store)"),
                                       id=f"relx:{n}", disabled=True))
                else:
                    opts.append(Option(Text(f"Related: item c{n} — {other.title}"),
                                       id=f"rel:{n}"))
        for n in model.referenced_by(self._store, self._num):
            opts.append(Option(Text(f"Mentioned by item c{n} — {self._store.items[n].title}"),
                               id=f"ref:{n}"))
        for idx, entry in model.qa_backlinks(self._qa, self._num):
            opts.append(Option(Text(f"Q&A entry {entry.ts}"), id=f"qa:{idx}"))
        if not opts:
            opts.append(Option(Text("No sources or links"), id="none", disabled=True))
        return opts

    # behaviour -------------------------------------------------------------

    def refresh_ages(self, now: _dt.datetime) -> None:
        """The clock moved: re-render the age line (the snapshot is unchanged)."""
        self.query_one("#sd-body", Static).update(self.body_content(now))

    def action_close(self) -> None:
        self.dismiss()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        kind, _, arg = (event.option.id or "").partition(":")
        app = self.app
        if kind == "src":
            stype, ptr = self._ctx.sources[int(arg)]
            self._follow(lambda: model.follow_pointer(self._root, self._store_dir,
                                                      stype, ptr))
        elif kind == "raw":
            _stype, ptr = self._ctx.sources[int(arg)]
            extras = model.case_extras(self._store_dir, ptr)
            if extras:
                rel, sha = extras
                self._follow(lambda: model.follow_raw(self._store_dir, rel, sha))
        elif kind in ("rel", "ref"):
            app.open_item(int(arg))
        elif kind == "qa":
            # The entry THIS screen listed (its own snapshot), never a position
            # re-read from the current log: a restore + append reuses positions.
            app.open_qa_entry(self._qa.entries[int(arg)])

    def _follow(self, fn) -> None:
        self.run_worker(self._follow_worker(fn), group="pointer", exclusive=True)

    async def _follow_worker(self, fn) -> None:
        try:
            view = await asyncio.to_thread(fn)
        except Exception as e:  # noqa: BLE001 - follow_* never raise; belt and braces
            view = model.PointerView("pointer", error=f"Could not follow: {e}")
        if is_active_screen(self):
            self.app.push_screen(PointerViewerScreen(view))


# -- the pointer viewer ----------------------------------------------------------

class PointerViewerScreen(ShortcutsMixin, GuardedDismissMixin, Screen):
    """What one pointer resolved to: read-only text with line numbers, or --
    for task / plan files and `.md` file pointers -- rendered Markdown, with
    `m` switching to the raw text. A pointer with a `#L` line starts raw (the
    line is what it points at). Markdown links are never opened."""

    _shortcuts_scope = "sitrep_tui.viewer"
    DEFAULT_CSS = """
    PointerViewerScreen #pv-title { background: $boost; padding: 0 1; height: auto; }
    PointerViewerScreen #pv-note { padding: 0 1; height: auto; color: $warning; }
    PointerViewerScreen #pv-note.hidden { display: none; }
    PointerViewerScreen #pv-text { height: 1fr; }
    PointerViewerScreen #pv-md { height: 1fr; padding: 0 1; }
    PointerViewerScreen #pv-md:focus { background: $boost 40%; }
    """
    BINDINGS = [Binding("escape", "close", "Back"),
                Binding("m", "toggle_markdown", "Rendered/raw")]

    def __init__(self, view: model.PointerView) -> None:
        super().__init__()
        self.view = view
        #: Showing the rendered Markdown (only possible for a markdown view).
        self.rendered = bool(view.markdown and not view.error and not view.focus_line)

    def compose(self) -> ComposeResult:
        yield Static(_text(self.view.title), id="pv-title")
        note = "\n".join(x for x in (self.view.error, self.view.note) if x)
        yield Static(_text(note), id="pv-note", classes="" if note else "hidden")
        if self._has_markdown():
            with VerticalScroll(id="pv-md"):
                # open_links=False: a link in a repo file is shown, never opened.
                yield Markdown(model.markdown_source(self.view.text), open_links=False)
        yield TextArea(self.view.text, read_only=True, show_line_numbers=True,
                       line_number_start=max(1, self.view.first_line), id="pv-text")
        yield _footer()

    def _has_markdown(self) -> bool:
        return bool(self.view.markdown and not self.view.error)

    def on_mount(self) -> None:
        area = self.query_one("#pv-text", TextArea)
        if self.view.focus_line:
            row = min(max(0, self.view.focus_line - self.view.first_line),
                      max(0, area.document.line_count - 1))
            area.move_cursor((row, 0), center=True)
        self._show()

    def _show(self) -> None:
        area = self.query_one("#pv-text", TextArea)
        if self._has_markdown():
            md = self.query_one("#pv-md", VerticalScroll)
            md.display = self.rendered
            area.display = not self.rendered
            (md if self.rendered else area).focus()
        else:
            area.focus()

    def check_action(self, action: str, parameters: tuple) -> "bool | None":
        if action == "toggle_markdown":
            return self._has_markdown()
        return super().check_action(action, parameters)

    def action_toggle_markdown(self) -> None:
        if self._has_markdown():
            self.rendered = not self.rendered
            self._show()

    def action_close(self) -> None:
        self.dismiss()


# -- the Q&A log -----------------------------------------------------------------

class QaLogScreen(_OpenLinkMixin, ShortcutsMixin, GuardedDismissMixin, Screen):
    """The Q&A log, newest entry first (the snapshot taken when it opened)."""

    _shortcuts_scope = "sitrep_tui.qa"
    _links_id = "ql-list"
    DEFAULT_CSS = """
    QaLogScreen #ql-title { background: $boost; padding: 0 1; height: auto; }
    QaLogScreen #ql-list { height: 1fr; }
    """
    BINDINGS = [_OPEN_BINDING, Binding("escape", "close", "Back")]

    def __init__(self, qa: "st.QaLog | None", qa_error: str) -> None:
        super().__init__()
        self._qa = qa
        self._qa_error = qa_error

    def compose(self) -> ComposeResult:
        entries = model.qa_newest_first(self._qa)
        title = f"Q&A log — {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
        if self._qa_error:
            title += f"\nQ&A log unusable: {self._qa_error}"
            if self._qa is not None:
                title += " — showing the last good log"
        yield Static(_text(title), id="ql-title")
        opts = []
        for idx, entry in entries:
            cids = ",".join(f"c{n}" for n in entry.items) or "-"
            opts.append(Option(Text(f"{entry.ts}  items: {cids} — "
                                    f"{model.qa_first_line(entry)}"), id=f"qa:{idx}"))
        if not opts:
            opts.append(Option(Text("No Q&A entries"), id="none", disabled=True))
        yield SelectOnClickList(*opts, id="ql-list")
        yield _footer()

    def on_mount(self) -> None:
        self.query_one("#ql-list", OptionList).focus()

    def action_close(self) -> None:
        self.dismiss()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        kind, _, arg = (event.option.id or "").partition(":")
        if kind == "qa":
            self.app.open_qa_entry(self._qa.entries[int(arg)])


class QaEntryScreen(_OpenLinkMixin, ShortcutsMixin, GuardedDismissMixin, Screen):
    """One Q&A entry: its body (scrollable) above links to the items it names.

    Shows the entry object it was given -- the one the user selected -- and
    says so when that entry is no longer in the current log."""

    _shortcuts_scope = "sitrep_tui.qa_entry"
    _links_id = "qe-links"
    DEFAULT_CSS = _SPLIT_CSS.format(cls="QaEntryScreen")
    BINDINGS = list(_SPLIT_BINDINGS)

    def __init__(self, entry: st.QaEntry, store: "st.TodoStore | None",
                 in_current_log: bool = True) -> None:
        super().__init__()
        self._entry = entry
        self._store = store
        self._in_current_log = in_current_log

    def compose(self) -> ComposeResult:
        title = f"Q&A {self._entry.ts}"
        if not self._in_current_log:
            title += " — no longer in the current log (the store changed since it was listed)"
        yield Static(_text(title), classes="sp-title", id="qe-title")
        with VerticalScroll(classes="sp-text", id="qe-text"):
            yield Static(_text("\n".join(self._entry.body) or "(empty)"), id="qe-body")
        opts = []
        items = self._store.items if self._store is not None else {}
        for n in self._entry.items:
            if n in items:
                opts.append(Option(Text(f"c{n}: {items[n].title}"), id=f"item:{n}"))
            else:
                opts.append(Option(Text(f"c{n} (not in store)"), id=f"itemx:{n}",
                                   disabled=True))
        if not opts:
            opts.append(Option(Text("This entry names no items"), id="none", disabled=True))
        yield SelectOnClickList(*opts, classes="sp-links", id="qe-links")
        yield _footer()

    def on_mount(self) -> None:
        self.query_one("#qe-links", OptionList).focus()

    def action_close(self) -> None:
        self.dismiss()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        kind, _, arg = (event.option.id or "").partition(":")
        if kind == "item":
            self.app.open_item(int(arg))


# -- the app ---------------------------------------------------------------------

class _SitrepScreen(Screen):
    """The default screen. ``AUTO_FOCUS = ""``: startup focus is claimed
    explicitly (`tui_conventions.md`, "Startup focus")."""

    AUTO_FOCUS = ""


class SitrepTuiApp(TuiSwitcherMixin, ShortcutsMixin, App):
    """The repository's sitrep store, read-only."""

    _shortcuts_scope = "sitrep_tui"
    TITLE = "ait sitrep tui"

    CSS = """
    #st-header { background: $boost; padding: 0 1; height: auto; }
    #st-banner { background: $error 30%; padding: 0 1; height: auto; display: none; }
    #st-banner.visible { display: block; }
    #st-situation { height: auto; max-height: 6; padding: 0 1; }
    #st-situation.hidden { display: none; }
    /* The column header: outside the list so it never scrolls; the left inset
       is the list's border + padding, so its columns sit over the rows'. */
    #st-columns { height: 1; padding: 0 1 0 2; text-style: bold; text-wrap: nowrap;
                  text-overflow: ellipsis; }
    /* One line per row, cut with an ellipsis (OptionList wraps by default and
       ignores Text.no_wrap): a short pane shows twice the rows. */
    #st-list { height: 1fr; text-wrap: nowrap; text-overflow: ellipsis; }
    """

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("q", "quit", "Quit"),
        # `priority`: the focused list's own hidden `enter` would otherwise
        # shadow this one in the footer. Inert (falls through) on sub-screens
        # and with no item highlighted -- see check_action.
        Binding("enter", "open_item", "Details", priority=True),
        Binding("d", "toggle_closed", "Done/dismissed"),
        Binding("l", "qa_log", "Q&A log"),
        Binding("s", "toggle_situation", "Situation"),
    ]

    def __init__(self, root: str, store_dir: str,
                 reload_interval: float = RELOAD_INTERVAL) -> None:
        super().__init__()
        self.current_tui_name = "sitrep_tui"
        self.root = root
        self.store_dir = store_dir
        self._reload_interval = reload_interval
        #: The last GOOD parse of each file; kept when a later read fails.
        self.store: "st.TodoStore | None" = None
        self.qa: "st.QaLog | None" = None
        self.todo_error = ""
        self.qa_error = ""
        self._digest = None
        self._show_closed = False
        self._show_situation = True
        self._loaded_at = ""
        #: Visible item cids in list order, and the label each row shows.
        self._order: list = []
        self._row_labels: dict = {}
        #: Width of the Item column, and refresh's per-item checks (the
        #: "What to do" guidance follows what refresh really re-checks).
        self._cid_w = model.COLUMNS[0][1]
        self._checks: dict = {}

    # composition -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("", id="st-header")
        yield Static("", id="st-banner")
        with VerticalScroll(id="st-situation"):
            yield Static("", id="st-situation-text")
        yield Static(_text(model.header_text()), id="st-columns")
        yield SelectOnClickList(id="st-list")
        yield _footer()

    def get_default_screen(self) -> Screen:
        return _SitrepScreen()

    def on_mount(self) -> None:
        # One small synchronous read so the first frame already shows the store.
        self._apply(model.load_snapshot(self.store_dir))
        self.set_interval(self._reload_interval, self._poll_store)
        self.call_after_refresh(self._claim_startup_focus)

    def _claim_startup_focus(self) -> None:
        try:
            self._list().focus()
        except Exception:  # noqa: BLE001 - the app may already be closing
            pass

    def _main(self) -> Screen:
        return self.screen_stack[0]

    def _list(self) -> OptionList:
        return self._main().query_one("#st-list", OptionList)

    # data ------------------------------------------------------------------

    async def _poll_store(self) -> None:
        """One reload tick. Never raises (a raising timer callback would end the
        app): a read failure is reported by the snapshot, anything else skips
        this tick."""
        try:
            snap = await asyncio.to_thread(model.load_snapshot, self.store_dir,
                                           self._digest)
            if snap is None:
                self._refresh_ages()
            else:
                self._apply(snap)
        except Exception as e:  # noqa: BLE001
            self.log.error(f"sitrep tui: reload tick failed: {e}")

    def _apply(self, snap: model.Snapshot) -> None:
        self._digest = snap.digest
        self.todo_error = snap.todo_error
        self.qa_error = snap.qa_error
        if snap.store is not None:
            self.store = snap.store
        if snap.qa is not None:
            self.qa = snap.qa
        self._checks = model.refresh_checks(self.store)
        self._loaded_at = _dt.datetime.now().strftime("%H:%M:%S")
        self._render_header()
        self._render_banner()
        self._render_situation()
        self._rebuild_list()

    def _render_header(self) -> None:
        if self.store is None:
            state = "store unusable"
        elif not self.store.items:
            state = "no items yet"
        else:
            now = sum(1 for it in self.store.items.values()
                      if it.group == "now" and it.state == "open")
            n = len(self.store.items)
            state = f"{n} item{'s' if n != 1 else ''} · {now} open in Pick now"
        self._main().query_one("#st-header", Static).update(
            _text(f"Sitrep · {self.root}\n{state} · read {self._loaded_at}"))

    def _render_banner(self) -> None:
        lines = []
        if self.todo_error:
            lines.append(f"Store unusable: {self.todo_error}")
            if self.store is not None:
                lines.append("Showing the last good view.")
            lines.append("Restore the last good generation: "
                         "./.aitask-scripts/aitask_sitrep_todo.sh restore todo")
        if self.qa_error:
            lines.append(f"Q&A log unusable: {self.qa_error} "
                         "(./.aitask-scripts/aitask_sitrep_todo.sh restore qa)")
        banner = self._main().query_one("#st-banner", Static)
        banner.update(_text("\n".join(lines)))
        banner.set_class(bool(lines), "visible")

    def _render_situation(self) -> None:
        situations = self.store.situations if self.store is not None else {}
        lines = []
        for theme in sorted(situations):
            lines.append(f"#### {theme}")
            lines.extend(situations[theme])
        pane = self._main().query_one("#st-situation", VerticalScroll)
        self._main().query_one("#st-situation-text", Static).update(_text("\n".join(lines)))
        pane.set_class(not (lines and self._show_situation), "hidden")

    def _selected_cid(self) -> "str | None":
        try:
            opt = self._list().highlighted_option
        except Exception:  # noqa: BLE001
            return None
        if opt is None or not (opt.id or "").startswith("c"):
            return None
        return opt.id

    def _rebuild_list(self) -> None:
        """Re-render the rows, keeping the highlighted item by cid. A highlighted
        item that vanished (or that the closed toggle hid) hands the highlight to
        the item now at its position, clamped to the last row."""
        ol = self._list()
        prev = self._selected_cid()
        prev_pos = self._order.index(prev) if prev in self._order else None
        now = model.resolve_now()
        options, order, labels = [], [], {}
        self._cid_w = model.cid_width(self.store)
        self._main().query_one("#st-columns", Static).update(
            _text(model.header_text(self._cid_w)))
        if self.store is not None:
            for slot, heading, items in model.group_items(self.store, self._show_closed):
                options.append(Option(Text(f"{heading} ({len(items)})", style="bold"),
                                      id=f"hdr:{slot}", disabled=True))
                for it in items:
                    label = model.row_text(it, now, self._cid_w, self._checks.get(it.num))
                    options.append(Option(_row(label), id=it.cid))
                    order.append(it.cid)
                    labels[it.cid] = label
        ol.clear_options()
        ol.add_options(options)
        self._order, self._row_labels = order, labels
        target = None
        if prev in order:
            target = prev
        elif order:
            target = order[min(prev_pos or 0, len(order) - 1)]
        if target is not None:
            ol.highlighted = ol.get_option_index(target)
        self.refresh_bindings()

    def _refresh_ages(self) -> None:
        """The files did not change but the clock did: relabel only the rows
        whose age text changed (no reparse, no rebuild, highlight kept), and let
        any open details screen re-render its age line."""
        if self.store is None:
            return
        now = model.resolve_now()
        ol = self._list()
        for cid in self._order:
            item = self.store.items.get(int(cid[1:]))
            if item is None:
                continue
            label = model.row_text(item, now, self._cid_w, self._checks.get(item.num))
            if label != self._row_labels.get(cid):
                ol.replace_option_prompt(cid, _row(label))
                self._row_labels[cid] = label
        for screen in self.screen_stack:
            hook = getattr(screen, "refresh_ages", None)
            if callable(hook):
                hook(now)

    # navigation ------------------------------------------------------------

    def open_item(self, num: int) -> None:
        """Item ids are never reused, not even across a restore (the writer's
        rule), so resolving one against the current store is identity-safe."""
        if self.store is None or num not in self.store.items:
            self.notify(f"c{num} is not in the store", severity="warning", markup=False)
            return
        self.push_screen(ItemDetailScreen(self.store, self.qa, num, self.root,
                                          self.store_dir, self._checks.get(num)))

    def open_qa_entry(self, entry: st.QaEntry) -> None:
        """Open the entry the user SELECTED -- the object from the listing
        screen's snapshot. Q&A entries have no id and a restore + append reuses
        positions, so a position is never re-resolved against the current log;
        whether the entry is still there is reported (exact field equality)."""
        current = self.qa.entries if self.qa is not None else []
        self.push_screen(QaEntryScreen(entry, self.store,
                                       in_current_log=entry in current))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "st-list":
            return
        event.stop()
        cid = event.option.id or ""
        if cid.startswith("c"):
            self.open_item(int(cid[1:]))

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "st-list":
            self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple) -> "bool | None":
        if action in _MAIN_ACTIONS and not isinstance(self.screen, _SitrepScreen):
            return False
        if action == "open_item" and self._selected_cid() is None:
            return False
        return super().check_action(action, parameters)

    def action_open_item(self) -> None:
        cid = self._selected_cid()
        if cid is not None and isinstance(self.screen, _SitrepScreen):
            self.open_item(int(cid[1:]))

    def action_toggle_closed(self) -> None:
        self._show_closed = not self._show_closed
        self._rebuild_list()

    def action_toggle_situation(self) -> None:
        self._show_situation = not self._show_situation
        self._render_situation()

    def action_qa_log(self) -> None:
        self.push_screen(QaLogScreen(self.qa, self.qa_error))


def main(argv: "list | None" = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ait sitrep tui", allow_abbrev=False,
        description="Show the repository's sitrep store (read-only).")
    ap.add_argument("--root", default=".", type=sitrep_cli.root_arg,
                    help="project root (a linked aiwork/ worktree maps to the "
                         "main worktree)")
    args = ap.parse_args(argv)
    try:
        root, _ = sh.canonical_root(os.path.abspath(args.root))
    except sh.HarvestFailure as e:
        print(f"ROOT_FAILED:{e}", file=sys.stderr)
        return 1
    # Project-relative config reads (shortcut overrides, tmux defaults).
    os.chdir(root)
    SitrepTuiApp(root, os.path.join(root, sh.STORE_NAME)).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
