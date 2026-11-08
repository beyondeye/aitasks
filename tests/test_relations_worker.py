"""Tests for the task-relations worker, spool and admission (t1981_3).

Scratch local-only repos under a temp dir (``aitasks/`` and ``aiplans/`` are
plain directories, so the data repo is the repo itself, which is the legacy
layout). The candidate provider is
``tests/fixtures/relation_candidates/reference_provider.py`` and the agent is
``stub_agent.py`` beside it, injected through the worker's test seams. No real
LLM, no network, never ``~/.aitask*``. No test changes the process cwd.

Interleavings across processes use the worker's barrier seam
(AIT_RELATIONS_TEST_BARRIER=<point>:<dir>); in-process ones replace
``relations_worker._test_hook``.

Run: python3 tests/test_relations_worker.py
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
LIB = REPO / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB))

import relations_schema as rs  # noqa: E402
import relations_spool as rsp  # noqa: E402
import relations_store as rst  # noqa: E402
import relations_worker as rw  # noqa: E402

FIX = TESTS / "fixtures" / "relation_candidates"
PROVIDER = f"{sys.executable} {FIX / 'reference_provider.py'}"
AGENT = f"{sys.executable} {FIX / 'stub_agent.py'}"
WORKER = str(LIB / "relations_worker.py")
CLI = str(REPO / ".aitask-scripts" / "aitask_relations.sh")
ENQUEUE = str(REPO / ".aitask-scripts" / "aitask_relations_enqueue.sh")

C10, C11, C12, C13 = ("2026-11-01 10:00", "2026-11-02 10:00", "2026-11-03 10:00",
                      "2026-11-04 10:00")


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check,
                          capture_output=True, text=True).stdout.strip()


def wait_for(cond, timeout=30.0, step=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(step)
    return cond()


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A zombie still answers kill(0); treat it as dead once it has exited.
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def orphan_sleeper(seconds=120):
    """A sleeper in its own session whose parent has already exited.

    Like an agent group orphaned by a killed worker: init (or the subreaper)
    reaps it, so a terminated group really disappears instead of lingering as
    a zombie of the test process.
    """
    out = subprocess.run([sys.executable, "-c",
                          "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c',"
                          f"'import time; time.sleep({seconds})'], start_new_session=True,"
                          " stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,"
                          " stderr=subprocess.DEVNULL); print(p.pid)"],
                         capture_output=True, text=True, check=True)
    pid = int(out.stdout.strip())
    assert wait_for(lambda: alive(pid), 5)
    return pid


class WBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="relations-worker-")
        self.tmp = Path(self._tmp.name)
        home = self.tmp / "home"
        home.mkdir()
        self.spec = self.tmp / "provider.json"
        self.agent_spec = self.tmp / "agent.json"
        self.launches = self.tmp / "launches.log"
        env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(home),
               "GIT_TERMINAL_PROMPT": "0", "REF_PROVIDER_SPEC": str(self.spec),
               "STUB_AGENT_SPEC": str(self.agent_spec),
               "AIT_RELATIONS_CANDIDATES_CMD": PROVIDER, "AIT_RELATIONS_AGENT_CMD": AGENT,
               "AITASKS_PROJECTS_INDEX": str(self.tmp / "no-registry.yaml"),
               # The CLI wrapper resolves its interpreter; pin this one (it has PyYAML).
               "AIT_PYTHON": sys.executable}
        self._env = mock.patch.dict(os.environ, env)
        self._env.start()
        for key in ("AITASKS_HOME", "AIT_RELATIONS", "TASK_DIR", "PLAN_DIR", "ARCHIVED_DIR",
                    "ARCHIVED_PLAN_DIR", "REF_PROVIDER_MODE", "REF_PROVIDER_SALT",
                    "AIT_RELATIONS_TEST_BARRIER"):
            os.environ.pop(key, None)
        self.root = self.tmp / "repo"
        for d in ("aitasks/metadata", "aitasks/archived", "aiplans/archived"):
            (self.root / d).mkdir(parents=True)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "T")
        self.config()
        self.provider([{"id": "11", "sources": ["mention_in", "cites"]}])
        self.agent("ok")
        self.task("10", C10, "Source goal: change `lib/x/shared.py`.\n")
        self.task("11", C11, "Candidate that uses the shared helper.\n")
        self.commit()
        self._procs = []

    def tearDown(self):
        for proc in self._procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        # Reap anything a test left (stub sleepers are killed by the tests).
        self._env.stop()
        self._tmp.cleanup()

    # ------------------------------------------------------------ fixture
    def config(self, enabled=True, **knobs):
        vals = {"settle_s": 0, "max_jobs_per_day": 40, "job_timeout_s": 20, "candidate_cap": 25}
        vals.update(knobs)
        text = "project:\n  name: aitasks\nrelations:\n"
        if enabled is not None:
            text += f"  enabled: {'true' if enabled else 'false'}\n"
        text += "".join(f"  {k}: {v}\n" for k, v in vals.items())
        (self.root / "aitasks/metadata/project_config.yaml").write_text(text)

    def task(self, tid, created, body, issue_type=None):
        fm = ["status: Ready", f"created_at: {created}"]
        if issue_type:
            fm.append(f"issue_type: {issue_type}")
        if "_" in tid:
            p = tid.split("_")[0]
            path = self.root / f"aitasks/t{p}/t{tid}_name.md"
        else:
            path = self.root / f"aitasks/t{tid}_name.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body)
        return path

    def plan(self, tid, text):
        path = self.root / f"aiplans/p{tid}_name.md"
        path.write_text("---\nTask: t" + tid + "\n---\n\n" + text)
        return path

    def commit(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "data", "--allow-empty")

    def provider(self, cands, truncated=None, coverage=None):
        spec = {"candidates": cands}
        if truncated:
            spec["truncated"] = truncated
        if coverage:
            spec["coverage"] = coverage
        self.spec.write_text(json.dumps(spec))

    def rel(self, to="11", rtype="affects", frm="10"):
        return {"from": f"aitasks#{frm}", "to": f"aitasks#{to}", "type": rtype,
                "description": f"t{frm} {rtype} t{to}",
                "basis": [{"kind": "path", "value": "lib/x/shared.py"}]}

    def agent(self, mode, relations=None, considered=None, **kw):
        spec = {"mode": mode, "launch_log": str(self.launches),
                "relations": relations if relations is not None else [self.rel()],
                "considered": considered if considered is not None else
                [{"ref": "aitasks#11", "outcome": "related", "sources": ["cites"]}]}
        spec.update(kw)
        self.agent_spec.write_text(json.dumps(spec))

    def sp(self):
        return rsp.Spool(rw.state_dir(str(self.root)))

    def launch_count(self):
        return len(self.launches.read_text().split()) if self.launches.exists() else 0

    def store(self):
        return rst.Store(str(self.root))

    def record(self, tid="10"):
        return self.store().read(no_fetch=True).files.get(rs.store_path("records", tid))

    def run_job(self, tid="10", trigger="manual", **kw):
        sp = self.sp()
        sp.enqueue("relations", trigger, tid, settle_s=0, **kw)
        job = sp.claim()
        self.assertIsNotNone(job)
        rw.process_job(str(self.root), sp, job)
        return sp

    def calls(self, sp=None):
        rows, _ = (sp or self.sp()).read_ledger()
        return [r for r in rows if r.get("kind") == "call"]

    def outcomes(self, sp=None):
        rows, _ = (sp or self.sp()).read_ledger()
        return {r["call_id"]: r for r in rows if r.get("kind") == "outcome"}

    def spawn_worker(self, barrier_points=None, extra_env=None):
        env = dict(os.environ)
        if barrier_points:
            env["AIT_RELATIONS_TEST_BARRIER"] = f"{barrier_points}:{self.tmp}"
        env.update(extra_env or {})
        proc = subprocess.Popen([sys.executable, WORKER, "run", str(self.root)], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._procs.append(proc)
        return proc

    def reached(self, point):
        return (self.tmp / f"{point}.reached").exists()

    def release(self, point):
        (self.tmp / f"{point}.release").write_text("go")


# ===================================================================== spool

class SpoolTests(WBase):
    def test_coalesce_priority_sticky_debounce(self):
        sp = self.sp()
        a = sp.enqueue("relations", "created", "10", settle_s=100, request_id="r1", ts=1000)
        self.assertEqual(a["not_before"], 1100)
        sp.enqueue("relations", "plan_approved", "10", settle_s=100, request_id="r2", ts=1010)
        c = sp.enqueue("relations", "fold", "10", settle_s=100, now=True, request_id="r1", ts=1020)
        self.assertEqual(c["trigger"], "plan_approved")  # the higher stage is kept
        self.assertTrue(c["now"])
        self.assertEqual(c["not_before"], 1120)            # debounced to the last enqueue
        self.assertEqual(c["request_ids"], ["r1", "r2"])
        self.assertEqual(len(sp.list_jobs()), 1)
        d = sp.enqueue("relations", "created", "10", settle_s=100, ts=1030)
        self.assertTrue(d["now"], "now is sticky")
        self.assertEqual(d["trigger"], "plan_approved")

    def test_enqueue_removes_failed_but_never_a_guard(self):
        sp = self.sp()
        sp.enqueue("relations", "manual", "10", settle_s=0)
        sp.fail(sp.claim(), "PROVIDER_ERROR:x")
        sp.write_guard("relations", "10", {"why": "spawn_gap", "agent": None})
        sp.enqueue("relations", "created", "10", settle_s=0)
        self.assertIsNone(sp._read(sp.path("failed", "relations__t10")))
        self.assertTrue(sp.guard("relations", "10"))

    def test_settle_respected_and_now_bypasses(self):
        sp = self.sp()
        sp.enqueue("relations", "created", "10", settle_s=100)
        self.assertIsNone(sp.claim())
        self.assertEqual(sp.job_state("10"), "pending(settling)")
        sp.enqueue("relations", "manual", "10", settle_s=100, now=True)
        self.assertEqual(sp.job_state("10"), "pending(queued)")
        job = sp.claim()
        self.assertEqual(job["task"], "10")
        self.assertEqual(sp.job_state("10"), "pending(running)")

    def test_job_state_values(self):
        sp = self.sp()
        self.assertIsNone(sp.job_state("10"))
        sp.enqueue("relations", "manual", "10", settle_s=0)
        job = sp.claim()
        sp.requeue(job, state=rsp.HOLD_CAPPED)
        self.assertEqual(sp.job_state("10"), "pending(capped)")
        sp.reset_holds()
        sp.fail(sp.claim(), "TIMEOUT")
        self.assertEqual(sp.job_state("10"), "failed(timeout)")
        sp.write_guard("relations", "10", {"why": "x"})
        self.assertEqual(sp.job_state("10"), "failed(interrupted_unresolved)")
        # The store's ANALYSIS: line reads it through the replaced hook.
        self.assertEqual(self.store().analysis_line("10", self.store().read(no_fetch=True)),
                         "failed(interrupted_unresolved)")


# ================================================================= pipeline

class PipelineTests(WBase):
    def test_analysed_record_and_usage(self):
        sp = self.run_job()
        rec = self.record()
        self.assertTrue(rec["analysed"])
        self.assertEqual(rec["run"]["stage"], 1)
        self.assertEqual([r["to"] for r in rec["relations"]], ["aitasks#11"])
        self.assertEqual(rec["inputs"]["candidates"][0]["created_at"], C11)
        self.assertEqual(rec["usage"]["input_tokens"], 115)
        self.assertEqual(rec["usage"]["cost_usd"], 0.0123)
        self.assertEqual(rec["run"]["candidate_provider"], "fallback")
        self.assertIn("screening_sha256", rec["inputs"])
        calls = self.calls(sp)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.outcomes(sp)[calls[0]["call_id"]]["outcome"], "ok")

    def test_up_to_date_skip(self):
        self.run_job()
        self.run_job()
        self.assertEqual(self.launch_count(), 1)
        rows, _ = self.sp().read_ledger()
        self.assertTrue(any(r.get("outcome") == "UP_TO_DATE" for r in rows))

    def test_zero_candidates_no_agent_call(self):
        self.provider([])
        self.run_job()
        rec = self.record()
        self.assertEqual(rec["relations"], [])
        self.assertTrue(rec["analysed"])
        self.assertEqual(self.launch_count(), 0)
        self.assertEqual(self.calls(), [])

    def test_invalid_output_fails_and_writes_nothing(self):
        for mode in ("invalid", "two_objects"):
            with self.subTest(mode=mode):
                self.agent(mode)
                sp = self.run_job()
                self.assertTrue(sp.job_state("10").startswith("failed(invalid_output"), sp.job_state("10"))
                self.assertIsNone(self.record())
                self.assertEqual(self.store()._outbox_paths(), [])
        # every failed call consumed allowance and was settled
        outs = self.outcomes()
        self.assertEqual({outs[c["call_id"]]["outcome"] for c in self.calls()}, {"invalid_output"})

    def test_relation_to_a_non_candidate_is_refused(self):
        self.agent("ok", relations=[self.rel(to="99")])
        sp = self.run_job()
        self.assertTrue(sp.job_state("10").startswith("failed(invalid_output"))
        self.assertIsNone(self.record())

    def test_fenced_output_accepted(self):
        self.agent("fenced")
        self.run_job()
        self.assertEqual(len(self.record()["relations"]), 1)

    def test_provider_failures_fail_before_up_to_date(self):
        self.run_job()
        before = self.record()
        for mode, env, expect in (("fail", {}, "failed(provider_error:exit_3)"),
                                  ("garbage", {}, "failed(provider_error:malformed:invalid json")):
            with self.subTest(mode=mode):
                os.environ["REF_PROVIDER_MODE"] = mode
                sp = self.run_job()
                self.assertTrue(sp.job_state("10").startswith(expect), sp.job_state("10"))
                os.environ.pop("REF_PROVIDER_MODE")
        self.provider([{"id": "11", "sources": ["mention_in"]}],
                      coverage={"answered": ["mention_in", "mention_out"], "missing_sources": ["cites"]})
        sp = self.run_job()
        self.assertTrue(sp.job_state("10").startswith("failed(candidates_unavailable:core_missing"))
        self.assertEqual(self.record(), before)  # never replaced by an empty record
        self.assertEqual(self.launch_count(), 1)

    def test_missing_provider_script(self):
        os.environ.pop("AIT_RELATIONS_CANDIDATES_CMD")
        with mock.patch.object(rw, "CANDIDATES_SCRIPT", str(self.tmp / "absent.sh")):
            sp = self.run_job()
        self.assertEqual(sp.job_state("10"), "failed(candidates_unavailable:no_provider)")

    def test_partial_coverage_recorded(self):
        self.provider([{"id": "11", "sources": ["mention_in"]}],
                      coverage={"answered": ["mention_in", "mention_out", "cites"],
                                "missing_sources": ["token"]})
        self.run_job()
        self.assertEqual(self.record()["coverage"], {"missing_sources": ["token"]})

    def test_truncated_candidates_get_entries(self):
        self.task("12", C12, "Hub-only candidate.\n")
        self.commit()
        self.provider([{"id": "11", "sources": ["mention_in"]}], truncated={"cites_hub": ["12"]})
        self.agent("ok", relations=[self.rel(to="12", rtype="informs")])
        self.run_job()
        refs = [c["ref"] for c in self.record()["inputs"]["candidates"]]
        self.assertEqual(refs, ["aitasks#11", "aitasks#12"])
        self.assertEqual(self.record()["relations"][0]["to"], "aitasks#12")

    def test_manual_verification_excluded(self):
        self.task("10", C10, "Verify things.\n", issue_type="manual_verification")
        sp = self.run_job()
        self.assertIsNone(self.record())
        self.assertEqual(self.launch_count(), 0)
        self.assertIsNone(sp.job_state("10"))

    def test_stamped_job_reads_the_stamp_snapshot(self):
        self.plan("10", "Approved: edit `lib/x/shared.py`.\n")
        self.commit()
        sha = rw.write_stamp(str(self.root), "10")
        self.plan("10", "Approved: edit `lib/x/shared.py`.\n- [x] progress mark\n")  # working edit
        self.run_job(trigger="plan_approved")
        rec = self.record()
        self.assertEqual(rec["run"]["stage"], 2)
        self.assertEqual(rec["inputs"]["source"]["plan_sha256"], sha)
        work = sorted((Path(rw.state_dir(str(self.root))) / "spool" / "work").iterdir())[-1]
        self.assertNotIn("progress mark", (work / "inputs/source/plan.md").read_text())

    def test_fold_after_approval_is_reanalysed(self):
        self.plan("10", "Plan.\n")
        self.commit()
        rw.write_stamp(str(self.root), "10")
        self.run_job(trigger="plan_approved")
        first = self.record()["run"]["id"]
        self.task("10", C10, "Source goal: change `lib/x/shared.py`.\n\n## Merged from t30\nmore\n")
        self.run_job(trigger="fold")
        self.assertNotEqual(self.record()["run"]["id"], first)
        self.assertEqual(self.launch_count(), 2)

    def test_screening_snapshot_agreement(self):
        self.plan("10", "Approved source plan with `approved_token`.\n")
        self.plan("11", "Approved candidate plan.\n")
        self.commit()
        rw.write_stamp(str(self.root), "10")
        rw.write_stamp(str(self.root), "11")
        self.plan("10", "Working source plan with `WORKING_ONLY_SRC` and lib/x/working_only.py.\n")
        self.plan("11", "Working candidate plan with `WORKING_ONLY_CAND`.\n")
        self.run_job()
        work = sorted((Path(rw.state_dir(str(self.root))) / "spool" / "work").iterdir(),
                      key=lambda p: p.stat().st_mtime)[-1]
        prompt = (work / "prompt.md").read_text()
        self.assertNotIn("WORKING_ONLY", prompt)
        self.assertIn("Approved candidate plan", prompt)
        first = self.record()
        # A non-conforming provider (reads the working plans) fails, writes nothing.
        os.environ["REF_PROVIDER_MODE"] = "working"
        sp = self.run_job()
        self.assertTrue(sp.job_state("10").startswith("failed(snapshot_mismatch"), sp.job_state("10"))
        self.assertEqual(self.record(), first)
        # Evidence changed with refs/digests/coverage equal -> re-analysed.
        os.environ["REF_PROVIDER_MODE"] = "salt"
        os.environ["REF_PROVIDER_SALT"] = "new evidence row"
        self.run_job()
        self.assertNotEqual(self.record()["inputs"]["screening_sha256"],
                            first["inputs"]["screening_sha256"])
        self.assertEqual(self.launch_count(), 2)

    def test_timeout_kills_process_group_and_retries_once(self):
        self.config(job_timeout_s=1)
        pid_file = self.tmp / "pids"
        self.agent("spawn_child_sleep", pid_file=str(pid_file))
        sp = self.run_job()  # first timeout: requeued
        leader, child = map(int, pid_file.read_text().split())
        self.assertTrue(wait_for(lambda: not alive(leader) and not alive(child), 10))
        self.assertEqual(sp.job_state("10"), "pending(queued)")
        rw.process_job(str(self.root), sp, sp.claim())  # retry: second timeout
        self.assertEqual(sp.job_state("10"), "failed(timeout)")
        self.assertEqual(len(self.calls()), 2)  # the retry consumed its own slot
        self.assertEqual({o["outcome"] for o in self.outcomes().values()}, {"timeout"})


# ==================================================================== state

class FreshStateTests(WBase):
    def test_fresh_index_between_jobs(self):
        self.task("20", C12, "Job A.\n")
        self.task("21", C13, "Job B original.\n")
        self.commit()
        self.provider([{"id": "11", "sources": ["mention_in"]}])
        self.agent("ok", relations=[], considered=[])
        sp = self.sp()
        sp.enqueue("relations", "manual", "20", settle_s=0, now=True)
        sp.enqueue("relations", "manual", "21", settle_s=0, now=True)
        def hook(point, **ctx):
            if point == "between_jobs" and ctx.get("task") == "20":
                self.task("21", "2026-11-09 09:00", "Job B rewritten.\n")
                self.task("12", C12, "Brand new candidate.\n")
                self.provider([{"id": "11", "sources": ["mention_in"]},
                               {"id": "12", "sources": ["mention_out"]}])
        with mock.patch.object(rw, "_test_hook", hook):
            rw.run_worker(str(self.root))
        rec = self.record("21")
        self.assertEqual(rec["task_created_at"], "2026-11-09 09:00")
        self.assertIn("aitasks#12", [c["ref"] for c in rec["inputs"]["candidates"]])
        self.assertEqual(rec["inputs"]["source"]["body_sha256"],
                         self.store().index.body_digest("21"))

    def test_one_snapshot_within_a_job(self):
        self.plan("10", "Working plan.\n")
        self.commit()
        def hook(point, **ctx):
            if point == "after_snapshot":
                rw.write_stamp(str(self.root), "10")  # lands after this job's snapshot
        with mock.patch.object(rw, "_test_hook", hook):
            self.run_job()
        rec = self.record()
        self.assertEqual(rec["run"]["stage"], 1)  # coherent: no half-applied stamp
        self.assertEqual(rec["inputs"]["source"]["plan_sha256"], self.store().index.plan_digest("10"))


# ===================================================================== caps

class CapTests(WBase):
    def test_failed_calls_consume_allowance(self):
        self.config(max_jobs_per_day=3, job_timeout_s=1)
        self.agent("sleep", sleep_s=30)
        sp = self.run_job()                       # timeout #1 (requeued)
        rw.process_job(str(self.root), sp, sp.claim())  # timeout #2 -> failed
        self.agent("error")
        self.run_job()                            # agent error
        self.assertEqual(sp.calls_today("relations"), 3)
        self.agent("ok")
        self.run_job()
        self.assertEqual(sp.job_state("10"), "pending(capped)")
        self.assertEqual(self.launch_count(), 3)
        self.run_job(over_cap=True)               # over_cap bypasses, and is recorded
        self.assertIsNotNone(self.record())
        self.assertTrue(self.calls(sp)[-1]["over_cap"])

    def test_unknown_cost_is_null_not_zero(self):
        self.agent("no_usage")
        self.run_job()
        out = list(self.outcomes().values())[0]
        self.assertIsNone(out["cost_usd"])
        self.assertIsNone(out["input_tokens"])
        res = subprocess.run([CLI, "usage"], cwd=self.root, capture_output=True, text=True)
        self.assertRegex(res.stdout, r"\|cost=0(\.0)?\+unknown\(1\)\|")

    def test_concurrent_dry_runs_share_the_last_slot(self):
        self.config(max_jobs_per_day=1)
        self.agent("ok", hold_s=1.0)
        procs = [subprocess.Popen([CLI, "analyze", "10", "--dry-run"], cwd=self.root,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                 for _ in range(2)]
        outs = [p.communicate(timeout=60)[0] for p in procs]
        refused = [o for o in outs if o.startswith("CAP_REACHED")]
        ran = [o for o in outs if o.lstrip().startswith("{")]
        self.assertEqual((len(ran), len(refused)), (1, 1), outs)
        self.assertEqual(self.launch_count(), 1)

    def test_worker_and_dry_run_share_the_last_slot(self):
        self.config(max_jobs_per_day=1)
        self.agent("ok", hold_s=1.0)
        self.sp().enqueue("relations", "manual", "10", settle_s=0, now=True)
        worker = self.spawn_worker()
        dry = subprocess.run([CLI, "analyze", "10", "--dry-run"], cwd=self.root,
                             capture_output=True, text=True, timeout=60)
        worker.wait(timeout=60)
        self.assertEqual(self.launch_count(), 1, dry.stdout)
        self.assertEqual(len(self.calls()), 1)


# ================================================================ handoff

class HandoffTests(WBase):
    def test_job_enqueued_before_release_runs_without_another_enqueue(self):
        self.agent("ok", relations=[], considered=[])
        self.sp().enqueue("relations", "manual", "10", settle_s=0, now=True)
        worker = self.spawn_worker("before_release")
        self.assertTrue(wait_for(lambda: self.reached("before_release")))
        self.task("12", C12, "Job B.\n")
        sp = self.sp()
        sp.enqueue("relations", "created", "12", settle_s=1)
        self.assertFalse(sp.worker_lock_free())  # the detached start would fail now
        self.release("before_release")
        worker.wait(timeout=60)
        self.assertIsNotNone(self.record("12"))

    def test_job_enqueued_after_release_runs(self):
        self.agent("ok", relations=[], considered=[])
        self.sp().enqueue("relations", "manual", "10", settle_s=0, now=True)
        worker = self.spawn_worker("after_release")
        self.assertTrue(wait_for(lambda: self.reached("after_release")))
        self.task("12", C12, "Job B.\n")
        self.sp().enqueue("relations", "created", "12", settle_s=1)
        self.release("after_release")
        worker.wait(timeout=60)
        self.assertIsNotNone(self.record("12"))

    def test_capped_only_spool_lets_the_worker_exit(self):
        self.config(max_jobs_per_day=1)
        self.sp().admit("relations", "99", "manual", cap=1)
        self.sp().enqueue("relations", "manual", "10", settle_s=0, now=True)
        self.assertEqual(rw.run_worker(str(self.root)), 0)
        self.assertEqual(self.sp().job_state("10"), "pending(capped)")
        self.assertEqual(self.launch_count(), 0)

    def test_single_worker_under_concurrent_enqueues(self):
        timeline = self.tmp / "timeline"
        self.agent("ok", relations=[], considered=[], hold_s=0.3, timeline=str(timeline))
        for tid in ("20", "21", "22", "23"):
            self.task(tid, C12, f"Task {tid}.\n")
        self.commit()
        procs = [subprocess.Popen([sys.executable, WORKER, "enqueue", str(self.root),
                                   "relations", "created", tid]) for tid in ("20", "21", "22", "23")]
        for p in procs:
            p.wait(timeout=30)
        sp = self.sp()
        self.assertTrue(wait_for(lambda: all(self.record(t) for t in ("20", "21", "22", "23")), 60))
        self.assertTrue(wait_for(sp.worker_lock_free, 30))
        events = [line.split() for line in timeline.read_text().splitlines()]
        running = peak = 0
        for kind, _ts in sorted(events, key=lambda e: float(e[1])):
            running += 1 if kind == "start" else -1
            peak = max(peak, running)
        self.assertEqual(peak, 1, "two agents ran at once: more than one worker")


# =============================================================== recovery

class RecoveryTests(WBase):
    def test_kill_after_admit_retries_and_keeps_the_slot(self):
        self.sp().enqueue("relations", "manual", "10", settle_s=0, now=True, request_id="rq")
        worker = self.spawn_worker("after_admit")
        self.assertTrue(wait_for(lambda: self.reached("after_admit")))
        worker.send_signal(signal.SIGKILL)
        worker.wait()
        self.assertEqual(self.sp().job_state("10"), "pending(running)")
        rw.run_worker(str(self.root))
        sp = self.sp()
        self.assertIsNotNone(self.record())
        self.assertEqual(sp.result("rq")["outcome"], "ANALYSED(published)")
        calls = self.calls(sp)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.outcomes(sp)[calls[0]["call_id"]]["outcome"], "interrupted")

    def test_kill_with_a_live_agent_group(self):
        pid_file = self.tmp / "pids"
        self.agent("spawn_child_sleep", pid_file=str(pid_file), sleep_s=120)
        self.sp().enqueue("relations", "manual", "10", settle_s=0, now=True)
        worker = self.spawn_worker()
        self.assertTrue(wait_for(pid_file.exists))
        leader, child = map(int, pid_file.read_text().split())
        worker.send_signal(signal.SIGKILL)
        worker.wait()
        self.assertTrue(alive(leader) and alive(child), "the orphaned agent outlives its worker")
        violation = self.tmp / "violation"
        self.agent("ok", check_dead=str(pid_file), violation=str(violation))
        rw.run_worker(str(self.root))
        self.assertFalse(violation.exists(), "a replacement started while the old group lived")
        self.assertFalse(alive(leader) or alive(child))
        self.assertIsNotNone(self.record())

    def _spawn_gap(self, request_id=None):
        sp = self.sp()
        sp.enqueue("relations", "manual", "10", settle_s=0, now=True)
        job = sp.claim()
        call_id = sp.admit("relations", "10", "manual", cap=40)
        sp.update_running(job, call_id=call_id, spawning=call_id)  # killed before `agent`
        if request_id:
            sp.enqueue("relations", "created", "10", settle_s=0, now=True, request_id=request_id)
        return call_id

    def test_unresolved_guard_holds_across_requests(self):
        call_id = self._spawn_gap(request_id="queued")
        rw.run_worker(str(self.root))
        sp = self.sp()
        self.assertTrue(sp.guard("relations", "10"))
        self.assertEqual(self.outcomes(sp)[call_id]["outcome"], "unresolved")
        self.assertEqual(sp.result("queued")["outcome"], "BLOCKED_UNRESOLVED")    # (a)
        self.assertEqual(sp.job_state("10"), "failed(interrupted_unresolved)")
        subprocess.run([ENQUEUE, "relations", "created", "10"], cwd=self.root, check=True)  # (b)
        self.assertTrue(wait_for(sp.worker_lock_free, 30))
        time.sleep(0.5)
        self.assertTrue(wait_for(sp.worker_lock_free, 30))
        self.assertTrue(sp.guard("relations", "10"))
        dry = subprocess.run([CLI, "analyze", "10", "--dry-run"], cwd=self.root,
                             capture_output=True, text=True)                         # (c)
        self.assertEqual((dry.returncode, dry.stdout.strip()), (3, "BLOCKED_UNRESOLVED"))
        self.assertEqual(self.launch_count(), 0)
        self.assertIsNone(self.record())

    def test_unblock_force_clears_a_spawn_gap_guard(self):
        self._spawn_gap()
        rw.run_worker(str(self.root))
        out = subprocess.run([CLI, "unblock", "10"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(out.returncode, 3)
        self.assertIn("STILL_UNRESOLVED:t10|no_pgid", out.stdout)
        out = subprocess.run([CLI, "unblock", "10", "--force"], cwd=self.root,
                             capture_output=True, text=True)
        self.assertIn("UNBLOCKED:t10|forced", out.stdout)
        rows, _ = self.sp().read_ledger()
        self.assertTrue(any(r.get("kind") == "unblock" and str(r.get("how")).startswith("forced") for r in rows))

    def _guard_on(self, pid):
        kind, tok = rw.leader_identity(pid)
        agent = {"pgid": pid, "leader_pid": pid, "identity": tok, "identity_kind": kind}
        sp = self.sp()
        sp.write_guard("relations", "10", {"call_id": None, "agent": agent, "why": "kill_unconfirmed"})
        sp.enqueue("relations", "manual", "10", settle_s=0, now=True)
        return sp

    def test_guard_on_a_live_group_until_it_ends(self):
        pid = orphan_sleeper()
        sp = self._guard_on(pid)
        rw.run_worker(str(self.root))
        self.assertEqual(self.launch_count(), 0)
        out = subprocess.run([CLI, "unblock", "10"], cwd=self.root, capture_output=True, text=True)
        self.assertIn("STILL_UNRESOLVED:t10|leader_alive", out.stdout)
        os.kill(pid, signal.SIGKILL)
        self.assertTrue(wait_for(lambda: not alive(pid), 10))
        rw.run_worker(str(self.root))  # the next start clears the guard; the job runs once
        self.assertFalse(sp.guard("relations", "10"))
        self.assertEqual(self.launch_count(), 1)
        self.assertIsNotNone(self.record())

    def test_unblock_kill_terminates_the_group(self):
        pid = orphan_sleeper()
        self._guard_on(pid)
        out = subprocess.run([CLI, "unblock", "10", "--kill"], cwd=self.root,
                             capture_output=True, text=True)
        self.assertIn("UNBLOCKED:t10|ended", out.stdout)
        self.assertFalse(alive(pid))

    def test_every_unresolved_invocation_must_be_resolved(self):
        """Two unresolved invocations of one task: ending one keeps the task blocked."""
        sp = self.sp()
        # (A) a preview killed in its spawn gap: never establishable on its own.
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        kind, tok = rw.leader_identity(gone.pid)
        gone.wait()
        a_call = sp.admit("relations", "10", "manual", cap=40, dry_run=True)
        sp.write_preview(a_call, {"op": "relations", "task": "10", "call_id": a_call, "spawning": a_call,
                                  "owner": {"pid": gone.pid, "identity": tok, "identity_kind": kind}})
        # (B) a preview whose agent is alive but only weakly identifiable.
        b_agent = orphan_sleeper()
        b_tok = rw._pid_anchor("_pid_starttime_ps", str(b_agent))  # a real, but weak, token
        self.assertTrue(b_tok)
        b_call = sp.admit("relations", "10", "manual", cap=40, dry_run=True)
        sp.write_preview(b_call, {"op": "relations", "task": "10", "call_id": b_call, "spawning": b_call,
                                  "agent": {"pgid": b_agent, "leader_pid": b_agent,
                                            "identity": b_tok, "identity_kind": "ps"},
                                  "owner": {"pid": gone.pid, "identity": tok, "identity_kind": kind}})
        rw.recover_previews(sp)
        self.assertEqual(sorted(g["_inv"] for g in sp.guard("relations", "10")), sorted([a_call, b_call]))
        # (C) a worker-originated unresolved invocation of the same task.
        sp.enqueue("relations", "manual", "10", settle_s=0, now=True)
        job = sp.claim()
        c_call = sp.admit("relations", "10", "manual", cap=40)
        sp.update_running(job, call_id=c_call, spawning=c_call)
        rw.recover_running(str(self.root), sp)
        self.assertEqual(len(sp.guard("relations", "10")), 3)
        # Only B's agent ends; A and C remain unresolved.
        os.kill(b_agent, signal.SIGKILL)
        self.assertTrue(wait_for(lambda: not alive(b_agent), 10))
        sp.enqueue("relations", "created", "10", settle_s=0, now=True)
        rw.run_worker(str(self.root))
        self.assertEqual(self.launch_count(), 0)
        self.assertEqual(sorted(g["_inv"] for g in sp.guard("relations", "10")), sorted([a_call, c_call]))
        self.assertEqual(sp.job_state("10"), "failed(interrupted_unresolved)")
        dry = subprocess.run([CLI, "analyze", "10", "--dry-run"], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual((dry.returncode, dry.stdout.strip()), (3, "BLOCKED_UNRESOLVED"))
        out = subprocess.run([CLI, "unblock", "10"], cwd=self.root, capture_output=True, text=True)
        self.assertIn("remaining=2", out.stdout)
        out = subprocess.run([CLI, "unblock", "10", "--force"], cwd=self.root, capture_output=True, text=True)
        self.assertIn("UNBLOCKED:t10|forced", out.stdout)
        self.assertFalse(sp.guard("relations", "10"))

    def test_guard_written_between_the_scan_and_admission_blocks_a_job(self):
        sp = self.sp()
        sp.enqueue("relations", "manual", "10", settle_s=0, now=True, request_id="r")

        def hook(point, **ctx):
            if point == "before_admit":  # a concurrent recoverer guards the task now
                sp.write_guard("relations", "10", {"call_id": "other-invocation", "agent": None,
                                                   "why": "preview:spawn_gap"})
        with mock.patch.object(rw, "_test_hook", hook):
            rw.run_worker(str(self.root))
        self.assertEqual(self.launch_count(), 0)
        self.assertEqual(self.calls(sp), [])
        self.assertIsNone(self.record())
        self.assertEqual(sp.result("r")["outcome"], "BLOCKED_UNRESOLVED")

    def test_guard_written_between_the_scan_and_admission_blocks_a_dry_run(self):
        env = dict(os.environ, AIT_RELATIONS_TEST_BARRIER=f"before_admit:{self.tmp}")
        cli = subprocess.Popen([CLI, "analyze", "10", "--dry-run"], cwd=self.root, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self._procs.append(cli)
        self.assertTrue(wait_for(lambda: self.reached("before_admit")))
        self.sp().write_guard("relations", "10", {"call_id": "other-invocation", "agent": None,
                                                  "why": "preview:spawn_gap"})
        self.release("before_admit")
        out, _ = cli.communicate(timeout=60)
        self.assertEqual((cli.returncode, out.strip()), (3, "BLOCKED_UNRESOLVED"))
        self.assertEqual(self.launch_count(), 0)
        self.assertEqual(self.calls(), [])

    def test_pid_reuse_reads_as_ended(self):
        agent = {"pgid": os.getpid(), "leader_pid": os.getpid(), "identity": "1", "identity_kind": "proc"}
        self.assertEqual(rw.agent_ended(agent), ("ended", "pid_reused"))
        self.assertEqual(rw.agent_ended({"pgid": None}), ("unknown", "no_pgid"))

    def test_second_interruption_fails_visibly(self):
        sp = self.sp()
        sp.enqueue("relations", "manual", "10", settle_s=0, now=True, request_id="r")
        job = sp.claim()
        sp.update_running(job, interrupted=1)
        rw.recover_running(str(self.root), sp)
        self.assertEqual(sp.job_state("10"), "failed(interrupted)")
        self.assertEqual(sp.result("r")["outcome"], "FAILED:INTERRUPTED")

    def test_running_entry_merged_into_a_newer_request(self):
        sp = self.sp()
        sp.enqueue("relations", "plan_approved", "10", settle_s=0, request_id="old")
        job = sp.claim()
        sp.enqueue("relations", "created", "10", settle_s=50, request_id="new")
        rw.recover_running(str(self.root), sp)
        jobs = sp.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["trigger"], "plan_approved")
        self.assertEqual(sorted(jobs[0]["request_ids"]), ["new", "old"])
        self.assertIsNone(sp._read(sp.path("running", "relations__t10")))


# ================================================================ switches

class SwitchTests(WBase):
    """An opt-out made after work was queued stops every paid launch."""

    def _assert_skipped(self, sp, outcome, request_id):
        self.assertEqual(self.launch_count(), 0)
        self.assertEqual(self.calls(sp), [])
        self.assertIsNone(self.record())
        self.assertEqual(sp.result(request_id)["outcome"], outcome)   # a visible outcome
        rows, _ = sp.read_ledger()
        self.assertTrue(any(r.get("kind") == "job" and r.get("outcome") == outcome for r in rows))
        self.assertIsNone(sp.job_state("10"))

    def test_disabled_after_queueing(self):
        sp = self.sp()
        sp.enqueue("relations", "created", "10", settle_s=0, request_id="r")
        self.config(enabled=False)
        rw.run_worker(str(self.root))
        self._assert_skipped(sp, "SKIPPED:disabled", "r")

    def test_host_off_after_queueing(self):
        sp = self.sp()
        sp.enqueue("relations", "created", "10", settle_s=0, request_id="r")
        os.environ["AIT_RELATIONS"] = "0"
        rw.run_worker(str(self.root))
        self._assert_skipped(sp, "SKIPPED:host_off", "r")

    def test_switched_off_during_the_job_before_admission(self):
        sp = self.sp()
        sp.enqueue("relations", "created", "10", settle_s=0, request_id="r")

        def hook(point, **ctx):
            if point == "after_snapshot":
                self.config(enabled=False)  # flipped while candidates are gathered
        with mock.patch.object(rw, "_test_hook", hook):
            rw.run_worker(str(self.root))
        self._assert_skipped(sp, "SKIPPED:disabled", "r")

    def test_dry_run_is_the_exception(self):
        self.config(enabled=False)
        out = subprocess.run([CLI, "analyze", "10", "--dry-run"], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(self.launch_count(), 1)


# ================================================================ dry runs

class DryRunRecoveryTests(WBase):
    """A killed preview is recovered like a running job before any replacement."""

    def _kill_a_dry_run_mid_agent(self):
        pid_file = self.tmp / "pids"
        self.agent("spawn_child_sleep", pid_file=str(pid_file), sleep_s=120)
        cli = subprocess.Popen([sys.executable, str(LIB / "relations_cli.py"), "analyze", "10",
                                "--dry-run"], cwd=self.root, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        self._procs.append(cli)
        self.assertTrue(wait_for(pid_file.exists))
        leader, child = map(int, pid_file.read_text().split())
        cli.send_signal(signal.SIGKILL)
        cli.wait()
        self.assertTrue(alive(leader) and alive(child), "the preview's agent outlives its CLI")
        self.assertEqual(len(self.sp().previews()), 1)
        return pid_file, leader, child

    def test_second_dry_run_ends_the_orphan_first(self):
        pid_file, leader, child = self._kill_a_dry_run_mid_agent()
        violation = self.tmp / "violation"
        self.agent("ok", check_dead=str(pid_file), violation=str(violation))
        out = subprocess.run([CLI, "analyze", "10", "--dry-run"], cwd=self.root,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertFalse(violation.exists(), "a replacement started while the old group lived")
        self.assertFalse(alive(leader) or alive(child))
        sp = self.sp()
        self.assertEqual(sp.previews(), [])
        first = self.calls(sp)[0]["call_id"]
        self.assertEqual(self.outcomes(sp)[first]["outcome"], "interrupted")  # still counted
        self.assertIsNone(self.record())  # a preview never writes relation results

    def test_worker_start_recovers_a_killed_preview(self):
        _pid_file, leader, child = self._kill_a_dry_run_mid_agent()
        rw.run_worker(str(self.root))
        self.assertFalse(alive(leader) or alive(child))
        self.assertEqual(self.sp().previews(), [])

    def test_unestablishable_preview_guards_the_task(self):
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        kind, tok = rw.leader_identity(gone.pid)
        gone.wait()
        sp = self.sp()
        call_id = sp.admit("relations", "10", "manual", cap=40, dry_run=True)
        sp.write_preview(call_id, {"op": "relations", "task": "10", "call_id": call_id,
                                   "spawning": call_id,  # killed before its `agent` record
                                   "owner": {"pid": gone.pid, "identity": tok, "identity_kind": kind}})
        out = subprocess.run([CLI, "analyze", "10", "--dry-run"], cwd=self.root,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual((out.returncode, out.stdout.strip()), (3, "BLOCKED_UNRESOLVED"))
        self.assertTrue(sp.guard("relations", "10"))
        self.assertEqual(self.outcomes(sp)[call_id]["outcome"], "unresolved")
        self.assertEqual(self.launch_count(), 0)
        sp.enqueue("relations", "manual", "10", settle_s=0, now=True)
        rw.run_worker(str(self.root))                      # a worker job is held too
        self.assertEqual(self.launch_count(), 0)

    def test_a_live_preview_is_left_alone(self):
        sp = self.sp()
        call_id = sp.admit("relations", "10", "manual", cap=40, dry_run=True)
        kind, tok = rw.leader_identity(os.getpid())
        sp.write_preview(call_id, {"op": "relations", "task": "10", "call_id": call_id,
                                   "spawning": call_id,
                                   "owner": {"pid": os.getpid(), "identity": tok, "identity_kind": kind}})
        rw.recover_previews(sp)
        self.assertEqual(len(sp.previews()), 1)
        self.assertFalse(sp.guard("relations", "10"))


    def _preview(self, owner_pid, agent=None, spawning=True):
        sp = self.sp()
        call_id = sp.admit("relations", "10", "manual", cap=40, dry_run=True)
        kind, tok = rw.leader_identity(owner_pid)
        rec = {"op": "relations", "task": "10", "call_id": call_id,
               "owner": {"pid": owner_pid, "identity": tok, "identity_kind": kind}}
        if spawning:
            rec["spawning"] = call_id
        if agent is not None:
            akind, atok = rw.leader_identity(agent)
            rec["agent"] = {"pgid": agent, "leader_pid": agent, "identity": atok, "identity_kind": akind}
        sp.write_preview(call_id, rec)
        return sp, call_id

    def test_preview_dying_after_startup_is_reconciled_before_admission(self):
        owner = orphan_sleeper()
        agent = orphan_sleeper()
        sp, call_id = self._preview(owner, agent=agent)
        dead_file = self.tmp / "dead"
        dead_file.write_text(str(agent))
        violation = self.tmp / "violation"
        self.agent("ok", check_dead=str(dead_file), violation=str(violation))
        sp.enqueue("relations", "manual", "10", settle_s=0, now=True)

        def hook(point, **ctx):
            if point == "after_snapshot":  # the preview's CLI dies mid-job
                os.kill(owner, signal.SIGKILL)
                assert wait_for(lambda: not alive(owner), 10)
        with mock.patch.object(rw, "_test_hook", hook):
            rw.run_worker(str(self.root))   # startup recovery saw a LIVE preview
        self.assertFalse(violation.exists(), "the worker launched while the preview's agent lived")
        self.assertFalse(alive(agent))
        self.assertIsNotNone(self.record())
        self.assertEqual(sp.previews(), [])
        self.assertEqual(self.outcomes(sp)[call_id]["outcome"], "interrupted")

    def test_concurrent_recoverers_act_once(self):
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait()
        sp, call_id = self._preview(gone.pid, spawning=False)
        code = ("import sys; sys.path.insert(0, %r); import relations_worker as rw, relations_spool as rsp;"
                " rw.recover_previews(rsp.Spool(%r))" % (str(LIB), rw.state_dir(str(self.root))))
        env = dict(os.environ, AIT_RELATIONS_TEST_BARRIER=f"preview_listed:{self.tmp}")
        other = subprocess.Popen([sys.executable, "-c", code], env=env)
        self._procs.append(other)
        self.assertTrue(wait_for(lambda: self.reached("preview_listed")))
        rw.recover_previews(sp)              # recovers while the other holds a stale listing
        self.release("preview_listed")
        self.assertEqual(other.wait(timeout=60), 0)
        rows, _ = sp.read_ledger()
        self.assertEqual(len([r for r in rows if r.get("kind") == "job"
                              and r.get("invocation") == call_id]), 1)
        self.assertEqual(len([r for r in rows if r.get("kind") == "outcome"
                              and r.get("call_id") == call_id]), 1)
        self.assertEqual(sp.previews(), [])

    def test_accounting_is_idempotent_per_invocation(self):
        sp = self.sp()
        call_id = sp.admit("relations", "10", "manual", cap=40)
        self.assertTrue(sp.settle_call(call_id, "interrupted"))
        self.assertFalse(sp.settle_call(call_id, "interrupted"))
        self.assertTrue(sp.log_job("relations", "10", "manual", "FAILED:INTERRUPTED", invocation=call_id))
        self.assertFalse(sp.log_job("relations", "10", "manual", "FAILED:INTERRUPTED", invocation=call_id))
        rows, _ = sp.read_ledger()
        self.assertEqual(len([r for r in rows if r.get("kind") in ("outcome", "job")]), 2)


# ================================================================== usage

class UsageCountTests(WBase):
    def test_one_job_row_per_terminal_job(self):
        self.config(job_timeout_s=1)
        self.agent("sleep", sleep_s=30)
        sp = self.run_job()                               # attempt 1: timeout, requeued
        rw.process_job(str(self.root), sp, sp.claim())    # attempt 2: timeout, failed
        self.agent("ok")
        self.run_job()                                    # a successful paid job
        rows, _ = sp.read_ledger()
        jobs = [r for r in rows if r.get("kind") == "job"]
        self.assertEqual([j["outcome"] for j in jobs], ["FAILED:TIMEOUT", "ANALYSED(published)"])
        self.assertEqual(len(self.calls(sp)), 3)


if __name__ == "__main__":
    unittest.main()
