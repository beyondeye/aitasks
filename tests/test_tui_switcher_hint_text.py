"""Characterization tests for the TUI switcher's rendered hint text (t1453).

t1453 replaces the switcher's inert ``bright_cyan`` markup with a resolvable
style, touching eleven call sites. Three of them carry non-obvious string
semantics that a careless replacement would silently break:

- ``_hint_segment`` (:248) builds a **regex replacement template** — the ``\\1``
  backreference must survive the edit;
- ``_render_hint``'s group hint (:746) and ``_render_session_row``'s group
  prefix (:804) both embed a **backslash-escaped literal bracket**, which must
  stay escaped or the bracket is parsed as a markup tag and vanishes.

The switcher overlay is mounted into every aitasks TUI, so a regression here is
visible everywhere at once. These tests pin the exact rendered text with the
style token parameterized on ``TUI_KEY_HINT_STYLE``, so they pass both before
and after the swap and fail on any *structural* drift.

They assert text only. That a style actually paints is a different question,
answered by the composited tier in ``test_markup_colour_contract.py``.

Run: python3 tests/test_tui_switcher_hint_text.py
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import tui_switcher as ts  # noqa: E402
from tui_switcher import (  # noqa: E402
    _HINT_ITEMS,
    _hint_segment,
    TUI_KEY_HINT_STYLE,
)

#: The opening tag every key hint is wrapped in. Parameterized so this module
#: pins structure, not colour — the colour is ratified once, in
#: test_markup_colour_contract.RatifiedStylesTests.
TAG = f"[{TUI_KEY_HINT_STYLE}]"

#: One entry per _HINT_ITEMS entry, in order. `{tag}` is the opening tag above.
#: render_label inlines the key into the word where it can ((B)oard) and
#: prefixes it otherwise; both shapes appear here deliberately.
EXPECTED_SEGMENTS = [
    "{tag}(B)[/]oard",
    "{tag}(M)[/]onitor",
    "{tag}(C)[/]ode",
    "{tag}(S)[/]ettings",
    "s{tag}(T)[/]ats",
    "s{tag}(Y)[/]ncer",
    "b{tag}(R)[/]ainstorm",
    "{tag}(G)[/]it",
    "e{tag}(X)[/]plore",
    "e{tag}(X)[/]plore+",
    "{tag}(N)[/]ew task",
    "ag{tag}(E)[/]nt",
]


def _expected_segment_row() -> str:
    return "  ".join(s.format(tag=TAG) for s in EXPECTED_SEGMENTS)


class _Capture:
    """Stands in for the Label / Static the renderers call .update() on."""

    def __init__(self) -> None:
        self.text: str | None = None
        self.display = True

    def update(self, text: str) -> None:
        self.text = text


def _overlay(multi_mode: bool) -> tuple[object, _Capture]:
    """An unmounted overlay with query_one stubbed.

    Constructed via __new__ so no DOM, tmux discovery or app is needed — the
    same shape test_monitor_completed_status.py uses for MonitorApp.
    """
    overlay = object.__new__(ts.TuiSwitcherOverlay)
    overlay._multi_mode = multi_mode
    overlay._all_sessions = []
    overlay._selected_group = None
    capture = _Capture()
    overlay.query_one = lambda *args, **kwargs: capture
    return overlay, capture


class _StubGroups:
    """Force group_sessions to report a chosen number of groups."""

    def __init__(self, groups: list[str]) -> None:
        self.groups = groups

    def __enter__(self):
        self._real = ts.group_sessions
        ts.group_sessions = lambda *a, **k: types.SimpleNamespace(groups=self.groups)
        return self

    def __exit__(self, *exc):
        ts.group_sessions = self._real
        return False


class HintSegmentTests(unittest.TestCase):
    """_hint_segment (:238-248) — the regex-replacement path."""

    def test_every_hint_item_renders_its_pinned_segment(self):
        self.assertEqual(len(EXPECTED_SEGMENTS), len(_HINT_ITEMS))
        for (action_id, label, key), expected in zip(_HINT_ITEMS, EXPECTED_SEGMENTS):
            with self.subTest(label=label):
                self.assertEqual(
                    _hint_segment(action_id, label, key),
                    expected.format(tag=TAG),
                )

    def test_the_backreference_is_substituted_not_emitted_literally(self):
        """The direct guard on :248's r-string: a lost \\1 leaves it verbatim."""
        for action_id, label, key in _HINT_ITEMS:
            with self.subTest(label=label):
                segment = _hint_segment(action_id, label, key)
                self.assertNotIn("\\1", segment)
                self.assertRegex(segment, r"\([A-Za-z0-9]\)")

    def test_exactly_one_key_group_is_highlighted(self):
        """`count=1` in the sub call — a second (K) group must stay unstyled."""
        for action_id, label, key in _HINT_ITEMS:
            with self.subTest(label=label):
                self.assertEqual(_hint_segment(action_id, label, key).count(TAG), 1)


