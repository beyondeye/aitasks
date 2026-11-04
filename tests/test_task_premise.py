"""Premise-staleness verdict core tests (t1663_1).

Pure: no git, no subprocess, no filesystem. Every input is a frozen list of
interchange rows, exactly the shape `aitask_premise_stale.sh` hands the core.

The load-bearing class is RowIntegrityTests: FRESH is a positive claim, so a
dropped, mangled or symbolic row must never be able to produce it. Its mutation
sweep carries a negative control (the unmutated sets DO read FRESH), without
which "never FRESH" would pass vacuously.

Run: ``python3 -m unittest tests.test_task_premise -v``
"""

import hashlib
import os
import sys
import types
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))

import roadmap_premise as rp  # noqa: E402
import task_premise as tp  # noqa: E402

BASE_SHA = "a" * 40
REV = "b" * 40
C1 = "c" * 40
C2 = "d" * 40
TS = "2026-01-01 10:00"


def base_rows(tier="A", n_paths=1, n_origins=0, sha=BASE_SHA, reason=""):
    return ["REV:" + REV, "BASE:%s|%s|%s" % (sha, TS, reason),
            "TIER:%s|%d|%d" % (tier, n_paths, n_origins)]


def decision(rows):
    return tp.check(rows).decision


def evidence(result):
    return [l for l in result.lines if l.split(":", 1)[0] in ("CHANGED", "DELETED", "UNKNOWN")]


class PublicSurfaceTests(unittest.TestCase):
    """`__all__` is the substitution contract with t1655."""

    def test_public_names_are_exactly_all(self):
        public = {name for name, value in vars(tp).items()
                  if not name.startswith("_")
                  and not isinstance(value, types.ModuleType)
                  and name not in ("dataclass", "field")}
        self.assertEqual(sorted(public), sorted(tp.__all__))

    def test_the_two_functions_t1655_consumes(self):
        self.assertTrue(callable(tp.baseline_for))
        self.assertTrue(callable(tp.check))

    def test_vocabularies_are_closed_and_disjoint_where_it_matters(self):
        self.assertEqual(len(set(tp.REASONS)), len(tp.REASONS))
        self.assertEqual(tp.DECISIONS, ("FRESH", "ASK_STALE", "SKIP"))
        for state in tp.PATH_STATES:
            self.assertTrue(state == "ok" or state == "deleted" or state in tp.PATH_REASONS)


class VocabularyDriftGuardTests(unittest.TestCase):
    """Post-phase `protocol_vocabulary_drift_guard`."""

    def test_the_three_vocabularies_are_disjoint(self):
        rows, lines, fields = set(tp.ROW_PREFIXES), set(tp.LINE_PREFIXES), set(tp.FIELD_PREFIXES)
        self.assertEqual(rows & lines, set())
        self.assertEqual(rows & fields, set())
        self.assertEqual(lines & fields, set())

    def test_task_fields_emits_nothing_outside_field_prefixes(self):
        for meta in (None, {}, {"premise_baseline": "x", "file_references": ["a", {"b": 1}]}):
            for line in tp.task_fields(meta):
                self.assertIn(line.split(":", 1)[0], tp.FIELD_PREFIXES, line)

    def test_the_parser_accepts_nothing_outside_row_prefixes(self):
        good = base_rows() + ["PATH:a.py|ok|0"]
        self.assertEqual(decision(good), tp.FRESH)
        for bogus in ("BASELINE:%s|x" % BASE_SHA, "CHANGED:a.py|1|2", "NOPE:x", "no colon"):
            result = tp.check(good + [bogus])
            self.assertEqual((result.decision, result.reason), (tp.SKIP, "engine_error"), bogus)

    def test_the_emitter_produces_nothing_outside_line_prefixes(self):
        inputs = [
            base_rows() + ["PATH:a.py|ok|0"],
            base_rows(n_paths=3) + ["PATH:a.py|ok|1", "LOG:a.py|%s|7" % C1,
                                    "PATH:b.py|deleted", "GONE:b.py|8|x",
                                    "PATH:c.py|absent_at_baseline"],
            ["BASE:||no_stored_baseline", "TIER:NONE|0|0"],
            ["garbage"],
        ]
        for rows in inputs:
            for line in tp.check(rows).lines:
                self.assertIn(line.split(":", 1)[0], tp.LINE_PREFIXES, line)


