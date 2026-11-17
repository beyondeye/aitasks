"""Tests for the docs-screenshot sample project (t2278_2).

`website/screenshots/sample_project.py` builds the only data a docs screenshot
may show. These tests build into a temporary directory and never touch the
real `aitasks/` tree.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_sample_project.py -v
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

from screenshots import sample_project as sp  # noqa: E402


class BaseDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = sp.build(Path(tmp.name) / "lumen", "base")

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                              text=True, check=True).stdout

    def test_is_a_standalone_ait_project(self):
        self.assertTrue(os.access(self.root / "ait", os.X_OK))
        self.assertTrue((self.root / ".aitask-scripts" / "aitask_ls.sh").is_file())

    def test_the_framework_scripts_are_a_copy_not_a_link(self):
        """TUIs locate their project as ``Path(__file__).resolve().parents[2]``
        (the monitor reads its config and the sitrep list from there): through
        a symlink they would resolve into the real repository and show its
        data. Control: the copy's files resolve inside the sample project."""
        scripts = self.root / ".aitask-scripts"
        self.assertFalse(scripts.is_symlink())
        app = (scripts / "monitor" / "monitor_app.py").resolve()
        self.assertEqual(app.parents[2], self.root.resolve())
        self.assertFalse(any(scripts.rglob("__pycache__")))

    def test_is_a_clean_git_repository_with_one_commit(self):
        self.assertEqual(self._git("rev-list", "--count", "HEAD").strip(), "1")
        self.assertEqual(self._git("status", "--porcelain").strip(), "")
        self.assertIn(sp.PERSON_EMAIL, self._git("log", "-1", "--format=%ae"))

    def test_parent_with_children_and_every_column(self):
        tasks = self.root / "aitasks"
        children = sorted(p.name for p in (tasks / "t12").glob("t12_*.md"))
        self.assertEqual(len(children), 3)
        parent = (tasks / "t12_add_checkout_page.md").read_text()
        self.assertIn("children_to_implement: [t12_1, t12_2, t12_3]", parent)
        columns = {line.split(": ")[1] for p in tasks.rglob("t*.md")
                   for line in p.read_text().splitlines() if line.startswith("boardcol: ")}
        self.assertEqual(columns, {c["id"] for c in sp.BASE_COLUMNS})

    def test_only_invented_names_reach_the_data(self):
        """The doc guide forbids the real repo names in an on-screen example."""
        config = (self.root / "aitasks" / "metadata" / "project_config.yaml").read_text()
        self.assertEqual(config, "project:\n  name: lumen\ntmux:\n  default_session: lumen\n")
        for path in (self.root / "aitasks").rglob("t*.md"):
            text = path.read_text()
            self.assertNotIn("aitasks", text, path.name)
            self.assertNotIn("9000", path.name)

    def test_dates_are_fixed(self):
        for path in (self.root / "aitasks").rglob("t*.md"):
            self.assertIn(f"created_at: {sp.FIXED_STAMP}", path.read_text(), path.name)

    def test_no_timer_can_repaint_the_board(self):
        local = (self.root / "aitasks" / "metadata" / "board_config.local.json").read_text()
        self.assertIn('"auto_refresh_minutes": 0', local)


class BuildContractTests(unittest.TestCase):
    def test_unknown_dataset_is_an_error_naming_the_known_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sp.DatasetError) as ctx:
                sp.build(Path(tmp) / "x", "no_such_dataset")
            self.assertIn("base", str(ctx.exception))
            self.assertFalse((Path(tmp) / "x").exists())

    def test_an_existing_root_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sp.DatasetError):
                sp.build(Path(tmp), "base")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_builders_do_not_import_tui_code(self):
        """A dataset is data. An adapter that imports a TUI would be the design
        this tool replaced."""
        source = Path(sp.__file__).read_text()
        for forbidden in ("textual", "aitask_board", "tui_switcher", "brainstorm_app",
                          "from tests", "import tests"):
            self.assertNotIn(forbidden, source, forbidden)


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          check=True).stdout


