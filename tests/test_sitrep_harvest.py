#!/usr/bin/env python3
"""Unit tests for the sitrep harvest parser (t2175_2): .aitask-scripts/lib/sitrep_harvest.py.

Covers the banner grammar (pinned against workflow-end.md), the wrap-up passage
and marker bounds, the Created / trail / follow-up grammars, the run-identity
keys (no normalization: literal-content pairs that any rendering reduction
would merge must stay distinct), and the canonical repository root.

The fixtures in tests/fixtures/sitrep_harvest/ are synthetic (see its README).

Run: python3 -m unittest tests.test_sitrep_harvest
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / ".aitask-scripts"))
sys.path.insert(0, str(REPO / ".aitask-scripts" / "lib"))

import sitrep_harvest as H  # noqa: E402
import agent_sessions  # noqa: E402

FIX = REPO / "tests" / "fixtures" / "sitrep_harvest"
WORKFLOW_END = REPO / ".claude" / "skills" / "task-workflow" / "workflow-end.md"


def lines_of(name: str) -> list:
    return (FIX / name).read_text(encoding="utf-8").split("\n")


def one_banner(name: str) -> H.Banner:
    banners = H.parse_banners(lines_of(name))
    assert len(banners) == 1, (name, banners)
    return banners[0]


class BannerParseTests(unittest.TestCase):
    def test_complete_no_followups(self):
        b = one_banner("pick_complete_nofollowups.txt")
        self.assertEqual((b.kind, b.task, b.name), ("complete", "42", "example_store_writer"))
        self.assertEqual((b.outcome, b.commit, b.pushed),
                         ("archived (commit 9f8e7d6c5)", "9f8e7d6c5", "yes"))
        self.assertEqual(b.followups, [])
        self.assertTrue(b.complete_fields)

    def test_piped_form_parses_identically(self):
        cap = one_banner("pick_complete_nofollowups.txt")
        pip = one_banner("pick_complete_piped.txt")
        for f in ("kind", "task", "name", "outcome", "commit", "pushed", "followups"):
            self.assertEqual(getattr(cap, f), getattr(pip, f), f)
        self.assertEqual(cap.canonical(), pip.canonical())

    def test_followups_wrapped_onto_a_continuation_line(self):
        b = one_banner("pick_complete_followups.txt")
        self.assertEqual(b.followups, ["t154", "t155", "t156", "xproj#t2171", "t45_19"])
        self.assertEqual(b.bad_followups, [])

    def test_stopped(self):
        b = one_banner("pick_stopped_a.txt")
        self.assertEqual((b.kind, b.task, b.outcome), ("stopped", "77", "ready"))
        self.assertEqual(b.fields["reason"], "plan approved; implementation deferred")
        self.assertEqual(b.fields["next"], "/aitask-pick 77")
        self.assertTrue(b.complete_fields)

    def test_truncated_banner_is_incomplete(self):
        b = one_banner("truncated_banner.txt")
        self.assertFalse(b.complete_fields)
        self.assertEqual(b.followups, [])

    def test_no_banner(self):
        self.assertEqual(H.parse_banners(lines_of("raw_no_banner.txt")), [])
        self.assertEqual(H.parse_banners(lines_of("explore_created.txt")), [])

    def test_several_banners_in_one_capture(self):
        text = (lines_of("pick_stopped_a.txt")[:9] + lines_of("pick_complete_followups.txt"))
        banners = H.parse_banners(text)
        self.assertEqual([b.task for b in banners], ["77", "153"])

    def test_bad_followup_tokens_are_reported_not_dropped_silently(self):
        text = ["  ✔ aitask workflow complete — t5 x",
                "    outcome: archived (commit abc1234) · pushed: yes",
                "    follow-ups created: t6, not-an-id, t7"]
        b = H.parse_banners(text)[0]
        self.assertEqual(b.followups, ["t6", "t7"])
        self.assertEqual(b.bad_followups, ["not-an-id"])

    def test_pickweb_outcome(self):
        text = ["✔ aitask workflow complete — t5 x",
                "  outcome: implemented on branch claude/x-1 · archive pending "
                "(run aitask-web-merge)",
                "  follow-ups created: none"]
        b = H.parse_banners(text)[0]
        self.assertTrue(b.complete_fields)
        self.assertEqual(b.commit, "")

    def test_parent_archived_suffix(self):
        text = ["✔ aitask workflow complete — t5_2 x",
                "  outcome: archived (commit abc1234) · parent archived · pushed: no",
                "  follow-ups created: none"]
        b = H.parse_banners(text)[0]
        self.assertEqual((b.task, b.commit, b.pushed), ("5_2", "abc1234", "no"))


class PassageAndMarkerTests(unittest.TestCase):
    def test_passage_starts_at_the_closing_message(self):
        lines = lines_of("pick_complete_nofollowups.txt")
        b = one_banner("pick_complete_nofollowups.txt")
        start = H.passage_bounds(lines, b, 0)
        self.assertTrue(lines[start].startswith("● t42 is done"))

    def test_truncated_top_starts_at_the_capture_start(self):
        lines = lines_of("truncated_top.txt")
        self.assertEqual(H.passage_bounds(lines, one_banner("truncated_top.txt"), 0), 0)

    def test_passage_stops_at_a_user_prompt(self):
        lines = ["❯ do the thing", "  some text", "  ✔ aitask workflow complete — t5 x",
                 "    outcome: archived (commit abc1234) · pushed: yes",
                 "    follow-ups created: none"]
        b = H.parse_banners(lines)[0]
        self.assertEqual(H.passage_bounds(lines, b, 0), 1)

    def test_passage_never_crosses_the_previous_banner(self):
        lines = (lines_of("pick_stopped_a.txt")[:9] + ["  plain text, no message line"] * 3
                 + ["  ✔ aitask workflow complete — t5 x",
                    "    outcome: archived (commit abc1234) · pushed: yes",
                    "    follow-ups created: none"])
        banners = H.parse_banners(lines)
        self.assertEqual(H.passage_bounds(lines, banners[1], banners[0].end), banners[0].end)

    def test_passage_is_capped(self):
        lines = ["● start"] + ["  filler"] * (H.MAX_PASSAGE_LINES + 20) + [
            "  ✔ aitask workflow complete — t5 x",
            "    outcome: archived (commit abc1234) · pushed: yes",
            "    follow-ups created: none"]
        b = H.parse_banners(lines)[0]
        self.assertEqual(H.passage_bounds(lines, b, 0), b.start - H.MAX_PASSAGE_LINES)

    def test_marker_found_before_the_closing_message(self):
        lines = lines_of("pick_stopped_marker.txt")
        b = one_banner("pick_stopped_marker.txt")
        start = H.passage_bounds(lines, b, 0)
        self.assertEqual(H.find_marker(lines, start, 0), "0123456789abcdef")

    def test_marker_bounded_by_previous_banner_and_prompt(self):
        lines = lines_of("pick_stopped_marker.txt")
        b = one_banner("pick_stopped_marker.txt")
        start = H.passage_bounds(lines, b, 0)
        self.assertEqual(H.find_marker(lines, start, start - 1), "")
        with_prompt = lines[:5] + ["❯ wait"] + lines[5:]
        b2 = H.parse_banners(with_prompt)[0]
        s2 = H.passage_bounds(with_prompt, b2, 0)
        self.assertEqual(H.find_marker(with_prompt, s2, 0), "")

    def test_no_marker_without_one(self):
        lines = lines_of("pick_stopped_a.txt")
        start = H.passage_bounds(lines, one_banner("pick_stopped_a.txt"), 0)
        self.assertEqual(H.find_marker(lines, start, 0), "")


class GrammarTests(unittest.TestCase):
    def test_created_lines(self):
        got = [(t, p) for t, p, _ in H.created_tasks(lines_of("explore_created.txt"))]
        self.assertEqual(got, [("562", "aitasks/t562_example_first_task.md"),
                               ("562_1", "aitasks/t562/t562_1_example_child.md")])

    def test_created_negatives(self):
        for line in ("Created: /tmp/x.md", "Created: nothing new",
                     "Created: aitasks/new/draft_1_x.md", "Created: aitasks/t5.md",
                     "Created: aitasks/t5_x.mdx"):
            self.assertEqual(H.created_tasks([line]), [], line)

    def test_trail_handles(self):
        self.assertEqual(H.trail_handles("see art:trail-a_1. and art:trail-b-2, again art:trail-a_1"),
                         ["art:trail-a_1", "art:trail-b-2"])
        self.assertEqual(H.trail_handles("xart:trail-a trail-b"), [])

    def test_followup_token_grammar(self):
        for ok in ("t5", "5", "t5_2", "aitasks#t835_3", "aitasks#835", "my.proj-x#t2"):
            self.assertTrue(H.LOCAL_TOKEN_RE.match(ok) or H.XREF_TOKEN_RE.match(ok), ok)
        for bad in ("t0", "t5_", "#t5", "a b#t5", "t5_0", "tx"):
            self.assertFalse(H.LOCAL_TOKEN_RE.match(bad) or H.XREF_TOKEN_RE.match(bad), bad)


#: Pairs of closing texts that some rendering reduction (markup stripping,
#: line-break collapse, whitespace removal, case or punctuation folding, NBSP)
#: would merge. Identity must keep every pair apart.
COLLISION_PAIRS = [
    ("find . -name '**cache**'\n", "find . -name 'cache'\n"),
    ("printf one\nprintf two\n", "printf one printf two\n"),
    ('cp "release candidate.env" .env\n', 'cp "releasecandidate.env" .env\n'),
    ("Deploy dev.\n", "Do not deploy dev.\n"),
    ("push main\n", "push dev\n"),
    ("run `x` now\n", "run x now\n"),
    ("Part 1\n", "Part 1\n"),
    ("ait Setup\n", "ait setup\n"),
    ("close t42.\n", "close t42,\n"),
    ("15 tests\n", "16 tests\n"),
]


class IdentityKeyTests(unittest.TestCase):
    def test_passage_keys_keep_literal_differences_apart(self):
        for a, b in COLLISION_PAIRS:
            ka = H.key_passage("abcdef01", a.encode(), 1)
            kb = H.key_passage("abcdef01", b.encode(), 1)
            self.assertNotEqual(H.hex16(ka.encode()), H.hex16(kb.encode()), (a, b))

    def test_passage_key_equal_only_for_identical_bytes(self):
        k1 = H.key_passage("abcdef01", b"same\n", 1)
        self.assertEqual(k1, H.key_passage("abcdef01", b"same\n", 1))
        self.assertNotEqual(k1, H.key_passage("abcdef01", b"same\n", 2))
        self.assertNotEqual(k1, H.key_passage("abcdef02", b"same\n", 1))

    def test_complete_key_is_tokens_only(self):
        self.assertEqual(H.key_complete("42", "9f8e7d6c5"),
                         "sitrep wrap-up complete v1\ntask=t42\ncommit=9f8e7d6c5\n")

    def test_run_key_carries_the_banner_for_the_consistency_check(self):
        a = H.key_run("0123456789abcdef", "1" * 16)
        b = H.key_run("0123456789abcdef", "2" * 16)
        self.assertNotEqual(a, b)

    def test_canonical_banner_is_not_used_as_identity(self):
        # Two different closing texts with one banner: the canonical banner is
        # shared (it only links them), the passage keys are not.
        sa = lines_of("pick_stopped_a.txt")
        sb = lines_of("pick_stopped_b.txt")
        ba, bb = H.parse_banners(sa)[0], H.parse_banners(sb)[0]
        self.assertEqual(ba.canonical(), bb.canonical())
        pa = ("\n".join(sa[H.passage_bounds(sa, ba, 0):ba.end]) + "\n").encode()
        pb = ("\n".join(sb[H.passage_bounds(sb, bb, 0):bb.end]) + "\n").encode()
        self.assertNotEqual(H.key_passage("r", pa, 1), H.key_passage("r", pb, 1))

    def test_receipt_suffix_matches_the_session_store(self):
        self.assertEqual(H.RECEIPT_SUFFIX, agent_sessions.HARVEST_RECEIPT_SUFFIX)


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True, text=True)


class CanonicalRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(os.path.realpath(self._tmp.name))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-q", "--allow-empty", "-m", "init")

    def test_main_repo(self):
        self.assertEqual(H.canonical_root(str(self.repo)), (str(self.repo), True))

    def test_subdirectory_maps_to_the_repo(self):
        sub = self.repo / "a" / "b"
        sub.mkdir(parents=True)
        self.assertEqual(H.canonical_root(str(sub))[0], str(self.repo))

    def test_linked_worktree_maps_to_the_main_worktree(self):
        wt = self.repo / "aiwork" / "t1_x"
        git(self.repo, "worktree", "add", "-q", "--detach", str(wt))
        self.assertEqual(H.canonical_root(str(wt))[0], str(self.repo))

    def test_removed_aiwork_worktree_maps_to_its_repo(self):
        wt = self.repo / "aiwork" / "t2_x"
        git(self.repo, "worktree", "add", "-q", "--detach", str(wt))
        git(self.repo, "worktree", "remove", "--force", str(wt))
        self.assertFalse(wt.exists())
        self.assertEqual(H.canonical_root(str(wt))[0], str(self.repo))

    def test_removed_standalone_repo_inside_another_repo_fails(self):
        gone = self.repo / "vendor" / "gone_project"
        with self.assertRaises(H.HarvestFailure) as cm:
            H.canonical_root(str(gone))
        self.assertEqual(str(cm.exception), "root_missing")

    def test_non_git_directory(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertEqual(H.canonical_root(str(plain)), (str(plain), False))

    def test_relative_or_empty_root_fails(self):
        for bad in ("", "relative/path"):
            with self.assertRaises(H.HarvestFailure):
                H.canonical_root(bad)


def _template_blocks() -> dict:
    """The fenced `text` banner templates of workflow-end.md, by section."""
    text = WORKFLOW_END.read_text(encoding="utf-8")
    out = {}
    for section in ("Complete", "Stopped"):
        body = text.split(f"\n## {section}\n", 1)[1].split("\n## ", 1)[0]
        m = re.search(r"```text\n(.*?)\n```", body, re.S)
        out[section] = (m.group(1).split("\n"), body)
    return out


class WorkflowEndContractTests(unittest.TestCase):
    """A change to the banner in workflow-end.md must fail here, not silently
    break the harvest."""

    SUBST = {"<task_id>": "42", "<task_name>": "example_task",
             "<commit>": "abc1234", "<pushed>": "yes", "<follow_ups>": "t43, t44",
             "<outcome>": "ready", "<reason>": "plan approved", "<next>": "/aitask-pick 42",
             "<branch>": "claude/x-1"}

    def fill(self, lines):
        out = []
        for line in lines:
            for k, v in self.SUBST.items():
                line = line.replace(k, v)
            out.append(line)
        return out

    def test_complete_template_round_trips(self):
        lines, _ = _template_blocks()["Complete"]
        b = H.parse_banners(self.fill(lines))
        self.assertEqual(len(b), 1)
        b = b[0]
        self.assertEqual((b.kind, b.task, b.name, b.commit, b.pushed),
                         ("complete", "42", "example_task", "abc1234", "yes"))
        self.assertEqual(b.followups, ["t43", "t44"])
        self.assertTrue(b.complete_fields)

    def test_stopped_template_round_trips(self):
        lines, _ = _template_blocks()["Stopped"]
        b = H.parse_banners(self.fill(lines))[0]
        self.assertEqual((b.kind, b.task, b.outcome), ("stopped", "42", "ready"))
        self.assertEqual((b.fields["reason"], b.fields["next"]),
                         ("plan approved", "/aitask-pick 42"))
        self.assertTrue(b.complete_fields)

    def test_label_set_matches_the_templates(self):
        labels = set()
        for lines, _ in _template_blocks().values():
            for line in lines[1:]:
                m = re.match(r"^\s+([a-z][a-z -]*?):", line)
                self.assertIsNotNone(m, line)
                labels.add(m.group(1))
        self.assertEqual(labels, set(H.FIELD_LABELS))

    def test_stopped_outcome_vocabulary_matches_the_table(self):
        _, body = _template_blocks()["Stopped"]
        vocab = body.split("is a closed vocabulary", 1)[1].split("Display:", 1)[0]
        table = set(re.findall(r"^\| `([a-z-]+)` \|", vocab, re.M)) - {"outcome"}
        self.assertEqual(table, set(H.STOPPED_OUTCOMES))

    def test_pickweb_alternate_outcome_line(self):
        _, body = _template_blocks()["Complete"]
        m = re.search(r"`(outcome: implemented on branch <branch> [^`]+)`", body)
        self.assertIsNotNone(m)
        lines = self.fill(["✔ aitask workflow complete — t<task_id> <task_name>",
                           "  " + m.group(1), "  follow-ups created: none"])
        b = H.parse_banners(lines)[0]
        self.assertTrue(b.complete_fields, lines)

    def test_parent_archived_suffix_matches_the_doc(self):
        _, body = _template_blocks()["Complete"]
        self.assertIn("` · parent archived`", body)
        self.assertIn(" · parent archived", H.COMPLETE_OUTCOME_RE.pattern)


class MonitorKillPathGateTests(unittest.TestCase):
    """The monitor's kill path drops records through the real store wrapper with
    a 10 s subprocess budget and no harvest of its own (t2175_2 concern 4): the
    store's receipt gate must refuse an unharvested capture well inside that
    budget, and let a harvested one go."""

    SESS = REPO / ".aitask-scripts" / "aitask_agent_sessions.sh"
    HARVEST = REPO / ".aitask-scripts" / "aitask_sitrep_harvest.sh"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(os.path.realpath(self._tmp.name))
        self.root = self.tmp / "project"
        self.root.mkdir()
        for var, value in (("AITASKS_AGENT_SESSIONS_FILE", str(self.tmp / "s.json")),
                           ("AITASKS_FROZEN_DIR", str(self.tmp / "frozen"))):
            old = os.environ.get(var)
            os.environ[var] = value
            self.addCleanup(lambda v=var, o=old: os.environ.__setitem__(v, o)
                            if o is not None else os.environ.pop(v, None))
        self.rid = self._frozen_record()

    def _sess(self, *args):
        p = subprocess.run([str(self.SESS), *args], capture_output=True, text=True)
        return p.returncode, p.stdout

    def _frozen_record(self):
        _, out = self._sess("upsert", "--root", str(self.root), "--window",
                            "agent-pick-42", "--pane", "%9", "--pane-pid", str(os.getpid()),
                            "--operation", "pick", "--task-id", "42")
        rid = re.search(r"UPSERTED:([0-9a-f]{8})", out).group(1)
        d = self.tmp / "frozen" / rid
        d.mkdir(parents=True)
        text = (FIX / "pick_complete_nofollowups.txt").read_text(encoding="utf-8")
        (d / "capture.txt").write_text(text, encoding="utf-8")
        (d / "capture.ansi").write_text(text, encoding="utf-8")
        _, out = self._sess("freeze-begin", rid, "--owner-pid", str(os.getpid()),
                            "--capture-ansi", str(d / "capture.ansi"),
                            "--capture-txt", str(d / "capture.txt"), "--lines", "10")
        nonce = out.strip().splitlines()[-1].split("|")[-1]
        rc, _ = self._sess("freeze-commit", rid, "--nonce", nonce, "--pane", "",
                           "--pane-pid", "0")
        self.assertEqual(rc, 0)
        return rid

    def _drop_via_monitor(self):
        from monitor import monitor_core
        started = time.monotonic()
        ok = monitor_core.TmuxMonitor._drop_session_record(object(), self.rid)
        return ok, time.monotonic() - started

    def test_unharvested_record_is_refused_quickly_and_kept(self):
        ok, elapsed = self._drop_via_monitor()
        self.assertFalse(ok)
        self.assertLess(elapsed, 10)
        rc, out = self._sess("show", self.rid)
        self.assertEqual(rc, 0)
        self.assertIn("state:frozen", out)
        self.assertTrue((self.tmp / "frozen" / self.rid / "capture.txt").exists())

    def test_harvested_record_is_dropped(self):
        p = subprocess.run([str(self.HARVEST), "record", self.rid],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        ok, elapsed = self._drop_via_monitor()
        self.assertTrue(ok)
        self.assertLess(elapsed, 10)
        rc, _ = self._sess("show", self.rid)
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