class EncodingTests(unittest.TestCase):
    HOSTILE = ["%", "%7C", "|", "a\nb", "c\rd", "%0A", "%0D", "a%25b", "tail\n", "\n", "plain.py",
               "x\nTASKFILES:42|keep.py"]

    def test_round_trip_is_lossless(self):
        for value in self.HOSTILE:
            enc = tp.encode_field(value)
            self.assertNotIn("\n", enc)
            self.assertNotIn("\r", enc)
            self.assertNotIn("|", enc)
            self.assertEqual(tp.decode_field(enc), value, repr(value))

    def test_encoding_is_injective_over_the_corpus(self):
        encoded = [tp.encode_field(v) for v in self.HOSTILE]
        self.assertEqual(len(set(encoded)), len(set(self.HOSTILE)))

    def test_it_extends_the_shared_vocab_rule(self):
        import parallel_admission_vocab as vocab
        for value in ("a|b%c", "plain"):
            self.assertEqual(tp.encode_field(value), vocab.encode_path(value))


class BaselineTests(unittest.TestCase):
    """Carried over from tests/test_roadmap_premise.py -- semantics unchanged."""

    @staticmethod
    def commit(path, sha, ct, ids):
        return "COMMIT:%s|%s|%d|%s" % (path, sha, ct, ",".join(ids))

    def test_newest_landing_commit_wins(self):
        rows = [self.commit("a.py", "sha1", 100, ["100"]),
                self.commit("b.py", "sha2", 200, ["100"])]
        self.assertEqual(tp.baseline_for(["100"], rows).sha, "sha2")

    def test_a_later_task_data_commit_does_not_move_the_baseline(self):
        rows = [self.commit("code.py", "landing", 100, ["100"]),
                self.commit("aitasks/t100_x.md", "meta", 500, ["100"])]
        self.assertEqual(tp.baseline_for(["100"], rows).sha, "landing")

    def test_metadata_only_is_not_unknown_history(self):
        rows = [self.commit("aiplans/p100.md", "meta", 100, ["100"])]
        self.assertEqual(tp.baseline_for(["100"], rows).reason, "metadata_only")
        rows = [self.commit("code.py", "sha", 100, ["999"])]
        self.assertEqual(tp.baseline_for(["100"], rows).reason, "unknown_history")

    def test_no_origin(self):
        self.assertEqual(tp.baseline_for([], []).reason, "no_origin")

    def test_data_prefixes_are_a_parameter(self):
        rows = [self.commit("code.py", "landing", 100, ["100"]),
                self.commit("mytasks/t100.md", "meta", 200, ["100"])]
        self.assertEqual(tp.baseline_for(["100"], rows).sha, "meta")
        self.assertEqual(tp.baseline_for(["100"], rows, data_prefixes=("mytasks/",)).sha,
                         "landing")

    def test_ties_break_deterministically(self):
        rows = [self.commit("a.py", "bbb", 100, ["100"]),
                self.commit("b.py", "aaa", 100, ["100"])]
        self.assertEqual(tp.baseline_for(["100"], rows).sha,
                         tp.baseline_for(["100"], list(reversed(rows))).sha)


