"""Minimonitor's key surface: hint table, key formatter, help entries, help modal.

Minimonitor renders no Footer — its 40-column companion layout surfaces every
binding in the bottom-docked ``#mini-key-hints`` band instead (the
tui_conventions.md "surface the hint in the pane's own text" exception). The
band has two modes (t2212): the **full** band and a **collapsed** one-liner
that names only the toggle and help keys, and ``H`` opens :class:`KeyHelpModal`,
which explains every binding.

**One table drives all three.** The tables below name *actions*, never keys:
the key shown is always the one the App's composed ``BINDINGS`` actually bound
— the post-override list ``ShortcutsMixin`` builds — so a user's rebind reaches
the band, the collapsed line and the help modal from the same source that
dispatches it. Never resolve a key here through
``keybinding_registry.resolve_key("minimonitor", ...)``: the shared actions
(``?``, ``j``, ``q``) live in the ``shared`` scope and that lookup misses their
overrides (tui_conventions.md, the MultiRowFooter ``hint_action`` note).

Overrides take effect when the App is constructed (the shortcut editor says
"restart the TUI to apply"), so rendering once per mode change from the
instance's ``BINDINGS`` is exact.
"""

from __future__ import annotations

from typing import NamedTuple

from rich.cells import cell_len
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.content import Content
from textual.keys import key_to_character
from textual.widgets import Label, Static

from guarded_dismiss import GuardedModalScreen


class HintSeg(NamedTuple):
    """One ``keys:label`` segment of a hint line.

    ``actions`` lists one or more binding actions whose keys are joined with
    ``/`` (``e/E:shadow``); ``suffix`` follows the keys verbatim, for keys that
    are not bindings of this App (``s/↑↓:switch`` — the arrows move focus
    between cards through the list widget itself).
    """

    actions: tuple[str, ...]
    label: str
    suffix: str = ""


#: A rendered line: (separator between its segments, the segments). The
#: separator is per line because the single spaces on some lines are measured
#: choices that buy wrapped rows at narrow widths, not inconsistency.
HintLine = tuple[str, tuple[HintSeg, ...]]


# The full band. Every binding of MiniMonitorApp appears here exactly once —
# the parity is test-pinned (tests/test_minimonitor_key_hints_modes.py), which
# keeps the convention's all-operations requirement true by construction.
#
# The budget is not the row COUNT but the RENDERED height at a NARROW width,
# and it is sharper than it looks. This band is `height: auto` and docked
# bottom, so at width 15 it overflows the screen, gains a scrollbar, loses
# another column to it, and re-wraps WIDER than a naive measurement predicts —
# then paints over row 0 and swallows `#mini-own-agent`, which
# `test_own_header_names_the_session_without_clipping_at_any_width` catches.
# At 40 columns it must stay TEN rows: an eleventh would cost the pane list a
# row at every pane height, which test_minimonitor_top_chrome_render pins.
#
# So MEASURE, never eyeball: render the app at (15, 30) and read
# `#mini-key-hints`'s region height. It must stay ≤ 29. Rich WORD-wraps, so
# word lengths decide, not character counts — which is why the labels are terse
# and why single spaces appear on several lines. Measured for t2212's layout:
#
#     width        15   18   22   40
#     before       28   22   18   10
#     this table   28   22   19   10
#     with ?:rebind 31  22   19   10   (over budget — `?` stays `?:keys`)
#
# History the labels encode:
# * `x`/`H` (t2212) sit on line 1 so they stay visible when short mode clips
#   the band to its first two rows; `i` moved down beside `I` to pay for them.
# * t2175_5 bought the rows `h` and `S` cost: "(followed)" for "(followed
#   agent)" and the glyph-first detect line ("≈strip =raw" still names both
#   modes) each save one wrapped row at (15, 30).
# * t1705_7 shortened the `j:`/`m:` line — at width 15 the band's most expensive
#   — to pay for `f`, `Z` and a wider `P` label. That headroom is spent on naming
#   BOTH states in `P:parked/frozen`: this band is the only binding surface, so a
#   user hunting for "how do I show parked agents again?" has nowhere else to
#   look. t2054 removed `R` again (restore/re-pick are the frozen-agent viewer's
#   own keys, reached with `tab`).
# * `P` shares a line with `p` deliberately (t1685): unrelated actions that
#   differ only in case read correctly side by side.
# * `o` (t2073_4) sits beside `e/E`: both open a helper bound to the followed
#   agent.
FULL_HINT_LINES: tuple[HintLine, ...] = (
    (" ", (
        HintSeg(("toggle_key_hints",), "hide"),
        HintSeg(("show_key_help",), "help"),
        HintSeg(("quit",), "quit"),
        HintSeg(("focus_sibling_pane",), "agent"),
    )),
    (" ", (
        HintSeg(("show_task_info",), "info"),
        HintSeg(("show_own_task_info",), "info (followed)"),
    )),
    ("  ", (
        HintSeg(("switch_to",), "switch", suffix="/↑↓"),
        HintSeg(("send_enter_to_sibling",), "send"),
    )),
    ("  ", (
        HintSeg(("cycle_compare_mode",), "detect ≈strip =raw"),
    )),
    ("  ", (
        HintSeg(("tui_switcher",), "switcher"),
        HintSeg(("switch_to_monitor",), "monitor"),
    )),
    ("  ", (
        HintSeg(("kill_own_agent",), "kill"),
        HintSeg(("pick_next_for_own",), "next"),
        HintSeg(("launch_shadow", "launch_shadow_pick"), "shadow"),
        HintSeg(("open_scratchpad",), "notes"),
    )),
    ("  ", (
        HintSeg(("pick_concerns",), "concerns"),
        HintSeg(("pick_task_by_number",), "pick"),
        HintSeg(("toggle_parked_visibility",), "parked/frozen"),
    )),
    ("  ", (
        HintSeg(("freeze_current",), "freeze"),
        HintSeg(("freeze_all",), "all"),
        HintSeg(("harvest_close",), "harvest"),
    )),
    (" ", (
        HintSeg(("toggle_review_loop",), "loop"),
        HintSeg(("open_shortcuts_editor",), "keys"),
        HintSeg(("toggle_multi_session",), "multi"),
        HintSeg(("open_sitrep",), "sitrep"),
    )),
    ("  ", (
        HintSeg(("toggle_mark",), "mark ★ (followed agent)"),
    )),
)

