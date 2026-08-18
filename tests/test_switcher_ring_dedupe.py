#!/usr/bin/env python3
"""TUI-switcher ring invariants over discovery output (t1544_1).

>>> CHARACTERIZATION OF A DEFECT — NOT A DESIRED INVARIANT. <<<
This file currently pins the switcher ring's **broken** behaviour so the fix in
t1544_1 is provable rather than asserted. It is rewritten to the post-fix
invariants in the same task. If you are reading this comment after t1544_1
landed, the rewrite was skipped — that is a bug.

Why the ring is fed *assembler output* rather than hand-built sessions:
`cross_group_ring` / `cross_group_step` are pure helpers and t1544_1 does not
change them. Feeding them a hand-built duplicate list would livelock before and
after the fix alike, proving nothing. The invariant t1544_1 actually
establishes is one level up — *discovery never hands the ring two records for
one repo* — so the ring must be driven from `_assemble_aitasks_sessions`.

The defect: `cross_group_step` locates the current entry by the FIRST `.key`
match. Two entries sharing a key therefore trap the walk — stepping off the
first lands on the second, whose key re-resolves to the first's index, so the
cursor oscillates inside the pair and every other repo becomes unreachable.

Run: python3 tests/test_switcher_ring_dedupe.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib")
)

from agent_launch_utils import (  # noqa: E402
    _assemble_aitasks_sessions,
    cross_group_ring,
    cross_group_step,
)

PASS = 0
FAIL = 0
TOTAL = 0


def assert_eq(desc: str, expected, actual) -> None:
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if expected == actual:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {desc} (expected {expected!r}, got {actual!r})")


def assert_true(desc: str, actual) -> None:
    assert_eq(desc, True, bool(actual))


def _make_fake_project(root: Path, *, default_session: str | None = None) -> Path:
    (root / "aitasks" / "metadata").mkdir(parents=True)
    cfg = root / "aitasks" / "metadata" / "project_config.yaml"
    if default_session is not None:
        cfg.write_text(f"tmux:\n  default_session: {default_session}\n")
    else:
        cfg.write_text("project:\n  name: fake\n")
    return root


class _Fixture:
    """tmpdir + an always-set AITASKS_PROJECTS_INDEX, restored on exit."""

    def __enter__(self) -> "_Fixture":
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self._saved = os.environ.get("AITASKS_PROJECTS_INDEX")
        idx = self.tmp / "projects.yaml"
        idx.write_text("projects:\n")
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        return self

    def __exit__(self, *exc) -> bool:
        if self._saved is None:
            os.environ.pop("AITASKS_PROJECTS_INDEX", None)
        else:
            os.environ["AITASKS_PROJECTS_INDEX"] = self._saved
        self._td.cleanup()
        return False


def _walk(ring, start_key: str, steps: int) -> list[str]:
    """Session names visited by `steps` successive right-steps from start_key."""
    seen = []
    key = start_key
    for _ in range(steps):
        entry = cross_group_step(ring, key, 1)
        seen.append(entry.session)
        key = entry.key
    return seen


def _two_live_one_repo_plus_another(fx: "_Fixture"):
    """Duplicate source 1: two live tmux sessions rooted at one repo."""
    repo_one = _make_fake_project(fx.tmp / "repo_one")
    repo_two = _make_fake_project(fx.tmp / "repo_two")
    sessions = _assemble_aitasks_sessions(
        [("sess_a", repo_one), ("sess_b", repo_one), ("sess_c", repo_two)],
        include_registered=True,
    )
    return sessions, repo_one, repo_two


def _check_duplicate_pair_reaches_the_ring() -> None:
    """CURRENT: discovery hands the ring two entries for one repo."""
    with _Fixture() as fx:
        sessions, repo_one, _ = _two_live_one_repo_plus_another(fx)
        ring = cross_group_ring(sessions)
        assert_eq("ring has one entry per discovered record", 3, len(ring))
        keys = [e.key for e in ring]
        assert_eq("only two distinct repos exist", 2, len(set(keys)))
        assert_true(
            "two ring entries share a key (the defect)",
            len(keys) != len(set(keys)),
        )


def _check_ring_walk_is_trapped_by_the_duplicate() -> None:
    """CURRENT: the second repo is unreachable by right-cycling."""
    with _Fixture() as fx:
        sessions, repo_one, repo_two = _two_live_one_repo_plus_another(fx)
        ring = cross_group_ring(sessions)
        start = os.path.realpath(repo_one)
        visited = _walk(ring, start, 6)
        assert_eq(
            "six right-steps oscillate inside the duplicate pair",
            ["sess_b"] * 6, visited,
        )
        assert_true(
            "the other repo is NEVER reached (the defect)",
            "sess_c" not in visited,
        )


def _check_no_duplicates_walks_every_repo() -> None:
    """Control: without a duplicate the walk already reaches every repo.

    Pins that the livelock is caused by the duplicate specifically, not by the
    ring helpers being broken in general — so the fix belongs upstream in
    discovery, which is where t1544_1 puts it.
    """
    with _Fixture() as fx:
        repo_one = _make_fake_project(fx.tmp / "repo_one")
        repo_two = _make_fake_project(fx.tmp / "repo_two")
        sessions = _assemble_aitasks_sessions(
            [("sess_a", repo_one), ("sess_c", repo_two)],
            include_registered=True,
        )
        ring = cross_group_ring(sessions)
        assert_eq("ring has two entries", 2, len(ring))
        visited = _walk(ring, os.path.realpath(repo_one), 4)
        assert_eq(
            "walk alternates between the two repos",
            ["sess_c", "sess_a", "sess_c", "sess_a"], visited,
        )


def main() -> int:
    _check_duplicate_pair_reaches_the_ring()
    _check_ring_walk_is_trapped_by_the_duplicate()
    _check_no_duplicates_walks_every_repo()
    print(f"\n{PASS}/{TOTAL} passed" + (f", {FAIL} FAILED" if FAIL else ""))
    return 1 if FAIL else 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211)."""

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
