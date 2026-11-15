"""Characterization golden for every model-stats reader (t1912_2).

`tests/lib/stats_reader_capture.py` prints what each reader of
`usagestats` / `verifiedstats` displays: the stats_data rankings, the model
picker, the settings TUI labels and Models tab, and `ait codeagent list-models`.
It runs over the fixture in `tests/golden/stats_readers/`, with "today" pinned.

The golden was captured on the tree **before** t1912_2 routed the readers
through the aitask-stats store overlay. With an empty stats branch, the overlay
must reproduce it byte for byte.

The fixture is writer-consistent: every `verified` prior equals its recorded
`verifiedstats` average, as on the live registry. So this file proves parity
for that shape only. The deliberate `list-models` VERIFIED change for missing
or inconsistent priors is pinned by tests/test_codeagent.sh (Tests 4b / 4c).

Regenerate (only for an intended display change):
  cd <scratch project with the fixture in aitasks/metadata, git-initialised>
  python3 tests/lib/stats_reader_capture.py "$PWD" --write tests/golden/stats_readers/expected.txt

Run: python3 -m pytest tests/test_stats_readers_golden.py -v
"""
from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "golden" / "stats_readers"
EXPECTED = FIXTURE / "expected.txt"
CAPTURE = REPO_ROOT / "tests" / "lib" / "stats_reader_capture.py"
AGENTS = ("claudecode", "codex", "opencode")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _clean_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("TASK_DIR", "METADATA_DIR", "GIT_DIR", "GIT_WORK_TREE")}
    env.update(GIT_ENV)
    if extra:
        env.update(extra)
    return env


def git(root, *args, env=None) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, env=env or _clean_env(), check=True)
    return proc.stdout.strip()


def make_project(base: Path, name: str = "proj") -> Path:
    """A git-initialised project holding the fixture under aitasks/metadata."""
    root = base / name
    meta = root / "aitasks" / "metadata"
    meta.mkdir(parents=True)
    for agent in AGENTS:
        shutil.copy(FIXTURE / f"models_{agent}.json", meta / f"models_{agent}.json")
    git(root, "init", "-q", "-b", "main")
    return root


def run_capture(root: Path, env: dict | None = None) -> str:
    proc = subprocess.run([sys.executable, str(CAPTURE), str(root)], cwd=root,
                          capture_output=True, text=True, env=env or _clean_env())
    if proc.returncode != 0:
        raise AssertionError(f"capture failed ({proc.returncode}):\n{proc.stderr}")
    return proc.stdout


def diff(expected: str, actual: str) -> str:
    return "".join(difflib.unified_diff(
        expected.splitlines(keepends=True), actual.splitlines(keepends=True),
        "expected.txt", "capture"))


class GoldenParityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_branch_reproduces_golden(self):
        root = make_project(self.base)
        actual = run_capture(root)
        expected = EXPECTED.read_text(encoding="utf-8")
        self.assertEqual(expected, actual, "reader output drifted:\n" + diff(expected, actual))


# ------------------------------------------------------------ branch-backed

STATS_CLI = REPO_ROOT / ".aitask-scripts" / "aitask_model_stats.py"
DAY = "2026-11-04"   # the capture's pinned today: month 2026-11, week 2026-W45


def stats_cli(root: Path, *args, env=None) -> str:
    proc = subprocess.run([sys.executable, str(STATS_CLI), *args, "--root", str(root)],
                          capture_output=True, text=True, env=env or _clean_env())
    if proc.returncode != 0:
        raise AssertionError(f"stats CLI {args} failed: {proc.stdout}{proc.stderr}")
    return proc.stdout.strip()


def seed(root: Path, env=None) -> None:
    """Branch counters for claudecode/bucketed: 2 verified runs at 40, 1 usage run.

    File side (fixture): pick all_time 4 runs / 380 (avg 95), month 2026-11
    1 run, prev_month 2026-10 2 runs; usage pick all_time 10.
    Effective (no marker): 6 runs / 460 -> avg 77 (76.67 rounds up), month
    1+2 = 3 runs, prev_month 2; usage all_time 11.
    Branch only (marker): 2 runs / 80 -> avg 40, month 2 runs.
    """
    for _ in range(2):
        stats_cli(root, "record-verified", "--agent", "claudecode", "--model", "bucketed",
                  "--skill", "pick", "--score", "2", "--date", DAY, env=env)
    stats_cli(root, "bump-usage", "--agent", "claudecode", "--model", "bucketed",
              "--skill", "pick", "--date", DAY, env=env)


