"""Own-panel header names the followed agent's tmux session (t1580).

`ait minimonitor`'s docked panel used to read only ``── this agent ──``, so the
followed agent was the one entry on screen with no repo context while every
other agent got a ``format_session_divider`` rule. It now reads
``── this agent · <session> ──``.

``.mini-own-header`` is ``height: 1``, which **clips** rather than wraps, so an
over-long header silently loses its trailing ``──`` and the rule reads as
broken. ``tmux.minimonitor.width`` reaches ``_target_width`` as a bare
``int(mm_cfg["width"])`` with no clamp, so the budget has to hold at *any*
width — which is why the sweep below runs from 1 rather than from a list of
plausible widths. Both sub-rule shedding thresholds (17/18) sit below the 22
the sibling width tests start at, so only a full sweep can see them.

Most cases here are on the pure ``_own_header_text`` formatter. The two
widget-level cases at the bottom prove the string actually reaches the mounted
header for both the ``this agent`` and ``this window`` states.

Run: python3 tests/test_minimonitor_own_header_session.py
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

# MiniMonitorApp only renames its tmux window when constructed by the production
# launcher, but scrub the ambient tmux env anyway so nothing here can touch the
# pane the suite is running in (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.cells import cell_len  # noqa: E402
from rich.markup import render as render_markup  # noqa: E402
from textual.widgets import Static  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.tmux_monitor import PaneCategory  # noqa: E402

#: The two labels the header can carry. They differ in width by one cell, which
#: is why every threshold below is derived per label rather than shared.
LABELS = ("this agent", "this window")

#: Widths the pure-formatter cases sweep. Starts at 1 deliberately: the
#: configured width is unvalidated, and the interesting rungs are all under 26.
SWEEP_WIDTHS = range(1, 61)


def _plain(markup: str) -> str:
    """The header as the terminal will actually show it.

    Measured on the RENDERED text, never on the markup string: `escape()` adds
    backslashes that do not occupy cells, so counting the markup would
    over-count a session name containing brackets and the budget assertions
    would pass for the wrong reason.
    """
    return render_markup(markup).plain


def _usable(width: int) -> int:
    """Cells the header actually gets — `.mini-own-header` is `padding: 0 1`."""
    return max(0, width - mm._OWN_HEADER_PADDING)


def _room(label: str, width: int) -> int:
    """Cells left for the session name at `width`, by the formatter's own rule."""
    return (_usable(width) - cell_len(f"── {label} ──")
            - cell_len(mm._OWN_HEADER_SEP))


def _rule_threshold(label: str) -> int:
    """Lowest width at which `── <label> ──` still fits whole."""
    return cell_len(f"── {label} ──") + mm._OWN_HEADER_PADDING


class FullFormTests(unittest.TestCase):
    """The feature itself: the session reaches the rule at a normal width."""

    def test_session_is_named_at_the_default_width(self):
        for label in LABELS:
            with self.subTest(label=label):
                self.assertEqual(
                    _plain(mm._own_header_text(label, "probe-session", 40)),
                    f"── {label} · probe-session ──",
                )

    def test_the_separator_is_the_named_constant(self):
        """The `·` is a constant, not a literal typed twice.

        Pinned so a change to `_OWN_HEADER_SEP` cannot leave this module
        asserting the old glyph and passing for a stale reason.
        """
        self.assertIn(
            mm._OWN_HEADER_SEP,
            _plain(mm._own_header_text("this agent", "probe-session", 40)),
        )


