"""Tests for StaleEntryModal (t826_10).

Verifies:
  - Self-contained DEFAULT_CSS (memory feedback_modal_self_contained_css).
  - Prune action calls aitask_projects.sh remove --force.
  - Repoint action calls aitask_projects.sh update <name> <new_path>.
  - Cancel dismisses cleanly without firing a subprocess.
  - Prune failure surfaces the stderr line, no RegistryRefresh posted.
  - Empty repoint input is a no-op.

The modal is instantiated outside a running Textual App, so app /
dismiss / post_message are monkeypatched directly on the instance.
This pattern is fine because all the methods under test only touch
those three slots plus subprocess.run.

Run: python3 tests/test_stale_entry_modal.py
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

import stale_entry_modal  # noqa: E402
from stale_entry_modal import RegistryRefresh, StaleEntryModal  # noqa: E402


def _build_modal(name: str = "ghost", root: Path = Path("/tmp/nope")):
    """Create a StaleEntryModal and stub the textual-runtime slots."""
    modal = StaleEntryModal(name, root)
    modal.dismiss = mock.Mock()
    modal.post_message = mock.Mock()
    return modal


class StaleEntryModalTests(unittest.TestCase):
    def setUp(self) -> None:
        # Patch the read-only `app` property on the class for the
        # duration of each test, so `modal.app.notify(...)` lands on a
        # Mock we can inspect.
        self._mock_app = mock.Mock()
        self._app_patch = mock.patch.object(
            StaleEntryModal, "app", self._mock_app,
        )
        self._app_patch.start()

    def tearDown(self) -> None:
        self._app_patch.stop()
    def test_css_is_self_contained(self):
        css = StaleEntryModal.DEFAULT_CSS
        self.assertIn("#stale_dialog", css)
        self.assertIn("#stale_actions", css)
        self.assertIn("Button", css)
        self.assertIn("$warning", css)

    def test_prune_calls_remove_force(self):
        modal = _build_modal("ghost")
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(
            stale_entry_modal.subprocess, "run", return_value=completed,
        ) as run:
            modal._do_prune()
        run.assert_called_once()
        argv = run.call_args.args[0]
        self.assertEqual(argv[-3:], ["remove", "ghost", "--force"])
        modal.app.notify.assert_called_once()
        self.assertIn("Removed ghost", modal.app.notify.call_args.args[0])
        posted = modal.post_message.call_args.args[0]
        self.assertIsInstance(posted, RegistryRefresh)
        modal.dismiss.assert_called_once_with("pruned")

    def test_repoint_calls_update(self):
        modal = _build_modal("moved")
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(
            stale_entry_modal.subprocess, "run", return_value=completed,
        ) as run:
            modal._apply_repoint("/new/path")
        run.assert_called_once()
        argv = run.call_args.args[0]
        self.assertEqual(argv[-3:], ["update", "moved", "/new/path"])
        posted = modal.post_message.call_args.args[0]
        self.assertIsInstance(posted, RegistryRefresh)
        modal.dismiss.assert_called_once_with("repointed")

    def test_cancel_dismisses_without_subprocess(self):
        modal = _build_modal()
        with mock.patch.object(stale_entry_modal.subprocess, "run") as run:
            modal._on_cancel()
        run.assert_not_called()
        modal.dismiss.assert_called_once_with(None)
        modal.post_message.assert_not_called()

    def test_prune_failure_surfaces_stderr(self):
        modal = _build_modal("ghost")
        completed = mock.Mock(
            returncode=1, stdout="", stderr="boom\n",
        )
        with mock.patch.object(
            stale_entry_modal.subprocess, "run", return_value=completed,
        ):
            modal._do_prune()
        modal.app.notify.assert_called_once()
        msg = modal.app.notify.call_args.args[0]
        self.assertIn("Prune failed: boom", msg)
        kwargs = modal.app.notify.call_args.kwargs
        self.assertEqual(kwargs.get("severity"), "error")
        modal.post_message.assert_not_called()
        modal.dismiss.assert_called_once_with(None)

    def test_repoint_failure_keeps_modal_open(self):
        # Validation error from cmd_update should NOT dismiss the modal
        # (the user may want to retry with a different path) and must
        # NOT post a RegistryRefresh.
        modal = _build_modal("ghost")
        completed = mock.Mock(
            returncode=1, stdout="",
            stderr="Not an aitasks project (no marker)\n",
        )
        with mock.patch.object(
            stale_entry_modal.subprocess, "run", return_value=completed,
        ):
            modal._apply_repoint("/no/marker/here")
        msg = modal.app.notify.call_args.args[0]
        self.assertIn("Repoint failed", msg)
        modal.post_message.assert_not_called()
        modal.dismiss.assert_not_called()

    def test_empty_repoint_input_is_noop(self):
        modal = _build_modal()
        with mock.patch.object(stale_entry_modal.subprocess, "run") as run:
            modal._apply_repoint(None)
            modal._apply_repoint("")
        run.assert_not_called()
        modal.post_message.assert_not_called()
        modal.dismiss.assert_not_called()


if __name__ == "__main__":
    unittest.main()
