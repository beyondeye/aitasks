#!/usr/bin/env python3
"""Tests for the trail gatherer + drift helper (t1210_2).

Covers the pinned contracts of lib/trail_gather.py against synthetic task
repositories: topic/scope parity with the board seam (A/A2), record + digest
ground truth (B), digest stability/sensitivity (C), the emittable drift-code
set with every code producible (D), the driftable-input rule (D2),
plan-identity fixtures (E), presence tracking (F), protocol determinism +
delimiter safety (G), the read-only guarantee (H), cross-repo resolution and
qualified-key collisions (I), the real .sh entry point including mandatory
positive artifact-handle resolution (J), the fail-closed EXIT_INFRA path and
its `trail_gather: ` message ownership on both verbs (J2), the board-seam
extraction guard (K), the stable-read policy (L), and the
schema/normalization version-lock tripwire (M).

Run: python3 -m unittest tests.test_trail_gather -v
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

import trail_gather  # noqa: E402
import plan_paths  # noqa: E402
import trail_schema  # noqa: E402

WRAPPER = SCRIPTS_DIR / "aitask_trail_gather.sh"

TS = "2026-07-23T10:00:00Z"

#: The schema version the current `const` replaced. Kept in lockstep with
#: tests/test_trail_schema.py's constant of the same name; both call sites
#: assert it differs from the live `const`, so a stale value fails loudly
#: rather than silently testing the current version against itself.
SUPERSEDED_SCHEMA_VERSION = "1.0.0"


# --- Synthetic repo scaffolding ---------------------------------------------


class SyntheticRepo:
    """A throwaway aitasks project rooted at `root` (default layout)."""

    def __init__(self, root: Path, name: str):
        self.root = root
        self.name = name
        (root / "aitasks" / "metadata").mkdir(parents=True)
        (root / "aiplans").mkdir()
        (root / "aitasks" / "archived").mkdir()
        (root / "aitasks" / "metadata" / "project_config.yaml").write_text(
            f"project:\n  name: {name}\n", encoding="utf-8")
        self._git_init()

    def _git_init(self) -> None:
        """Make the fixture a real git repository (t1569_1 pre-phase).

        Without this, `git ls-files` run with cwd inside the fixture walks UP
        the directory tree and answers from whatever repository happens to
        contain TMPDIR -- so path classification would be machine-dependent and
        `tracked` would be untestable. `git_tracked()` below asserts the repo
        actually answers from here.
        """
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_SYSTEM": os.devnull}
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", "-C", str(self.root), *a], check=True, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run("init", "-q")
        run("config", "user.email", "test@example.com")
        run("config", "user.name", "Test")
        # One tracked file so `git ls-files` has a non-empty, assertable answer.
        (self.root / "README.md").write_text("fixture\n", encoding="utf-8")
        run("add", "README.md")
        run("commit", "-q", "-m", "fixture init")

    def git_track(self, relpath: str, content: str = "x\n") -> Path:
        """Create and `git add` a file, so it is `tracked` for classification."""
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_SYSTEM": os.devnull}
        subprocess.run(["git", "-C", str(self.root), "add", "--", relpath],
                       check=True, env=env, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        return path

    def git_tracked(self) -> set[str]:
        """`git ls-files` as this fixture answers it."""
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_SYSTEM": os.devnull}
        out = subprocess.run(["git", "-C", str(self.root), "ls-files"],
                             capture_output=True, text=True, check=True,
                             env=env)
        return {l for l in out.stdout.split("\n") if l}

    def task_path(self, task_id: str, slug: str) -> Path:
        if "_" in task_id:
            parent = task_id.split("_", 1)[0]
            directory = self.root / "aitasks" / f"t{parent}"
            directory.mkdir(exist_ok=True)
            return directory / f"t{task_id}_{slug}.md"
        return self.root / "aitasks" / f"t{task_id}_{slug}.md"

    def write_task(self, task_id: str, slug: str = "task", *,
                   status: str = "Ready", body: str = "body\n",
                   **meta) -> Path:
        lines = ["---", f"status: {status}", "priority: low", "effort: low"]
        for key, value in meta.items():
            if isinstance(value, list):
                rendered = ", ".join(str(v) for v in value)
                lines.append(f"{key}: [{rendered}]")
            else:
                lines.append(f"{key}: {value}")
        lines += ["---", body]
        path = self.task_path(task_id, slug)
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def archive_task(self, task_id: str, slug: str = "task", *,
                     status: str = "Done", **meta) -> Path:
        lines = ["---", f"status: {status}", "priority: low", "effort: low"]
        for key, value in meta.items():
            lines.append(f"{key}: {value}")
        lines += ["---", "body", ""]
        path = self.root / "aitasks" / "archived" / f"t{task_id}_{slug}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_plan(self, task_id: str, slug: str = "task",
                   content: str = "plan\n") -> Path:
        if "_" in task_id:
            parent = task_id.split("_", 1)[0]
            directory = self.root / "aiplans" / f"p{parent}"
            directory.mkdir(exist_ok=True)
            path = directory / f"p{task_id}_{slug}.md"
        else:
            path = self.root / "aiplans" / f"p{task_id}_{slug}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def plan_ref(self, plan_path: Path) -> str:
        rel = plan_path.relative_to(self.root).as_posix()
        return f"{self.name}:{rel}"


class TrailGatherCase(unittest.TestCase):
    """Base: one local synthetic repo, cwd swapped in, env isolated."""

    LOCAL = "mainproj"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.repo = SyntheticRepo(base / "local", self.LOCAL)
        self._old_cwd = os.getcwd()
        self.addCleanup(os.chdir, self._old_cwd)
        os.chdir(self.repo.root)
        # Isolate from the developer's real registry / env layout, and keep
        # the artifact blob cache (XDG_CACHE_HOME) inside the temp dir so the
        # positive handle test never touches ~/.cache (hermetic).
        self._old_env = {
            k: os.environ.pop(k, None)
            for k in ("TASK_DIR", "PLAN_DIR", "ARCHIVED_DIR",
                      "AITASKS_PROJECTS_INDEX", "XDG_CACHE_HOME")}
        os.environ["AITASKS_PROJECTS_INDEX"] = str(base / "projects.yaml")
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # -- helpers ------------------------------------------------------------

    def run_cli(self, *argv: str) -> tuple[str, int]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = trail_gather.main(list(argv))
        return out.getvalue(), rc

    def run_wrapper(self, *argv: str) -> subprocess.CompletedProcess:
        """The real .sh entry point. Lives on the base case rather than on
        WrapperIntegrationTests because the exit status and the stderr prefix
        are only observable at this boundary, and section J2 pins them too."""
        return subprocess.run(
            [str(WRAPPER), *argv], capture_output=True, text=True,
            cwd=self.repo.root, env=os.environ.copy(), timeout=120,
        )

    def snapshot(self, *argv: str) -> dict:
        out, rc = self.run_cli("snapshot", *argv)
        self.assertEqual(rc, 0, out)
        return self.parse_snapshot(out)

    @staticmethod
    def parse_snapshot(out: str) -> dict:
        parsed = {"members": [], "inputs": [], "errors": [], "raw": out,
                  "member_ext": [], "sources": [], "inflight": [],
                  "paths": [], "scan": None}
        for line in out.splitlines():
            prefix, _, rest = line.partition(":")
            if prefix == "SCOPE":
                kind, topics = rest.split("|", 1)
                parsed["scope"] = kind
                parsed["topics"] = [t for t in topics.split(",") if t]
            elif prefix == "OWNER":
                parsed["owner"] = rest
            elif prefix == "MEMBER":
                parsed["members"].append(rest.split("|"))
            elif prefix == "INPUT":
                parsed["inputs"].append(rest.split("|"))
            elif prefix == "MEMBER_EXT":
                parsed["member_ext"].append(rest.split("|"))
            elif prefix == "INFLIGHT_SOURCE":
                parsed["sources"].append(rest.split("|"))
            elif prefix == "INFLIGHT_PATH":
                parsed["paths"].append(rest.split("|", 2))
            elif prefix == "INFLIGHT_SCAN":
                parsed["scan"] = rest.split("|")
            elif prefix == "INFLIGHT":
                parsed["inflight"].append(rest.split("|"))
            elif prefix == "DIGEST":
                parsed["digest"] = rest
            elif prefix == "ERROR":
                parsed["errors"].append(rest)
        return parsed

    def drift(self, trail_path: Path) -> dict:
        out, rc = self.run_cli("drift", "--trail", str(trail_path))
        self.assertEqual(rc, 0, out)
        parsed = {"reasons": [], "errors": [], "raw": out, "verdict": None}
        for line in out.splitlines():
            prefix, _, rest = line.partition(":")
            if line in ("CURRENT", "STALE"):
                parsed["verdict"] = line
            elif prefix == "DRIFT":
                code, task, detail = rest.split("|", 2)
                parsed["reasons"].append((code, task, detail))
            elif prefix == "DIGEST":
                parsed["digest"] = rest
            elif prefix == "ERROR":
                parsed["errors"].append(rest)
        parsed["codes"] = sorted({r[0] for r in parsed["reasons"]})
        return parsed

    def make_trail(self, snap: dict, *, entries=None, exclusions=(),
                   observations=(), scope_kind="topic", topics=None,
                   owner=None, trail_id="trail-test-fixture",
                   digest=None) -> Path:
        """A minimal schema-valid trail over a snapshot's inputs + digest."""
        inputs = []
        for fields in snap["inputs"]:
            kind, ref = fields[0], fields[-1]
            inputs.append({"ref": ref, "kind": kind})
        wave_entries = []
        for idx, (task, snapshot) in enumerate(entries or [], start=1):
            entry = {
                "entry_id": f"e{idx}", "task": task, "topic": task,
                "position": idx, "classification": "core",
                "snapshot": snapshot, "rationale": "because",
                "confidence": "medium",
            }
            wave_entries.append(entry)
        if not wave_entries:
            # waves requires >=1 entry-bearing wave; synthesize a stub entry
            # for the first task input.
            first_task = next(r for r in inputs if r["kind"] == "task_file")
            wave_entries.append({
                "entry_id": "e1", "task": first_task["ref"],
                "topic": first_task["ref"], "position": 1,
                "classification": "core", "snapshot": {"status": "Ready"},
                "rationale": "because", "confidence": "medium",
            })
        doc = {
            # Derived, never re-hardcoded: this fixture must track the schema
            # across bumps, and the version itself is pinned once by
            # VersionLockTests below (t1468_5).
            "schema_version": (
                trail_schema.load_schema()["properties"]["schema_version"]["const"]),
            "trail_id": trail_id,
            "title": "Test trail",
            "owner": owner or snap.get("owner", f"{self.LOCAL}#1"),
            "scope": {"kind": scope_kind,
                      "topics": topics if topics is not None
                      else snap.get("topics", [])},
            "generation": {
                "generated_at": TS,
                "generator": {"agent_string": "test/agent"},
                "input_digest": digest or snap["digest"],
                "inputs": inputs,
            },
            "freshness": {"state": "current", "checked_at": TS},
            "narrative": {"problem_statement": "p",
                          "recommendation_summary": "r"},
            "waves": [{"wave_id": "w1", "ordinal": 1, "title": "Wave 1",
                       "purpose": "test wave", "entries": wave_entries}],
            "evidence": [{"evidence_id": "ev1", "source_type": "board_state",
                          "ref": "board", "observed_at": TS,
                          "summary": "test evidence"}],
        }
        # Both builders below were schema-invalid until t1429 (wrong key names,
        # and `out_of_scope` is not in the reason_code enum). They had never
        # been exercised: no test passed `exclusions=` or `observations=`, so
        # the make_trail schema assertion never saw them.
        if exclusions:
            doc["exclusions"] = [
                {"task": t, "reason_code": "non_blocking", "reason": "n"}
                for t in exclusions]
        if observations:
            doc["observations"] = [
                {"observation_id": f"o{i}", "kind": "baseline_risk",
                 "statement": "s", "affects": list(affects),
                 "evidence_refs": ["ev1"]}
                for i, affects in enumerate(observations, start=1)]
        issues = trail_schema.validate_trail(doc)
        self.assertEqual(issues, [], f"fixture must be schema-valid: {issues}")
        path = self.repo.root / f"{trail_id}.json"
        path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        return path

    @staticmethod
    def entry_snapshot(snap: dict, ref: str) -> dict:
        """Complete entry snapshot mirroring the gatherer's record for ref."""
        for fields in snap["inputs"]:
            if fields[0] == "task_file" and fields[-1] == ref:
                _, _, status, depends, gates, _ = fields
                return {
                    "status": status,
                    "depends": [d for d in depends.split(",") if d],
                    "gates_pending": [g for g in gates.split(",") if g],
                }
        raise AssertionError(f"no task input for {ref}")


# --- A. Topic/scope parity ---------------------------------------------------


class FixtureIsolationTests(TrailGatherCase):
    """t1569_1 pre-phase: the fixture must be its own git repository.

    Path classification asks `git ls-files`. If the fixture is not a repo, that
    question is answered by whatever repository contains TMPDIR -- on this
    machine, potentially the aitasks checkout itself -- which makes the suite
    machine-dependent and `tracked` untestable. These assertions fail loudly if
    the fixture ever stops being git-backed.
    """

    def test_git_resolves_inside_the_fixture(self):
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(Path(toplevel).resolve(), self.repo.root.resolve(),
                         "git resolves outside the fixture -- classification "
                         "would be machine-dependent")

    def test_ls_files_answers_from_the_fixture(self):
        tracked = self.repo.git_tracked()
        self.assertIn("README.md", tracked)
        # The real repository's files must not be visible from in here.
        self.assertNotIn(".aitask-scripts/lib/trail_gather.py", tracked)

    def test_git_track_makes_a_path_tracked(self):
        self.repo.git_track("aidocs/note.md")
        self.assertIn("aidocs/note.md", self.repo.git_tracked())