def mark_migrated(root: Path, agent: str = "claudecode") -> None:
    """Commit migrations/<agent>.json onto the local aitask-stats ref."""
    env = _clean_env()
    tip = git(root, "rev-parse", "refs/heads/aitask-stats", env=env)
    blob = subprocess.run(["git", "-C", str(root), "hash-object", "-w", "--stdin"],
                          input="{}\n", capture_output=True, text=True, env=env,
                          check=True).stdout.strip()
    tree = git(root, "rev-parse", f"{tip}^{{tree}}", env=env)
    idx = root / ".git" / "mark.index"
    ienv = {**env, "GIT_INDEX_FILE": str(idx)}
    git(root, "read-tree", tree, env=ienv)
    git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},migrations/{agent}.json",
        env=ienv)
    new_tree = git(root, "write-tree", env=ienv)
    idx.unlink()
    commit = git(root, "commit-tree", new_tree, "-p", tip, "-m", "marker", env=env)
    git(root, "update-ref", "refs/heads/aitask-stats", commit, tip, env=env)


def lines_of(text: str, prefix: str) -> list:
    return [line for line in text.splitlines() if line.startswith(prefix)]


def section(text: str, title: str) -> str:
    """The body of one `== <title>` section of a capture."""
    out, on = [], False
    for line in text.splitlines():
        if line.startswith("== "):
            on = line == f"== {title}"
            continue
        if on:
            out.append(line)
    return "\n".join(out)