class VerdictTests(unittest.TestCase):
    def test_unchanged_is_fresh(self):
        result = tp.check(base_rows() + ["PATH:a.py|ok|0"])
        self.assertEqual(result.decision, tp.FRESH)
        self.assertEqual(result.lines[1], "CHECKED:" + REV)

    def test_changed_is_ask_stale_with_culprits(self):
        result = tp.check(base_rows() + ["PATH:a.py|ok|2", "LOG:a.py|%s|20" % C1,
                                         "LOG:a.py|%s|10_2" % C2])
        self.assertEqual(result.decision, tp.ASK_STALE)
        self.assertEqual(evidence(result), ["CHANGED:a.py|2|10_2,20"])

    def test_deleted_is_ask_stale(self):
        result = tp.check(base_rows() + ["PATH:a.py|deleted", "GONE:a.py|30|chore: drop"])
        self.assertEqual(evidence(result), ["DELETED:a.py|30|chore: drop"])

    def test_deleted_without_gone_keeps_the_deletion(self):
        result = tp.check(base_rows() + ["PATH:a.py|deleted"])
        self.assertEqual(evidence(result), ["DELETED:a.py|unknown|"])

    def test_unknown_moves_the_verdict_exactly_like_changed(self):
        for state in ("absent_at_baseline", "history_unavailable", "invalid_reference",
                      "no_index_history"):
            result = tp.check(base_rows(n_paths=2) + ["PATH:a.py|ok|0", "PATH:b.py|%s" % state])
            self.assertEqual(result.decision, tp.ASK_STALE, state)
            self.assertEqual(evidence(result), ["UNKNOWN:b.py|%s" % state])

    def test_history_unavailable_is_never_unchanged(self):
        self.assertEqual(decision(base_rows() + ["PATH:a.py|history_unavailable"]),
                         tp.ASK_STALE)

    def test_empty_scope_is_skip_not_fresh_not_ask_stale(self):
        result = tp.check(base_rows(tier="NONE", n_paths=0))
        self.assertEqual((result.decision, result.reason), (tp.SKIP, "empty_scope"))
        self.assertEqual(result.lines[2], "FINGERPRINT:NONE")

    def test_empty_scope_ignores_origin_unknowns(self):
        rows = base_rows(tier="B", n_paths=0, n_origins=1) + ["ORIGIN:42|UNKNOWN_HISTORY"]
        result = tp.check(rows)
        self.assertEqual((result.decision, result.reason), (tp.SKIP, "empty_scope"))

    def test_origin_unknown_history_drives_ask_stale_when_a_path_was_checked(self):
        rows = base_rows(tier="B", n_paths=1, n_origins=2) + [
            "ORIGIN:42|FILES", "ORIGIN:43|UNKNOWN_HISTORY", "PATH:a.py|ok|0"]
        result = tp.check(rows)
        self.assertEqual(result.decision, tp.ASK_STALE)
        self.assertEqual(evidence(result), ["UNKNOWN:43|unknown_history"])

    def test_every_precondition_reason_is_skip_with_that_reason(self):
        for reason in ("no_origin", "unknown_history", "metadata_only", "no_stored_baseline",
                       "invalid_baseline", "history_rewritten", "scope_error",
                       "invalid_frontmatter", "not_a_git_repo"):
            result = tp.check(base_rows(tier="NONE", n_paths=0, reason=reason))
            self.assertEqual((result.decision, result.reason), (tp.SKIP, reason))
            self.assertEqual(result.lines[2], "FINGERPRINT:NONE")

    def test_checked_is_none_exactly_when_no_rev_row(self):
        no_rev = tp.check(["BASE:||no_stored_baseline", "TIER:NONE|0|0"])
        self.assertEqual(no_rev.lines[1], "CHECKED:NONE")
        with_rev = tp.check(base_rows(tier="NONE", n_paths=0, reason="history_rewritten"))
        self.assertEqual(with_rev.lines[1], "CHECKED:" + REV)
        self.assertEqual(with_rev.lines[0], "BASELINE:%s|%s" % (BASE_SHA, TS))

    def test_a_fresh_verdict_without_rev_is_impossible(self):
        rows = ["BASE:%s|%s|" % (BASE_SHA, TS), "TIER:A|1|0", "PATH:a.py|ok|0"]
        self.assertEqual(tp.check(rows).reason, "engine_error")


