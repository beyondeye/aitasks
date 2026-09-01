"""Byte-exact characterization of gate_ledger.build_block / append_block (t1657_1).

t1657_1 splits ``build_block`` into a *pure envelope renderer* that moves to
``lib/ledger_block.py`` and a gate-specific *compatibility wrapper* that stays on
``gate_ledger``. The split is only safe if the wrapper emits exactly what the
whole function emits today, so this file freezes today's output as literal
goldens rather than as shape assertions.

Why byte-exact and not ``assertIn``: the three things being separated out are
each a single character or token in the output — the ``ICONS`` lookup, the
``attempt=`` clause, and the ``> Label: value`` body rendering with its backtick
wrapping. A substring assertion passes while any of them silently changes
position, spacing, or order.

The wrapper must keep resolving all of these, none of which may move to the seam
(they are gate-specific, and moving them would invert the module dependency):

* ``ICONS`` — status → glyph, including the ``⚠`` fallback for an unknown status;
* ``next_attempt`` + ``TERMINAL_STATUSES`` — the auto-attempt ordinal, and its
  *absence* for a non-terminal status;
* ``BODY_KEYS`` — body label text, fixed order, and which values get backticks;
* the literal ``gate:`` namespace in the marker.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_gate_ledger_build_characterization.py -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "lib"))
import gate_ledger  # noqa: E402


RUN = "2026-06-30T10:00:00Z"

#: (label, gate, status, fields, exact expected block).
#: Covers every status in VALID_STATUSES plus an unregistered one, both
#: attempt paths, the marker tail keys, and the body matrix.
GOLDENS = [
    (
        "pass — auto attempt on an empty ledger",
        "g", "pass", {"run": RUN},
        "> **✅ gate:g** run=2026-06-30T10:00:00Z status=pass attempt=1",
    ),
    (
        "explicit attempt wins over the auto ordinal",
        "g", "pass", {"run": RUN, "attempt": "7"},
        "> **✅ gate:g** run=2026-06-30T10:00:00Z status=pass attempt=7",
    ),
    (
        "fail — terminal, so it gets an ordinal",
        "g", "fail", {"run": RUN},
        "> **❌ gate:g** run=2026-06-30T10:00:00Z status=fail attempt=1",
    ),
    (
        "skip — terminal",
        "g", "skip", {"run": RUN},
        "> **⏭ gate:g** run=2026-06-30T10:00:00Z status=skip attempt=1",
    ),
    (
        "error — terminal, and shares the fallback glyph",
        "g", "error", {"run": RUN},
        "> **⚠ gate:g** run=2026-06-30T10:00:00Z status=error attempt=1",
    ),
    (
        "running — NON-terminal, so no attempt= clause at all",
        "g", "running", {"run": RUN},
        "> **\U0001f504 gate:g** run=2026-06-30T10:00:00Z status=running",
    ),
    (
        "pending — NON-terminal, so no attempt= clause at all",
        "g", "pending", {"run": RUN},
        "> **⏸ gate:g** run=2026-06-30T10:00:00Z status=pending",
    ),
    (
        "unknown status — ⚠ fallback AND no attempt (not terminal)",
        "g", "bogus", {"run": RUN},
        "> **⚠ gate:g** run=2026-06-30T10:00:00Z status=bogus",
    ),
    (
        "marker tail keys keep their fixed duration-then-type order",
        "g", "pass", {"run": RUN, "duration": "3s", "type": "machine"},
        "> **✅ gate:g** run=2026-06-30T10:00:00Z status=pass attempt=1"
        " duration=3s type=machine",
    ),
    (
        "all body keys — fixed order, backticks on verifier and log only",
        "g", "pass",
        {"run": RUN, "verifier": "v.sh", "result": "ok", "log": "/l",
         "note": "n"},
        "> **✅ gate:g** run=2026-06-30T10:00:00Z status=pass attempt=1\n"
        ">\n"
        "> Verifier: `v.sh`\n"
        "> Result: ok\n"
        "> Log: `/l`\n"
        "> Note: n",
    ),
    (
        "a single body key still emits the '>' separator line",
        "g", "pass", {"run": RUN, "note": "just a note"},
        "> **✅ gate:g** run=2026-06-30T10:00:00Z status=pass attempt=1\n"
        ">\n"
        "> Note: just a note",
    ),
]


class BuildBlockGoldenTest(unittest.TestCase):

    def test_every_golden_matches_byte_for_byte(self):
        for label, gate, status, fields, expected in GOLDENS:
            with self.subTest(label):
                self.assertEqual(
                    gate_ledger.build_block("", gate, status, dict(fields)),
                    expected,
                )

    def test_matrix_covers_every_valid_status(self):
        """A status added to VALID_STATUSES without a golden would slip through."""
        covered = {status for _, _, status, _, _ in GOLDENS}
        self.assertEqual(set(gate_ledger.VALID_STATUSES) - covered, set())

    def test_auto_attempt_counts_prior_terminal_runs(self):
        prior = "\n\n".join(
            gate_ledger.build_block("", "g", "fail", {"run": RUN, "attempt": str(i)})
            for i in (1, 2)
        )
        self.assertEqual(
            gate_ledger.build_block(prior, "g", "pass", {"run": RUN}),
            "> **✅ gate:g** run=2026-06-30T10:00:00Z status=pass attempt=3",
        )

    def test_auto_attempt_ignores_a_different_gate(self):
        prior = gate_ledger.build_block("", "other", "fail", {"run": RUN})
        self.assertEqual(
            gate_ledger.build_block(prior, "g", "pass", {"run": RUN}),
            "> **✅ gate:g** run=2026-06-30T10:00:00Z status=pass attempt=1",
        )

    def test_absent_run_is_generated_as_iso_z(self):
        block = gate_ledger.build_block("", "g", "pass", {})
        m = re.match(
            r"^> \*\*✅ gate:g\*\* run=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
            r" status=pass attempt=1$",
            block,
        )
        self.assertIsNotNone(m, f"unexpected generated-run block: {block!r}")

    def test_fields_argument_is_not_mutated(self):
        """build_block pops from a copy — callers reuse their dict."""
        fields = {"run": RUN, "attempt": "2"}
        gate_ledger.build_block("", "g", "pass", fields)
        self.assertEqual(fields, {"run": RUN, "attempt": "2"})


class AppendBlockGoldenTest(unittest.TestCase):

    BODY = "---\nstatus: Ready\n---\n\nBody.\n"

    def test_creates_the_section_at_eof(self):
        new_text, block = gate_ledger.append_block(
            self.BODY, "g", "pass", {"run": RUN})
        self.assertEqual(
            new_text,
            self.BODY
            + f"\n{gate_ledger.SECTION_HEADER}\n{gate_ledger.SECTION_COMMENT}\n"
            + f"\n{block}\n",
        )

    def test_appends_into_an_existing_section_without_a_second_header(self):
        first, _ = gate_ledger.append_block(self.BODY, "g", "pass", {"run": RUN})
        second, blk2 = gate_ledger.append_block(
            first, "h", "pass", {"run": "2026-06-30T11:00:00Z"})
        self.assertEqual(second, first + f"\n{blk2}\n")
        self.assertEqual(second.count(gate_ledger.SECTION_HEADER), 1)

    def test_missing_trailing_newline_is_normalized(self):
        new_text, _ = gate_ledger.append_block(
            "no trailing newline", "g", "pass", {"run": RUN})
        self.assertTrue(new_text.startswith("no trailing newline\n"))

    def test_returned_block_is_build_block_output(self):
        _, block = gate_ledger.append_block(self.BODY, "g", "pass", {"run": RUN})
        self.assertEqual(
            block, gate_ledger.build_block(self.BODY, "g", "pass", {"run": RUN}))


if __name__ == "__main__":
    unittest.main()
