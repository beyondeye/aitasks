"""Integration / contract tests for the brainstorm module-ops lifecycle (t906).

Risk-mitigation ("after") coverage for t756_3. The existing
``test_brainstorm_apply_module_ops.py`` covers the happy-path apply functions at
unit level; this module adds higher-level integration/contract coverage for the
four surfaces t756_3's risk evaluation flagged:

  A. Multi-output parser robustness — malformed module-decomposer blocks.
  B. Auto-apply gate + idempotency — the pure ``*_needs_apply`` contract the
     Textual poller relies on (apply exactly once, then stop tracking).
  C. Group-metadata restore — apply reads all options back from br_groups.yaml,
     the contract that lets apply run after an app restart.
  D. Linked child-task creation — ``_create_linked_module_task`` driven through
     a real stubbed ``aitask_create.sh`` script (subprocess + stdout-parse
     boundary), end-to-end with module_tasks persistence.

Scope honesty: the Textual auto-apply poller *App methods*
(``_poll_module_agents`` / ``_try_apply_module_agent_if_needed`` in
``brainstorm_app.py``) cannot run headless, so Group B exercises their decision
contract — the needs-apply gate plus apply idempotency — not the interval/timer
wiring. The timer wiring and live agent launch remain owned by the
manual-verification task t905.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

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
from brainstorm.brainstorm_dag import list_nodes  # noqa: E402
from brainstorm.brainstorm_session import (  # noqa: E402
    GROUPS_FILE,
    _create_linked_module_task,
    _module_decomposer_needs_apply,
    _module_merger_needs_apply,
    _module_tasks_map,
    apply_module_decompose_from_sections,
    apply_module_decomposer_output,
    apply_module_merger_output,
    discard_module_decomposer_output,
    module_decomposer_review_enabled,
    parse_module_decomposer_output,
    record_operation,
)

TASK = "756"


def _seed_base(wt: Path) -> None:
    """Seed a minimal worktree with an umbrella root at HEAD (n000_init)."""
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
        wt,
        "n000_init",
        [],
        "Umbrella",
        {"component_core": "Core"},
        "## Overview\nUmbrella\n",
        "bootstrap",
    )
    set_head(wt, "n000_init")


def _module_block(module: str, node_id: str) -> str:
    return f"""--- MODULE_NODE_START ---
--- MODULE_NAME_START ---
{module}
--- MODULE_NAME_END ---
--- NODE_YAML_START ---
node_id: {node_id}
parents: []
description: "{module} root"
proposal_file: br_proposals/{node_id}.md
created_at: "2026-06-02 12:00"
component_{module}: "{module} component"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
## Overview
{module} proposal
--- PROPOSAL_END ---
--- MODULE_NODE_END ---
"""


def _module_block_custom(name: str, yaml_body: str) -> str:
    """A MODULE_NODE block with an arbitrary MODULE_NAME and NODE_YAML body —
    used to drive the parser's validation guards."""
    return f"""--- MODULE_NODE_START ---
--- MODULE_NAME_START ---
{name}
--- MODULE_NAME_END ---
--- NODE_YAML_START ---
{yaml_body}
--- NODE_YAML_END ---
--- PROPOSAL_START ---
## Overview
body
--- PROPOSAL_END ---
--- MODULE_NODE_END ---
"""


def _node_output(node_id: str) -> str:
    return f"""--- NODE_YAML_START ---
node_id: {node_id}
parents: []
description: "Merged parser"
proposal_file: br_proposals/{node_id}.md
created_at: "2026-06-02 12:00"
component_parser: "Merged parser component"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
## Overview
Merged parser into umbrella.
--- PROPOSAL_END ---
"""


def _record_decompose(modules, **extra) -> None:
    record_operation(
        TASK,
        "module_decompose_001",
        "module_decompose",
        ["module_decomposer_001"],
        "n000_init",
        modules=list(modules),
        subgraph=UMBRELLA_SUBGRAPH,
        **extra,
    )


