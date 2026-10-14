"""Tests for the brainstorm prune-dimensions op (t1983).

Covers the deterministic core (section-tag rewrite, importance ranking, the
apply path and its failure boundary), the explorer-input filter on
``active_dimensions``, and the wizard config step (ranked checklist, top-N
re-checking, and state restore on configure -> confirm -> Back).
"""

from __future__ import annotations

import asyncio
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

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Checkbox, Input, Label, RadioButton, RadioSet  # noqa: E402

import brainstorm.brainstorm_session as bs  # noqa: E402
from brainstorm.brainstorm_app import ActionsWizardScreen  # noqa: E402
from brainstorm.brainstorm_crew import _assemble_input_explorer  # noqa: E402
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
from brainstorm.brainstorm_schemas import extract_dimensions  # noqa: E402
from brainstorm.brainstorm_sections import (  # noqa: E402
    parse_sections,
    strip_dimension_tags,
    validate_sections,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    GROUPS_FILE,
    PrunePartialFailure,
    PruneRefused,
    apply_prune_dimensions,
    dimension_rank_signals,
    rank_dimensions,
    record_operation,
    run_prune_operation,
)
from brainstorm.utils import _parse_prune_label  # noqa: E402

SOURCE = "n001_explorer_001"

PROPOSAL = """\
# Proposal
<!-- section: overview [dimensions: requirements_*] -->
## Overview
Covers component_alpha (not component_alpha_ext) and requirements_core.
<!-- /section: overview -->
<!-- section: components [dimensions: component_*] -->
<!-- section: component_alpha [dimensions: component_alpha] -->
Alpha prose.
<!-- /section: component_alpha -->
<!-- section: component_beta [dimensions: component_beta] -->
Beta prose.
<!-- /section: component_beta -->
<!-- /section: components -->
<!-- section: decisions [dimensions: component_alpha, assumption_cache, tradeoff_speed] -->
Decisions mention tradeoff_speed.
<!-- /section: decisions -->
<!-- section: open_questions -->
None.
<!-- /section: open_questions -->
"""

DIMS = {
    "requirements_core": "Core requirement",
    "requirements_extra": "Extra requirement",
    "component_alpha": "Alpha",
    "component_beta": "Beta",
    "component_alpha_ext": "Alpha extension",
    "assumption_cache": "Cache is warm",
    "tradeoff_speed": "Speed over size",
    "tradeoff_cost": "Cost",
}


def _seed_session(wt: Path, *, active=None, module: str | None = None) -> None:
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / GRAPH_STATE_FILE).write_text(
        yaml.safe_dump({
            "current_head": None,
            "current_heads": {},
            "history": {},
            "next_node_id": 2,
            "active_dimensions": list(active or []),
            "module_tasks": {},
            "last_synced_at": {},
        }),
        encoding="utf-8",
    )
    create_node(wt, "n000_init", [], "Root", {"component_alpha": "Alpha"},
                "## Overview\nRoot\n", "bootstrap")
    set_head(wt, "n000_init")
    create_node(
        wt, SOURCE, ["n000_init"], "Source", dict(DIMS), PROPOSAL,
        "explore_001", reference_files=["src/a.py"], module_label=module,
    )
    set_head(wt, SOURCE, module=module or UMBRELLA_SUBGRAPH)


def _graph_state(wt: Path) -> dict:
    return yaml.safe_load((wt / GRAPH_STATE_FILE).read_text(encoding="utf-8"))


def _groups(wt: Path) -> dict:
    path = wt / GROUPS_FILE
    if not path.is_file():
        return {}
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("groups", {})


# --------------------------------------------------------------------------
# strip_dimension_tags
# --------------------------------------------------------------------------