class TruncationBoundaryTests(unittest.TestCase):
    """The session name gives way by cells, at a computed boundary."""

    def test_the_longest_fitting_session_survives_whole(self):
        for label in LABELS:
            with self.subTest(label=label):
                room = _room(label, 40)
                session = "s" * room
                self.assertEqual(
                    _plain(mm._own_header_text(label, session, 40)),
                    f"── {label} · {session} ──",
                    "a session name that exactly fits was truncated anyway",
                )

    def test_one_character_past_the_boundary_is_ellipsized(self):
        """The other side of the same boundary — without this, a formatter that
        never truncates at all would pass the case above."""
        for label in LABELS:
            with self.subTest(label=label):
                room = _room(label, 40)
                session = "s" * (room + 1)
                out = _plain(mm._own_header_text(label, session, 40))
                self.assertEqual(out, f"── {label} · {'s' * (room - 1)}… ──")
                self.assertLessEqual(cell_len(out), _usable(40))

    def test_a_wide_session_name_is_truncated_on_cells_not_code_points(self):
        """`len()` would count 20 CJK characters as 20 and overflow by 20.

        The formatter budgets with `cell_len` / `_clip`, so the result fits the
        row it is actually painted into.
        """
        out = _plain(mm._own_header_text("this agent", "課題" * 20, 40))
        self.assertLessEqual(cell_len(out), _usable(40))
        self.assertTrue(out.endswith("──"), out)


class SheddingLadderTests(unittest.TestCase):
    """Three rungs, decoration first. Each is pinned where it takes over."""

    def test_the_session_segment_is_dropped_whole_not_stubbed(self):
        """At width 22 there is exactly 1 cell of room.

        Asserted as EQUALITY with the bare rule, not as "it fits": a `· …` stub
        also fits 20 cells, so only equality distinguishes "dropped" from
        "truncated down to nothing". This is the assertion `_MIN_SESSION_CELLS`
        exists to satisfy.
        """
        self.assertEqual(_room("this agent", 22), 1)
        self.assertEqual(
            _plain(mm._own_header_text("this agent", "probe-session", 22)),
            "── this agent ──",
        )

    def test_the_session_segment_reappears_at_min_session_cells(self):
        """The first width that affords `_MIN_SESSION_CELLS` shows a name again.

        Without this, a formatter that dropped the session at EVERY width would
        pass the case above.
        """
        width = 25
        self.assertEqual(_room("this agent", width), mm._MIN_SESSION_CELLS)
        self.assertEqual(
            _plain(mm._own_header_text("this agent", "probe-session", width)),
            "── this agent · pro… ──",
        )

    def test_the_rule_glyphs_shed_before_the_label_does(self):
        """Below its threshold each label keeps its text and loses the rule.

        A HALF rule is the failure mode this whole module exists for, so "no
        rule at all" is asserted positively — `assertNotIn("──")` — rather than
        inferred from a length check.
        """
        for label in LABELS:
            threshold = _rule_threshold(label)
            with self.subTest(label=label, at=threshold):
                at = _plain(mm._own_header_text(label, "", threshold))
                self.assertEqual(at, f"── {label} ──")
            with self.subTest(label=label, below=threshold - 1):
                below = _plain(mm._own_header_text(label, "", threshold - 1))
                self.assertNotIn("──", below, "a clipped half-rule survived")
                self.assertEqual(below, label)

    def test_the_two_labels_have_different_thresholds(self):
        """Guards the derivation itself.

        `this window` is one cell wider than `this agent`, so a shared hardcoded
        threshold would be wrong for one of them. If these ever coincide the
        per-label sweep above has quietly become one case tested twice.
        """
        self.assertEqual(_rule_threshold("this agent"), 18)
        self.assertEqual(_rule_threshold("this window"), 19)

    def test_the_label_itself_is_clipped_on_the_last_rung(self):
        out = _plain(mm._own_header_text("this window", "", 12))
        self.assertEqual(out, "this wind…")


class WidthPostConditionTests(unittest.TestCase):
    """The invariant every rung is accountable to."""

    def test_the_header_never_exceeds_its_row_at_any_width(self):
        """The sweep a fixed `(40, 30, 26, 22)` list cannot do.

        Both shedding thresholds sit below 22, so the sibling width tests in
        `test_minimonitor_top_chrome_render.py` are structurally blind to a rung
        that overflows. This is the case that fails if rung 3 is ever removed.
        """
        sessions = ("", "s" * 8, "s" * 200, "課題" * 30, "[dim]x[/]")
        for width in SWEEP_WIDTHS:
            for label in LABELS:
                for session in sessions:
                    out = _plain(mm._own_header_text(label, session, width))
                    with self.subTest(width=width, label=label,
                                      session=len(session)):
                        self.assertLessEqual(
                            cell_len(out), _usable(width),
                            f"header overran its row: {out!r}",
                        )

    def test_a_degenerate_width_yields_no_header_rather_than_raising(self):
        self.assertEqual(_plain(mm._own_header_text("this agent", "s", 1)), "")


