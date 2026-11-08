"""CLI tests for the analysis verbs of ``ait relations`` (t1981_3).

``analysis-state`` (every D8 state, including the cross-host ones), ``stamp``,
``plan-digest``, ``analyze`` (``--dry-run``, ``--now --wait``, the cap), ``usage``,
``ledgers --export`` and ``enable`` / ``disable``. The CLI runs as a subprocess
(``aitask_relations.sh``) in scratch repos; the cross-host cases use two clones
of one bare origin. Stub provider and agent: tests/fixtures/relation_candidates/.

Run: python3 tests/test_relations_analysis_cli.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(TESTS.parent / ".aitask-scripts" / "lib"))

import relations_schema as rs  # noqa: E402
import relations_store as rst  # noqa: E402
import relations_worker as rw  # noqa: E402
import test_relations_worker as tw  # noqa: E402

CLI = tw.CLI


def run(root, *args, env=None):
    proc = subprocess.run([CLI, *args], cwd=str(root), capture_output=True, text=True,
                          env=env, timeout=120)
    return proc.returncode, proc.stdout


def state_of(root, tid, expect=None, env=None):
    args = ["analysis-state", tid] + (["--expect-plan", expect] if expect else [])
    _rc, out = run(root, *args, env=env)
    lines = dict(line.split(":", 1) for line in out.splitlines() if ":" in line)
    return lines.get("ANALYSIS_STATE"), out


class CliBase(tw.WBase):
    def approve(self, tid="10", plan="Approved plan v1.\n", root=None):
        """Commit a plan and stamp it (synchronous outbox write); returns the digest."""
        root = root or self.root
        (root / "aiplans").mkdir(exist_ok=True)
        (root / f"aiplans/p{tid}_name.md").write_text(f"---\nTask: t{tid}\n---\n\n{plan}")
        tw.git(root, "add", "-A")
        tw.git(root, "commit", "-q", "-m", "plan")
        return rw.write_stamp(str(root), tid)

    def analyse_now(self, tid="10", trigger="plan_approved", root=None):
        sp = rw.rsp.Spool(rw.state_dir(str(root or self.root)))
        sp.enqueue("relations", trigger, tid, settle_s=0)
        rw.process_job(str(root or self.root), sp, sp.claim())
        return sp


class AnalysisStateTests(CliBase):
    def test_disabled_and_no_expected_identity(self):
        self.config(enabled=False)
        self.assertEqual(state_of(self.root, "10", "a" * 64)[0], "disabled")
        self.config()
        self.assertEqual(state_of(self.root, "10")[0],
                         "incomplete:unverifiable(no_expected_identity)")

    def test_no_stamp(self):
        self.assertEqual(state_of(self.root, "10", "a" * 64)[0], "incomplete:unverifiable(no_stamp)")

    def test_missing_then_complete(self):
        sha = self.approve()
        self.assertEqual(state_of(self.root, "10", sha)[0], "incomplete:missing")
        self.analyse_now()
        self.assertEqual(state_of(self.root, "10", sha)[0], "complete")

    def test_pending_and_failed(self):
        sha = self.approve()
        sp = rw.rsp.Spool(rw.state_dir(str(self.root)))
        sp.enqueue("relations", "plan_approved", "10", settle_s=300)
        self.assertEqual(state_of(self.root, "10", sha)[0], "incomplete:pending(settling)")
        os.environ["REF_PROVIDER_MODE"] = "fail"
        rw.process_job(str(self.root), sp, (sp.enqueue("relations", "manual", "10", settle_s=0, now=True)
                                            and sp.claim()))
        self.assertEqual(state_of(self.root, "10", sha)[0],
                         "incomplete:failed(provider_error:exit_3)")

    def test_stamp_mismatch_newer_plan_without_stamp(self):
        self.approve()
        self.analyse_now()
        # A newer plan is committed but never stamped (its approval record lost).
        (self.root / "aiplans/p10_name.md").write_text("---\nTask: t10\n---\n\nPlan v2.\n")
        tw.git(self.root, "add", "-A")
        tw.git(self.root, "commit", "-q", "-m", "v2")
        _rc, out = run(self.root, "plan-digest", "10")
        expect = out.strip().split(":", 1)[1]
        self.assertEqual(state_of(self.root, "10", expect)[0], "incomplete:unverifiable(stamp_mismatch)")

    def test_delayed_publish_after_reapproval_never_accepts_the_old_stamp(self):
        old = self.approve()
        self.analyse_now()
        self.assertEqual(state_of(self.root, "10", old)[0], "complete")
        new = self.approve(plan="Re-approved plan v2.\n")  # outbox only, not yet published
        self.assertNotEqual(old, new)
        store = rst.Store(str(self.root))
        self.assertIn(rs.store_path("approvals", "10"), store.read(no_fetch=True).pending)
        self.assertEqual(state_of(self.root, "10", old)[0], "incomplete:unverifiable(stamp_mismatch)")
        self.assertEqual(state_of(self.root, "10", new)[0], "incomplete:inputs_mismatch")

    def test_fold_after_approval_reads_inputs_mismatch_until_reanalysed(self):
        sha = self.approve()
        self.analyse_now()
        self.task("10", tw.C10, "Source goal: change `lib/x/shared.py`.\n\n## Merged from t30\nx\n")
        self.assertEqual(state_of(self.root, "10", sha)[0], "incomplete:inputs_mismatch")
        self.analyse_now(trigger="fold")
        self.assertEqual(state_of(self.root, "10", sha)[0], "complete")

    def test_host_off_note(self):
        sha = self.approve()
        env = dict(os.environ, AIT_RELATIONS="0")
        state, out = state_of(self.root, "10", sha, env=env)
        self.assertEqual(state, "incomplete:missing")
        self.assertIn("NOTE:analysis is switched off on this host (AIT_RELATIONS=0)", out)
        self.assertIn("RELATIONS_STATE:host_off", out)


class CrossHostTests(CliBase):
    def setUp(self):
        super().setUp()
        self.origin = self.tmp / "origin.git"
        tw.git(self.tmp, "init", "-q", "--bare", str(self.origin))
        tw.git(self.root, "remote", "add", "origin", str(self.origin))
        tw.git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        self.other = self.tmp / "other"
        tw.git(self.tmp, "clone", "-q", str(self.origin), str(self.other))
        tw.git(self.other, "config", "user.email", "o@example.com")
        tw.git(self.other, "config", "user.name", "O")
        tw.git(self.other, "checkout", "-q", "main")

    def test_record_from_an_earlier_approval_plus_a_newer_stamp(self):
        self.approve()
        self.analyse_now()                                 # stage-2 record, plan v1, published
        rst.Store(str(self.root)).flush()
        tw.git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        tw.git(self.other, "pull", "-q", "origin", "main")
        new = self.approve(plan="Plan v2 approved elsewhere.\n", root=self.other)
        rst.Store(str(self.other)).flush()                 # the newer stamp is published
        self.assertEqual(state_of(self.root, "10", new)[0], "incomplete:inputs_mismatch")

    def test_no_stamp_visible_is_unverifiable(self):
        self.approve(root=self.root)
        # The task data reaches the other clone, but the approving clone never
        # published its stamp: the other clone cannot see one.
        tw.git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        tw.git(self.other, "pull", "-q", "origin", "main")
        sha = rw.plan_digest(str(self.other), "10")
        self.assertIsNotNone(sha)
        self.assertEqual(state_of(self.other, "10", sha)[0], "incomplete:unverifiable(no_stamp)")

    def test_unreachable_remote_is_unverifiable(self):
        sha = self.approve()
        self.analyse_now()
        rst.Store(str(self.root)).flush()
        tw.git(self.root, "remote", "set-url", "origin", str(self.tmp / "gone.git"))
        self.assertEqual(state_of(self.root, "10", sha)[0], "incomplete:unverifiable(store_stale)")


class VerbTests(CliBase):
    def test_stamp_line_and_synchronous_outbox(self):
        self.plan("10", "Plan.\n")
        self.commit()
        rc, out = run(self.root, "stamp", "10")
        self.assertEqual(rc, 0)
        sha = out.strip().split(":", 1)[1]
        visible = rst.Store(str(self.root)).visible()
        stamp = rst._loads(visible[rs.store_path("approvals", "10")])
        self.assertEqual(stamp["plan_sha256"], sha)  # visible the moment stamp returned
        self.assertEqual(stamp["task_created_at"], tw.C10)
        self.assertEqual(stamp["data_commit"], tw.git(self.root, "rev-parse", "HEAD"))

    def test_stamp_disabled_and_errors(self):
        self.config(enabled=False)
        (self.root / "aitasks/metadata/project_config.yaml").write_text("relations:\n  enabled: false\n")
        self.assertEqual(run(self.root, "stamp", "10"), (0, "STAMP:disabled\n"))
        self.config()
        self.assertEqual(run(self.root, "stamp", "10"), (1, "STAMP_ERROR:plan_not_committed\n"))

    def test_plan_digest(self):
        self.assertEqual(run(self.root, "plan-digest", "10"), (1, "PLAN_DIGEST_ERROR:no_plan\n"))
        self.plan("10", "Plan.\n")
        self.commit()
        rc, out = run(self.root, "plan-digest", "10")
        self.assertEqual((rc, out.strip()),
                         (0, "PLAN_DIGEST:" + rs.digests("", (self.root / "aiplans/p10_name.md").read_text())["plan_sha256"]))

    def test_dry_run_writes_nothing(self):
        rc, out = run(self.root, "analyze", "10", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn('"analysed": true', out)
        store = rst.Store(str(self.root))
        self.assertIsNone(rst.ors.resolve(str(self.root), rst.L_REF))
        self.assertEqual(store._outbox_paths(), [])

    def test_dry_run_works_while_disabled(self):
        self.config(enabled=False)
        rc, out = run(self.root, "analyze", "10", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn('"relations"', out)
        self.assertEqual(run(self.root, "analyze", "10")[0], 1)

    def test_now_wait_is_bounded(self):
        self.agent("ok", hold_s=8)
        start = time.monotonic()
        rc, out = run(self.root, "analyze", "10", "--now", "--wait", "1")
        self.assertLess(time.monotonic() - start, 6)
        self.assertEqual(rc, 3)
        self.assertRegex(out, r"^WAIT_TIMEOUT:t10\|pending\((running|queued)\)")
        self.assertTrue(tw.wait_for(lambda: self.record() is not None, 60))

    def test_now_wait_reports_the_outcome(self):
        rc, out = run(self.root, "analyze", "10", "--now", "--wait", "60")
        self.assertEqual((rc, out.strip()), (0, "ANALYZED:t10|ANALYSED(published)"))

    def test_now_at_cap_refuses_without_over_cap(self):
        self.config(max_jobs_per_day=1)
        rw.rsp.Spool(rw.state_dir(str(self.root))).admit("relations", "99", "manual", cap=1)
        self.assertEqual(run(self.root, "analyze", "10", "--now"), (3, "CAP_REACHED:1/1\n"))
        self.assertEqual(run(self.root, "analyze", "10", "--dry-run"), (3, "CAP_REACHED:1/1\n"))
        rc, out = run(self.root, "analyze", "10", "--now", "--over-cap", "--wait", "60")
        self.assertEqual(rc, 0, out)

    def test_host_off_refuses_queueing(self):
        env = dict(os.environ, AIT_RELATIONS="0")
        rc, out = run(self.root, "analyze", "10", env=env)
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("HOST_OFF:"))

    def test_usage_and_ledgers_export(self):
        self.analyse_now(trigger="manual")
        sd = Path(rw.state_dir(str(self.root)))
        with open(sd / "usage.jsonl", "a") as fh:
            fh.write("{not json\n")
        (sd / "notify.jsonl").write_text('{"kind": "offer"}\n')
        rc, out = run(self.root, "usage", "--days", "1")
        self.assertEqual(rc, 0)
        self.assertIn("USAGE:local|relations|manual|jobs=1|calls=1|failed_calls=0|unsettled=0|in=115|out=42", out)
        self.assertIn("LEDGER_CORRUPT:usage.jsonl|1", out)
        self.assertIn("USAGE:store|relations|manual|records=1|in=115", out)
        rc, out = run(self.root, "ledgers", "--export")
        rows = [__import__("json").loads(line) for line in out.splitlines()]
        self.assertTrue(all(r["host"] for r in rows))
        self.assertEqual({r["ledger"] for r in rows}, {"usage", "notify"})
        self.assertTrue(any(r.get("corrupt_line") for r in rows))


class EnableTests(CliBase):
    def setUp(self):
        super().setUp()
        self.config(enabled=None)
        self.commit()

    def committed(self):
        return tw.git(self.root, "show", "HEAD:aitasks/metadata/project_config.yaml")

    def test_enable_commits_and_reads_back(self):
        rc, out = run(self.root, "enable")
        self.assertEqual(rc, 0, out)
        self.assertIn("PROJECT_NAME:kept:aitasks", out)
        self.assertIn("COMMIT:COMMITTED:", out)
        self.assertIn("RELATIONS:enabled(test/stub, cap 40/day)", out)
        self.assertIn("enabled: true", self.committed())
        rc, out = run(self.root, "disable")
        self.assertEqual(rc, 0, out)
        self.assertIn("RELATIONS:disabled", out)
        self.assertIn("enabled: false", self.committed())

    def test_enable_seeds_one_registry_binding(self):
        cfg = self.root / "aitasks/metadata/project_config.yaml"
        cfg.write_text(cfg.read_text().replace("project:\n  name: aitasks\n", ""))
        self.commit()
        Path(os.environ["AITASKS_PROJECTS_INDEX"]).write_text(f"- name: aitasks\n  path: {self.root}\n")
        rc, out = run(self.root, "enable")
        self.assertEqual(rc, 0, out)
        self.assertIn("PROJECT_NAME:seeded:aitasks", out)
        self.assertIn("name: aitasks", self.committed())

    def test_enable_refuses_without_a_resolvable_name(self):
        cfg = self.root / "aitasks/metadata/project_config.yaml"
        cfg.write_text(cfg.read_text().replace("project:\n  name: aitasks\n", ""))
        self.commit()
        before = cfg.read_text()
        for registry in ("", f"- name: a\n  path: {self.root}\n- name: b\n  path: {self.root}\n"):
            with self.subTest(registry=registry or "empty"):
                Path(os.environ["AITASKS_PROJECTS_INDEX"]).write_text(registry)
                rc, out = run(self.root, "enable")
                self.assertEqual(rc, 1)
                self.assertTrue(out.startswith("PROJECT_UNRESOLVED:"), out)
                self.assertEqual(cfg.read_text(), before)


if __name__ == "__main__":
    unittest.main()
