"""The gate_ledger re-export contract across the t1657_1 seam extraction.

t1657_1 moves generic marker-block primitives out of ``lib/gate_ledger.py`` into
``lib/ledger_block.py``. Eight names in that moving set are referenced from
**outside** ``gate_ledger``, so every one must still resolve as
``gate_ledger.<name>`` afterwards. Measured across the repo at planning time:

=========================  ====  ==================================================
name                       refs  a notable external consumer
=========================  ====  ==================================================
``has_gate_markers``          8  ``tests/test_gate_ledger_public_api.py``
``parse_gate_run_blocks``     7  ``board/aitask_merge.py``
``SECTION_HEADER``            3  ``aitask_merge._union_gate_runs`` section rebuild
``SECTION_COMMENT``           3  same
``iso_now``                   2  ``lib/gate_orchestrator.py:359``
``GateRun``                   2  ``tests/test_gate_stale_signed_unit.py:35``
``build_block``               1  ``tests/test_aitask_merge.py:301``
``_atomic_write``             1  ``lib/gate_registry_sync.py:519`` — **private**,
                                 yet consumed externally
=========================  ====  ==================================================

That coverage is real but *incidental*: it is spread over six unrelated test
files, none of which states the contract. This file states it.

**The eight do not re-export the same way, and asserting one uniform thing would
be wrong.** ``build_block`` must stay a gate-specific wrapper over the seam's
pure renderer — it resolves ``ICONS``, ``next_attempt`` and ``BODY_KEYS``, none of
which may move — so ``gate_ledger.build_block is ledger_block.render_block`` is
false *by design*. An identity assertion over it would push the implementation
toward the very shape the task rejects. Three classes, asserted differently:

* **alias** — moved verbatim, so identity holds: ``iso_now``, ``_atomic_write``.
* **wrapper** — namespace- or gate-bound, so only signature and behaviour hold:
  ``build_block``, ``append_block``, ``parse_gate_run_blocks``,
  ``has_gate_markers``. ``MARKER_RE`` / ``MARKER_SEARCH_RE`` bake ``gate:`` into
  the pattern, which is why the last two are wrappers and not aliases.
* **value** — gate-specific constants: ``SECTION_HEADER``, ``SECTION_COMMENT``.

Written BEFORE the extraction, so it characterizes rather than expects: the
surface half runs identically in both worlds, and the alias half activates once
``ledger_block`` exists. That conditional is not a permanent hole — the seam is
imported unconditionally by ``tests/test_ledger_block_multisection.py``, so a
refactor that never produced the module fails there.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_ledger_block_reexport.py -v
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "lib"))
import gate_ledger  # noqa: E402

try:
    ledger_block = importlib.import_module("ledger_block")
except ImportError:                      # pre-extraction
    ledger_block = None


#: Names that move verbatim — after extraction gate_ledger must expose the very
#: same object the seam defines.
ALIASES = ("iso_now", "_atomic_write")

#: Names that stay gate-bound wrappers. Signature is pinned exactly as it is
#: today; identity is deliberately NOT asserted.
WRAPPER_SIGNATURES = {
    "build_block": "(text: 'str', gate: 'str', status: 'str', fields: 'dict') -> 'str'",
    "append_block": "(text: 'str', gate: 'str', status: 'str', fields: 'dict') -> 'tuple[str, str]'",
    "parse_gate_run_blocks": "(text: 'str') -> 'list[GateRun]'",
    "has_gate_markers": "(text: 'str') -> 'bool'",
}

#: Gate-specific constants, pinned by value.
CONSTANTS = {
    "SECTION_HEADER": "## Gate Runs",
    "SECTION_COMMENT": (
        "<!-- Appended by the gate framework. Do not edit by hand; use "
        "`./.aitask-scripts/aitask_gate.sh append` for corrections. -->"
    ),
}

#: GateRun's shape, in declaration order.
GATERUN_FIELDS = ["name", "icon", "fields", "body_fields", "line_number",
                  "raw_marker", "raw_body_lines"]

RUN = "2026-06-30T10:00:00Z"


class SurfaceTest(unittest.TestCase):
    """Runs identically before and after the extraction."""

    def test_every_external_name_resolves_on_gate_ledger(self):
        for name in (*ALIASES, *WRAPPER_SIGNATURES, *CONSTANTS, "GateRun"):
            with self.subTest(name):
                self.assertTrue(hasattr(gate_ledger, name),
                                f"gate_ledger.{name} no longer resolves")

    def test_aliases_are_callable(self):
        for name in ALIASES:
            with self.subTest(name):
                self.assertTrue(callable(getattr(gate_ledger, name)))

    def test_wrapper_signatures_are_unchanged(self):
        for name, expected in WRAPPER_SIGNATURES.items():
            with self.subTest(name):
                actual = str(inspect.signature(getattr(gate_ledger, name)))
                self.assertEqual(actual, expected)

    def test_constants_keep_their_exact_values(self):
        for name, expected in CONSTANTS.items():
            with self.subTest(name):
                self.assertEqual(getattr(gate_ledger, name), expected)

    def test_gaterun_shape_is_stable(self):
        self.assertTrue(dataclasses.is_dataclass(gate_ledger.GateRun))
        self.assertEqual(
            [f.name for f in dataclasses.fields(gate_ledger.GateRun)],
            GATERUN_FIELDS,
        )
        self.assertTrue(gate_ledger.GateRun.__dataclass_params__.frozen)


class WrapperBehaviourTest(unittest.TestCase):
    """Behaviour the wrappers must preserve — identity cannot express this."""

    def test_parse_round_trips_a_built_block(self):
        block = gate_ledger.build_block("", "g", "pass", {"run": RUN})
        runs = gate_ledger.parse_gate_run_blocks(block)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].name, "g")
        self.assertEqual(runs[0].fields["run"], RUN)
        self.assertEqual(runs[0].fields["status"], "pass")

    def test_parse_binds_the_gate_namespace(self):
        """A foreign namespace must NOT parse as a gate run — this is exactly
        what makes parse_gate_run_blocks a wrapper rather than an alias."""
        foreign = ("> **✉ note:t349** id=2026-09-01T10:00:00Z.aa "
                   "at=2026-09-01T10:00:00Z")
        self.assertEqual(gate_ledger.parse_gate_run_blocks(foreign), [])
        self.assertFalse(gate_ledger.has_gate_markers(foreign))

    def test_has_gate_markers_detects_a_real_marker(self):
        block = gate_ledger.build_block("", "g", "pass", {"run": RUN})
        self.assertTrue(gate_ledger.has_gate_markers(block))
        self.assertFalse(gate_ledger.has_gate_markers("no markers here"))

    def test_iso_now_shape(self):
        self.assertRegex(gate_ledger.iso_now(),
                         r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_atomic_write_round_trips(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.md")
            gate_ledger._atomic_write(p, "content\n")
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "content\n")


@unittest.skipIf(ledger_block is None,
                 "lib/ledger_block.py does not exist yet (pre-extraction)")
class SeamAliasIdentityTest(unittest.TestCase):
    """Activates once the seam lands. Aliases must be the SAME object."""

    def test_verbatim_moves_are_the_same_object(self):
        for name in ALIASES:
            with self.subTest(name):
                self.assertIs(getattr(gate_ledger, name),
                              getattr(ledger_block, name),
                              f"gate_ledger.{name} must re-export the seam's "
                              f"object, not a copy")

    def test_wrappers_are_not_bare_seam_functions(self):
        """build_block resolves ICONS / next_attempt / BODY_KEYS, so it cannot
        be the seam's pure renderer. Guards against over-extraction."""
        renderer = getattr(ledger_block, "render_block", None)
        if renderer is not None:
            self.assertIsNot(gate_ledger.build_block, renderer)

    def test_gate_specific_symbols_stayed_behind(self):
        """These must NOT appear on the seam — moving them would invert the
        module dependency (ledger_block -> gate_ledger)."""
        for name in ("next_attempt", "ICONS", "TERMINAL_STATUSES", "BODY_KEYS",
                     "derive_gate_runs", "derive_status", "effective_gates"):
            with self.subTest(name):
                self.assertFalse(
                    hasattr(ledger_block, name),
                    f"ledger_block.{name} is gate-specific and must stay in "
                    f"gate_ledger")


if __name__ == "__main__":
    unittest.main()