#: The collapsed band's labelled rung. `x:keys H:help` is 13 cells, so with the
#: defaults it fits one row down to width 15 (13 content cells after padding).
COLLAPSED_HINT_LINE: HintLine = (" ", (
    HintSeg(("toggle_key_hints",), "keys"),
    HintSeg(("show_key_help",), "help"),
))


def key_display(key: str) -> str:
    """Render a binding key the way every minimonitor key surface shows it.

    The base key becomes its character when it has a printable, non-blank one
    (``question_mark`` → ``?``) and otherwise keeps its name (``space``,
    ``tab``, ``enter``, ``f12``), so the default band keeps the exact names its
    hints have always used. ``ctrl`` becomes a ``^`` prefix exactly as Textual's
    ``App.get_key_display`` renders it (``ctrl+x`` → ``^x``,
    ``ctrl+shift+f12`` → ``shift+^f12``); other modifiers stay ``+``-joined
    (``alt+x``). Override keys are arbitrary ``event.key`` names captured by the
    shortcut editor, so this is what keeps a rebound chord short.
    """
    if not key:
        return ""
    modifiers, base = Binding(key, "").parse_key()
    if not base:  # a bare "+" splits to ["", ""]
        return key
    char = key_to_character(base)
    shown = char if char and char.isprintable() and not char.isspace() else base
    if "ctrl" in modifiers:
        modifiers = [m for m in modifiers if m != "ctrl"]
        shown = f"^{shown}"
    return "+".join([*modifiers, shown])


def binding_keymap(bindings) -> dict[str, str]:
    """``{action: key}`` over an App's composed bindings (first binding wins)."""
    keymap: dict[str, str] = {}
    for b in bindings:
        action = getattr(b, "action", None)
        key = getattr(b, "key", None)
        if action and key and action not in keymap:
            keymap[action] = key
    return keymap


def _render_seg(seg: HintSeg, keymap: dict[str, str]) -> str:
    keys = "/".join(key_display(keymap[a]) for a in seg.actions)
    return f"{keys}{seg.suffix}:{seg.label}"


def render_hints(lines: tuple[HintLine, ...], keymap: dict[str, str]) -> str:
    """Render hint lines, joined by newlines, with the keys ``keymap`` binds."""
    return "\n".join(
        sep.join(_render_seg(seg, keymap) for seg in segs)
        for sep, segs in lines
    )