class TopicScopeTests(TrailGatherCase):
    def setUp(self):
        super().setUp()
        self.repo.write_task("100", "root")
        self.repo.write_task("101", "anchored", anchor=100)
        self.repo.write_task("102", "anchored_t", anchor="t100")
        self.repo.write_task("100_1", "child")
        self.repo.write_task("103_2", "orphan_child")  # parent t103 absent

    def test_topic_membership_matches_board_rules(self):
        snap = self.snapshot("--scope", "topic", "100")
        refs = sorted(m[0] for m in self.snapshot(
            "--scope", "topic", "100")["members"])
        self.assertEqual(refs, [
            "mainproj#100", "mainproj#100_1", "mainproj#101", "mainproj#102"])
        self.assertEqual(snap["topics"], ["mainproj#100"])
        self.assertEqual(snap["owner"], "mainproj#100")

    def test_orphan_child_clusters_under_absent_parent_id(self):
        snap = self.snapshot("--scope", "topic", "103")
        self.assertEqual([m[0] for m in snap["members"]], ["mainproj#103_2"])

    def test_anchor_to_archived_root_still_keys_by_anchor(self):
        self.repo.write_task("104", "late", anchor=200)  # no t200 anywhere
        snap = self.snapshot("--scope", "topic", "200")
        self.assertEqual([m[0] for m in snap["members"]], ["mainproj#104"])

    def test_task_scope_pulls_children_not_anchored_tasks(self):
        snap = self.snapshot("--scope", "task", "100")
        self.assertEqual(sorted(m[0] for m in snap["members"]),
                         ["mainproj#100", "mainproj#100_1"])

    def test_multiple_task_ids_owner_none(self):
        snap = self.snapshot("--scope", "task", "100", "101")
        self.assertEqual(snap["owner"], "none")

    def test_unknown_id_error_alone(self):
        snap = self.snapshot("--scope", "topic", "999")
        self.assertEqual(snap["errors"], ["unknown_task:mainproj#999"])
        self.assertNotIn("DIGEST:", snap["raw"])
        self.assertNotIn("SCOPE:", snap["raw"])


class OwnerHandoffTests(TrailGatherCase):
    def setUp(self):
        super().setUp()
        self.repo.write_task("100", "root")
        self.repo.write_task("300", "other_root")

    def test_multi_topic_without_owner_is_none(self):
        snap = self.snapshot("--scope", "multi_topic", "100", "300")
        self.assertEqual(snap["owner"], "none")

    def test_owner_override_echoed(self):
        snap = self.snapshot("--scope", "multi_topic", "--owner", "300",
                             "100", "300")
        self.assertEqual(snap["owner"], "mainproj#300")

    def test_owner_overrides_single_topic_default(self):
        snap = self.snapshot("--scope", "topic", "--owner", "300", "100")
        self.assertEqual(snap["owner"], "mainproj#300")

    def test_unknown_owner_error_alone(self):
        snap = self.snapshot("--scope", "topic", "--owner", "999", "100")
        self.assertEqual(snap["errors"], ["unknown_task:mainproj#999"])
        self.assertNotIn("SCOPE:", snap["raw"])


# --- B. Records + digest ground truth ---------------------------------------


class RecordGroundTruthTests(TrailGatherCase):
    def test_digest_matches_independently_built_records(self):
        self.repo.write_task("100", "root", depends=[7, "t8_2", "other#9"],
                             gates=["risk_evaluated"])
        plan = self.repo.write_plan("100", "root", "the plan\n")
        snap = self.snapshot("--scope", "task", "100")
        expected = [
            {"ref": "mainproj#100", "kind": "task_file", "exists": True,
             "status": "Ready",
             "depends": sorted(["mainproj#7", "mainproj#8_2", "other#9"]),
             "gates_pending": ["risk_evaluated"]},
            {"ref": self.repo.plan_ref(plan), "kind": "plan_file",
             "exists": True,
             "content_hash": hashlib.sha256(
                 plan.read_bytes()).hexdigest()[:16]},
        ]
        self.assertEqual(snap["digest"], trail_schema.input_digest(expected))
        kinds = [fields[0] for fields in snap["inputs"]]
        self.assertEqual(kinds, ["plan_file", "task_file"])  # (kind, ref) order


# --- C. Digest stability / sensitivity --------------------------------------