class StripDimensionTagsTests(unittest.TestCase):
    def test_drops_pruned_exact_keeps_glob_and_kept(self):
        out = strip_dimension_tags(PROPOSAL, {"component_alpha", "tradeoff_speed"})
        self.assertIn(
            "<!-- section: decisions [dimensions: component_alpha, tradeoff_speed] -->",
            out,
        )
        self.assertIn("<!-- section: overview [dimensions: requirements_*] -->", out)
        self.assertIn("<!-- section: components [dimensions: component_*] -->", out)

    def test_all_pruned_marker_becomes_untagged_and_prose_is_kept(self):
        out = strip_dimension_tags(PROPOSAL, {"component_alpha"})
        self.assertIn("<!-- section: component_beta -->", out)
        self.assertIn("Beta prose.", out)
        self.assertIn("<!-- /section: component_beta -->", out)

    def test_unchanged_lines_are_byte_identical(self):
        out = strip_dimension_tags(PROPOSAL, {"component_alpha"})
        before, after = PROPOSAL.split("\n"), out.split("\n")
        self.assertEqual(len(before), len(after))
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        # Only the two open markers carrying a pruned exact tag change.
        self.assertEqual(
            [before[i].split("[")[0] for i in changed],
            ["<!-- section: component_beta ", "<!-- section: decisions "],
        )

    def test_keeping_everything_is_identity(self):
        self.assertEqual(strip_dimension_tags(PROPOSAL, DIMS.keys()), PROPOSAL)

    def test_result_validates_against_kept_keys(self):
        kept = {"component_alpha", "requirements_core"}
        out = strip_dimension_tags(PROPOSAL, kept)
        self.assertEqual(validate_sections(parse_sections(out), node_keys=list(kept)), [])

    def test_text_around_marker_is_preserved(self):
        line = "  <!-- section: x [dimensions: component_a, component_b] --> tail"
        self.assertEqual(
            strip_dimension_tags(line, {"component_b"}),
            "  <!-- section: x [dimensions: component_b] --> tail",
        )


# --------------------------------------------------------------------------
# rank_dimensions
# --------------------------------------------------------------------------


class RankDimensionsTests(unittest.TestCase):
    def test_signals(self):
        sig = dimension_rank_signals(DIMS, PROPOSAL, ["requirements_extra"])
        # component_alpha: exact tag in its leaf section and in decisions.
        self.assertEqual(sig["component_alpha"][0], 2)
        # Glob tags do not count toward any one key.
        self.assertEqual(sig["requirements_core"][0], 0)
        # Whole-token mentions: component_alpha_ext does not count for
        # component_alpha, and marker lines are not prose.
        self.assertEqual(sig["component_alpha"][1], 1)
        self.assertEqual(sig["component_alpha_ext"][1], 1)
        self.assertEqual(sig["tradeoff_speed"][1], 1)
        self.assertEqual(sig["requirements_extra"][2], 1)
        self.assertEqual(sig["tradeoff_cost"], (0, 0, 0))

    def test_order_tags_then_mentions_then_active_then_node_order(self):
        ranked = rank_dimensions(DIMS, PROPOSAL, ["requirements_extra"])
        self.assertEqual(ranked, [
            "component_alpha",       # (2, 1, 0)
            "tradeoff_speed",        # (1, 1, 0)
            "component_beta",        # (1, 0, 0)
            "assumption_cache",      # (1, 0, 0) — node order after beta
            "requirements_core",     # (0, 1, 0)
            "component_alpha_ext",   # (0, 1, 0) — node order
            "requirements_extra",    # (0, 0, 1)
            "tradeoff_cost",         # (0, 0, 0)
        ])

    def test_prefix_plays_no_part(self):
        # A tagged tradeoff outranks every untagged requirement, so the top N
        # can leave a kind with no keys at all.
        ranked = rank_dimensions(DIMS, PROPOSAL, [])
        top3 = ranked[:3]
        self.assertIn("tradeoff_speed", top3)
        self.assertFalse(any(k.startswith("requirements_") for k in top3))

    def test_empty_proposal_keeps_node_order(self):
        self.assertEqual(rank_dimensions(DIMS, "", []), list(DIMS))


class ParsePruneLabelTests(unittest.TestCase):
    def test_strips_rank_prefix(self):
        self.assertEqual(_parse_prune_label("3. component_x — value"), "component_x")

    def test_value_with_dash_and_digits(self):
        self.assertEqual(
            _parse_prune_label("12. tradeoff_y — 2. costs — 40 ms"), "tradeoff_y"
        )

    def test_unprefixed_label(self):
        self.assertEqual(_parse_prune_label("component_z — v"), "component_z")


