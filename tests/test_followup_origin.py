#!/usr/bin/env python3
"""Origin-resolution semantics for follow-up tasks (t1569_2).

Two tests here are the load-bearing negative controls:

- `test_anchor_is_never_exact` — `anchor` is a topic ROOT, and reporting it as
  `exact` would claim direct causation the data does not support.
- `test_mixed_verifies_does_not_confer_exact` — a `verifies:` list holding one
  good and one malformed id must NOT return `exact` over the valid subset. That
  would hand a consumer a silently incomplete origin surface it could call
  CLEAR. It is written to fail against the obvious "keep the valid ones and
  report the rest" implementation.

The canonicalisation tests cover all three id shapes the live corpus actually
holds (`int`, `'t1018_1'`, bare `'1018_1'`); `task_yaml` normalises neither of
the two fields read here, so an uncanonicalised implementation silently misses
almost every origin.
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, ".aitask-scripts", "lib"))

import followup_origin as fo  # noqa: E402


class ResolveContractTests(unittest.TestCase):
    def test_resolve_returns_exactly_two_values(self):
        """The published contract is a TWO-tuple; widening it breaks the consumer."""
        result = fo.resolve({"verifies": ["t42"]})
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_resolve_detailed_carries_residue(self):
        detailed = fo.resolve_detailed({"verifies": ["t42", "not-an-id"]})
        self.assertIn("residue", detailed)
        self.assertIn("origins", detailed)
        self.assertIn("quality", detailed)


class TruthTableTests(unittest.TestCase):
    def test_all_valid_verifies_is_exact(self):
        self.assertEqual(fo.resolve({"verifies": ["t42", "t43"]}), (["42", "43"], fo.EXACT))

    def test_anchor_only_is_topic(self):
        self.assertEqual(fo.resolve({"anchor": 130}), (["130"], fo.TOPIC))

    def test_neither_is_unknown(self):
        self.assertEqual(fo.resolve({}), ([], fo.UNKNOWN))

    def test_verifies_wins_over_anchor(self):
        origins, quality = fo.resolve({"verifies": ["t42"], "anchor": 130})
        self.assertEqual((origins, quality), (["42"], fo.EXACT))

    def test_anchor_is_never_exact(self):
        """Negative control: anchor is a topic ROOT, never a direct origin."""
        for anchor in (130, "t130", "130", "85_2", "t85_2"):
            _, quality = fo.resolve({"anchor": anchor})
            self.assertEqual(quality, fo.TOPIC, "anchor %r must not be exact" % (anchor,))
            self.assertNotEqual(quality, fo.EXACT)

    def test_empty_verifies_list_falls_through_to_anchor(self):
        self.assertEqual(fo.resolve({"verifies": [], "anchor": 7}), (["7"], fo.TOPIC))


class MalformedEntryTests(unittest.TestCase):
    """Rule 2: a malformed entry DEGRADES the verdict; it is not advisory."""

    def test_mixed_verifies_does_not_confer_exact(self):
        """The load-bearing control against a silently incomplete origin surface."""
        origins, quality = fo.resolve({"verifies": ["t42", "not-an-id"], "anchor": 130})
        self.assertNotEqual(quality, fo.EXACT)
        self.assertEqual(quality, fo.TOPIC)
        self.assertEqual(origins, ["130"])

    def test_mixed_verifies_without_anchor_is_unknown(self):
        origins, quality = fo.resolve({"verifies": ["t42", "not-an-id"]})
        self.assertEqual(quality, fo.UNKNOWN)
        self.assertEqual(origins, [])

    def test_wholly_unparseable_verifies_with_anchor_is_topic(self):
        self.assertEqual(fo.resolve({"verifies": ["??"], "anchor": 9}), (["9"], fo.TOPIC))

    def test_wholly_unparseable_verifies_without_anchor_is_unknown(self):
        self.assertEqual(fo.resolve({"verifies": ["??", "!!"]}), ([], fo.UNKNOWN))

    def test_unparseable_anchor_is_unknown(self):
        self.assertEqual(fo.resolve({"anchor": "aitasks#835_3"}), ([], fo.UNKNOWN))

    def test_degradation_loses_no_information(self):
        """BOTH halves stay recoverable: the parsed ids AND the malformed token.

        Asserting only the residue would pass against an implementation that
        silently discards the id that *did* parse -- which is what the withheld
        quality claim is supposed to be explaining.
        """
        detailed = fo.resolve_detailed({"verifies": ["t42", "not-an-id"]})
        self.assertEqual(detailed["quality"], fo.UNKNOWN)
        self.assertEqual(detailed["origins"], [])
        self.assertEqual(detailed["residue"], ["not-an-id"])
        self.assertEqual(detailed["degraded_origins"], ["42"])

    def test_degraded_origins_survive_a_fallthrough_to_topic(self):
        detailed = fo.resolve_detailed({"verifies": ["t42", "??"], "anchor": 130})
        self.assertEqual(detailed["quality"], fo.TOPIC)
        self.assertEqual(detailed["origins"], ["130"])
        self.assertEqual(detailed["degraded_origins"], ["42"])
        self.assertEqual(detailed["residue"], ["??"])

    def test_degraded_origins_empty_when_nothing_was_withheld(self):
        self.assertEqual(fo.resolve_detailed({"verifies": ["t42"]})["degraded_origins"], [])
        self.assertEqual(fo.resolve_detailed({"anchor": 9})["degraded_origins"], [])

    def test_unparseable_anchor_still_reports_its_parsed_verifies(self):
        detailed = fo.resolve_detailed({"verifies": ["t42", "??"], "anchor": "nope"})
        self.assertEqual(detailed["quality"], fo.UNKNOWN)
        self.assertEqual(detailed["degraded_origins"], ["42"])
        self.assertEqual(sorted(detailed["residue"]), ["??", "nope"])

    def test_residue_from_anchor_is_reported(self):
        detailed = fo.resolve_detailed({"anchor": "nope"})
        self.assertEqual(detailed["residue"], ["nope"])


class CanonicalisationTests(unittest.TestCase):
    """All three shapes the live corpus holds must resolve to bare-string ids."""

    def test_int_anchor(self):
        self.assertEqual(fo.resolve({"anchor": 1018})[0], ["1018"])

    def test_t_prefixed_verifies(self):
        self.assertEqual(fo.resolve({"verifies": ["t1018_1"]})[0], ["1018_1"])

    def test_bare_string_child_verifies(self):
        self.assertEqual(fo.resolve({"verifies": ["1018_1"]})[0], ["1018_1"])

    def test_int_verifies(self):
        self.assertEqual(fo.resolve({"verifies": [1018]})[0], ["1018"])

    def test_mixed_shapes_all_canonicalise_to_one_form(self):
        origins, quality = fo.resolve({"verifies": ["t1018_1", 1018, "42_3"]})
        self.assertEqual(quality, fo.EXACT)
        self.assertEqual(origins, ["1018_1", "1018", "42_3"])

    def test_duplicates_collapse(self):
        self.assertEqual(fo.resolve({"verifies": ["t42", "42", 42]})[0], ["42"])


class FollowupKindIsNotReadTests(unittest.TestCase):
    def test_followup_kind_does_not_change_the_result(self):
        base = {"anchor": 130}
        baseline = fo.resolve(dict(base))
        for kind in ("risk_mitigation", "manual_verification", "upstream_defect", None):
            variant = dict(base)
            if kind is not None:
                variant["followup_kind"] = kind
            self.assertEqual(fo.resolve(variant), baseline)

    def test_followup_kind_alone_confers_no_origin(self):
        self.assertEqual(fo.resolve({"followup_kind": "risk_mitigation"}), ([], fo.UNKNOWN))


class ResidueEncodingTests(unittest.TestCase):
    def test_percent_is_encoded_first_so_the_encoding_is_injective(self):
        # If `%` were encoded last, "%09" and a literal TAB would collide.
        self.assertEqual(fo.encode_residue("%09"), "%2509")
        self.assertEqual(fo.encode_residue("\t"), "%09")
        self.assertNotEqual(fo.encode_residue("%09"), fo.encode_residue("\t"))

    def test_round_trip_of_every_hazardous_byte(self):
        for token in ("a\tb", "a\nb", "a\rb", "a,b", "100%", "%09", "\t,\n%", "plain"):
            self.assertEqual(fo.decode_residue(fo.encode_residue(token)), token)

    def test_encoded_token_contains_no_separator(self):
        encoded = fo.encode_residue("a\tb,c\nd")
        for bad in ("\t", "\n", ","):
            self.assertNotIn(bad, encoded)


class CliRecordLayoutTests(unittest.TestCase):
    """Exactly five tab-separated fields, path last — a sixth breaks consumers."""

    def setUp(self):
        import shutil
        import tempfile

        self.tmp = tempfile.mkdtemp(prefix="fo_cli_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def _run(self, *paths):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = fo.main(list(paths))
        return rc, buf.getvalue().splitlines()

    def test_every_row_has_exactly_five_fields(self):
        good = self._write("t42_x.md", "---\nverifies: [t7]\n---\nbody\n")
        nofm = self._write("t43_y.md", "no frontmatter here\n")
        noid = self._write("weird_name.md", "---\nanchor: 5\n---\nbody\n")
        rc, rows = self._run(good, nofm, noid)
        self.assertEqual(rc, 0)
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(len(row.split("\t")), 5, "row must have 5 fields: %r" % row)

    def test_marker_rows_match_the_reference_shape(self):
        nofm = self._write("t43_y.md", "no frontmatter\n")
        noid = self._write("weird_name.md", "---\nanchor: 5\n---\nb\n")
        _, rows = self._run(nofm, noid)
        by_marker = {r.split("\t")[1]: r.split("\t") for r in rows}
        self.assertIn("NO_FRONTMATTER", by_marker)
        self.assertIn("UNPARSEABLE_ID", by_marker)
        for fields in by_marker.values():
            self.assertEqual(fields[0], "-")
            self.assertEqual(fields[2], "-")
            self.assertEqual(fields[3], "-")

    def test_empty_residue_renders_a_dash(self):
        good = self._write("t42_x.md", "---\nverifies: [t7]\n---\nb\n")
        _, (row,) = self._run(good)
        fields = row.split("\t")
        self.assertEqual(fields[0], "42")
        self.assertEqual(fields[1], fo.EXACT)
        self.assertEqual(fields[2], "7")
        self.assertEqual(fields[3], "-")
        self.assertEqual(fields[4], good)

    def test_residue_with_separators_round_trips_through_the_record(self):
        # A YAML scalar carrying a tab, a comma and a percent.
        task = self._write("t44_z.md", '---\nverifies: ["a\\tb,c%d"]\n---\nb\n')
        _, (row,) = self._run(task)
        fields = row.split("\t")
        self.assertEqual(len(fields), 5, "separator in residue must not add a field")
        self.assertEqual(fields[1], fo.UNKNOWN)
        self.assertEqual(fo.decode_residue(fields[3]), "a\tb,c%d")

    def test_path_is_the_last_field(self):
        good = self._write("t42_x.md", "---\nanchor: 9\n---\nb\n")
        _, (row,) = self._run(good)
        self.assertEqual(row.split("\t")[4], good)

    def test_no_arguments_is_a_usage_error(self):
        self.assertEqual(fo.main([]), 2)


class TaskIdFromPathTests(unittest.TestCase):
    def test_parent_and_child(self):
        self.assertEqual(fo.task_id_from_path("aitasks/t16_a.md"), "16")
        self.assertEqual(fo.task_id_from_path("aitasks/t16/t16_2_a.md"), "16_2")

    def test_unparseable(self):
        self.assertIsNone(fo.task_id_from_path("aitasks/notes.md"))


class LiveCorpusShapeTests(unittest.TestCase):
    """Shape only — never frozen counts, which drift with the corpus."""

    def _followups(self):
        import glob

        sys.path.insert(0, os.path.join(REPO_ROOT, ".aitask-scripts", "lib"))
        from task_yaml import parse_frontmatter

        found = []
        pattern = os.path.join(REPO_ROOT, "aitasks", "**", "t*.md")
        for path in glob.glob(pattern, recursive=True):
            if "/archived/" in path:
                continue
            with open(path, "r", encoding="utf-8") as handle:
                parsed = parse_frontmatter(handle.read())
            if parsed and parsed[0].get("followup_kind"):
                found.append(parsed[0])
        return found

    def test_qualities_partition_the_followup_population(self):
        followups = self._followups()
        if not followups:
            self.skipTest("no follow-up tasks in this corpus")
        counts = {fo.EXACT: 0, fo.TOPIC: 0, fo.UNKNOWN: 0}
        for metadata in followups:
            counts[fo.resolve(metadata)[1]] += 1
        # Mutually exclusive and exhaustive: no double counting.
        self.assertEqual(sum(counts.values()), len(followups))
        # Both evidenced classes are populated, so this is not vacuous.
        self.assertGreater(counts[fo.EXACT] + counts[fo.TOPIC], 0)

    def test_no_followup_resolves_to_exact_via_anchor_alone(self):
        for metadata in self._followups():
            if not metadata.get("verifies") and metadata.get("anchor"):
                self.assertNotEqual(fo.resolve(metadata)[1], fo.EXACT)


if __name__ == "__main__":
    unittest.main()