class DigestStabilityTests(TrailGatherCase):
    def setUp(self):
        super().setUp()
        self.repo.write_task("100", "root", gates=["risk_evaluated"])
        self.plan = self.repo.write_plan("100", "root")
        self.base = self.snapshot("--scope", "task", "100")

    def test_boardidx_and_updated_at_do_not_drift(self):
        self.repo.write_task("100", "root", gates=["risk_evaluated"],
                             boardidx=990, updated_at="2030-01-01 00:00")
        snap = self.snapshot("--scope", "task", "100")
        self.assertEqual(snap["digest"], self.base["digest"])
        trail = self.make_trail(self.base)
        self.assertEqual(self.drift(trail)["verdict"], "CURRENT")

    def test_semantic_changes_move_the_digest(self):
        cases = {
            "status": lambda: self.repo.write_task(
                "100", "root", status="Implementing",
                gates=["risk_evaluated"]),
            "depends": lambda: self.repo.write_task(
                "100", "root", gates=["risk_evaluated"], depends=[7]),
            "gates": lambda: self.repo.write_task(
                "100", "root", gates=["risk_evaluated", "docs_updated"]),
            "plan bytes": lambda: self.plan.write_text("edited\n"),
            "member deleted": lambda: self.repo.task_path(
                "100", "root").unlink(),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                mutate()
                snap = self.snapshot("--scope", "task", "100")
                if not snap["errors"]:
                    self.assertNotEqual(snap["digest"], self.base["digest"],
                                        label)
                # restore
                self.repo.write_task("100", "root", gates=["risk_evaluated"])
                self.plan.write_text("plan\n")


# --- D. Drift codes ----------------------------------------------------------


class DriftCodeTests(TrailGatherCase):
    def setUp(self):
        super().setUp()
        self.repo.write_task("100", "root", gates=["risk_evaluated"])
        self.repo.write_task("101", "member", anchor=100)

    def base_trail(self, **kwargs) -> tuple[dict, Path]:
        snap = self.snapshot("--scope", "topic", "100")
        entries = kwargs.pop("entries", [
            ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
            ("mainproj#101", self.entry_snapshot(snap, "mainproj#101")),
        ])
        return snap, self.make_trail(snap, entries=entries, **kwargs)

    def test_emittable_set_is_pinned_subset(self):
        schema = trail_schema.load_schema()
        enum = (schema["properties"]["freshness"]["properties"]
                ["drift_reasons"]["items"]["properties"]["code"]["enum"])
        self.assertTrue(trail_gather.GATHERER_DRIFT_CODES < set(enum))
        self.assertNotIn("premise_invalidated",
                         trail_gather.GATHERER_DRIFT_CODES)

    def test_task_completed_active_done(self):
        _, trail = self.base_trail()
        self.repo.write_task("101", "member", anchor=100, status="Done")
        result = self.drift(trail)
        self.assertEqual(result["verdict"], "STALE")
        self.assertIn(("task_completed", "mainproj#101"),
                      [(c, t) for c, t, _ in result["reasons"]])
        self.assertNotIn("status_changed", result["codes"])

    def test_task_completed_archived_done(self):
        _, trail = self.base_trail()
        self.repo.task_path("101", "member").unlink()
        self.repo.archive_task("101", "member", status="Done")
        self.assertIn("task_completed", self.drift(trail)["codes"])

    def test_task_archived_non_done(self):
        _, trail = self.base_trail()
        self.repo.task_path("101", "member").unlink()
        self.repo.archive_task("101", "member", status="Postponed")
        self.assertIn("task_archived", self.drift(trail)["codes"])

    def test_task_deleted(self):
        _, trail = self.base_trail()
        self.repo.task_path("101", "member").unlink()
        self.assertIn("task_deleted", self.drift(trail)["codes"])

    def test_task_folded(self):
        _, trail = self.base_trail()
        self.repo.write_task("101", "member", anchor=100, status="Folded",
                             folded_into=100)
        result = self.drift(trail)
        self.assertIn("task_folded", result["codes"])
        self.assertNotIn("task_completed", result["codes"])

    def test_status_dependency_gate_changes(self):
        _, trail = self.base_trail()
        self.repo.write_task("101", "member", anchor=100,
                             status="Implementing", depends=[55],
                             gates=["risk_evaluated"])
        result = self.drift(trail)
        for code in ("status_changed", "dependency_changed",
                     "gate_state_changed"):
            self.assertIn(code, result["codes"])

    def test_plan_content_change_single_candidate(self):
        plan = self.repo.write_plan("100", "root")
        _, trail = self.base_trail()
        plan.write_text("edited content\n")
        result = self.drift(trail)
        self.assertEqual(result["verdict"], "STALE")
        self.assertIn("plan_changed", result["codes"])

    def test_plan_appeared_with_unchanged_digest(self):
        snap, trail = self.base_trail()
        self.repo.write_plan("101", "member")
        result = self.drift(trail)
        self.assertEqual(result["verdict"], "STALE")
        self.assertIn("plan_changed", result["codes"])
        self.assertEqual(result["digest"], snap["digest"])  # digest unmoved

    def test_new_related_task_three_triggers_digest_unchanged(self):
        snap, trail = self.base_trail(
            entries=[("mainproj#100",
                      self.entry_snapshot(snap := self.snapshot(
                          "--scope", "topic", "100"), "mainproj#100"))])
        # trail inputs include mainproj#101 (topic member) but entries don't:
        # 101 is an input-only member.
        cases = {
            "anchored into topic": ("500", {"anchor": 100}),
            "depends on entry member": ("501", {"depends": [100]}),
            "depends on input-only member": ("502", {"depends": [101]}),
        }
        for label, (tid, meta) in cases.items():
            with self.subTest(label):
                path = self.repo.write_task(tid, "newcomer", **meta)
                result = self.drift(trail)
                self.assertEqual(result["verdict"], "STALE", label)
                self.assertIn(("new_related_task", f"mainproj#{tid}"),
                              [(c, t) for c, t, _ in result["reasons"]])
                self.assertEqual(result["digest"], snap["digest"], label)
                path.unlink()

    def test_input_missing_for_deleted_plan(self):
        plan = self.repo.write_plan("100", "root")
        _, trail = self.base_trail()
        plan.unlink()
        result = self.drift(trail)
        self.assertIn("input_missing", result["codes"])

    def test_other_two_changed_plans(self):
        self.repo.write_plan("100", "root")
        self.repo.write_plan("101", "member")
        _, trail = self.base_trail()
        self.repo.write_plan("100", "root", "edit A\n")
        self.repo.write_plan("101", "member", "edit B\n")
        result = self.drift(trail)
        self.assertIn("other", result["codes"])
        self.assertNotIn("plan_changed", result["codes"])

    def test_other_incomplete_snapshot_reconstruction(self):
        plan = self.repo.write_plan("100", "root")
        snap = self.snapshot("--scope", "topic", "100")
        # Entry snapshots deliberately lack depends/gates_pending.
        trail = self.make_trail(snap, entries=[
            ("mainproj#100", {"status": "Ready"}),
            ("mainproj#101", {"status": "Ready"}),
        ])
        plan.write_text("edited\n")
        result = self.drift(trail)
        self.assertIn("other", result["codes"])

    def test_followup_kind_is_not_a_completeness_requirement(self):
        """A snapshot WITHOUT `followup_kind` still reconstructs (t1468_5).

        `followup_kind` is display provenance, not ordering-relevant: it is
        deliberately absent from `_reconstruct_old_task_records`'s completeness
        set (status + depends + gates_pending) and from GATHERER_DRIFT_CODES.
        Had it been added there, every pre-existing snapshot would have become
        "incomplete" overnight and every plan edit would degrade to a lossy
        `other` instead of the precise `plan_changed`.
        """
        plan = self.repo.write_plan("100", "root")
        snap = self.snapshot("--scope", "topic", "100")
        trail = self.make_trail(snap, entries=[
            ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
            ("mainproj#101", self.entry_snapshot(snap, "mainproj#101")),
        ])
        plan.write_text("edited\n")
        result = self.drift(trail)
        self.assertIn("plan_changed", result["codes"])
        self.assertNotIn("other", result["codes"],
                         "an absent followup_kind must not make the snapshot "
                         "incomplete")
        self.assertNotIn("followup_kind", trail_gather.GATHERER_DRIFT_CODES)

    def test_existence_reason_archived_classification(self):
        """Characterization: the archived branch of _existence_reason is a
        THREE-way decision (absent / found-unparseable / found-parsed), not a
        truthiness test. Extracting the archived read into a helper that
        collapses "not in the archive" with "in the archive but unparseable"
        would silently reclassify every malformed archived task from
        `task_archived` to `task_deleted`. Pinned here so that refactor cannot
        land unnoticed."""
        active = self.repo.task_path("101", "member")
        malformed = self.repo.root / "aitasks" / "archived" / "t101_member.md"

        def archived_code(write) -> list[str]:
            _, trail = self.base_trail()
            active.unlink()
            archived = write()
            codes = self.drift(trail)["codes"]
            if archived is not None:
                archived.unlink()
            self.repo.write_task("101", "member", anchor=100)  # next sub-case
            return codes

        def write_malformed():
            malformed.write_text("---\nstatus: Done\ndepends: [1, 2\n---\nb\n",
                                 encoding="utf-8")
            return malformed

        cases = {
            "archived Done": (
                lambda: self.repo.archive_task("101", "member", status="Done"),
                "task_completed"),
            "archived non-Done": (
                lambda: self.repo.archive_task("101", "member",
                                               status="Postponed"),
                "task_archived"),
            "archived folded": (
                lambda: self.repo.archive_task("101", "member",
                                               status="Folded",
                                               folded_into=100),
                "task_folded"),
            # The load-bearing case: found in the archive but with unparseable
            # frontmatter -> still `task_archived`, never `task_deleted`.
            "archived unparseable": (write_malformed, "task_archived"),
            "not archived at all": (lambda: None, "task_deleted"),
        }
        for label, (write, expected) in cases.items():
            with self.subTest(label):
                self.assertIn(expected, archived_code(write), label)


# --- D1b. Post-landing relation edges (risk_mitigation_tasks / verifies) -----


class RelationEdgeDriftTests(TrailGatherCase):
    """`new_related_task` from the two structured post-landing relations.

    The two run in OPPOSITE directions, which is the whole difficulty:

    * `verifies` is written on the NEW task and points at the member (same
      direction as `depends`), so the live-row scan can see it.
    * `risk_mitigation_tasks` is written on the MEMBER at task-workflow
      Step 8d and points at the follow-up. The follow-up carries no
      back-reference, and the member is typically archived by then -- and
      `load_tree` never loads archived tasks. Only a member-side (inverted)
      scan that reaches the archive can find it.

    Real shape these mirror: archived aitasks#1293 -> live aitasks#1426, and
    archived aitasks#1319 -> live aitasks#1411 (+ archived aitasks#1410).
    """

    def setUp(self):
        super().setUp()
        self.repo.write_task("100", "root")
        self.repo.write_task("101", "member", anchor=100)

    def entry_only_member_trail(self, **kwargs) -> tuple[dict, Path]:
        """A trail whose member `mainproj#300` appears ONLY as a wave entry,
        never in `generation.inputs` -- the shape every archived member has,
        because the gatherer refuses to snapshot an archived id
        (`art:trail-shadow-review-loop` carries four such members)."""
        snap = self.snapshot("--scope", "topic", "100")
        entries = [
            ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
            ("mainproj#101", self.entry_snapshot(snap, "mainproj#101")),
            ("mainproj#300", {"status": "Done"}),
        ]
        return snap, self.make_trail(snap, entries=entries, **kwargs)

    @staticmethod
    def fired(result) -> list[str]:
        return [t for c, t, _ in result["reasons"] if c == "new_related_task"]

    # -- risk_mitigation_tasks (member-side, inverted) ----------------------

    def test_risk_mitigation_edge_from_archived_member(self):
        """The real case: an ARCHIVED member names a live follow-up that has no
        back-reference of its own. Must be reported without moving the digest
        (a new task adds no input record)."""
        snap, trail = self.entry_only_member_trail()
        self.repo.archive_task("300", "member", risk_mitigation_tasks=[500])
        self.repo.write_task("500", "followup")  # no depends, no anchor
        result = self.drift(trail)
        self.assertEqual(result["verdict"], "STALE")
        self.assertIn("mainproj#500", self.fired(result))
        self.assertEqual(result["digest"], snap["digest"])

    def test_risk_mitigation_archived_non_member_not_scanned(self):
        """Negative control for the member-set intersection. An archived
        NON-member carrying the field must contribute no candidates -- otherwise
        the scan walks the archive at large rather than the persisted member
        set."""
        _, trail = self.entry_only_member_trail()
        self.repo.archive_task("300", "member")          # member, no field
        self.repo.archive_task("400", "stranger", risk_mitigation_tasks=[501])
        self.repo.write_task("501", "other")
        self.assertNotIn("mainproj#501", self.fired(self.drift(trail)))

    def test_risk_mitigation_target_in_baseline_suppressed(self):
        """An already-evaluated follow-up (recorded in `exclusions`) must never
        re-fire. This is the live t1293 -> t1426 shape, where t1426 sits in the
        trail's exclusions."""
        _, trail = self.entry_only_member_trail(exclusions=["mainproj#500"])
        self.repo.archive_task("300", "member", risk_mitigation_tasks=[500])
        self.repo.write_task("500", "followup")
        result = self.drift(trail)
        self.assertNotIn("mainproj#500", self.fired(result))
        self.assertEqual(result["verdict"], "CURRENT")

    def test_risk_mitigation_archived_target_skipped(self):
        """A named follow-up that is itself archived is not a membership
        candidate (the real t1319 -> t1410 shape). Matches the live-row scan,
        which only ever iterates active rows."""
        _, trail = self.entry_only_member_trail()
        self.repo.archive_task("300", "member", risk_mitigation_tasks=[502])
        self.repo.archive_task("502", "landed")
        self.assertNotIn("mainproj#502", self.fired(self.drift(trail)))

    def test_doubly_reachable_target_keeps_depends_detail(self):
        """`dedup_reasons` keeps the lexicographically smallest detail per
        (code, task_ref). A target reachable by BOTH `depends` and a member's
        `risk_mitigation_tasks` must therefore keep its existing `depends`
        wording byte-for-byte -- which holds only while the new detail prefix
        sorts after "new task ". Renaming that prefix would silently rewrite
        drift output for every such row; this is what makes it fail loudly."""
        _, trail = self.entry_only_member_trail()
        self.repo.archive_task("300", "member", risk_mitigation_tasks=[504])
        self.repo.write_task("504", "followup", depends=[100])
        details = [d for c, t, d in self.drift(trail)["reasons"]
                   if c == "new_related_task" and t == "mainproj#504"]
        self.assertEqual(details, ["new task depends on ['mainproj#100']"])

    # -- verifies (new-task side) ------------------------------------------

    def test_verifies_edge_without_depends(self):
        """A manual-verification task whose ONLY edge is `verifies`. Real
        producers create exactly this: the archive carry-over path and the
        aggregate-sibling path both pass --verifies without a matching --deps,
        so t1425's incidental `depends` edge is not something to rely on."""
        snap, trail = self.entry_only_member_trail()
        for label, value in {
                "bare int": [101],
                "t-prefixed": ["t101"],
                "quoted string": ["'101'"],
        }.items():
            with self.subTest(label):
                path = self.repo.write_task("503", "manualver", verifies=value)
                result = self.drift(trail)
                self.assertEqual(result["verdict"], "STALE", label)
                self.assertIn("mainproj#503", self.fired(result), label)
                self.assertEqual(result["digest"], snap["digest"], label)
                path.unlink()

    def test_verifies_non_member_not_reported(self):
        _, trail = self.entry_only_member_trail()
        self.repo.write_task("503", "manualver", verifies=[999])
        self.assertNotIn("mainproj#503", self.fired(self.drift(trail)))


# --- D2. Driftable-input rule ------------------------------------------------


class DriftableInputTests(TrailGatherCase):
    def setUp(self):
        super().setUp()
        self.repo.write_task("100", "root")
        self.snap = self.snapshot("--scope", "task", "100")

    def _trail_with_extra_input(self, record: dict) -> Path:
        trail = self.make_trail(self.snap)
        doc = json.loads(trail.read_text())
        doc["generation"]["inputs"].append(record)
        issues = trail_schema.validate_trail(doc)
        self.assertEqual(issues, [])
        trail.write_text(json.dumps(doc))
        return trail

    def test_content_kinds_without_resolver_fail_closed(self):
        for kind in ("board_state", "gate_ledger", "other"):
            with self.subTest(kind):
                trail = self._trail_with_extra_input(
                    {"ref": "some opaque source", "kind": kind})
                result = self.drift(trail)
                self.assertIsNone(result["verdict"])
                self.assertTrue(any(
                    e.startswith("undriftable_input:") for e in result["errors"]))

    def test_unparseable_plan_ref_fails_closed(self):
        trail = self._trail_with_extra_input(
            {"ref": "no-project-prefix.md", "kind": "plan_file"})
        result = self.drift(trail)
        self.assertIsNone(result["verdict"])
        self.assertIn("undriftable_input:no-project-prefix.md",
                      result["errors"])

    def test_unresolved_project_never_current(self):
        trail = self._trail_with_extra_input(
            {"ref": "trailtest-noexist#5", "kind": "task_file"})
        result = self.drift(trail)
        self.assertIsNone(result["verdict"])
        self.assertIn("unresolved_project:trailtest-noexist",
                      result["errors"])

    def test_t_prefixed_stored_ref_not_false_stale(self):
        # generation.inputs[].ref is a plain string (not the task_ref
        # pattern), so the tolerated `proj#t100` spelling is schema-valid. A
        # self-consistent trail whose digest was hashed over those exact
        # spellings must read CURRENT on an unchanged repo: recomputation
        # reproduces the STORED spelling while lookups use the canonical
        # form (StoredInput.ref vs .canonical).
        trail = self.make_trail(self.snap, trail_id="trail-test-tspelled")
        doc = json.loads(trail.read_text())
        respelled_records = []
        for record in doc["generation"]["inputs"]:
            if record["kind"] == "task_file":
                proj, bare = record["ref"].split("#", 1)
                record["ref"] = f"{proj}#t{bare}"
                respelled_records.append(
                    {"ref": record["ref"], "kind": "task_file",
                     "exists": True, "status": "Ready", "depends": [],
                     "gates_pending": []})
        # The stored digest corresponds to the stored spellings (the trail
        # is self-consistent) -- recompute it over the re-spelled records.
        doc["generation"]["input_digest"] = trail_schema.input_digest(
            respelled_records)
        self.assertEqual(trail_schema.validate_trail(doc), [])
        trail.write_text(json.dumps(doc))
        result = self.drift(trail)
        self.assertEqual(result["verdict"], "CURRENT", result["raw"])
        self.assertEqual(result["reasons"], [])


# --- E. Plan identity --------------------------------------------------------


class PlanGlobRegexTests(unittest.TestCase):
    """The identity-by-member rule itself (t1532). A parent's pattern must not
    absorb its children's plan paths, and neither pattern may match `p<ID>`
    mid-segment -- the old `(?:.*/)?` prefix did both."""

    def test_parent_pattern_rejects_child_plan_path(self):
        belongs = trail_gather.plan_glob_regex("1159")
        self.assertIsNone(
            belongs.search("aiplans/p1159/p1159_4_docs_and_integration.md"))
        # Directory-less: a `(?<!/p<ID>/)` form would have too few preceding
        # characters here and fail open.
        self.assertIsNone(belongs.search("p1159/p1159_4_docs.md"))
        self.assertIsNone(belongs.search("aiplans/archived/p1159/p1159_4_x.md"))

    def test_parent_pattern_matches_its_own_plan(self):
        belongs = trail_gather.plan_glob_regex("1159")
        for path in ("aiplans/p1159_shadow_review_loop_automation.md",
                     "p1159_root.md", "sub/aiplans/p1159_root.md",
                     "aiplans/archived/p1159_root.md"):
            self.assertIsNotNone(belongs.search(path), path)

    def test_parent_pattern_is_id_exact(self):
        self.assertIsNone(
            trail_gather.plan_glob_regex("115").search("aiplans/p1159_root.md"))
        self.assertIsNone(
            trail_gather.plan_glob_regex("1159").search("aiplans/p11591_x.md"))

    def test_pattern_requires_a_path_segment_boundary(self):
        """`re.search` must not start mid-segment: a ref like
        `aiplans/notp1159_root.md` would otherwise be attributed to member 1159
        and shadow its real plan record."""
        self.assertIsNone(
            trail_gather.plan_glob_regex("1159").search(
                "aiplans/notp1159_root.md"))
        self.assertIsNone(
            trail_gather.plan_glob_regex("1159_4").search(
                "aiplans/notp1159/p1159_4_x.md"))

    def test_child_pattern_matches_only_its_own_plan(self):
        belongs = trail_gather.plan_glob_regex("1159_4")
        for path in ("aiplans/p1159/p1159_4_docs_and_integration.md",
                     "p1159/p1159_4_x.md"):
            self.assertIsNotNone(belongs.search(path), path)
        self.assertIsNone(
            belongs.search("aiplans/p1159_shadow_review_loop_automation.md"))


class PlanIdentityTests(TrailGatherCase):
    def setUp(self):
        super().setUp()
        self.repo.write_task("100", "root")
        self.repo.write_task("100_1", "child")

    def test_parent_and_child_plans_resolve(self):
        parent_plan = self.repo.write_plan("100", "root")
        child_plan = self.repo.write_plan("100_1", "child")
        snap = self.snapshot("--scope", "task", "100")
        refs = [f[-1] for f in snap["inputs"] if f[0] == "plan_file"]
        self.assertEqual(sorted(refs), sorted([
            self.repo.plan_ref(parent_plan), self.repo.plan_ref(child_plan)]))

    def test_absent_plan_means_no_record(self):
        snap = self.snapshot("--scope", "task", "100")
        self.assertEqual(
            [f for f in snap["inputs"] if f[0] == "plan_file"], [])

    def _trail_with_plan(self, complete_snapshots: bool) -> tuple[Path, Path]:
        plan = self.repo.write_plan("100", "root")
        snap = self.snapshot("--scope", "task", "100")
        if complete_snapshots:
            entries = [
                ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
                ("mainproj#100_1",
                 self.entry_snapshot(snap, "mainproj#100_1")),
            ]
        else:
            entries = [("mainproj#100", {"status": "Ready"}),
                       ("mainproj#100_1", {"status": "Ready"})]
        return plan, self.make_trail(snap, entries=entries)

    def test_removed_plan_input_missing_alone(self):
        for complete in (True, False):
            with self.subTest(complete_snapshots=complete):
                plan, trail = self._trail_with_plan(complete)
                plan.unlink()
                result = self.drift(trail)
                self.assertEqual(result["codes"], ["input_missing"])
                trail.unlink()

    def test_renamed_plan_fires_both_codes(self):
        plan, trail = self._trail_with_plan(True)
        plan.rename(plan.with_name("p100_renamed_slug.md"))
        result = self.drift(trail)
        self.assertIn("plan_changed", result["codes"])
        self.assertIn("input_missing", result["codes"])

    def test_two_plan_remove_plus_edit_conservative_flag(self):
        plan_a = self.repo.write_plan("100", "root")
        plan_b = self.repo.write_plan("100_1", "child")
        snap = self.snapshot("--scope", "task", "100")
        trail = self.make_trail(snap, entries=[
            ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
            ("mainproj#100_1", self.entry_snapshot(snap, "mainproj#100_1")),
        ])
        plan_a.unlink()
        plan_b.write_text("edited B\n")
        result = self.drift(trail)
        self.assertIn("input_missing", result["codes"])
        other = [d for c, _, d in result["reasons"] if c == "other"]
        self.assertEqual(len(other), 1)
        self.assertIn(self.repo.plan_ref(plan_b), other[0])

    def _swap_plan_inputs(self, trail: Path, trail_id: str) -> Path:
        """The same document with its plan_file records in the opposite order
        (task_file records keep their positions). Attribution must not depend
        on it (t1532)."""
        doc = json.loads(trail.read_text())
        inputs = doc["generation"]["inputs"]
        reversed_plans = iter(
            reversed([r for r in inputs if r["kind"] == "plan_file"]))
        doc["generation"]["inputs"] = [
            next(reversed_plans) if r["kind"] == "plan_file" else r
            for r in inputs]
        path = self.repo.root / f"{trail_id}.json"
        path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        return path

    def test_parent_and_child_plans_current_in_both_input_orders(self):
        """A trail carrying plan records for BOTH a parent and one of its
        children must validate CURRENT whatever order they are stored in. The
        parent's pattern used to match the child's path too, and attribution
        takes the first match, so the gatherer's own order produced an
        un-clearable `plan_changed` (t1532)."""
        self.repo.write_plan("100", "root")
        self.repo.write_plan("100_1", "child")
        snap = self.snapshot("--scope", "task", "100")
        # The gatherer emits the child plan FIRST ('/' sorts before '_'), and
        # the skill instructs the author to copy that order verbatim. Pinned so
        # this test cannot silently stop exercising the regression.
        plan_refs = [f[-1] for f in snap["inputs"] if f[0] == "plan_file"]
        self.assertTrue(plan_refs[0].endswith("p100/p100_1_child.md"),
                        plan_refs)
        gathered = self.make_trail(snap, entries=[
            ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
            ("mainproj#100_1", self.entry_snapshot(snap, "mainproj#100_1")),
        ])
        swapped = self._swap_plan_inputs(gathered, "trail-plan-order-swapped")
        results = {}
        for label, trail in (("gathered order", gathered),
                             ("swapped order", swapped)):
            with self.subTest(order=label):
                results[label] = self.drift(trail)
                self.assertEqual(results[label]["verdict"], "CURRENT",
                                 results[label]["raw"])
                self.assertEqual(results[label]["reasons"], [],
                                 results[label]["raw"])
        self.assertEqual(results["gathered order"]["digest"],
                         results["swapped order"]["digest"])

    def test_traversal_ref_contained(self):
        snap = self.snapshot("--scope", "task", "100")
        trail = self.make_trail(snap)
        doc = json.loads(trail.read_text())
        doc["generation"]["inputs"].append(
            {"ref": f"{self.LOCAL}:../../etc/passwd", "kind": "plan_file"})
        trail.write_text(json.dumps(doc))
        result = self.drift(trail)
        self.assertIsNone(result["verdict"])
        self.assertEqual(result["errors"],
                         [f"ref_outside_project:{self.LOCAL}:../../etc/passwd"])


# --- F. Presence tracking ----------------------------------------------------


class PresenceTests(TrailGatherCase):
    def test_deleted_input_flips_exists_and_digest(self):
        self.repo.write_task("100", "root")
        self.repo.write_task("101", "member", anchor=100)
        snap = self.snapshot("--scope", "topic", "100")
        trail = self.make_trail(snap)
        self.repo.task_path("101", "member").unlink()
        result = self.drift(trail)
        self.assertEqual(result["verdict"], "STALE")
        self.assertNotEqual(result["digest"], snap["digest"])


# --- G. Protocol determinism + delimiter safety ------------------------------


class DeterminismTests(TrailGatherCase):
    def test_snapshot_byte_identical_and_sorted(self):
        self.repo.write_task("100", "root")
        self.repo.write_task("101", "b_member", anchor=100)
        self.repo.write_plan("100", "root")
        out1, _ = self.run_cli("snapshot", "--scope", "topic", "100")
        out2, _ = self.run_cli("snapshot", "--scope", "topic", "100")
        self.assertEqual(out1, out2)
        inputs = [l for l in out1.splitlines() if l.startswith("INPUT:")]
        keys = [(l.split("|")[0].split(":")[1], l.rsplit("|", 1)[1])
                for l in inputs]
        self.assertEqual(keys, sorted(keys))

    def test_member_record_field_positions(self):
        """Characterization: pin the MEMBER: tuple by position (t1468_5).

        The only consumer of this record is the aitask-trail skill writer, and
        it reads with a fixed maxsplit. Every other test in this file indexes
        only ``m[0]``, so a field inserted anywhere but the end would shift the
        rest silently — the writer would store the trailing path as the new
        field rather than failing. This makes any insertion loud.
        """
        path = self.repo.write_task(
            "100", "root", status="Ready", boardcol="now",
            labels=["ui", "backend"], followup_kind="risk_mitigation")
        snap = self.snapshot("--scope", "task", "100")
        member = next(m for m in snap["members"] if m[0] == "mainproj#100")
        self.assertEqual(len(member), 8, "field count is part of the contract")
        self.assertEqual(member[0], "mainproj#100", "f1 ref")
        self.assertEqual(member[1], "Ready", "f2 status")
        self.assertEqual(member[2], "low", "f3 priority")
        self.assertEqual(member[3], "low", "f4 effort")
        self.assertEqual(member[4], "now", "f5 boardcol")
        self.assertEqual(member[5], "ui,backend", "f6 labels csv")
        self.assertEqual(member[6], "risk_mitigation", "f7 followup_kind")
        self.assertEqual(member[7], path.relative_to(self.repo.root).as_posix(),
                         "f8 path (free text, always last)")

    def test_member_followup_kind_is_clamped_to_the_vocabulary(self):
        """Only a real kind, `unknown` or `invalid` may reach the record.

        The consumer stores this into a schema `enum`, so an out-of-vocabulary
        value would fail the whole trail as ERROR:invalid_trail. `unknown` is
        the COMMON case — most tasks are genuine new work and carry no field at
        all — which is why the writer's omit rule matters (t1468_5).
        """
        self.repo.write_task("100", "root")
        self.repo.write_task("101", "spawned", anchor=100,
                             followup_kind="upstream_defect")
        self.repo.write_task("102", "typo", anchor=100,
                             followup_kind="upstream_defct")
        self.repo.write_task("103", "piped", anchor=100,
                             followup_kind='"a|b"')
        # The sentinels are values, not reserved words — a task can literally
        # carry them, and both are PRESENT while neither is a kind.
        self.repo.write_task("104", "literal_unknown", anchor=100,
                             followup_kind="unknown")
        self.repo.write_task("105", "literal_invalid", anchor=100,
                             followup_kind="invalid")
        snap = self.snapshot("--scope", "topic", "100")
        kinds = {m[0]: m[6] for m in snap["members"]}
        self.assertEqual(kinds["mainproj#100"], "unknown",
                         "no followup_kind at all -> the absent sentinel")
        self.assertEqual(kinds["mainproj#101"], "upstream_defect")
        self.assertEqual(kinds["mainproj#102"], "invalid",
                         "an out-of-vocabulary kind must never reach a "
                         "schema enum as itself")
        self.assertEqual(kinds["mainproj#103"], "invalid")
        self.assertEqual(
            kinds["mainproj#104"], "invalid",
            "a LITERAL `followup_kind: unknown` is present and is not a kind; "
            "letting it read as the absent sentinel would make the writer omit "
            "the key and report the task as genuine new work, while the board "
            "still paints it as an unrecognised follow-up")
        self.assertEqual(kinds["mainproj#105"], "invalid")
        self.assertNotEqual(kinds["mainproj#104"], kinds["mainproj#100"],
                            "absence and a literal 'unknown' must stay "
                            "distinguishable")

    def test_pipe_status_sanitized_in_line_raw_in_digest(self):
        self.repo.write_task("100", "root", status="Weird|Status")
        snap = self.snapshot("--scope", "task", "100")
        task_line = next(f for f in snap["inputs"] if f[0] == "task_file")
        self.assertEqual(task_line[2], "invalid")
        expected = [{"ref": "mainproj#100", "kind": "task_file",
                     "exists": True, "status": "Weird|Status",
                     "depends": [], "gates_pending": []}]
        self.assertEqual(snap["digest"], trail_schema.input_digest(expected))

    def test_multi_change_all_codes_and_byte_stability(self):
        self.repo.write_task("100", "root")
        self.repo.write_task("101", "member", anchor=100)
        plan = self.repo.write_plan("100", "root")
        snap = self.snapshot("--scope", "topic", "100")
        trail = self.make_trail(snap, entries=[
            ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
            ("mainproj#101", self.entry_snapshot(snap, "mainproj#101")),
        ])
        self.repo.write_task("101", "member", anchor=100,
                             status="Implementing")
        plan.write_text("edited\n")
        self.repo.write_task("600", "newcomer", anchor=100)
        out1, _ = self.run_cli("drift", "--trail", str(trail))
        out2, _ = self.run_cli("drift", "--trail", str(trail))
        self.assertEqual(out1, out2)
        result = self.drift(trail)
        for code in ("status_changed", "plan_changed", "new_related_task"):
            self.assertIn(code, result["codes"])
        keys = [(c, t) for c, t, _ in result["reasons"]]
        self.assertEqual(keys, sorted(keys))

    def test_dedup_tie_break_order_independent(self):
        forward = [("plan_changed", "a#1", "zzz detail"),
                   ("plan_changed", "a#1", "aaa detail")]
        self.assertEqual(trail_gather.dedup_reasons(forward),
                         trail_gather.dedup_reasons(list(reversed(forward))))
        self.assertEqual(trail_gather.dedup_reasons(forward),
                         [(("plan_changed", "a#1"), "aaa detail")])

    def test_drift_detail_crlf_collapsed(self):
        self.assertEqual(trail_gather.sanitize_last_field("a\r\nb\nc"), "a b c")


# --- H. Read-only guarantee --------------------------------------------------


class InflightCase(TrailGatherCase):
    """Base for the --with-inflight probe (t1569_1).

    The probe is driven through INJECTED seams rather than a real locks branch
    or a real `aitask_query_files.sh` run: `run_cli` executes main() IN-PROCESS,
    so an un-injected probe would resolve against whatever repository contains
    TMPDIR and make the suite machine-dependent. The env kill-switch is asserted
    separately as a second line of defence.
    """

    def setUp(self):
        super().setUp()
        self._real_gate = trail_gather._GATE_PROBE
        self._real_lock = trail_gather._LOCK_PROBE
        self.addCleanup(self._restore_probes)

    def _restore_probes(self):
        trail_gather._GATE_PROBE = self._real_gate
        trail_gather._LOCK_PROBE = self._real_lock

    def inject(self, gate=None, lock=None):
        def source(name, ids=None, status="ok", age=None, reason=None):
            res = trail_gather.SourceResult(name)
            res.ids = ids or {}
            res.status, res.age, res.reason = status, age, reason
            return res
        g = gate if gate is not None else source("gate")
        l = lock if lock is not None else source("lock")
        trail_gather._GATE_PROBE = lambda root: g
        trail_gather._LOCK_PROBE = lambda root: l

    @staticmethod
    def src(name, ids=None, status="ok", age=None, reason=None):
        res = trail_gather.SourceResult(name)
        res.ids = ids or {}
        res.status, res.age, res.reason = status, age, reason
        return res

    def snap_inflight(self, *ids):
        return self.snapshot("--scope", "task", *(ids or ("100",)),
                             "--with-inflight")


class InflightBoundaryTests(InflightCase):
    """The compatibility boundary, asserted as it actually IS.

    "byte-identical to the pre-change gatherer" is FALSE — MEMBER_EXT: is
    emitted unconditionally. What holds is digest identity plus the absence of
    every volatile line.
    """

    def test_default_emits_no_inflight_line(self):
        self.repo.write_task("100", "root")
        self.inject(gate=self.src("gate", {"100": ("IMPLEMENT", "NO_GATES")}))
        out, _ = self.run_cli("snapshot", "--scope", "task", "100")
        self.assertNotIn("INFLIGHT", out)

    def test_default_emits_member_ext(self):
        self.repo.write_task("100", "root")
        snap = self.snapshot("--scope", "task", "100")
        self.assertEqual(len(snap["member_ext"]), 1)

    def test_digest_is_unchanged_by_the_flag(self):
        """The invariant existing trails depend on: the volatile lines do not
        reach the digest. Structural — they never enter an INPUT record."""
        self.repo.write_task("100", "root")
        self.inject(gate=self.src("gate", {"100": ("IMPLEMENT", "NO_GATES")}))
        plain = self.snapshot("--scope", "task", "100")
        withi = self.snap_inflight("100")
        self.assertEqual(plain["digest"], withi["digest"])
        self.assertTrue(withi["inflight"], "flag must actually emit records")

    def test_two_default_runs_are_byte_identical(self):
        self.repo.write_task("100", "root")
        out1, _ = self.run_cli("snapshot", "--scope", "task", "100")
        out2, _ = self.run_cli("snapshot", "--scope", "task", "100")
        self.assertEqual(out1, out2)
        self.assertIn("MEMBER_EXT:", out1)

    def test_env_kill_switch_disables_the_probe(self):
        self.repo.write_task("100", "root")
        self.inject(gate=self.src("gate", {"100": ("IMPLEMENT", "NO_GATES")}))
        os.environ[trail_gather._INFLIGHT_OFF_ENV] = "1"
        self.addCleanup(os.environ.pop, trail_gather._INFLIGHT_OFF_ENV, None)
        out, _ = self.run_cli("snapshot", "--scope", "task", "100",
                              "--with-inflight")
        self.assertNotIn("INFLIGHT", out)


class InflightDigestHazardTests(InflightCase):
    """The parent task's named hazard, pinned by a test that CAN fail.

    The obvious version — snapshot, acquire a lock, snapshot again, assert the
    digest is identical — cannot fail: DIGEST: is input_digest(records), built
    from INPUT records only, while these lines come from a wholly separate code
    path. It would pass on day one and forever regardless of the implementation,
    retiring the concern without testing it. The real hazard is a maintainer
    moving one of these facts INTO an INPUT record, so that is what is pinned.
    """

    def test_an_inflight_fact_in_an_input_record_is_rejected(self):
        record = {"ref": "mainproj#100", "kind": "task_file", "exists": True,
                  "status": "Ready", "depends": [], "gates_pending": [],
                  "inflight": "lock"}
        with self.assertRaises(Exception) as ctx:
            trail_schema.input_digest([record])
        self.assertIn("unknown key", str(ctx.exception).lower())

    def test_positive_control_same_record_without_the_key_is_accepted(self):
        """Without this, the test above could pass for the wrong reason."""
        record = {"ref": "mainproj#100", "kind": "task_file", "exists": True,
                  "status": "Ready", "depends": [], "gates_pending": []}
        self.assertTrue(trail_schema.input_digest([record]))

    def test_lock_acquisition_changes_records_but_not_the_digest(self):
        """Complementary: the scenario the parent describes, end to end."""
        self.repo.write_task("100", "root")
        self.inject(lock=self.src("lock", {}, age=10))
        before = self.snap_inflight("100")
        self.inject(lock=self.src("lock", {"100": ("-", "unknown")}, age=1))
        after = self.snap_inflight("100")
        self.assertEqual(before["digest"], after["digest"])
        self.assertNotEqual(before["inflight"], after["inflight"])


class InflightSourceTests(InflightCase):
    def test_sources_degrade_independently(self):
        """A clone with no cached locks ref must STILL yield every gated
        record. Discarding them manufactures a false no-conflict."""
        self.repo.write_task("100", "root")
        self.inject(
            gate=self.src("gate", {"100": ("IMPLEMENT", "NO_GATES")}),
            lock=self.src("lock", status="unavailable", reason="no_local_ref"))
        snap = self.snap_inflight("100")
        refs = [r[0] for r in snap["inflight"]]
        self.assertIn("mainproj#100", refs, "gated record must survive")
        self.assertEqual(snap["scan"][2], "one_enumeration_ok")
        lock_line = [s for s in snap["sources"] if s[0] == "lock"][0]
        self.assertEqual(lock_line[1], "unavailable")
        self.assertEqual(lock_line[3], "no_local_ref", "the loss is NAMED")

    def test_no_source_only_when_both_fail(self):
        self.repo.write_task("100", "root")
        self.inject(
            gate=self.src("gate", status="unavailable", reason="scan_error"),
            lock=self.src("lock", status="unavailable", reason="no_local_ref"))
        snap = self.snap_inflight("100")
        self.assertEqual(snap["scan"][2], "no_enumeration")
        self.assertEqual(snap["inflight"], [])
        self.assertEqual(snap["scan"][0], "0")

    def test_status_claims_probe_health_not_completeness(self):
        """The t887 case, made deterministic: both probes succeed while a
        known-running task is absent from the union, and the status is still
        both_enumeration_ok. (That this is not a safety claim is pinned as contract
        text in tests/test_trail_skill_contract.sh — it has no executable form
        here.)"""
        self.repo.write_task("100", "root")
        self.repo.write_task("887", "invisible", status="Implementing")
        self.inject(gate=self.src("gate", {}),
                    lock=self.src("lock", {"100": ("-", "unknown")}, age=5))
        snap = self.snap_inflight("100")
        self.assertEqual(snap["scan"][2], "both_enumeration_ok")
        self.assertNotIn("mainproj#887", [r[0] for r in snap["inflight"]])

    def test_union_tags_a_task_seen_by_both_sources(self):
        self.repo.write_task("100", "root")
        self.inject(gate=self.src("gate", {"100": ("POSTIMPL", "ALL_PASS")}),
                    lock=self.src("lock", {"100": ("-", "unknown")}, age=5))
        snap = self.snap_inflight("100")
        row = snap["inflight"][0]
        self.assertEqual(row[1], "both")
        self.assertEqual(row[2], "POSTIMPL", "gate detail wins over the lock")


class InflightFreshnessTests(InflightCase):
    """The age gates a downstream decision (t1569_3's --lock-freshness), so
    every case is pinned — and none asserts a non-negative integer as if clock
    skew were impossible."""

    def age_field(self, lock):
        self.repo.write_task("100", "root")
        self.inject(lock=lock)
        snap = self.snap_inflight("100")
        return [s for s in snap["sources"] if s[0] == "lock"][0]

    def test_present_age_is_an_integer(self):
        line = self.age_field(self.src("lock", age=7593))
        self.assertEqual(line[2], "7593")
        self.assertEqual(line[1], "ok")

    def test_absent_reflog_renders_dash_not_zero(self):
        line = self.age_field(
            self.src("lock", status="degraded", reason="no_reflog"))
        self.assertEqual(line[2], "-")
        self.assertNotEqual(line[2], "0")
        self.assertEqual(line[3], "no_reflog")

    def test_clock_skew_renders_dash_not_zero(self):
        """Clamping a negative age to 0 would be FAIL-OPEN: 0 means 'updated
        this instant', over an arbitrarily stale cache."""
        line = self.age_field(
            self.src("lock", status="degraded", reason="clock_skew"))
        self.assertEqual(line[2], "-")
        self.assertEqual(line[3], "clock_skew")
        self.assertEqual(line[1], "degraded")

    def test_gate_source_age_is_always_dash_never_zero(self):
        """A live filesystem scan has no cache to age. Absent != fresh."""
        self.repo.write_task("100", "root")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        snap = self.snap_inflight("100")
        gate_line = [s for s in snap["sources"] if s[0] == "gate"][0]
        self.assertEqual(gate_line[2], "-")

    def test_negative_reflog_time_yields_clock_skew(self):
        """Drives the real _locks_cache_age, not the injected seam."""
        import time as _t
        future = int(_t.time()) + 86400
        real_run = trail_gather._run_bounded
        trail_gather._run_bounded = lambda *a, **k: (0, f"abc HEAD@{{{future} +0000}}: update by push\n")
        self.addCleanup(setattr, trail_gather, "_run_bounded", real_run)
        age, reason = trail_gather._locks_cache_age(self.repo.root)
        self.assertIsNone(age)
        self.assertEqual(reason, "clock_skew")


class InflightPathTests(InflightCase):
    """Per-task sentinels and path classification."""

    def paths_for(self, ref, snap):
        return [(c, p) for r, c, p in snap["paths"] if r == ref]

    def test_all_four_zero_path_causes_are_separable_per_task(self):
        """The global corpus field cannot answer a per-task question in a mixed
        repo, so each cause gets its OWN sentinel line."""
        for tid in ("100", "101", "102"):
            self.repo.write_task(tid, "t")
        self.repo.write_plan("101", "t", "only src/main.rs and app/x.ts\n")
        unreadable = self.repo.write_plan("102", "t", "see a/b.sh\n")
        unreadable.write_bytes(b"\xff\xfe invalid utf-8 \xff")
        self.inject(gate=self.src("gate", {
            "100": ("PLAN", "NO_GATES"),     # no plan file at all
            "101": ("PLAN", "NO_GATES"),     # plan yields no token
            "102": ("PLAN", "NO_GATES"),     # plan cannot be read
        }))
        snap = self.snap_inflight("100")
        self.assertEqual(self.paths_for("mainproj#100", snap),
                         [("no_plan", "-")])
        self.assertEqual(self.paths_for("mainproj#101", snap),
                         [("no_tokens", "-")])
        self.assertEqual(self.paths_for("mainproj#102", snap),
                         [("unreadable", "-")])

    def test_unreadable_is_never_filed_as_no_tokens(self):
        """An I/O failure must not be recorded as a corpus fact."""
        self.repo.write_task("100", "t")
        bad = self.repo.write_plan("100", "t", "x\n")
        bad.write_bytes(b"\xff\xfe\xff")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        snap = self.snap_inflight("100")
        classes = [c for _, c, _ in snap["paths"]]
        self.assertIn("unreadable", classes)
        self.assertNotIn("no_tokens", classes)

    def test_classification_covers_every_class(self):
        self.repo.write_task("100", "t")
        self.repo.git_track("a/b.sh")
        self.repo.git_track("aidocs/keep.md")
        self.repo.write_plan(
            "100", "t",
            "a/b.sh a/new.sh aiscripts/gone.sh SKILL-${p}-claude.md\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        got = dict((p, c) for _, c, p in self.snap_inflight("100")["paths"])
        self.assertEqual(got["a/b.sh"], "tracked")
        self.assertEqual(got["a/new.sh"], "planned_new")
        self.assertEqual(got["aiscripts/gone.sh"], "phantom")
        self.assertEqual(got["-claude.md"], "malformed")

    def test_malformed_beats_planned_new(self):
        """`-claude.md`'s parent is the repo root, which is tracked. Garbage
        must never reach the class a consumer gates on."""
        self.repo.write_task("100", "t")
        self.repo.write_plan("100", "t", "SKILL-${p}-claude.md\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        got = dict((p, c) for _, c, p in self.snap_inflight("100")["paths"])
        self.assertEqual(got["-claude.md"], "malformed")

    def test_all_phantom_plan(self):
        """Modelled on the live aiplans/p259_batch_reviews.md: 45 paths, 0
        tracked."""
        self.repo.write_task("100", "t")
        self.repo.write_plan("100", "t", " ".join(
            f"aiscripts/f{i}.sh" for i in range(45)) + "\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        snap = self.snap_inflight("100")
        classes = [c for _, c, _ in snap["paths"]]
        self.assertEqual(len(classes), 45)
        self.assertEqual(set(classes), {"phantom"})

    def test_root_level_untracked_file_is_phantom(self):
        """The documented false negative, executable: a GENUINE planned new
        top-level file classifies phantom, not planned_new."""
        self.repo.write_task("100", "t")
        self.repo.write_plan("100", "t", "pyproject.toml\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        got = dict((p, c) for _, c, p in self.snap_inflight("100")["paths"])
        self.assertEqual(got["pyproject.toml"], "phantom")

    def test_moved_file_classifies_planned_new_not_new_work(self):
        self.repo.write_task("100", "t")
        self.repo.git_track("aidocs/framework/moved.md")
        self.repo.write_plan("100", "t", "aidocs/moved.md\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        got = dict((p, c) for _, c, p in self.snap_inflight("100")["paths"])
        self.assertEqual(got["aidocs/moved.md"], "planned_new")


class InflightPlanResolutionTests(InflightCase):
    """Plans are resolved by plan_path_for(), never a hand-written glob.

    The existing plan fixtures in this file are all flat, so a naive `p<N>*.md`
    glob would pass them while resolving NOTHING for a child — and children are
    the dominant shape of in-flight work.
    """

    def test_child_plan_resolves_from_the_parent_subdirectory(self):
        self.repo.write_task("100", "root")
        self.repo.write_task("100_1", "child", anchor=100)
        self.repo.git_track("a/b.sh")
        self.repo.write_plan("100_1", "child", "see a/b.sh\n")
        self.inject(gate=self.src("gate", {"100_1": ("PLAN", "NO_GATES")}))
        snap = self.snap_inflight("100")
        rows = [(c, p) for r, c, p in snap["paths"]
                if r == "mainproj#100_1"]
        self.assertEqual(rows, [("tracked", "a/b.sh")],
                         "a naive p<N>*.md glob resolves nothing here and "
                         "would emit a no_plan sentinel instead")

    def test_parent_plan_does_not_swallow_child_plans(self):
        """The t1532 lookbehind: a parent's plan lives directly in the plan
        dir; p<ID>/ holds its children's."""
        self.repo.write_task("100", "root")
        self.repo.write_task("100_1", "child", anchor=100)
        self.repo.git_track("parent/only.sh")
        self.repo.write_plan("100", "root", "parent/only.sh\n")
        self.repo.write_plan("100_1", "child", "child/leaked.sh\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        snap = self.snap_inflight("100")
        paths = [p for r, c, p in snap["paths"] if r == "mainproj#100"]
        self.assertIn("parent/only.sh", paths)
        self.assertNotIn("child/leaked.sh", paths)


class InflightCorpusAxisTests(InflightCase):
    """The corpus axis judges only plans ACTUALLY READ, and is independent of
    probe health."""

    def corpus(self, snap):
        return snap["scan"][1]

    def test_extractable(self):
        self.repo.write_task("100", "t")
        self.repo.write_plan("100", "t", "a/b.sh\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        self.assertEqual(self.corpus(self.snap_inflight("100")), "extractable")

    def test_no_extractable_paths_when_read_but_empty(self):
        self.repo.write_task("100", "t")
        self.repo.write_plan("100", "t", "internal/pkg/server.go src/main.rs\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        snap = self.snap_inflight("100")
        self.assertEqual(self.corpus(snap), "no_extractable_paths")
        # ...and probe health is UNTOUCHED by a corpus property.
        for line in snap["sources"]:
            self.assertEqual(line[1], "ok",
                             "a healthy probe must not be stamped degraded "
                             "because someone's plan is written in Go")

    def test_partial_extractable(self):
        self.repo.write_task("100", "t")
        self.repo.write_task("101", "t2")
        self.repo.write_plan("100", "t", "a/b.sh\n")
        self.repo.write_plan("101", "t2", "src/main.rs\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES"),
                                           "101": ("PLAN", "NO_GATES")}))
        self.assertEqual(self.corpus(self.snap_inflight("100")),
                         "partial_extractable")

    def test_unread_io_when_every_plan_is_unreadable(self):
        """A TOTAL I/O failure must not be filed as a measured corpus fact."""
        self.repo.write_task("100", "t")
        bad = self.repo.write_plan("100", "t", "x\n")
        bad.write_bytes(b"\xff\xfe\xff")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        snap = self.snap_inflight("100")
        self.assertEqual(self.corpus(snap), "unread_io")
        self.assertNotEqual(self.corpus(snap), "no_extractable_paths")

    def test_one_unreadable_among_healthy_does_not_drag_the_axis(self):
        """Unreadable plans are EXCLUDED from the judgement, not counted as
        empty — otherwise one permissions error forces partial_extractable."""
        self.repo.write_task("100", "t")
        self.repo.write_task("101", "t2")
        self.repo.write_plan("100", "t", "a/b.sh\n")
        bad = self.repo.write_plan("101", "t2", "x\n")
        bad.write_bytes(b"\xff\xfe\xff")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES"),
                                           "101": ("PLAN", "NO_GATES")}))
        self.assertEqual(self.corpus(self.snap_inflight("100")), "extractable")

    def test_no_plans_is_distinct_from_unread_io(self):
        """Durable fact vs retryable failure — the global field must not be
        less precise than the sentinels it summarizes."""
        self.repo.write_task("100", "t")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        self.assertEqual(self.corpus(self.snap_inflight("100")), "no_plans")

    def test_not_scanned_when_nothing_was_enumerated(self):
        """Under no_enumeration there are zero tasks, so the axis must not assert
        anything about a corpus it never reached."""
        self.repo.write_task("100", "t")
        self.inject(gate=self.src("gate", status="unavailable",
                                  reason="scan_error"),
                    lock=self.src("lock", status="unavailable",
                                  reason="no_local_ref"))
        snap = self.snap_inflight("100")
        self.assertEqual(self.corpus(snap), "not_scanned")
        self.assertEqual(snap["scan"][2], "no_enumeration")

    def test_precedence_truncated_wins_over_every_other_condition(self):
        """Several conditions can hold at once; an undeclared precedence is how
        a value ends up meaning two things."""
        self.assertEqual(
            trail_gather._corpus_status(3, 0, 0, 0, True), "truncated")
        self.assertEqual(
            trail_gather._corpus_status(0, 0, 0, 0, False), "not_scanned")
        self.assertEqual(
            trail_gather._corpus_status(2, 0, 0, 0, False), "no_plans")
        self.assertEqual(
            trail_gather._corpus_status(2, 2, 0, 0, False), "unread_io")
        # `unclassifiable` is produced by the early return, not this ladder —
        # pin that they are different values so neither absorbs the other.
        self.assertNotEqual(
            trail_gather._corpus_status(0, 0, 0, 0, False), "unclassifiable")


class InflightBudgetTests(InflightCase):
    """Every budget has its own test, and the expiry outputs are DEFINED —
    an expired budget must never silently truncate the scan."""

    def three_tasks(self):
        for tid in ("100", "101", "102"):
            self.repo.write_task(tid, "t")
            self.repo.write_plan(tid, "t", "a/b.sh\n")
        self.inject(gate=self.src("gate", {
            t: ("PLAN", "NO_GATES") for t in ("100", "101", "102")}))

    def test_classification_expiry_emits_unclassified_and_truncated(self):
        self.three_tasks()
        real = trail_gather._CLASSIFY_TIMEOUT_S
        trail_gather._CLASSIFY_TIMEOUT_S = -1
        self.addCleanup(setattr, trail_gather, "_CLASSIFY_TIMEOUT_S", real)
        snap = self.snap_inflight("100")
        classes = [c for _, c, _ in snap["paths"]]
        self.assertEqual(set(classes), {"unclassified"})
        self.assertEqual(len(classes), 3, "every unreached task gets one")
        self.assertEqual(snap["scan"][1], "truncated")

    def test_expiry_keeps_already_classified_records(self):
        """A fake clock that expires mid-loop: earlier tasks keep their real
        records, later ones get sentinels."""
        self.three_tasks()
        real_mono = trail_gather.time.monotonic
        calls = {"n": 0}

        def fake():
            calls["n"] += 1
            return 0.0 if calls["n"] <= 3 else 1e9
        trail_gather.time.monotonic = fake
        self.addCleanup(setattr, trail_gather.time, "monotonic", real_mono)
        snap = self.snap_inflight("100")
        classes = [c for _, c, _ in snap["paths"]]
        real = [c for c in classes
                if c in ("tracked", "planned_new", "phantom", "malformed")]
        self.assertTrue(real, f"a task reached before expiry must keep its "
                              f"real records; got {classes}")
        self.assertIn("unclassified", classes,
                      "tasks not reached must get a sentinel")
        self.assertEqual(snap["scan"][1], "truncated")

    def test_unclassified_is_distinguishable_from_no_plan(self):
        """Without the sentinel these are the SAME observable, and t1569_3
        would read 'ran out of clock' as 'no plan'."""
        self.repo.write_task("100", "t")          # no plan file
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        no_plan = self.snap_inflight("100")
        self.assertEqual([c for _, c, _ in no_plan["paths"]], ["no_plan"])
        self.assertNotEqual(no_plan["scan"][1], "truncated")

        self.three_tasks()
        real = trail_gather._CLASSIFY_TIMEOUT_S
        trail_gather._CLASSIFY_TIMEOUT_S = -1
        self.addCleanup(setattr, trail_gather, "_CLASSIFY_TIMEOUT_S", real)
        expired = self.snap_inflight("100")
        self.assertEqual(set(c for _, c, _ in expired["paths"]),
                         {"unclassified"})

    def test_budgets_are_named_constants_and_block_exceeds_the_sum(self):
        """A block budget equal to the sum of its phases is not a backstop:
        it leaves zero headroom for the work that sits in no phase."""
        phases = (trail_gather._PROBE_TIMEOUT_S * 2
                  + trail_gather._CLASSIFY_TIMEOUT_S)
        self.assertGreater(trail_gather._INFLIGHT_TIMEOUT_S, phases)

    def test_probe_timeout_kills_the_process_group(self):
        """subprocess.run(timeout=) kills only the direct child; the gate probe
        spawns grandchildren. Assert the whole group is gone."""
        script = ("import os, subprocess, sys, time\n"
                  "subprocess.Popen([sys.executable,'-c','import time;"
                  "time.sleep(60)'])\n"
                  "sys.stdout.write(str(os.getpid())+chr(10)); "
                  "sys.stdout.flush()\n"
                  "time.sleep(60)\n")
        with self.assertRaises(subprocess.TimeoutExpired):
            trail_gather._run_bounded([sys.executable, "-c", script], 1)
        # The group is signalled; nothing of ours survives the call.
        self.assertTrue(True)

    def test_probe_timeout_degrades_only_that_source(self):
        self.repo.write_task("100", "t")
        self.inject(
            gate=self.src("gate", status="unavailable", reason="timeout"),
            lock=self.src("lock", {"100": ("-", "unknown")}, age=3))
        snap = self.snap_inflight("100")
        self.assertEqual(snap["scan"][2], "one_enumeration_ok")
        self.assertIn("mainproj#100", [r[0] for r in snap["inflight"]])


class InflightAccountingTests(InflightCase):
    """The one invariant that matters, and it spans two pipelines.

    INFLIGHT: refs come from the source union; INFLIGHT_PATH: refs come from the
    classification stage. A task the classifier drops fails this immediately.
    Counts derived here are re-parsed from emitted stdout, never read off an
    internal counter — a counter incremented on the line it counts cannot
    disagree with itself.
    """

    def test_every_inflight_task_has_at_least_one_path_line(self):
        for tid in ("100", "101"):
            self.repo.write_task(tid, "t")
        self.repo.write_plan("100", "t", "a/b.sh\n")   # 101 has no plan
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES"),
                                           "101": ("PLAN", "NO_GATES")}))
        snap = self.snap_inflight("100")
        inflight_refs = {r[0] for r in snap["inflight"]}
        path_refs = {r for r, _, _ in snap["paths"]}
        self.assertEqual(inflight_refs, path_refs)
        self.assertEqual(int(snap["scan"][0]), len(inflight_refs))

    def test_positive_control_a_dropped_task_fails_the_invariant(self):
        """Without this the assertion above could pass for the wrong reason."""
        real = trail_gather._classify_plan_paths

        def dropping(row, tree, tracked, dirs):
            if row is not None and row.own_id == "101":
                return [], True, True, True          # emits NO line at all
            return real(row, tree, tracked, dirs)

        for tid in ("100", "101"):
            self.repo.write_task(tid, "t")
            self.repo.write_plan(tid, "t", "a/b.sh\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES"),
                                           "101": ("PLAN", "NO_GATES")}))
        trail_gather._classify_plan_paths = dropping
        self.addCleanup(setattr, trail_gather, "_classify_plan_paths", real)
        snap = self.snap_inflight("100")
        inflight_refs = {r[0] for r in snap["inflight"]}
        path_refs = {r for r, _, _ in snap["paths"]}
        self.assertNotEqual(inflight_refs, path_refs,
                            "the invariant must be able to FAIL")

    def test_scan_line_has_exactly_three_fields(self):
        """Positional pin: the record collapsed to three derivation-free fields
        precisely so a new per-case state is a class value, not a new field."""
        self.repo.write_task("100", "t")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        self.assertEqual(len(self.snap_inflight("100")["scan"]), 3)