class RowIntegrityTests(unittest.TestCase):
    """Review finding 10: partial parsing must never produce an all-clear."""

    def test_mixed_valid_and_malformed_log_rows(self):
        rows = base_rows(n_paths=2) + ["PATH:a.py|ok|1", "LOG:a.py|%s|20" % C1,
                                       "PATH:b.py|ok|1", "LOG:b.py|notasha|21"]
        result = tp.check(rows)
        self.assertEqual(result.decision, tp.ASK_STALE)
        self.assertEqual(evidence(result), ["CHANGED:a.py|1|20", "UNKNOWN:b.py|malformed_row"])

    def test_a_dropped_log_row_is_caught_by_the_attested_count(self):
        result = tp.check(base_rows() + ["PATH:a.py|ok|1"])
        self.assertEqual(evidence(result), ["UNKNOWN:a.py|malformed_row"])

    def test_an_extra_log_row_is_caught_too(self):
        result = tp.check(base_rows() + ["PATH:a.py|ok|0", "LOG:a.py|%s|20" % C1])
        self.assertEqual(evidence(result), ["UNKNOWN:a.py|malformed_row"])

    def test_scope_breaking_rows_are_engine_error(self):
        cases = {
            "malformed PATH": base_rows() + ["PATH:a.py"],
            "PATH bad state": base_rows() + ["PATH:a.py|fine"],
            "PATH raw newline-less but bad escape": base_rows() + ["PATH:a%zz|ok|0"],
            "TIER count mismatch": base_rows(n_paths=2) + ["PATH:a.py|ok|0"],
            "unknown prefix": base_rows() + ["PATH:a.py|ok|0", "WHAT:x"],
            "duplicate BASE": base_rows() + ["PATH:a.py|ok|0", "BASE:%s||" % BASE_SHA],
            "duplicate REV": base_rows() + ["PATH:a.py|ok|0", "REV:" + REV],
            "unparseable ORIGIN": base_rows(tier="B", n_origins=1) + ["ORIGIN:x|FILES",
                                                                      "PATH:a.py|ok|0"],
            "non-hex REV": ["REV:HEAD"] + base_rows()[1:] + ["PATH:a.py|ok|0"],
            "duplicate PATH": base_rows(n_paths=2) + ["PATH:a.py|ok|0", "PATH:a.py|ok|0"],
            "orphan LOG": base_rows() + ["PATH:a.py|ok|0", "LOG:z.py|%s|1" % C1],
            "unknown BASE reason": base_rows(reason="because") + ["PATH:a.py|ok|0"],
            "missing TIER": base_rows()[:2] + ["PATH:a.py|ok|0"],
            "missing BASE": [base_rows()[0], base_rows()[2], "PATH:a.py|ok|0"],
        }
        for name, rows in cases.items():
            result = tp.check(rows)
            self.assertEqual((result.decision, result.reason), (tp.SKIP, "engine_error"), name)

    def test_symbolic_baselines_are_invalid_baseline(self):
        for sha in ("HEAD", "main", "abc1234", "HEAD~1", BASE_SHA + "^", ""):
            rows = ["REV:" + REV, "BASE:%s|%s|" % (tp.encode_field(sha), TS), "TIER:A|1|0",
                    "PATH:a.py|ok|0"]
            result = tp.check(rows)
            self.assertEqual((result.decision, result.reason), (tp.SKIP, "invalid_baseline"),
                             sha)
            self.assertEqual(result.lines[0], "BASELINE:NONE")

    def test_an_uppercase_full_sha_is_accepted_and_normalized(self):
        rows = ["REV:" + REV, "BASE:%s|%s|" % ("A" * 40, TS), "TIER:A|1|0", "PATH:a.py|ok|0"]
        result = tp.check(rows)
        self.assertEqual(result.decision, tp.FRESH)
        self.assertTrue(result.lines[0].startswith("BASELINE:" + "a" * 40))

    def test_non_utf8_input_is_engine_error_not_a_crash(self):
        class Raising:
            def __iter__(self):
                yield "REV:" + REV
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")
        self.assertEqual(tp.check(Raising()).reason, "engine_error")

    # --- the mutation sweep ---

    FRESH_A = base_rows(n_paths=2) + ["PATH:a.py|ok|0", "PATH:b%7Cc.py|ok|0"]
    FRESH_B = base_rows(tier="B", n_paths=2, n_origins=2) + [
        "ORIGIN:42|FILES", "ORIGIN:43|NO_FILES", "PATH:a.py|ok|0", "PATH:lib%0Ax.py|ok|0"]
    # A set whose only evidence is one change: removing that evidence must not
    # make it FRESH either.
    STALE_A = base_rows(n_paths=1) + ["PATH:a.py|ok|1", "LOG:a.py|%s|20" % C1]

    @staticmethod
    def _mutations(line):
        prefix, _, rest = line.partition(":")
        fields = rest.split("|")
        out = {
            "drop": None,
            "duplicate": [line, line],
            "truncate-last-field": [prefix + ":" + "|".join(fields[:-1])],
            "garble-prefix": [prefix.lower() + ":" + rest],
            "stray-field": [line + "|extra"],
            "count-to-x": [prefix + ":" + "|".join("x" if f.isdigit() else f for f in fields)],
            "sha-to-HEAD": [prefix + ":" + "|".join("HEAD" if len(f) in (40, 64) else f
                                                    for f in fields)],
        }
        return out

    def _sweep(self, rows, expected_unmutated):
        self.assertEqual(decision(rows), expected_unmutated, "negative control")
        checked = 0
        for i, line in enumerate(rows):
            for name, replacement in self._mutations(line).items():
                mutated = rows[:i] + (replacement or []) + rows[i + 1:]
                if mutated == rows:
                    continue
                checked += 1
                self.assertNotEqual(decision(mutated), tp.FRESH,
                                    "row %d (%s) mutated by %s" % (i, line, name))
        self.assertGreater(checked, 20)

    def test_sweep_tier_a_fresh(self):
        self._sweep(self.FRESH_A, tp.FRESH)

    def test_sweep_tier_b_fresh(self):
        self._sweep(self.FRESH_B, tp.FRESH)

    def test_sweep_stale_never_becomes_fresh(self):
        self._sweep(self.STALE_A, tp.ASK_STALE)


