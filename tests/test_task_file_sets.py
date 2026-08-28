#!/usr/bin/env python3
"""Framing and bucketing semantics for the batch task->file-set map (t1569_2).

The load-bearing tests here are the framing ones. A framing fault does not make
the whole-corpus byte-equality oracle *fail* -- it makes it pass over a corrupt
map, which is why these are written first (the plan's `pin_path_framing`
pre-phase mitigation) and why each carries a negative control:

- `test_separator_bytes_in_path_and_message_survive` is paired with
  `test_rejected_x1e_framing_misparses_the_same_fixture`, which proves the
  framing this design rejected actually mis-parses that same input. Without it
  the adversarial fixture could pass for the wrong reason.
- `test_only_the_first_path_token_is_newline_stripped` pins the exact strip.
  A blanket `.strip()` corrupts a path that legitimately begins or ends with a
  newline, and the corruption is silent.
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, ".aitask-scripts", "lib"))

import task_file_sets as tfs  # noqa: E402


SHA_A = b"a" * 40
SHA_B = b"b" * 40
SHA_C = b"c" * 40


def record(sha, ct, message, paths):
    """Build one record exactly as `git log -z --name-only --format=...` emits it.

    Note the newline before the first path: git puts it between the format
    output and the name list, and it lands on that token only.
    """
    blob = b"\x00" + sha + b"\x00" + ct + b"\x00" + message
    if paths:
        blob += b"\x00\n" + b"\x00".join(paths)
    blob += b"\x00"
    return blob


class FramingTests(unittest.TestCase):
    def test_basic_record_round_trips(self):
        raw = record(SHA_A, b"1700000000", b"feature: thing (t42)", [b"a.py", b"b.py"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.sha, "a" * 40)
        self.assertEqual(rec.committed_at, 1700000000)
        self.assertEqual(rec.task_ids, ["42"])
        self.assertEqual(rec.paths, ["a.py", "b.py"])

    def test_separator_bytes_in_path_and_message_survive(self):
        """A path AND a message carrying \\x1e/\\x1f must parse correctly.

        This is the adversarial fixture: it is exactly the input that breaks a
        \\x1e/\\x1f-delimited framing.
        """
        nasty_path = b"src/we\x1eird\x1fname.py"
        nasty_msg = b"bug: fix \x1e thing \x1f here (t99)"
        raw = record(SHA_A, b"1700000001", nasty_msg, [nasty_path, b"plain.py"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.task_ids, ["99"])
        # Correct, not merely non-empty: the byte-weird path is intact.
        self.assertEqual(rec.paths, ["src/we\x1eird\x1fname.py", "plain.py"])

    def test_rejected_x1e_framing_misparses_the_same_fixture(self):
        """Negative control for the test above.

        Proves the rejected framing genuinely mis-parses this input, so the
        adversarial fixture cannot pass for the wrong reason.
        """
        nasty_path = "src/we\x1eird\x1fname.py"
        nasty_msg = "bug: fix \x1e thing \x1f here (t99)"
        # The framing this design rejected: \x1e records, \x1f fields.
        stream = "\x1e" + "a" * 40 + "\x1f" + "1700000001" + "\x1f" + nasty_msg + "\x1f"
        stream += "\n" + nasty_path + "\x00plain.py\x00"

        records = [r for r in stream.split("\x1e") if r.strip("\x00\n ")]
        # One commit, shredded into three "records" by the \x1e bytes that the
        # path and the message happen to contain.
        self.assertEqual(len(records), 3)
        # No record recovers the real message, and none recovers the real path.
        for rec in records:
            fields = rec.split("\x1f")
            self.assertNotIn(nasty_msg, fields)
            self.assertNotIn(nasty_path, fields)

        # The NUL framing parses the identical logical commit correctly.
        (good,) = tfs.parse_log_stream(
            record(SHA_A, b"1700000001", nasty_msg.encode(), [nasty_path.encode(), b"plain.py"])
        )
        self.assertEqual(good.paths, [nasty_path, "plain.py"])
        self.assertEqual(good.task_ids, ["99"])

    def test_only_the_first_path_token_is_newline_stripped(self):
        """A path that legitimately starts/ends with a newline must survive."""
        raw = record(SHA_A, b"1700000002", b"chore: x (t7)", [b"first.py", b"\nodd.py", b"tail.py\n"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.paths, ["first.py", "\nodd.py", "tail.py\n"])

    def test_leading_newline_is_removed_from_the_first_path(self):
        raw = record(SHA_A, b"1700000003", b"chore: x (t7)", [b"only.py"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.paths, ["only.py"])

    def test_empty_commit_message_is_not_mistaken_for_a_record_marker(self):
        raw = record(SHA_A, b"1700000004", b"", [b"a.py"]) + record(
            SHA_B, b"1700000005", b"feature: y (t8)", [b"b.py"]
        )
        recs = tfs.parse_log_stream(raw)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0].task_ids, [])
        self.assertEqual(recs[1].task_ids, ["8"])

    def test_commit_touching_no_files(self):
        raw = record(SHA_A, b"1700000006", b"chore: empty (t9)", [])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.paths, [])

    def test_empty_stream_yields_no_records(self):
        self.assertEqual(tfs.parse_log_stream(b""), [])

    # --- fail-closed --------------------------------------------------------

    def test_bad_hash_raises_framing_error(self):
        raw = record(b"nothex" + b"0" * 34, b"1700000000", b"x (t1)", [b"a.py"])
        with self.assertRaises(tfs.FramingError) as ctx:
            tfs.parse_log_stream(raw)
        self.assertIn("40-hex", ctx.exception.detail)

    def test_bad_timestamp_raises_framing_error(self):
        raw = record(SHA_A, b"not-a-number", b"x (t1)", [b"a.py"])
        with self.assertRaises(tfs.FramingError) as ctx:
            tfs.parse_log_stream(raw)
        self.assertIn("timestamp", ctx.exception.detail)

    def test_stream_not_starting_with_a_marker_raises(self):
        with self.assertRaises(tfs.FramingError):
            tfs.parse_log_stream(b"garbage\x00" + record(SHA_A, b"1", b"x", [b"a.py"]))

    def test_framing_error_carries_the_token_index(self):
        raw = record(SHA_A, b"nope", b"x", [b"a.py"])
        with self.assertRaises(tfs.FramingError) as ctx:
            tfs.parse_log_stream(raw)
        self.assertIsInstance(ctx.exception.token_index, int)

    def test_truncated_header_alone_raises(self):
        raw = b"\x00" + SHA_A + b"\x00" + b"1700000000\x00"
        with self.assertRaises(tfs.FramingError) as ctx:
            tfs.parse_log_stream(raw)
        self.assertIn("incomplete record header", ctx.exception.detail)

    def test_valid_prefix_plus_truncation_does_not_emit_a_partial_map(self):
        """The dangerous shape: good records, then a header cut short.

        Returning the good ones would emit a map that looks complete and exits
        0 -- a short answer indistinguishable from a correct one.
        """
        raw = record(SHA_A, b"1700000000", b"feature: a (t1)", [b"a.py"])
        raw += b"\x00" + SHA_B + b"\x00" + b"1700000001\x00"
        with self.assertRaises(tfs.FramingError):
            tfs.parse_log_stream(raw)

    def test_stream_not_ending_on_a_nul_raises(self):
        """A cut mid-token: the final path would silently be a truncated one."""
        raw = record(SHA_A, b"1", b"x (t1)", [b"a.py"])[:-1]
        with self.assertRaises(tfs.FramingError) as ctx:
            tfs.parse_log_stream(raw)
        self.assertIn("truncated", ctx.exception.detail)

    def test_a_commit_touching_no_files_is_still_a_clean_end(self):
        """Guard the fix: the legitimate trailing NUL must NOT raise."""
        raw = record(SHA_A, b"1", b"chore: x (t1)", [b"a.py"])
        raw += record(SHA_B, b"2", b"chore: empty (t2)", [])
        recs = tfs.parse_log_stream(raw)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[1].paths, [])

    def test_non_bytes_input_is_rejected(self):
        with self.assertRaises(TypeError):
            tfs.parse_log_stream("a str, not bytes")


class MatchingTests(unittest.TestCase):
    def test_id_is_matched_anywhere_in_the_full_message(self):
        """The oracle greps the whole message, not just the subject."""
        raw = record(SHA_A, b"1", b"subject with no id\n\nbody mentions (t55)", [b"a.py"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.task_ids, ["55"])

    def test_comma_form_matches_neither_id(self):
        """`(t100, t101)` is not the literal `(t100)` -- the oracle matches neither."""
        raw = record(SHA_A, b"1", b"ait: link follow-ups (t100, t101)", [b"a.py"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.task_ids, [])

    def test_trailing_comma_form_matches_neither_id(self):
        raw = record(SHA_A, b"1", b"ait: record (t1529, mitigation not required)", [b"a.py"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.task_ids, [])

    def test_child_and_parent_ids_are_distinct(self):
        raw = record(SHA_A, b"1", b"x (t42_3)", [b"a.py"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.task_ids, ["42_3"])

    def test_multiple_distinct_ids_in_one_message(self):
        raw = record(SHA_A, b"1", b"x (t42) and (t43)", [b"a.py"])
        (rec,) = tfs.parse_log_stream(raw)
        self.assertEqual(rec.task_ids, ["42", "43"])


class BucketingTests(unittest.TestCase):
    def setUp(self):
        raw = (
            record(SHA_A, b"100", b"feature: parent work (t42)", [b"p.py"])
            + record(SHA_B, b"200", b"feature: child work (t42_1)", [b"c.py"])
            + record(SHA_C, b"300", b"chore: empty (t77)", [])
        )
        self.records = tfs.parse_log_stream(raw)
        self.own = tfs.bucket_own_paths(self.records)
        self.seen = tfs.matched_ids(self.records)

    def test_own_paths_do_not_include_children(self):
        self.assertEqual(self.own["42"], {"p.py"})

    def test_paths_for_unions_disk_children(self):
        kids = {"42": {"42_1"}}
        self.assertEqual(tfs.paths_for("42", self.own, kids), {"p.py", "c.py"})

    def test_paths_for_without_disk_children_excludes_them(self):
        """The divergence case: no on-disk child means the oracle sees only its own."""
        self.assertEqual(tfs.paths_for("42", self.own, {}), {"p.py"})

    def test_status_files(self):
        self.assertEqual(tfs.status_for("42", self.own, {}, self.seen), tfs.FILES)

    def test_status_no_files(self):
        self.assertEqual(tfs.status_for("77", self.own, {}, self.seen), tfs.NO_FILES)

    def test_status_unknown_history(self):
        self.assertEqual(
            tfs.status_for("999", self.own, {}, self.seen), tfs.UNKNOWN_HISTORY
        )

    def test_status_unknown_history_for_offdisk_child_parent(self):
        """A parent whose only work landed under a child that is gone from disk.

        The oracle cannot see it, so the honest answer is UNKNOWN_HISTORY --
        never NO_FILES, which would read as a false 'touched nothing'.
        """
        raw = record(SHA_A, b"100", b"feature: work (t1016_1)", [b"x.py"])
        recs = tfs.parse_log_stream(raw)
        own, seen = tfs.bucket_own_paths(recs), tfs.matched_ids(recs)
        self.assertEqual(tfs.status_for("1016", own, {}, seen), tfs.UNKNOWN_HISTORY)
        # ...and the recovered expansion does find it.
        recovered = tfs.children_from_commits(own)
        self.assertEqual(tfs.paths_for("1016", own, recovered), {"x.py"})
        self.assertEqual(tfs.status_for("1016", own, recovered, seen), tfs.FILES)

    def test_status_no_files_when_child_matched_but_touched_nothing(self):
        raw = record(SHA_A, b"1", b"chore: nothing (t5_1)", [])
        recs = tfs.parse_log_stream(raw)
        own, seen = tfs.bucket_own_paths(recs), tfs.matched_ids(recs)
        self.assertEqual(tfs.status_for("5", own, {"5": {"5_1"}}, seen), tfs.NO_FILES)

    def test_commit_index_carries_timestamps(self):
        index = tfs.commit_index(self.records)
        self.assertEqual(index["p.py"], [("a" * 40, 100, ["42"])])
        self.assertEqual(index["c.py"], [("b" * 40, 200, ["42_1"])])


class DiskChildrenTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.mkdtemp(prefix="tfs_kids_")
        self.addCleanup(__import__("shutil").rmtree, self.tmp, ignore_errors=True)

    def _touch(self, rel):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()

    def test_active_and_archived_children_are_both_found(self):
        self._touch("aitasks/t42/t42_1_alpha.md")
        self._touch("aitasks/archived/t42/t42_2_beta.md")
        kids = tfs.children_from_disk(self.tmp)
        self.assertEqual(kids["42"], {"42_1", "42_2"})

    def test_a_stray_child_of_another_parent_is_not_claimed(self):
        self._touch("aitasks/t42/t99_1_stray.md")
        self.assertEqual(tfs.children_from_disk(self.tmp), {})

    def test_parent_file_is_not_a_child(self):
        self._touch("aitasks/t42_parent.md")
        self.assertEqual(tfs.children_from_disk(self.tmp), {})

    def test_no_children_yields_empty_map(self):
        self.assertEqual(tfs.children_from_disk(self.tmp), {})


class RecoveredExpansionTests(unittest.TestCase):
    def test_children_from_commits_recovers_offdisk_children(self):
        own = {"1016_1": {"a.py"}, "1016_2": {"b.py"}, "42": {"c.py"}}
        self.assertEqual(tfs.children_from_commits(own)["1016"], {"1016_1", "1016_2"})

    def test_children_from_commits_ignores_parent_only_ids(self):
        self.assertNotIn("42", tfs.children_from_commits({"42": {"c.py"}}))


if __name__ == "__main__":
    unittest.main()