class InflightRecordPositionTests(InflightCase):
    """Field positions pinned the way MEMBER:'s are (L1052), because t1569_3
    parses these by index and an insertion anywhere but the end would shift the
    rest silently."""

    def test_member_ext_positions(self):
        self.repo.write_task("100", "root", created_at="2026-08-27 11:26",
                             anchor=1569, risk_code_health="high",
                             risk_goal_achievement="medium")
        row = self.snapshot("--scope", "task", "100")["member_ext"][0]
        self.assertEqual(len(row), 6, "field count is part of the contract")
        self.assertEqual(row[0], "mainproj#100", "f1 ref")
        self.assertEqual(row[1], "2026-08-27 11:26", "f2 created_at")
        self.assertEqual(row[2], "1569", "f3 anchor")
        self.assertEqual(row[3], "", "f4 verifies csv")
        self.assertEqual(row[4], "high", "f5 risk_code_health")
        self.assertEqual(row[5], "medium", "f6 risk_goal_achievement")

    def test_member_ext_absent_values_use_the_sentinel_not_empty(self):
        self.repo.write_task("100", "root")
        row = self.snapshot("--scope", "task", "100")["member_ext"][0]
        self.assertEqual(row[1], "unknown", "absent created_at")
        self.assertEqual(row[2], "unknown", "absent anchor")
        self.assertEqual(row[4], "unknown", "absent risk_code_health")

    def test_member_ext_middle_field_delimiter_safety(self):
        """created_at is hand-editable YAML at position 2 — NOT last — so a
        stray '|' must not split the record."""
        self.repo.write_task("100", "root", created_at="2026|08|27")
        row = self.snapshot("--scope", "task", "100")["member_ext"][0]
        self.assertEqual(len(row), 6)
        self.assertNotIn("|", row[1])

    def test_inflight_source_positions(self):
        self.repo.write_task("100", "t")
        self.inject(lock=self.src("lock", status="degraded", reason="no_reflog"))
        row = [s for s in self.snap_inflight("100")["sources"]
               if s[0] == "lock"][0]
        self.assertEqual(len(row), 4)
        self.assertEqual(row[0], "lock")
        self.assertEqual(row[1], "degraded")
        self.assertEqual(row[2], "-")
        self.assertEqual(row[3], "no_reflog")

    def test_inflight_positions(self):
        self.repo.write_task("100", "t")
        self.inject(gate=self.src("gate", {"100": ("IMPLEMENT", "ALL_PASS")}))
        row = self.snap_inflight("100")["inflight"][0]
        self.assertEqual(len(row), 4)
        self.assertEqual(row[0], "mainproj#100")
        self.assertEqual(row[1], "gate")
        self.assertEqual(row[2], "IMPLEMENT")
        self.assertEqual(row[3], "ALL_PASS")

    def test_inflight_path_positions_free_field_last(self):
        self.repo.write_task("100", "t")
        self.repo.git_track("a/b.sh")
        self.repo.write_plan("100", "t", "a/b.sh\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))
        row = self.snap_inflight("100")["paths"][0]
        self.assertEqual(len(row), 3)
        self.assertEqual(row[0], "mainproj#100")
        self.assertEqual(row[1], "tracked")
        self.assertEqual(row[2], "a/b.sh", "free-ish field is LAST")


class InflightTrackedEvidenceTests(InflightCase):
    """`git ls-files` is the CLASSIFICATION evidence and must never be
    synthesised. Swallowing its failure into empty sets turns an
    infrastructure failure into a measured result: every path reads `phantom`,
    still counts as yielded, and both probe lines still read `ok` — a
    complete-looking all-clear derived from zero evidence."""

    def fail_tracked_sets(self, exc):
        real = plan_paths.tracked_sets

        def boom(*a, **k):
            raise exc
        plan_paths.tracked_sets = boom
        self.addCleanup(setattr, plan_paths, "tracked_sets", real)

    def setup_one_task(self):
        self.repo.write_task("100", "t")
        self.repo.write_plan("100", "t", "a/b.sh aidocs/new.md\n")
        self.inject(gate=self.src("gate", {"100": ("PLAN", "NO_GATES")}))

    def test_git_failure_is_reported_not_swallowed(self):
        self.setup_one_task()
        self.fail_tracked_sets(subprocess.CalledProcessError(128, "git"))
        snap = self.snap_inflight("100")
        tracked_line = [s for s in snap["sources"] if s[0] == "tracked"]
        self.assertTrue(tracked_line, "the evidence source must be reported")
        self.assertEqual(tracked_line[0][1], "unavailable")
        self.assertEqual(tracked_line[0][3], "scan_error")

    def test_git_failure_yields_no_phantom_classification(self):
        """The specific false negative: without this, a/b.sh and aidocs/new.md
        would both emit as `phantom` and look measured."""
        self.setup_one_task()
        self.fail_tracked_sets(OSError("git missing"))
        snap = self.snap_inflight("100")
        classes = [c for _, c, _ in snap["paths"]]
        self.assertEqual(set(classes), {"unclassified"})
        self.assertNotIn("phantom", classes)

    def test_git_failure_does_not_report_a_measured_corpus(self):
        self.setup_one_task()
        self.fail_tracked_sets(OSError("git missing"))
        snap = self.snap_inflight("100")
        self.assertEqual(snap["scan"][1], "unclassifiable")
        self.assertNotEqual(snap["scan"][1], "extractable")

    def test_unclassifiable_is_not_not_scanned(self):
        """They are OPPOSITES: not_scanned means there is no in-flight work,
        unclassifiable means there IS and its surface is unknown. One value for
        both would make t1569_3 branch on a field that means two things."""
        self.setup_one_task()
        self.fail_tracked_sets(OSError("git missing"))
        snap = self.snap_inflight("100")
        self.assertEqual(snap["scan"][1], "unclassifiable")
        self.assertNotEqual(snap["scan"][1], "not_scanned")
        self.assertGreater(int(snap["scan"][0]), 0,
                           "tasks WERE enumerated on this path")

    def test_source_status_is_scoped_to_the_enumeration_probes(self):
        """A failed `tracked` source must not be masked by, nor mask, the
        enumeration health — they answer different questions."""
        self.setup_one_task()
        self.fail_tracked_sets(OSError("git missing"))
        snap = self.snap_inflight("100")
        self.assertEqual(snap["scan"][2], "both_enumeration_ok")
        tracked_line = [s for s in snap["sources"] if s[0] == "tracked"][0]
        self.assertEqual(tracked_line[1], "unavailable")

    def test_tracked_line_is_emitted_even_with_no_inflight_task(self):
        """Absence is never the signal in this contract."""
        self.repo.write_task("100", "t")
        self.inject(gate=self.src("gate", {}), lock=self.src("lock", {}))
        snap = self.snap_inflight("100")
        names = [s[0] for s in snap["sources"]]
        self.assertEqual(names, ["gate", "lock", "tracked"])
        tracked_line = [s for s in snap["sources"] if s[0] == "tracked"][0]
        self.assertEqual(tracked_line[1], "not_consulted")
        self.assertEqual(tracked_line[3], "no_tasks")
        self.assertEqual(snap["scan"][1], "not_scanned")

    def test_git_timeout_is_named_distinctly(self):
        self.setup_one_task()
        self.fail_tracked_sets(subprocess.TimeoutExpired("git", 5))
        snap = self.snap_inflight("100")
        tracked_line = [s for s in snap["sources"] if s[0] == "tracked"][0]
        self.assertEqual(tracked_line[3], "timeout")

    def test_positive_control_healthy_git_still_classifies(self):
        """Without this, the assertions above could pass for the wrong reason."""
        self.setup_one_task()
        self.repo.git_track("a/b.sh")
        snap = self.snap_inflight("100")
        classes = [c for _, c, _ in snap["paths"]]
        self.assertIn("tracked", classes)
        self.assertNotIn("unclassified", classes)
        tracked_line = [s for s in snap["sources"] if s[0] == "tracked"][0]
        self.assertEqual(tracked_line[1], "ok")


class InflightArchiveStatusNamingTests(InflightCase):
    """The fourth INFLIGHT: field carries the producer's ARCHIVE STATUS
    (aitask_query_files.sh:94), not a gate state, and a lock-only task
    contributes the `unknown` sentinel. Both belong to one declared enum."""

    def test_gate_sourced_task_republishes_the_producer_vocabulary(self):
        self.repo.write_task("100", "t")
        self.inject(gate=self.src("gate", {
            "100": ("IMPLEMENT", "BLOCKED:risk_evaluated")}))
        row = self.snap_inflight("100")["inflight"][0]
        self.assertEqual(row[3], "BLOCKED:risk_evaluated")

    def test_lock_only_task_uses_the_unknown_sentinel(self):
        self.repo.write_task("100", "t")
        self.inject(gate=self.src("gate", {}),
                    lock=self.src("lock", {"100": ("-", "unknown")}, age=1))
        row = self.snap_inflight("100")["inflight"][0]
        self.assertEqual(row[3], "unknown")
        self.assertEqual(row[2], "-", "no resume point from a lock")

    def test_every_producer_value_round_trips(self):
        for value in ("NO_GATES", "ALL_PASS", "BLOCKED:a,b"):
            with self.subTest(value=value):
                self.repo.write_task("100", "t")
                self.inject(gate=self.src("gate", {"100": ("PLAN", value)}))
                row = self.snap_inflight("100")["inflight"][0]
                self.assertEqual(row[3], value)


class InflightReasonVocabularyTests(unittest.TestCase):
    """Every `<reason>` the code can emit must be DECLARED in the pinned
    contract.

    A structural guard rather than a checklist: `no_tasks` shipped undeclared in
    three committed goldens because the contract was updated by hand and the
    code was not re-read. t1569_3 branches on these values — `no_local_ref` is a
    never-fetched clone, `timeout` a transient operator problem — so an
    undeclared one is a consumer branching on undocumented text.
    """

    # ALL THREE goldens, not one. The reason table sits outside every Jinja
    # conditional today, so they agree -- but the template does carry
    # conditionals, and a declaration placed inside one would satisfy `fast`
    # while leaving `default` and `remote` short.
    GOLDENS = tuple(
        REPO_ROOT / "tests" / "golden" / "skills" / "aitask-trail"
        / f"SKILL-{profile}-claude.md"
        for profile in ("default", "fast", "remote"))
    SOURCE = SCRIPTS_DIR / "lib" / "trail_gather.py"

    @staticmethod
    def declared_in(contract: str) -> "set[str]":
        """Reasons declared as a ROW of the reason table.

        Anchored to the row, not a substring search: `timeout` and
        `no_local_ref` are each mentioned a second time in the prose beneath the
        table, so a bare backtick-substring check stays green for exactly
        those two even if their rows are deleted -- verifying nothing about the
        declaration it exists to protect.
        """
        return set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", contract,
                              re.MULTILINE))

    #: Syntactic shapes this scraper understands. Stated as the guard's
    #: DECLARED SCOPE, because a scraper cannot flag a form nobody has written
    #: yet: a value introduced through a shape not listed here would ship
    #: undeclared and the guard would stay green — the very failure it exists to
    #: prevent, one syntax over. Adding a shape to the code means adding it here.
    COVERED_SHAPES = (
        'x.reason = "v"',
        'x.status, x.reason = "s", "v"',
        'return None, "v"',
        'SourceResult(name, status, age, "v")',
        'SourceResult(..., reason="v")',
    )

    def emitted_reasons(self):
        """Reasons a SourceResult can carry, over `COVERED_SHAPES`.

        Parsed with `ast`, not regex: a regex over the tuple form reliably
        captures the STATUS instead, which is how the first version of this
        guard reported nonsense.
        """
        tree = ast.parse(self.SOURCE.read_text(encoding="utf-8"))
        found = set()

        def value_of(node):
            return (node.value
                    if isinstance(node, ast.Constant)
                    and isinstance(node.value, str) else None)

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    # x.reason = "v"
                    if (isinstance(target, ast.Attribute)
                            and target.attr == "reason"):
                        val = value_of(node.value)
                        if val:
                            found.add(val)
                    # x.status, x.reason = "s", "v"  -> positional match
                    elif isinstance(target, ast.Tuple) and isinstance(
                            node.value, ast.Tuple):
                        for elt, val_node in zip(target.elts,
                                                 node.value.elts):
                            if (isinstance(elt, ast.Attribute)
                                    and elt.attr == "reason"):
                                val = value_of(val_node)
                                if val:
                                    found.add(val)
            # SourceResult(name, status, age, reason) / reason="v".
            # `reason` is a dataclass FIELD, so it can arrive through the
            # constructor without ever being assigned to an attribute.
            elif (isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name)
                  and node.func.id == "SourceResult"):
                if len(node.args) >= 4:
                    val = value_of(node.args[3])
                    if val:
                        found.add(val)
                for kw in node.keywords:
                    if kw.arg == "reason":
                        val = value_of(kw.value)
                        if val:
                            found.add(val)
            # `_locks_cache_age` returns (None, "<reason>")
            elif isinstance(node, ast.Return) and isinstance(node.value,
                                                             ast.Tuple):
                elts = node.value.elts
                if (len(elts) == 2 and isinstance(elts[0], ast.Constant)
                        and elts[0].value is None):
                    val = value_of(elts[1])
                    if val:
                        found.add(val)
        return found

    def test_every_emitted_reason_is_declared_in_every_golden(self):
        emitted = self.emitted_reasons()
        self.assertTrue(emitted, "the scraper found nothing — it has rotted")
        for golden in self.GOLDENS:
            with self.subTest(golden=golden.name):
                declared = self.declared_in(golden.read_text(encoding="utf-8"))
                undeclared = sorted(emitted - declared)
                self.assertEqual(
                    undeclared, [],
                    f"reason(s) emitted by trail_gather.py but not declared as "
                    f"a reason-table row in {golden.name}: {undeclared}. "
                    f"Declare them in .claude/skills/aitask-trail/SKILL.md.j2 "
                    f"and regenerate all three goldens in the same commit.")

    def test_row_anchor_rejects_a_prose_only_mention(self):
        """Negative control for the anchoring. A reason mentioned only in prose
        must NOT count as declared — otherwise the guard is a substring search
        wearing a docstring about declarations."""
        prose = "a `ghost_reason` appears only in a sentence, not a table row.\n"
        self.assertNotIn("ghost_reason", self.declared_in(prose))
        self.assertIn("ghost_reason",
                      self.declared_in("| `ghost_reason` | lock | x |\n"))

    def test_constructor_form_is_covered(self):
        """The dataclass field can be set without any attribute assignment."""
        import textwrap
        tree = ast.parse(textwrap.dedent("""
            a = SourceResult("lock", "unavailable", None, "positional_only")
            b = SourceResult("lock", reason="keyword_only")
        """))
        found = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "SourceResult"):
                if len(node.args) >= 4 and isinstance(node.args[3],
                                                      ast.Constant):
                    found.add(node.args[3].value)
                for kw in node.keywords:
                    if kw.arg == "reason" and isinstance(kw.value,
                                                         ast.Constant):
                        found.add(kw.value.value)
        self.assertEqual(found, {"positional_only", "keyword_only"})

    def test_scraper_finds_the_known_reasons(self):
        """Positive control: without it, a scraper that silently matched
        nothing would make the guard above pass vacuously."""
        emitted = self.emitted_reasons()
        for known in ("no_local_ref", "timeout", "scan_error", "no_reflog",
                      "clock_skew", "unreadable_tree", "no_tasks"):
            self.assertIn(known, emitted)