class MarkupSafetyTests(unittest.TestCase):
    """The session name is tmux-side user input, so it is data, not markup."""

    def test_a_session_name_containing_markup_renders_literally(self):
        """Unescaped, `[/]` closes the `[dim]` span early and `[dim]` is eaten.

        Driven through a real `Static` — the widget the header is actually
        mounted as — so this exercises Textual's parser, not just Rich's.
        """
        widget = Static(mm._own_header_text("this agent", "[dim]x[/]", 40))
        content = widget.render()
        self.assertEqual(content.plain, "── this agent · [dim]x[/] ──")

    def test_the_header_keeps_exactly_one_dim_span(self):
        """The escape must not fragment the rule into several styled runs.

        `test_own_panel_header_stays_dim` (test_monitor_session_divider.py)
        checks the header is dim; this checks a bracket-bearing session name has
        not split it into a dim part and an unstyled part.
        """
        content = Static(
            mm._own_header_text("this agent", "[dim]x[/]", 40)
        ).render()
        styles = [s.style for s in content.spans]
        self.assertEqual(len(styles), 1, f"rule was fragmented: {styles!r}")
        self.assertIn("dim", styles[0])

    def test_escaping_happens_after_truncation(self):
        """The backslashes must not be charged to the cell budget.

        Escaping first would make `[dim]x[/]` measure 11 instead of 9 and
        truncate a name that fits.
        """
        session = "[dim]x[/]"
        room = _room("this agent", 40)
        self.assertLess(cell_len(session), room)
        self.assertEqual(
            _plain(mm._own_header_text("this agent", session, 40)),
            f"── this agent · {session} ──",
        )


class EmptySessionTests(unittest.TestCase):
    def test_no_session_yields_the_bare_rule(self):
        for label in LABELS:
            with self.subTest(label=label):
                self.assertEqual(
                    _plain(mm._own_header_text(label, "", 40)),
                    f"── {label} ──",
                )
                self.assertNotIn(
                    mm._OWN_HEADER_SEP,
                    _plain(mm._own_header_text(label, "", 40)),
                    "a dangling separator was left behind",
                )


# --- widget level -----------------------------------------------------------


def _snap(*, window_name="agent-pick-1580", category=PaneCategory.AGENT,
          session="probe-session"):
    pane = SimpleNamespace(
        pane_id="%4",
        session_name=session,
        window_index="7",
        pane_index="0",
        window_name=window_name,
        category=category,
        current_command="python",
    )
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)


class _FakePanel:
    """Stands in for `#mini-own-agent`, carrying what the build site writes."""

    def __init__(self) -> None:
        self.mounted: list = []
        self.display = False
        self.styles = SimpleNamespace(max_height=None)

    async def remove_children(self):
        pass

    async def mount_all(self, widgets):
        self.mounted = list(widgets)


class MountedHeaderTests(unittest.TestCase):
    """The formatter's output actually reaches the docked panel.

    Same `__new__`-stub shape the sibling modules use — the pure cases above
    prove the string, these prove the wiring.
    """

    def _build(self, snap, app_session="probe-session"):
        """`app_session` is `self._session`, and it is a parameter on purpose.

        `_find_own_window_snapshot` resolves the followed pane with
        `session_name in ("", self._session)`, so the two values are not
        independent: the fallback case below needs them to DIFFER, and every
        other case needs them to agree or no panel is built at all.
        """
        panel = _FakePanel()
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app.query_one = lambda *a, **k: panel
        app._snapshots = {snap.pane.pane_id: snap}
        app._session = app_session
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
        return panel.mounted[0].render().plain

    def test_the_agent_state_names_the_session(self):
        self.assertEqual(self._build(_snap()),
                         "── this agent · probe-session ──")

    def test_the_renamed_window_state_names_it_too(self):
        """The `this window` path is not left bare (t1580 acceptance)."""
        header = self._build(
            _snap(window_name="noam_bugs", category=PaneCategory.OTHER)
        )
        self.assertEqual(header, "── this window · probe-session ──")

    def test_a_paneless_session_name_falls_back_to_the_app_session(self):
        """`PaneInfo` built outside a list-panes path carries `session_name=""`.

        The header must still name a session rather than rendering a dangling
        separator or an empty segment.
        """
        self.assertEqual(
            self._build(_snap(session=""), app_session="fallback-session"),
            "── this agent · fallback-session ──",
        )