class StandinInstallTests(unittest.TestCase):
    """Every dataset ships the stand-in agent (t2278_4)."""

    def test_every_dataset_installs_an_ignored_executable_standin(self):
        for name in sp.DATASETS:
            with self.subTest(name), tempfile.TemporaryDirectory(prefix="ait_shots_test_") as tmp:
                root = sp.build(Path(tmp) / "lumen", name)
                claude = root / sp.STANDIN_BIN / "claude"
                self.assertTrue(os.access(claude, os.X_OK))
                self.assertEqual(_git(root, "status", "--porcelain").strip(), "")
                self.assertEqual(_git(root, "check-ignore", str(claude)).strip(), str(claude))
                version = subprocess.run([str(claude), "--version"], capture_output=True,
                                         text=True, timeout=30,
                                         env={**os.environ, "AIT_PYTHON": sys.executable})
                self.assertEqual(version.stdout.strip(), "2.1.322 (Claude Code)")


class AgentsDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = sp.build(Path(tmp.name) / "lumen", "agents")

    def test_every_operation_launches_the_agent_the_standin_answers_as(self):
        config = json.loads((self.root / "aitasks" / "metadata" / "codeagent_config.json")
                            .read_text())
        self.assertTrue(config["defaults"])
        self.assertEqual({v.split("/")[0] for v in config["defaults"].values()}, {"claudecode"})
        self.assertIn("shadow", config["defaults"])
        self.assertTrue((self.root / "aitasks" / "metadata" / "models_claudecode.json").is_file())
        self.assertTrue((self.root / "aitasks" / "metadata" / "profiles" / "fast.yaml").is_file())

    def test_a_local_origin_holds_main(self):
        self.assertEqual(_git(self.root, "ls-remote", "--heads", "origin").split()[-1],
                         "refs/heads/main")
        remote = _git(self.root, "remote", "get-url", "origin").strip()
        self.assertTrue(Path(remote).resolve().is_relative_to(self.root.resolve()))

    def test_tasks_keep_their_base_status(self):
        """No ``Implementing`` task without a live lock holder: sitrep's crash
        recovery would report each one."""
        for path in (self.root / "aitasks").rglob("t*.md"):
            self.assertNotIn("status: Implementing", path.read_text(), path.name)