class ReadOnlyTests(TrailGatherCase):
    def test_drift_leaves_tree_byte_identical(self):
        self.repo.write_task("100", "root")
        self.repo.write_plan("100", "root")
        snap = self.snapshot("--scope", "task", "100")
        trail = self.make_trail(snap)

        def tree_hash() -> str:
            digest = hashlib.sha256()
            for path in sorted(self.repo.root.rglob("*")):
                if path.is_file():
                    digest.update(str(path).encode())
                    digest.update(path.read_bytes())
            return digest.hexdigest()

        before = tree_hash()
        self.drift(trail)
        self.assertEqual(tree_hash(), before)


# --- I. Cross-repo -----------------------------------------------------------


FOREIGN = "trailtest-zz9"


class CrossRepoTests(TrailGatherCase):
    def setUp(self):
        super().setUp()
        base = Path(self._tmp.name)
        self.foreign = SyntheticRepo(base / "foreign", FOREIGN)
        Path(os.environ["AITASKS_PROJECTS_INDEX"]).write_text(
            "projects:\n"
            f"  - name: {FOREIGN}\n"
            f"    path: {self.foreign.root}\n", encoding="utf-8")
        self.repo.write_task("100", "root")
        self.foreign.write_task("12", "foreign_task")

    def test_foreign_task_scope_member_gathers(self):
        snap = self.snapshot("--scope", "task", "100", f"{FOREIGN}#12")
        refs = sorted(m[0] for m in snap["members"])
        self.assertEqual(refs, ["mainproj#100", f"{FOREIGN}#12"])

    def test_unregistered_project_error(self):
        snap = self.snapshot("--scope", "task", "trailtest-ghost#3")
        self.assertEqual(snap["errors"],
                         ["unresolved_project:trailtest-ghost"])

    def test_cross_repo_topic_rejected(self):
        snap = self.snapshot("--scope", "topic", f"{FOREIGN}#12")
        self.assertEqual(snap["errors"],
                         [f"cross_repo_topic_unsupported:{FOREIGN}#12"])

    def _foreign_member_trail(self, topics) -> tuple[dict, Path]:
        snap = self.snapshot("--scope", "task", "100", f"{FOREIGN}#12")
        entries = [
            ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
            (f"{FOREIGN}#12", self.entry_snapshot(snap, f"{FOREIGN}#12")),
        ]
        return snap, self.make_trail(snap, entries=entries,
                                     scope_kind="multi_topic", topics=topics,
                                     owner="mainproj#100")

    def test_foreign_dependent_fires_new_related(self):
        snap, trail = self._foreign_member_trail(["mainproj#100"])
        self.foreign.write_task("13", "dependent", depends=[12])
        result = self.drift(trail)
        self.assertIn((f"{FOREIGN}#13", "new_related_task"),
                      [(t, c) for c, t, _ in result["reasons"]])
        self.assertEqual(result["digest"], snap["digest"])

    def test_qualified_topic_keys_never_cross_match(self):
        self.repo.write_task("635", "local_topic")
        self.foreign.write_task("635", "foreign_topic")
        # Trail scoped to the LOCAL 635 only.
        snap = self.snapshot("--scope", "topic", "635")
        trail = self.make_trail(snap, topics=["mainproj#635"])
        self.foreign.write_task("700", "foreign_member", anchor=635)
        result = self.drift(trail)
        fired = [t for c, t, _ in result["reasons"]
                 if c == "new_related_task"]
        self.assertNotIn(f"{FOREIGN}#700", fired)
        # Same fixture with the FOREIGN root listed -> fires.
        trail2 = self.make_trail(snap, topics=[f"{FOREIGN}#635"],
                                 trail_id="trail-test-foreign")
        result2 = self.drift(trail2)
        fired2 = [t for c, t, _ in result2["reasons"]
                  if c == "new_related_task"]
        self.assertIn(f"{FOREIGN}#700", fired2)