class BranchBackedReaderTests(unittest.TestCase):
    """Every reader family shows file + branch, or branch only after migration."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.root = make_project(self.base)
        seed(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_marker_sums_file_and_branch_in_every_reader(self):
        out = run_capture(self.root)
        # 1. stats_data rankings
        self.assertIn("pick|claudecode|all_time|claude-bucketed-1|Claude Bucketed 1|score=77|runs=6",
                      out)
        self.assertIn("pick|claudecode|month|claude-bucketed-1|Claude Bucketed 1|score=60|runs=3",
                      out)   # (100 + 80) / 3
        self.assertIn("pick|claudecode|all_time|claude-bucketed-1|Claude Bucketed 1|runs=11", out)
        # 2. picker
        self.assertIn('"description": "bucketed stats  [77 (6 runs, 3 this mo, 2 prev mo)]"',
                      section(out, "picker[pick]._build_options_for_agent(claudecode)"))
        self.assertIn('"name": "bucketed", "runs": 8}',
                      section(out, "picker[pick]._build_top_usage"))   # recent 7 + 1
        # 3. settings
        self.assertIn("pick|claudecode/bucketed|verified=' [dim][77 (6 runs, 3 this mo, 2 prev mo)][/dim]'",
                      out)
        self.assertIn("pick: 77 (6 runs, 3 this month, 2 last month)",
                      section(out, "settings._populate_models_tab"))
        # 4. list-models: the headline follows the effective score, not the prior 95
        lm = section(out, "list-models claudecode")
        self.assertIn("NOTES:bucketed stats VERIFIED:pick=77,explore=90", lm)
        self.assertIn("STATS:pick(runs 6, avg 77),explore(runs 2, avg 90)", lm)
        # Untouched rows and agents stay as in the golden.
        golden = EXPECTED.read_text(encoding="utf-8")
        self.assertEqual(section(out, "list-models codex"), section(golden, "list-models codex"))
        self.assertIn("NOTES:pre-bucket format VERIFIED:pick=75\nSTATS:pick(runs 2, avg 75)", lm)

    def test_marker_means_branch_only_in_every_reader(self):
        mark_migrated(self.root)
        out = run_capture(self.root)
        verified = section(out, "stats_data.load_verified_rankings")
        self.assertEqual(lines_of(verified, "pick|claudecode|all_time|"),
                         ["pick|claudecode|all_time|claude-bucketed-1|Claude Bucketed 1|score=40|runs=2"])
        self.assertEqual(lines_of(verified, "wrap|claudecode|"), [])   # no branch data
        self.assertIn("pick|codex|all_time|gpt-5.3-codex|GPT5.3-Codex|score=80|runs=3",
                      verified)                                        # codex not migrated
        self.assertIn('"description": "bucketed stats  [40 (2 runs, 2 this mo)]"',
                      section(out, "picker[pick]._build_options_for_agent(claudecode)"))
        self.assertIn('"description": "pre-bucket format  [score: 75]"',
                      section(out, "picker[pick]._build_options_for_agent(claudecode)"))
        self.assertIn("pick|claudecode/bucketed|verified=' [dim][40 (2 runs, 2 this mo)][/dim]'",
                      out)
        lm = section(out, "list-models claudecode")
        self.assertIn("NOTES:bucketed stats VERIFIED:pick=40,explore=90\nSTATS:pick(runs 2, avg 40)",
                      lm)
        # The flat row has no branch counters: the prior is all that is left.
        self.assertIn("NOTES:pre-bucket format VERIFIED:pick=75\nMODEL:unsorted", lm)


class HostileTaskDirTests(unittest.TestCase):
    """The branch read is the registry's repository, never the cwd's."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.cwd_repo = make_project(self.base, "cwd_repo")
        seed(self.cwd_repo)                                 # +2 verified, +1 usage
        self.other = make_project(self.base, "other")
        stats_cli(self.other, "record-verified", "--agent", "claudecode", "--model",
                  "bucketed", "--skill", "pick", "--score", "5", "--date", DAY)

    def tearDown(self):
        self._tmp.cleanup()

    def _probe(self, code: str, env_extra: dict) -> str:
        proc = subprocess.run([sys.executable, "-c", code], cwd=self.cwd_repo,
                              capture_output=True, text=True, env=_clean_env(env_extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    PRELUDE = ("import sys; sys.path.insert(0, %r); "
               % str(REPO_ROOT / ".aitask-scripts" / "lib"))

    def test_load_all_models_with_root_ignores_cwd_branch(self):
        decoy = self.base / "decoy"
        (decoy / "metadata").mkdir(parents=True)
        out = self._probe(
            self.PRELUDE + "from config_utils import load_all_models; "
            f"m = load_all_models({str(self.other)!r})['claudecode']['models'][0]; "
            "print(m['verifiedstats']['pick']['all_time']['runs'])",
            {"TASK_DIR": str(decoy)})
        self.assertEqual(out, "5")      # other's file 4 + other's branch 1, not the cwd's 2

    def test_stats_data_absolute_task_dir_reads_that_repos_branch(self):
        out = self._probe(
            self.PRELUDE + "from datetime import date; from stats_data import load_verified_rankings; "
            "w = load_verified_rankings(today=date(2026, 11, 4)).by_window['pick']['claudecode']['all_time']; "
            "print([e.runs for e in w if e.cli_id == 'claude-bucketed-1'][0])",
            {"TASK_DIR": str(self.other / "aitasks")})
        self.assertEqual(out, "5")


# -------------------------------------------- post-phase: readers_never_fetch

class ReadersNeverFetchTests(unittest.TestCase):
    """No reader path reaches the network, even with a newer origin tip."""

    NETWORK = {"fetch", "ls-remote", "push", "pull", "remote", "clone"}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.origin = self.base / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.origin)], check=True,
                       env=_clean_env())
        self.root = make_project(self.base)
        git(self.root, "remote", "add", "origin", str(self.origin))
        seed(self.root)                                     # local == origin: +2 runs
        writer = make_project(self.base, "writer")
        git(writer, "remote", "add", "origin", str(self.origin))
        stats_cli(writer, "record-verified", "--agent", "claudecode", "--model",
                  "bucketed", "--skill", "pick", "--score", "5", "--date", DAY)
        local = git(self.root, "rev-parse", "refs/heads/aitask-stats")
        remote = git(self.origin, "rev-parse", "refs/heads/aitask-stats")
        self.assertNotEqual(local, remote, "origin must be strictly newer")

    def tearDown(self):
        self._tmp.cleanup()

    def _wrapper(self) -> tuple:
        bindir = self.base / "bin"
        bindir.mkdir()
        log = self.base / "git.log"
        real = shutil.which("git")
        wrapper = bindir / "git"
        wrapper.write_text("#!/bin/sh\n"
                           f"printf '%s\\n' \"$*\" >> '{log}'\n"
                           f"exec '{real}' \"$@\"\n")
        wrapper.chmod(0o755)
        return bindir, log

    @staticmethod
    def _subcommand(argv: str) -> str:
        words = argv.split()
        i = 0
        while i < len(words):
            w = words[i]
            if w in ("-C", "-c", "--git-dir", "--work-tree"):
                i += 2
                continue
            if w.startswith("-"):
                i += 1
                continue
            return w
        return ""

    def test_full_capture_reads_only_the_local_ref(self):
        bindir, log = self._wrapper()
        env = _clean_env({"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"})
        out = run_capture(self.root, env=env)
        calls = log.read_text().splitlines() if log.exists() else []
        self.assertTrue(calls, "the git wrapper saw no calls: the probe is not wired")
        network = [c for c in calls if self._subcommand(c) in self.NETWORK]
        self.assertEqual(network, [], f"a reader reached the network: {network}")
        # Local values (file 4 + local 2 = 6), never origin's newer 7.
        self.assertIn("pick|claudecode|all_time|claude-bucketed-1|Claude Bucketed 1|score=77|runs=6",
                      out)
        self.assertIn("VERIFIED:pick=77,explore=90", section(out, "list-models claudecode"))


if __name__ == "__main__":
    unittest.main()
