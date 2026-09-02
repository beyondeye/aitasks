"""The ledger-block namespace is a validated identifier (t1669).

``lib/ledger_block.py`` interpolates the caller's ``namespace`` straight into a
regex. Before this fix the module *declared* the intended charset
(``_NAMESPACE_CHARS``) and never applied it, so:

* ``parse_blocks(gate_text, "....")`` returned the **gate** ledger's records — a
  wildcard namespace silently cross-parsing another ledger's blocks, which a
  consumer would then union, dedup and order under the wrong spec;
* ``build_marker_re("note(")`` crashed inside ``re`` with a ``PatternError``.

The contract is now: a namespace matching ``_NAMESPACE_CHARS`` or a
``ValueError``. Rejecting rather than ``re.escape``-ing is the point — escaping
would make a nonsense namespace *work*.

Two things this file pins that a builders-only guard would miss:

1. **Every public entry point that takes a namespace validates it**, driven from
   one table (`ENTRY_POINTS`) so a sixth entry point cannot be added without
   either appearing here or failing the coverage assertion.
2. **The precompiled-pattern route validates too.** ``has_markers`` /
   ``parse_blocks`` never read ``namespace`` when handed a pattern, so a guard
   placed only inside the builders leaves those two public arguments unchecked.
   The negative case below fails in exactly that scenario, and the positive
   control beside it stops a "fix" that just breaks ``gate_ledger``'s
   module-level precompilation instead.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_ledger_block_namespace_validation.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "lib"))
import ledger_block  # noqa: E402


#: A rendered gate block, built through the seam itself.
GATE_TEXT = ledger_block.render_block(
    "gate", "tests_pass", "✅",
    [("run", "2026-01-01T00:00:00Z"), ("attempt", "1")],
    ["> Note: seeded by the namespace-validation suite"],
)

#: Namespaces that must be refused. ``"...."`` is the silent cross-parse,
#: ``"note("`` the ``re`` crash, ``"note|gate"`` the alternation that
#: re-partitions the whole pattern, ``"gate\n"`` the reason the matcher is
#: anchored with ``\A``/``\Z`` rather than ``^``/``$``.
BAD_NAMESPACES = ("....", "note(", "", "note|gate", "gate\n", "ga te",
                  "gate:note", "gate-1")

#: Namespaces that must keep working. Both are live in the tree: ``gate`` is
#: ``gate_ledger.NAMESPACE``; ``note`` is the second ledger's.
GOOD_NAMESPACES = ("gate", "note")

#: Every public entry point taking a namespace, as ``name -> call(namespace)``.
#: Driving both the reject and the accept set from one table is what stops a new
#: entry point from being added with no guard.
ENTRY_POINTS = {
    "build_marker_re":
        lambda ns: ledger_block.build_marker_re(ns),
    "build_marker_search_re":
        lambda ns: ledger_block.build_marker_search_re(ns),
    "has_markers":
        lambda ns: ledger_block.has_markers(GATE_TEXT, ns),
    "parse_blocks":
        lambda ns: ledger_block.parse_blocks(GATE_TEXT, ns),
    "render_block":
        lambda ns: ledger_block.render_block(ns, "n", "x", [], []),
}


class NamespaceRejectionTest(unittest.TestCase):
    """Out-of-charset namespaces raise, at every entry point."""

    def test_every_entry_point_rejects_every_bad_namespace(self):
        for name, call in ENTRY_POINTS.items():
            for ns in BAD_NAMESPACES:
                with self.subTest(entry_point=name, namespace=ns):
                    with self.assertRaises(ValueError):
                        call(ns)

    def test_message_names_the_charset_and_the_offending_value(self):
        """The guard's message is part of the guard.

        Asserted with ``assertIn`` rather than ``assertRaisesRegex``: the
        message embeds the charset literal, which is itself a regex.
        """
        for name, call in ENTRY_POINTS.items():
            with self.subTest(entry_point=name):
                with self.assertRaises(ValueError) as cm:
                    call("....")
                msg = str(cm.exception)
                self.assertIn(ledger_block._NAMESPACE_CHARS, msg)
                self.assertIn(repr("...."), msg)

    def test_entry_point_table_covers_the_module(self):
        """Coverage claim, executable: no public namespace-taking function is
        missing from ``ENTRY_POINTS``."""
        import inspect

        taking_namespace = {
            name for name, obj in vars(ledger_block).items()
            if inspect.isfunction(obj) and not name.startswith("_")
            and "namespace" in inspect.signature(obj).parameters
        }
        self.assertEqual(taking_namespace, set(ENTRY_POINTS))


class NamespaceAcceptanceTest(unittest.TestCase):
    """The namespaces actually in the tree keep working, unchanged."""

    def test_every_entry_point_accepts_the_live_namespaces(self):
        for name, call in ENTRY_POINTS.items():
            for ns in GOOD_NAMESPACES:
                with self.subTest(entry_point=name, namespace=ns):
                    call(ns)  # must not raise

    def test_gate_parsing_is_unchanged(self):
        blocks = ledger_block.parse_blocks(GATE_TEXT, "gate")
        self.assertEqual([b.name for b in blocks], ["tests_pass"])
        self.assertEqual(blocks[0].fields["attempt"], "1")

    def test_render_emits_the_namespace_verbatim(self):
        self.assertTrue(GATE_TEXT.startswith("> **✅ gate:tests_pass**"))


class PrecompiledPatternRouteTest(unittest.TestCase):
    """``namespace`` is validated even when a supplied pattern makes it unused.

    This is the hole a builders-only guard leaves: on this route neither
    function ever reads the argument, so nothing would reject it.
    """

    def setUp(self):
        self.marker_re = ledger_block.build_marker_re("gate")
        self.search_re = ledger_block.build_marker_search_re("gate")

    def test_parse_blocks_rejects_a_bad_namespace_despite_a_valid_pattern(self):
        for ns in BAD_NAMESPACES:
            with self.subTest(namespace=ns):
                with self.assertRaises(ValueError):
                    ledger_block.parse_blocks(GATE_TEXT, ns,
                                              marker_re=self.marker_re)

    def test_has_markers_rejects_a_bad_namespace_despite_a_valid_pattern(self):
        for ns in BAD_NAMESPACES:
            with self.subTest(namespace=ns):
                with self.assertRaises(ValueError):
                    ledger_block.has_markers(GATE_TEXT, ns,
                                             search_re=self.search_re)

    def test_the_supported_precompiled_route_still_works(self):
        """Positive control for ``gate_ledger``'s module-level precompilation —
        so the two assertions above cannot be satisfied by breaking it."""
        blocks = ledger_block.parse_blocks(GATE_TEXT, "gate",
                                           marker_re=self.marker_re)
        self.assertEqual([b.name for b in blocks], ["tests_pass"])
        self.assertTrue(ledger_block.has_markers(GATE_TEXT, "gate",
                                                 search_re=self.search_re))


class CrossLedgerParseTest(unittest.TestCase):
    """The reported defect, as a negative control.

    Without this the suite would pass against a validator that is defined but
    never wired into ``parse_blocks``.
    """

    def test_wildcard_namespace_no_longer_cross_parses_the_gate_ledger(self):
        # Pre-fix this returned the gate record.
        with self.assertRaises(ValueError):
            ledger_block.parse_blocks(GATE_TEXT, "....")

    def test_a_valid_foreign_namespace_still_matches_nothing(self):
        """Rejection must not be doing the isolation work: a *legal* namespace
        that is simply not this ledger's still parses zero blocks."""
        self.assertEqual(ledger_block.parse_blocks(GATE_TEXT, "note"), [])
        self.assertFalse(ledger_block.has_markers(GATE_TEXT, "note"))


if __name__ == "__main__":
    unittest.main()