class RenderHintTests(unittest.TestCase):
    """_render_hint (:730-750) — the composed bottom row."""

    def test_single_session_mode(self):
        overlay, capture = _overlay(multi_mode=False)
        overlay._render_hint()
        self.assertEqual(
            capture.text,
            _expected_segment_row()
            + "\n"
            + f"{TAG}Enter[/] switch  {TAG}J/Esc[/] close",
        )

    def test_multi_session_mode_with_one_group_omits_the_group_hint(self):
        overlay, capture = _overlay(multi_mode=True)
        with _StubGroups(["only"]):
            overlay._render_hint()
        self.assertEqual(
            capture.text,
            _expected_segment_row()
            + "\n"
            + f"{TAG}Enter[/] switch  {TAG}←/→[/] session  {TAG}J/Esc[/] close",
        )

    def test_multi_session_mode_with_two_groups_adds_the_escaped_group_hint(self):
        """Pins :746 — `\\[` must stay escaped or the bracket is eaten as a tag."""
        overlay, capture = _overlay(multi_mode=True)
        with _StubGroups(["a", "b"]):
            overlay._render_hint()
        self.assertEqual(
            capture.text,
            _expected_segment_row()
            + "\n"
            + f"{TAG}Enter[/] switch  {TAG}←/→[/] session  "
            + f"{TAG}\\[/][/] group  {TAG}J/Esc[/] close",
        )

    def test_the_group_hint_bracket_is_escaped(self):
        """Rendered independently of the exact surrounding text."""
        overlay, capture = _overlay(multi_mode=True)
        with _StubGroups(["a", "b"]):
            overlay._render_hint()
        self.assertIn("\\[/]", capture.text)


class SessionRowPrefixTests(unittest.TestCase):
    """_render_session_row (:798-805) — the `\\[group]` prefix."""

    def _prefix(self, groups: list[str], selected: str | None) -> str:
        overlay = object.__new__(ts.TuiSwitcherOverlay)
        overlay._multi_mode = True
        overlay._all_sessions = []
        overlay._selected_group = selected
        overlay._attached_session = None
        overlay._selected_key = None
        capture = _Capture()
        overlay.query_one = lambda *a, **k: capture
        with _StubGroups(groups):
            overlay._render_session_row()
        return capture.text or ""

    def test_a_real_group_renders_an_escaped_bracket_prefix(self):
        text = self._prefix(["proj"], "proj")
        self.assertTrue(
            text.startswith(f"{TAG}\\[proj][/]  Session: "),
            f"unexpected session row: {text!r}",
        )

    def test_only_the_ungrouped_bucket_renders_no_prefix(self):
        text = self._prefix([ts.PROJECT_GROUP_UNGROUPED_LABEL], None)
        self.assertTrue(
            text.startswith("Session: "), f"unexpected session row: {text!r}"
        )
        self.assertNotIn(TAG, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