def render_collapsed(keymap: dict[str, str], content_width: int | None) -> str:
    """The collapsed band's text: the first rung that fits ``content_width``.

    1. ``<toggle>:keys <help>:help`` — the labelled line;
    2. ``<toggle> <help>`` — keys only, so both ACTIVE shortcuts stay visible
       when a rebind to a long chord would not fit with labels.

    ``content_width`` is the band's measured content width (pane width minus
    its gutter); ``None`` — before layout, or an App built without ``__init__``
    in a test — means rung 1.

    The band is always ONE row whatever this returns: ``#mini-key-hints
    .collapsed`` sets ``height: 1`` with no wrapping and an ellipsis. Both keys
    are visible whenever rung 2 fits, i.e. ``cell_len(a) + 1 + cell_len(b) <=
    content_width`` — at width 15 any two keys of up to 6 display cells each
    (every single key, ``^y``, ``alt+y``); at width 24, up to 10 each
    (``shift+f12``). Longer chords at narrower widths lose their tail to the
    ellipsis, still on one row.
    """
    labelled = render_hints((COLLAPSED_HINT_LINE,), keymap)
    if content_width is None or cell_len(labelled) <= content_width:
        return labelled
    _sep, segs = COLLAPSED_HINT_LINE
    return " ".join(
        "/".join(key_display(keymap[a]) for a in seg.actions) for seg in segs
    )


class HelpEntry(NamedTuple):
    """One help-modal entry: the actions it explains, a title and a paragraph.

    ``literal_keys`` replaces the action keys for entries that are not bindings
    of this App (arrow-key navigation, the mouse).
    """

    actions: tuple[str, ...]
    title: str
    description: str
    literal_keys: str = ""