class ProtocolTests(unittest.TestCase):
    ROWS = base_rows(n_paths=3) + ["PATH:a.py|ok|1", "LOG:a.py|%s|7" % C1,
                                   "PATH:b.py|deleted", "GONE:b.py|8|feat: x|y",
                                   "PATH:c.py|absent_at_baseline"]

    def test_fixed_line_order(self):
        lines = tp.check(self.ROWS).lines
        self.assertEqual([l.split(":", 1)[0] for l in lines],
                         ["BASELINE", "CHECKED", "FINGERPRINT", "FILES", "CHANGED",
                          "DELETED", "UNKNOWN", "DISPLAY", "DECISION"])

    def test_same_input_twice_is_byte_identical(self):
        self.assertEqual(tp.check(self.ROWS).lines, tp.check(list(self.ROWS)).lines)

    def test_a_real_change_changes_the_output(self):
        fresh = tp.check(base_rows() + ["PATH:a.py|ok|0"]).lines
        stale = tp.check(base_rows() + ["PATH:a.py|ok|1", "LOG:a.py|%s|7" % C1]).lines
        self.assertNotEqual(fresh, stale)

    def test_hostile_paths_stay_encoded_and_one_line(self):
        hostile = "x\nTASKFILES:42|keep.py"
        rows = base_rows() + ["PATH:%s|ok|1" % tp.encode_field(hostile),
                              "LOG:%s|%s|7" % (tp.encode_field(hostile), C1)]
        result = tp.check(rows)
        self.assertEqual(evidence(result), ["CHANGED:%s|1|7" % tp.encode_field(hostile)])
        for line in result.lines:
            self.assertNotIn("\n", line)
        self.assertIn("x%0ATASKFILES:42|keep.py", result.lines[-2])  # DISPLAY: raw but one line

    def test_rows_with_trailing_newlines_parse(self):
        rows = [r + "\n" for r in base_rows() + ["PATH:a.py|ok|0"]] + ["\n"]
        self.assertEqual(decision(rows), tp.FRESH)


