#!/usr/bin/env python3
"""Tests for the trail gatherer + drift helper (t1210_2).

Covers the pinned contracts of lib/trail_gather.py against synthetic task
repositories: topic/scope parity with the board seam (A/A2), record + digest
ground truth (B), digest stability/sensitivity (C), the emittable drift-code
set with every code producible (D), the driftable-input rule (D2),
plan-identity fixtures (E), presence tracking (F), protocol determinism +
delimiter safety (G), the read-only guarantee (H), cross-repo resolution and
qualified-key collisions (I), the real .sh entry point including mandatory
positive artifact-handle resolution (J), the board-seam extraction guard (K),
the stable-read policy (L), and the schema/normalization version-lock
tripwire (M).

Run: python3 -m unittest tests.test_trail_gather -v
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
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
import trail_schema  # noqa: E402

WRAPPER = SCRIPTS_DIR / "aitask_trail_gather.sh"

TS = "2026-07-23T10:00:00Z"


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

    def snapshot(self, *argv: str) -> dict:
        out, rc = self.run_cli("snapshot", *argv)
        self.assertEqual(rc, 0, out)
        return self.parse_snapshot(out)

    @staticmethod
    def parse_snapshot(out: str) -> dict:
        parsed = {"members": [], "inputs": [], "errors": [], "raw": out}
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
            "schema_version": "1.0.0",
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
        if exclusions:
            doc["exclusions"] = [
                {"task": t, "reason": "out_of_scope", "note": "n"}
                for t in exclusions]
        if observations:
            doc["observations"] = [
                {"observation_id": f"o{i}", "category": "baseline_risk",
                 "summary": "s", "affects": list(affects),
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
        self.assertEqual(trail_gather._free_text("a\r\nb\nc"), "a b c")


# --- H. Read-only guarantee --------------------------------------------------


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
    def run_wrapper(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(WRAPPER), *argv], capture_output=True, text=True,
            cwd=self.repo.root, env=os.environ.copy(), timeout=120,
        )

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
        self.assertEqual(const, "1.0.0")
        self.assertEqual(trail_schema.NORMALIZATION_VERSION, "1.0.0")
        self.assertEqual(
            trail_gather.SCHEMA_NORMALIZATION_LOCK.get(const),
            trail_schema.NORMALIZATION_VERSION)

    def test_old_schema_trail_is_invalid_never_false_stale(self):
        self.repo.write_task("100", "root")
        snap = self.snapshot("--scope", "task", "100")
        trail = self.make_trail(snap)
        doc = json.loads(trail.read_text())
        doc["schema_version"] = "0.9.0"
        trail.write_text(json.dumps(doc))
        out, rc = self.run_cli("drift", "--trail", str(trail))
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("ERROR:invalid_trail:"), out)
        self.assertNotIn("STALE", out)
        self.assertNotIn("CURRENT", out)


if __name__ == "__main__":
    unittest.main()
