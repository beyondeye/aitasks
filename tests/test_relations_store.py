"""Tests for the task-relations store (t1981_1).

Scratch working repos plus a bare ``origin`` under a temp dir; never the real
``aitask-relations`` branch and never ``~/.aitask*``. No test changes the
process cwd: every Store is built with an explicit repo path.

Interleavings are deterministic: ``relations_store._test_hook`` is replaced
by a callback that runs the competing operation synchronously at a named point.

Run: python3 tests/test_relations_store.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_LIB = Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"
sys.path.insert(0, str(_LIB))

import orphan_ref_store as ors  # noqa: E402
import relations_schema as rs  # noqa: E402
import relations_store as rst  # noqa: E402

HAVE_ZSTD = shutil.which("zstd") is not None
C1 = "2026-01-01 10:00"
C2 = "2026-02-02 11:00"


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check,
                          capture_output=True, text=True).stdout.strip()


# ------------------------------------------------------------------ fixture

class Env:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.remote = tmp / "origin.git"
        git(tmp, "init", "-q", "--bare", str(self.remote))

    def clone(self, name, remote=True, project="aitasks") -> Path:
        root = self.tmp / name
        root.mkdir()
        git(root, "init", "-q")
        git(root, "config", "user.email", "t@example.com")
        git(root, "config", "user.name", "T")
        if remote:
            git(root, "remote", "add", "origin", str(self.remote))
        for d in ("aitasks/metadata", "aitasks/archived", "aiplans/archived"):
            (root / d).mkdir(parents=True)
        if project is not None:
            set_config(root, project)
        return root


def set_config(root, project="aitasks", relations_enabled=None):
    text = f"project:\n  name: {project}\n"
    if relations_enabled is not None:
        text += f"relations:\n  enabled: {'true' if relations_enabled else 'false'}\n"
    (root / "aitasks/metadata/project_config.yaml").write_text(text)


def task_text(created, body="Goal text.\n", status="Ready", folded_into=None,
              folded_tasks=None, extra=""):
    fm = [f"status: {status}", f"created_at: {created}"]
    if folded_into:
        fm.append(f"folded_into: {folded_into}")
    if folded_tasks:
        fm.append(f"folded_tasks: [{', '.join(str(x) for x in folded_tasks)}]")
    return "---\n" + "\n".join(fm) + "\n---\n\n" + body + extra


def task_relpath(tid, archived=False):
    base = "aitasks/archived" if archived else "aitasks"
    if "_" in tid:
        p, _c = tid.split("_")
        return f"{base}/t{p}/t{tid}_name.md"
    return f"{base}/t{tid}_name.md"


def write_task(root, tid, created, archived=False, **kw):
    path = root / task_relpath(tid, archived)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_text(created, **kw), encoding="utf-8")
    return path


def write_plan(root, tid, text, archived=False):
    base = "aiplans/archived" if archived else "aiplans"
    if "_" in tid:
        p, _c = tid.split("_")
        path = root / base / f"p{p}" / f"p{tid}_name.md"
    else:
        path = root / base / f"p{tid}_name.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_bundle(path: Path, members: dict, corrupt=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, text in members.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    raw = buf.getvalue()
    out = subprocess.run(["zstd", "-q", "-c"], input=raw, capture_output=True, check=True).stdout
    if corrupt:
        out = out[: len(out) // 2]
    path.write_bytes(out)


def S(root, **kw) -> rst.Store:
    return rst.Store(str(root), timeout=kw.pop("timeout", 15), **kw)


def _qref(value, project):
    return rs.qref(value) if "#" in str(value) else f"{project}#{rs.norm_id(value)}"


def record(root, tid, rels=(), stage=1, at="2026-11-05T10:00:00Z", created=None,
           cands=None, coverage=None, project="aitasks"):
    """A valid relations record for ``tid`` whose digests match the live files.

    Relation ends may be bare ids (local project) or qualified refs; a ref of
    another project gets a candidate entry with no readable digests.
    """
    idx = rst.TaskIndex(str(root))
    own = _qref(tid, project)
    tid = rs.norm_id(tid)
    created = created or idx.live_created_at(tid)
    rels = list(rels)
    cand_refs = list(cands) if cands is not None else sorted(
        {_qref(e, project) for r in rels for e in (r[0], r[1])} - {own})
    candidates = []
    for ref in cand_refs:
        ref = _qref(ref, project)
        proj, cid = rs.parse_ref(ref)
        local = proj == project
        candidates.append({
            "ref": ref, "created_at": (idx.live_created_at(cid) if local else None) or C1,
            "body_sha256": _d(idx.body_digest(cid)) if local else None,
            "plan_sha256": _d(idx.plan_digest(cid)) if local else None})
    relations = []
    for frm, to, rtype, *rest in rels:
        basis = rest[0] if rest else [{"kind": "path", "value": "lib/x/shared.py"}]
        relations.append({"from": _qref(frm, project), "to": _qref(to, project),
                          "type": rtype, "description": f"{frm} {rtype} {to}", "basis": basis})
    rec = {
        "schema": rs.SCHEMA, "task": own, "task_created_at": created,
        "analysed": True,
        "run": {"id": "r1", "trigger": "manual", "stage": stage, "at": at},
        "inputs": {"source": {"body_sha256": _d(idx.body_digest(tid)) or "0" * 64,
                              "plan_sha256": _d(idx.plan_digest(tid))},
                   "candidates": candidates},
        "relations": relations,
    }
    if coverage:
        rec["coverage"] = {"missing_sources": coverage}
    return rec


def _d(value):
    return None if value in (None, rst.UNREADABLE) else value


def stamp(root, tid, plan_sha, created=None):
    idx = rst.TaskIndex(str(root))
    return {"task": f"aitasks#{tid}", "task_created_at": created or idx.live_created_at(tid),
            "approved_at": "2026-11-05T09:00:00Z", "data_commit": "abc",
            "body_sha256": idx.body_digest(tid), "plan_sha256": plan_sha}


def remote_files(env) -> dict:
    tip = ors.resolve(env.remote, "refs/heads/aitask-relations")
    return ors.read_files(env.remote, tip) if tip else {}


class HookPlan:
    """Replace _test_hook: run ``fn`` once at ``point`` (optionally a given attempt)."""

    def __init__(self, point, fn, attempt=None):
        self.point, self.fn, self.attempt, self.fired = point, fn, attempt, False

    def __call__(self, point, **ctx):
        if point != self.point or self.fired:
            return
        if self.attempt is not None and ctx.get("attempt") != self.attempt:
            return
        self.fired = True
        self.fn(**ctx)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="relations-test-")
        self.tmp = Path(self._tmp.name)
        home = self.tmp / "home"
        home.mkdir()
        patch = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                 "HOME": str(home), "GIT_TERMINAL_PROMPT": "0"}
        self._env = mock.patch.dict(os.environ, patch)
        self._env.start()
        for key in ("AITASKS_HOME", "AIT_RELATIONS", "TASK_DIR", "PLAN_DIR",
                    "ARCHIVED_DIR", "ARCHIVED_PLAN_DIR"):
            os.environ.pop(key, None)
        self.env = Env(self.tmp)

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def new_env(self, name):
        sub = self.tmp / name
        sub.mkdir()
        self.env = Env(sub)
        return self.env

    def tasks(self, roots, spec):
        """spec: {tid: created} written to every root."""
        for root in roots:
            for tid, created in spec.items():
                write_task(root, tid, created)

    def publish(self, root, tid, rels=(), **kw):
        out = S(root).write(rs.store_path("records", tid), record(root, tid, rels, **kw))
        self.assertTrue(any(x.startswith("PUBLISHED:") for x in out), out)
        return out


# ------------------------------------------------------------------- schema

class SchemaTests(Base):
    def setUp(self):
        super().setUp()
        self.root = self.env.clone("a", remote=False)
        self.tasks([self.root], {"1": C1, "2": C1})

    def rec(self, **kw):
        return record(self.root, "1", [("1", "2", "affects")], **kw)

    def test_valid_record_passes(self):
        rs.validate("records", "records/t1.json", self.rec())

    def test_rejections(self):
        cases = []
        r = self.rec(); r["relations"][0]["type"] = "blocks"; cases.append(r)
        r = self.rec(); r["relations"][0]["basis"] = [{"kind": "task_ref", "value": "t2"}]; cases.append(r)
        r = self.rec(); r["bogus"] = 1; cases.append(r)
        r = self.rec(); r["relations"][0]["basis"] = [{"kind": "path", "value": "shared.py"}]; cases.append(r)
        r = self.rec(); r["relations"][0]["basis"] = [{"kind": "path", "value": "../x/y.py"}]; cases.append(r)
        r = self.rec(); r["inputs"]["candidates"] = []; cases.append(r)
        r = self.rec(); r["relations"][0]["description"] = "x" * 601; cases.append(r)
        r = self.rec(); del r["task_created_at"]; cases.append(r)
        for i, bad in enumerate(cases):
            with self.subTest(i=i), self.assertRaises(rs.SchemaError):
                rs.validate("records", "records/t1.json", bad)
        with self.assertRaises(rs.SchemaError):
            rs.validate("records", "records/t2.json", self.rec())  # path/task mismatch

    def test_task_created_at_required_on_every_kind(self):
        approval = stamp(self.root, "1", "a" * 64)
        dismissal = {"task": "aitasks#1", "task_created_at": C1, "at": "x", "by": "me",
                     "evidence_digest": "b" * 64}
        obs = {"schema": rs.SCHEMA, "task": "aitasks#1", "task_created_at": C1,
               "run": {"id": "r", "trigger": "manual", "stage": 1, "at": "x"},
               "inputs": {"body_sha256": "a" * 64, "plan_sha256": None, "evidence_digest": "c" * 64},
               "evidence": [], "band": "low", "reasons": [], "disposition": "keep"}
        for kind, obj in (("approvals", approval), ("dismissals", dismissal), ("obsolescence", obs)):
            rs.validate(kind, f"{kind}/t1.json", obj)
            bad = dict(obj); del bad["task_created_at"]
            with self.subTest(kind=kind), self.assertRaises(rs.SchemaError):
                rs.validate(kind, f"{kind}/t1.json", bad)

    def test_wins_identity_first(self):
        old = {"task_created_at": C1, "run": {"stage": 2, "at": "2026-12-01"}}
        new = {"task_created_at": C2, "run": {"stage": 1, "at": "2026-01-01"}}
        self.assertTrue(rs.wins("records", new, old, C2))
        self.assertFalse(rs.wins("records", old, new, C2))
        self.assertFalse(rs.wins("records", new, old, None))  # unknown identity: (stage, at)
        with self.assertRaises(ValueError):
            rs.wins("records", None, old, C2)


class DigestTests(unittest.TestCase):
    def test_plan_normalization(self):
        plan = "---\nTask: t1.md\nBase branch: main\n---\n\n# Plan\n\nStep 1.\n"
        moved = plan.replace("Base branch: main", "Base branch: dev\nWorktree: aiwork/x")
        noted = plan + "\n## Final Implementation Notes\n\n- done\n\n## Post-Review Changes\n\n- y\n"
        d = rs.sha256_text(rs.normalize_plan(plan))
        self.assertEqual(d, rs.sha256_text(rs.normalize_plan(moved)))
        self.assertEqual(d, rs.sha256_text(rs.normalize_plan(noted)))
        self.assertNotEqual(d, rs.sha256_text(rs.normalize_plan(plan + "Step 2.\n")))

    def test_body_normalization_ignores_framework_sections(self):
        body = task_text(C1)
        ledger = body + ("\n## Gate Runs\n<!-- Appended by the gate framework. -->\n\n"
                         "> **✅ gate:plan_approved** run=2026-11-04T10:14:07Z status=pass attempt=1 type=human\n")
        self.assertEqual(rs.digests(body)["body_sha256"], rs.digests(ledger)["body_sha256"])
        self.assertNotEqual(rs.digests(body)["body_sha256"],
                            rs.digests(body + "More goal.\n")["body_sha256"])


# ------------------------------------------------------------- local / read

class LocalAndReadTests(Base):
    def test_local_only_forward_and_reverse(self):
        root = self.env.clone("a", remote=False)
        self.tasks([root], {"1": C1, "2": C1})
        self.publish(root, "1", [("1", "2", "affects")])
        snap = S(root).read()
        self.assertEqual(snap.state, "local_only")
        fwd = S(root).relations("1")
        rev = S(root).relations("2")
        self.assertEqual([r.direction for r in fwd], ["this task affects t2"])
        self.assertEqual([r.direction for r in rev], ["t1 affects this task"])
        self.assertEqual(rev[0].freshness, "fresh")

    def test_outbox_overlay_pending(self):
        root = self.env.clone("a")
        self.tasks([root], {"1": C1, "2": C1})
        out = S(root).write("records/t1.json", record(root, "1", [("1", "2", "informs", [])]),
                            flush=False)
        self.assertEqual(out, ["OUTBOX:records/t1.json"])
        snap = S(root).read()
        self.assertIn("records/t1.json", snap.pending)
        self.assertTrue(S(root).relations("2")[0].pending_push)

    def test_store_states(self):
        root = self.env.clone("a")
        self.tasks([root], {"1": C1, "2": C1})
        self.assertEqual(S(root).read().state, "empty")
        self.publish(root, "1", [("1", "2", "affects")])
        self.assertTrue(S(root).read().state.startswith("fresh@"))
        git(root, "remote", "set-url", "origin", str(self.tmp / "missing.git"))
        self.assertRegex(S(root).read().state, r"^stale:.+@\d{4}-")
        self.assertEqual(len(S(root).relations("2")), 1)  # latest known data kept
        fresh = self.env.clone("b")
        git(fresh, "remote", "set-url", "origin", str(self.tmp / "missing.git"))
        self.assertTrue(S(fresh).read().state.startswith("unreachable:"))
        self.assertEqual(S(fresh).analysis_line("1"), "unknown(store_unreachable)")
        self.assertEqual(S(fresh).read(no_fetch=True).state, "unreachable:no_fetch")
        # a clone that never fetched but holds local-only data: stale@never
        loc = self.env.clone("c", remote=False)
        self.tasks([loc], {"1": C1, "2": C1})
        self.publish(loc, "1", [("1", "2", "affects")])
        git(loc, "remote", "add", "origin", str(self.tmp / "missing.git"))
        self.assertRegex(S(loc).read().state, r"^stale:.+@never$")

    def test_analysis_line(self):
        root = self.env.clone("a", remote=False)
        self.tasks([root], {"1": C1, "2": C1})
        self.assertEqual(S(root).analysis_line("1"), "disabled")
        set_config(root, relations_enabled=True)
        self.assertEqual(S(root).analysis_line("1"), "never")
        self.assertEqual(S(root).relations_state(), "enabled")
        with mock.patch.dict(os.environ, {"AIT_RELATIONS": "0"}):
            self.assertEqual(S(root).relations_state(), "host_off")
        self.publish(root, "1", [("1", "2", "affects")], stage=2, coverage=["cites"])
        self.assertEqual(S(root).analysis_line("1"), "analysed:1(stage=2,partial)")
        write_task(root, "1", C1, body="Changed goal.\n")
        self.assertEqual(S(root).analysis_line("1"), "analysed:1(stage=2,stale,partial)")


# ---------------------------------------------------------- remote / outbox

class RemoteTests(Base):
    def test_unreachable_retains_then_publishes(self):
        root = self.env.clone("a")
        self.tasks([root], {"1": C1, "2": C1})
        git(root, "remote", "set-url", "origin", str(self.tmp / "nowhere.git"))
        out = S(root).write("records/t1.json", record(root, "1", [("1", "2", "affects")]))
        self.assertTrue(out[-1].startswith("RETAINED:1|"), out)
        status = S(root).status()
        self.assertTrue(status[0].startswith("OUTBOX:records/t1.json|age="), status)
        self.assertNotIn("err=-", status[0])
        git(root, "remote", "set-url", "origin", str(self.env.remote))
        self.assertIn("PUBLISHED:1", S(root).flush())
        self.assertEqual(S(root).status(), ["OUTBOX:none"])
        self.assertIn("records/t1.json", remote_files(self.env))

    def test_two_clone_cas_race(self):
        a, b = self.env.clone("a"), self.env.clone("b")
        self.tasks([a, b], {"1": C1, "2": C1, "3": C1})

        def b_publishes(**_):
            self.publish(b, "3", [("3", "2", "informs", [])])

        with mock.patch.object(rst, "_test_hook", HookPlan("after_pin", b_publishes)):
            out = S(a).write("records/t1.json", record(a, "1", [("1", "2", "affects")]))
        self.assertIn("PUBLISHED:1", out)
        files = remote_files(self.env)
        self.assertIn("records/t1.json", files)
        self.assertIn("records/t3.json", files)

    def test_newest_wins_superseded_and_stale_run(self):
        a, b = self.env.clone("a"), self.env.clone("b")
        self.tasks([a, b], {"1": C1, "2": C1})
        self.publish(b, "1", [("1", "2", "affects")], stage=2, at="2026-11-05T12:00:00Z")
        out = S(a).write("records/t1.json", record(a, "1", [("1", "2", "informs", [])], stage=1))
        self.assertIn("SUPERSEDED:records/t1.json", out)
        self.assertEqual(S(a).status(), ["OUTBOX:none"])
        out = S(a).write("records/t1.json", record(a, "1", [("1", "2", "informs", [])], stage=1,
                                                    at="2026-11-06T00:00:00Z"))
        self.assertEqual(out, ["STALE_RUN:records/t1.json"])

    def test_replacement_child_identity_first(self):
        a = self.env.clone("a")
        self.tasks([a], {"5": C1, "9": C1})
        write_task(a, "5_2", C1)
        self.publish(a, "5_2", [("5_2", "9", "affects")], stage=2, at="2026-12-01T00:00:00Z")
        # the child is deleted and its number reused by a new, unapproved task
        write_task(a, "5_2", C2, body="A different child.\n")
        new = record(a, "5_2", [("5_2", "9", "informs", [])], stage=1, at="2026-01-01T00:00:00Z")
        out = S(a).write("records/t5_2.json", new)
        self.assertNotIn("STALE_RUN:records/t5_2.json", out)
        self.assertNotIn("SUPERSEDED:records/t5_2.json", out)
        self.assertIn("PUBLISHED:1", out)
        rel = S(a).relations("5_2")
        self.assertEqual([r.type for r in rel], ["informs"])
        old = record(a, "5_2", [("5_2", "9", "affects")], created=C1)
        self.assertEqual(S(a).write("records/t5_2.json", old), ["IDENTITY_MISMATCH:records/t5_2.json"])

    def test_removal_interleaving_both_paths(self):
        a, b = self.env.clone("a"), self.env.clone("b")
        self.tasks([a, b], {"1": C1, "2": C1, "3": C1})
        self.publish(b, "3", [("3", "2", "affects")], stage=2, at="2026-12-01T00:00:00Z")
        store = S(a)
        store.write("records/t1.json", record(a, "1", [("1", "2", "affects")]), flush=False)
        store.write("records/t3.json", record(a, "3", [("3", "2", "informs", [])], stage=1),
                    flush=False)
        rewritten = {}

        def rewrite(**_):
            for path, tid in (("records/t1.json", "1"), ("records/t3.json", "3")):
                rec = record(a, tid, [(tid, "2", "advisory_precedes", [])], stage=2,
                             at="2026-12-09T00:00:00Z")
                data = rst._dumps(rec)
                Path(store.outbox_dir, path).write_bytes(data)
                rewritten[path] = data

        with mock.patch.object(rst, "_test_hook", HookPlan("before_removal", rewrite)):
            out = S(a).flush()
        self.assertIn("PUBLISHED:1", out)
        self.assertIn("SUPERSEDED:records/t3.json", out)
        for path, data in rewritten.items():
            self.assertEqual(Path(store.outbox_dir, path).read_bytes(), data, path)

    def test_same_clone_bookkeeping_never_rewinds(self):
        a = self.env.clone("a")
        self.tasks([a], {"1": C1, "2": C1, "3": C1})

        def second_publisher(**_):
            S(a).write("records/t3.json", record(a, "3", [("3", "2", "informs", [])]))

        with mock.patch.object(rst, "_test_hook", HookPlan("before_bookkeeping", second_publisher)):
            S(a).write("records/t1.json", record(a, "1", [("1", "2", "affects")]))
        tip = ors.resolve(self.env.remote, "refs/heads/aitask-relations")
        self.assertEqual(ors.resolve(a, rst.L_REF), tip)
        snap = S(a).read()
        self.assertTrue(snap.state.startswith("fresh@"))
        self.assertEqual({"records/t1.json", "records/t3.json"}, set(snap.files))


# ---------------------------------------------------------- the ref model

class RefModelTests(Base):
    def test_upgrade_remote_absent(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "2": C1})
        self.publish(a, "1", [("1", "2", "affects")])
        git(a, "remote", "add", "origin", str(self.env.remote))
        out = S(a).flush()
        self.assertIn("UPGRADED:1", out)
        self.assertIn("records/t1.json", remote_files(self.env))
        self.assertNotIn("UPGRADED:1", " ".join(S(a).flush()))

    def test_upgrade_independent_histories_and_no_resurrection(self):
        a, b = self.env.clone("a", remote=False), self.env.clone("b")
        self.tasks([a], {"1": C1, "2": C1, "3": C1})
        self.tasks([b], {"2": C1, "3": C1})
        self.publish(b, "3", [("3", "2", "informs", [])])
        self.publish(a, "1", [("1", "2", "affects")])
        git(a, "remote", "add", "origin", str(self.env.remote))
        out = S(a).flush()
        self.assertTrue(any(x.startswith("UPGRADED:") for x in out), out)
        tip = ors.resolve(self.env.remote, "refs/heads/aitask-relations")
        parents = git(self.env.remote, "rev-list", "--parents", "-n1", tip).split()[1:]
        files = remote_files(self.env)
        self.assertIn("records/t1.json", files)
        self.assertIn("records/t3.json", files)
        self.assertTrue(ors.is_ancestor(a, ors.resolve(a, rst.L_REF), tip))
        self.assertGreaterEqual(len(parents), 1)
        self.assertEqual([x for x in S(a).flush() if x.startswith("UPGRADED")], [])
        # b does not know task 1: gc there removes it; a must not resurrect it
        out = S(b).gc()
        self.assertIn("GC_REMOVED:records/t1.json|task_gone", out)
        S(a).read()
        S(a).flush()
        self.assertNotIn("records/t1.json", remote_files(self.env))
        self.assertNotIn("records/t1.json", S(a).read().files)

    def test_local_descendant_with_empty_outbox(self):
        a = self.env.clone("a")
        self.tasks([a], {"1": C1, "2": C1, "3": C1})
        self.publish(a, "3", [("3", "2", "informs", [])])
        git(a, "remote", "remove", "origin")
        self.publish(a, "1", [("1", "2", "affects")])  # local-only commit; outbox drains
        self.assertEqual(S(a).status(), ["OUTBOX:none"])
        git(a, "remote", "add", "origin", str(self.env.remote))
        out = S(a).flush()
        self.assertIn("UPGRADED:1", out)
        self.assertIn("records/t1.json", remote_files(self.env))

    def test_local_descendant_remote_moved(self):
        a, b = self.env.clone("a"), self.env.clone("b")
        self.tasks([a, b], {"1": C1, "2": C1, "3": C1, "4": C1})
        self.publish(a, "3", [("3", "2", "informs", [])])
        git(a, "remote", "remove", "origin")
        self.publish(a, "1", [("1", "2", "affects")])
        self.publish(b, "4", [("4", "2", "informs", [])])
        git(a, "remote", "add", "origin", str(self.env.remote))
        S(a).flush()
        self.assertEqual({"records/t1.json", "records/t3.json", "records/t4.json"},
                         {p for p in remote_files(self.env) if p.startswith("records/")})

    def test_local_remote_local_keeps_everything(self):
        a, b = self.env.clone("a", remote=False), self.env.clone("b")
        self.tasks([a, b], {"1": C1, "2": C1, "3": C1, "4": C1})
        self.publish(a, "1", [("1", "2", "affects")])
        git(a, "remote", "add", "origin", str(self.env.remote))
        S(a).flush()
        self.publish(b, "3", [("3", "2", "informs", [])])
        S(a).read()  # fetches b's record into L
        self.publish(a, "4", [("4", "2", "informs", [])])
        git(a, "remote", "remove", "origin")
        self.assertFalse(git(a, "for-each-ref", "refs/remotes/"))
        snap = S(a).read()
        self.assertEqual(snap.state, "local_only")
        self.assertEqual({"records/t1.json", "records/t3.json", "records/t4.json"}, set(snap.files))

    def test_snapshot_race_after_resolve_local_and_after_pin(self):
        for point in ("after_resolve_local", "after_pin"):
            with self.subTest(point=point):
                self.new_env(point)
                a = self.env.clone("a")
                self.tasks([a], {"1": C1, "2": C1, "3": C1})
                self.publish(a, "3", [("3", "2", "informs", [])])
                # task 3 disappears; a cleanup in the same clone deletes its record
                (a / task_relpath("3")).unlink()

                def cleanup(**_):
                    self.assertIn("GC_REMOVED:records/t3.json|task_gone", S(a).gc())

                with mock.patch.object(rst, "_test_hook", HookPlan(point, cleanup)):
                    out = S(a).write("records/t1.json", record(a, "1", [("1", "2", "affects")]))
                self.assertIn("PUBLISHED:1", out)
                files = remote_files(self.env)
                self.assertNotIn("records/t3.json", files)
                self.assertIn("records/t1.json", files)

    def test_two_upgraders_in_one_clone(self):
        a, b = self.env.clone("a", remote=False), self.env.clone("b")
        self.tasks([a, b], {"1": C1, "2": C1, "3": C1})
        self.publish(b, "3", [("3", "2", "informs", [])])
        self.publish(a, "1", [("1", "2", "affects")])
        git(a, "remote", "add", "origin", str(self.env.remote))

        def other_upgrader(**_):
            S(a).flush()

        with mock.patch.object(rst, "_test_hook", HookPlan("after_pin", other_upgrader)):
            S(a).flush()
        merges = git(self.env.remote, "rev-list", "--merges", "refs/heads/aitask-relations")
        self.assertEqual(len(merges.split()), 1, merges)

    def test_lease_rejects_stale_base_even_with_tip_as_parent(self):
        a = self.env.clone("a")
        self.tasks([a], {"1": C1, "2": C1, "3": C1})
        self.publish(a, "1", [("1", "2", "affects")])
        r = ors.resolve(a, rst.L_REF)
        self.publish(a, "3", [("3", "2", "informs", [])])
        c = ors.resolve(self.env.remote, "refs/heads/aitask-relations")
        stale = ors.commit_tree_from_files(a, ors.read_files(a, r), "stale", parents=(r, c))
        self.assertEqual(ors.cas_push(a, stale, rst.BRANCH, r, 15), "CONFLICT")
        self.assertEqual(ors.cas_push(a, stale, rst.BRANCH, c, 15), "OK")

    def test_merge_path_table(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "2": C1})
        store = S(a)
        p = "records/t1.json"
        live = rst._dumps(record(a, "1", [("1", "2", "affects")], at="2026-11-06T00:00:00Z"))
        older = rst._dumps(record(a, "1", [("1", "2", "informs", [])], at="2026-11-01T00:00:00Z"))
        dead = rst._dumps(record(a, "1", [("1", "2", "informs", [])], created=C2))
        mp = store.merge_path
        with self.assertRaises(ValueError):
            mp(p, [], live, older)
        self.assertEqual(mp(p, [None], live, live), live)            # l == r
        self.assertEqual(mp(p, [older], older, live), live)          # l untouched
        self.assertEqual(mp(p, [older], live, older), live)          # r untouched, l present
        self.assertEqual(mp(p, [live], None, live), live)            # local deletion, r valid
        self.assertIsNone(mp(p, [dead], None, dead))                 # local deletion, r eligible
        self.assertEqual(mp(p, [None], live, older), live)           # both changed -> wins
        self.assertEqual(mp(p, [None], older, live), live)
        self.assertEqual(mp(p, [older], live, None), live)           # remote deletion vs live local
        self.assertIsNone(mp(p, [older], dead, None))                # remote deletion vs dead local
        self.assertEqual(mp(p, [older], None, live), live)           # local deletion vs remote modification
        self.assertEqual(mp(p, [older, live], live, dead), live)     # criss-cross: l untouched? no
        # zero merge bases through the real normalization (unrelated histories)
        lc = ors.commit_tree_from_files(a, {"records/t1.json": live, "records/t9.json": older}, "l")
        rc = ors.commit_tree_from_files(a, {"records/t1.json": older, "records/t8.json": older}, "r")
        self.assertEqual(ors.merge_bases(a, lc, rc), [])
        merged = store.three_way(lc, rc)
        self.assertEqual(merged["records/t9.json"], older)  # local-only path kept
        self.assertEqual(merged["records/t8.json"], older)  # remote-only path kept
        self.assertEqual(merged["records/t1.json"], live)   # conflict: local newer wins

    def test_publish_vs_concurrent_absorb_keeps_x(self):
        a = self.env.clone("a")
        self.tasks([a], {"1": C1, "2": C1, "3": C1})
        self.publish(a, "3", [("3", "2", "informs", [])])
        store = S(a)

        def sibling(commit, **_):
            # a concurrent reader's absorb: another child of L, sibling of the pushed P
            cur = ors.resolve(a, rst.L_REF)
            files = ors.read_files(a, cur)
            files["records/t7.json"] = b"{}\n"
            s = ors.commit_tree_from_files(a, files, "sibling", parents=(cur,))
            self.assertEqual(ors.cas_local(a, rst.L_REF, s, cur), "OK")

        with mock.patch.object(rst, "_test_hook", HookPlan("before_bookkeeping", sibling)):
            out = store.write("records/t1.json", record(a, "1", [("1", "2", "affects")]))
        self.assertIn("PUBLISHED:1", out)
        self.assertEqual(S(a).status(), ["OUTBOX:none"])
        git(a, "remote", "set-url", "origin", str(self.tmp / "gone.git"))
        self.assertIn("records/t1.json", S(a).read().files)
        git(a, "remote", "remove", "origin")
        self.assertIn("records/t1.json", S(a).read().files)

    def test_integrate_failure_keeps_outbox(self):
        a = self.env.clone("a")
        self.tasks([a], {"1": C1, "2": C1})
        real = rst.Store.integrate
        calls = {"n": 0}

        def flaky(self_, commit):
            calls["n"] += 1
            if calls["n"] == 1 and ors.resolve(self_.root, rst.L_REF) is None:
                return False
            return real(self_, commit)

        with mock.patch.object(rst.Store, "integrate", flaky):
            out = S(a).write("records/t1.json", record(a, "1", [("1", "2", "affects")]))
        self.assertTrue(any(x.startswith("RETAINED:") and "integrate_failed" in x for x in out), out)
        self.assertIn("records/t1.json", S(a).read(no_fetch=True).files)
        before = ors.resolve(self.env.remote, "refs/heads/aitask-relations")
        out = S(a).flush()
        self.assertEqual(S(a).status(), ["OUTBOX:none"])
        self.assertEqual(ors.resolve(self.env.remote, "refs/heads/aitask-relations"), before)

    def test_divergent_fallback_continuity(self):
        a, b = self.env.clone("a", remote=False), self.env.clone("b")
        self.tasks([a, b], {"1": C1, "2": C1, "3": C1})
        self.publish(a, "1", [("1", "2", "affects")])
        self.publish(b, "3", [("3", "2", "informs", [])])
        git(a, "remote", "add", "origin", str(self.env.remote))
        snap = S(a).read()
        self.assertEqual({"records/t1.json", "records/t3.json"}, set(snap.files))
        self.assertEqual(snap.pending, {"records/t1.json"})
        git(a, "remote", "set-url", "origin", str(self.tmp / "gone.git"))
        snap = S(a).read()
        self.assertTrue(snap.state.startswith("stale:"))
        self.assertEqual({"records/t1.json", "records/t3.json"}, set(snap.files))
        git(a, "remote", "remove", "origin")
        self.assertEqual({"records/t1.json", "records/t3.json"}, set(S(a).read().files))
        git(a, "remote", "add", "origin", str(self.env.remote))
        before = remote_files(self.env)["records/t3.json"]
        S(a).flush()
        files = remote_files(self.env)
        self.assertIn("records/t1.json", files)
        self.assertEqual(files["records/t3.json"], before)

    def test_offline_gc_vs_remote_replacement(self):
        for replaced in (True, False):
            with self.subTest(replaced=replaced):
                self.new_env(f"case_{replaced}")
                a, b = self.env.clone("a"), self.env.clone("b")
                self.tasks([a, b], {"5": C1, "9": C1})
                for root in (a, b):
                    write_task(root, "5_2", C1)
                self.publish(a, "5_2", [("5_2", "9", "affects")])
                S(b).read()
                for root in (a, b):  # the child is recreated with a new identity
                    write_task(root, "5_2", C2, body="New child.\n")
                git(a, "remote", "remove", "origin")
                self.assertIn("GC_REMOVED:records/t5_2.json|identity_mismatch", S(a).gc())
                if replaced:
                    self.publish(b, "5_2", [("5_2", "9", "informs", [])])
                git(a, "remote", "add", "origin", str(self.env.remote))
                S(a).read()
                S(a).flush()
                files = remote_files(self.env)
                if replaced:
                    self.assertIn("records/t5_2.json", files)
                    self.assertEqual(json.loads(files["records/t5_2.json"])["task_created_at"], C2)
                    self.assertIn("records/t5_2.json", S(a).read().files)
                else:
                    self.assertNotIn("records/t5_2.json", files)

    def test_gc_vs_local_replacement(self):
        for replaced in (True, False):
            with self.subTest(replaced=replaced):
                self.new_env(f"case_{replaced}")
                a = self.env.clone("a")
                self.tasks([a], {"5": C1, "9": C1})
                write_task(a, "5_2", C1)
                self.publish(a, "5_2", [("5_2", "9", "affects")])
                write_task(a, "5_2", C2, body="New child.\n")
                if replaced:
                    git(a, "remote", "remove", "origin")
                    self.publish(a, "5_2", [("5_2", "9", "informs", [])])
                    self.assertEqual(S(a).status(), ["OUTBOX:none"])
                    git(a, "remote", "add", "origin", str(self.env.remote))
                out = S(a).gc()
                if replaced:
                    self.assertIn("GC_KEPT:records/t5_2.json|revalidated", out)
                    S(a).flush()
                    rec = json.loads(remote_files(self.env)["records/t5_2.json"])
                    self.assertEqual(rec["task_created_at"], C2)
                    self.assertEqual(S(a).status(), ["OUTBOX:none"])
                else:
                    self.assertIn("GC_REMOVED:records/t5_2.json|identity_mismatch", out)
                    self.assertNotIn("records/t5_2.json", remote_files(self.env))


# --------------------------------------------------------------------- gc

class GcTests(Base):
    def test_gc_retry_revalidation(self):
        a, b = self.env.clone("a"), self.env.clone("b")
        self.tasks([a, b], {"5": C1, "9": C1, "7": C1})
        for root in (a, b):
            write_task(root, "5_2", C1)
        self.publish(a, "5_2", [("5_2", "9", "affects")])
        self.publish(a, "7", [("7", "9", "informs", [])])
        for root in (a, b):
            write_task(root, "5_2", C2, body="New child.\n")
            (root / task_relpath("7")).unlink()

        def replacement(**_):
            self.publish(b, "5_2", [("5_2", "9", "informs", [])])

        with mock.patch.object(rst, "_test_hook", HookPlan("gc_after_select", replacement, attempt=0)):
            out = S(a).gc()
        self.assertIn("GC_KEPT:records/t5_2.json|revalidated", out)
        self.assertIn("GC_REMOVED:records/t7.json|task_gone", out)
        files = remote_files(self.env)
        self.assertEqual(json.loads(files["records/t5_2.json"])["task_created_at"], C2)
        self.assertNotIn("records/t7.json", files)

    @unittest.skipUnless(HAVE_ZSTD, "zstd not installed")
    def test_gc_existence_across_archives(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"9": C1, "10": C1, "11": C1, "12": C1, "13": C1})
        for tid in ("10", "11", "12", "13"):
            self.publish(a, tid, [(tid, "9", "informs", [])])
        # 10 archived loose; 11 in a numbered bundle; 12 in the legacy bundle; 13 deleted
        (a / task_relpath("10")).rename(write_task(a, "10", C1, archived=True))
        (a / task_relpath("11")).unlink()
        make_bundle(a / "aitasks/archived/_b0/old0.tar.zst", {"t11_name.md": task_text(C1)})
        (a / task_relpath("12")).unlink()
        make_bundle(a / "aitasks/archived/old.tar.zst", {"t12_name.md": task_text(C1)})
        (a / task_relpath("13")).unlink()
        self.assertEqual(S(a).gc(dry_run=True), ["GC_WOULD_REMOVE:records/t13.json|task_gone"])
        self.assertEqual(S(a).gc(), ["GC_REMOVED:records/t13.json|task_gone"])
        self.assertEqual({"records/t10.json", "records/t11.json", "records/t12.json"},
                         set(S(a).read().files))
        make_bundle(a / "aitasks/archived/_b0/old0.tar.zst", {"t11_name.md": task_text(C1)},
                    corrupt=True)
        self.assertTrue(S(a).gc()[0].startswith("GC_REFUSED:scan_incomplete"))


# ------------------------------------------------- archives and freshness

@unittest.skipUnless(HAVE_ZSTD, "zstd not installed")
class ArchiveAndFreshnessTests(Base):
    def test_legacy_bundle_task_is_indexed_and_kept(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "12": C1})
        self.publish(a, "1", [("1", "12", "affects")])
        (a / task_relpath("12")).unlink()
        make_bundle(a / "aitasks/archived/old.tar.zst", {"t12_name.md": task_text(C1)})
        rels = S(a).relations("1")
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0].freshness, "fresh")
        self.assertEqual(S(a).gc(), ["GC_NONE"])

    def test_duplicate_precedence(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1})
        write_task(a, "14", C1, archived=True)
        make_bundle(a / "aitasks/archived/old.tar.zst", {"t14_name.md": task_text(C2)})
        idx = rst.TaskIndex(str(a))
        idx.full_scan()
        self.assertEqual(idx.live_created_at("14"), C1)  # loose beats legacy
        self.assertTrue(any(d.startswith("INDEX_DUPLICATE:t14") for d in idx.duplicates))

    def test_folded_canonicalization(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "20": C1})
        write_task(a, "21", C1, status="Folded", folded_into="20")
        write_task(a, "22", C1)
        self.publish(a, "1", [("1", "21", "affects"), ("1", "22", "informs", [])])
        self.assertEqual({r.to for r in S(a).relations("1")}, {"aitasks#20", "aitasks#22"})
        self.assertEqual(len(S(a).relations("20")), 1)
        # 22 is folded into 30, whose archived file lives in the legacy bundle
        (a / task_relpath("22")).unlink()
        make_bundle(a / "aitasks/archived/old.tar.zst",
                    {"t30_name.md": task_text(C1, status="Done", folded_tasks=[22])})
        self.assertIn("aitasks#30", {r.to for r in S(a).relations("1")})
        self.assertEqual(S(a).gc(dry_run=True), ["GC_NONE"])

    def test_freshness_markers_and_stamp_baseline(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "2": C1})
        write_plan(a, "1", "---\nTask: t1\n---\n\n# Plan\nStep 1.\n")
        self.publish(a, "1", [("1", "2", "affects")])
        self.assertEqual(S(a).relations("2")[0].freshness, "fresh")
        approved = rst.TaskIndex(str(a)).plan_digest("1")
        S(a).write("approvals/t1.json", stamp(a, "1", approved))
        write_plan(a, "1", "---\nTask: t1\n---\n\n# Plan\nStep 1. [done]\n")  # progress mark
        self.assertEqual(S(a).relations("2")[0].freshness, "fresh")
        write_task(a, "2", C1, body="Target rewritten.\n")
        self.assertEqual(S(a).relations("1")[0].freshness, "stale:target_changed")
        write_task(a, "1", C1, body="Source rewritten.\n")
        self.assertEqual(S(a).relations("1")[0].freshness, "stale:source_changed")

    def test_bundled_task_keeps_stale_marker(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "2": C1})
        self.publish(a, "1", [("1", "2", "affects")])
        edited = task_text(C1, body="Target rewritten before archival.\n", status="Done")
        write_task(a, "2", C1, body="Target rewritten before archival.\n", status="Done")
        self.assertEqual(S(a).relations("1")[0].freshness, "stale:target_changed")
        (a / task_relpath("2")).unlink()
        make_bundle(a / "aitasks/archived/_b0/old0.tar.zst", {"t2_name.md": edited})
        self.assertEqual(S(a).relations("1")[0].freshness, "stale:target_changed")
        (a / "aitasks/archived/_b0/old0.tar.zst").unlink()
        make_bundle(a / "aitasks/archived/old.tar.zst", {"t2_name.md": edited})
        self.assertEqual(S(a).relations("1")[0].freshness, "stale:target_changed")
        make_bundle(a / "aitasks/archived/old.tar.zst", {"t2_name.md": edited}, corrupt=True)
        self.assertEqual(S(a).relations("1")[0].freshness, "unverified:target_baseline")


class ReviewFindingTests(Base):
    """Regressions for the Step-8 review findings (each one reproduced first)."""

    def test_unreadable_primary_frontmatter_refuses_gc(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "22": C1})
        self.publish(a, "22", [("22", "1", "informs", [])])
        (a / task_relpath("22")).unlink()
        primary = write_task(a, "30", C1, archived=True, status="Done", folded_tasks=[22])
        self.assertEqual(S(a).gc(dry_run=True), ["GC_NONE"])  # folded: it exists
        primary.write_text("# no frontmatter any more\n\nBody.\n", encoding="utf-8")
        out = S(a).gc()
        self.assertTrue(out[0].startswith("GC_REFUSED:scan_incomplete"), out)
        self.assertIn("records/t22.json", S(a).read().files)
        idx = rst.TaskIndex(str(a))
        idx.full_scan()
        self.assertTrue(any("t30: no frontmatter" in e for e in idx.errors), idx.errors)

    def test_short_writes_are_completed_and_failures_never_publish(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "2": C1})
        real_write = os.write

        def half(fd, data):
            data = bytes(data)
            return real_write(fd, data[: max(1, len(data) // 2)])

        rec = record(a, "1", [("1", "2", "affects")])
        with mock.patch.object(rst.os, "write", half):
            self.assertEqual(S(a).write("records/t1.json", rec, flush=False),
                             ["OUTBOX:records/t1.json"])
        entry = Path(S(a).outbox_dir, "records/t1.json")
        self.assertEqual(json.loads(entry.read_bytes()), rec)
        before = entry.read_bytes()

        def broken(fd, data):
            raise OSError(28, "No space left on device")

        newer = record(a, "1", [("1", "2", "informs", [])], at="2026-12-01T00:00:00Z")
        with mock.patch.object(rst.os, "write", broken), self.assertRaises(OSError):
            S(a).write("records/t1.json", newer, flush=False)
        self.assertEqual(entry.read_bytes(), before)  # the prior durable entry survives
        self.assertEqual([p.name for p in entry.parent.iterdir()], ["t1.json"])  # no temp left

        def zero(fd, data):
            return 0

        with mock.patch.object(rst.os, "write", zero), self.assertRaises(OSError):
            S(a).write("records/t1.json", newer, flush=False)
        self.assertEqual(entry.read_bytes(), before)

    def test_same_store_read_observes_its_own_writes(self):
        a = self.env.clone("a")
        self.tasks([a], {"1": C1, "2": C1})
        store = S(a)
        self.assertEqual(store.read().state, "empty")
        store.write("records/t1.json", record(a, "1", [("1", "2", "affects")]), flush=False)
        with mock.patch.object(rst.ors, "probe_remote_branch",
                               side_effect=AssertionError("a second refresh")):
            snap = store.read()
        self.assertIn("records/t1.json", snap.files)
        self.assertIn("records/t1.json", snap.pending)
        self.assertTrue(snap.state.startswith("fresh@"), snap.state)
        self.assertEqual(len(store.relations("2")), 1)

    def test_invalid_record_shapes_are_reported_not_consumed(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "2": C1, "3": C1})
        self.publish(a, "3", [("3", "2", "informs", [])])
        tip = ors.resolve(a, rst.L_REF)
        bad = ors.build_commit(a, tip, {"records/t1.json": b'{"analysed": true, "relations": []}\n',
                                        "records/t4.json": b"not json\n"}, "damage")
        self.assertEqual(ors.cas_local(a, rst.L_REF, bad, tip), "OK")
        snap = S(a).read()
        self.assertNotIn("records/t1.json", snap.files)
        self.assertIn("records/t3.json", snap.files)
        self.assertTrue(any(c.startswith("records/t1.json|schema:") for c in snap.corrupt), snap.corrupt)
        self.assertIn("records/t4.json|invalid_json", snap.corrupt)
        self.assertEqual(S(a).analysis_line("1"), "disabled")  # no KeyError
        self.assertEqual(len(S(a).relations("2")), 1)
        # a valid write replaces the damaged blob; the damaged one never wins
        out = S(a).write("records/t1.json", record(a, "1", [("1", "2", "affects")]))
        self.assertIn("PUBLISHED:1", out)
        self.assertIn("records/t1.json", S(a).read().files)

    def test_symmetric_reverse_other_is_the_far_end(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "2": C1})
        self.publish(a, "1", [("1", "2", "coordinates_with")])
        (rel,) = S(a).relations("2")
        self.assertEqual(rel.other, "aitasks#1")
        self.assertEqual(rel.direction, "this task coordinates with t1")
        (rel,) = S(a).relations("1")
        self.assertEqual(rel.other, "aitasks#2")

    def test_write_compares_one_blob_under_the_lock(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "2": C1, "3": C1})
        self.publish(a, "3", [("3", "2", "informs", [])])
        with mock.patch.object(rst.ors, "read_files",
                               side_effect=AssertionError("whole-store read under the lock")):
            out = S(a).write("records/t1.json", record(a, "1", [("1", "2", "affects")]), flush=False)
        self.assertEqual(out, ["OUTBOX:records/t1.json"])
        self.assertIsNone(ors.read_file(a, ors.resolve(a, rst.L_REF), "records/t1.json"))
        self.assertIsNotNone(ors.read_file(a, ors.resolve(a, rst.L_REF), "records/t3.json"))


class ReviewRound2Tests(Base):
    """Regressions for the second Step-8 review round."""

    def test_non_list_folded_tasks_refuses_gc(self):
        a = self.env.clone("a", remote=False)
        self.tasks([a], {"1": C1, "22": C1})
        self.publish(a, "22", [("22", "1", "informs", [])])
        (a / task_relpath("22")).unlink()
        primary = write_task(a, "30", C1, archived=True, status="Done", folded_tasks=[22])
        self.assertEqual(S(a).gc(dry_run=True), ["GC_NONE"])
        primary.write_text(primary.read_text().replace("folded_tasks: [22]", 'folded_tasks: "22"'))
        out = S(a).gc()
        self.assertTrue(out[0].startswith("GC_REFUSED:scan_incomplete"), out)
        self.assertIn("records/t22.json", S(a).read().files)
        idx = rst.TaskIndex(str(a))
        idx.full_scan()
        self.assertNotIn("2", idx._fold_of)  # "22" is never read as ["2", "2"]
        self.assertTrue(any("folded_tasks is not a list" in e for e in idx.errors), idx.errors)
        for bad in ("folded_tasks: {22: 1}", "folded_tasks: [[22]]", "folded_tasks: [true]"):
            with self.subTest(bad=bad):
                primary.write_text(task_text(C1, status="Done").replace(
                    "created_at", f"{bad}\ncreated_at", 1), encoding="utf-8")
                self.assertTrue(S(a).gc()[0].startswith("GC_REFUSED:scan_incomplete"))

    def test_local_project_identity_is_resolved_and_preserved(self):
        a = self.env.clone("a", remote=False, project="mobile")
        self.tasks([a], {"1": C1, "2": C1})
        store = S(a)
        self.assertEqual(store.project, "mobile")
        self.publish(a, "1", [("1", "2", "affects"), ("1", "aitasks#5", "informs", [])],
                     project="mobile")
        rels = {r.other: r for r in S(a).relations("1")}
        self.assertEqual(set(rels), {"mobile#2", "aitasks#5"})
        self.assertEqual(rels["aitasks#5"].freshness, "unverified:target_baseline")
        self.assertEqual(rels["aitasks#5"].direction, "this task informs aitasks#5")
        (rev,) = S(a).relations("mobile#2")
        self.assertEqual((rev.from_, rev.to, rev.other), ("mobile#1", "mobile#2", "mobile#1"))
        self.assertEqual(rev.direction, "t1 affects this task")
        self.assertEqual(len(S(a).relations("aitasks#5")), 1)  # reverse of a foreign ref
        self.assertEqual(S(a).analysis_line("aitasks#5"), "unknown(other_project)")
        # a record naming another project's task is refused, not rewritten
        foreign = record(a, "1", [("1", "2", "affects")], project="mobile")
        foreign["task"] = "aitasks#1"
        foreign["relations"][0]["from"] = "aitasks#1"
        self.assertEqual(S(a).write("records/t1.json", foreign),
                         ["PROJECT_MISMATCH:records/t1.json|aitasks#1"])

    def test_missing_project_name_is_an_install_defect(self):
        a = self.env.clone("a", remote=False, project=None)
        with self.assertRaises(rst.ProjectUnresolved):
            S(a)
        (a / "aitasks/metadata/project_config.yaml").write_text("project:\n  name: My.Proj\n")
        with self.assertRaises(rst.ProjectUnresolved):
            S(a)

    def test_ref_grammar_matches_the_shared_parser(self):
        import cross_repo_notation
        for ref in ("aitasks#1", "aitasks#t1_2", "_mobile#1", "-mobile#3", "a_b-c#10_2",
                    "Mobile#1", "mob.ile#1", "#1", "aitasks#", "aitasks#x1", "aitasks#1_",
                    " aitasks#1 ", "aitasks#1#2"):
            with self.subTest(ref=ref):
                shared = cross_repo_notation.parse_ref(ref)
                try:
                    ours = rs.parse_ref(ref)
                except rs.SchemaError:
                    ours = None
                self.assertEqual(ours, shared)


if __name__ == "__main__":
    unittest.main()