class FingerprintTests(unittest.TestCase):
    def fp(self, **kw):
        args = dict(baseline_sha=BASE_SHA, tier="A", paths=["a.py", "b.py"], origin_ids=[])
        args.update(kw)
        return tp.fingerprint(**args)

    def test_identical_inputs_identical_digest(self):
        self.assertEqual(self.fp(), self.fp(paths=["b.py", "a.py"]))
        self.assertRegex(self.fp(), r"^[0-9a-f]{16}$")

    def test_each_tuple_element_changes_the_digest(self):
        base = self.fp()
        for kw in ({"baseline_sha": C1}, {"tier": "B"}, {"paths": ["a.py"]},
                   {"paths": ["a.py", "c.py"]}, {"origin_ids": ["42"]}):
            self.assertNotEqual(self.fp(**kw), base, kw)

    def test_list_boundaries_are_unambiguous(self):
        """Review regression: comma-joined lists made ["a,b"] collide with ["a", "b"]."""
        self.assertNotEqual(self.fp(paths=["a,b"]), self.fp(paths=["a", "b"]))
        self.assertNotEqual(self.fp(paths=["a|b"]), self.fp(paths=["a", "b"]))
        self.assertNotEqual(self.fp(paths=['a","b']), self.fp(paths=["a", "b"]))
        self.assertNotEqual(self.fp(origin_ids=["1,2"]), self.fp(origin_ids=["1", "2"]))
        self.assertNotEqual(self.fp(paths=["a"], origin_ids=["b"]),
                            self.fp(paths=["a", "b"], origin_ids=[]))

    def test_the_comma_collision_through_check(self):
        one = tp.check(base_rows(n_paths=1) + ["PATH:a,b|ok|0"])
        two = tp.check(base_rows(n_paths=2) + ["PATH:a|ok|0", "PATH:b|ok|0"])
        self.assertEqual((one.decision, two.decision), (tp.FRESH, tp.FRESH))
        self.assertNotEqual(one.fingerprint, two.fingerprint)

    def test_a_non_utf8_path_still_fingerprints(self):
        self.assertRegex(self.fp(paths=["bad\udcff.py"]), r"^[0-9a-f]{16}$")

    def test_checked_rev_and_timestamp_do_not_move_it(self):
        one = tp.check(["REV:" + REV, "BASE:%s|%s|" % (BASE_SHA, TS), "TIER:A|1|0",
                        "PATH:a.py|ok|0"])
        two = tp.check(["REV:" + C2, "BASE:%s|%s|" % (BASE_SHA, "2027-05-05 05:05"),
                        "TIER:A|1|0", "PATH:a.py|ok|0"])
        self.assertEqual(one.fingerprint, two.fingerprint)
        self.assertIsNotNone(one.fingerprint)


