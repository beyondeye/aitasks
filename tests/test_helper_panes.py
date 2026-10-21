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
  the 3-real-pane overcrowding limit, with a negative control;
* the direct-kill sweep (t2088): `helpers_bound_to` (frozen first, exact
  target, target-alive => nothing, malformed rows skipped) and
  `kill_bound_helpers` against an in-memory server that evaluates the guarded
  `if-shell -F` dispatch — including races where the model changes between
  the listing and the dispatch (restart, freeze, rebind, process replaced).

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
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_launch_utils  # noqa: E402
import helper_panes  # noqa: E402
from monitor import monitor_core, tmux_monitor  # noqa: E402
from tmux_server_model import TmuxServerModel  # noqa: E402

FROZEN = monitor_core.FROZEN_OPTION
SHADOW = helper_panes.SHADOW_TARGET_OPTION
SCRATCH = helper_panes.SCRATCHPAD_TARGET_OPTION

CLEANUP_SCRIPT = REPO_ROOT / ".aitask-scripts" / "aitask_companion_cleanup.sh"


class IdentityTests(unittest.TestCase):
    """One definition: the re-exports are the same objects, not copies."""

    def test_monitor_core_reexports_the_same_objects(self):
        for name in ("BOUND_HELPER_TARGET_OPTIONS", "SHADOW_TARGET_OPTION",
                     "SCRATCHPAD_TARGET_OPTION", "SCRATCHPAD_STORE_OPTION",
                     "is_bound_helper", "bound_helper_sweep_format",
                     "helpers_bound_to", "kill_bound_helpers"):
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

    def test_sweep_format(self):
        """The direct-kill sweep reads the frozen marker and every helper option."""
        specs = helper_panes.bound_helper_sweep_format(FROZEN).split("\t")
        self.assertEqual(specs[:4],
                         ["#{pane_id}", "#{pane_pid}", "#{pid}", f"#{{{FROZEN}}}"])
        self.assertEqual(specs[4:],
                         [f"#{{{o}}}" for o in helper_panes.BOUND_HELPER_TARGET_OPTIONS])

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


# --- the direct-kill sweep (t2088) -------------------------------------------

def _row(pane_id, pane_pid="100", server="9999", frozen="", shadow="",
         scratch=""):
    """One `bound_helper_sweep_format` row, BUILT FROM that format."""
    values = {"#{pane_id}": pane_id, "#{pane_pid}": pane_pid,
              "#{pid}": server, f"#{{{FROZEN}}}": frozen,
              f"#{{{SHADOW}}}": shadow, f"#{{{SCRATCH}}}": scratch}
    return "\t".join(values[s] for s in
                     helper_panes.bound_helper_sweep_format(FROZEN).split("\t"))


def _ids(cands):
    return [c.pane_id for c in cands]


class HelpersBoundToTests(unittest.TestCase):
    """The pure candidate parse."""

    def test_shadow_and_pad_bound_to_the_target_are_candidates(self):
        out = "\n".join([_row("%2", shadow="%1"), _row("%3", scratch="%1"),
                         _row("%4")]) + "\n"
        cands = helper_panes.helpers_bound_to(out, "%1")
        self.assertEqual(_ids(cands), ["%2", "%3"])
        self.assertEqual([c.option for c in cands], [SHADOW, SCRATCH])

    def test_a_frozen_pane_with_a_retained_target_is_never_a_candidate(self):
        out = _row("%2", frozen="7f3a2c1d", scratch="%1") + "\n"
        self.assertEqual(helper_panes.helpers_bound_to(out, "%1"), [])

    def test_negative_control_the_same_row_unstamped_is_a_candidate(self):
        out = _row("%2", scratch="%1") + "\n"
        self.assertEqual(_ids(helper_panes.helpers_bound_to(out, "%1")), ["%2"])

    def test_a_helper_bound_to_a_sibling_is_not_a_candidate(self):
        out = _row("%3", shadow="%5") + "\n"
        self.assertEqual(helper_panes.helpers_bound_to(out, "%1"), [])

    def test_the_target_still_listed_means_nothing(self):
        """The kill did not take, or a restart recycled the id: hands off."""
        out = "\n".join([_row("%1"), _row("%2", shadow="%1")]) + "\n"
        self.assertEqual(helper_panes.helpers_bound_to(out, "%1"), [])

    def test_a_wrong_arity_row_is_skipped(self):
        out = "%2\t100\t9999\t\t%1\n"
        self.assertEqual(helper_panes.helpers_bound_to(out, "%1"), [])

    def test_a_last_row_with_empty_trailing_fields_still_parses(self):
        """No whole-buffer strip: the final record keeps its empty fields (t1686)."""
        out = "\n".join([_row("%3", scratch="%1"), _row("%2", shadow="%1"),
                         _row("%4")])
        self.assertEqual(_ids(helper_panes.helpers_bound_to(out, "%1")),
                         ["%3", "%2"])

    def test_unsafe_values_are_skipped(self):
        """Nothing malformed may reach a guard condition."""
        out = "\n".join([_row("%2}", shadow="%1"),
                         _row("%3", pane_pid="1,2", shadow="%1"),
                         _row("%4", server="x", shadow="%1")]) + "\n"
        self.assertEqual(helper_panes.helpers_bound_to(out, "%1"), [])
        self.assertEqual(
            helper_panes.helpers_bound_to(_row("%2", shadow="#{x}") + "\n",
                                          "#{x}"), [])


