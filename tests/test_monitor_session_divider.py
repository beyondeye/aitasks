"""Style contract for the repo/session divider in both monitor TUIs (t1449).

In multi-session mode each tmux session is one repo/project, so the
``── <session> ──`` rule the agent list draws between groups *is* the repo
boundary. It used to be rendered ``[dim]`` — the exact style the per-agent
task-title line under every card uses — so it read as one more task title and
the grouping was invisible. It is now **bold cyan**, single-sourced in
``monitor_shared.format_session_divider``.

Everything here asserts against ``Static.render()`` **spans**, not ``.plain``:
``.plain`` strips markup, which is precisely the thing under test (the existing
structural coverage in ``test_minimonitor_other_section.py`` and
``test_multi_session_*.sh`` asserts widget counts and plain text, so a colour
change today would break nothing and be caught by nothing).

The two ``── … ──`` rows in the pane list get **different** colours, not one
shared one: the repo divider is cyan and the ``── other (N) ──`` section header
is a light violet. They share a glyph shape, so a shared colour would make
them read as one kind of boundary — cyan has to keep meaning "repo boundary"
alone. The docked own-agent panel header (``── this agent ──``) is outside the
pane list and deliberately stays ``dim``; that is pinned as a negative control.

Run: python3 tests/test_monitor_session_divider.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MiniMonitorApp/MonitorApp only rename their tmux window when constructed by
# the production launcher, but scrub the ambient tmux env anyway so nothing here
# can touch the pane the suite is running in (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual.app import App, ComposeResult  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402
from textual.widgets import Static  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    SECTION_HEADER_STYLE,
    SESSION_DIVIDER_STYLE,
    STATE_STYLE_ACTIVE,
    STATE_STYLE_DONE,
    STATE_STYLE_IDLE,
    STATE_STYLE_PROMPT,
    format_section_header,
    format_session_divider,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.tmux_monitor import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxPaneInfo,
)


#: Colour half of each style ("bold #af87ff" → "#af87ff").
SECTION_HEADER_COLOUR = SECTION_HEADER_STYLE.split()[-1]
SESSION_DIVIDER_COLOUR = SESSION_DIVIDER_STYLE.split()[-1]

#: The state ladder's colours, derived rather than named. Spelling these as
#: literals is what made the collision guards below go quietly vacuous when the
#: DONE colour changed: `dodger_blue1` simply stopped being a colour anyone
#: used, so `assertNotIn` kept passing while checking nothing (t1453).
STATE_COLOURS = {
    "PROMPT": STATE_STYLE_PROMPT.split()[-1],
    "DONE": STATE_STYLE_DONE.split()[-1],
    "IDLE": STATE_STYLE_IDLE.split()[-1],
    "ACTIVE": STATE_STYLE_ACTIVE.split()[-1],
}
#: Non-state colours that also carry meaning in the agent lists.
RESERVED_COLOURS = {"MARK": "white", "CONTROL_FALLBACK": "red"}


def _styles(widget: Static) -> list[str]:
    """Every style string ``widget``'s rendered Content carries.

    Textual 8.2.7 renders ``Static("[bold cyan]x[/]")`` to
    ``Content('x', spans=[Span(0, 1, style='bold cyan')])`` — the span keeps the
    *whole* style string, so membership tests below look for the substring
    ``cyan`` rather than an exact match.

    **A span assertion alone is not enough** — see ``CompositedColourTests``.
    The span keeps whatever string the markup carried, resolved or not, so a
    colour name Textual cannot parse survives every check at this level and
    still paints default-foreground on screen.
    """
    return [str(span.style) for span in widget.render().spans]


def _assert_divider_style(case: unittest.TestCase, widget: Static, where: str):
    styles = _styles(widget)
    case.assertTrue(
        any("cyan" in s for s in styles),
        f"{where}: divider is not cyan: {styles!r} / {widget.render()!r}",
    )
    case.assertFalse(
        any("dim" in s for s in styles),
        f"{where}: divider is still dim — it will read as a task title: "
        f"{styles!r}",
    )


class SharedSeamTests(unittest.TestCase):
    """The formatter both TUIs go through."""

    def test_formatter_emits_the_rule_in_the_shared_style(self):
        markup = format_session_divider("sA")
        self.assertIn(SESSION_DIVIDER_STYLE, markup)
        self.assertIn("── sA ──", markup)

    def test_style_is_not_dim(self):
        """The whole point: dim is what the task-title lines use."""
        self.assertNotIn("dim", SESSION_DIVIDER_STYLE)
        self.assertIn("cyan", SESSION_DIVIDER_STYLE)

    def test_style_collides_with_no_state_colour(self):
        """Cyan carries no meaning in either agent list.

        The state colours are read from the STATE_STYLE_* constants rather than
        named here, so this guard tracks the ladder instead of going vacuous
        when a state's colour changes. Compares the colour *token*: with a hex
        state colour, a substring check would be strictly weaker.
        """
        for name, taken in {**STATE_COLOURS, **RESERVED_COLOURS}.items():
            with self.subTest(state=name):
                self.assertNotEqual(taken, SESSION_DIVIDER_COLOUR)

    def test_formatter_owns_no_indent(self):
        """Call sites own their own leading indent, never the style."""
        self.assertFalse(format_session_divider("sA").startswith(" "))

    def test_section_header_is_a_different_colour_from_the_divider(self):
        """The two `── … ──` rules share a shape, so they must not share a hue.

        A section boundary and a repo boundary are different things; collapsing
        them onto one colour is the defect this task exists to fix, one level up.
        """
        self.assertNotEqual(SECTION_HEADER_STYLE, SESSION_DIVIDER_STYLE)
        self.assertNotIn("cyan", SECTION_HEADER_STYLE)
        self.assertNotIn("dim", SECTION_HEADER_STYLE)

    def test_section_header_collides_with_no_state_colour(self):
        for name, taken in {**STATE_COLOURS, **RESERVED_COLOURS}.items():
            with self.subTest(state=name):
                self.assertNotEqual(taken, SECTION_HEADER_COLOUR)

    def test_section_header_formatter_emits_the_rule(self):
        markup = format_section_header("other (2)")
        self.assertIn(SECTION_HEADER_STYLE, markup)
        self.assertIn("── other (2) ──", markup)


# --- minimonitor ------------------------------------------------------------


def _snap(
    pane_id: str,
    *,
    window_index: str = "1",
    pane_index: str = "0",
    window_name: str = "agent-pick-42",
    category=PaneCategory.AGENT,
    session: str = "s1",
    command: str = "python",
):
    pane = SimpleNamespace(
        pane_id=pane_id,
        session_name=session,
        window_index=window_index,
        pane_index=pane_index,
        window_name=window_name,
        category=category,
        current_command=command,
    )
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)


class _FakeContainer:
    """Captures what `_rebuild_pane_list` mounts."""

    def __init__(self) -> None:
        self.mounted: list = []

    async def remove_children(self):
        pass

    async def mount_all(self, widgets):
        self.mounted = list(widgets)


def _mk_list_app(snapshots, *, own_window_index=None, multi_session=False):
    """MiniMonitorApp stubbed down to what `_rebuild_pane_list` touches.

    Same harness shape as ``tests/test_minimonitor_other_section.py``.
    """
    container = _FakeContainer()
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app.query_one = lambda *a, **k: container
    app._own_window_index = own_window_index
    app._session = "s1"
    app._snapshots = {s.pane.pane_id: s for s in snapshots}
    app._task_cache = SimpleNamespace(
        get_task_id=lambda w: None,
        get_task_id_for_pane=lambda p: None,
        get_task_info=lambda t, s=None: None,
    )
    app._monitor = SimpleNamespace(
        multi_session=multi_session,
        get_compare_mode=lambda pid: "stripped",
        is_compare_mode_overridden=lambda pid: False,
        get_shadow_snapshot=lambda pid: None,
        get_session_to_project_mapping=lambda: {},
    )
    app._completed_pane_ids = frozenset()
    app._gate_cache = SimpleNamespace(summary_for=lambda i: None, clear=lambda: None)
    app._init_agent_marks()
    return app, container


def _statics(widgets):
    return [w for w in widgets if isinstance(w, Static)
            and not isinstance(w, mm.MiniPaneCard)]


class MiniMonitorDividerTests(unittest.TestCase):
    def _two_session_rebuild(self, *, category=PaneCategory.AGENT):
        app, container = _mk_list_app(
            [
                _snap("%1", window_name="agent-pick-42", session="sA",
                      category=category),
                _snap("%2", window_index="2", window_name="agent-pick-43",
                      session="sB", category=category),
            ],
            multi_session=True,
        )
        asyncio.run(app._rebuild_pane_list())
        return container.mounted

    def test_dividers_render_cyan(self):
        mounted = self._two_session_rebuild()
        dividers = [w for w in _statics(mounted)
                    if w.has_class("mini-session-divider")]
        self.assertEqual(len(dividers), 2,
                         f"expected one divider per session: {mounted}")
        for div in dividers:
            _assert_divider_style(self, div, "minimonitor")
        plains = [d.render().plain for d in dividers]
        self.assertEqual(plains, ["── sA ──", "── sB ──"])

    def test_other_section_header_has_its_own_colour(self):
        """The scope decision, pinned: distinguishable, but NOT the divider's.

        The `── other (N) ──` header uses the same glyph shape as the repo
        divider, so it needs a colour of its own — and it must not be cyan, or
        cyan stops meaning "repo boundary". It must not be dim either: that is
        what the task-title lines use.
        """
        mounted = self._two_session_rebuild(category=PaneCategory.OTHER)
        headers = [w for w in _statics(mounted)
                   if w.has_class("mini-section-header")]
        self.assertEqual(len(headers), 1, f"expected one header: {mounted}")
        styles = _styles(headers[0])
        self.assertTrue(any(SECTION_HEADER_STYLE in s for s in styles),
                        f"other header is not the section-header style: {styles!r}")
        self.assertFalse(any("cyan" in s for s in styles),
                         f"other header took over the divider colour: {styles!r}")
        self.assertFalse(any("dim" in s for s in styles),
                         f"other header is still dim: {styles!r}")

    def test_section_header_css_carries_no_competing_style(self):
        """`.mini-section-header` must not re-declare colour or text-style.

        Same reasoning as the divider's CSS: the markup span wins, so anything
        left here is dead config that reads as if the header were still muted.
        """
        css = mm.MiniMonitorApp.CSS
        start = css.index(".mini-section-header")
        block = css[start:css.index("}", start)]
        self.assertNotIn("color:", block, f"stale colour source: {block!r}")
        self.assertNotIn("text-style:", block, f"stale style source: {block!r}")

    def test_own_panel_header_stays_dim(self):
        """Negative control: the docked "this agent/window" header, same shape."""
        panel = _FakeContainer()
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app.query_one = lambda *a, **k: panel
        app._snapshots = {"%4": _snap("%4", window_index="7",
                                      window_name="agent-pick-42")}
        app._session = "s1"
        app._own_window_index = "7"
        app._own_panel_built = False
        app._own_card = None
        app._own_identity_text = ""
        app._own_mark_state = None
        app._target_width = 40
        app._task_cache = SimpleNamespace(
            get_task_id_for_pane=lambda p: None,
            get_task_info=lambda t, s=None: None,
        )
        app._init_agent_marks()
        asyncio.run(app._maybe_build_own_agent_panel())

        styles = _styles(panel.mounted[0])
        self.assertTrue(any("dim" in s for s in styles),
                        f"own-panel header lost its dim: {styles!r}")
        for taken in ("cyan", SECTION_HEADER_COLOUR):
            self.assertFalse(
                any(taken in s for s in styles),
                f"own-panel header took a pane-list rule colour: {styles!r}",
            )

    def test_css_carries_no_competing_colour(self):
        """`.mini-session-divider` must not re-declare a colour.

        Leaving `color: $text-muted` in place would be a second, now-untrue
        source of truth for the same row: the markup span wins, so the CSS would
        be dead config that reads as if the divider were still muted.
        """
        css = mm.MiniMonitorApp.CSS
        start = css.index(".mini-session-divider")
        block = css[start:css.index("}", start)]
        self.assertNotIn("color:", block, f"stale colour source: {block!r}")


# --- full monitor -----------------------------------------------------------


class _FakeMonitor:
    """Same shape as ``tests/test_monitor_focus_switch.py``, multi-session on."""

    multi_session = True

    def __init__(self, snapshots: dict[str, PaneSnapshot]) -> None:
        self.snapshots = snapshots
        self._gen = 0

    @property
    def capture_generation(self) -> int:
        return self._gen

    async def _run_offloaded(self, fn):
        return fn()

    def get_shadow_snapshot(self, followed_pane_id):
        return None

    async def capture_all_classified_async(self):
        self._gen += 1
        classified = [(s.pane, s.content, None) for s in self.snapshots.values()]
        return self._gen, classified

    def commit_snapshots(self, gen, classified):
        if gen != self._gen:
            return None
        return dict(self.snapshots)

    async def capture_all_async(self) -> dict[str, PaneSnapshot] | None:
        gen, classified = await self.capture_all_classified_async()
        return self.commit_snapshots(gen, classified)

    def get_session_to_project_mapping(self) -> dict[str, Path]:
        return {}

    async def get_session_to_project_mapping_async(self) -> dict[str, Path]:
        return self.get_session_to_project_mapping()

    def control_state(self) -> TmuxControlState:
        return TmuxControlState.CONNECTED

    def get_compare_mode(self, pane_id: str) -> str:
        return "stripped"

    def is_compare_mode_overridden(self, pane_id: str) -> bool:
        return False


def _monitor_snapshot(pane_id: str, session: str) -> PaneSnapshot:
    idx = int(pane_id.lstrip("%"))
    pane = TmuxPaneInfo(
        window_index="0",
        window_name=f"agent-{idx}",
        pane_index=str(idx),
        pane_id=pane_id,
        pane_pid=10_000 + idx,
        current_command="bash",
        width=80,
        height=24,
        category=PaneCategory.AGENT,
        session_name=session,
    )
    return PaneSnapshot(
        pane=pane,
        content=f"agent-{idx}\nready",
        timestamp=0.0,
        idle_seconds=0.0,
        is_idle=False,
    )


class MonitorDividerTests(unittest.TestCase):
    def _dividers(self) -> list[str]:
        """Render the real app in multi-session mode; return divider plains."""
        captured: dict[str, list] = {}

        async def runner():
            app = MonitorApp(session="sA", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                snapshots = {
                    "%1": _monitor_snapshot("%1", "sA"),
                    "%2": _monitor_snapshot("%2", "sB"),
                }
                app._monitor = _FakeMonitor(snapshots)
                app._snapshots = snapshots
                app._focused_pane_id = "%1"

                async def no_focus_request():
                    return None

                app._consume_focus_request = no_focus_request
                self.assertTrue(app._rebuild_pane_list())
                await pilot.pause()
                captured["dividers"] = list(
                    app.query("#pane-list .session-divider")
                )
                captured["styles"] = [_styles(w) for w in captured["dividers"]]
                captured["plains"] = [
                    w.render().plain for w in captured["dividers"]
                ]

        asyncio.run(runner())
        return captured

    def test_dividers_render_cyan(self):
        captured = self._dividers()
        self.assertEqual(len(captured["dividers"]), 2,
                         f"expected one divider per session: {captured}")
        for styles in captured["styles"]:
            self.assertTrue(any("cyan" in s for s in styles),
                            f"full monitor: divider is not cyan: {styles!r}")
            self.assertFalse(any("dim" in s for s in styles),
                             f"full monitor: divider is still dim: {styles!r}")

    def test_divider_keeps_the_two_column_indent(self):
        """The indent belongs to the call site, and the seam must not eat it."""
        captured = self._dividers()
        self.assertEqual(captured["plains"], ["  ── sA ──", "  ── sB ──"])


class _RuleHost(App):
    """A host that paints both pane-list rules under the REAL minimonitor CSS.

    Mounting is what makes this a *composited* assertion. It is not redundant
    with the span tests above: a span keeps the markup's style string verbatim,
    so a colour Textual's parser does not know survives every span check and
    then paints nothing. Textual's palette is CSS colour names — it does **not**
    know Rich's xterm names, and `[bold medium_purple1]` is silently inert
    (caught here during t1449, which is why this class exists).
    """

    CSS = mm.MiniMonitorApp.CSS

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="mini-pane-list")

    def on_mount(self) -> None:
        # Two reference controls in the SAME CSS context as the rules: one
        # carrying each style, one unstyled. Comparing runs against each other
        # rather than against a literal hex is what keeps this environment-
        # independent — the truecolor a compositor reports depends on colour
        # depth and palette quantisation, so a literal makes the test pass or
        # fail on WHERE it runs rather than on whether the style is live
        # (t1453).
        self.query_one("#mini-pane-list", VerticalScroll).mount(
            Static(format_session_divider("aitasks"),
                   classes="mini-session-divider"),
            Static(format_section_header("other (2)"),
                   classes="mini-section-header"),
            Static(f"[{SESSION_DIVIDER_STYLE}]REFDIVIDER[/]"),
            Static(f"[{SECTION_HEADER_STYLE}]REFHEADER[/]"),
            Static("REFPLAIN"),
        )


class CompositedColourTests(unittest.TestCase):
    """The rules must reach the terminal in their declared colours."""

    def _painted(self) -> dict[str, str]:
        painted: dict[str, str] = {}

        async def runner():
            host = _RuleHost()
            async with host.run_test(size=(40, 6)) as pilot:
                await pilot.app.workers.wait_for_complete()
                for strip in host.screen._compositor.render_strips():
                    for seg in strip:
                        text = seg.text.strip()
                        if not text or seg.style is None or seg.style.color is None:
                            continue
                        painted[text] = seg.style.color.get_truecolor().hex.lower()

        asyncio.run(runner())
        return painted

    def test_both_rules_paint_their_declared_colour(self):
        painted = self._painted()
        divider = painted.get("── aitasks ──")
        header = painted.get("── other (2) ──")
        self.assertIsNotNone(divider, f"divider not on screen: {painted}")
        self.assertIsNotNone(header, f"section header not on screen: {painted}")

        # Each rule must match a reference run carrying the same style in the
        # same CSS context, and that reference must differ from an unstyled
        # run. The first half says the call site uses the declared style; the
        # second says the style is live rather than silently inert. Neither
        # names a literal hex — see the note in _RuleHost.on_mount.
        self.assertNotEqual(
            painted.get("REFDIVIDER"), painted.get("REFPLAIN"),
            f"SESSION_DIVIDER_STYLE is inert: {painted}")
        self.assertNotEqual(
            painted.get("REFHEADER"), painted.get("REFPLAIN"),
            f"SECTION_HEADER_STYLE is inert: {painted}")
        self.assertEqual(divider, painted.get("REFDIVIDER"),
                         f"divider painted {divider}, but "
                         f"SESSION_DIVIDER_STYLE resolves to "
                         f"{painted.get('REFDIVIDER')}: {painted}")
        self.assertEqual(header, painted.get("REFHEADER"),
                         f"section header painted {header}, but "
                         f"SECTION_HEADER_STYLE resolves to "
                         f"{painted.get('REFHEADER')}: {painted}")

    def test_the_two_rules_do_not_paint_the_same_colour(self):
        """The whole point of giving the section header its own style."""
        painted = self._painted()
        self.assertNotEqual(painted.get("── aitasks ──"),
                            painted.get("── other (2) ──"),
                            f"both rules painted the same colour: {painted}")

    def test_neither_rule_paints_the_default_foreground(self):
        """The failure mode an unparseable colour name produces.

        `[bold medium_purple1]` paints exactly this — the theme's default text
        colour — while every span-level assertion still passes.
        """
        painted = self._painted()
        default = painted.get("── this is not mounted ──")
        self.assertIsNone(default)  # sanity: the lookup returns None when absent
        for label in ("── aitasks ──", "── other (2) ──"):
            self.assertNotEqual(
                painted.get(label), "#e0e0e0",
                f"{label} painted the default foreground — its colour name is "
                f"probably not one Textual can parse: {painted}",
            )


class CrossTuiAgreementTests(unittest.TestCase):
    """Monitor and minimonitor must not drift apart again."""

    def test_both_tuis_resolve_to_the_same_divider_style(self):
        app, container = _mk_list_app(
            [_snap("%1", session="sA"),
             _snap("%2", window_index="2", session="sB")],
            multi_session=True,
        )
        asyncio.run(app._rebuild_pane_list())
        mini = [_styles(w) for w in _statics(container.mounted)
                if w.has_class("mini-session-divider")]

        full = MonitorDividerTests("test_dividers_render_cyan")._dividers()

        self.assertTrue(mini, "no minimonitor dividers rendered")
        self.assertTrue(full["styles"], "no monitor dividers rendered")
        self.assertEqual(
            {tuple(s) for s in mini}, {tuple(s) for s in full["styles"]},
            f"divider styles diverged: mini={mini!r} full={full['styles']!r}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