class TaskFieldsTests(unittest.TestCase):
    """The producer's scope reader: YAML entries, never a comma split."""

    @staticmethod
    def parse(frontmatter):
        import task_yaml
        parsed = task_yaml.parse_frontmatter("---\n%s\n---\nbody\n" % frontmatter)
        return parsed[0] if parsed else None

    def test_a_quoted_comma_entry_stays_one_path(self):
        lines = tp.task_fields(self.parse('file_references: ["a,b.py", lib/x.py:3-5]'))
        self.assertEqual(lines, ("FIELD_BASELINE:", "FIELD_REF:a,b.py",
                                 "FIELD_REF:lib/x.py:3-5", "FIELD_END:2"))

    def test_baseline_is_read_and_encoded(self):
        lines = tp.task_fields(self.parse("premise_baseline: %s @ %s" % (BASE_SHA, TS)))
        self.assertEqual(lines[0], "FIELD_BASELINE:%s @ %s" % (BASE_SHA, TS))
        self.assertEqual(lines[-1], "FIELD_END:0")

    def test_hostile_entries_are_encoded_one_per_line(self):
        lines = tp.task_fields({"file_references": ["a|b", "c\nd", "%7C"]})
        self.assertEqual(lines[1:], ("FIELD_REF:a%7Cb", "FIELD_REF:c%0Ad", "FIELD_REF:%257C",
                                     "FIELD_END:3"))

    def test_a_bare_scalar_is_one_entry_and_a_mapping_is_a_bad_ref(self):
        self.assertEqual(tp.task_fields({"file_references": "a.py"})[1], "FIELD_REF:a.py")
        lines = tp.task_fields({"file_references": [{"x": 1}, "b.py"]})
        self.assertTrue(lines[1].startswith("FIELD_BADREF:"))
        self.assertEqual(lines[-1], "FIELD_END:2")

    def test_non_string_entries_are_bad_refs_never_dropped_or_coerced(self):
        """Review regression: YAML turns unquoted null / on / 010 into None / True / 8."""
        import datetime
        meta = self.parse("file_references: [good.py, null, on, 010, 1.5, 2026-01-01]")
        self.assertEqual(meta["file_references"][1:4], [None, True, 8])   # the YAML premise
        lines = tp.task_fields(meta)
        self.assertEqual(lines[1], "FIELD_REF:good.py")
        bad = [l for l in lines if l.startswith("FIELD_BADREF:")]
        self.assertEqual(len(bad), 5, lines)
        self.assertEqual(lines[-1], "FIELD_END:6")
        self.assertNotIn("FIELD_REF:True", lines)
        self.assertNotIn("FIELD_REF:8", lines)
        self.assertIsInstance(meta["file_references"][5], datetime.date)

    def test_quoted_strings_are_the_control(self):
        lines = tp.task_fields(self.parse('file_references: ["on", "010", "null"]'))
        self.assertEqual(lines[1:], ("FIELD_REF:on", "FIELD_REF:010", "FIELD_REF:null",
                                     "FIELD_END:3"))

    def test_a_string_and_a_non_string_with_the_same_text_stay_distinct(self):
        lines = tp.task_fields(self.parse('file_references: ["True", true]'))
        self.assertEqual(lines[1], "FIELD_REF:True")
        self.assertTrue(lines[2].startswith("FIELD_BADREF:"))
        self.assertNotEqual(lines[2][len("FIELD_BADREF:"):], "True")

    def test_nul_never_crosses_into_the_protocol(self):
        """Review regression: bash `$( )` would turn "a\\0.py" into "a.py"."""
        meta = self.parse('premise_baseline: "%s\\0 @ %s"\nfile_references: ["a\\0.py", "\\0"]'
                          % (BASE_SHA, TS))
        self.assertIn("\x00", meta["file_references"][0])                # the YAML premise
        lines = tp.task_fields(meta)
        for line in lines:
            self.assertNotIn("\x00", line)
        self.assertTrue(lines[0].startswith("FIELD_BASELINE:<invalid premise_baseline:"))
        self.assertEqual([l.split(":", 1)[0] for l in lines[1:]],
                         ["FIELD_BADREF", "FIELD_BADREF", "FIELD_END"])

    def test_a_non_string_baseline_is_a_diagnostic_not_a_sha(self):
        for value in (12345, True, ["x"]):
            line = tp.task_fields({"premise_baseline": value})[0]
            self.assertTrue(line.startswith("FIELD_BASELINE:<invalid premise_baseline:"), line)

    def test_no_parseable_frontmatter_is_invalid(self):
        self.assertEqual(tp.task_fields(None), ("FIELD_INVALID:frontmatter",))
        self.assertEqual(tp.task_fields(["not", "a", "mapping"]), ("FIELD_INVALID:frontmatter",))


