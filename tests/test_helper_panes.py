"""The bound-helper pane rule is defined once and reached by every consumer (t2073_3).

`lib/helper_panes.py` owns the helper-target options (`@aitask_shadow_target`,
`@aitask_scratchpad_target`) and the one predicate over them. This file pins:

* identity — `monitor_core` and the `tmux_monitor` shim re-export the SAME
  objects, so no consumer can hold a private copy of the tuple;
* every Python format that classifies helpers carries every option in the
  tuple (`FROZEN_AWARE_PANE_FORMAT`, `_LIST_PANES_FORMAT`, and the format the
  minimonitor occupancy check sends);
* the bash copy (`aitask_companion_cleanup.sh`) names every option in BOTH of
  its `-F` formats — the tripwire that fails when a kind is added here and not
  there;
* the occupancy check: a scratchpad bound to the agent does not count toward
  the 3-real-pane overcrowding limit, with a negative control.

Run: python3 tests/test_helper_panes.py
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_launch_utils  # noqa: E402
import helper_panes  # noqa: E402
from monitor import monitor_core, tmux_monitor  # noqa: E402

CLEANUP_SCRIPT = REPO_ROOT / ".aitask-scripts" / "aitask_companion_cleanup.sh"


class IdentityTests(unittest.TestCase):
    """One definition: the re-exports are the same objects, not copies."""

    def test_monitor_core_reexports_the_same_objects(self):
        for name in ("BOUND_HELPER_TARGET_OPTIONS", "SHADOW_TARGET_OPTION",
                     "SCRATCHPAD_TARGET_OPTION", "SCRATCHPAD_STORE_OPTION",
                     "is_bound_helper"):
            with self.subTest(name=name):
                self.assertIs(getattr(monitor_core, name),
                              getattr(helper_panes, name))

    def test_tmux_monitor_shim_reexports_the_same_objects(self):
        for name in ("BOUND_HELPER_TARGET_OPTIONS", "SHADOW_TARGET_OPTION",
                     "SCRATCHPAD_TARGET_OPTION", "is_bound_helper"):
            with self.subTest(name=name):
                self.assertIs(getattr(tmux_monitor, name),
                              getattr(helper_panes, name))

    def test_the_tuple_holds_both_kinds_and_not_the_store_option(self):
        self.assertEqual(
            helper_panes.BOUND_HELPER_TARGET_OPTIONS,
            ("@aitask_shadow_target", "@aitask_scratchpad_target"),
        )
        self.assertNotIn(helper_panes.SCRATCHPAD_STORE_OPTION,
                         helper_panes.BOUND_HELPER_TARGET_OPTIONS,
                         "the store option is a duplicate-lookup key, not a "
                         "helper marker")


class PythonFormatTests(unittest.TestCase):
    """Every Python helper-classifying format carries every helper option."""

    def test_frozen_aware_format(self):
        specs = monitor_core.FROZEN_AWARE_PANE_FORMAT.split("\t")
        self.assertEqual(len(specs), monitor_core._FROZEN_AWARE_ARITY)
        for opt in helper_panes.BOUND_HELPER_TARGET_OPTIONS:
            self.assertIn(f"#{{{opt}}}", specs)

    def test_discovery_format(self):
        specs = monitor_core.TmuxMonitor._LIST_PANES_FORMAT.split("\t")
        for opt in helper_panes.BOUND_HELPER_TARGET_OPTIONS:
            self.assertIn(f"#{{{opt}}}", specs)


class CleanupScriptTripwireTests(unittest.TestCase):
    """The bash copy reads every option — in job 1 AND job 2."""

    def _formats(self) -> list[str]:
        text = CLEANUP_SCRIPT.read_text()
        return re.findall(r"-F '([^']*)'", text)

    def test_both_jobs_have_a_format(self):
        formats = self._formats()
        self.assertEqual(len(formats), 2,
                         f"expected job 1 + job 2 `-F` formats, got {formats}")

    def test_every_helper_option_appears_in_both_formats(self):
        for fmt in self._formats():
            for opt in helper_panes.BOUND_HELPER_TARGET_OPTIONS:
                with self.subTest(fmt=fmt, opt=opt):
                    self.assertIn(f"#{{{opt}}}", fmt.split("|"))

    def test_negative_control_a_missing_option_is_detected(self):
        """The check above is not vacuous: an option absent from a format fails it."""
        fmt = self._formats()[0].replace("|#{@aitask_scratchpad_target}", "")
        self.assertNotIn("#{@aitask_scratchpad_target}", fmt.split("|"))


class _OccupancyTmux:
    """Answers `list-panes -F` from a pane model; records `split-window`."""

    def __init__(self, panes: list[dict[str, str]]):
        self.panes = panes
        self.calls: list[list[str]] = []

    def run(self, args, **_kw):
        self.calls.append(list(args))
        if args[0] == "list-panes":
            fmt = args[args.index("-F") + 1]
            rows = ["|".join(p.get(spec.strip("#{}"), "")
                             for spec in fmt.split("|"))
                    for p in self.panes]
            return 0, "\n".join(rows) + "\n"
        if args[0] == "split-window":
            return 0, "%99\n"
        return 1, ""

    def spawn(self, *_a, **_kw):
        return None

    def splits(self) -> list[list[str]]:
        return [c for c in self.calls if c[0] == "split-window"]


class OccupancyCheckTests(unittest.TestCase):
    """`_companion_check_and_split` counts bound helpers as non-occupants."""

    def _run(self, panes):
        stub = _OccupancyTmux(panes)
        saved = agent_launch_utils._TMUX
        agent_launch_utils._TMUX = stub
        try:
            result = agent_launch_utils._companion_check_and_split(
                "demo", "1", "%1", 40, None)
        finally:
            agent_launch_utils._TMUX = saved
        return result, stub

    @staticmethod
    def _pane(pane_id: str, **opts: str) -> dict[str, str]:
        return {"pane_id": pane_id, "pane_dead": "0",
                "pane_start_command": "claude", **opts}

    def test_the_sent_format_carries_every_helper_option(self):
        _result, stub = self._run([self._pane("%1")])
        fmt = stub.calls[0][stub.calls[0].index("-F") + 1]
        for opt in helper_panes.BOUND_HELPER_TARGET_OPTIONS:
            self.assertIn(f"#{{{opt}}}", fmt.split("|"))
        self.assertTrue(fmt.endswith("#{pane_start_command}"),
                        "the free-text start command must stay LAST")

    def test_a_bound_scratchpad_does_not_count_toward_the_limit(self):
        panes = [self._pane("%1"), self._pane("%2"),
                 self._pane("%3", **{"@aitask_scratchpad_target": "%1"})]
        (split_ran, companion, _agent), stub = self._run(panes)
        self.assertTrue(split_ran)
        self.assertEqual(companion, "%99")
        self.assertEqual(len(stub.splits()), 1)

    def test_negative_control_three_real_panes_refuse(self):
        panes = [self._pane("%1"), self._pane("%2"), self._pane("%3")]
        (split_ran, _companion, _agent), stub = self._run(panes)
        self.assertFalse(split_ran)
        self.assertEqual(stub.splits(), [])

    def test_a_frozen_standin_with_a_retained_target_still_counts(self):
        """Frozen first: a stand-in occupies the window whatever it carries."""
        panes = [self._pane("%1"), self._pane("%2"),
                 self._pane("%3", **{"@aitask_scratchpad_target": "%1",
                                     "@aitask_frozen": "7f3a2c1d"})]
        (split_ran, _companion, _agent), stub = self._run(panes)
        self.assertFalse(split_ran)
        self.assertEqual(stub.splits(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
