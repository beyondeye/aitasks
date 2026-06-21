"""Unit tests for the crew-aggregate roll-up helpers (t1041).

Covers the derive-on-read fix for a stale `_crew_status.yaml`:
`compute_crew_progress`, the all-terminal rule in `compute_crew_status`,
`runner_is_live`, `effective_crew_rollup`, and `list_crews` reflecting the
derived value.
"""

from __future__ import annotations

import os
import sys
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from agentcrew.agentcrew_utils import (  # noqa: E402
    compute_crew_progress,
    compute_crew_status,
    effective_crew_rollup,
    list_crews,
    runner_is_live,
    write_yaml,
)


def _ts(offset_seconds: float = 0.0) -> str:
    t = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return t.strftime("%Y-%m-%d %H:%M:%S")


def _member(crew_dir: str, name: str, status: str, progress: int = 0) -> None:
    write_yaml(
        os.path.join(crew_dir, f"{name}_status.yaml"),
        {"agent_name": name, "status": status, "progress": progress},
    )


def _crew_status(crew_dir: str, status: str, progress: int) -> None:
    write_yaml(
        os.path.join(crew_dir, "_crew_status.yaml"),
        {"status": status, "progress": progress},
    )


def _runner_alive(crew_dir: str, status: str, hb_offset_seconds: float) -> None:
    write_yaml(
        os.path.join(crew_dir, "_runner_alive.yaml"),
        {"status": status, "last_heartbeat": _ts(hb_offset_seconds)},
    )


class TestComputeCrewProgress(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(compute_crew_progress([]), 0)

    def test_all_completed(self):
        self.assertEqual(compute_crew_progress(["Completed", "Completed"]), 100)

    def test_partial(self):
        self.assertEqual(
            compute_crew_progress(["Completed", "Running", "Waiting", "Completed"]), 50
        )


class TestComputeCrewStatusTerminal(unittest.TestCase):
    def test_all_completed(self):
        self.assertEqual(compute_crew_status(["Completed", "Completed"]), "Completed")

    def test_all_aborted_is_aborted(self):
        # Previously fell through to "Running"; now a real terminal crew state.
        self.assertEqual(compute_crew_status(["Aborted"]), "Aborted")
        self.assertEqual(compute_crew_status(["Aborted", "Aborted"]), "Aborted")

    def test_completed_plus_aborted_is_completed(self):
        self.assertEqual(compute_crew_status(["Completed", "Aborted"]), "Completed")

    def test_error_still_wins(self):
        self.assertEqual(compute_crew_status(["Aborted", "Error"]), "Error")

    def test_running_still_running(self):
        self.assertEqual(compute_crew_status(["Completed", "Running"]), "Running")


class TestEffectiveCrewRollup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rollup_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_stale_terminal_derives_completed(self):
        # Persisted aggregate lags: file says Running/80, member is Completed/100.
        _crew_status(self.tmp, "Running", 80)
        _member(self.tmp, "comparator", "Completed", 100)
        self.assertEqual(effective_crew_rollup(self.tmp, "Running", 80), ("Completed", 100))

    def test_killing_preserved_while_runner_live(self):
        _member(self.tmp, "worker", "Running", 50)
        _runner_alive(self.tmp, "running", hb_offset_seconds=-5)
        self.assertEqual(effective_crew_rollup(self.tmp, "Killing", 40), ("Killing", 40))

    def test_killing_derived_when_runner_stopped(self):
        # Runner gone + members settled -> Killing must not stick permanently.
        _member(self.tmp, "worker", "Aborted", 0)
        _runner_alive(self.tmp, "stopped", hb_offset_seconds=-5)
        self.assertEqual(effective_crew_rollup(self.tmp, "Killing", 40), ("Aborted", 0))

    def test_killing_derived_when_heartbeat_stale(self):
        _member(self.tmp, "worker", "Completed", 100)
        _runner_alive(self.tmp, "running", hb_offset_seconds=-10_000)  # very old
        self.assertEqual(effective_crew_rollup(self.tmp, "Killing", 40), ("Completed", 100))

    def test_no_members_preserves_persisted(self):
        _crew_status(self.tmp, "Initializing", 0)
        self.assertEqual(effective_crew_rollup(self.tmp, "Initializing", 0), ("Initializing", 0))


class TestRunnerIsLive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="runner_live_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_no_file(self):
        self.assertFalse(runner_is_live(self.tmp))

    def test_running_fresh(self):
        _runner_alive(self.tmp, "running", hb_offset_seconds=-1)
        self.assertTrue(runner_is_live(self.tmp))

    def test_running_stale(self):
        _runner_alive(self.tmp, "running", hb_offset_seconds=-10_000)
        self.assertFalse(runner_is_live(self.tmp))

    def test_stopped(self):
        _runner_alive(self.tmp, "stopped", hb_offset_seconds=-1)
        self.assertFalse(runner_is_live(self.tmp))


class TestListCrewsDerives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="list_crews_test_")
        self.prev_cwd = os.getcwd()
        os.chdir(self.tmp)
        crew_dir = os.path.join(self.tmp, ".aitask-crews", "crew-stale")
        os.makedirs(crew_dir)
        write_yaml(os.path.join(crew_dir, "_crew_meta.yaml"), {"name": "stale"})
        _crew_status(crew_dir, "Running", 80)
        _member(crew_dir, "comparator", "Completed", 100)

    def tearDown(self):
        os.chdir(self.prev_cwd)
        shutil.rmtree(self.tmp)

    def test_list_crews_reflects_derived_value(self):
        crews = list_crews()
        self.assertEqual(len(crews), 1)
        self.assertEqual(crews[0]["id"], "stale")
        self.assertEqual(crews[0]["status"], "Completed")
        self.assertEqual(crews[0]["progress"], 100)


if __name__ == "__main__":
    unittest.main()