class SubstitutabilityTests(unittest.TestCase):
    """t1655: the row shape must absorb roadmap_premise's inputs.

    A test-local adapter turns the roadmap's COMMIT: index into interchange rows;
    the core must reproduce the roadmap's verdict on every fixture.
    """

    @staticmethod
    def hexify(name):
        return hashlib.sha1(name.encode()).hexdigest()

    def adapt(self, origin_ids, origin_paths, commit_lines):
        base = tp.baseline_for(origin_ids, commit_lines)
        if not base.resolved:
            return ["BASE:||%s" % base.reason, "TIER:NONE|0|0"]
        by_path = {}
        for line in commit_lines:
            path, sha, ct, ids = line[len("COMMIT:"):].rsplit("|", 3)
            by_path.setdefault(path, []).append((self.hexify(sha), int(ct), ids))
        paths = sorted(set(origin_paths))
        rows = ["REV:" + REV, "BASE:%s|%d|" % (self.hexify(base.sha), base.committed_at),
                "TIER:B|%d|0" % len(paths)]
        for p in paths:
            seen = by_path.get(p)
            key = tp.encode_field(p)
            if not seen:
                rows.append("PATH:%s|no_index_history" % key)
            elif not any(ct <= base.committed_at for _, ct, _ in seen):
                rows.append("PATH:%s|absent_at_baseline" % key)
            else:
                later = [(s, ids) for s, ct, ids in seen if ct > base.committed_at]
                rows.append("PATH:%s|ok|%d" % (key, len(later)))
                rows.extend("LOG:%s|%s|%s" % (key, s, ids) for s, ids in later)
        return rows

    @staticmethod
    def commit(path, sha, ct, ids):
        return "COMMIT:%s|%s|%d|%s" % (path, sha, ct, ",".join(ids))

    def test_the_roadmap_fixtures_reproduce(self):
        c = self.commit
        fixtures = [
            (["100"], ["a.py"], [c("a.py", "s1", 100, ["100"])]),
            (["100"], ["code.py"], [c("code.py", "landing", 100, ["100"]),
                                    c("code.py", "other", 200, ["777"]),
                                    c("aitasks/t100_x.md", "meta", 500, ["100"])]),
            (["100"], ["a.py", "never.py"], [c("a.py", "s1", 100, ["100"])]),
            (["100"], ["later.py"], [c("a.py", "s1", 100, ["100"]),
                                     c("later.py", "s2", 200, ["777"])]),
            (["100"], [], [c("code.py", "landing", 100, ["100"])]),
            ([], ["a.py"], []),
            (["100"], ["code.py"], [c("aiplans/p100.md", "meta", 100, ["100"])]),
            (["100"], ["a|b%c.py"], [c("a|b%c.py", "s1", 100, ["100"]),
                                     c("a|b%c.py", "s2", 200, ["777"])]),
        ]
        for origin_ids, paths, commits in fixtures:
            want = rp.check(origin_ids, paths, commits)
            got = tp.check(self.adapt(origin_ids, paths, commits))
            self.assertEqual(got.decision, want.decision, (origin_ids, paths))
            self.assertEqual(got.reason, want.reason, (origin_ids, paths))
            self.assertEqual(sorted(p for p, _, _ in got.changed),
                             sorted(p for p, _, _ in want.changed))
            self.assertEqual(sorted(got.unknown), sorted(want.unknown))


if __name__ == "__main__":
    unittest.main()