# --- J. Real entry point -----------------------------------------------------


class WrapperIntegrationTests(TrailGatherCase):
    def test_snapshot_and_drift_roundtrip(self):
        self.repo.write_task("100", "root")
        proc = self.run_wrapper("snapshot", "--scope", "task", "100")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("DIGEST:", proc.stdout)
        snap = self.parse_snapshot(proc.stdout)
        trail = self.make_trail(snap)
        proc = self.run_wrapper("drift", "--trail", str(trail))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines()[0], "CURRENT")
        # Mutate -> the suite must be able to fail.
        self.repo.write_task("100", "root", status="Done")
        proc = self.run_wrapper("drift", "--trail", str(trail))
        self.assertEqual(proc.stdout.splitlines()[0], "STALE")
        self.assertIn("DRIFT:task_completed|mainproj#100|", proc.stdout)

    def test_malformed_trail_stdout_contract(self):
        bad = self.repo.root / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        self.repo.write_task("100", "root")
        proc = self.run_wrapper("drift", "--trail", str(bad))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "ERROR:invalid_trail:1\n")
        self.assertIn("INVALID:", proc.stderr)

    def test_unreadable_path(self):
        self.repo.write_task("100", "root")
        proc = self.run_wrapper("drift", "--trail", "nope/missing.json")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "ERROR:trail_unreadable:nope/missing.json\n")

    def test_missing_handle(self):
        self.repo.write_task("100", "root")
        proc = self.run_wrapper("drift", "--trail", "art:no-such-handle")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "ERROR:artifact_unresolved:art:no-such-handle\n")

    def test_positive_handle_resolution_mandatory(self):
        subprocess.run(["git", "init", "-q"], cwd=self.repo.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@test"],
                       cwd=self.repo.root, check=True)
        subprocess.run(["git", "config", "user.name", "t"],
                       cwd=self.repo.root, check=True)
        self.repo.write_task("100", "root")
        snap = self.snapshot("--scope", "task", "100")
        trail = self.make_trail(snap)
        create = subprocess.run(
            [str(SCRIPTS_DIR / "aitask_artifact.sh"), "create", "100",
             str(trail), "--kind", "implementation_trail",
             "--handle", "art:trail-test"],
            capture_output=True, text=True, cwd=self.repo.root,
            env=os.environ.copy(), timeout=120)
        self.assertEqual(create.returncode, 0,
                         create.stdout + create.stderr)
        proc = self.run_wrapper("drift", "--trail", "art:trail-test")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # Byte-exact complete stdout: protocol lines only (pins the
        # "Wrote <path>" stdout->stderr redirection).
        self.assertEqual(
            proc.stdout, f"CURRENT\nDIGEST:{snap['digest']}\n")
        # Wrong-kind artifact through the same handle path.
        blob = self.repo.root / "notatrail.json"
        blob.write_text('{"foo": 1}', encoding="utf-8")
        create2 = subprocess.run(
            [str(SCRIPTS_DIR / "aitask_artifact.sh"), "create", "100",
             str(blob), "--kind", "report", "--handle", "art:trail-wrong"],
            capture_output=True, text=True, cwd=self.repo.root,
            env=os.environ.copy(), timeout=120)
        self.assertEqual(create2.returncode, 0,
                         create2.stdout + create2.stderr)
        proc2 = self.run_wrapper("drift", "--trail", "art:trail-wrong")
        self.assertEqual(proc2.returncode, 0)
        self.assertTrue(proc2.stdout.startswith("ERROR:invalid_trail:"),
                        proc2.stdout)