class StandinAgentTests(unittest.TestCase):
    """``standin_agent.py``: what it draws and what it records."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(sp.__file__).parent))
        import standin_agent

        cls.agent = standin_agent

    def plain(self, text):
        return re.sub(r"\x1b\[[0-9;]*[mHJ]", "", text)

    def test_roles_from_the_launch_argv(self):
        for argv, role in ((["claude", "--model", "m", "/aitask-pick 14"], "pick"),
                           (["claude", "--model", "m", "/aitask-pick", "14"], "pick"),
                           (["claude", "/aitask-shadow", "%7", "14"], "shadow"),
                           (["claude", "/aitask-sitrep"], "sitrep"),
                           (["claude"], "agent")):
            with self.subTest(argv):
                self.assertEqual(self.agent.role_and_lines(argv)[0], role)

    def test_the_shadow_never_shows_the_followed_pane_id(self):
        _, lines = self.agent.role_and_lines(["claude", "/aitask-shadow", "%7", "14"])
        self.assertNotIn("%7", self.plain("\n".join(lines)))

    def test_every_frame_row_fits_the_pane(self):
        for argv in (["claude", "/aitask-pick", "14"], ["claude", "/aitask-pick", "15"],
                     ["claude", "/aitask-shadow", "%1", "14"], ["claude", "/aitask-sitrep"]):
            _, lines = self.agent.role_and_lines(argv)
            for width in (30, 38, 58, 85, 119):
                with self.subTest(argv=argv[1], width=width):
                    rows = self.plain(self.agent.frame(lines, width, 30)).split("\r\n")
                    self.assertEqual(len(rows), 30)
                    self.assertTrue(all(len(row) <= width for row in rows),
                                    [row for row in rows if len(row) > width])

    def test_wrapping_keeps_the_hanging_indent(self):
        rows = self.agent.wrap("● " + "word " * 20, 30)
        self.assertGreater(len(rows), 1)
        self.assertTrue(all(row.startswith("  ") for row in rows[1:]))
        rows = self.agent.wrap("  ⎿  " + "word " * 20, 30)
        self.assertTrue(all(row.startswith("     ") for row in rows[1:]))

    def test_identity_is_logged_with_the_pane_and_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(self.agent, "STANDIN_DIR", Path(tmp)), \
                    mock.patch.dict(os.environ, {"TMUX_PANE": "%9"}):
                self.agent.log_identity("pick", ["claude", "/aitask-pick", "14"])
            line = (Path(tmp) / "log").read_text().strip()
        self.assertEqual(line, f"pick|/aitask-pick 14|%9|{os.getpid()}")

    def start_in_a_terminal(self, tmp):
        """The stand-in on a real pty, once it is drawn AND in raw mode.
        Returns ``(pid, master)``. A copy of the script in ``tmp`` keeps its
        identity log there."""
        import pty
        import select
        import termios

        script = Path(tmp) / "standin_agent.py"
        script.write_text(Path(self.agent.__file__).read_text())
        pid, master = pty.fork()
        if pid == 0:                                  # child: the stand-in itself
            os.execv(sys.executable, [sys.executable, str(script), "/aitask-pick", "14"])
        deadline = time.monotonic() + 15
        seen = b""
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                seen += os.read(master, 4096)
            # It draws first, then switches the terminal to raw mode (no ICANON).
            if b"for shortcuts" in seen and not termios.tcgetattr(master)[3] & termios.ICANON:
                return pid, master
        os.kill(pid, 9)
        os.waitpid(pid, 0)
        os.close(master)
        self.fail("the stand-in never reached raw mode")

    def wait_exit(self, pid, master, seconds):
        """The exit code, or None if it is still running after ``seconds``."""
        import select

        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                return os.waitstatus_to_exitcode(status)
            if select.select([master], [], [], 0.05)[0]:
                try:
                    os.read(master, 4096)
                except OSError:
                    pass
        return None

    def test_ctrl_c_and_ctrl_d_end_it_and_restore_the_terminal(self):
        import termios

        for key in (b"\x03", b"\x04"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                pid, master = self.start_in_a_terminal(tmp)
                try:
                    os.write(master, key)
                    code = self.wait_exit(pid, master, 10)
                    self.assertEqual(code, 0)
                    # The mode it found is back: canonical input and echo.
                    mode = termios.tcgetattr(master)[3]
                    self.assertTrue(mode & termios.ICANON)
                    self.assertTrue(mode & termios.ECHO)
                finally:
                    if code is None:
                        os.kill(pid, 9)
                        os.waitpid(pid, 0)
                    os.close(master)

    def test_any_other_key_leaves_it_running(self):
        """Control for the test above: only C-c and C-d end it."""
        with tempfile.TemporaryDirectory() as tmp:
            pid, master = self.start_in_a_terminal(tmp)
            code = None
            try:
                os.write(master, b"q\r")
                code = self.wait_exit(pid, master, 1.0)
                self.assertIsNone(code)
                os.write(master, b"\x04")
                code = self.wait_exit(pid, master, 10)
                self.assertEqual(code, 0)
            finally:
                if code is None:                      # still running: never leak it
                    os.kill(pid, 9)
                    os.waitpid(pid, 0)
                os.close(master)

    def test_it_imports_nothing_from_tests_or_the_framework(self):
        import ast

        tree = ast.parse(Path(self.agent.__file__).read_text())
        modules = {alias.name.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.Import) for alias in node.names}
        modules |= {(node.module or "").split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom)}
        stdlib = set(sys.stdlib_module_names) | {"__future__"}
        self.assertEqual(modules - stdlib, set())


if __name__ == "__main__":
    unittest.main()
