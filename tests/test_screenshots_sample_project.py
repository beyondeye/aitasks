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


def _framework_env(root):
    """The environment a session's setup command gets, for a framework call."""
    home = root / ".standin" / "home"
    return {**os.environ, "HOME": str(home), "AIT_PYTHON": sys.executable,
            # As a session pins them: a framework call must not write into the
            # caller's configuration or cache (the artifact cache links into
            # this temp project).
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            # The sample person, as a session's scratch .gitconfig names them
            # (never the identity of whoever runs the tests).
            "GIT_AUTHOR_NAME": sp.PERSON_NAME, "GIT_AUTHOR_EMAIL": sp.PERSON_EMAIL,
            "GIT_COMMITTER_NAME": sp.PERSON_NAME, "GIT_COMMITTER_EMAIL": sp.PERSON_EMAIL,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": f"{root / sp.STANDIN_BIN}{os.pathsep}{os.environ['PATH']}"}


class PinnedPythonShimTests(unittest.TestCase):
    """A bare ``python3`` in a framework script must not be the user's wrapper,
    which runs ``$HOME/.aitask/venv`` and breaks under the scratch HOME."""

    def test_python_on_the_standin_path_is_the_pinned_interpreter(self):
        with tempfile.TemporaryDirectory(prefix="ait_shots_test_") as tmp:
            root = sp.build(Path(tmp) / "lumen", "base")
            for name in ("python3", "python"):
                shim = root / sp.STANDIN_BIN / name
                out = subprocess.run([str(shim), "-c", "import sys; print(sys.executable)"],
                                     capture_output=True, text=True, timeout=30,
                                     env={**os.environ, "HOME": tmp,
                                          "AIT_PYTHON": sys.executable})
                self.assertEqual(out.stdout.strip(), sys.executable, out.stderr)
                unset = {k: v for k, v in os.environ.items() if k != "AIT_PYTHON"}
                refused = subprocess.run([str(shim), "-c", "print(1)"], capture_output=True,
                                         text=True, timeout=30, env=unset)
                self.assertNotEqual(refused.returncode, 0)


class BoardLocksDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = sp.build(Path(tmp.name) / "lumen", "board_locks")

    def test_the_real_lock_command_takes_a_lock_on_the_local_origin(self):
        remote = _git(self.root, "remote", "get-url", "origin").strip()
        self.assertTrue(Path(remote).resolve().is_relative_to(self.root.resolve()))
        env = _framework_env(self.root)
        for argv in (["./ait", "lock", "--init"],
                     ["./ait", "lock", "14", "--email", sp.PERSON_EMAIL]):
            done = subprocess.run(argv, cwd=self.root, env=env, capture_output=True, text=True,
                                  timeout=120)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        listed = _git(self.root, "ls-tree", "--name-only", "origin/aitask-locks")
        self.assertIn("t14_lock.yaml", listed)

    def test_without_the_origin_the_lock_would_be_a_silent_no_op(self):
        """The control for the dataset's reason to exist."""
        with tempfile.TemporaryDirectory(prefix="ait_shots_test_") as tmp:
            root = sp.build(Path(tmp) / "lumen", "base")
            done = subprocess.run(["./ait", "lock", "14", "--email", sp.PERSON_EMAIL], cwd=root,
                                  env=_framework_env(root), capture_output=True, text=True,
                                  timeout=120)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(_git(root, "branch", "-a", "--list", "*aitask-locks*").strip(), "")


class TrailsDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = sp.build(Path(tmp.name) / "lumen", "trails")

    def test_the_owner_task_carries_the_trail_artifact(self):
        owner = (self.root / "aitasks" / "t12_add_checkout_page.md").read_text()
        self.assertIn(sp.TRAIL_HANDLE, owner)
        self.assertIn("implementation_trail", owner)
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")

    def test_the_stored_trail_is_what_the_framework_reads_back(self):
        out = self.root / ".standin" / "read_back.json"
        done = subprocess.run(["./ait", "artifact", "get", sp.TRAIL_HANDLE, "--out", str(out)],
                              cwd=self.root, env=_framework_env(self.root), capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        doc = json.loads(out.read_text())
        self.assertEqual(doc["title"], sp.TRAIL_NAME)
        self.assertEqual([w["title"] for w in doc["waves"]],
                         ["Unblock sign-in", "Build the checkout", "Polish after launch"])
        # Members name the sample project, so the TUI draws local task cards.
        refs = {e["task"] for w in doc["waves"] for e in w["entries"]}
        self.assertEqual(refs, {f"lumen#{t}" for t in ("14", "12_1", "12_2", "12_3", "15", "9")})
        for ref in refs:
            task_id = ref.split("#")[1]
            self.assertTrue(list((self.root / "aitasks").rglob(f"t{task_id}_*.md")), ref)

    def test_the_trail_is_current_by_the_frameworks_own_drift_check(self):
        """The digest is the gatherer's, over the real task files: an invented
        one reads as stale on screen."""
        done = subprocess.run(["./.aitask-scripts/aitask_trail_gather.sh", "drift", "--trail",
                               sp.TRAIL_HANDLE], cwd=self.root, env=_framework_env(self.root),
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("STALE", done.stdout)
        self.assertNotIn("DRIFT:", done.stdout)
        self.assertIn("CURRENT", done.stdout.upper())

    def test_no_build_day_in_the_trail(self):
        doc = (self.root / ".standin" / "trail_checkout_launch.json").read_text()
        self.assertEqual(set(re.findall(r"20\d\d-\d\d-\d\dT[0-9:]+Z", doc)), {sp.TRAIL_STAMP})


class HostCacheIsolationTests(unittest.TestCase):
    """Framework commands a dataset runs cache under XDG_CACHE_HOME (the
    artifact cache links into the project). Nothing may land in the cache the
    caller's environment names: it would dangle once the project is removed."""

    def test_building_a_dataset_leaves_the_callers_cache_untouched(self):
        for name in ("trails", "brainstorm"):
            with self.subTest(name), tempfile.TemporaryDirectory(prefix="ait_shots_test_") as tmp:
                outer = Path(tmp) / "outer_cache"
                outer.mkdir()
                with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(outer)}):
                    root = sp.build(Path(tmp) / "lumen", name)
                self.assertEqual(list(outer.rglob("*")), [])
                if name == "trails":
                    # Positive control: the cache WAS written, inside the tree.
                    inner = root / ".standin" / "home" / ".cache"
                    self.assertTrue(any(inner.rglob("sha256:*")), list(inner.rglob("*")))


class BrainstormDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = sp.build(Path(tmp.name) / "lumen", "brainstorm")
        cls.session = cls.root / ".aitask-crews" / f"crew-brainstorm-{sp.BRAINSTORM_TASK}"

    def test_the_session_holds_the_root_and_three_applied_nodes(self):
        import yaml
        nodes = {p.stem: yaml.safe_load(p.read_text())
                 for p in (self.session / "br_nodes").glob("*.yaml")}
        self.assertEqual(sorted(nodes), ["n000_init", "n001_numbered_pages", "n002_load_more",
                                         "n003_hybrid"])
        self.assertEqual(nodes["n001_numbered_pages"]["parents"], ["n000_init"])
        self.assertEqual(nodes["n003_hybrid"]["parents"],
                         ["n001_numbered_pages", "n002_load_more"])
        for node_id in nodes:
            self.assertTrue((self.session / "br_proposals" / f"{node_id}.md").is_file())
        state = yaml.safe_load((self.session / "br_graph_state.yaml").read_text())
        self.assertEqual(state["current_head"], "n003_hybrid")

    def test_the_apply_step_completed_each_operation_record(self):
        import yaml
        groups = yaml.safe_load((self.session / "br_groups.yaml").read_text())["groups"]
        self.assertEqual(groups["explore_001"]["status"], "Completed")
        self.assertEqual(groups["explore_001"]["nodes_created"],
                         ["n001_numbered_pages", "n002_load_more"])
        self.assertEqual(groups["synthesize_002"]["status"], "Completed")
        self.assertEqual(groups["synthesize_002"]["nodes_created"], ["n003_hybrid"])

    def test_the_framework_lists_the_session(self):
        done = subprocess.run(["./ait", "brainstorm", "status", sp.BRAINSTORM_TASK],
                              cwd=self.root, env=_framework_env(self.root), capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("n003_hybrid", done.stdout)

    def test_no_build_day_in_the_session(self):
        today = time.strftime("%Y-%m-%d")
        for path in self.session.rglob("*"):
            if path.is_file() and path.suffix in (".yaml", ".md") \
                    and not path.name.startswith("_crew") and ".git" not in path.parts:
                self.assertNotIn(today, path.read_text(), path.name)

    def test_no_agent_was_started(self):
        log = self.root / ".standin" / "log"
        self.assertFalse(log.exists(), log.read_text() if log.exists() else "")

    def test_the_project_stays_a_clean_repository(self):
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")


class SettingsDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = sp.build(Path(tmp.name) / "lumen", "settings")

    def test_every_seed_agent_has_its_model_list(self):
        meta = self.root / "aitasks" / "metadata"
        for name in ("models_claudecode.json", *sp.SETTINGS_SEED_FILES):
            with self.subTest(name):
                self.assertTrue(json.loads((meta / name).read_text())["models"])

    def test_the_agent_defaults_are_the_seeds(self):
        """The Agent Defaults tab shows the seed's per-operation models, not
        the stand-in routing of ``agents`` (settings launches no agent)."""
        config = json.loads((self.root / "aitasks" / "metadata" / "codeagent_config.json")
                            .read_text())
        seed = json.loads((sp.REPO_ROOT / "seed" / "codeagent_config.json").read_text())
        self.assertEqual(config["defaults"], seed["defaults"])
        self.assertGreater(len(set(config["defaults"].values())), 1)

    def test_the_project_stays_a_clean_repository(self):
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")


class CodebrowserDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = sp.build(Path(tmp.name) / "lumen", "codebrowser")

    def test_each_task_has_a_tagged_code_commit_and_an_archive_commit(self):
        subjects = _git(self.root, "log", "--format=%s").splitlines()
        for task, subject, _files in sp.CODEBROWSER_HISTORY:
            with self.subTest(task.task_id):
                self.assertIn(subject, subjects)
                self.assertTrue(subject.endswith(f"(t{task.task_id})"))
                self.assertIn(f"ait: Archive completed t{task.task_id} task and plan files",
                              subjects)
        self.assertIn("ait: Archive completed t5 task and plan files", subjects)

    def test_one_file_carries_lines_from_four_tasks(self):
        """What the annotation gutter shows: blame of cart.py maps to the
        (tN) subjects of four different tasks."""
        blame = _git(self.root, "blame", "--line-porcelain", "src/checkout/cart.py")
        ids = set(re.findall(r"^summary .*\((t\d+(?:_\d+)?)\)$", blame, re.M))
        self.assertEqual(ids, {"t3", "t4", "t5_2", "t6"})

    def test_every_archived_task_and_plan_exists(self):
        for task in [t for t, _s, _f in sp.CODEBROWSER_HISTORY] + [sp.CODEBROWSER_PARENT]:
            with self.subTest(task.task_id):
                text = task.task_path(self.root).read_text()
                self.assertIn("status: Done", text)
                self.assertIn(f"completed_at: {task.completed}", text)
                self.assertIn("## Final Implementation Notes", task.plan_path(self.root).read_text())

    def test_dates_are_fixed(self):
        """Commit dates and archived file times are the fixed sample dates."""
        dates = {d[:7] for d in _git(self.root, "log", "--format=%aI").split()}
        self.assertEqual(dates, {"2026-01", "2026-02"})
        mtimes = {time.strftime("%Y-%m", time.gmtime(p.stat().st_mtime))
                  for p in (self.root / "aitasks" / "archived").rglob("*.md")}
        self.assertEqual(mtimes, {"2026-01", "2026-02"})

    def test_only_invented_names(self):
        text = "\n".join(p.read_text() for p in (self.root / "src").rglob("*.py"))
        self.assertNotIn("aitasks", text)
        self.assertIn("lumen", (self.root / "README.md").read_text())

    def test_the_project_stays_a_clean_repository(self):
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")


class StatsDatasetTests(unittest.TestCase):
    """Dates relative to the build day: the one documented exception."""

    @classmethod
    def setUpClass(cls):
        from datetime import date
        cls.today = date(2026, 6, 10)       # a Wednesday
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        with mock.patch.object(sp, "_today", return_value=cls.today):
            cls.root = sp.build(Path(tmp.name) / "lumen", "stats")
        cls.archived = sorted((cls.root / "aitasks" / "archived").glob("t*.md"))

    def _completed(self):
        from datetime import date
        out = []
        for path in self.archived:
            stamp = re.search(r"^completed_at: (\S+)", path.read_text(), re.M).group(1)
            out.append(date.fromisoformat(stamp))
        return out

    def test_completions_fall_in_the_window_before_the_build_day(self):
        from datetime import timedelta
        days = self._completed()
        self.assertGreaterEqual(len(days), 50)
        self.assertTrue(all(self.today - timedelta(days=sp.STATS_DAYS) <= d < self.today
                            for d in days))
        # The last 30 days hold most of them: the daily chart is populated.
        recent = [d for d in days if d >= self.today - timedelta(days=30)]
        self.assertGreaterEqual(len(recent), 30)

    def test_weekends_are_quiet_and_midweek_busy(self):
        weekdays = [d.weekday() for d in self._completed()]
        self.assertEqual([w for w in weekdays if w >= 5], [])
        self.assertGreater(weekdays.count(2), weekdays.count(4))

    def test_the_build_is_deterministic_for_one_day(self):
        self.assertEqual([t.completed for t in sp._stats_tasks(self.today)],
                         [t.completed for t in sp._stats_tasks(self.today)])

    def test_only_completed_at_moves_with_the_build_day(self):
        """Another build day shifts the dates and nothing else."""
        from datetime import timedelta
        a = sp._stats_tasks(self.today)
        b = sp._stats_tasks(self.today + timedelta(days=7))
        self.assertEqual([(t.task_id, t.slug, t.issue_type) for t in a],
                         [(t.task_id, t.slug, t.issue_type) for t in b])

    def test_the_project_stays_a_clean_repository(self):
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")


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
