"""Tests for the brainstorm always-on runtime strip + the finalized tab keymap
(t983_9).

Two concerns, both testable without a running Textual App:

1. The pure runner-state derivation backing the always-on header strip
   (`derive_runner_state`, `format_status_strip`). These take plain values and
   do no I/O, mirroring the model used by `tests/test_brainstorm_wizard_steps.py`.
2. The finalized Browse/Session/Running tab keymap — asserted against the
   class-level ``BINDINGS`` and action methods so the Status→Running rename
   cannot silently regress (a missed reference would hide a key binding).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    derive_runner_state,
    format_status_strip,
)


class DeriveRunnerStateTests(unittest.TestCase):
    def test_none_is_grey_no_runner(self):
        self.assertEqual(derive_runner_state("none", False), ("No runner", "#888888"))

    def test_stopped_is_grey(self):
        self.assertEqual(
            derive_runner_state("stopped", False), ("Runner stopped", "#888888")
        )

    def test_active_is_green(self):
        self.assertEqual(
            derive_runner_state("running", False), ("Runner active", "#50FA7B")
        )

    def test_stale_is_red(self):
        self.assertEqual(
            derive_runner_state("running", True), ("Runner stale", "#FF5555")
        )

    def test_none_and_stopped_win_over_stale(self):
        # An explicit none/stopped status takes precedence over the stale flag.
        self.assertEqual(derive_runner_state("none", True), ("No runner", "#888888"))
        self.assertEqual(
            derive_runner_state("stopped", True), ("Runner stopped", "#888888")
        )


class FormatStatusStripTests(unittest.TestCase):
    def test_idle_when_zero_running(self):
        self.assertEqual(
            format_status_strip("running", False, 0),
            "[#50FA7B]●[/#50FA7B] Runner active   idle",
        )

    def test_count_rendered_when_running(self):
        self.assertEqual(
            format_status_strip("running", False, 3),
            "[#50FA7B]●[/#50FA7B] Runner active   ▶ 3 running",
        )

    def test_singular_count(self):
        self.assertIn("▶ 1 running", format_status_strip("running", False, 1))

    def test_no_runner_idle(self):
        self.assertEqual(
            format_status_strip("none", False, 0),
            "[#888888]●[/#888888] No runner   idle",
        )

    def test_dot_color_tracks_state(self):
        # The dot color must match the derived state color (stale → red).
        self.assertTrue(
            format_status_strip("running", True, 2).startswith("[#FF5555]●[/#FF5555]")
        )


class RunningTabKeymapTests(unittest.TestCase):
    """Locks the finalized b/s/r keymap + Status→Running rename (t983_9)."""

    def _binding_map(self):
        return {
            b.key: b.action
            for b in BrainstormApp.BINDINGS
            if hasattr(b, "key") and hasattr(b, "action")
        }

    def test_tab_keys_final(self):
        m = self._binding_map()
        self.assertEqual(m.get("b"), "tab_browse")
        self.assertEqual(m.get("s"), "tab_session")
        self.assertEqual(m.get("r"), "tab_running")

    def test_no_stale_status_action(self):
        m = self._binding_map()
        self.assertNotIn("tab_status", m.values())

    def test_action_methods_exist(self):
        for action in ("action_tab_browse", "action_tab_session", "action_tab_running"):
            self.assertTrue(
                hasattr(BrainstormApp, action), f"missing {action}"
            )
        # The renamed-away method must be gone (else the rename is incomplete).
        self.assertFalse(hasattr(BrainstormApp, "action_tab_status"))


if __name__ == "__main__":
    unittest.main()