# Source: website/content/docs/tuis/minimonitor/how-to.md — the "Key Bindings
# Quick Reference" table and the how-to section named on each entry. Condensed
# to one paragraph per key; re-derive from those sections when either changes.
# Every MiniMonitorApp binding action has exactly one entry here (test-pinned),
# in the order the full band lists them.
KEY_HELP: tuple[HelpEntry, ...] = (
    # Source: this task (t2212); how-to.md — "How to Collapse the Key Hints or
    # Open the Full Key Help"
    HelpEntry(("toggle_key_hints",), "Collapse / expand the key hints",
              "Switches the bottom band between the full key list and a single "
              "line that names only this key and the help key, giving the rows "
              "back to the agent list. The choice is remembered per user "
              "(minimonitor_key_hints in aitasks/metadata/userconfig.yaml), so "
              "every new minimonitor opens the same way."),
    HelpEntry(("show_key_help",), "Key help",
              "Opens this list. Scroll with the arrow keys or Page Up / Page "
              "Down; Esc, q or this key closes it."),
    # Source: how-to.md — "How to Quit"
    HelpEntry(("quit",), "Quit",
              "Closes minimonitor and its pane; the rest of the tmux session is "
              "unaffected. Minimonitor already closes itself when its agent "
              "exits, so this is mainly for reclaiming the column early."),
    # Source: how-to.md — "How to Focus the Sibling Agent Pane"
    HelpEntry(("focus_sibling_pane",), "Focus the agent pane",
              "Moves tmux focus to the agent pane beside minimonitor, so your "
              "next keystrokes go to the agent. To come back, use tmux's own "
              "pane keys (Ctrl-b o, or Ctrl-b and an arrow)."),
    # Source: how-to.md — "How to Show Task Info for an Agent"
    HelpEntry(("show_task_info",), "Task info (selected card)",
              "Opens the task detail dialog for the highlighted card's task. "
              "Cards whose window name carries no task id show a warning "
              "instead."),
    HelpEntry(("show_own_task_info",), "Task info (followed agent)",
              "Opens the task detail dialog for the agent this minimonitor "
              "follows — the one pinned at the top, which the list never "
              "selects — whichever card is highlighted."),
    # Source: how-to.md — "How to Navigate the Agent List"
    HelpEntry((), "Move between cards",
              "Moves focus between the agent cards in the list. A click on a "
              "card does the same, and the wheel scrolls the list.",
              literal_keys="↑/↓"),
    # Source: how-to.md — "How to Switch to the Selected Agent"
    HelpEntry(("switch_to",), "Switch to the selected agent",
              "Switches tmux focus to the highlighted card's agent window, "
              "which may be in another window or session."),
    # Source: how-to.md — "How to Send Enter to the Sibling Agent"
    HelpEntry(("send_enter_to_sibling",), "Send Enter to the agent",
              "Sends one Enter keystroke to the agent pane beside minimonitor, "
              "unblocking an agent that waits for it, while tmux focus stays "
              "here."),
    # Source: how-to.md — "Key Bindings Quick Reference" (`d` row)
    HelpEntry(("cycle_compare_mode",), "Idle-detection mode",
              "Cycles how minimonitor decides an agent is idle: ≈ compares "
              "the pane output with colour codes stripped, = compares it "
              "exactly."),
    # Source: how-to.md — "How to Jump to Another TUI"
    HelpEntry(("tui_switcher",), "TUI switcher",
              "Opens the TUI switcher overlay to jump to board, monitor, "
              "codebrowser, settings or brainstorm, focusing the window that "
              "runs it or launching it."),
    # Source: how-to.md — "Key Bindings Quick Reference" (`m` row)
    HelpEntry(("switch_to_monitor",), "Full monitor",
              "Switches to the full monitor with this agent focused."),
    # Source: how-to.md — "Key Bindings Quick Reference" (`k` row) and "How to
    # Freeze the Agent You Are Done With"
    HelpEntry(("kill_own_agent",), "Kill the followed agent",
              "Kills the followed agent after a confirmation. When it is "
              "frozen, this drops its record and its captured output instead "
              "(confirmed with a red Drop button)."),
    # Source: how-to.md — "Key Bindings Quick Reference" (`n` row)
    HelpEntry(("pick_next_for_own",), "Next sibling task",
              "Launches an agent on the followed task's next ready sibling "
              "task."),
    # Source: how-to.md — "How to Launch a Shadow Agent"
    HelpEntry(("launch_shadow",), "Shadow agent",
              "Launches an advisory shadow agent beside the followed agent. It "
              "reads that agent's output to explain it, help answer its "
              "prompts or challenge its plan, and never types into it. One "
              "shadow per agent."),
    # Source: how-to.md — "Key Bindings Quick Reference" (`E` row)
    HelpEntry(("launch_shadow_pick",), "Shadow agent (choose agent)",
              "Same as the shadow key, but first lets you choose the code agent "
              "and model the shadow runs on."),
    # Source: how-to.md — "How to Open a Scratchpad"
    HelpEntry(("open_scratchpad",), "Scratchpad notes",
              "Opens a small notes editor in a split of the followed agent's "
              "pane. For a task agent the notes are saved per task; any other "
              "agent gets an unsaved pad."),
    # Source: how-to.md — "How to Pick Shadow Concerns"
    HelpEntry(("pick_concerns",), "Pick shadow concerns",
              "Parses the shadow's concern block into a checklist; the ones you "
              "tick are copied to the clipboard, ready to paste into the agent. "
              "Inside the picker, r rejects a concern, t spins one off as a "
              "task and e edits the payload."),
    # Source: how-to.md — "How to Pick a Task by Number"
    HelpEntry(("pick_task_by_number",), "Pick a task by number",
              "Asks for a task number, shows its details, then launches an "
              "agent on it or moves it to a board column. A task that is not "
              "Ready, or still waits on a dependency, launches only through an "
              "explicit Launch anyway."),
    # Source: how-to.md — "How to Mark an Agent as Prioritized"
    HelpEntry(("toggle_parked_visibility",), "Hide / show parked and frozen",
              "Hides parked and frozen agents from the list, and shows them "
              "again on the next press — one filter over both kinds."),
    # Source: how-to.md — "How to Freeze the Agent You Are Done With"
    HelpEntry(("freeze_current",), "Freeze the followed agent",
              "Ends the followed agent's process and keeps its captured output, "
              "after a confirmation. The frozen-agent viewer replays it in "
              "place; restore or re-pick it from there."),
    HelpEntry(("freeze_all",), "Freeze every agent",
              "Freezes every agent on this machine, across all projects and "
              "including parked ones; the confirmation names the real count."),
    # Source: website/content/docs/tuis/minimonitor/_index.md — "Relationship to
    # monitor" (Sitrep row); sitrep_close.action_harvest_close
    HelpEntry(("harvest_close",), "Harvest the followed agent",
              "Harvests the followed agent's wrap-up into the sitrep todo list, "
              "shows what was captured, then offers to close the agent."),
    # Source: how-to.md — "How to Run the Auto-Recheck Loop"
    HelpEntry(("toggle_review_loop",), "Auto-recheck loop",
              "Arms or disarms the loop: once the followed agent settles after "
              "real work, minimonitor asks the shadow for a fresh review round. "
              "A status line shows the loop's state while it is armed."),
    # Source: how-to.md — "Key Bindings Quick Reference" (`?` row)
    HelpEntry(("open_shortcuts_editor",), "Rebind keys",
              "Opens the shortcut editor to rebind any key listed here. New "
              "keys take effect the next time minimonitor starts."),
    # Source: how-to.md — "How to Toggle the Multi-Session View"
    HelpEntry(("toggle_multi_session",), "Multi-session view",
              "Toggles between agents from every aitasks tmux session and only "
              "this session's. In-memory only."),
    # Source: _index.md — "Relationship to monitor" (Sitrep row);
    # sitrep_close.action_open_sitrep
    HelpEntry(("open_sitrep",), "Sitrep window",
              "Opens, or switches to, the sitrep window of the followed agent's "
              "repository."),
    # Source: how-to.md — "How to Mark an Agent as Prioritized"
    HelpEntry(("toggle_mark",), "Mark the followed agent",
              "Cycles the followed agent's mark: ★ prioritized, P parked, "
              "unmarked. Marks are per user and visible in every project's "
              "monitors."),
    # Source: how-to.md — "Mouse Support"
    HelpEntry((), "Mouse",
              "Click a card to focus it, scroll or drag the scrollbar to move "
              "through the list, and click dialog buttons. Scrolling to the "
              "bottom pins the list there as it refreshes.",
              literal_keys="mouse"),
)


