"""Tests for the consumer side of the task-relations store (t1981_5).

``lib/relations_consume.py`` and the ``related-work`` / ``notify-candidates`` /
``notify-outcome`` verbs of ``ait relations`` (aidocs/framework/task_relations.md
D8 and its "Consumer API"). Scratch repos only (local-only store unless a test
says otherwise); no test changes the process cwd -- the CLI runs as a subprocess
with ``cwd=`` or in-process with an explicit root.

Run: python3 tests/test_relations_consume.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(ROOT / ".aitask-scripts" / "lib"))

import relations_cli as rcli  # noqa: E402
import relations_consume as rc  # noqa: E402
import relations_schema as rs  # noqa: E402
import relations_store as rst  # noqa: E402
import test_relations_store as ts  # noqa: E402

CLI = str(ROOT / ".aitask-scripts" / "aitask_relations.sh")
SHARED = "lib/x/shared.py"
C_OLD = "2026-01-01 10:00"
OID = "a" * 40


def git(cwd, *args):
    return ts.git(cwd, *args)


def task_file(root, tid, created, body="Goal.\n", status="Ready", archived=False, **meta):
    fm = [f"status: {status}", f"created_at: {created}"]
    fm += [f"{k}: {v}" for k, v in meta.items()]
    path = root / ts.task_relpath(tid, archived)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body, encoding="utf-8")
    return path


def code_commit(root, subject, files, branch=None):
    """Commit ``files`` ({path: text}) with ``subject``; returns the sha."""
    if branch:
        git(root, "checkout", "-q", "-B", branch)
    for path, text in files.items():
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            git(root, "rm", "-q", path)
            continue
        p.write_text(text, encoding="utf-8")
        git(root, "add", "--", path)
    git(root, "commit", "-q", "--allow-empty", "-m", subject)
    sha = git(root, "rev-parse", "HEAD")
    if branch:
        git(root, "checkout", "-q", "-")
    return sha


def note_block(sender, at, nid_hex="b" * 24):
    nid = f"{at}.{nid_hex}"
    return nid, (f"\n## Inbox\n\n> **✉ note:{sender}** id={nid} from={sender} at={at} "
                 f"base={OID} base_branch=main dirty=no host=h1\n>\n> | body\n")


def receipt_block(by, ids, at="2026-11-07T12:00:00Z"):
    return (f"\n> **👁 note:read** id={at}.{'c' * 24} by={by} at={at} mode=explicit "
            f"ids={','.join(ids)}\n")


def run(root, *args):
    env = dict(os.environ, AIT_PYTHON=sys.executable)
    proc = subprocess.run([CLI, *args], cwd=str(root), capture_output=True, text=True,
                          env=env, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def lines_with(out, prefix):
    return [ln for ln in out.splitlines() if ln.startswith(prefix)]


def inproc(root, argv):
    """Run a verb in-process (for patched cases); returns (rc, stdout)."""
    args = rcli.build_parser().parse_args(argv)
    buf = io.StringIO()
    fn = {"related-work": rcli.cmd_related_work, "notify-candidates": rcli.cmd_notify_candidates,
          "notify-outcome": rcli.cmd_notify_outcome}[args.verb]
    with contextlib.redirect_stdout(buf):
        code = fn(str(root), args)
    return code, buf.getvalue()


class CBase(ts.Base):
    def setUp(self):
        super().setUp()
        self.root = self.env.clone("repo", remote=False)
        ts.set_config(self.root, relations_enabled=True)
        git(self.root, "commit", "-q", "--allow-empty", "-m", "init")

    def enable(self, value=True):
        ts.set_config(self.root, relations_enabled=value)

    def publish(self, tid, rels=(), **kw):  # noqa: D401 - a store write on self.root
        return super().publish(self.root, tid, rels, **kw)

    def ledger(self, name):
        path = Path(rst.Store(str(self.root)).state_dir) / f"{name}.jsonl"
        if not path.exists():
            return []
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


# ===================================================== D9 pick-time display

class PickObsolescenceTests(CBase):
    """`related-work --point pick` shows the task's OWN band when medium+ (t1981_6)."""
    T = "20"
    CREATED = "2026-11-01 10:00"

    def setUp(self):
        super().setUp()
        task_file(self.root, self.T, self.CREATED, "Goal.\n")

    def assess(self, band, disposition="refresh"):
        idx = rst.TaskIndex(str(self.root))
        rec = {"schema": rs.SCHEMA, "task": f"aitasks#{self.T}", "task_created_at": self.CREATED,
               "run": {"id": "r", "trigger": "manual", "stage": 1, "at": "2026-11-08T10:00:00Z"},
               "inputs": {"body_sha256": idx.body_digest(self.T), "plan_sha256": None,
                          "evidence_digest": "d" * 64},
               "evidence": [{"id": "duplicate_of:1", "kind": "duplicate_of", "detail": "x",
                             "source": "store:records/t21.json"}],
               "band": band, "disposition": disposition,
               "reasons": [{"text": "why | it is obsolete", "evidence_ids": ["duplicate_of:1"]}]}
        out = rst.Store(str(self.root)).write(rs.store_path("obsolescence", self.T), rec)
        self.assertTrue(any(x.startswith("PUBLISHED:") for x in out), out)

    def dismiss(self, digest="d" * 64):
        out = rst.Store(str(self.root)).write(rs.store_path("dismissals", self.T), {
            "task": f"aitasks#{self.T}", "task_created_at": self.CREATED,
            "at": "2026-11-08T11:00:00Z", "by": "me", "evidence_digest": digest})
        self.assertTrue(any(x.startswith("PUBLISHED:") for x in out), out)

    def pick(self, point="pick"):
        _rc, out, _err = run(self.root, "related-work", self.T, "--point", point)
        return out

    def test_medium_band_is_shown_with_reasons(self):
        self.assess("medium")
        out = self.pick()
        self.assertEqual(lines_with(out, "OBSOLESCENCE:"), ["OBSOLESCENCE:medium|refresh|fresh"])
        self.assertEqual(lines_with(out, "OBSOLESCENCE_REASON:"),
                         ["OBSOLESCENCE_REASON:why %7C it is obsolete"])
        _rc, js, _ = run(self.root, "related-work", self.T, "--point", "pick", "--json")
        self.assertEqual(json.loads(js)["obsolescence"]["band"], "medium")

    def test_low_band_dismissed_and_review_point_show_nothing(self):
        self.assess("low")
        self.assertEqual(lines_with(self.pick(), "OBSOLESCENCE"), [])
        self.assess("high", "drop")
        self.assertEqual(lines_with(self.pick("review"), "OBSOLESCENCE"), [])
        self.dismiss("e" * 64)                       # an older digest: still shown
        self.assertEqual(lines_with(self.pick(), "OBSOLESCENCE:"), ["OBSOLESCENCE:high|drop|fresh"])
        self.dismiss()                               # keyed to this digest: hidden
        self.assertEqual(lines_with(self.pick(), "OBSOLESCENCE"), [])

    def test_body_change_marks_inputs_stale(self):
        self.assess("medium")
        task_file(self.root, self.T, self.CREATED, "Goal, rewritten.\n")
        self.assertEqual(lines_with(self.pick(), "OBSOLESCENCE:"), ["OBSOLESCENCE:medium|refresh|stale"])