def _write_decomposer_output(wt: Path, body: str) -> None:
    (wt / "module_decomposer_001_output.md").write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Group A — multi-output parser robustness
# --------------------------------------------------------------------------- #
class ParserRobustnessTests(unittest.TestCase):
    def test_three_blocks_create_roots_in_document_order(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            _write_decomposer_output(
                wt,
                _module_block("parser", "n001_module_decomposer_001_parser")
                + _module_block("cache", "n002_module_decomposer_001_cache")
                + _module_block("io", "n003_module_decomposer_001_io"),
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _record_decompose(["parser", "cache", "io"])
                created = apply_module_decomposer_output(TASK, "module_decomposer_001")

            self.assertEqual(
                created,
                [
                    "n001_module_decomposer_001_parser",
                    "n002_module_decomposer_001_cache",
                    "n003_module_decomposer_001_io",
                ],
            )
            self.assertEqual(read_node(wt, created[2])["module_label"], "io")
            self.assertEqual(read_node(wt, created[2])["parents"], ["n000_init"])
            self.assertEqual(get_head(wt), "n000_init")  # umbrella HEAD untouched

    def test_no_module_blocks_raises(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            _write_decomposer_output(wt, "garbage with no node blocks\n")
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _record_decompose(["parser"])
                with self.assertRaisesRegex(ValueError, "no MODULE_NODE blocks"):
                    apply_module_decomposer_output(TASK, "module_decomposer_001")

    def test_empty_module_name_raises(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            _write_decomposer_output(
                wt,
                _module_block_custom(
                    "",
                    'node_id: n001_x\nparents: []\ndescription: "x"\n'
                    'component_x: "x"\n',
                ),
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _record_decompose(["x"])
                with self.assertRaisesRegex(
                    ValueError, "MODULE_NAME block cannot be empty"
                ):
                    apply_module_decomposer_output(TASK, "module_decomposer_001")

    def test_missing_node_id_raises(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            _write_decomposer_output(
                wt,
                _module_block_custom(
                    "parser",
                    'parents: []\ndescription: "no id"\ncomponent_parser: "p"\n',
                ),
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _record_decompose(["parser"])
                with self.assertRaisesRegex(ValueError, "missing node_id"):
                    apply_module_decomposer_output(TASK, "module_decomposer_001")

    def test_duplicate_node_id_raises(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            create_node(
                wt,
                "n001_module_decomposer_001_parser",
                ["n000_init"],
                "pre-existing",
                {"component_parser": "p"},
                "## Overview\npre\n",
                "module_decompose_001",
                module_label="parser",
            )
            _write_decomposer_output(
                wt, _module_block("parser", "n001_module_decomposer_001_parser")
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _record_decompose(["parser"])
                with self.assertRaisesRegex(ValueError, "already exists"):
                    apply_module_decomposer_output(TASK, "module_decomposer_001")


# --------------------------------------------------------------------------- #
# Group B — auto-apply gate + idempotency contract
# --------------------------------------------------------------------------- #
class AutoApplyGateTests(unittest.TestCase):
    def test_decomposer_needs_apply_lifecycle(self):
        """False (no output) → True (completed, unapplied) → False (applied).

        This is exactly the gate ``_try_apply_module_agent_if_needed`` uses to
        decide whether to apply and then discard a tracked agent.
        """
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                # No output file yet → nothing to apply.
                self.assertFalse(
                    _module_decomposer_needs_apply(TASK, "module_decomposer_001")
                )

                _write_decomposer_output(
                    wt,
                    _module_block("parser", "n001_module_decomposer_001_parser"),
                )
                _record_decompose(["parser"])

                # Completed output, nodes not created → needs apply.
                self.assertTrue(
                    _module_decomposer_needs_apply(TASK, "module_decomposer_001")
                )

                apply_module_decomposer_output(TASK, "module_decomposer_001")

                # Applied once → must not re-apply (idempotent / drained).
                self.assertFalse(
                    _module_decomposer_needs_apply(TASK, "module_decomposer_001")
                )

    def test_merger_needs_apply_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            create_node(
                wt,
                "n001_parser",
                ["n000_init"],
                "Parser root",
                {"component_parser": "Parser"},
                "## Overview\nParser\n",
                "module_decompose_001",
                module_label="parser",
            )
            set_head(wt, "n001_parser", module="parser")
            (wt / "module_merger_001_output.md").write_text(
                _node_output("n002_module_merger_001"), encoding="utf-8"
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                self.assertTrue(
                    _module_merger_needs_apply(TASK, "module_merger_001")
                )
                record_operation(
                    TASK,
                    "module_merge_001",
                    "module_merge",
                    ["module_merger_001"],
                    "n001_parser",
                    subgraph=UMBRELLA_SUBGRAPH,
                    source_subgraph="parser",
                    destination_subgraph=UMBRELLA_SUBGRAPH,
                )
                apply_module_merger_output(TASK, "module_merger_001")
                self.assertFalse(
                    _module_merger_needs_apply(TASK, "module_merger_001")
                )


# --------------------------------------------------------------------------- #
# Group C — group-metadata restore ("after app restart")
# --------------------------------------------------------------------------- #
class GroupMetadataRestoreTests(unittest.TestCase):
    def test_from_sections_apply_reads_modules_from_persisted_group(self):
        """apply takes only (task, group_name); modules/head come off disk."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            (wt / PROPOSALS_DIR / "n000_init.md").write_text(
                "<!-- section: parser [dimensions: component_parser] -->\n"
                "## Parser\nParser section.\n"
                "<!-- /section: parser -->\n\n"
                "<!-- section: cache [dimensions: component_cache] -->\n"
                "## Cache\nCache section.\n"
                "<!-- /section: cache -->\n",
                encoding="utf-8",
            )
            node = read_node(wt, "n000_init")
            node["component_parser"] = "Parser"
            node["component_cache"] = "Cache"
            (wt / NODES_DIR / "n000_init.yaml").write_text(
                yaml.safe_dump(node), encoding="utf-8"
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _record_decompose(["parser", "cache"], from_sections=True)
                # Fresh call — every option (modules, head_at_creation) is read
                # back from br_groups.yaml, nothing passed in.
                created = apply_module_decompose_from_sections(
                    TASK, "module_decompose_001"
                )
            self.assertEqual(len(created), 2)
            self.assertEqual(read_node(wt, created[0])["module_label"], "parser")
            self.assertEqual(read_node(wt, created[1])["module_label"], "cache")

    def test_from_sections_apply_without_modules_in_group_raises(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _record_decompose([], from_sections=True)
                with self.assertRaisesRegex(ValueError, "requires modules"):
                    apply_module_decompose_from_sections(TASK, "module_decompose_001")

    def test_merger_apply_reads_subgraphs_from_group(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            create_node(
                wt,
                "n001_parser",
                ["n000_init"],
                "Parser root",
                {"component_parser": "Parser"},
                "## Overview\nParser\n",
                "module_decompose_001",
                module_label="parser",
            )
            set_head(wt, "n001_parser", module="parser")
            (wt / "module_merger_001_output.md").write_text(
                _node_output("n002_module_merger_001"), encoding="utf-8"
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                record_operation(
                    TASK,
                    "module_merge_001",
                    "module_merge",
                    ["module_merger_001"],
                    "n001_parser",
                    subgraph=UMBRELLA_SUBGRAPH,
                    source_subgraph="parser",
                    destination_subgraph=UMBRELLA_SUBGRAPH,
                )
                new_id = apply_module_merger_output(TASK, "module_merger_001")
            # Source + destination came purely from persisted group metadata.
            self.assertEqual(
                read_node(wt, new_id)["parents"], ["n000_init", "n001_parser"]
            )
            self.assertEqual(get_head(wt), new_id)

    def test_merger_apply_missing_destination_subgraph_raises(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            (wt / "module_merger_001_output.md").write_text(
                _node_output("n002_module_merger_001"), encoding="utf-8"
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                # destination_subgraph deliberately omitted from the group.
                record_operation(
                    TASK,
                    "module_merge_001",
                    "module_merge",
                    ["module_merger_001"],
                    "n001_parser",
                    subgraph=UMBRELLA_SUBGRAPH,
                    source_subgraph="parser",
                )
                with self.assertRaisesRegex(
                    ValueError, "missing source/destination subgraph"
                ):
                    apply_module_merger_output(TASK, "module_merger_001")


# --------------------------------------------------------------------------- #
# Group D — linked child-task creation via a stubbed aitask_create.sh
# --------------------------------------------------------------------------- #
class _StubRepo:
    """Context manager: a temp dir containing a stub
    ``.aitask-scripts/aitask_create.sh`` that records its argv and emits a
    crafted stdout, with cwd switched into it (so the relative script path in
    ``_create_linked_module_task`` resolves to the stub)."""

    def __init__(self, stdout_lines, returncode=0):
        self._stdout_lines = stdout_lines
        self._returncode = returncode
        self._tmp = None
        self._prev_cwd = None
        self.argv_log = None

    def __enter__(self):
        self._tmp = tempfile.mkdtemp()
        root = Path(self._tmp)
        scripts = root / ".aitask-scripts"
        scripts.mkdir(parents=True)
        self.argv_log = root / "argv.log"
        echo_lines = "".join(
            f'echo {repr(line)}\n' for line in self._stdout_lines
        )
        stub = scripts / "aitask_create.sh"
        stub.write_text(
            "#!/usr/bin/env bash\n"
            f'printf "%s\\n" "$@" > {repr(str(self.argv_log))}\n'
            f"{echo_lines}"
            f"exit {self._returncode}\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        self._prev_cwd = os.getcwd()
        os.chdir(root)
        return self

    def recorded_argv(self):
        return self.argv_log.read_text(encoding="utf-8").splitlines()

    def __exit__(self, *exc):
        os.chdir(self._prev_cwd)
        return False


class LinkedTaskCreationTests(unittest.TestCase):
    def test_create_linked_task_parses_id_and_passes_expected_args(self):
        with _StubRepo(["aitasks/t756/t756_1_parser_module.md"]) as repo:
            task_id = _create_linked_module_task(TASK, "parser", "desc")
        self.assertEqual(task_id, "756_1")
        argv = repo.recorded_argv()
        for expected in (
            "--batch", "--commit", "--silent",
            "--parent", "756",
            "--name", "parser_module",
            "--type", "feature",
            "--desc", "desc",
        ):
            self.assertIn(expected, argv)

    def test_create_linked_task_parent_only_id(self):
        with _StubRepo(["aitasks/t900_parser_module.md"]):
            self.assertEqual(_create_linked_module_task(TASK, "parser", "d"), "900")

    def test_create_linked_task_script_failure_raises(self):
        with _StubRepo(["boom"], returncode=1):
            with self.assertRaisesRegex(RuntimeError, "aitask_create.sh failed"):
                _create_linked_module_task(TASK, "parser", "d")

    def test_create_linked_task_unparseable_output_raises(self):
        with _StubRepo(["not-a-task-path"]):
            with self.assertRaisesRegex(ValueError, "could not parse created task id"):
                _create_linked_module_task(TASK, "parser", "d")

    def test_decompose_with_link_to_task_persists_module_tasks(self):
        """End-to-end: parser → apply → linked child task → module_tasks write.

        crew_worktree is patched to the worktree; cwd is switched (via _StubRepo)
        so the create-script shell-out resolves to the stub. The module HEAD is
        created AND module_tasks[module] is persisted in br_graph_state.yaml.
        """
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            _write_decomposer_output(
                wt, _module_block("parser", "n001_module_decomposer_001_parser")
            )
            with _StubRepo(["aitasks/t756/t756_1_parser_module.md"]) as repo:
                with patch(
                    "brainstorm.brainstorm_session.crew_worktree", return_value=wt
                ):
                    _record_decompose(["parser"], link_to_task=True)
                    created = apply_module_decomposer_output(
                        TASK, "module_decomposer_001"
                    )
                argv = repo.recorded_argv()

            self.assertEqual(created, ["n001_module_decomposer_001_parser"])
            self.assertEqual(get_head(wt, module="parser"), created[0])
            self.assertEqual(_module_tasks_map(wt), {"parser": "756_1"})
            self.assertIn("--parent", argv)
            self.assertIn("756", argv)


# --------------------------------------------------------------------------- #
# Group E — review-gate parse + helpers (t929_1: iterate-before-apply)
# --------------------------------------------------------------------------- #
class ReviewGateTests(unittest.TestCase):
    def test_parse_is_pure_and_returns_structured_blocks(self):
        """parse_module_decomposer_output yields structured blocks and mutates
        neither the graph nor the filesystem."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            text = (
                _module_block("parser", "n001_module_decomposer_001_parser")
                + _module_block("cache", "n002_module_decomposer_001_cache")
            )
            before = set(list_nodes(wt))
            blocks = parse_module_decomposer_output(text)
            after = set(list_nodes(wt))

            self.assertEqual(after, before)  # no graph mutation
            self.assertEqual([b["module_name"] for b in blocks], ["parser", "cache"])
            self.assertEqual(
                [b["node_id"] for b in blocks],
                [
                    "n001_module_decomposer_001_parser",
                    "n002_module_decomposer_001_cache",
                ],
            )
            for b in blocks:
                self.assertIn("proposal_excerpt", b)
                self.assertTrue(b["proposal_excerpt"])
                self.assertIsInstance(b["node_data"], dict)

    def test_parse_no_blocks_raises(self):
        with self.assertRaises(ValueError):
            parse_module_decomposer_output("nothing to see here\n")

    def test_review_enabled_reads_persisted_flag(self):
        """module_decomposer_review_enabled reflects the group's persisted flag;
        absent (legacy groups) defaults to False."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _record_decompose(["parser"], review_before_apply=True)
                self.assertTrue(
                    module_decomposer_review_enabled(TASK, "module_decomposer_001")
                )
                _record_decompose(["parser"], review_before_apply=False)
                self.assertFalse(
                    module_decomposer_review_enabled(TASK, "module_decomposer_001")
                )
                _record_decompose(["parser"])  # no flag → legacy default
                self.assertFalse(
                    module_decomposer_review_enabled(TASK, "module_decomposer_001")
                )

    def test_discard_output_neutralizes_needs_apply(self):
        """Cancelling/superseding a proposal renames its output aside so the
        poller's needs-apply gate goes False — and the graph is untouched."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                _write_decomposer_output(
                    wt, _module_block("parser", "n001_module_decomposer_001_parser")
                )
                _record_decompose(["parser"], review_before_apply=True)
                self.assertTrue(
                    _module_decomposer_needs_apply(TASK, "module_decomposer_001")
                )
                nodes_before = set(list_nodes(wt))
                discard_module_decomposer_output(
                    TASK, "module_decomposer_001", suffix="cancelled"
                )
                self.assertFalse(
                    _module_decomposer_needs_apply(TASK, "module_decomposer_001")
                )
                self.assertEqual(set(list_nodes(wt)), nodes_before)  # graph intact
                self.assertTrue(
                    (wt / "module_decomposer_001_output.cancelled.md").is_file()
                )


if __name__ == "__main__":
    unittest.main()