# --- ambiguous-session substitution -----------------------------------------


class _SpyMonitor:
    """Records whether the SYNC session→project mapping was consulted at all.

    Since t1598 the answer must be "never": `_root_for_snap` reads the map
    `_refresh_data` published for this tick, so any `consulted` count above zero
    means a sync tmux round-trip crept back onto the render path. The counter
    was already asserted for the pass-through case; it is now a poison pill for
    every case.

    The "unambiguous name passes through" case asserts on that, not merely on
    the returned string: a resolver that looked the project up and then happened
    to return the session anyway would satisfy a value-only assertion while
    paying the lookup on every panel build.
    """

    def __init__(self, mapping):
        self._mapping = mapping
        self.consulted = 0

    def get_session_to_project_mapping(self):
        self.consulted += 1
        return self._mapping


class AmbiguousSessionTests(unittest.TestCase):
    """`aitasks` names no repo, so the project basename stands in (t1580).

    Not an "unconfigured repo" check — see `_session_is_ambiguous`. The name
    collides whether it was defaulted or chosen, and runtime cannot tell which.
    """

    def _resolve(self, session, *, mapping=None, project_root=None,
                 monitor=True):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._session = "app-session"
        app._project_root = project_root
        spy = _SpyMonitor(mapping or {})
        app._monitor = spy if monitor else None
        # Publish this "tick's" session→root map the way `_refresh_data` does.
        # Since t1598 `_root_for_snap` reads the published map rather than
        # calling `get_session_to_project_mapping()` — that sync call was a tmux
        # round-trip on the render path, which `_own_header_session` is on.
        app._set_session_root_map(mapping or {})
        return app._own_header_session(_snap(session=session)), spy

    def test_a_distinctive_session_passes_through_untouched(self):
        out, spy = self._resolve(
            "aitasks_mobile",
            mapping={"aitasks_mobile": Path("/repos/somewhere-else")},
        )
        self.assertEqual(out, "aitasks_mobile")
        self.assertEqual(spy.consulted, 0,
                         "the project mapping was consulted needlessly")

    def test_the_render_path_never_makes_the_sync_mapping_call(self):
        """Poison pill for the t1598 async port (see `_SpyMonitor`)."""
        for label, kwargs in (
            ("distinctive", dict(session="aitasks_mobile",
                                 mapping={"aitasks_mobile": Path("/repos/x")})),
            ("ambiguous", dict(session=mm.DEFAULT_TMUX_SESSION,
                               mapping={mm.DEFAULT_TMUX_SESSION:
                                        Path("/repos/aitasks_mobile")})),
        ):
            with self.subTest(case=label):
                _out, spy = self._resolve(**kwargs)
                self.assertEqual(
                    spy.consulted, 0,
                    "a sync get_session_to_project_mapping() ran on the render "
                    "path — that is the blocking tmux round-trip t1598 removed",
                )

    def test_the_ambiguous_name_is_replaced_by_the_project_basename(self):
        out, _ = self._resolve(
            mm.DEFAULT_TMUX_SESSION,
            mapping={mm.DEFAULT_TMUX_SESSION: Path("/repos/aitasks_mobile")},
        )
        self.assertEqual(out, "aitasks_mobile")

    def test_an_explicitly_configured_default_is_substituted_too(self):
        """The decided rule, pinned as its own case.

        A repo may set `tmux.default_session: aitasks` deliberately —
        `seed/project_config.yaml` documents exactly that. The rejected
        alternative (read the owning config and honour an explicit choice)
        would make THIS case return "aitasks"; the chosen rule substitutes
        regardless of provenance, because the name collides either way. Asserted
        separately from the case above so the decision is not an untested
        corollary of it.
        """
        out, _ = self._resolve(
            mm.DEFAULT_TMUX_SESSION,
            # Indistinguishable at runtime from the implicit fallback — that is
            # precisely the point. Only the config file, which is not read,
            # would say which one this is.
            mapping={mm.DEFAULT_TMUX_SESSION: Path("/repos/deliberate_repo")},
        )
        self.assertEqual(out, "deliberate_repo")

    def test_a_foreign_session_resolves_to_its_own_project_not_the_local_one(self):
        """Multi-session mode: the followed pane may live in another project.

        Resolving from `self._project_root` instead of through `_root_for_snap`
        would silently label it with the minimonitor's own repo.
        """
        out, _ = self._resolve(
            mm.DEFAULT_TMUX_SESSION,
            mapping={mm.DEFAULT_TMUX_SESSION: Path("/repos/the_followed_one")},
            project_root=Path("/repos/the_local_one"),
        )
        self.assertEqual(out, "the_followed_one")

    def test_it_falls_back_to_the_local_root_when_the_mapping_misses(self):
        out, _ = self._resolve(
            mm.DEFAULT_TMUX_SESSION,
            mapping={"some-other-session": Path("/repos/unrelated")},
            project_root=Path("/repos/the_local_one"),
        )
        self.assertEqual(out, "the_local_one")

    def test_it_fails_soft_to_the_session_name(self):
        """Every unresolvable path yields the session, never "" or a crash.

        `_root_for_snap` answers None on a `__new__`-built stub (both class
        floors are None), which is the case the fail-soft contract exists for.
        """
        for label, kwargs in (
            ("no monitor", dict(monitor=False, project_root=None)),
            ("no root at all", dict(mapping={}, project_root=None)),
            ("root with an empty name", dict(mapping={}, project_root=Path("/"))),
        ):
            with self.subTest(case=label):
                out, _ = self._resolve(mm.DEFAULT_TMUX_SESSION, **kwargs)
                self.assertEqual(out, mm.DEFAULT_TMUX_SESSION)

    def test_the_substituted_value_still_goes_through_the_width_budget(self):
        """Substitution happens before formatting, so a long basename truncates.

        Otherwise the fix for one defect would reintroduce the other.
        """
        long_root = Path("/repos/" + "a-very-long-project-name" * 3)
        out, _ = self._resolve(
            mm.DEFAULT_TMUX_SESSION,
            mapping={mm.DEFAULT_TMUX_SESSION: long_root},
        )
        header = _plain(mm._own_header_text("this agent", out, 40))
        self.assertLessEqual(cell_len(header), _usable(40))
        self.assertTrue(header.endswith("──"), header)


class DefaultSessionConstantTests(unittest.TestCase):
    """`DEFAULT_TMUX_SESSION` is the canonical spelling of the fallback name.

    Scoped to the launcher module that owns it. `_read_default_session` derives
    **both** of its returns from the constant, so this pins that derivation
    rather than restating the literal — which is what stops the substitution
    rule above from silently keying off a value the resolver no longer returns.

    Deliberately does NOT reach into `applink/server.py`, which keeps its own
    `DEFAULT_SESSION`. Whether that standalone listener should share this
    contract is an open question, not an established one, and answering it by
    importing applink from a minimonitor-header test would create the shared
    contract rather than record a decision to have one. See t1583.
    """

    def test_read_default_session_returns_the_constant(self):
        from agent_launch_utils import DEFAULT_TMUX_SESSION, _read_default_session

        self.assertEqual(
            _read_default_session(Path("/nonexistent-project-root")),
            DEFAULT_TMUX_SESSION,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