# =================================================================== push/pull

class NotifyCandidatesTests(CBase):
    def setUp(self):
        super().setUp()
        task_file(self.root, "10", C_OLD, f"Source: change `{SHARED}`.\n", status="Implementing")
        task_file(self.root, "11", C_OLD, f"Target uses `{SHARED}` and `helper_fn`.\n",
                  status="Implementing")
        code_commit(self.root, "feature: Change the helper (t10)",
                    {SHARED: "def helper_fn():\n    return 2\n"})

    def push_rows(self, out):
        return lines_with(out, "PUSH:")

    def test_forward_affects_pushes_with_evidence(self):
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        code, out, _ = run(self.root, "notify-candidates", "10")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.push_rows(out)), 1, out)
        self.assertTrue(self.push_rows(out)[0].startswith(f"PUSH:aitasks#11|affects|path:{SHARED}|"))
        self.assertIn(f"  EVIDENCE:path:{SHARED}|", out)
        self.assertIn(f"CHANGED_FILE:{SHARED}", out)
        self.assertNotIn("PUSH_NONE", out)

    def test_reverse_affects_never_pushes(self):
        # "11 affects 10", the shared basis in 10's diff: 10 landing pushes nothing.
        self.publish("11", [("11", "10", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertEqual(self.push_rows(out), [])
        self.assertIn("PULL:aitasks#11|affects|reverse_direction", out)

    def test_coordinates_with_pushes_whichever_end_is_source(self):
        task_file(self.root, "12", C_OLD, f"Also edits `{SHARED}`.\n", status="Implementing")
        self.publish("11", [("11", "10", "coordinates_with", [{"kind": "path", "value": SHARED}])])
        self.publish("10", [("10", "12", "coordinates_with", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        to = sorted(r.split("|")[0] for r in self.push_rows(out))
        self.assertEqual(to, ["PUSH:aitasks#11", "PUSH:aitasks#12"], out)

    def test_task_ref_never_confirms(self):
        cs = rc.ChangeSet("x", ["c"], {"a.py": "c"}, [("c", "a.py", "see t11 and t10")])
        self.assertEqual(rc.confirm([{"kind": "task_ref", "value": "t11"}], cs)[0],
                         "unconfirmed_impact")
        # an affects whose only diff-visible basis is a task_ref
        self.publish("10", [("10", "11", "affects", [{"kind": "task_ref", "value": "t10"},
                                                      {"kind": "path", "value": "lib/other.py"}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertEqual(self.push_rows(out), [])
        self.assertIn("PULL:aitasks#11|affects|unconfirmed_impact", out)

    def test_unrelated_landing_is_pull(self):
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": "lib/elsewhere.py"}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PULL:aitasks#11|affects|unconfirmed_impact", out)

    def test_symbol_and_token_bases(self):
        self.publish("10", [("10", "11", "affects", [{"kind": "symbol", "value": "helper_fn"}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PUSH:aitasks#11|affects|symbol:helper_fn|", out)
        cs = rc.ChangeSet("x", ["c"], {}, [("c", "f", "helper_fnx = 1")])
        self.assertEqual(rc.confirm([{"kind": "symbol", "value": "helper_fn"}], cs)[0],
                         "unconfirmed_impact")  # identifier-bounded
        self.assertEqual(rc.confirm([{"kind": "token", "value": "fnx"}], cs)[0], "confirmed_impact")

    def test_target_moved_away(self):
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        task_file(self.root, "11", C_OLD, "Target rewritten: nothing about that file now.\n",
                  status="Implementing")
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PULL:aitasks#11|affects|target_moved", out)

    def test_target_plan_no_longer_cites_basis(self):
        task_file(self.root, "11", C_OLD, "Plan holder.\n", status="Ready")
        ts.write_plan(self.root, "11", f"---\nTask: t11\n---\n\nEdit `{SHARED}`.\n")
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PUSH:aitasks#11", out)  # plan holder, still citing
        ts.write_plan(self.root, "11", "---\nTask: t11\n---\n\nA different approach.\n")
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PULL:aitasks#11|affects|target_moved", out)

    def test_target_state_and_closed(self):
        task_file(self.root, "11", C_OLD, f"Ready, no plan, cites `{SHARED}`.\n", status="Ready")
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PULL:aitasks#11|affects|target_state", out)
        (self.root / ts.task_relpath("11")).unlink()
        task_file(self.root, "11", C_OLD, f"cites `{SHARED}`\n", status="Done", archived=True,
                  completed_at="2026-11-06 10:00")
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PULL:aitasks#11|affects|target_closed", out)

    def test_other_types_are_pull(self):
        self.publish("10", [("10", "11", "informs", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PULL:aitasks#11|informs|type_not_pushed", out)

    def test_disabled_with_saved_relations_never_pushes(self):
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("PUSH:aitasks#11", out)  # control: enabled pushes
        self.enable(False)
        code, out, _ = run(self.root, "notify-candidates", "10", "--option", "disabled", "--log")
        self.assertEqual(code, 0)
        self.assertEqual(self.push_rows(out), [], out)
        self.assertIn("PUSH_NONE:disabled", out)
        self.assertIn("PULL:aitasks#11|affects|relations_disabled", out)
        self.assertIn(f"CHANGED_FILE:{SHARED}", out)
        self.assertIn(f"SUMMARY:{rc.DISABLED_TEXT}", out)
        summary = [r for r in self.ledger("notify") if r.get("kind") == "summary"]
        self.assertEqual(summary[-1]["analysis_state"], "disabled")
        self.assertEqual(summary[-1]["option"], "disabled")
        self.assertEqual(summary[-1]["push"], 0)

    def test_empty_changeset_warns(self):
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10", "--rev", "HEAD~1")
        self.assertIn("CHANGESET:0|commits:HEAD~1", out)
        self.assertTrue(lines_with(out, "WARN:no change found"), out)
        self.assertIn("PULL:aitasks#11|affects|unconfirmed_impact", out)


# =============================================================== change sets

class ChangeSetTests(CBase):
    def test_subject_token_is_exact(self):
        a = code_commit(self.root, "feature: A (t10)", {"a.py": "1\n"})
        code_commit(self.root, "feature: B (t100)", {"b.py": "1\n"})
        code_commit(self.root, "ait: mentions (t10) in body only", {"c.py": "1\n"})
        commits = rc.commits_for(str(self.root), "10")
        self.assertIn(a, commits)
        self.assertEqual(len([c for c in commits]), 2)  # A and the ait: subject carrying (t10)
        b_only = rc.commits_for(str(self.root), "100")
        self.assertEqual(len(b_only), 1)

    def test_rename_counts_both_paths_and_hunks(self):
        code_commit(self.root, "chore: add", {"old/name.py": "x = 1\n-- dashed\n"})
        (self.root / "new").mkdir()
        git(self.root, "mv", "old/name.py", "new/name.py")
        sha = code_commit(self.root, "refactor: move (t10)", {})
        cs = rc.changeset_for_commits(str(self.root), [sha], "commits:HEAD")
        self.assertIn("old/name.py", cs.paths)
        self.assertIn("new/name.py", cs.paths)
        sha2 = code_commit(self.root, "fix: edit (t10)", {"new/name.py": "x = 2\n-- dashed\n"})
        cs = rc.changeset_for_commits(str(self.root), [sha2], "commits:HEAD")
        texts = [line for _c, _f, line in cs.hunks]
        self.assertIn("x = 1", texts)
        self.assertIn("x = 2", texts)
        self.assertEqual({f for _c, f, _l in cs.hunks}, {"new/name.py"})

    def test_worktree_branch_via_rev_and_diff_override(self):
        task_file(self.root, "10", C_OLD, f"`{SHARED}`\n", status="Implementing")
        task_file(self.root, "11", C_OLD, f"`{SHARED}`\n", status="Implementing")
        base = git(self.root, "rev-parse", "HEAD")
        code_commit(self.root, "feature: on the task branch (t10)", {SHARED: "y\n"},
                    branch="aitask/t10_name")
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")  # HEAD: nothing landed here
        self.assertIn("PULL:aitasks#11|affects|unconfirmed_impact", out)
        _c, out, _ = run(self.root, "notify-candidates", "10", "--rev", "aitask/t10_name")
        self.assertIn("PUSH:aitasks#11", out)
        _c, out, _ = run(self.root, "notify-candidates", "10", "--diff", f"{base}..aitask/t10_name")
        self.assertIn(f"CHANGESET:0|diff:{base}..aitask/t10_name", out)
        self.assertIn("PUSH:aitasks#11", out)

    def test_dash_range_refused(self):
        with self.assertRaises(ValueError):
            rc.changeset_for_range(str(self.root), "--output=x")


# ============================================================== related work

class RelatedWorkTests(CBase):
    T = "20"

    def setUp(self):
        super().setUp()
        task_file(self.root, self.T, "2026-11-01 10:00", f"T cites `{SHARED}`.\n")

    def landed(self, tid, at="2026-11-05 10:00", reason=None, touch=True):
        meta = {"completed_at": at}
        if reason:
            meta["archived_reason"] = reason
        task_file(self.root, tid, C_OLD, f"L cites `{SHARED}`.\n", status="Done",
                  archived=True, **meta)
        ts.write_plan(self.root, tid, f"---\nTask: t{tid}\n---\n\nplan\n", archived=True)
        if touch:
            code_commit(self.root, f"feature: L (t{tid})", {SHARED: f"{tid}\n"})

    def items(self, out):
        return lines_with(out, "ITEM:")

    def test_pick_groups_direction_and_confirmation(self):
        self.landed("21")                                   # landed, touches the basis
        self.landed("22", reason="superseded", touch=False)  # dropped
        self.landed("25", touch=False)                       # landed, unconfirmed
        self.landed("26", at="2026-10-01 10:00", touch=False)  # before T's creation
        task_file(self.root, "23", C_OLD, "in flight\n", status="Implementing")
        task_file(self.root, "24", C_OLD, "pending\n")
        p = [{"kind": "path", "value": SHARED}]
        self.publish("21", [("21", self.T, "affects", p)])
        self.publish("22", [("22", self.T, "supersedes", p)])
        self.publish("25", [("25", self.T, "coordinates_with", p)])
        self.publish("26", [("26", self.T, "affects", p)])
        self.publish(self.T, [(self.T, "23", "coordinates_with", p), (self.T, "24", "affects", p)])
        code, out, _ = run(self.root, "related-work", self.T, "--point", "pick")
        self.assertEqual(code, 0, out)
        items = self.items(out)
        groups = [i.split("|")[0][len("ITEM:"):] for i in items]
        self.assertEqual(groups, ["landed", "landed", "dropped", "in_flight", "own"], out)
        self.assertIn("|aitasks#21|", items[0])
        self.assertIn("|confirmed_impact|", items[0])
        self.assertIn("aiplans/archived/p21_name.md", items[0])
        self.assertIn("t21 affects this task", items[0])
        self.assertIn("|unconfirmed_impact|", items[1])
        self.assertIn("dropped:superseded@", items[2])
        self.assertIn("BEFORE_REFERENCE:1", out)
        self.assertIn("REFERENCE:", out)
        self.assertTrue(lines_with(out, "SUMMARY:analysed"), out)

    def test_outgoing_edge_to_landed_task_is_own(self):
        self.landed("21")
        self.publish(self.T, [(self.T, "21", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "related-work", self.T, "--point", "pick")
        self.assertTrue(self.items(out)[0].startswith("ITEM:own|this task affects t21|"), out)

    def test_cap_and_more(self):
        p = [{"kind": "path", "value": SHARED}]
        rels = []
        for n in range(30, 40):
            task_file(self.root, str(n), C_OLD, "x\n")
            rels.append((self.T, str(n), "informs", p))
        self.publish(self.T, rels)
        _c, out, _ = run(self.root, "related-work", self.T, "--point", "pick")
        self.assertEqual(len(self.items(out)), 8)
        self.assertIn("MORE:2", out)

    def test_review_late_and_covered_by_note(self):
        p = [{"kind": "path", "value": SHARED}]
        since = "2026-11-06T10:00:00Z"
        task_file(self.root, "40", C_OLD, "pending\n", status="Implementing")
        task_file(self.root, "41", C_OLD, "pending\n", status="Implementing")
        self.landed("42", at="2026-11-07 10:00")
        self.publish("40", [("40", self.T, "affects", p)], at="2026-11-07T09:00:00Z")  # late
        self.publish("41", [("41", self.T, "affects", p)], at="2026-11-01T09:00:00Z")  # old
        self.publish("42", [("42", self.T, "affects", p)], at="2026-11-01T09:00:00Z")  # landed
        nid, block = note_block("t42", "2026-11-07T11:00:00Z")
        old_nid, old_block = note_block("t40", "2026-11-05T11:00:00Z", "d" * 24)
        path = self.root / ts.task_relpath(self.T)
        path.write_text(path.read_text() + block + old_block.replace("\n## Inbox\n", "")
                        + receipt_block(f"t{self.T}", [nid]))
        _c, out, _ = run(self.root, "related-work", self.T, "--point", "review", "--since", since)
        items = self.items(out)
        self.assertEqual(len(items), 2, out)
        landed = next(i for i in items if "aitasks#42" in i)
        late = next(i for i in items if "aitasks#40" in i)
        self.assertTrue(landed.startswith("ITEM:landed|"))
        self.assertIn(f"covered_by_note={nid}", landed)   # acknowledged still covers
        self.assertTrue(late.startswith("ITEM:late|"))
        self.assertNotIn("covered_by_note", late)          # its note predates since
        self.assertIn("REFERENCE:2026-11-06T10:00:00Z|since", out)

    def test_note_point_lists_open_ends_only(self):
        self.landed("21")
        task_file(self.root, "23", C_OLD, "x\n", status="Implementing")
        p = [{"kind": "path", "value": SHARED}]
        self.publish(self.T, [(self.T, "21", "affects", p), (self.T, "23", "coordinates_with", p)])
        _c, out, _ = run(self.root, "related-work", self.T, "--point", "note")
        items = self.items(out)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].startswith("ITEM:in_flight|"))

    def test_empty_never_stands_alone(self):
        _c, out, _ = run(self.root, "related-work", self.T, "--point", "pick")
        ls = out.splitlines()
        self.assertIn("RELATED_WORK:0", ls)
        self.assertLess(ls.index(next(x for x in ls if x.startswith("SUMMARY:"))),
                        ls.index("RELATED_WORK:0"))
        self.assertIn("SUMMARY:not analysed yet", out)


# ============================================================ completeness

class CompletenessTests(CBase):
    STATES = ("incomplete:pending(queued)", "incomplete:pending(running)",
              "incomplete:failed(TIMEOUT)", "incomplete:missing", "incomplete:inputs_mismatch",
              "incomplete:unverifiable(no_stamp)", "incomplete:unverifiable(store_stale)",
              "incomplete:unverifiable(store_unreachable)",
              "incomplete:unverifiable(stamp_mismatch)",
              "incomplete:unverifiable(no_expected_identity)")

    def setUp(self):
        super().setUp()
        task_file(self.root, "10", C_OLD, "Source.\n", status="Implementing")
        ts.write_plan(self.root, "10", "---\nTask: t10\n---\n\nApproved plan.\n")
        code_commit(self.root, "feature: x (t10)", {"a.py": "1\n"})

    def test_incomplete_states_never_read_as_no_targets(self):
        for state in self.STATES:
            with mock.patch.object(rcli, "analysis_state", return_value=(state, None)):
                code, out = inproc(self.root, ["notify-candidates", "10"])
            self.assertEqual(code, 0)
            self.assertIn(f"PUSH_NONE:{state}", out, state)
            self.assertNotIn("PUSH_NONE:complete", out, state)
            self.assertNotIn("no affected targets", out, state)
            self.assertIn("INCOMPLETE", lines_with(out, "SUMMARY:")[0], state)

    def test_expected_identity_real_states(self):
        idx = rst.TaskIndex(str(self.root))
        plan_sha = idx.plan_digest("10")
        self.publish("10", [], stage=2)
        s = ts.S(self.root)
        s.write(rs.store_path("approvals", "10"), ts.stamp(self.root, "10", plan_sha))
        _c, out, _ = run(self.root, "notify-candidates", "10")
        self.assertIn("ANALYSIS_STATE:incomplete:unverifiable(no_expected_identity)", out)
        _c, out, _ = run(self.root, "notify-candidates", "10", "--expect-plan", plan_sha)
        self.assertIn("ANALYSIS_STATE:complete", out)
        self.assertIn("PUSH_NONE:complete", out)
        self.assertIn("no affected targets", out)
        self.assertIn("RECORD:stage=2|source=fresh", out)
        # a resumed session whose committed plan is newer than the visible stamp
        _c, out, _ = run(self.root, "notify-candidates", "10", "--expect-plan", "f" * 64)
        self.assertIn("ANALYSIS_STATE:incomplete:unverifiable(stamp_mismatch)", out)
        self.assertIn("PUSH_NONE:incomplete:unverifiable(stamp_mismatch)", out)

    def test_missing_record(self):
        idx = rst.TaskIndex(str(self.root))
        plan_sha = idx.plan_digest("10")
        ts.S(self.root).write(rs.store_path("approvals", "10"), ts.stamp(self.root, "10", plan_sha))
        _c, out, _ = run(self.root, "notify-candidates", "10", "--expect-plan", plan_sha)
        self.assertIn("ANALYSIS_STATE:incomplete:missing", out)
        self.assertIn("RECORD:none", out)
        self.assertIn("PUSH_NONE:incomplete:missing", out)


# ===================================================== wording, ledgers, cost

class WordingLedgerTests(CBase):
    def setUp(self):
        super().setUp()
        task_file(self.root, "10", C_OLD, f"`{SHARED}`\n", status="Implementing")
        task_file(self.root, "11", C_OLD, f"`{SHARED}`\n", status="Implementing")
        code_commit(self.root, "feature: x (t10)", {SHARED: "1\n"})

    def test_disabled_wording_identical_everywhere(self):
        self.enable(False)
        seen = set()
        for point in rc.POINTS:
            _c, out, _ = run(self.root, "related-work", "10", "--point", point)
            seen.add(lines_with(out, "SUMMARY:")[0])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        seen.add(lines_with(out, "SUMMARY:")[0])
        self.assertEqual(seen, {f"SUMMARY:{rc.DISABLED_TEXT}"})

    def test_plain_summary_states(self):
        self.assertEqual(rc.plain_summary("enabled", "fresh@x", "never"), "not analysed yet")
        self.assertEqual(rc.plain_summary("enabled", "fresh@x", "analysed:0(stage=1)"),
                         "analysed, 0 relations (stage 1)")
        self.assertIn("unknown, not none",
                      rc.plain_summary("enabled", "unreachable:timeout", "unknown(store_unreachable)"))
        self.assertIn("switched off on this host",
                      rc.plain_summary("host_off", "local_only", "never"))
        self.assertIn("analysis capped", rc.plain_summary("enabled", "local_only", "pending(capped)"))
        self.assertIn("interrupted_unresolved",
                      rc.plain_summary("enabled", "local_only", "failed(interrupted_unresolved)"))
        self.assertIn("another project", rc.plain_summary("enabled", "local_only",
                                                          "unknown(other_project)"))

    def test_ledgers_rows_and_export(self):
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "related-work", "11", "--point", "pick", "--log")
        _c, out, _ = run(self.root, "notify-candidates", "10", "--option", "proceed", "--log")
        run_id = lines_with(out, "RUN_ID:")[0].split(":", 1)[1]
        code, out2, _ = run(self.root, "notify-outcome", "10", "--run", run_id, "--to",
                            "aitasks#11", "--type", "affects", "--outcome", "sent",
                            "--note-id", "n1")
        self.assertEqual(code, 0)
        self.assertIn("RECORDED:sent|aitasks#11", out2)
        pull = self.ledger("pull")
        shown = [r for r in pull if r.get("outcome") == "shown"]
        self.assertEqual(len(shown), 1)
        for key in ("at", "host", "task", "point", "relation", "freshness", "confirmation"):
            self.assertIn(key, shown[0])
        notify = self.ledger("notify")
        offered = [r for r in notify if r.get("outcome") == "offered"]
        self.assertEqual(offered[0]["relation"]["to"], "aitasks#11")
        self.assertEqual(offered[0]["confirmation"], "confirmed_impact")
        summary = [r for r in notify if r.get("kind") == "summary"][0]
        self.assertEqual((summary["option"], summary["push"]), ("proceed", 1))
        self.assertEqual(summary["analysis_state"], "incomplete:unverifiable(no_expected_identity)")
        outcome = [r for r in notify if r.get("kind") == "outcome"][0]
        self.assertEqual((outcome["run_id"], outcome["note_id"]), (run_id, "n1"))
        _c, exported, _ = run(self.root, "ledgers", "--export")
        names = {json.loads(x)["ledger"] for x in exported.splitlines() if x.strip()}
        self.assertTrue({"pull", "notify"} <= names, exported)

    def test_bad_option_and_since_refused(self):
        code, _o, _e = run(self.root, "notify-candidates", "10", "--option", "sideways")
        self.assertEqual(code, 1)
        code, _o, _e = run(self.root, "related-work", "10", "--point", "review", "--since", "soon")
        self.assertEqual(code, 1)

    # [pick_cost_guard]
    def test_disabled_project_never_fetches(self):
        env = self.new_env("remote")
        root = env.clone("r", remote=True)
        ts.set_config(root, relations_enabled=False)
        task_file(root, "10", C_OLD, "x\n")

        def boom(*_a, **_k):
            raise AssertionError("a disabled project must not fetch")
        with mock.patch.object(rst.ors, "probe_remote_branch", boom), \
                mock.patch.object(rst.ors, "fetch_pinned", boom):
            code, out = inproc(root, ["related-work", "10", "--point", "pick"])
            code2, out2 = inproc(root, ["notify-candidates", "10"])
        self.assertEqual((code, code2), (0, 0))
        self.assertIn(f"SUMMARY:{rc.DISABLED_TEXT}", out)
        self.assertIn("PUSH_NONE:disabled", out2)


# [protocol_roundtrip_test]
class ProtocolRoundTripTests(unittest.TestCase):
    HOSTILE = ["plain", "a|b", "100%", "%7C literal", "line1\nline2", "cr\r\nlf", "%0A%25|\n%"]

    def test_enc_dec_round_trip(self):
        for value in self.HOSTILE:
            self.assertEqual(rc.dec(rc.enc(value)), value)
            self.assertNotIn("|", rc.enc(value))
            self.assertNotIn("\n", rc.enc(value))

    def _rel(self, desc, value):
        return rst.Rel(from_="aitasks#1", to="aitasks#2", other="aitasks#2", type="affects",
                       description=desc, basis=[{"kind": "token", "value": value}], evidence=[],
                       record_task="aitasks#1", direction="this task affects t2",
                       freshness="fresh", pending_push=False)

    def test_rows_are_one_line_and_decode(self):
        for desc in self.HOSTILE:
            for value in self.HOSTILE:
                rel = self._rel(desc, value)
                row = rc.Row("PUSH", rel, "aitasks#2", matched=[("token", value, "c|1", f"f|{value}")],
                             confirmation="confirmed_impact")
                push, ev = rc.row_lines(row)
                fields = push.split("|")
                self.assertEqual(len(fields), 4)
                self.assertEqual(rc.dec(fields[3]), desc)
                self.assertEqual(rc.dec(fields[2]), f"token:{value}")
                efields = ev.strip().split("|")
                self.assertEqual(len(efields), 3)
                self.assertEqual(rc.dec(efields[0][len("EVIDENCE:token:"):]), value)
                self.assertEqual(rc.dec(efields[2]), f"f|{value}")
                it = rc.Item("landed", rel, rc.End("landed"), "confirmed_impact", plan="p|x",
                             covered_by_note="n|1")
                head, body = rc.item_lines(it)
                hf = head.split("|")
                self.assertEqual(len(hf), 9)
                self.assertEqual(rc.dec(hf[7]), "p|x")
                self.assertEqual(rc.dec(hf[8][len("covered_by_note="):]), "n|1")
                self.assertEqual(rc.dec(body.strip()), desc)
                for line in (push, ev, head, body):
                    self.assertNotIn("\n", line)
                    self.assertNotIn("\r", line)


class TimeTests(unittest.TestCase):
    def test_parse_time_forms(self):
        self.assertEqual(rc.iso(rc.parse_time("2026-11-08T09:38:00Z")), "2026-11-08T09:38:00Z")
        local = rc.parse_time("2026-11-08 11:38")
        self.assertIsNotNone(local)
        self.assertIsNotNone(local.tzinfo)
        self.assertIsNone(rc.parse_time("soon"))
        self.assertTrue(rc.after(None, local))  # unknown time is shown, never hidden


# ============================================================ skill text

SKILLS = ROOT / ".claude" / "skills"


def render(profile):
    out = subprocess.run([sys.executable, str(ROOT / ".aitask-scripts/lib/skill_template.py"),
                          str(SKILLS / "task-workflow/SKILL.md"),
                          str(ROOT / f"aitasks/metadata/profiles/{profile}.yaml"), "claude"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise unittest.SkipTest(f"renderer unavailable: {out.stderr.strip()[:200]}")
    return out.stdout


def section(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


class SkillTextTests(unittest.TestCase):
    def test_four_surfaces_display_summary_verbatim(self):
        proc = (SKILLS / "task-workflow/related-work-check.md").read_text()
        self.assertIn("Display the `SUMMARY:` line verbatim", proc)
        self.assertIn("## Pick-time check", proc)
        self.assertIn("## Review-time re-check", proc)
        src = (SKILLS / "task-workflow/SKILL.md").read_text()
        check8 = section(src, "**Check 8 - Related work", "If none of the checks trigger")
        self.assertIn("`related-work-check.md`", check8)
        self.assertIn("## Pick-time check", check8)
        step8 = section(src, "### Step 8: User Review and Approval", "- **Show change summary:**")
        self.assertIn("## Review-time re-check", step8)
        step8e = section(src, "### Step 8e:", "### Step 9:")
        self.assertIn("Display its `SUMMARY:` line verbatim", step8e)
        note = (SKILLS / "aitask-note/SKILL.md").read_text()
        self.assertIn("related-work <sender> --point note", note)
        self.assertIn("Display its `SUMMARY:` line", note)

    def test_step8e_branches_converge_on_one_compute_step(self):
        for profile in ("default", "fast", "remote"):
            text = section(render(profile), "### Step 8e:", "### Step 9:")
            c = section(text, "**C. Option-specific work**", "**D. Compute, offer and log**")
            d = section(text, "**D. Compute, offer and log**", "#### Judgement-based offers")
            self.assertIn("**re-run A**", c, profile)
            for opt in ("wait_failed", "wait_refused_cap", "fallback_unavailable"):
                self.assertIn(f"`option={opt}`", c, (profile, opt))
            calls = re.findall(r"aitask_relations\.sh notify-candidates [^\n]*", text)
            self.assertEqual(len(calls), 1, (profile, calls))
            self.assertIn("$EXPECT $REV --option <option> --log", calls[0])
            self.assertIn(calls[0], d)
            self.assertLess(d.index("notify-candidates"), d.index("--fallback-push"), profile)
            self.assertIn("With `option=disabled` the verb prints no `PUSH:` row", d)
            self.assertIn("notify-outcome", d)
            if profile == "remote":
                self.assertIn("not_offered", d)
                self.assertNotIn("multi-select", d)
            else:
                self.assertIn("multi-select", d)

    def test_option_vocabulary_matches_the_verb(self):
        src = (SKILLS / "task-workflow/SKILL.md").read_text()
        step8e = section(src, "### Step 8e:", "### Step 9:")
        named = set(re.findall(r"option=([a-z_]+)", step8e))
        self.assertEqual(named, set(rc.OPTIONS))

    def test_profile_key_documented_and_shipped(self):
        doc = (SKILLS / "task-workflow/profiles.md").read_text()
        self.assertIn("| `relations_incomplete_action` |", doc)
        for base in ("aitasks/metadata/profiles", "seed/profiles"):
            for profile, value in (("default", "ask"), ("fast", "ask"), ("remote", "proceed")):
                text = (ROOT / base / f"{profile}.yaml").read_text()
                self.assertIn(f"\nrelations_incomplete_action: {value}\n", text, (base, profile))


# ======================================================= review-round fixes

class ReviewFixTests(CBase):
    def setUp(self):
        super().setUp()
        task_file(self.root, "10", C_OLD, f"Source `{SHARED}`.\n", status="Implementing")
        task_file(self.root, "11", C_OLD, f"Target `{SHARED}` and `helper_fn`.\n",
                  status="Implementing")

    # --- note targets are the bare ids the writer accepts
    def test_push_and_item_rows_carry_bare_note_target(self):
        code_commit(self.root, "feature: x (t10)", {SHARED: "def helper_fn(): pass\n"})
        self.publish("10", [("10", "11", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "notify-candidates", "10")
        ls = out.splitlines()
        i = next(k for k, x in enumerate(ls) if x.startswith("PUSH:aitasks#11|"))
        self.assertEqual(ls[i + 1], "  NOTE_TARGET:11")
        _c, out, _ = run(self.root, "related-work", "11", "--point", "note")
        self.assertIn("  NOTE_TARGET:10", out.splitlines())
        store = rst.Store(str(self.root))
        self.assertEqual(rc.note_target(store, "aitasks#12_3"), "12_3")
        self.assertEqual(rc.note_target(store, "mobile#42"), "42|project=mobile")
        for line in lines_with(out, "  NOTE_TARGET:"):
            self.assertRegex(line.strip(), r"^NOTE_TARGET:\d+(_\d+)?(\|project=[a-z0-9_-]+)?$")

    def test_skill_text_uses_note_target_not_qualified_ref(self):
        src = (SKILLS / "task-workflow/SKILL.md").read_text()
        d = section(section(src, "### Step 8e:", "### Step 9:"), "**D. Compute", "#### Judgement")
        self.assertIn("`/aitask-note <target> --from <task_id>`", d)
        self.assertIn("`NOTE_TARGET:` value", d)
        self.assertNotIn("/aitask-note <to>", d)
        note = (SKILLS / "aitask-note/SKILL.md").read_text()
        self.assertIn("`NOTE_TARGET:` value", note)

    # --- an unreadable or empty change set is never an all-clear
    def _complete(self):
        ts.write_plan(self.root, "10", "---\nTask: t10\n---\n\nApproved.\n")
        sha = rst.TaskIndex(str(self.root)).plan_digest("10")
        self.publish("10", [], stage=2)
        ts.S(self.root).write(rs.store_path("approvals", "10"), ts.stamp(self.root, "10", sha))
        return sha

    def test_unreadable_changeset_is_not_all_clear(self):
        sha = self._complete()
        _c, out, _ = run(self.root, "notify-candidates", "10", "--expect-plan", sha,
                         "--diff", "no-such-ref..HEAD")
        self.assertIn("ANALYSIS_STATE:complete", out)        # the verdict is kept
        self.assertIn("PUSH_NONE:changeset_unreadable", out)
        self.assertNotIn("PUSH_NONE:complete", out)
        self.assertNotIn("no affected targets", out)
        self.assertIn("unknown", lines_with(out, "SUMMARY:")[0])

    def test_empty_changeset_is_not_all_clear(self):
        sha = self._complete()
        _c, out, _ = run(self.root, "notify-candidates", "10", "--expect-plan", sha)
        self.assertIn("ANALYSIS_STATE:complete", out)
        self.assertIn("PUSH_NONE:changeset_empty", out)
        self.assertNotIn("no affected targets", out)
        code_commit(self.root, "feature: real (t10)", {"z.py": "1\n"})
        _c, out, _ = run(self.root, "notify-candidates", "10", "--expect-plan", sha)
        self.assertIn("PUSH_NONE:complete", out)            # control
        self.assertIn("no affected targets", out)

    # --- bundled archived plans are located (extracted)
    @unittest.skipUnless(ts.HAVE_ZSTD, "zstd not installed")
    def test_bundled_plan_is_extracted_and_located(self):
        task_file(self.root, "21", C_OLD, f"L `{SHARED}`.\n", status="Done", archived=True,
                  completed_at="2026-11-05 10:00")
        idx = rst.TaskIndex(str(self.root))
        bundle = rc.archive_iter.archive_path_for_id(21, idx.plan_archived_dir)
        ts.make_bundle(bundle, {"p21_name.md": "---\nTask: t21\n---\n\nBundled plan body.\n"})
        task_file(self.root, "20", "2026-11-01 10:00", "T\n")
        self.publish("21", [("21", "20", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "related-work", "20", "--point", "pick")
        item = lines_with(out, "ITEM:landed|")[0]
        plan = rc.dec(item.split("|")[7])
        self.assertNotEqual(plan, "-", out)
        self.assertTrue(os.path.isabs(plan))
        self.assertIn("Bundled plan body.", Path(plan).read_text())

    # --- the lock reference time never fetches
    def test_review_without_since_reads_local_lock_ref_only(self):
        env = self.new_env("remote")
        root = env.clone("r", remote=True)
        ts.set_config(root, relations_enabled=False)
        task_file(root, "10", C_OLD, "x\n", status="Implementing")
        git(root, "commit", "-q", "--allow-empty", "-m", "init")
        lock = "task_id: 10\nlocked_by: a@b\nlocked_at: 2026-11-08 11:38\nhostname: h\n"
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=root, input=lock,
                              capture_output=True, text=True, check=True).stdout.strip()
        tree = subprocess.run(["git", "mktree"], cwd=root, input=f"100644 blob {blob}\tt10_lock.yaml\n",
                              capture_output=True, text=True, check=True).stdout.strip()
        commit = git(root, "commit-tree", tree, "-m", "lock")
        git(root, "update-ref", "refs/remotes/origin/aitask-locks", commit)
        real_git = rst.ors.git

        def guarded(repo, *args, **kw):
            if args and args[0] in ("fetch", "ls-remote", "push"):
                raise AssertionError(f"network git call: {args}")
            return real_git(repo, *args, **kw)

        def boom(*_a, **_k):
            raise AssertionError("a disabled project must not fetch")
        real_run = subprocess.run

        def no_lock_script(argv, *a, **kw):
            if any(str(x).endswith("aitask_lock.sh") for x in argv):
                raise AssertionError("aitask_lock.sh --check fetches; it must not run here")
            return real_run(argv, *a, **kw)
        with mock.patch.object(rst.ors, "git", guarded), \
                mock.patch.object(rst.ors, "probe_remote_branch", boom), \
                mock.patch.object(rst.ors, "fetch_pinned", boom), \
                mock.patch.object(subprocess, "run", no_lock_script):
            code, out = inproc(root, ["related-work", "10", "--point", "review"])
        self.assertEqual(code, 0)
        self.assertIn(f"SUMMARY:{rc.DISABLED_TEXT}", out)
        ref = lines_with(out, "REFERENCE:")[0]
        self.assertTrue(ref.endswith("|lock"), ref)
        self.assertEqual(rc.parse_time("2026-11-08 11:38"), rc.parse_time(ref.split(":", 1)[1].split("|")[0]))

    # --- deletions and quoted paths keep the real file name
    def test_deleted_file_hunks_keep_old_path(self):
        code_commit(self.root, "chore: add", {SHARED: "def helper_fn():\n    pass\n"})
        sha = code_commit(self.root, "refactor: drop (t10)", {SHARED: None})
        cs = rc.changeset_for_commits(str(self.root), [sha], "x")
        self.assertIn(SHARED, cs.paths)
        files = {f for _c, f, _l in cs.hunks}
        self.assertEqual(files, {SHARED})
        status, matched = rc.confirm([{"kind": "symbol", "value": "helper_fn"}], cs)
        self.assertEqual((status, matched[0][3]), ("confirmed_impact", SHARED))

    def test_quoted_paths_are_unquoted(self):
        name = "lib/café x\tt.py"
        code_commit(self.root, "chore: add", {name: "a = 1\n"})
        sha = code_commit(self.root, "fix: edit (t10)", {name: "a = 2\n"})
        cs = rc.changeset_for_commits(str(self.root), [sha], "x")
        self.assertIn(name, cs.paths)
        self.assertEqual({f for _c, f, _l in cs.hunks}, {name})
        sha2 = code_commit(self.root, "fix: drop (t10)", {name: None})
        cs = rc.changeset_for_commits(str(self.root), [sha2], "x")
        self.assertEqual({f for _c, f, _l in cs.hunks}, {name})
        self.assertEqual(rc._unquote('"a\\\\b\\"c\\303\\251"'), 'a\\b"cé')


class RoundTwoFixTests(CBase):
    def test_active_done_task_is_not_landed(self):
        task_file(self.root, "20", "2026-11-01 10:00", f"T `{SHARED}`.\n", status="Implementing")
        task_file(self.root, "21", C_OLD, f"done, not archived `{SHARED}`.\n", status="Done",
                  completed_at="2026-11-05 10:00")
        code_commit(self.root, "feature: L (t21)", {SHARED: "1\n"})
        store = rst.Store(str(self.root))
        self.assertEqual(rc.end_state(store, "aitasks#21").label(), "pending:Done")
        self.publish("21", [("21", "20", "affects", [{"kind": "path", "value": SHARED}])])
        _c, out, _ = run(self.root, "related-work", "20", "--point", "pick")
        self.assertFalse(lines_with(out, "ITEM:landed|"), out)
        self.assertTrue(lines_with(out, "ITEM:pending|"), out)
        # control: once archived it is landed
        (self.root / ts.task_relpath("21")).unlink()
        task_file(self.root, "21", C_OLD, f"archived `{SHARED}`.\n", status="Done", archived=True,
                  completed_at="2026-11-05 10:00")
        _c, out, _ = run(self.root, "related-work", "20", "--point", "pick")
        self.assertTrue(lines_with(out, "ITEM:landed|"), out)

    @unittest.skipUnless(ts.HAVE_ZSTD, "zstd not installed")
    def test_plan_extraction_only_for_shown_rows(self):
        task_file(self.root, "20", "2026-11-01 10:00", "T\n")
        task_file(self.root, "21", C_OLD, "L\n", status="Done", archived=True,
                  completed_at="2026-11-05 10:00")
        idx = rst.TaskIndex(str(self.root))
        bundle = rc.archive_iter.archive_path_for_id(21, idx.plan_archived_dir)
        ts.make_bundle(bundle, {"p21_name.md": "---\nTask: t21\n---\n\nBundled.\n"})
        self.publish("21", [("21", "20", "affects", [{"kind": "path", "value": SHARED}])])
        extract = Path(rst.Store(str(self.root)).state_dir) / "archived-plans"
        _c, out, _ = run(self.root, "related-work", "20", "--point", "note")
        self.assertIn("RELATED_WORK:0", out)
        self.assertFalse(extract.exists() and any(extract.iterdir()), "note view extracted a plan")
        _c, out, _ = run(self.root, "related-work", "20", "--point", "pick")  # control
        self.assertTrue((extract / "p21_name.md").exists())


if __name__ == "__main__":
    unittest.main()