# --------------------------------------------------------------------------
# apply_prune_dimensions / run_prune_operation
# --------------------------------------------------------------------------


class _SessionCase(unittest.TestCase):
    MODULE: str | None = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="brainstorm_prune_")
        self.wt = Path(self.tmp)
        _seed_session(self.wt, active=["component_alpha", "tradeoff_cost"],
                      module=self.MODULE)
        self._patch = patch.object(bs, "crew_worktree", return_value=self.wt)
        self._patch.start()
        self.src_yaml = (self.wt / NODES_DIR / f"{SOURCE}.yaml").read_bytes()
        self.src_md = (self.wt / PROPOSALS_DIR / f"{SOURCE}.md").read_bytes()
        self.subgraph = self.MODULE or UMBRELLA_SUBGRAPH

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _record(self, group="prune_dimensions_001"):
        record_operation("1", group, "prune_dimensions", agents=[],
                         head_at_creation=SOURCE, subgraph=self.subgraph)
        return group

    def _assert_source_untouched(self):
        self.assertEqual(
            (self.wt / NODES_DIR / f"{SOURCE}.yaml").read_bytes(), self.src_yaml
        )
        self.assertEqual(
            (self.wt / PROPOSALS_DIR / f"{SOURCE}.md").read_bytes(), self.src_md
        )

    def _node_files(self):
        return sorted(p.name for p in (self.wt / NODES_DIR).iterdir())


class ApplyPruneTests(_SessionCase):
    KEPT = ["component_alpha", "requirements_core", "tradeoff_speed"]

    def test_child_has_kept_keys_tags_rewritten_and_head_moves(self):
        group = self._record()
        new_id = apply_prune_dimensions("1", group, SOURCE, self.KEPT)
        self.assertEqual(new_id, "n002_prune_dimensions_001")
        self._assert_source_untouched()

        child = read_node(self.wt, new_id)
        self.assertEqual(set(extract_dimensions(child)), set(self.KEPT))
        self.assertEqual(child["parents"], [SOURCE])
        self.assertEqual(child["reference_files"], ["src/a.py"])
        self.assertEqual(child["created_by_group"], group)
        for field in ("node_id", "description", "proposal_file", "created_at"):
            self.assertIn(field, child)

        text = (self.wt / PROPOSALS_DIR / f"{new_id}.md").read_text(encoding="utf-8")
        self.assertEqual(
            validate_sections(parse_sections(text),
                              node_keys=list(extract_dimensions(child))),
            [],
        )
        self.assertIn("Beta prose.", text)
        self.assertIn("<!-- section: component_beta -->", text)

        self.assertEqual(get_head(self.wt, module=self.subgraph), new_id)
        grp = _groups(self.wt)[group]
        self.assertEqual(grp["status"], "Completed")
        self.assertEqual(grp["nodes_created"], [new_id])
        self.assertEqual(
            _graph_state(self.wt)["active_dimensions"],
            ["component_alpha", "tradeoff_cost"],
        )

    def test_refusals_write_nothing(self):
        group = self._record()
        before_nodes = self._node_files()
        before_counter = _graph_state(self.wt)["next_node_id"]
        cases = [
            [],                                  # empty kept
            ["component_alpha", "component_nope"],  # unknown key
            list(DIMS),                          # nothing to prune
        ]
        for kept in cases:
            with self.subTest(kept=kept):
                with self.assertRaises(PruneRefused):
                    apply_prune_dimensions("1", group, SOURCE, kept)
                self.assertEqual(self._node_files(), before_nodes)
                self.assertEqual(_graph_state(self.wt)["next_node_id"], before_counter)
                self.assertEqual(get_head(self.wt, module=self.subgraph), SOURCE)
        self._assert_source_untouched()

    def test_missing_source_proposal_is_refused_before_any_write(self):
        group = self._record()
        (self.wt / PROPOSALS_DIR / f"{SOURCE}.md").unlink()
        before_nodes = self._node_files()
        before_counter = _graph_state(self.wt)["next_node_id"]
        with self.assertRaises(PruneRefused) as ctx:
            apply_prune_dimensions("1", group, SOURCE, self.KEPT)
        self.assertIsInstance(ctx.exception, ValueError)
        self.assertIn("source proposal missing", str(ctx.exception))
        self.assertEqual(self._node_files(), before_nodes)
        self.assertEqual(
            sorted(p.name for p in (self.wt / PROPOSALS_DIR).iterdir()),
            ["n000_init.md"],
        )
        self.assertEqual(get_head(self.wt, module=self.subgraph), SOURCE)
        self.assertEqual(_graph_state(self.wt)["next_node_id"], before_counter)
        self.assertNotEqual(_groups(self.wt)[group]["status"], "Completed")

    def test_existing_empty_source_proposal_is_pruned(self):
        group = self._record()
        (self.wt / PROPOSALS_DIR / f"{SOURCE}.md").write_text("", encoding="utf-8")
        new_id = apply_prune_dimensions("1", group, SOURCE, self.KEPT)
        self.assertEqual(
            (self.wt / PROPOSALS_DIR / f"{new_id}.md").read_text(encoding="utf-8"), ""
        )
        self.assertEqual(get_head(self.wt, module=self.subgraph), new_id)


