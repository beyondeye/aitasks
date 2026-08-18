#!/usr/bin/env python3
"""TUI-switcher ring invariants over discovery output (t1544_1).

The invariant this file pins is **one ring entry per repository**, and the
traversal property that follows from it: right-cycling reaches every repo.

Why the ring is fed *assembler output* rather than hand-built sessions:
`cross_group_ring` / `cross_group_step` are pure helpers and t1544_1 does not
change them — they remain duplicate-fragile by construction. What t1544_1
establishes is one level up: *discovery never hands the ring two records for
one repo*. Driving the ring from hand-built lists would therefore prove
nothing about the fix; it must be driven from `_assemble_aitasks_sessions`.

The defect this replaced (kept here as the rationale for the assertions
below): `cross_group_step` locates the current entry by the FIRST `.key`
match, so two entries sharing a key trapped the walk — stepping off the first
landed on the second, whose key re-resolved to the first's index, so the
cursor oscillated inside the pair and every other repo became unreachable.
Before the fix, six right-steps from a duplicated repo returned the same
session six times and the second repo was never reached.

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
        self.set_registry([])
        return self

    def set_registry(self, entries: list[tuple[str, Path]]) -> Path:
        idx = self.tmp / "projects.yaml"
        lines = ["projects:\n"]
        for name, root in entries:
            lines.append(f"  - name: {name}\n")
            lines.append(f"    path: {root}\n")
        idx.write_text("".join(lines))
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        return idx

    def __exit__(self, *exc) -> bool:
        if self._saved is None:
            os.environ.pop("AITASKS_PROJECTS_INDEX", None)
        else:
            os.environ["AITASKS_PROJECTS_INDEX"] = self._saved
        self._td.cleanup()
        return False


def _walk_keys(ring, start_key: str, steps: int) -> list[str]:
    """Repo keys visited by `steps` successive right-steps from start_key."""
    seen = []
    key = start_key
    for _ in range(steps):
        entry = cross_group_step(ring, key, 1)
        seen.append(entry.key)
        key = entry.key
    return seen


def _check_duplicate_live_sessions_yield_one_ring_entry() -> None:
    """Duplicate source 1 must not reach the ring."""
    with _Fixture() as fx:
        repo_one = _make_fake_project(fx.tmp / "repo_one")
        repo_two = _make_fake_project(fx.tmp / "repo_two")
        sessions = _assemble_aitasks_sessions(
            [("sess_a", repo_one), ("sess_b", repo_one), ("sess_c", repo_two)],
            include_registered=True,
        )
        ring = cross_group_ring(sessions)
        assert_eq("one ring entry per repo, not per record", 2, len(ring))
        keys = [e.key for e in ring]
        assert_eq("all ring keys distinct", len(keys), len(set(keys)))
        assert_true(
            "the surviving entry for the duplicated repo is the live one",
            "sess_a" in [e.session for e in ring],
        )


def _check_walk_reaches_every_repo() -> None:
    """The traversal property: N steps visit all N repos, none unreachable.

    Asserted positively — visiting every distinct repo key — rather than by
    checking that the ring merely shrank, which a broken walk could satisfy.
    """
    with _Fixture() as fx:
        repo_one = _make_fake_project(fx.tmp / "repo_one")
        repo_two = _make_fake_project(fx.tmp / "repo_two")
        repo_three = _make_fake_project(fx.tmp / "repo_three")
        sessions = _assemble_aitasks_sessions(
            [
                ("sess_a", repo_one),
                ("sess_b", repo_one),      # duplicate of repo_one
                ("sess_c", repo_two),
                ("sess_d", repo_three),
            ],
            include_registered=True,
        )
        ring = cross_group_ring(sessions)
        assert_eq("three repos -> three ring entries", 3, len(ring))
        expected = {
            os.path.realpath(repo_one),
            os.path.realpath(repo_two),
            os.path.realpath(repo_three),
        }
        visited = _walk_keys(ring, os.path.realpath(repo_one), 3)
        assert_eq("three steps visit three distinct repos", 3, len(set(visited)))
        assert_eq("every repo is reachable by right-cycling", expected, set(visited))
        assert_eq(
            "the walk wraps back to the starting repo",
            os.path.realpath(repo_one), visited[-1],
        )


def _check_aliased_registry_row_yields_one_ring_entry() -> None:
    """Duplicate source 2 must not reach the ring either.

    A registry row whose name differs from the directory basename at a live
    path is invisible to the name-based skip, so before t1544_1 it produced a
    second ring entry for a repo already present.
    """
    with _Fixture() as fx:
        repo = _make_fake_project(fx.tmp / "realname")
        other = _make_fake_project(fx.tmp / "other_repo")
        fx.set_registry([("registry_alias", repo)])
        sessions = _assemble_aitasks_sessions(
            [("live_sess", repo), ("other_sess", other)],
            include_registered=True,
        )
        ring = cross_group_ring(sessions)
        assert_eq("aliased row does not add a ring entry", 2, len(ring))
        keys = [e.key for e in ring]
        assert_eq("all ring keys distinct", len(keys), len(set(keys)))
        visited = _walk_keys(ring, os.path.realpath(repo), 2)
        assert_eq(
            "both repos reachable despite the alias",
            {os.path.realpath(repo), os.path.realpath(other)}, set(visited),
        )


def main() -> int:
    _check_duplicate_live_sessions_yield_one_ring_entry()
    _check_walk_reaches_every_repo()
    _check_aliased_registry_row_yields_one_ring_entry()
    print(f"\n{PASS}/{TOTAL} passed" + (f", {FAIL} FAILED" if FAIL else ""))
    return 1 if FAIL else 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211)."""

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
