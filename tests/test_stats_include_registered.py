#!/usr/bin/env python3
"""Tests for the stats TUI session discovery (t1098).

The stats TUI must list registered repos even when they have no live tmux
session, and must drop STALE registry rows (it has no repair UI). Covered by
exercising the module-level `discover_stats_sessions()` helper with a
monkeypatched `discover_aitasks_sessions`, so no Textual app is mounted.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
STATS_APP_PATH = PROJECT_DIR / ".aitask-scripts" / "stats" / "stats_app.py"

spec = importlib.util.spec_from_file_location("stats_app", STATS_APP_PATH)
assert spec is not None and spec.loader is not None
stats_app = importlib.util.module_from_spec(spec)
sys.modules["stats_app"] = stats_app
spec.loader.exec_module(stats_app)

AitasksSession = stats_app.AitasksSession

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


# --- fixture ---------------------------------------------------------------

LIVE = AitasksSession(
    session="aitasks",
    project_root=Path("/repos/aitasks"),
    project_name="aitasks",
    is_live=True,
)
REGISTERED = AitasksSession(
    session="aitasks_go",
    project_root=Path("/repos/aitasks_go"),
    project_name="aitasks_go",
    is_live=False,
)
STALE = AitasksSession(
    session="gone",
    project_root=Path("/repos/gone"),
    project_name="gone",
    is_live=False,
    is_stale=True,
)

_calls: list[dict] = []


def _fake_discover(*, include_registered: bool = False):
    _calls.append({"include_registered": include_registered})
    # Registry-inclusive callers see all three; the helper must filter STALE.
    if include_registered:
        return [LIVE, REGISTERED, STALE]
    return [LIVE]


# --- tests -----------------------------------------------------------------

def _check_discover_stats_sessions() -> None:
    _calls.clear()
    orig = stats_app.discover_aitasks_sessions
    stats_app.discover_aitasks_sessions = _fake_discover
    try:
        result = stats_app.discover_stats_sessions()
    finally:
        stats_app.discover_aitasks_sessions = orig

    assert_eq("opts into include_registered=True",
              [{"include_registered": True}], _calls)

    names = [s.project_name for s in result]
    assert_true("live session included", "aitasks" in names)
    assert_true("registered (no live session) included", "aitasks_go" in names)
    assert_true("stale registry row excluded", "gone" not in names)
    assert_eq("only non-stale entries returned", 2, len(result))


def _check_stats_drops_a_real_assembler_stale_row() -> None:
    """Seam check: a STALE row the REAL assembler emits must not reach the TUI.

    The check above feeds hand-built AitasksSession objects; this one runs
    `_assemble_aitasks_sessions` for real so the two halves of the layered
    contract cannot drift apart — the assembler KEEPS stale rows (the switcher
    needs them to offer repair) and `discover_stats_sessions` DROPS them. A
    dedupe or filter added to either layer that quietly changed the other would
    otherwise go unnoticed (t1544_1).
    """
    import os
    import tempfile

    sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))
    from agent_launch_utils import _assemble_aitasks_sessions

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        live = tmp / "live_proj"
        (live / "aitasks" / "metadata").mkdir(parents=True)
        (live / "aitasks" / "metadata" / "project_config.yaml").write_text(
            "project:\n  name: live_proj\n"
        )
        idx = tmp / "projects.yaml"
        idx.write_text(
            "projects:\n"
            "  - name: ghost\n"
            f"    path: {tmp / 'no_such_dir'}\n"
        )
        saved = os.environ.get("AITASKS_PROJECTS_INDEX")
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        orig = stats_app.discover_aitasks_sessions
        stats_app.discover_aitasks_sessions = (
            lambda *, include_registered=False: _assemble_aitasks_sessions(
                [("live_sess", live)], include_registered=include_registered
            )
        )
        try:
            assembled = _assemble_aitasks_sessions(
                [("live_sess", live)], include_registered=True
            )
            result = stats_app.discover_stats_sessions()
        finally:
            stats_app.discover_aitasks_sessions = orig
            if saved is None:
                os.environ.pop("AITASKS_PROJECTS_INDEX", None)
            else:
                os.environ["AITASKS_PROJECTS_INDEX"] = saved

    assert_eq("the assembler emits both rows", 2, len(assembled))
    assert_true(
        "one of them is the stale ghost",
        any(s.is_stale for s in assembled),
    )
    assert_eq("stats TUI drops the assembler's STALE row", 1, len(result))
    assert_eq("the live project survives", "live_proj", result[0].project_name)


def main() -> int:
    _check_discover_stats_sessions()
    _check_stats_drops_a_real_assembler_stale_row()
    print(f"\n{PASS}/{TOTAL} passed"
          + (f", {FAIL} FAILED" if FAIL else ""))
    return 1 if FAIL else 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211).

    ``assert_eq`` / ``assert_true`` tally into ``FAIL`` instead of raising, so
    the assertion is on ``main()``'s return code; detail goes to stdout.
    """

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
