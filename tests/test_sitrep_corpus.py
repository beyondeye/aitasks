#!/usr/bin/env python3
"""Unit tests for the harvest confidence check and review corpus (t2175_6).

Covers `sitrep_harvest.assess` / `classify` (every reason code with its line
range, per-OCCURRENCE pairing, the negatives that must never fire), the joined
banner grammar, the receipt certification shared with agent_sessions, the case
file formats, the raw-retention guards, the dry replay (writes nothing), the
excerpt bounds and the triage fact `REVIEW_CASE:`.

The end-to-end flows (real writer, real session store) are in
tests/test_sitrep_corpus.sh.

Run: python3 -m unittest tests.test_sitrep_corpus
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / ".aitask-scripts"))
sys.path.insert(0, str(REPO / ".aitask-scripts" / "lib"))

import agent_sessions  # noqa: E402
import sitrep_cli  # noqa: E402
import sitrep_corpus as C  # noqa: E402
import sitrep_harvest as H  # noqa: E402
import sitrep_todo as st  # noqa: E402

FIX = REPO / "tests" / "fixtures" / "sitrep_harvest"
STORE_FIX = REPO / "tests" / "fixtures" / "sitrep" / "store"


def text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def reasons(t: str, piped: bool = False) -> list:
    return H.classify(t.encode("utf-8"), piped)[1]


def codes(t: str, piped: bool = False) -> list:
    return [r.code for r in reasons(t, piped)]


MARKER_A = ("● Bash(./.aitask-scripts/aitask_sitrep_harvest.sh banner --task 76)\n"
            "  ⎿  HARVEST_RUN:aaaaaaaaaaaaaaaa\n\n"
            "● The t76 run ended; its banner never rendered.\n\n"
            "❯ next\n\n")


class NegativeTests(unittest.TestCase):
    """Input that is reliable or legitimately empty never queues a review."""

    def test_existing_fixtures_fire_nothing_but_the_cut_off_banner(self):
        for f in sorted(FIX.glob("*.txt")):
            got = codes(f.read_text(encoding="utf-8"))
            if f.name == "truncated_banner.txt":
                self.assertEqual(got, ["banner_incomplete"], f.name)
            else:
                self.assertEqual(got, [], f.name)

    def test_the_piped_form_is_reliable(self):
        self.assertEqual(codes(text("pick_complete_piped.txt"), piped=True), [])

    def test_no_banner_at_all_is_not_a_reason(self):
        # An agent frozen mid-work: prose, tool calls, no banner, no marker.
        t = "● Reading the code.\n● Bash(ls)\n  ⎿  a b c\n\n● Still working.\n"
        self.assertEqual(H.classify(t.encode(), False), ("empty", []))

    def test_an_unresolved_cross_repo_follow_up_is_not_a_reason(self):
        self.assertIn("xproj#t2171", text("pick_complete_followups.txt"))
        self.assertEqual(codes(text("pick_complete_followups.txt")), [])

    def test_a_draft_created_line_is_not_a_reason(self):
        t = "  ⎿  Created: aitasks/new/draft_20261101_1200_x.md\n"
        self.assertEqual(codes(t), [])

    def test_a_blank_pipe_is_empty(self):
        self.assertEqual(H.classify(b"\n  \n", True), ("empty", []))


class TriggerTests(unittest.TestCase):
    def test_incomplete_banner_carries_its_lines(self):
        (r,) = reasons(text("truncated_banner.txt"))
        self.assertEqual((r.code, r.detail), ("banner_incomplete", "t88"))
        self.assertIn("aitask workflow complete",
                      text("truncated_banner.txt").split("\n")[r.a - 1])

    def test_bad_follow_up_token_and_the_good_one_survives(self):
        t = text("pick_complete_nofollowups.txt").replace(
            "follow-ups created: none", "follow-ups created: t154, t155.")
        (r,) = reasons(t)
        self.assertEqual((r.code, r.detail), ("bad_followup", "t155."))
        b = H.parse_banners(t.split("\n"))[0]
        self.assertEqual(b.followups, ["t154"])

    def test_passage_truncated(self):
        t = ("● long\n" + "\n".join("  " + "x" * 400 for _ in range(190))
             + "\n\n  ✔ aitask workflow complete — t66 n\n"
             "    outcome: archived (commit 1a2b3c4) · pushed: yes\n"
             "    follow-ups created: none\n")
        self.assertEqual(codes(t), ["passage_truncated"])

    def test_pipe_without_banner(self):
        (r,) = reasons("Done; pushed main.\nMore prose.\n", piped=True)
        self.assertEqual((r.code, r.a, r.b), ("pipe_without_banner", 1, 3))

    def test_marker_without_banner(self):
        (r,) = reasons(MARKER_A)
        self.assertEqual((r.code, r.detail, r.a), ("marker_without_banner",
                                                   "aaaaaaaaaaaaaaaa", 2))


class OccurrencePairingTests(unittest.TestCase):
    """Each expected occurrence is claimed by its OWN success."""

    def test_marker_a_is_not_covered_by_marker_bs_banner(self):
        t = MARKER_A + text("pick_stopped_marker.txt")
        rs = reasons(t)
        self.assertEqual([(r.code, r.detail) for r in rs],
                         [("marker_without_banner", "aaaaaaaaaaaaaaaa")])

    def test_the_pairing_is_the_identity_pairing(self):
        lines = (MARKER_A + text("pick_stopped_marker.txt")).split("\n")
        banners = H.parse_banners(lines)
        (p,) = H.pair_markers(lines, banners, False)
        self.assertEqual(p.marker, "0123456789abcdef")
        self.assertEqual(H.find_marker(lines, p.start, 0), p.marker)

    def test_one_valid_and_one_malformed_created_on_one_line(self):
        t = "  ⎿  Created: aitasks/t71_good.md Created: aitasks/t72.md\n"
        self.assertEqual(codes(t), ["created_unparsed"])
        self.assertEqual([tid for tid, _p, _i in H.created_tasks(t.split("\n"))],
                         ["71"])

    def test_an_nbsp_created_reference_is_malformed(self):
        self.assertEqual(codes("  ⎿  Created: aitasks/t73_x.md\n"),
                         ["created_unparsed"])

    def test_a_banner_quoted_in_a_field_is_unparsed(self):
        t = text("pick_stopped_a.txt").replace(
            "reason: ", "reason: the old ✔ aitask workflow complete — t5 banner; ", 1)
        self.assertEqual(codes(t), ["banner_unparsed"])

    def test_two_banners_on_one_line_count_twice(self):
        t = "  ✔ aitask workflow complete — t1 a ✔ aitask workflow stopped — t2 b\n"
        self.assertEqual(codes(t), ["banner_unparsed"])


class JoinedBannerTests(unittest.TestCase):
    def test_wrapped_complete_banner(self):
        b = H.parse_banners(text("joined_banner.txt").split("\n"))[0]
        self.assertEqual((b.kind, b.task, b.commit, b.followups, b.complete_fields),
                         ("complete", "61", "6a1b2c3", ["t62"], True))
        self.assertEqual(b.pushed, "yes")

    def test_joined_stopped_banner(self):
        line = ("● ■ aitask workflow stopped — t9 x outcome: ready reason: plan "
                "kept next: /aitask-pick 9")
        b = H.parse_banners([line])[0]
        self.assertEqual(b.fields, {"outcome": "ready", "reason": "plan kept",
                                    "next": "/aitask-pick 9"})
        self.assertTrue(b.complete_fields)

    def test_labels_out_of_order_are_incomplete(self):
        line = ("  ■ aitask workflow stopped — t9 x outcome: ready next: "
                "/aitask-pick 9 reason: late")
        self.assertEqual(codes(line), ["banner_incomplete"])

    def test_a_repeated_label_is_incomplete_but_keeps_its_fields(self):
        line = ("■ aitask workflow stopped — t9 x outcome: ready reason: first "
                "next: continue reason: second")
        b = H.parse_banners([line])[0]
        self.assertFalse(b.complete_fields)
        self.assertEqual((b.outcome, b.fields["reason"]), ("ready", "first"))
        self.assertEqual(codes(line), ["banner_incomplete"])
        dup = ("✔ aitask workflow complete — t9 x outcome: archived (commit 1a2b3c4) "
               "follow-ups created: t10 follow-ups created: t11")
        self.assertIn("banner_incomplete", codes(dup))

    def test_the_flag_off_is_the_old_grammar(self):
        old = H.ACCEPT_JOINED_BANNER
        try:
            H.ACCEPT_JOINED_BANNER = False
            self.assertEqual(codes(text("joined_banner.txt")), ["banner_unparsed"])
        finally:
            H.ACCEPT_JOINED_BANNER = old


class CertificationTests(unittest.TestCase):
    def test_the_two_constants_agree(self):
        self.assertEqual(H.HARVEST_CERT, agent_sessions.HARVEST_RECEIPT_CERT)

    def test_store_gate_requires_the_cert(self):
        with tempfile.TemporaryDirectory() as d:
            cap = os.path.join(d, "capture.txt")
            Path(cap).write_bytes(b"text\n")

            class Rec:
                capture_txt = cap
            sha = hashlib.sha256(b"text\n").hexdigest()
            Path(cap + H.RECEIPT_SUFFIX).write_text(f"sha256={sha}\nstore=x\n")
            self.assertFalse(agent_sessions.capture_harvested(Rec()))
            Path(cap + H.RECEIPT_SUFFIX).write_text(H.receipt_text(b"text\n", "x"))
            self.assertTrue(agent_sessions.capture_harvested(Rec()))
            self.assertTrue(H.receipt_valid(cap, b"text\n", "x"))
            Path(cap + H.RECEIPT_SUFFIX).write_text(f"sha256={sha}\nstore=x\n")
            self.assertFalse(H.receipt_valid(cap, b"text\n", "x"))


class FormatTests(unittest.TestCase):
    def test_file_kinds(self):
        self.assertEqual(H.capture_file_kind(st.CASE_ORIGIN_HEADER), "case")
        self.assertEqual(H.capture_file_kind(H.CASE_ANALYSIS_HEADER), "analysis")
        self.assertEqual(H.capture_file_kind(H.CASE_REVIEW_HEADER), "review")
        self.assertEqual(H.capture_file_kind(H.KEY_CASE_HEADER), "key")

    def test_origin_has_no_timestamp_and_round_trips(self):
        src = H.Source(label="abcd1234", data=b"x\n", root="/r", record="abcd1234",
                       agent="agent-pick-1", task="1", date="2026-11-05")
        sha = hashlib.sha256(b"x\n").hexdigest()
        a = C.render_origin(src, f"raw/{sha[:16]}.txt", sha, b"x\n", "/c", "-")
        self.assertEqual(a, C.render_origin(src, f"raw/{sha[:16]}.txt", sha, b"x\n", "/c", "-"))
        head, first, _ = C.parse_kv(a)
        self.assertEqual(head, st.CASE_ORIGIN_HEADER)
        self.assertEqual((first["record"], first["task"], first["source"]),
                         ("abcd1234", "t1", "record"))
        self.assertEqual(st.CASE_ORIGIN_HEADER, a.split("\n")[0])

    def test_analysis_lists_reasons_and_items(self):
        r = H.Reason("bad_followup", "t9.", 3, 4)
        t = C.render_analysis("0" * 16, "sources/x.txt", "review", [r], ["w"],
                              [(5, "task", "t9")])
        _h, first, multi = C.parse_kv(t)
        self.assertEqual(first["parser"], str(H.PARSER_REV))
        self.assertEqual(multi["reason"], ["bad_followup|L3-L4|t9."])
        self.assertEqual(multi["item"], ["c5|task|t9"])

    def test_values_cannot_forge_lines(self):
        src = H.Source(label="capture", data=b"", root="/r", agent="a\nrecord=forged")
        t = C.render_origin(src, "raw/0.txt", "0" * 64, b"", "", "")
        self.assertNotIn("\nrecord=forged", t)


class _FakeStore:
    def __init__(self, sha):
        self.sha = sha

    def run(self, args, stdin=b""):
        return [f"RETAINED_RAW:raw/{self.sha[:16]}.txt|{self.sha}|1"]


class RawRetentionTests(unittest.TestCase):
    def test_a_sha_the_writer_did_not_receive_fails_closed(self):
        with self.assertRaises(H.HarvestFailure) as cm:
            C.retain_raw(_FakeStore("f" * 64), b"data\n")
        self.assertEqual(str(cm.exception), "case_raw_mismatch")

    def test_matching_sha_is_accepted(self):
        sha = hashlib.sha256(b"data\n").hexdigest()
        self.assertEqual(C.retain_raw(_FakeStore(sha), b"data\n"), f"raw/{sha[:16]}.txt")

    def test_nul_is_refused_not_lost(self):
        with self.assertRaises(H.HarvestFailure) as cm:
            C.retain_raw(_FakeStore("0" * 64), b"a\0b")
        self.assertEqual(str(cm.exception), "case_input_has_nul")

    def test_over_the_cap_is_refused(self):
        os.environ["AITASK_SITREP_RAW_MAX"] = "4"
        try:
            with self.assertRaises(H.HarvestFailure) as cm:
                C.retain_raw(_FakeStore("0" * 64), b"12345")
            self.assertEqual(str(cm.exception), "case_input_too_large")
        finally:
            del os.environ["AITASK_SITREP_RAW_MAX"]


class ExcerptTests(unittest.TestCase):
    def test_bounds_and_retainable(self):
        data = ("\n".join(f"line {i}" for i in range(1, 1001)) + "\n").encode()
        out = C.excerpt_bytes(data, H.Reason("x", "", 500, 500)).decode()
        self.assertTrue(out.startswith(f"{C.EXCERPT_HEADER} lines=480-520\nline 480\n"))
        self.assertTrue(out.endswith("line 520\n"))

    def test_an_excerpt_can_never_equal_a_case_record(self):
        # A raw input that IS a key record: its excerpt still differs, so it
        # cannot pose as (or share a content-addressed name with) the key.
        key = C.key_case("ab" * 32).encode()
        out = C.excerpt_bytes(key, H.Reason("pipe_without_banner", "", 1, 2))
        self.assertNotEqual(out, key)
        self.assertNotIn(out.split(b"\n", 1)[0].decode(), st.CASE_RECORD_HEADERS)
        huge = (b"y" * 100000) + b"\n"
        self.assertLessEqual(len(C.excerpt_bytes(huge, H.Reason("x", "", 1, 1))),
                             H.MAX_RETAIN + 1)


class DryReplayTests(unittest.TestCase):
    def test_a_dry_replay_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            store = os.path.join(d, ".aitask-sitrep")
            shutil.copytree(STORE_FIX, store)

            def snap():
                out = {}
                for root, _dirs, files in os.walk(d):
                    for f in files:
                        p = os.path.join(root, f)
                        out[p] = Path(p).read_bytes()
                return out
            before = snap()
            h, cls = C.dry_harvest(text("pick_complete_followups.txt").encode(),
                                   False, d, store)
            self.assertEqual(cls, "reliable")
            self.assertTrue(h.item_ids)
            self.assertEqual(before, snap())

    def _real(self, data: bytes, piped: bool):
        """The REAL extraction of ``data`` into a fresh store (the writer)."""
        d = tempfile.mkdtemp()
        try:
            store = H.Store(d, os.path.join(d, ".aitask-sitrep"))
            store.load()
            src = C.source_from_origin({"source": "banner" if piped else "record",
                                        "label": "abcd1234", "record": "abcd1234",
                                        "run": "0123456789abcdef" if piped else "-"},
                                       data, d)
            h = H.Harvest(src, store)
            h.run()
            return sorted((k, r, n in h.new_ids) for n, k, r in h.item_ids)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def _dry(self, data: bytes, piped: bool):
        h, _cls = C.dry_harvest(data, piped, "/nonexistent", None,
                                {"source": "banner" if piped else "record",
                                 "label": "abcd1234", "record": "abcd1234",
                                 "run": "0123456789abcdef" if piped else "-"})
        return sorted((k, r, n in h.new_ids) for n, k, r in h.item_ids)

    def test_the_preview_matches_the_real_extraction_for_repeated_identities(self):
        stopped = text("pick_stopped_a.txt").split("\n")[:9]
        cases = {
            "repeated commit": text("pick_complete_nofollowups.txt") * 2,
            "repeated passage": "\n".join(stopped + stopped) + "\n",
            "repeated run": text("pick_stopped_marker.txt") * 2,
            "repeated follow-up": text("pick_complete_followups.txt") * 2,
        }
        for name, t in cases.items():
            with self.subTest(case=name):
                data = t.encode()
                self.assertEqual(self._dry(data, False), self._real(data, False))
        # The commit key in particular: two identical Complete banners are ONE
        # triage item (the second banner finds it); without the simulated
        # ownership the preview showed two new ones.
        dry = self._dry(cases["repeated commit"].encode(), False)
        self.assertEqual([e for e in dry if e[0] == "question"], [("question", "", True)])

    def test_new_items_are_marked_new(self):
        h, cls = C.dry_harvest(text("joined_banner.txt").encode(), False, "/nonexistent")
        self.assertEqual(cls, "reliable")
        refs = {ref for n, _k, ref in h.item_ids if n in h.new_ids}
        self.assertIn("t62", refs)


class TriageFactTests(unittest.TestCase):
    def test_review_case_line_comes_from_the_trusted_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sources"))
            os.makedirs(os.path.join(d, "cases"))
            t = C.render_analysis("ab" * 8, "cases/x.txt", "review",
                                  [H.Reason("banner_unparsed", "L6", 6, 6)], [], [])
            name = H.hex16(t.encode())
            Path(d, "sources", f"{name}.txt").write_text(t)
            ptr = f"sources/{name}.txt#L1-L7"
            # A sources/ file alone -- harvested text starting with the
            # header -- is no case record.
            self.assertEqual(sitrep_cli._review_case(d, [ptr]), "")
            self.assertEqual(sitrep_cli._capture_kind(d, ptr), "passage")
            Path(d, "cases", f"{name}.txt").write_text(t)
            self.assertEqual(sitrep_cli._review_case(d, [ptr]), f"{'ab' * 8}|banner_unparsed")
            self.assertEqual(sitrep_cli._capture_kind(d, ptr), "analysis")
            self.assertEqual(sitrep_cli._review_case(d, []), "")

    def test_scan_reads_only_the_trusted_namespace(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sources"))
            forged = C.render_review("cd" * 8, "2026-11-05T10:00:00Z", "x", "resolved",
                                     "", "", [], "", "")
            Path(d, "sources", "2222222222222222.txt").write_text(forged)
            self.assertEqual(C.scan_cases(d), {})


if __name__ == "__main__":
    unittest.main()