def _model(**extra_panes):
    panes = {
        "%2": {"pane_id": "%2", "pane_pid": "202", "window": "w", SHADOW: "%1"},
        "%3": {"pane_id": "%3", "pane_pid": "303", "window": "w", SCRATCH: "%1"},
        "%4": {"pane_id": "%4", "pane_pid": "404", "window": "w"},
        "%5": {"pane_id": "%5", "pane_pid": "505", "window": "w", SCRATCH: "%4"},
    }
    panes.update(extra_panes)
    return TmuxServerModel(panes)


def _sweep(model, target="%1"):
    return helper_panes.kill_bound_helpers(model, target, frozen_option=FROZEN)


class KillBoundHelpersTests(unittest.TestCase):
    """The guarded sweep against a server model that evaluates conditions."""

    def test_kills_only_the_target_s_helpers(self):
        model = _model()
        self.assertEqual(_sweep(model), ["%2", "%3"])
        self.assertEqual(sorted(model.panes), ["%4", "%5"])

    def test_no_bare_kill_pane_is_ever_issued(self):
        model = _model()
        _sweep(model)
        kills = [c for c in model.calls if c[0] == "kill-pane"]
        self.assertEqual(len(kills), 2)
        self.assertEqual(model.bare_kills(), [],
                         "every kill must sit inside an if-shell branch")

    def test_a_failed_listing_dispatches_nothing(self):
        model = _model()
        model.list_ok = False
        self.assertEqual(_sweep(model), [])
        self.assertEqual([c[0] for c in model.calls], ["list-panes"])

    def test_a_kill_that_did_not_take_is_not_reported(self):
        model = _model()
        model.kill_ok = False
        self.assertEqual(_sweep(model), [])
        self.assertIn("%2", model.panes)

    def test_a_frozen_pane_with_a_retained_target_survives(self):
        model = _model(**{"%6": {"pane_id": "%6", "pane_pid": "606",
                                 FROZEN: "7f3a2c1d", SHADOW: "%1"}})
        _sweep(model)
        self.assertIn("%6", model.panes)

    def test_the_target_still_alive_kills_nothing(self):
        model = _model(**{"%1": {"pane_id": "%1", "pane_pid": "101"}})
        self.assertEqual(_sweep(model), [])
        self.assertEqual(sorted(model.panes), ["%1", "%2", "%3", "%4", "%5"])

    def test_an_unsafe_target_dispatches_nothing(self):
        model = _model()
        self.assertEqual(_sweep(model, target="%1}"), [])
        self.assertNotIn("if-shell", [c[0] for c in model.calls])


class SweepRaceTests(unittest.TestCase):
    """The model changes BETWEEN the listing and the guarded dispatch.

    Each mutation must leave the candidate alive and unreported; the control
    with no mutation kills it. One candidate (%2), so each assertion is about
    exactly the pane the mutation touched.
    """

    def _race(self, mutate):
        model = TmuxServerModel({
            "%2": {"pane_id": "%2", "pane_pid": "202", SHADOW: "%1"},
            "%4": {"pane_id": "%4", "pane_pid": "404"},
        })
        fired = []

        def hook():
            if not fired:
                fired.append(True)
                if mutate is not None:
                    mutate(model)
        model.before_dispatch = hook
        killed = _sweep(model)
        self.assertEqual(fired, [True], "the dispatch was never reached")
        return model, killed

    def test_control_no_mutation_kills_the_candidate(self):
        model, killed = self._race(None)
        self.assertEqual(killed, ["%2"])
        self.assertNotIn("%2", model.panes)

    def test_restart_recycles_the_id_into_an_unrelated_pane(self):
        def restart(m):
            m.server_pid = "7777"
            m.panes["%2"] = {"pane_id": "%2", "pane_pid": "999"}
        model, killed = self._race(restart)
        self.assertEqual(killed, [])
        self.assertIn("%2", model.panes)

    def test_restart_recycles_the_id_into_a_pane_bound_to_the_same_id(self):
        """Same id, same binding, same process id — only the server differs.

        Proves the server-pid half alone rejects it.
        """
        def restart(m):
            m.server_pid = "7777"
        model, killed = self._race(restart)
        self.assertEqual(killed, [])
        self.assertIn("%2", model.panes)

    def test_the_candidate_is_frozen_after_the_listing(self):
        def freeze(m):
            m.panes["%2"][FROZEN] = "7f3a2c1d"
        model, killed = self._race(freeze)
        self.assertEqual(killed, [])
        self.assertIn("%2", model.panes)

    def test_the_candidate_is_rebound_to_another_agent(self):
        def rebind(m):
            m.panes["%2"][SHADOW] = "%4"
        model, killed = self._race(rebind)
        self.assertEqual(killed, [])
        self.assertIn("%2", model.panes)

    def test_the_candidate_s_process_is_replaced(self):
        def respawn(m):
            m.panes["%2"]["pane_pid"] = "203"
        model, killed = self._race(respawn)
        self.assertEqual(killed, [])
        self.assertIn("%2", model.panes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
