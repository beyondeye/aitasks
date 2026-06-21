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
from agent_launch_utils import (
    AitasksSession,
    _parse_registry_records,
    _read_registry_index,
    discover_aitasks_sessions,
)


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
        # Pin the module-level gateway singleton to NO socket flag: _fake_run
        # prefix-matches argv[:2] == ["tmux", "list-sessions"], but since t953
        # a default-constructed TmuxClient carries `-L ait`. Swapping the
        # singleton (rather than setting the env var pre-import) stays correct
        # under run_all_python_tests.sh, where another module may import
        # agent_launch_utils first and freeze the cached socket args.
        self._saved_tmux = agent_launch_utils._TMUX
        agent_launch_utils._TMUX = agent_launch_utils.TmuxClient(socket_args=[])
        # Empty tmux to force the live-tmux loop to return [].
        self._tmux_patch = mock.patch.object(
            agent_launch_utils.subprocess, "run",
            side_effect=self._fake_run,
        )
        self._tmux_patch.start()
        self._index_override = None

    def tearDown(self) -> None:
        self._tmux_patch.stop()
        agent_launch_utils._TMUX = self._saved_tmux
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

    def test_stale_entry_surfaces_with_is_stale_true(self):
        # Registry points at a path that doesn't contain the marker
        # file — the entry must reach the consumer with is_stale=True
        # so the TUI switcher can render it distinctly (t826_6).
        idx = self.tmp / "projects.yaml"
        _make_registry(idx, [("ghost", self.tmp / "nonexistent")])
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        result = discover_aitasks_sessions(include_registered=True)
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertFalse(entry.is_live)
        self.assertTrue(entry.is_stale)
        self.assertEqual(entry.project_name, "ghost")
        # _read_default_session falls back to "aitasks" when the
        # project_config.yaml is missing — acceptable for STALE rows,
        # the session name is informational.
        self.assertEqual(entry.session, "aitasks")

    def test_ok_entry_has_is_stale_false(self):
        proj = _make_fake_project(self.tmp / "proj_ok", default_session="ok_sess")
        self._set_registry([("proj_ok", proj)])
        result = discover_aitasks_sessions(include_registered=True)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].is_stale)
        self.assertFalse(result[0].is_live)

    def test_read_registry_index_returns_status_tuples(self):
        # Direct unit test: _read_registry_index must return a list of
        # (name, path, status, project_group) 4-tuples (t1025_1 added the
        # group), with status ∈ {"OK", "STALE"}.
        proj_ok = _make_fake_project(self.tmp / "ok_proj")
        idx = self.tmp / "projects.yaml"
        _make_registry(idx, [
            ("ok_proj", proj_ok),
            ("stale_proj", self.tmp / "no_such_dir"),
        ])
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        entries = _read_registry_index()
        self.assertEqual(len(entries), 2)
        for tup in entries:
            self.assertEqual(len(tup), 4)
        names = {e[0]: e[2] for e in entries}
        self.assertEqual(names["ok_proj"], "OK")
        self.assertEqual(names["stale_proj"], "STALE")
        # No project_group declared -> empty 4th element.
        groups = {e[0]: e[3] for e in entries}
        self.assertEqual(groups["ok_proj"], "")

    def test_parse_registry_records_exposes_named_fields(self):
        idx = self.tmp / "projects.yaml"
        idx.write_text(
            "projects:\n"
            "  - name: alpha\n"
            "    path: /tmp/alpha\n"
            "    git_remote: https://example.test/alpha.git\n"
            "    last_opened: 2026-01-02\n"
            "    project_group: suite_a\n"
        )
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)

        records = _parse_registry_records()

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.name, "alpha")
        self.assertEqual(record.path, "/tmp/alpha")
        self.assertEqual(record.git_remote, "https://example.test/alpha.git")
        self.assertEqual(record.last_opened, "2026-01-02")
        self.assertEqual(record.project_group, "suite_a")

    def test_multiple_entries_emitted_sorted(self):
        proj_x = _make_fake_project(self.tmp / "px", default_session="bbb")
        proj_y = _make_fake_project(self.tmp / "py", default_session="aaa")
        self._set_registry([("px", proj_x), ("py", proj_y)])
        result = discover_aitasks_sessions(include_registered=True)
        # discover_aitasks_sessions sorts by session name (the dataclass
        # field), so "aaa" (py) comes before "bbb" (px).
        self.assertEqual([s.session for s in result], ["aaa", "bbb"])
        self.assertEqual([s.project_name for s in result], ["py", "px"])

    def test_live_entry_dedupes_stale_registered_with_same_project_name(self):
        # Parallel of the OK-dedup test below: a STALE registry entry
        # sharing project_name with a live entry must NOT leak through
        # (the live one wins; the user is already in the session).
        # Locks the de-dup invariant for the t826_10 stale-render path
        # so a future tweak to discover_aitasks_sessions does not
        # surface STALE ghosts next to live rows.
        ghost_root = self.tmp / "no_such_dir"  # marker missing -> STALE
        self._set_registry([("shared", ghost_root)])
        # Live project's basename must equal the registry name for
        # dedup-by-project_name to fire (project_name comes from
        # project_root.name on the live side).
        live_only_project = _make_fake_project(
            self.tmp / "shared", default_session="live_sess",
        )
        with mock.patch.object(
            agent_launch_utils, "_walk_up_to_aitasks",
            side_effect=lambda p: live_only_project if p == live_only_project else None,
        ):
            def _fake_tmux(argv, *a, **k):
                if argv[:2] == ["tmux", "list-sessions"]:
                    return mock.Mock(returncode=0, stdout="live_sess\n", stderr="")
                if argv[:2] == ["tmux", "list-panes"]:
                    return mock.Mock(returncode=0, stdout=f"{live_only_project}\n", stderr="")
                if argv[0] == "tmux":
                    return mock.Mock(returncode=1, stdout="", stderr="")
                return mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch.object(
                agent_launch_utils.subprocess, "run", side_effect=_fake_tmux,
            ):
                result = discover_aitasks_sessions(include_registered=True)
        # Only the live entry survives — no STALE ghost beside it.
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].is_live)
        self.assertFalse(result[0].is_stale)

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