class ApplyPruneModuleTests(_SessionCase):
    """Inside a module subgraph the child joins it and moves only its HEAD."""

    MODULE = "auth"
    KEPT = ApplyPruneTests.KEPT

    def test_child_joins_the_module(self):
        group = self._record()
        new_id = apply_prune_dimensions("1", group, SOURCE, self.KEPT)
        self._assert_source_untouched()
        self.assertEqual(read_node(self.wt, new_id).get("module_label"), "auth")
        self.assertEqual(get_head(self.wt, module="auth"), new_id)
        self.assertEqual(get_head(self.wt), "n000_init")

    def test_refusal_leaves_the_module_head(self):
        group = self._record()
        (self.wt / PROPOSALS_DIR / f"{SOURCE}.md").unlink()
        with self.assertRaises(PruneRefused):
            apply_prune_dimensions("1", group, SOURCE, self.KEPT)
        self.assertEqual(get_head(self.wt, module="auth"), SOURCE)


class RunPruneFailureBoundaryTests(_SessionCase):
    """Only a refusal before any write deletes the operation record.

    Negative control (not shipped code): a variant of ``run_prune_operation``
    that called ``delete_group`` on *every* exception would fail the "record
    survives" assertions in the two fault-injection tests below.
    """

    KEPT = ["component_alpha", "tradeoff_speed"]

    def _run(self):
        return run_prune_operation(
            "1", "prune_dimensions_001", source_node=SOURCE, kept=self.KEPT,
            head_at_creation=SOURCE, subgraph=UMBRELLA_SUBGRAPH,
            mode="top_n", top_n=2, kept_count=2,
            pruned_dimensions=[k for k in DIMS if k not in self.KEPT],
        )

    def test_success_records_extras(self):
        new_id = self._run()
        grp = _groups(self.wt)["prune_dimensions_001"]
        self.assertEqual(grp["operation"], "prune_dimensions")
        self.assertEqual(grp["agents"], [])
        self.assertEqual(grp["source_node"], SOURCE)
        self.assertEqual(grp["status"], "Completed")
        self.assertEqual(grp["nodes_created"], [new_id])
        self.assertEqual(len(grp["pruned_dimensions"]), len(DIMS) - 2)

    def test_refusal_before_mutation_deletes_record(self):
        (self.wt / PROPOSALS_DIR / f"{SOURCE}.md").unlink()
        before_nodes = self._node_files()
        before_counter = _graph_state(self.wt)["next_node_id"]
        with self.assertRaises(PruneRefused):
            self._run()
        self.assertNotIn("prune_dimensions_001", _groups(self.wt))
        self.assertEqual(self._node_files(), before_nodes)
        self.assertEqual(_graph_state(self.wt)["next_node_id"], before_counter)
        self.assertEqual(get_head(self.wt), SOURCE)

    def _assert_refused_without_trace(self):
        before_nodes = self._node_files()
        before_counter = _graph_state(self.wt)["next_node_id"]
        with self.assertRaises(PruneRefused) as ctx:
            self._run()
        self.assertNotIn("prune_dimensions_001", _groups(self.wt))
        self.assertEqual(self._node_files(), before_nodes)
        self.assertEqual(_graph_state(self.wt)["next_node_id"], before_counter)
        self.assertEqual(get_head(self.wt), SOURCE)
        return ctx.exception

    def test_undecodable_source_proposal_is_refused_and_record_removed(self):
        (self.wt / PROPOSALS_DIR / f"{SOURCE}.md").write_bytes(b"# P\n\xff\xfe bad\n")
        exc = self._assert_refused_without_trace()
        self.assertIn("source proposal unreadable", str(exc))

    def test_undecodable_source_node_is_refused_and_record_removed(self):
        (self.wt / NODES_DIR / f"{SOURCE}.yaml").write_bytes(b"node_id: \xff\xfe\n")
        exc = self._assert_refused_without_trace()
        self.assertIn("unreadable", str(exc))

    def test_unanticipated_preflight_failure_is_a_refusal(self):
        # Any failure before the first write leaves the session untouched, so
        # it must not leave an agent-less record stuck in Waiting.
        with patch.object(bs, "strip_dimension_tags",
                          side_effect=RuntimeError("parser bug")):
            exc = self._assert_refused_without_trace()
        self.assertIn("prune preflight failed: RuntimeError", str(exc))

    def test_fault_after_child_creation_keeps_record(self):
        def boom(*a, **kw):
            raise OSError("disk full")

        with patch.object(bs, "set_head", side_effect=boom):
            with self.assertRaises(PrunePartialFailure) as ctx:
                self._run()
        exc = ctx.exception
        self.assertEqual(exc.stage, "node_created")
        self.assertEqual(exc.new_node_id, "n002_prune_dimensions_001")
        grp = _groups(self.wt).get("prune_dimensions_001")
        self.assertIsNotNone(grp, "operation record must survive a partial failure")
        self.assertEqual(grp["status"], "Error")
        self.assertIn("node_created", grp["error"])
        self.assertEqual(grp["nodes_created"], ["n002_prune_dimensions_001"])
        # No rollback: the child exists, HEAD still points at the source.
        self.assertTrue((self.wt / NODES_DIR / "n002_prune_dimensions_001.yaml").is_file())
        self.assertEqual(get_head(self.wt), SOURCE)
        self._assert_source_untouched()

    def test_fault_after_head_move_keeps_record(self):
        real = bs.update_operation

        def flaky(task_num, group_name, **fields):
            if fields.get("status") == "Completed":
                raise OSError("write failed")
            return real(task_num, group_name, **fields)

        with patch.object(bs, "update_operation", side_effect=flaky):
            with self.assertRaises(PrunePartialFailure) as ctx:
                self._run()
        self.assertEqual(ctx.exception.stage, "head_moved")
        self.assertEqual(get_head(self.wt), "n002_prune_dimensions_001")
        grp = _groups(self.wt).get("prune_dimensions_001")
        self.assertIsNotNone(grp, "operation record must survive a partial failure")
        self.assertEqual(grp["status"], "Error")
        self.assertIn("head_moved", grp["error"])


