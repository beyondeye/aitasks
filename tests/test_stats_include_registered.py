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

def test_discover_stats_sessions() -> None:
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


def main() -> int:
    test_discover_stats_sessions()
    print(f"\n{PASS}/{TOTAL} passed"
          + (f", {FAIL} FAILED" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
