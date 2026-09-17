"""TUI switcher: warn when a bootstrap fell back on an unreadable default_session (t1811).

`_ensure_session_live` creates a registered-but-inactive project's tmux session
through `tmux_bootstrap.sh`. When that project's `tmux.default_session` cannot be
read faithfully, the helper uses "aitasks" and reports a
`DEFAULT_SESSION_UNREADABLE:<shape>:<cfg>` sentinel on stderr. Before t1811 the
switcher read the helper's stderr only on failure, so a successful bootstrap
under the fallback name was silent — on exactly the path that creates the
session. Two routes carry the shape to the notification: the discovery-time
`AitasksSession.default_session_problem` field, and the helper's stderr.

The real method runs; only `subprocess.run` (the helper) and `app` are replaced.
The sentinel stderr is produced by the real bash reporter, not typed here.

Run: python3 tests/test_tui_switcher_default_session_notify.py
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import tui_switcher as ts  # noqa: E402
from agent_launch_utils import AitasksSession  # noqa: E402

BOOTSTRAP = REPO_ROOT / ".aitask-scripts" / "lib" / "tmux_bootstrap.sh"


def _real_sentinel_stderr(shape: str) -> str:
    """What the helper writes for an unreadable value, from the real reporter."""
    return subprocess.run(
        ["bash", "-c",
         'source "$1"; _tmux_bootstrap_report_unreadable "$2" "$3"; '
         'echo "spawn_session_detached: using tmux session \'aitasks\' instead" >&2',
         "_", str(BOOTSTRAP), "/p/proj_b/aitasks/metadata/project_config.yaml", shape],
        capture_output=True, text=True, check=True,
    ).stderr


def _entry(*, problem: str | None = None) -> AitasksSession:
    return AitasksSession(
        session="aitasks",
        project_root=Path("/p/proj_b"),
        project_name="proj_b",
        is_live=False,
        default_session_problem=problem,
    )


class EnsureSessionLiveNotifyTests(unittest.TestCase):
    def _run(self, entry: AitasksSession, *, rc: int, stderr: str):
        ov = ts.TuiSwitcherOverlay(session="sA", selected_session="aitasks")
        ov._all_sessions = [entry]
        ov._selected_key = entry.key
        ov._push_stale_modal = MagicMock()
        app = MagicMock()
        calls = []

        def fake_run(argv, *a, **k):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, rc, stdout="", stderr=stderr)

        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=app), \
             patch.object(subprocess, "run", side_effect=fake_run):
            ok = ov._ensure_session_live()
        # The real method reached the real helper invocation.
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1].endswith("tmux_bootstrap.sh"), calls[0])
        warnings = [c for c in app.notify.call_args_list
                    if c.kwargs.get("severity") == "warning"]
        return ok, ov, app, warnings

    def test_sentinel_on_stderr_warns_after_a_successful_bootstrap(self):
        stderr = _real_sentinel_stderr("block_scalar")
        ok, ov, _app, warnings = self._run(_entry(), rc=0, stderr=stderr)
        self.assertTrue(ok)
        self.assertEqual(len(warnings), 1)
        message = warnings[0].args[0]
        for part in ("proj_b", "block_scalar", "'aitasks'"):
            self.assertIn(part, message)
        self.assertTrue(ov._all_sessions[0].is_live, "the bootstrap still counts as done")

    def test_a_file_level_shape_is_worded_as_invalid_yaml(self):
        """encoding / non_printable describe the file, not the default_session line (t1825)."""
        for shape in ("non_printable", "encoding"):
            with self.subTest(route="stderr", shape=shape):
                ok, _ov, _app, warnings = self._run(
                    _entry(), rc=0, stderr=_real_sentinel_stderr(shape))
                self.assertTrue(ok)
                self.assertEqual(len(warnings), 1)
                message = warnings[0].args[0]
                for part in ("proj_b", "project_config.yaml is not valid YAML", shape, "'aitasks'"):
                    self.assertIn(part, message)
                self.assertNotIn("single-line", message)
            with self.subTest(route="field", shape=shape):
                _ok, _ov, _app, warnings = self._run(_entry(problem=shape), rc=0, stderr="")
                self.assertIn("not valid YAML", warnings[0].args[0])

    def test_an_illegal_name_is_worded_as_a_tmux_target_problem(self):
        """illegal_tmux_name is neither wording above (t1828).

        The value IS a single-line plain scalar and the file IS valid YAML —
        it was read correctly and is simply unusable as a tmux target, so it
        needs its own sentence in both the bash reporter and this notice.
        """
        for route, kwargs in (
            ("stderr", dict(entry=_entry(),
                            stderr=_real_sentinel_stderr("illegal_tmux_name"))),
            ("field", dict(entry=_entry(problem="illegal_tmux_name"), stderr="")),
        ):
            with self.subTest(route=route):
                ok, _ov, _app, warnings = self._run(
                    kwargs["entry"], rc=0, stderr=kwargs["stderr"])
                self.assertTrue(ok)
                self.assertEqual(len(warnings), 1)
                message = warnings[0].args[0]
                for part in ("proj_b", "target separators", "'aitasks'"):
                    self.assertIn(part, message)
                self.assertNotIn("single-line", message)
                self.assertNotIn("not valid YAML", message)

    def test_a_line_shape_keeps_the_value_wording(self):
        """CONTROL for the branch above: a line shape still names the value form."""
        _ok, _ov, _app, warnings = self._run(_entry(problem="block_scalar"), rc=0, stderr="")
        self.assertIn("single-line plain or quoted value", warnings[0].args[0])
        self.assertNotIn("not valid YAML", warnings[0].args[0])

    def test_the_entry_field_alone_also_warns(self):
        ok, _ov, _app, warnings = self._run(_entry(problem="typed_scalar"), rc=0, stderr="")
        self.assertTrue(ok)
        self.assertEqual(len(warnings), 1)
        self.assertIn("typed_scalar", warnings[0].args[0])

    def test_a_readable_config_bootstraps_silently(self):
        """NEGATIVE CONTROL: no field, no sentinel -> no notification at all."""
        ok, ov, app, warnings = self._run(_entry(), rc=0, stderr="")
        self.assertTrue(ok)
        self.assertEqual(warnings, [])
        app.notify.assert_not_called()
        self.assertTrue(ov._all_sessions[0].is_live)

    def test_a_failed_bootstrap_keeps_its_own_path(self):
        """NEGATIVE CONTROL: a stale-path failure opens the modal, not this warning."""
        stderr = ("BOOTSTRAP_FAILED:stale_path\n"
                  "spawn_session_detached: not an aitasks project: /p/proj_b\n")
        ok, ov, _app, warnings = self._run(_entry(), rc=42, stderr=stderr)
        self.assertFalse(ok)
        self.assertEqual(warnings, [])
        ov._push_stale_modal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
