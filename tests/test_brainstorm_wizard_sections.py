"""Tests for brainstorm wizard section-selection helpers.

Covers the pure-logic helpers introduced for the section-selection wizard step
(t571_4): `_sections_intersection`, `_parse_section_label`, and the app-level
`_node_sections` / `_node_has_sections` methods.

Pilot-driven end-to-end wizard tests are intentionally NOT included here; the
full in-TUI checklist lives in aitasks/t571/t571_7_manual_verification_*.md.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import (  # noqa: E402
    _parse_section_label,
    _sections_intersection,
)


class SectionsIntersectionTests(unittest.TestCase):
    def test_empty_mapping_returns_empty(self):
        self.assertEqual(_sections_intersection({}), [])

    def test_single_node_returns_its_sections(self):
        self.assertEqual(
            _sections_intersection({"alpha": ["auth", "storage"]}),
            ["auth", "storage"],
        )

    def test_two_node_intersection_drops_unique(self):
        self.assertEqual(
            _sections_intersection({
                "alpha": ["auth", "storage", "telemetry"],
                "beta":  ["auth", "storage"],
            }),
            ["auth", "storage"],
        )

    def test_three_node_intersection_keeps_only_shared(self):
        self.assertEqual(
            _sections_intersection({
                "alpha": ["auth", "storage", "telemetry"],
                "beta":  ["auth", "storage"],
                "gamma": ["auth", "ui"],
            }),
            ["auth"],
        )

    def test_disjoint_nodes_return_empty(self):
        self.assertEqual(
            _sections_intersection({"a": ["x"], "b": ["y"]}),
            [],
        )

    def test_node_with_no_sections_collapses_intersection(self):
        self.assertEqual(
            _sections_intersection({"a": ["auth"], "b": []}),
            [],
        )

    def test_result_is_sorted(self):
        # When all nodes share the same sections, result is sorted alphabetically.
        self.assertEqual(
            _sections_intersection({
                "a": ["zeta", "alpha", "mu"],
                "b": ["mu", "zeta", "alpha"],
            }),
            ["alpha", "mu", "zeta"],
        )


class ParseSectionLabelTests(unittest.TestCase):
    def test_bare_name_is_returned_as_is(self):
        self.assertEqual(_parse_section_label("auth"), "auth")

    def test_strips_dim_suffix(self):
        self.assertEqual(
            _parse_section_label("auth [dim][component_auth][/]"),
            "auth",
        )

    def test_strips_any_trailing_content_after_first_space(self):
        # The suffix could be other rich markup — still stripped.
        self.assertEqual(_parse_section_label("storage  [foo]"), "storage")


class NodeSectionsTests(unittest.TestCase):
    """Exercise `_node_sections` / `_node_has_sections` on a temp session."""

    PROPOSAL_WITH_SECTIONS = """\
# Proposal

<!-- section: auth [dimensions: component_auth] -->
Use JWT.
<!-- /section: auth -->

<!-- section: storage -->
Postgres.
<!-- /section: storage -->
"""

    PLAN_WITH_SECTIONS = """\
# Plan

<!-- section: auth [dimensions: component_auth] -->
Adopt OAuth.
<!-- /section: auth -->

<!-- section: storage -->
Redis cache in front.
<!-- /section: storage -->
"""

    PROPOSAL_NO_SECTIONS = "# Proposal\n\nNo markers here.\n"

    def setUp(self):
        # Isolate from host state: patch AGENTCREW_DIR to a temp path.
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_wizard_sections_")
        import agentcrew.agentcrew_utils as ac_mod
        import brainstorm.brainstorm_session as bs_mod

        self._orig_agentcrew_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "agentcrew")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR

        self.task_num = "999"
        self.wt_path = Path(ac_mod.AGENTCREW_DIR) / f"crew-brainstorm-{self.task_num}"
        self.wt_path.mkdir(parents=True)
        (self.wt_path / "br_proposals").mkdir()
        (self.wt_path / "br_plans").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        import agentcrew.agentcrew_utils as ac_mod
        import brainstorm.brainstorm_session as bs_mod
        ac_mod.AGENTCREW_DIR = self._orig_agentcrew_dir
        bs_mod.AGENTCREW_DIR = self._orig_agentcrew_dir

    def _write_proposal(self, node_id: str, content: str) -> None:
        (self.wt_path / "br_proposals" / f"{node_id}.md").write_text(content, encoding="utf-8")

    def _write_plan(self, node_id: str, content: str) -> None:
        (self.wt_path / "br_plans" / f"{node_id}_plan.md").write_text(content, encoding="utf-8")

    def _make_app(self):
        from brainstorm.brainstorm_app import BrainstormApp
        app = BrainstormApp.__new__(BrainstormApp)
        # Bypass __init__ — it touches a lot of session infrastructure. For
        # these helpers we only need `session_path`.
        app.session_path = self.wt_path
        return app

    def test_plan_preferred_over_proposal(self):
        self._write_proposal("n1", self.PROPOSAL_NO_SECTIONS)
        self._write_plan("n1", self.PLAN_WITH_SECTIONS)
        app = self._make_app()
        sections = app._node_sections("n1")
        self.assertEqual([s.name for s in sections], ["auth", "storage"])

    def test_falls_back_to_proposal_when_plan_missing(self):
        self._write_proposal("n1", self.PROPOSAL_WITH_SECTIONS)
        app = self._make_app()
        sections = app._node_sections("n1")
        self.assertEqual([s.name for s in sections], ["auth", "storage"])

    def test_returns_empty_when_neither_has_sections(self):
        self._write_proposal("n1", self.PROPOSAL_NO_SECTIONS)
        app = self._make_app()
        self.assertEqual(app._node_sections("n1"), [])

    def test_has_sections_true_when_any_present(self):
        self._write_plan("n1", self.PLAN_WITH_SECTIONS)
        app = self._make_app()
        self.assertTrue(app._node_has_sections("n1"))

    def test_has_sections_false_on_plain_text(self):
        self._write_proposal("n1", self.PROPOSAL_NO_SECTIONS)
        app = self._make_app()
        self.assertFalse(app._node_has_sections("n1"))

    def test_has_sections_false_when_node_missing(self):
        app = self._make_app()
        self.assertFalse(app._node_has_sections("nonexistent"))


if __name__ == "__main__":
    unittest.main()