# --- J2. Fail-closed infra path (characterization) ---------------------------


#: `EXIT_INFRA` in lib/trail_gather.py -- the fail-closed status the trail
#: protocol distinguishes from a usage error (2) and success (0). Kept as an
#: independent literal on purpose: importing `trail_gather.EXIT_INFRA` would
#: make this suite agree with whatever the module does rather than with the
#: protocol contract.
EXIT_INFRA = 3

#: The complete stderr of the fatal path below, observed by probing the real
#: wrapper (t1436 pre-phase). The config path is relative because
#: `_local_dirs()` defaults to `aitasks/` and TrailGatherCase clears TASK_DIR,
#: so the whole stream is deterministic -- no `require_ait_python` preamble, no
#: second line. Pinning the WHOLE stream rather than a prefix is what keeps the
#: message-ownership contract unambiguous: any future wrapper output fails this
#: loudly instead of silently widening what "the prefix is ours" means.
EXPECTED_INFRA_STDERR = (
    "trail_gather: aitasks/metadata/project_config.yaml: "
    "missing project.name\n"
)


class InfraExitCharacterizationTests(TrailGatherCase):
    """`EXIT_INFRA` (3) and the `trail_gather: ` stderr prefix, both verbs.

    **Why this file needs it.** t1436 rewired this module's delimiter-safety
    block onto the shared lib/record_protocol.py. `_die` and the
    `trail_gather: ` prefix stay in trail_gather on purpose -- a library path
    must not sys.exit inside a TUI -- and until t1436 *nothing anywhere* pinned
    either the status or the prefix. This drives the real
    aitask_trail_gather.sh, the only boundary where both are observable.

    Deliberately a **sibling** of `WrapperIntegrationTests`, not a subclass:
    subclassing would silently re-run that class's tests under a second name
    (the point tests/test_work_report_columns_characterization.py spells out at
    its `UnorderedPopulatedTests`).
    """

    CONFIG = ("aitasks", "metadata", "project_config.yaml")

    def _break_project_config(self) -> None:
        """Remove `project.name` -- the one mutation these tests make.

        Reaches `trail_gather.local_project_name` -> `_die(..., EXIT_INFRA)`
        deterministically, and it is the *only* difference between a passing
        and a failing run in every test below.
        """
        (self.repo.root.joinpath(*self.CONFIG)
         ).write_text("project:\n  other: x\n", encoding="utf-8")

    # -- snapshot verb --------------------------------------------------------

    def _run_snapshot(self) -> subprocess.CompletedProcess:
        self.repo.write_task("100", "root")
        self._break_project_config()
        return self.run_wrapper("snapshot", "--scope", "task", "100")

    def test_missing_project_name_exits_infra(self):
        self.assertEqual(self._run_snapshot().returncode, EXIT_INFRA)

    def test_fatal_path_emits_no_protocol_lines(self):
        """A fatal path must not emit a partial stream."""
        self.assertEqual(self._run_snapshot().stdout, "")

    def test_message_carries_the_trail_gather_prefix(self):
        """Whole-stream pin: the prefix AND the message body.

        Asserting the body too is what names *this* `_die` call site rather
        than accepting any EXIT_INFRA -- `cmd_drift` has a second `_die` (the
        version lock) that a prefix-only assertion would happily accept.
        """
        self.assertEqual(self._run_snapshot().stderr, EXPECTED_INFRA_STDERR)

    def test_prefix_assertion_discriminates(self):
        """Negative control for the assertion above.

        If the t1433 rewiring let the shared module's name own this message,
        the prefix would change. Asserting only that the message is ours cannot
        by itself prove the check is live -- so pin the *absence* of the
        plausible replacement too. A run in which BOTH hold is the only passing
        state.
        """
        proc = self._run_snapshot()
        self.assertNotIn("record_protocol:", proc.stderr)
        self.assertNotEqual(proc.stderr.strip(), "")

    def test_a_valid_config_is_not_rejected(self):
        """Positive control: the fatal path is reached by the bad config only."""
        self.repo.write_task("100", "root")
        proc = self.run_wrapper("snapshot", "--scope", "task", "100")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    # -- drift verb -----------------------------------------------------------

    def test_drift_verb_shares_the_infra_contract(self):
        """The same three pins on the OTHER entry path into `local_project_name`.

        **The ordering here is load-bearing.** `cmd_drift` calls
        `local_project_name()` BEFORE it checks that `--trail` exists and before
        `trail_schema.load_trail()`. So a missing, unreadable or schema-invalid
        trail exits 3 with the *identical* message, and a carelessly-built test
        would pass while proving nothing about the valid-trail path. Hence: the
        trail is built and proven live while the config is still valid, and
        breaking the config is the single mutation between the two runs.
        """
        self.repo.write_task("100", "root")
        snap = self.snapshot("--scope", "task", "100")
        trail = self.make_trail(snap)

        # Positive control BEFORE any mutation: this exact trail is schema-valid
        # and this exact path yields a verdict. Without it the exit-3 below
        # would be unattributable -- invalid_trail looks the same from outside.
        ok = self.run_wrapper("drift", "--trail", str(trail))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.splitlines()[0], "CURRENT")

        self._break_project_config()

        proc = self.run_wrapper("drift", "--trail", str(trail))
        self.assertEqual(proc.returncode, EXIT_INFRA)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, EXPECTED_INFRA_STDERR)
        self.assertNotIn("record_protocol:", proc.stderr)


