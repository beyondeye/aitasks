"""Structural contract of the GitHub contribution-check workflow (t2235).

GitHub silently drops labels supplied by issue authors without push access,
so the workflow must also run when a contribution issue is *opened* unlabeled,
keep unrelated events out of its concurrency group, and never interpolate the
issue body into a script. These are focused assertions on the shipped YAML;
actual GitHub scheduling is covered by live manual verification, not here.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / ".aitask-scripts" / "ci_templates" / "github" / "contribution-check.yml"
INSTALLED = REPO_ROOT / ".github" / "workflows" / "contribution-check.yml"
WORKFLOWS = (TEMPLATE, INSTALLED)

ELIGIBILITY_CLAUSES = (
    "github.event.action == 'labeled' && github.event.label.name == 'contribution'",
    "github.event.action == 'opened'",
    # The block header the check script parses, not the bare name: an ordinary
    # issue that merely mentions it must not be labeled a contribution.
    "contains(github.event.issue.body, '<!-- aitask-contribute-metadata')",
    "!contains(github.event.issue.labels.*.name, 'contribution')",
)


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _triggers(doc: dict) -> dict:
    # YAML 1.1 reads the bare key `on` as boolean True.
    return doc.get("on", doc.get(True))


def _job(doc: dict) -> dict:
    return doc["jobs"]["check-contribution"]


def _normalise(expr: str) -> str:
    return re.sub(r"\s+", " ", expr).strip()


class ContributionWorkflowContract(unittest.TestCase):
    def test_installed_copy_matches_template(self):
        self.assertEqual(TEMPLATE.read_bytes(), INSTALLED.read_bytes())

    def test_triggers_on_opened_and_labeled(self):
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                self.assertEqual(_triggers(_load(path))["issues"]["types"], ["opened", "labeled"])

    def test_concurrency_is_job_level(self):
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                doc = _load(path)
                self.assertNotIn("concurrency", doc, "workflow-level concurrency admits ineligible events")
                conc = _job(doc)["concurrency"]
                self.assertIn("github.event.issue.number", conc["group"])
                self.assertIs(conc["cancel-in-progress"], False)

    def test_job_condition_has_every_eligibility_clause(self):
        for path in WORKFLOWS:
            condition = _normalise(_job(_load(path))["if"])
            for clause in ELIGIBILITY_CLAUSES:
                with self.subTest(path=path.name, clause=clause):
                    self.assertIn(clause, condition)

    def test_label_step_runs_only_on_opened(self):
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                steps = _job(_load(path))["steps"]
                label_steps = [s for s in steps if "--add-label contribution" in s.get("run", "")]
                self.assertEqual(len(label_steps), 1)
                self.assertEqual(_normalise(label_steps[0]["if"]), "github.event.action == 'opened'")

    def test_issue_body_never_interpolated(self):
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"\$\{\{\s*github\.event\.issue\.body")
                for step in _job(_load(path))["steps"]:
                    self.assertNotIn("issue.body", step.get("run", ""))


if __name__ == "__main__":
    unittest.main()
