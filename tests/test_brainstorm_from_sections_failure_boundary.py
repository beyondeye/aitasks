"""Failure boundary of the from-sections Module Decompose op (t2005).

``run_module_decompose_from_sections`` owns the operation record the way
``run_prune_operation`` does: every read and check — including that every
module has a section — runs before the first write, and a refusal deletes the
record; a failure after writing started keeps the record as ``status: Error``
with the module and stage reached, the roots created and, when ``create_node``
itself stopped part-way, the incomplete root.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import brainstorm.brainstorm_session as bs  # noqa: E402
from brainstorm.brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    create_node,
    get_head,
    read_node,
    set_head,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    GROUPS_FILE,
    ModuleDecomposePartialFailure,
    ModuleDecomposeRefused,
    run_module_decompose_from_sections,
)
from launch_modes import DEFAULT_LAUNCH_MODE  # noqa: E402

TASK = "2005"
GROUP = "module_decompose_001"
SOURCE = "n000_init"
PARSER_ROOT = "n001_module_decomposer_sections_parser"
CACHE_ROOT = "n002_module_decomposer_sections_cache"

SECTIONED_PROPOSAL = (
    "<!-- section: parser [dimensions: component_parser] -->\n"
    "## Parser\nParser section.\n"
    "<!-- /section: parser -->\n\n"
    "<!-- section: cache [dimensions: component_cache] -->\n"
    "## Cache\nCache section.\n"
    "<!-- /section: cache -->\n"
)


def _seed(wt: Path, proposal: str = SECTIONED_PROPOSAL) -> None:
    """An umbrella root at HEAD with a parser/cache sectioned proposal."""
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / GRAPH_STATE_FILE).write_text(
        yaml.safe_dump({
            "current_head": None,
            "current_heads": {},
            "history": {},
            "next_node_id": 1,
            "active_dimensions": [],
            "module_tasks": {},
            "last_synced_at": {},
        }),
        encoding="utf-8",
    )
    create_node(
        wt, SOURCE, [], "Umbrella",
        {"component_parser": "Parser", "component_cache": "Cache"},
        proposal, "bootstrap",
    )
    set_head(wt, SOURCE)


def _groups(wt: Path) -> dict:
    path = wt / GROUPS_FILE
    if not path.is_file():
        return {}
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("groups", {})


def _module_tasks(wt: Path) -> dict:
    gs = yaml.safe_load((wt / GRAPH_STATE_FILE).read_text(encoding="utf-8")) or {}
    return gs.get("module_tasks") or {}


class FromSectionsFailureBoundaryTests(unittest.TestCase):
    """Only a refusal before any write deletes the operation record.

    Negative control (not shipped code): a variant of
    ``run_module_decompose_from_sections`` that called ``delete_group`` on
    *every* exception would fail the "record survives" assertions in the
    fault-injection tests below; the pre-t2005 apply, which checked each
    module's section inside its creation loop, wrote the parser root before
    refusing ``missing`` and left the record ``Waiting`` on a link failure.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="brainstorm_from_sections_boundary_")
        self.wt = Path(self.tmp)
        _seed(self.wt)
        self._patch = patch.object(bs, "crew_worktree", return_value=self.wt)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, modules, link_to_task=False):
        """Run the op with the extras ``BrainstormApp._run_design_op`` passes."""
        return run_module_decompose_from_sections(
            TASK,
            GROUP,
            head_at_creation=SOURCE,
            subgraph=UMBRELLA_SUBGRAPH,
            modules=list(modules),
            from_sections=True,
            link_to_task=link_to_task,
            source_subgraph=UMBRELLA_SUBGRAPH,
            review_before_apply=True,
            instructions="",
            launch_mode=DEFAULT_LAUNCH_MODE,
        )

    def _snapshot(self):
        return (
            sorted(p.name for p in (self.wt / NODES_DIR).iterdir()),
            sorted(p.name for p in (self.wt / PROPOSALS_DIR).iterdir()),
            (self.wt / GRAPH_STATE_FILE).read_bytes(),
        )

    def _assert_refused_without_trace(self, modules):
        before = self._snapshot()
        with self.assertRaises(ModuleDecomposeRefused) as ctx:
            self._run(modules)
        self.assertIsInstance(ctx.exception, ValueError)
        self.assertNotIn(GROUP, _groups(self.wt))
        # Nodes, proposals, counter, HEADs and module_tasks are all untouched.
        self.assertEqual(self._snapshot(), before)
        return ctx.exception

    # -- success -----------------------------------------------------------

    def test_success_records_extras_and_completes(self):
        created = self._run(["parser", "cache"])
        self.assertEqual(created, [PARSER_ROOT, CACHE_ROOT])
        grp = _groups(self.wt)[GROUP]
        self.assertEqual(grp["operation"], "module_decompose")
        self.assertEqual(grp["agents"], [])
        self.assertEqual(grp["status"], "Completed")
        self.assertEqual(grp["nodes_created"], [PARSER_ROOT, CACHE_ROOT])
        self.assertEqual(grp["modules"], ["parser", "cache"])
        self.assertTrue(grp["from_sections"])
        self.assertNotIn("error", grp)
        self.assertNotIn("incomplete_node", grp)
        self.assertEqual(get_head(self.wt, module="parser"), PARSER_ROOT)
        self.assertEqual(get_head(self.wt, module="cache"), CACHE_ROOT)
        self.assertEqual(get_head(self.wt), SOURCE)
        self.assertEqual(read_node(self.wt, CACHE_ROOT)["module_label"], "cache")

    # -- refusals: nothing written, record removed ---------------------------

    def test_missing_section_is_refused_before_any_write(self):
        exc = self._assert_refused_without_trace(["parser", "missing", "absent"])
        self.assertIn("'missing'", str(exc))
        self.assertIn("'absent'", str(exc))
        self.assertIn("no section found for modules", str(exc))

    def test_single_missing_section_keeps_the_singular_message(self):
        exc = self._assert_refused_without_trace(["parser", "missing"])
        self.assertIn("no section found for module 'missing'", str(exc))

    def test_invalid_sections_are_refused_and_record_removed(self):
        (self.wt / PROPOSALS_DIR / f"{SOURCE}.md").write_text(
            SECTIONED_PROPOSAL
            + "\n<!-- section: ghost [dimensions: component_ghost] -->\n"
            "## Ghost\nGhost section.\n"
            "<!-- /section: ghost -->\n",
            encoding="utf-8",
        )
        exc = self._assert_refused_without_trace(["parser", "cache"])
        self.assertIn("source proposal sections invalid", str(exc))

    def test_no_modules_is_refused_and_record_removed(self):
        exc = self._assert_refused_without_trace([])
        self.assertIn("requires modules", str(exc))

    def test_unanticipated_preflight_failure_is_a_refusal(self):
        # Any failure before the first write leaves the session untouched, so
        # it must not leave an agent-less record stuck in Waiting.
        with patch.object(bs, "_section_for_module",
                          side_effect=RuntimeError("parser bug")):
            exc = self._assert_refused_without_trace(["parser", "cache"])
        self.assertIn("module decompose preflight failed: RuntimeError", str(exc))

    # -- partial failures: record kept as Error ------------------------------

    def test_link_failure_after_first_root_keeps_record_as_error(self):
        with patch.object(
            bs, "_create_linked_module_task",
            side_effect=RuntimeError("aitask_create.sh failed: boom"),
        ):
            with self.assertRaises(ModuleDecomposePartialFailure) as ctx:
                self._run(["parser", "cache"], link_to_task=True)
        exc = ctx.exception
        self.assertEqual(exc.module, "parser")
        self.assertEqual(exc.stage, "node_recorded")
        self.assertEqual(exc.created, [PARSER_ROOT])
        self.assertIsNone(exc.incomplete_node_id)
        grp = _groups(self.wt).get(GROUP)
        self.assertIsNotNone(grp, "operation record must survive a partial failure")
        self.assertEqual(grp["status"], "Error")
        self.assertIn("parser", grp["error"])
        self.assertIn("node_recorded", grp["error"])
        self.assertIn("boom", grp["error"])
        self.assertEqual(grp["nodes_created"], [PARSER_ROOT])
        self.assertNotIn("incomplete_node", grp)
        # No rollback: parser's root and HEAD stay; cache was never started.
        self.assertEqual(get_head(self.wt, module="parser"), PARSER_ROOT)
        self.assertFalse((self.wt / NODES_DIR / f"{CACHE_ROOT}.yaml").exists())
        self.assertEqual(_module_tasks(self.wt), {})

    def test_fault_between_node_and_record_keeps_node_in_record(self):
        real = bs.set_head

        def flaky(wt, node_id, module=UMBRELLA_SUBGRAPH):
            if module == "cache":
                raise OSError("disk full")
            return real(wt, node_id, module=module)

        with patch.object(bs, "set_head", side_effect=flaky):
            with self.assertRaises(ModuleDecomposePartialFailure) as ctx:
                self._run(["parser", "cache"])
        exc = ctx.exception
        self.assertEqual(exc.module, "cache")
        self.assertEqual(exc.stage, "node_created")
        self.assertEqual(exc.created, [PARSER_ROOT, CACHE_ROOT])
        self.assertIsNone(exc.incomplete_node_id)
        grp = _groups(self.wt).get(GROUP)
        self.assertIsNotNone(grp, "operation record must survive a partial failure")
        self.assertEqual(grp["status"], "Error")
        self.assertIn("cache: node_created", grp["error"])
        # The cache root is complete but its own nodes_created write never ran:
        # the except path records it.
        self.assertEqual(grp["nodes_created"], [PARSER_ROOT, CACHE_ROOT])
        self.assertIsNone(get_head(self.wt, module="cache"))

    def test_proposal_write_fault_records_incomplete_node(self):
        # create_node writes the node YAML before the proposal; fail only the
        # cache root's proposal write so the real create_node stops in between.
        real_write_text = Path.write_text
        target = self.wt / PROPOSALS_DIR / f"{CACHE_ROOT}.md"

        def flaky(path_self, *args, **kwargs):
            if path_self == target:
                raise OSError("disk full")
            return real_write_text(path_self, *args, **kwargs)

        with patch.object(Path, "write_text", flaky):
            with self.assertRaises(ModuleDecomposePartialFailure) as ctx:
                self._run(["parser", "cache"])
        # Precondition: the fault fired after the YAML landed.
        self.assertTrue((self.wt / NODES_DIR / f"{CACHE_ROOT}.yaml").is_file())
        self.assertFalse(target.exists())
        exc = ctx.exception
        self.assertEqual(exc.module, "cache")
        self.assertEqual(exc.stage, "counter_bumped")
        self.assertEqual(exc.created, [PARSER_ROOT])
        self.assertEqual(exc.incomplete_node_id, CACHE_ROOT)
        self.assertIn(f"incomplete node {CACHE_ROOT}", str(exc))
        grp = _groups(self.wt).get(GROUP)
        self.assertIsNotNone(grp, "operation record must survive a partial failure")
        self.assertEqual(grp["status"], "Error")
        self.assertEqual(grp["incomplete_node"], CACHE_ROOT)
        self.assertIn("cache: counter_bumped", grp["error"])
        # The incomplete root is named, never listed as created.
        self.assertEqual(grp["nodes_created"], [PARSER_ROOT])
        self.assertIsNone(get_head(self.wt, module="cache"))
        self.assertEqual(get_head(self.wt, module="parser"), PARSER_ROOT)

    def test_fault_on_completion_write_keeps_record_as_error(self):
        real = bs.update_operation

        def flaky(task_num, group_name, **fields):
            if fields.get("status") == "Completed":
                raise OSError("write failed")
            return real(task_num, group_name, **fields)

        with patch.object(bs, "update_operation", side_effect=flaky):
            with self.assertRaises(ModuleDecomposePartialFailure) as ctx:
                self._run(["parser", "cache"])
        self.assertEqual(ctx.exception.created, [PARSER_ROOT, CACHE_ROOT])
        grp = _groups(self.wt).get(GROUP)
        self.assertIsNotNone(grp, "operation record must survive a partial failure")
        self.assertEqual(grp["status"], "Error")
        self.assertIn("write failed", grp["error"])
        self.assertEqual(grp["nodes_created"], [PARSER_ROOT, CACHE_ROOT])
        self.assertNotIn("incomplete_node", grp)
        self.assertEqual(get_head(self.wt, module="cache"), CACHE_ROOT)


if __name__ == "__main__":
    unittest.main()