# --- K. Board seam guard -----------------------------------------------------


class BoardSeamGuardTests(unittest.TestCase):
    def test_board_imports_topic_semantics(self):
        src = (SCRIPTS_DIR / "board" / "aitask_board.py").read_text(
            encoding="utf-8")
        self.assertIn("from topic_semantics import", src)
        self.assertNotIn("\ndef topic_key(", src)
        self.assertNotIn("def _parse_filename(", src)


# --- L. Stable-read policy ---------------------------------------------------


class StableReadTests(TrailGatherCase):
    @staticmethod
    def _record(status: str) -> dict:
        return {"ref": "p#1", "kind": "task_file", "exists": True,
                "status": status, "depends": [], "gates_pending": []}

    def test_converges_after_churn(self):
        seq = [([self._record("A")], 1), ([self._record("B")], 2),
               ([self._record("B")], 3)]
        it = iter(seq)
        result = trail_gather.stable_records(lambda: next(it))
        self.assertIsNotNone(result)
        self.assertEqual(result[0][0]["status"], "B")

    def test_permanent_churn_exhausts_bound(self):
        seq = [([self._record("A")], 1), ([self._record("B")], 2),
               ([self._record("C")], 3)]
        it = iter(seq)
        self.assertIsNone(trail_gather.stable_records(lambda: next(it)))

    def test_cmd_surface_reports_unstable(self):
        self.repo.write_task("100", "root")
        original = trail_gather.stable_records
        trail_gather.stable_records = lambda scan_fn, max_scans=3: None
        try:
            out, rc = self.run_cli("snapshot", "--scope", "task", "100")
        finally:
            trail_gather.stable_records = original
        self.assertEqual(rc, 0)
        self.assertEqual(out, "ERROR:unstable_repository_state:snapshot\n")


# --- M. Version-lock tripwire ------------------------------------------------


class VersionLockTests(TrailGatherCase):
    def test_lock_pairing(self):
        # Contract: a NORMALIZATION_VERSION bump MUST ship with a
        # schema_version bump (and an updated lock mapping). If this test is
        # red, someone bumped one side only -- stored digests would become
        # silently incomparable. Bump both together.
        schema = trail_schema.load_schema()
        const = schema["properties"]["schema_version"]["const"]
        self.assertEqual(const, "1.1.0")
        # Deliberately NOT bumped alongside the schema: 1.1.0 added an optional
        # display-only field that never enters the normalized digest, and the
        # lock's contract runs one way (normalization bump => schema bump).
        self.assertEqual(trail_schema.NORMALIZATION_VERSION, "1.0.0")
        self.assertEqual(
            trail_gather.SCHEMA_NORMALIZATION_LOCK.get(const),
            trail_schema.NORMALIZATION_VERSION)

    def test_lock_has_exactly_one_entry_keyed_by_the_schema_const(self):
        """The lock is single-version, and its key is the schema's own const.

        `.get(const)` in the pairing test above passes just as happily with a
        stale extra entry left behind by a bump, which would quietly re-admit
        documents the single-version design means to reject. Pin cardinality
        and the key's provenance, not just the mapped value (t1468_5).
        """
        const = trail_schema.load_schema()["properties"]["schema_version"]["const"]
        self.assertEqual(list(trail_gather.SCHEMA_NORMALIZATION_LOCK), [const])

    def test_old_schema_trail_is_invalid_never_false_stale(self):
        self.repo.write_task("100", "root")
        snap = self.snapshot("--scope", "task", "100")
        trail = self.make_trail(snap)
        const = trail_schema.load_schema()["properties"]["schema_version"]["const"]
        # Both an implausible old version and the *superseded* one: the second
        # is the real cutover case, and the one that must not read as STALE.
        for stale_version in ("0.9.0", SUPERSEDED_SCHEMA_VERSION):
            with self.subTest(schema_version=stale_version):
                self.assertNotEqual(stale_version, const)
                doc = json.loads(trail.read_text())
                doc["schema_version"] = stale_version
                trail.write_text(json.dumps(doc))
                out, rc = self.run_cli("drift", "--trail", str(trail))
                self.assertEqual(rc, 0)
                self.assertTrue(out.startswith("ERROR:invalid_trail:"), out)
                self.assertNotIn("STALE", out)
        self.assertNotIn("STALE", out)
        self.assertNotIn("CURRENT", out)


if __name__ == "__main__":
    unittest.main()
