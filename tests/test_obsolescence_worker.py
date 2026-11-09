"""Tests for the obsolescence job, the landed fan-out and ``ait obsolete`` (t1981_6).

Builds on test_relations_worker.WBase: a legacy-mode scratch repo with tasks 10
and 11, the stub candidate provider and the stub agent (whose ``payload`` key
answers for the obsolescence op). The premise engine is replaced through
AIT_OBSOLESCENCE_PREMISE_CMD.

Run: python3 tests/test_obsolescence_worker.py
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

import test_relations_store as ts  # noqa: E402
import test_relations_worker as tw  # noqa: E402
from test_relations_worker import rs, rsp, rst, rw  # noqa: E402

import obsolete_cli as ocli  # noqa: E402

OBS = str(tw.REPO / ".aitask-scripts" / "aitask_obsolete.sh")
GOOD = {"band": "medium", "disposition": "fold_into", "fold_target": "aitasks#11",
        "reasons": [{"text": "t11 records the same goal.", "evidence_ids": ["duplicate_of:1"]}]}


def premise_stub(tmp, decision="SKIP", rc=0):
    path = Path(tmp) / f"premise_{decision}_{rc}.sh"
    path.write_text(f"#!/usr/bin/env bash\necho 'DISPLAY:stub'\necho 'DECISION:{decision}'\nexit {rc}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


class OBase(tw.WBase):
    def setUp(self):
        super().setUp()
        self._prem = mock.patch.dict(os.environ, {
            "AIT_OBSOLESCENCE_PREMISE_CMD": premise_stub(self.tmp)})
        self._prem.start()
        self.agent("ok", payload=GOOD)

    def tearDown(self):
        self._prem.stop()
        super().tearDown()

    # -------------------------------------------------------------- helpers
    def write(self, tid, body, status="Ready", archived=False, extra=(), created=None):
        fm = [f"status: {status}", f"created_at: {created or tw.C12}", *extra]
        path = self.root / ts.task_relpath(tid, archived)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body, encoding="utf-8")
        return path

    def duplicate(self, frm="11", to="10"):
        out = self.store().write(rs.store_path("records", frm),
                                 ts.record(self.root, frm, [(frm, to, "duplicates")]))
        self.assertTrue(any(x.startswith("PUBLISHED:") for x in out), out)

    def run_obs(self, tid="10", trigger="manual"):
        sp = self.sp()
        sp.enqueue("obsolescence", trigger, tid, settle_s=0)
        job = sp.claim()
        self.assertIsNotNone(job)
        rw.process_job(str(self.root), sp, job)
        return sp

    def obs(self, tid="10"):
        return self.store().read(no_fetch=True).files.get(rs.store_path("obsolescence", tid))

    def jobs(self, tid=None):
        rows, _ = self.sp().read_ledger()
        return [r for r in rows if r.get("kind") == "job" and r.get("op") == "obsolescence"
                and (tid is None or r.get("task") == tid)]

    def latest_work(self):
        base = Path(rw.state_dir(str(self.root))) / "spool" / "work"
        return max(base.iterdir(), key=lambda p: p.stat().st_mtime)

    def cli(self, *args, stdin="", env=None):
        e = dict(os.environ, **(env or {}))
        proc = subprocess.run([OBS, *args], cwd=str(self.root), input=stdin, capture_output=True,
                              text=True, env=e, timeout=120)
        return proc.returncode, proc.stdout, proc.stderr


# ===================================================================== job

class JobTests(OBase):
    def test_context_only_is_none_without_an_agent(self):
        self.run_obs()
        rec = self.obs()
        self.assertEqual((rec["band"], rec["disposition"], rec["reasons"], rec["evidence"]),
                         ("none", "keep", [], []))
        self.assertEqual(self.launch_count(), 0)
        self.assertTrue(self.jobs("10")[-1]["outcome"].startswith("ASSESSED("))

    def test_signal_row_is_assessed_and_validated(self):
        self.duplicate()
        self.run_obs()
        rec = self.obs()
        self.assertEqual(rec["band"], "medium")
        self.assertEqual(rec["fold_target"], "aitasks#11")
        self.assertEqual([e["kind"] for e in rec["evidence"]], ["duplicate_of"])
        self.assertEqual(self.launch_count(), 1)
        self.assertEqual([c["op"] for c in self.calls()], ["obsolescence"])

    def _rejected(self, payload):
        self.duplicate()
        self.agent("ok", payload=payload)
        self.run_obs()
        self.assertIsNone(self.obs())
        self.assertTrue(self.jobs("10")[-1]["outcome"].startswith("FAILED:INVALID_OUTPUT"),
                        self.jobs("10")[-1])
        outcomes = self.outcomes()
        self.assertEqual([o["outcome"] for o in outcomes.values()], ["invalid_output"])

    def test_unknown_evidence_id_is_rejected(self):
        self._rejected(dict(GOOD, reasons=[{"text": "x", "evidence_ids": ["path_deleted:1"]}]))

    def test_unexplained_warning_is_rejected(self):
        self._rejected({"band": "high", "reasons": [], "disposition": "drop"})

    def test_none_with_an_action_is_rejected(self):
        self._rejected({"band": "none", "reasons": [{"text": "x", "evidence_ids": ["duplicate_of:1"]}],
                        "disposition": "drop"})

    def test_fold_into_needs_an_allowed_target(self):
        self._rejected(dict(GOOD, fold_target=None))

    def test_fold_into_self_is_not_allowed(self):
        self._rejected(dict(GOOD, fold_target="aitasks#10"))

    def test_schema_refuses_unexplained_records(self):
        base = {"schema": rs.SCHEMA, "task": "aitasks#1", "task_created_at": "x",
                "run": {"id": "r", "trigger": "manual", "stage": 1, "at": "x"},
                "inputs": {"body_sha256": "a" * 64, "plan_sha256": None, "evidence_digest": "c" * 64},
                "evidence": [{"id": "e:1", "kind": "duplicate_of", "detail": "d", "source": "s"}]}
        for bad in ({"band": "high", "reasons": [], "disposition": "drop"},
                    {"band": "low", "reasons": [], "disposition": "keep"},
                    {"band": "none", "reasons": [{"text": "t", "evidence_ids": ["e:1"]}],
                     "disposition": "drop"},
                    {"band": "low", "reasons": [{"text": "t", "evidence_ids": []}], "disposition": "keep"},
                    {"band": "none", "reasons": [], "disposition": "keep", "fold_target": "aitasks#2"}):
            with self.subTest(bad=bad), self.assertRaises(rs.SchemaError):
                rs.validate("obsolescence", "obsolescence/t1.json", dict(base, **bad))
        rs.validate("obsolescence", "obsolescence/t1.json",
                    dict(base, band="none", reasons=[], disposition="keep"))

    def test_up_to_date_on_a_rerun(self):
        self.duplicate()
        self.run_obs()
        self.run_obs()
        self.assertEqual(self.jobs("10")[-1]["outcome"], "UP_TO_DATE")
        self.assertEqual(self.launch_count(), 1)

    def test_archived_task_is_excluded(self):
        self.write("15", "Done.\n", status="Done", archived=True)
        self.run_obs("15")
        self.assertEqual(self.jobs("15")[-1]["outcome"], "EXCLUDED")

    def test_incomplete_evidence_fails_never_none(self):
        with mock.patch.dict(os.environ, {"AIT_OBSOLESCENCE_PREMISE_CMD": premise_stub(self.tmp, rc=1)}):
            self.run_obs()
        self.assertIsNone(self.obs())
        self.assertTrue(self.jobs("10")[-1]["outcome"].startswith("FAILED:EVIDENCE_INCOMPLETE"))

    def test_cap_is_per_op(self):
        self.config(max_jobs_per_day=1)
        self.sp().admit("relations", "11", "manual", cap=1)  # relations' only slot
        self.duplicate()
        self.run_obs()
        self.assertEqual(self.obs()["band"], "medium")


class ScoringInputTests(OBase):
    """Context rows (path facts) never reach the assessor nor the citable ids."""

    def setUp(self):
        super().setUp()
        tw.git(self.root, "add", "-A")
        for path, text in (("src/k/a.py", "1"),):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(text)
        tw.git(self.root, "add", "-A")
        tw.git(self.root, "commit", "-q", "-m", "a")
        (self.root / "src/k2").mkdir(parents=True, exist_ok=True)
        tw.git(self.root, "mv", "src/k/a.py", "src/k2/b.py")
        tw.git(self.root, "commit", "-q", "-m", "a->b")
        self.task("10", tw.C10, "Source goal: change `src/k/a.py`.\n")
        self.commit()
        self.duplicate()

    def dry_prompt(self):
        sp = self.sp()
        outcome, _rec = rw.analyse_obsolescence(str(self.root), sp,
                                                {"op": "obsolescence", "task": "10", "trigger": "manual"},
                                                dry_run=True)
        self.assertEqual(outcome, "ASSESSED")
        work = self.latest_work()
        # The per-run work directory is the only intended difference between runs.
        prompt = (work / "prompt.md").read_bytes().replace(str(work).encode(), b"<WORK>")
        return prompt, (work / "inputs" / "evidence.json").read_bytes()

    def test_path_rows_are_not_in_the_prompt_nor_citable(self):
        code, out, _ = self.cli("evidence", "10", "--no-fetch")
        self.assertIn("|path_renamed|context|", out)
        prompt, evidence = self.dry_prompt()
        self.assertNotIn(b"path_", prompt)
        self.assertNotIn(b"path_", evidence)
        self.agent("ok", payload=dict(GOOD, reasons=[{"text": "x", "evidence_ids": ["path_renamed:1"]}]))
        self.run_obs()
        self.assertIsNone(self.obs())
        self.assertTrue(self.jobs("10")[-1]["outcome"].startswith("FAILED:INVALID_OUTPUT"))

    def test_changed_path_fact_leaves_scoring_inputs_identical(self):
        first = self.dry_prompt()
        self.run_obs()
        rec = self.obs()
        self.assertNotIn("path_", json.dumps(rec["evidence"]))
        (self.root / "src/k3").mkdir(parents=True, exist_ok=True)
        tw.git(self.root, "mv", "src/k2/b.py", "src/k3/c.py")
        tw.git(self.root, "commit", "-q", "-m", "b->c")
        second = self.dry_prompt()
        self.assertEqual(first, second)
        self.run_obs()
        self.assertEqual(self.jobs("10")[-1]["outcome"], "UP_TO_DATE")
        _code, out, _ = self.cli("evidence", "10", "--no-fetch")
        self.assertIn("src/k3/c.py", out)


# ================================================================== landed

class LandedTests(OBase):
    def test_fanout_targets(self):
        self.write("50", "Landed.\n", status="Done", archived=True,
                   extra=["completed_at: 2026-11-05 10:00"])
        self.write("13", "Follow-up of 50.\n", extra=["verifies: [50]"])
        self.write("14", "MV of 50.\n", extra=["verifies: [50]", "issue_type: manual_verification"])
        self.write("16", "Archived follow-up.\n", status="Done", archived=True, extra=["verifies: [50]"])
        out = self.store().write(rs.store_path("records", "50"),
                                 ts.record(self.root, "50", [("50", "10", "affects"),
                                                             ("50", "16", "affects")]))
        self.assertTrue(any(x.startswith("PUBLISHED:") for x in out), out)
        self.assertEqual(rw.landed_targets(str(self.root), "50"), ["10", "13"])

    def test_disabled_reads_nothing_and_enqueues_nothing(self):
        self.config(enabled=False)
        sp = self.sp()
        with mock.patch.object(rw, "landed_targets", side_effect=AssertionError("read")):
            rw.cmd_enqueue(str(self.root), "obsolescence", "landed", "50")
        self.assertIn("ENQUEUE:obsolescence|landed|t50|SKIPPED:disabled",
                      Path(sp.log_path).read_text())
        self.assertEqual(sp.list_jobs(), [])

    def test_enabled_fanout_enqueues_each_target(self):
        self.write("13", "Follow-up of 50.\n", extra=["verifies: [50]"])
        self.write("50", "Landed.\n", status="Done", archived=True)
        sp = self.sp()
        with mock.patch.object(rw, "start_worker_detached", return_value=False):
            rw.cmd_enqueue(str(self.root), "obsolescence", "landed", "50")
        self.assertEqual(sorted(j["task"] for j in sp.list_jobs()), ["13"])
        self.assertIn("LANDED_FANOUT:t50|1", Path(sp.log_path).read_text())


# ===================================================================== CLI

class CliTests(OBase):
    def assess(self):
        self.duplicate()
        self.run_obs()

    def test_dismiss_hides_until_the_digest_changes(self):
        self.assess()
        _c, out, _ = self.cli("ls")
        self.assertIn("OBSOLETE:t10|medium|fold_into:aitasks#11|fresh|reasons=1", out)
        code, out, _ = self.cli("dismiss", "10", "--note", "still wanted")
        self.assertEqual(code, 0, out)
        self.assertIn("DISMISSED:t10|", out)
        _c, out, _ = self.cli("ls")
        self.assertIn("OBSOLETE:0", out)
        _c, out, _ = self.cli("ls", "--all")
        self.assertIn("|dismissed", out)
        _c, out, _ = self.cli("show", "10")
        self.assertIn("DISMISSED:current|", out)
        # New evidence -> a new digest -> it resurfaces.
        self.write("12", "Supersedes 10.\n")
        out2 = self.store().write(rs.store_path("records", "12"),
                                  ts.record(self.root, "12", [("12", "10", "supersedes")]))
        self.assertTrue(any(x.startswith("PUBLISHED:") for x in out2), out2)
        self.agent("ok", payload=dict(GOOD, reasons=[{"text": "x", "evidence_ids": ["superseded_by:1"]}]))
        self.run_obs()
        _c, out, _ = self.cli("ls")
        self.assertIn("OBSOLETE:t10|medium|", out)
        _c, out, _ = self.cli("show", "10")
        self.assertIn("DISMISSED:stale|", out)

    def test_show_and_no_assessment(self):
        code, out, _ = self.cli("show", "11")
        self.assertEqual(code, 1)
        self.assertIn("NO_ASSESSMENT:t11", out)
        self.assess()
        _c, out, _ = self.cli("show", "10")
        self.assertIn("REASON:duplicate_of:1|", out)
        self.assertIn("CONTEXT:see ait obsolete evidence 10", out)
        self.assertTrue(out.startswith("RELATIONS_STATE:enabled\nSTORE:"), out)

    def dismissal_exists(self):
        return rs.store_path("dismissals", "10") in self.store().read(no_fetch=True).files

    def test_review_never_acts_without_an_explicit_choice(self):
        self.assess()
        code, out, _ = self.cli("review", stdin="")
        self.assertIn("REVIEW_ENDED:eof", out)
        self.assertFalse(self.dismissal_exists())
        code, out, err = self.cli("review", stdin="x\n\ns\n")
        self.assertIn("SKIPPED:t10", out)
        self.assertIn("Choose one of", err)
        self.assertFalse(self.dismissal_exists())
        code, out, _ = self.cli("review", stdin="d\n\n")
        self.assertIn("DISMISSED:t10|", out)
        self.assertTrue(self.dismissal_exists())

    def snapshot(self):
        files = {p: p.read_text() for p in (self.root / "aitasks").rglob("*.md")}
        return files, tw.git(self.root, "status", "--porcelain")

    def test_review_fold_refusals_mutate_nothing(self):
        self.assess()
        self.commit()
        before = self.snapshot()
        cases = [
            ("f\n10\n", "FOLD_REFUSED:is_self", None),
            ("f\n99\n", "FOLD_REFUSED:99|not_found", None),
            ("f\n\ny\n", "FOLD_REFUSED:10|status_Implementing",
             "sed -i 's/^status: Ready/status: Implementing/' aitasks/t10_name.md"),
        ]
        for stdin, needle, hook in cases:
            with self.subTest(needle=needle):
                env = {"AIT_OBSOLETE_REVIEW_PRE_MUTATE_HOOK": hook} if hook else {}
                _c, out, _ = self.cli("review", stdin=stdin, env=env)
                self.assertIn(needle, out)
                if hook:  # undo the hook's simulated concurrent change, then compare
                    p = self.root / "aitasks/t10_name.md"
                    p.write_text(p.read_text().replace("status: Implementing", "status: Ready"))
                self.assertEqual(self.snapshot(), before)

    def test_review_fold_into_an_implementing_destination_is_refused(self):
        self.assess()
        p = self.root / "aitasks/t11_name.md"
        p.write_text(p.read_text().replace("status: Ready", "status: Implementing"))
        self.commit()
        before = self.snapshot()
        _c, out, _ = self.cli("review", stdin="f\n\n")
        self.assertIn("FOLD_REFUSED:11|status_Implementing", out)
        self.assertEqual(self.snapshot(), before)

    def test_review_valid_fold(self):
        self.assess()
        self.commit()
        _c, out, err = self.cli("review", stdin="f\n\ny\n")
        self.assertIn("FOLDED:t10|t11", out, err)
        self.assertIn("folded_into: 11", (self.root / "aitasks/t10_name.md").read_text())

    def test_sweep_cli_budget_and_disabled(self):
        with mock.patch.dict(os.environ, {"AIT_RELATIONS": "1"}):
            code, out, _ = self.cli("sweep", "--budget", "0")
        self.assertEqual(code, 0, out)
        self.assertIn("SWEEP:0|budget=0|candidates=2", out)
        self.config(enabled=False)
        code, out, _ = self.cli("sweep")
        self.assertEqual(code, 1)
        self.assertIn("DISABLED:", out)


# =================================================================== sweep

class SweepTests(OBase):
    def order(self):
        store = self.store()
        return ocli.sweep_order(str(self.root), store, store.read(no_fetch=True), self.sp())

    def sweep(self, n=3):
        picks = []
        for _ in range(n):
            pick = self.order()[0]
            picks.append(pick)
            self.run_obs(pick, trigger="sweep")
        return picks

    def test_a_permanent_failure_cannot_starve_assessed_tasks(self):
        self.run_obs("10")
        self.run_obs("11")
        self.write("12", "Bad origin.\n", extra=["verifies: [not-an-id]"])
        picks = self.sweep(4)
        # Boosted once (never assessed), then strict rotation by last attempt.
        self.assertEqual(picks, ["12", "10", "11", "12"])
        self.assertIsNone(self.obs("12"))
        self.assertTrue(all(j["outcome"].startswith("FAILED:EVIDENCE_INCOMPLETE")
                            for j in self.jobs("12")))

        # Control: a "no record first" group rule picks the failing task every time.
        def group_rule():
            snap = self.store().read(no_fetch=True)
            ids = ocli._active_eligible(self.store())
            return sorted(ids, key=lambda t: (rs.store_path("obsolescence", t) in snap.files,
                                              ocli._id_key(t)))[0]
        self.assertEqual(group_rule(), "12")

    def test_rotation_revisits_a_task_whose_evidence_changed(self):
        self.write("60", "Origin.\n")
        self.write("12", "Follow-up.\n", extra=["verifies: [60]"])
        for tid in ("10", "11", "12", "60"):
            self.run_obs(tid)
        self.assertEqual(self.obs("12")["band"], "none")
        first = self.sweep(1)
        # The origin is archived as superseded: a signal change, body and plan unchanged.
        (self.root / "aitasks/t60_name.md").unlink()
        self.write("60", "Origin.\n", status="Done", archived=True,
                   extra=["archived_reason: superseded"])
        self.agent("ok", payload={"band": "low", "disposition": "keep",
                                  "reasons": [{"text": "origin superseded",
                                               "evidence_ids": ["origin_state:1"]}]})
        picks = first + self.sweep(2)
        self.assertEqual(picks, ["10", "11", "12"])
        rec = self.obs("12")
        self.assertEqual([e["kind"] for e in rec["evidence"]], ["origin_state"])
        self.assertEqual(rec["band"], "low")
        # Control: ordering existing records by id would pick t10 every time.
        self.assertEqual(sorted(("10", "11", "12"), key=ocli._id_key)[0], "10")


# ============================================ incomplete relation snapshots

class SnapshotGapTests(OBase):
    def corrupt(self, path):
        import orphan_ref_store as ors
        ref = "refs/heads/aitask-relations"
        base = ors.resolve(str(self.root), ref)
        new = ors.build_commit(str(self.root), base, {path: b"{not json"}, "corrupt")
        self.assertEqual(ors.cas_local(str(self.root), ref, new, base), "OK")

    def test_corrupt_relation_record_never_yields_an_all_clear(self):
        self.duplicate()
        self.run_obs()
        before = self.obs()
        self.assertEqual(before["band"], "medium")
        self.corrupt("records/t11.json")
        self.assertTrue(any(c.startswith("records/t11.json|")
                            for c in self.store().read(no_fetch=True).corrupt))
        self.run_obs()
        self.assertTrue(self.jobs("10")[-1]["outcome"].startswith(
            "FAILED:EVIDENCE_INCOMPLETE:store_corrupt:records/t11.json"), self.jobs("10")[-1])
        self.assertEqual(self.obs(), before)          # the assessment was not replaced
        _c, out, _ = self.cli("evidence", "10", "--no-fetch")
        self.assertIn("INCOMPLETE:store_corrupt:records/t11.json", out)

    def test_corrupt_store_never_publishes_a_first_assessment(self):
        self.duplicate()
        self.corrupt("records/t11.json")
        self.run_obs()
        self.assertIsNone(self.obs())
        self.assertEqual(self.launch_count(), 0)

    def test_snapshot_states(self):
        import obsolescence_evidence as oe

        def snap(state, corrupt=()):
            return rst.Snapshot(state=state, base=None, files={}, pending=set(), corrupt=list(corrupt))
        for ok in ("empty", "local_only", "fresh@2026-11-08T10:00:00Z", "stale:timeout@never"):
            with self.subTest(state=ok):
                self.assertEqual(oe.snapshot_incomplete(snap(ok)), [])
        self.assertEqual(oe.snapshot_incomplete(snap("unreachable:no_fetch")),
                         ["store_unreachable:no_fetch"])
        self.assertEqual(oe.snapshot_incomplete(snap("local_only", ["records/t1.json|invalid_json"])),
                         ["store_corrupt:records/t1.json"])


# ================================================================= unblock

class UnblockTests(OBase):
    def test_obsolescence_guard_is_cleared_through_its_own_op_only(self):
        sp = self.sp()
        gap = {"call_id": "c1", "agent": None, "why": "spawn_gap", "at": rsp.utc_iso()}
        sp.write_guard("obsolescence", "10", dict(gap))
        sp.write_guard("relations", "10", dict(gap, call_id="c2"))
        with mock.patch.object(rw, "start_worker_detached", return_value=False):
            code, out = self._unblock(["unblock", "10"])
            self.assertEqual(code, 3)
            self.assertIn("STILL_UNRESOLVED:t10|no_pgid", out)
            code, out = self._unblock(["unblock", "10", "--force"])
            self.assertEqual((code, out.strip()), (0, "UNBLOCKED:t10|forced"))
        self.assertEqual(sp.guard("obsolescence", "10"), [])
        self.assertEqual(len(sp.guard("relations", "10")), 1)  # per-op isolation
        _c, out, _ = tw_cli(self.root, "unblock", "10", "--op", "obsolescence")
        self.assertIn("NO_GUARD:t10", out)
        _c, out, _ = tw_cli(self.root, "unblock", "10")
        self.assertIn("STILL_UNRESOLVED:t10", out)

    def _unblock(self, argv):
        import contextlib
        import io
        buf = io.StringIO()
        args = ocli.build_parser().parse_args(argv)
        with contextlib.redirect_stdout(buf):
            code = ocli.cmd_unblock(str(self.root), args)
        return code, buf.getvalue()


def tw_cli(root, *args):
    proc = subprocess.run([tw.CLI, *args], cwd=str(root), capture_output=True, text=True,
                          env=dict(os.environ), timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


if __name__ == "__main__":
    unittest.main()
