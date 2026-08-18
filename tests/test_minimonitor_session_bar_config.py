"""`tmux.minimonitor.session_bar` must actually reach the app (t1566).

The session bar ships hidden, so this config key is the *only* way a user can
get it back. Every other test of the feature sets ``_session_bar_enabled``
directly on an app instance — which means a misspelt key in ``main()``, or a
constructor argument that was read but never forwarded, would leave the option
**inert while the whole rendered suite stayed green**. That gap is what this
module exists to close, and it is why it lives apart from
``test_minimonitor_top_chrome_render.py``: that module's contract is rendered
geometry, this one's is config-to-constructor wiring.

The chain, end to end:

    project_config.yaml -> main() -> constructor kwarg
      -> _session_bar_enabled -> bar.display -> rows on screen

Links 1-3 are here; the last two are in the render module's
``_populate``/``CollapseToggleContractTests``.

``main()`` is driven for real — not re-implemented — through its module-level
seams: ``load_project_tmux_config``, ``load_monitor_config``,
``_detect_tmux_session``, ``sys.argv`` and ``MiniMonitorApp`` are patched, so
nothing touches tmux or the repository's own config file, and the assertion is
on the kwargs the production call site actually passed.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts" / "monitor")
)

import minimonitor_app as mm  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def _main_kwargs(tmux_config):
    """Run the real ``main()`` over ``tmux_config``; return its app kwargs."""
    captured = {}

    class _CaptureApp:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            """Never start a UI — main() is what is under test, not the app."""

    with patch.object(mm, "load_project_tmux_config", lambda root: tmux_config), \
         patch.object(mm, "load_monitor_config", lambda root: {}), \
         patch.object(mm, "_detect_tmux_session", lambda: "probe-session"), \
         patch.object(mm, "MiniMonitorApp", _CaptureApp), \
         patch.object(sys, "argv", ["minimonitor"]):
        mm.main()
    return captured


class MainReadsTheSessionBarKeyTests(unittest.TestCase):
    """One case per shape a user's `project_config.yaml` can actually take."""

    def test_absent_minimonitor_block_defaults_to_off(self):
        self.assertIs(_main_kwargs({})["session_bar"], False)

    def test_block_present_but_key_absent_defaults_to_off(self):
        """The realistic case: someone set `width` and nothing else."""
        cfg = {"minimonitor": {"width": 40}}
        self.assertIs(_main_kwargs(cfg)["session_bar"], False)

    def test_explicit_false_is_off(self):
        cfg = {"minimonitor": {"session_bar": False}}
        self.assertIs(_main_kwargs(cfg)["session_bar"], False)

    def test_explicit_true_reaches_the_constructor(self):
        """The one row a misspelt key breaks — the rest pass either way.

        `session_bar: false` and an unread key are indistinguishable, so this is
        the assertion that actually proves the wiring rather than the default.
        """
        cfg = {"minimonitor": {"session_bar": True}}
        self.assertIs(_main_kwargs(cfg)["session_bar"], True)

    def test_malformed_minimonitor_value_falls_back_instead_of_raising(self):
        """`minimonitor: oops` must not take the TUI down on startup.

        Same guard shape the sibling `width` key uses; a bare `in` test against
        a string would raise `TypeError` here instead of defaulting.
        """
        cfg = {"minimonitor": "oops"}
        self.assertIs(_main_kwargs(cfg)["session_bar"], False)

    def test_the_harness_would_notice_a_dropped_kwarg(self):
        """NEGATIVE CONTROL for the five cases above.

        They all read ``captured["session_bar"]``; if main() stopped passing the
        kwarg entirely they would fail with `KeyError` rather than a readable
        assertion, and a reader could not tell "wired to False" from "not wired
        at all". Name the distinction explicitly.
        """
        self.assertIn(
            "session_bar", _main_kwargs({}),
            "main() no longer passes session_bar to MiniMonitorApp — the "
            "config key is inert regardless of what the value cases say",
        )


class ConstructorStoresTheFlagTests(unittest.TestCase):
    """Link 3: the kwarg must land on the attribute the render path reads."""

    def _app(self, **kwargs):
        return mm.MiniMonitorApp(
            session="probe-session", project_root=REPO_ROOT,
            refresh_seconds=999, **kwargs,
        )

    def test_default_is_off(self):
        self.assertIs(self._app()._session_bar_enabled, False)

    def test_true_is_stored(self):
        self.assertIs(self._app(session_bar=True)._session_bar_enabled, True)

    def test_the_default_survives_a_new_without_init(self):
        """Several suites build the app with `__new__` and hand-set attributes.

        `_rebuild_session_bar` reads `_session_bar_enabled` on every tick, so an
        `__init__`-only default would `AttributeError` there — the same hazard
        the t1539 scroll state is a class attribute for.
        """
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        self.assertIs(app._session_bar_enabled, False)


if __name__ == "__main__":
    unittest.main()
