#!/usr/bin/env python3
"""Session-discovery dedupe for `_assemble_aitasks_sessions` (t1544_1).

`AitasksSession.key` (realpath of `project_root`) is the identity every
registry-inclusive consumer caches, labels and cycles on, so one repo must
produce exactly one record there. Three inputs used to produce two:

  1. two live tmux sessions whose panes walk up to the same project root;
  2. a registry row whose `name` differs from `project_root.name` at a path
     that is also live (the `live_names` skip matches on name, not path);
  3. two registry rows pointing at the same path under different names.

These checks call `_assemble_aitasks_sessions` DIRECTLY, constructing the
`live_roots` tuples the tmux scan would have produced. The tmux round-trips are
the other half of discovery and are already covered end-to-end by
tests/test_discover_include_registered.py, tests/test_discover_default_unchanged.py
and tests/test_discover_async_parity.py; faking them here would pin that
plumbing rather than the assembly logic, and duplicate source 1 is not
expressible through a tmux fake at all (tmux session names are unique, yet two
sessions can share a repo).

Registry reads are REAL: every check sets `AITASKS_PROJECTS_INDEX`, including
the live-only ones — `_build_registry_group_lookup()` runs unconditionally and
would otherwise read the developer's own ~/.config/aitasks/projects.yaml and
make results machine-dependent.

Run: python3 tests/test_discover_session_dedupe.py
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

from agent_launch_utils import _assemble_aitasks_sessions  # noqa: E402

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


def assert_false(desc: str, actual) -> None:
    assert_eq(desc, False, bool(actual))


# --- fixtures --------------------------------------------------------------
# Shape mirrors tests/test_discover_include_registered.py::_make_fake_project /
# _make_registry. Duplicated rather than cross-imported: there is no
# tests/conftest.py or tests/__init__.py and no test module in this repo
# imports another (see also test_discover_default_unchanged.py).


def _make_fake_project(root: Path, *, default_session: str | None = None) -> Path:
    (root / "aitasks" / "metadata").mkdir(parents=True)
    cfg = root / "aitasks" / "metadata" / "project_config.yaml"
    if default_session is not None:
        cfg.write_text(f"tmux:\n  default_session: {default_session}\n")
    else:
        cfg.write_text("project:\n  name: fake\n")
    return root


def _make_registry(path: Path, entries: list[tuple[str, Path]]) -> None:
    lines = ["projects:\n"]
    for name, root in entries:
        lines.append(f"  - name: {name}\n")
        lines.append(f"    path: {root}\n")
    path.write_text("".join(lines))


class _Fixture:
    """tmpdir + an always-set AITASKS_PROJECTS_INDEX, restored on exit."""

    def __enter__(self) -> "_Fixture":
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self._saved = os.environ.get("AITASKS_PROJECTS_INDEX")
        self.set_registry([])  # never fall through to the real user registry
        return self

    def set_registry(self, entries: list[tuple[str, Path]]) -> Path:
        idx = self.tmp / "projects.yaml"
        _make_registry(idx, entries)
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        return idx

    def __exit__(self, *exc) -> bool:
        if self._saved is None:
            os.environ.pop("AITASKS_PROJECTS_INDEX", None)
        else:
            os.environ["AITASKS_PROJECTS_INDEX"] = self._saved
        self._td.cleanup()
        return False


# --- characterization: CURRENT non-duplicate behavior ----------------------
# These pin behavior that the dedupe must NOT change. They pass before and
# after the edit, byte for byte. A diff touching one of them in the
# implementation commit is a red flag.


def _check_single_live_root() -> None:
    with _Fixture() as fx:
        proj = _make_fake_project(fx.tmp / "solo")
        out = _assemble_aitasks_sessions(
            [("solo_sess", proj)], include_registered=False
        )
        assert_eq("single live root -> one record", 1, len(out))
        assert_eq("session preserved verbatim", "solo_sess", out[0].session)
        assert_eq("project_root preserved", proj, out[0].project_root)
        assert_eq("project_name is the basename", "solo", out[0].project_name)
        assert_true("live record is_live", out[0].is_live)
        assert_false("live record not stale", out[0].is_stale)
        assert_eq("ungrouped repo resolves to None", None, out[0].project_group)


def _check_live_plus_registered_distinct_names() -> None:
    with _Fixture() as fx:
        live = _make_fake_project(fx.tmp / "live_proj")
        reg = _make_fake_project(fx.tmp / "reg_proj", default_session="reg_sess")
        fx.set_registry([("reg_proj", reg)])
        out = _assemble_aitasks_sessions(
            [("live_sess", live)], include_registered=True
        )
        assert_eq("live + distinct registered -> two records", 2, len(out))
        by_name = {s.project_name: s for s in out}
        assert_true("live record is_live", by_name["live_proj"].is_live)
        assert_eq("live session name", "live_sess", by_name["live_proj"].session)
        assert_false("registered record not live", by_name["reg_proj"].is_live)
        assert_eq(
            "registered session from its own config",
            "reg_sess", by_name["reg_proj"].session,
        )
        assert_false("OK registry row not stale", by_name["reg_proj"].is_stale)


def _check_stale_registry_row() -> None:
    with _Fixture() as fx:
        ghost = fx.tmp / "no_such_dir"  # marker missing -> STALE
        fx.set_registry([("ghost", ghost)])
        out = _assemble_aitasks_sessions([], include_registered=True)
        # The ASSEMBLER emits it (the TUI switcher needs it to offer repair).
        assert_eq("stale row emitted by the assembler", 1, len(out))
        assert_true("stale row flagged", out[0].is_stale)
        assert_false("stale row not live", out[0].is_live)
        assert_eq("stale row keeps the registry name", "ghost", out[0].project_name)
        assert_eq(
            "stale row session falls back to aitasks", "aitasks", out[0].session
        )
        # The stats TUI is the consumer that must DROP it — a different layer.
        # The half that runs the real `discover_stats_sessions` lives in
        # tests/test_stats_include_registered.py (that module already imports
        # stats_app / Textual; this one deliberately does not).
        assert_eq(
            "discover_stats_sessions' predicate drops it",
            [], [s for s in out if not s.is_stale],
        )


def _check_sort_by_session_name() -> None:
    with _Fixture() as fx:
        px = _make_fake_project(fx.tmp / "px", default_session="bbb")
        py = _make_fake_project(fx.tmp / "py", default_session="aaa")
        fx.set_registry([("px", px), ("py", py)])
        out = _assemble_aitasks_sessions([], include_registered=True)
        assert_eq(
            "sorted by session name, not registry order",
            ["aaa", "bbb"], [s.session for s in out],
        )
        assert_eq(
            "and carry the matching projects",
            ["py", "px"], [s.project_name for s in out],
        )


def _check_sort_is_stable_on_session_ties() -> None:
    # Equal sort keys (both repos fall back to session="aitasks"): the stable
    # sort must keep insertion order, and insertion order is live-then-
    # registered. This is the ordering property the dedupe must not disturb.
    with _Fixture() as fx:
        live = _make_fake_project(fx.tmp / "live_a")
        reg = _make_fake_project(fx.tmp / "reg_b")
        fx.set_registry([("reg_b", reg)])
        out = _assemble_aitasks_sessions(
            [("aitasks", live)], include_registered=True
        )
        assert_eq("distinct roots both survive", 2, len(out))
        assert_eq(
            "session names tie", ["aitasks", "aitasks"],
            [s.session for s in out],
        )
        assert_eq(
            "stable sort keeps live before registered",
            ["live_a", "reg_b"], [s.project_name for s in out],
        )


def _check_no_flag_call_keeps_both_live_sessions() -> None:
    """Non-regression for the tmux-session-oriented consumers.

    `ait monitor` builds {s.session: project_root} (monitor_core.py:1798) and
    lists live session names (monitor_core.py:1966), so the default (no-flag)
    call must still report BOTH tmux sessions rooted in one repo. The key
    dedupe is scoped to include_registered=True on purpose.
    """
    with _Fixture() as fx:
        proj = _make_fake_project(fx.tmp / "shared_repo")
        out = _assemble_aitasks_sessions(
            [("sess_a", proj), ("sess_b", proj)], include_registered=False
        )
        assert_eq("no-flag call keeps both live sessions", 2, len(out))
        assert_eq(
            "both session names visible",
            ["sess_a", "sess_b"], sorted(s.session for s in out),
        )


def main() -> int:
    _check_single_live_root()
    _check_live_plus_registered_distinct_names()
    _check_stale_registry_row()
    _check_sort_by_session_name()
    _check_sort_is_stable_on_session_ties()
    _check_no_flag_call_keeps_both_live_sessions()
    print(f"\n{PASS}/{TOTAL} passed" + (f", {FAIL} FAILED" if FAIL else ""))
    return 1 if FAIL else 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211).

    ``assert_eq`` tallies into ``FAIL`` instead of raising, so the assertion is
    on ``main()``'s return code; detail goes to stdout.
    """

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