# --------------------------------------------------------------------------
# Explorer input filter
# --------------------------------------------------------------------------


class ExplorerActiveDimensionsFilterTests(unittest.TestCase):
    def test_keys_absent_from_baseline_are_not_offered(self):
        tmp = tempfile.mkdtemp(prefix="brainstorm_prune_explorer_")
        try:
            wt = Path(tmp)
            _seed_session(wt)
            out = _assemble_input_explorer(
                wt, SOURCE, "Explore",
                ["component_alpha", "component_gone", "legacy_name"],
                "n009_explorer_009",
            )
            block = out.split("## Active Dimensions", 1)[1].split("\n")[1]
            self.assertEqual(block, "component_alpha, legacy_name")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# Wizard config step (pilot)
# --------------------------------------------------------------------------


class _PruneHost(App):
    task_num = "1"

    def __init__(self, session_path: Path) -> None:
        super().__init__()
        self.session_path = session_path
        self.read_only = False

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            ActionsWizardScreen(op_key="prune_dimensions", node_id=SOURCE, marked=[])
        )


class PruneWizardTests(unittest.TestCase):
    DEFAULT_N = len(DIMS) - 1  # min(40, T - 1)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="brainstorm_prune_wiz_")
        self.wt = Path(self.tmp)
        _seed_session(self.wt, active=["requirements_extra"])
        self.ranked = rank_dimensions(DIMS, PROPOSAL, ["requirements_extra"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def _settle(self, pilot, n=4):
        for _ in range(n):
            await pilot.pause()

    @staticmethod
    def _rows(screen):
        return list(screen.query("Checkbox.chk_prune_dim"))

    @classmethod
    def _checked(cls, screen):
        return {_parse_prune_label(str(cb.label)) for cb in cls._rows(screen) if cb.value}

    @staticmethod
    def _set_row(screen, key, value):
        for cb in screen.query("Checkbox.chk_prune_dim"):
            if _parse_prune_label(str(cb.label)) == key:
                cb.value = value
                return
        raise AssertionError(f"no row for {key}")

    def _run(self, body):
        async def runner():
            app = _PruneHost(self.wt)
            async with app.run_test(size=(160, 60)) as pilot:
                await self._settle(pilot)
                screen = app.screen
                self.assertIsInstance(screen, ActionsWizardScreen)
                self.assertEqual(screen._wizard_step_id, "config")
                await body(pilot, screen)
        asyncio.run(runner())

    def test_flat_ranked_list_and_default_top_n(self):
        async def body(pilot, screen):
            rows = self._rows(screen)
            self.assertEqual(
                [_parse_prune_label(str(cb.label)) for cb in rows], self.ranked
            )
            self.assertTrue(str(rows[0].label).startswith("1. "))
            # One flat group: a single subheader.
            self.assertEqual(len(list(screen.query(".fcl_subheader"))), 1)
            self.assertEqual(self._checked(screen), set(self.ranked[:self.DEFAULT_N]))
            self.assertEqual(screen.query_one("#prune_top_n", Input).value,
                             str(self.DEFAULT_N))

        self._run(body)

    def test_changing_n_rechecks_and_keep_selected_keeps_toggles(self):
        async def body(pilot, screen):
            screen.query_one("#prune_top_n", Input).value = "3"
            await self._settle(pilot)
            self.assertEqual(self._checked(screen), set(self.ranked[:3]))

            rs = screen.query_one(".rs_prune_mode", RadioSet)
            list(rs.query(RadioButton))[1].value = True
            await self._settle(pilot)
            self.assertEqual(screen._prune_mode, "selected")
            self._set_row(screen, self.ranked[6], True)
            await self._settle(pilot)
            # Changing N in "Keep selected" mode does not re-check.
            screen.query_one("#prune_top_n", Input).value = "2"
            await self._settle(pilot)
            self.assertEqual(
                self._checked(screen), set(self.ranked[:3]) | {self.ranked[6]}
            )

            self.assertTrue(screen._actions_collect_config())
            cfg = screen._wizard_config
            self.assertEqual(cfg["kept"], self.ranked[:3] + [self.ranked[6]])
            self.assertEqual(
                cfg["dropped"], [k for k in self.ranked if k not in cfg["kept"]]
            )
            self.assertEqual(cfg["mode"], "selected")
            self.assertEqual(cfg["source_node"], SOURCE)

        self._run(body)

    def test_n_change_under_filter_keeps_checked_rows_visible(self):
        async def body(pilot, screen):
            from brainstorm.widgets import FuzzyCheckList
            screen.query_one("#prune_top_n", Input).value = "1"
            await self._settle(pilot)
            fcl = screen.query_one("#prune_dims", FuzzyCheckList)
            fcl.query_one(Input).value = "zzz_matches_nothing"
            await self._settle(pilot)
            visible = {_parse_prune_label(str(cb.label))
                       for cb in self._rows(screen) if cb.display}
            self.assertEqual(visible, {self.ranked[0]})

            screen.query_one("#prune_top_n", Input).value = "3"
            await self._settle(pilot)
            self.assertEqual(self._checked(screen), set(self.ranked[:3]))
            visible = {_parse_prune_label(str(cb.label))
                       for cb in self._rows(screen) if cb.display}
            self.assertEqual(visible, set(self.ranked[:3]))

            # Shrinking N unchecks rows; non-matching unchecked rows hide again.
            screen.query_one("#prune_top_n", Input).value = "2"
            await self._settle(pilot)
            visible = {_parse_prune_label(str(cb.label))
                       for cb in self._rows(screen) if cb.display}
            self.assertEqual(visible, set(self.ranked[:2]))

        self._run(body)

    def test_confirm_then_back_restores_edited_state(self):
        async def body(pilot, screen):
            screen.query_one("#prune_top_n", Input).value = "4"
            await self._settle(pilot)
            rs = screen.query_one(".rs_prune_mode", RadioSet)
            list(rs.query(RadioButton))[1].value = True
            await self._settle(pilot)
            self._set_row(screen, self.ranked[0], False)   # one off inside N
            self._set_row(screen, self.ranked[5], True)    # one on below N
            await self._settle(pilot)
            expected = (set(self.ranked[:4]) - {self.ranked[0]}) | {self.ranked[5]}
            self.assertEqual(self._checked(screen), expected)

            screen._on_actions_next()
            await self._settle(pilot)
            self.assertEqual(screen._wizard_step_id, "confirm")
            screen._on_actions_back()
            await self._settle(pilot)

            self.assertEqual(screen._wizard_step_id, "config")
            self.assertEqual(screen._prune_mode, "selected")
            rs = screen.query_one(".rs_prune_mode", RadioSet)
            self.assertEqual(rs.pressed_index, 1)
            self.assertEqual(screen.query_one("#prune_top_n", Input).value, "4")
            self.assertEqual(self._checked(screen), expected)
            counts = str(screen.query_one("#prune_counts", Label).render())
            self.assertIn(f"Keeping {len(expected)} of {len(DIMS)}", counts)

        self._run(body)

    def test_confirm_then_back_with_defaults_keeps_defaults(self):
        async def body(pilot, screen):
            screen._on_actions_next()
            await self._settle(pilot)
            self.assertEqual(screen._wizard_step_id, "confirm")
            screen._on_actions_back()
            await self._settle(pilot)
            self.assertEqual(screen._prune_mode, "top_n")
            self.assertEqual(screen.query_one("#prune_top_n", Input).value,
                             str(self.DEFAULT_N))
            self.assertEqual(self._checked(screen), set(self.ranked[:self.DEFAULT_N]))

        self._run(body)

    def test_different_source_resets_to_its_defaults(self):
        async def body(pilot, screen):
            screen.query_one("#prune_top_n", Input).value = "2"
            await self._settle(pilot)
            screen._on_actions_next()
            await self._settle(pilot)
            # Re-enter config for another node (as node-select would): the
            # collected state belongs to SOURCE and must not leak.
            screen._wizard_config["_selected_node"] = "n000_init"
            screen._actions_show_config()
            await self._settle(pilot)
            self.assertEqual(screen._prune_source, "n000_init")
            self.assertEqual(screen._prune_mode, "top_n")
            # n000_init has one dimension -> default N clamps to 1.
            self.assertEqual(screen.query_one("#prune_top_n", Input).value, "1")
            self.assertEqual(self._checked(screen), {"component_alpha"})

        self._run(body)

    def test_confirm_summary_and_no_launch_mode(self):
        async def body(pilot, screen):
            screen.query_one("#prune_top_n", Input).value = "3"
            await self._settle(pilot)
            screen._on_actions_next()
            await self._settle(pilot)
            summary = "\n".join(screen._build_summary())
            self.assertIn("Keep top 3 overall", summary)
            self.assertIn(f"Keeping:[/] 3 of {len(DIMS)}", summary)
            self.assertIn("Per kind:", summary)
            self.assertNotIn("Launch mode", summary)
            self.assertFalse(list(screen.query("#launch-mode-field")))

        self._run(body)


if __name__ == "__main__":
    unittest.main()