def help_entry_keys(entry: HelpEntry, keymap: dict[str, str]) -> str:
    """The key text a help entry is headed by."""
    if entry.literal_keys:
        return entry.literal_keys
    return "/".join(key_display(keymap[a]) for a in entry.actions)


class KeyHelpModal(GuardedModalScreen):
    """Scrollable list of every minimonitor key with a paragraph each (t2212).

    Sized for the companion pane: full width up to 64 columns, full height, so
    it works at 40x20 and degrades to 24 columns. ``close_keys`` carries the
    App's ACTIVE help key: Textual stops the binding chain at a modal, so the
    App's own binding never fires while this is open and the modal must close
    itself on that key — whatever the user rebound it to.
    """

    DEFAULT_CSS = """
    KeyHelpModal {
        align: center middle;
    }
    KeyHelpModal #mm-help-dialog {
        width: 100%;
        max-width: 64;
        height: 100%;
        border: round $accent;
        background: $surface;
        padding: 0 1;
    }
    KeyHelpModal #mm-help-title {
        width: 100%;
        text-style: bold;
    }
    KeyHelpModal #mm-help-scroll {
        height: 1fr;
    }
    KeyHelpModal .mm-help-entry {
        width: 100%;
        margin-bottom: 1;
    }
    KeyHelpModal #mm-help-footer {
        width: 100%;
        height: auto;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
    ]

    def __init__(self, keymap: dict[str, str], close_keys: tuple[str, ...]):
        super().__init__()
        self._keymap = dict(keymap)
        self._close_keys = tuple(k for k in close_keys if k)

    def compose(self) -> ComposeResult:
        help_key = key_display(self._keymap.get("show_key_help", ""))
        with Container(id="mm-help-dialog"):
            yield Label("Minimonitor keys", id="mm-help-title")
            with VerticalScroll(id="mm-help-scroll"):
                for entry in KEY_HELP:
                    yield Static(
                        Content.assemble(
                            (help_entry_keys(entry, self._keymap), "bold"),
                            "  ", entry.title, "\n", entry.description,
                        ),
                        classes="mm-help-entry",
                    )
            # Content, never a str: a str is parsed as markup, and a key rebound
            # to `[` would be read as a tag.
            yield Label(
                Content(f"Esc/{help_key} close" if help_key else "Esc close"),
                id="mm-help-footer",
            )

    def on_mount(self) -> None:
        self.query_one("#mm-help-scroll", VerticalScroll).focus()

    def on_key(self, event) -> None:
        if event.key in self._close_keys:
            event.stop()
            event.prevent_default()
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
