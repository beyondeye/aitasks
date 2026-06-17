"""Tests for the brainstorm Session-lifecycle tab (t983_8).

Session ops (pause/resume/finalize/archive/delete) left the Actions wizard for a
dedicated **Session** tab. These tests cover the new surface and guard the
"split" — the wizard op list must no longer carry session ops.

Following the established brainstorm test pattern (see
``test_brainstorm_node_action_modal.py``): ``BrainstormApp.__init__`` is bypassed
with ``__new__`` and the Textual query layer is replaced by a recording fake, so
no full TUI boot is needed. The end-to-end in-TUI flow (press ``s`` → Session
tab → confirm → apply) is covered by manual verification.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    DeleteSessionModal,
    OperationRow,
    _DESIGN_OPS,
    _SESSION_OPS,
)

_SESSION_KEYS = {op_key for op_key, _label, _desc in _SESSION_OPS}
_DESIGN_KEYS = {op_key for op_key, _label, _desc in _DESIGN_OPS}


class _FakeContainer:
    """Records remove_children()/mount() calls in lieu of a real VerticalScroll."""

    def __init__(self) -> None:
        self.mounted: list = []
        self.cleared = False

    def remove_children(self) -> None:
        self.cleared = True
        self.mounted = []

    def mount(self, widget) -> None:
        self.mounted.append(widget)

    def op_rows(self) -> list:
        return [w for w in self.mounted if isinstance(w, OperationRow)]


def _bare_app(**attrs):
    """A BrainstormApp with __init__ bypassed and a recording query layer."""
    app = BrainstormApp.__new__(BrainstormApp)
    app.read_only = False
    app.session_data = {}
    app.session_path = Path("/nonexistent")
    app._session_confirm_op = ""
    app._wizard_op = ""
    app._wizard_config = {}
    app._wizard_has_sections = False
    app._cmp_section_checks = {}
    app._wizard_subgraph_count = 1
    container = _FakeContainer()
    app._container = container
    app.query_one = lambda *a, **k: container
    app.call_after_refresh = lambda *a, **k: None
    app.notices = []
    app.notify = lambda msg, **kw: app.notices.append((msg, kw))
    for k, v in attrs.items():
        setattr(app, k, v)
    return app, container


class SessionOpDisabledTests(unittest.TestCase):
    """The pure disabled-state logic that drives both the list and the guard."""

    def setUp(self):
        self.app = BrainstormApp.__new__(BrainstormApp)

    def _disabled(self, op_key, status, head="n001"):
        return self.app._is_session_op_disabled(op_key, status, head)

    def test_pause_only_when_active(self):
        self.assertFalse(self._disabled("pause", "active"))
        self.assertTrue(self._disabled("pause", "paused"))

    def test_resume_only_when_paused(self):
        self.assertFalse(self._disabled("resume", "paused"))
        self.assertTrue(self._disabled("resume", "active"))

    def test_finalize_needs_active_and_head(self):
        self.assertFalse(self._disabled("finalize", "active", head="n001"))
        self.assertTrue(self._disabled("finalize", "active", head=None))
        self.assertTrue(self._disabled("finalize", "paused", head="n001"))

    def test_archive_only_when_completed(self):
        self.assertFalse(self._disabled("archive", "completed"))
        self.assertTrue(self._disabled("archive", "active"))

    def test_delete_always_enabled(self):
        for status in ("init", "active", "paused", "completed"):
            self.assertFalse(self._disabled("delete", status))


class RefreshSessionTabTests(unittest.TestCase):
    """_refresh_session_tab mounts one OperationRow per session op with the
    right disabled-state for the current status."""

    def test_mounts_all_session_ops(self):
        app, container = _bare_app(session_data={"status": "active"})
        with mock.patch(
            "brainstorm.brainstorm_app.get_head", return_value="n001"
        ):
            app._refresh_session_tab()
        rows = container.op_rows()
        self.assertEqual([r.op_key for r in rows], [k for k, _, _ in _SESSION_OPS])
        self.assertEqual({r.op_key for r in rows}, _SESSION_KEYS)

    def test_disabled_state_tracks_status(self):
        app, container = _bare_app(session_data={"status": "paused"})
        with mock.patch(
            "brainstorm.brainstorm_app.get_head", return_value="n001"
        ):
            app._refresh_session_tab()
        by_key = {r.op_key: r for r in container.op_rows()}
        # paused: resume enabled, pause/finalize/archive disabled, delete enabled.
        self.assertFalse(by_key["resume"].op_disabled)
        self.assertTrue(by_key["pause"].op_disabled)
        self.assertTrue(by_key["finalize"].op_disabled)
        self.assertTrue(by_key["archive"].op_disabled)
        self.assertFalse(by_key["delete"].op_disabled)

    def test_read_only_shows_no_ops(self):
        app, container = _bare_app(read_only=True, session_data={"status": "completed"})
        app._refresh_session_tab()
        self.assertEqual(container.op_rows(), [])


class WizardSplitRegressionTests(unittest.TestCase):
    """Guard: the Actions wizard op list is design-ops-only now — no session op
    may leak back into op_select."""

    def test_step1_has_no_session_ops(self):
        app, container = _bare_app(session_data={"status": "active"})
        app._enter_wizard_step = lambda step_id: None
        app._mount_recent_ops = lambda c: None
        with mock.patch(
            "brainstorm.brainstorm_app.list_subgraphs", return_value=["umbrella"]
        ):
            app._actions_show_step1()
        keys = {r.op_key for r in container.op_rows()}
        self.assertTrue(keys, "expected design ops to render")
        self.assertEqual(keys, _DESIGN_KEYS)
        self.assertFalse(keys & _SESSION_KEYS, "session ops must not be in the wizard")


class DispatchSessionOpTests(unittest.TestCase):
    """_dispatch_session_op: delete → modal; lifecycle ops → inline confirm."""

    def test_delete_pushes_delete_modal(self):
        app, _ = _bare_app(task_num="42")
        pushed = []
        app.push_screen = lambda screen, cb=None: pushed.append((screen, cb))
        app._dispatch_session_op("delete")
        self.assertEqual(len(pushed), 1)
        self.assertIsInstance(pushed[0][0], DeleteSessionModal)
        self.assertEqual(pushed[0][1], app._on_delete_result)

    def test_lifecycle_op_routes_to_confirm(self):
        app, _ = _bare_app()
        seen = []
        app._show_session_confirm = lambda op: seen.append(op)
        app._dispatch_session_op("pause")
        self.assertEqual(seen, ["pause"])


class SessionConfirmTests(unittest.TestCase):
    """_show_session_confirm stashes the op; _on_session_confirm executes it
    explicitly (no longer reads _wizard_op) and clears the stash."""

    def test_confirm_executes_stashed_op(self):
        app, _ = _bare_app()
        executed = []
        app._execute_session_op = lambda op=None: executed.append(op)
        app._refresh_session_tab = lambda: None
        app._session_op_summary = lambda op: "summary"
        app._show_session_confirm("archive")
        self.assertEqual(app._session_confirm_op, "archive")
        app._on_session_confirm()
        self.assertEqual(executed, ["archive"])
        self.assertEqual(app._session_confirm_op, "")

    def test_cancel_restores_list_without_executing(self):
        app, _ = _bare_app()
        executed = []
        app._execute_session_op = lambda op=None: executed.append(op)
        refreshed = []
        app._refresh_session_tab = lambda: refreshed.append(True)
        app._on_session_cancel()
        self.assertEqual(executed, [])
        self.assertTrue(refreshed)


class SessionOpSummaryTests(unittest.TestCase):
    """One-line confirmation summaries."""

    def test_static_summaries(self):
        app, _ = _bare_app()
        self.assertIn("paused", app._session_op_summary("pause"))
        self.assertIn("resumed", app._session_op_summary("resume"))
        self.assertIn("archived", app._session_op_summary("archive"))

    def test_finalize_summary_reads_head(self):
        app, _ = _bare_app()
        with mock.patch(
            "brainstorm.brainstorm_app.get_head", return_value="n007"
        ):
            summary = app._session_op_summary("finalize")
        self.assertIn("n007", summary)
        self.assertIn("aiplans/", summary)


class ExecuteSessionOpTests(unittest.TestCase):
    """_execute_session_op takes an explicit op (no longer reads _wizard_op)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_session_tab_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_explicit_op_pauses_without_wizard_state(self):
        app, _ = _bare_app(task_num="42")
        app._wizard_op = ""  # wizard state is intentionally empty
        reloaded = []
        app._load_existing_session = lambda: reloaded.append(True)
        with mock.patch("brainstorm.brainstorm_app.save_session") as save:
            app._execute_session_op("pause")
        save.assert_called_once_with("42", {"status": "paused"})
        self.assertTrue(reloaded)


if __name__ == "__main__":
    unittest.main()
