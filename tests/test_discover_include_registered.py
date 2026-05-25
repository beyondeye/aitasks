"""Tests for `discover_aitasks_sessions(include_registered=True)` (t826_2).

Verifies:
  - Synthesized entries from `~/.config/aitasks/projects.yaml` carry
    `is_live=False` and resolve `session` from each project's
    `tmux.default_session` (or default to "aitasks").
  - The `AITASKS_PROJECTS_INDEX` env-var override is honored.
  - Entries whose path is missing the marker file are silently
    excluded (stale handling — surfacing them is t826_5's scope).
  - When a registered project's `project_name` already appears in
    the live-tmux results, the registry entry is deduped out (the
    live one wins).

Run: python3 tests/test_discover_include_registered.py
  or: bash tests/run_all_python_tests.sh
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

import agent_launch_utils
from agent_launch_utils import AitasksSession, discover_aitasks_sessions


def _make_fake_project(tmp: Path, *, default_session: str | None = None) -> Path:
    """Create a fake aitasks project rooted at <tmp>."""
    (tmp / "aitasks" / "metadata").mkdir(parents=True)
    cfg = tmp / "aitasks" / "metadata" / "project_config.yaml"
    if default_session is not None:
        cfg.write_text(f"tmux:\n  default_session: {default_session}\n")
    else:
        cfg.write_text("project:\n  name: fake\n")
    return tmp


def _make_registry(path: Path, entries: list[tuple[str, Path]]) -> None:
    lines = ["projects:\n"]
    for name, root in entries:
        lines.append(f"  - name: {name}\n")
        lines.append(f"    path: {root}\n")
    path.write_text("".join(lines))


class IncludeRegisteredTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        # Empty tmux to force the live-tmux loop to return [].
        self._tmux_patch = mock.patch.object(
            agent_launch_utils.subprocess, "run",
            side_effect=self._fake_run,
        )
        self._tmux_patch.start()
        self._index_override = None

    def tearDown(self) -> None:
        self._tmux_patch.stop()
        self._tmpdir.cleanup()
        os.environ.pop("AITASKS_PROJECTS_INDEX", None)

    def _fake_run(self, argv, *args, **kwargs):
        """Mock subprocess.run for tmux calls only — return empty session list."""
        if argv and argv[0] == "tmux":
            return mock.Mock(returncode=1, stdout="", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    def _set_registry(self, entries: list[tuple[str, Path]]) -> Path:
        idx = self.tmp / "projects.yaml"
        _make_registry(idx, entries)
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        return idx

    def test_inactive_entry_has_is_live_false(self):
        proj = _make_fake_project(self.tmp / "proj_a", default_session="customsess")
        self._set_registry([("proj_a", proj)])
        result = discover_aitasks_sessions(include_registered=True)
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertFalse(entry.is_live)
        self.assertEqual(entry.session, "customsess")
        self.assertEqual(entry.project_name, "proj_a")
        self.assertEqual(entry.project_root, proj)

    def test_session_defaults_to_aitasks_when_field_absent(self):
        proj = _make_fake_project(self.tmp / "proj_b", default_session=None)
        self._set_registry([("proj_b", proj)])
        result = discover_aitasks_sessions(include_registered=True)
        self.assertEqual(result[0].session, "aitasks")

    def test_env_var_override_is_honored(self):
        proj = _make_fake_project(self.tmp / "proj_env", default_session="envsess")
        self._set_registry([("proj_env", proj)])
        # _set_registry already set AITASKS_PROJECTS_INDEX; verify by
        # unsetting the default location is irrelevant — index path
        # came from the env var.
        result = discover_aitasks_sessions(include_registered=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].project_name, "proj_env")

    def test_stale_entry_silently_excluded(self):
        # Registry points at a path that doesn't contain the marker
        # file — the entry must be skipped without error.
        idx = self.tmp / "projects.yaml"
        _make_registry(idx, [("ghost", self.tmp / "nonexistent")])
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        result = discover_aitasks_sessions(include_registered=True)
        self.assertEqual(result, [])

    def test_multiple_entries_emitted_sorted(self):
        proj_x = _make_fake_project(self.tmp / "px", default_session="bbb")
        proj_y = _make_fake_project(self.tmp / "py", default_session="aaa")
        self._set_registry([("px", proj_x), ("py", proj_y)])
        result = discover_aitasks_sessions(include_registered=True)
        # discover_aitasks_sessions sorts by session name (the dataclass
        # field), so "aaa" (py) comes before "bbb" (px).
        self.assertEqual([s.session for s in result], ["aaa", "bbb"])
        self.assertEqual([s.project_name for s in result], ["py", "px"])

    def test_live_entry_dedupes_registered_with_same_project_name(self):
        proj = _make_fake_project(self.tmp / "shared", default_session="not_used")
        self._set_registry([("shared", proj)])
        # Inject a fake "live" entry with project_name="shared" — the
        # registry entry must be deduped out by name.
        live_entry = AitasksSession(
            session="live_sess",
            project_root=proj,
            project_name="shared",
            is_live=True,
        )
        with mock.patch.object(
            agent_launch_utils, "_walk_up_to_aitasks",
            side_effect=lambda p: proj if p == proj else None,
        ):
            # Fake tmux to return one live session whose pane walks up
            # to <proj>.
            def _fake_tmux(argv, *a, **k):
                if argv[:2] == ["tmux", "list-sessions"]:
                    return mock.Mock(returncode=0, stdout="live_sess\n", stderr="")
                if argv[:2] == ["tmux", "list-panes"]:
                    return mock.Mock(returncode=0, stdout=f"{proj}\n", stderr="")
                if argv[0] == "tmux":
                    return mock.Mock(returncode=1, stdout="", stderr="")
                return mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch.object(
                agent_launch_utils.subprocess, "run", side_effect=_fake_tmux,
            ):
                result = discover_aitasks_sessions(include_registered=True)
        # Exactly one entry — the live one — survives.
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].is_live)
        self.assertEqual(result[0].session, "live_sess")
        # Mention `live_entry` for clarity even though we built it
        # manually for documentation; the real check is on result.
        self.assertEqual(live_entry.project_name, "shared")


if __name__ == "__main__":
    unittest.main()
