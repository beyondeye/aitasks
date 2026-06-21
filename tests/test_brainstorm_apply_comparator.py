"""Tests for the comparator completion lifecycle (t1020).

A Compare operation produces analysis output only (no node), so it lacks the
explorer/synthesizer apply path that flips ``br_groups.yaml`` group status
``Waiting`` → ``Completed``. Before t1020 a finished comparator left its group
stuck at ``Waiting``, producing the contradictory "100% + Waiting" Status
screen and giving the comparison ``_output.md`` no in-TUI path.

Engine coverage (no App):
- ``apply_comparator_output`` flips the owning compare group to ``Completed``
  and returns the group name (the core AC #1 fix).
- ``_comparator_needs_apply`` is the restart-safe idempotency signal: True
  before apply, False after.
- group resolution: an unknown agent yields no group → ``apply_comparator_output``
  raises a clear ``ValueError``.

App coverage (bare app — the AC #3 output-access path):
- ``_open_group_operation`` pushes ``OperationDetailScreen`` for a group with a
  completed agent, and is gated (notify, no push) for a Waiting group — keeping
  the action consistent with the rendered ``o: open output`` hint.
"""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_session import (  # noqa: E402
    GROUPS_FILE,
    _comparator_needs_apply,
    _read_groups_file,
    apply_comparator_output,
    record_operation,
)

TASK_NUM = "42"
AGENT = "comparator_001"
GROUP = "compare_001"


def _group_status(wt: Path, group_name: str = GROUP) -> str:
    groups = _read_groups_file(str(wt / GROUPS_FILE)).get("groups", {})
    return groups.get(group_name, {}).get("status", "")


def _seed_compare_group(wt: Path, agent_status: str = "Completed") -> None:
    """Record a Waiting compare group and lay down the comparator's status +
    output files as a finished comparator would on disk."""
    with patch(
        "brainstorm.brainstorm_session.crew_worktree", return_value=wt,
    ):
        record_operation(
            TASK_NUM, GROUP, "compare", [AGENT], head_at_creation="n000_init",
        )
    # The comparator writes free-form analysis to _output.md (no NODE_YAML).
    (wt / f"{AGENT}_output.md").write_text(
        "## Comparison matrix\n| dim | nA | nB |\n", encoding="utf-8",
    )
    (wt / f"{AGENT}_status.yaml").write_text(
        f"status: {agent_status}\nprogress: 100\n", encoding="utf-8",
    )


def _apply(wt: Path, agent_name: str = AGENT):
    with patch(
        "brainstorm.brainstorm_session.crew_worktree", return_value=wt,
    ):
        return apply_comparator_output(TASK_NUM, agent_name)


def _needs_apply(wt: Path, agent_name: str = AGENT) -> bool:
    with patch(
        "brainstorm.brainstorm_session.crew_worktree", return_value=wt,
    ):
        return _comparator_needs_apply(TASK_NUM, agent_name)


class ApplyComparatorEngineTests(unittest.TestCase):
    def test_record_operation_starts_waiting(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_compare_group(wt)
            self.assertEqual(_group_status(wt), "Waiting")

    def test_apply_flips_group_to_completed(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_compare_group(wt)
            self.assertEqual(_group_status(wt), "Waiting")

            group = _apply(wt)

            self.assertEqual(group, GROUP)
            self.assertEqual(_group_status(wt), "Completed")

    def test_needs_apply_true_before_false_after(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_compare_group(wt)
            self.assertTrue(_needs_apply(wt))

            _apply(wt)

            # Restart-safe idempotency: a finalized group never re-applies.
            self.assertFalse(_needs_apply(wt))

    def test_needs_apply_false_when_group_absent(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            # No record_operation → no group on disk.
            self.assertFalse(_needs_apply(wt))

    def test_apply_unknown_agent_raises(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_compare_group(wt)
            with self.assertRaises(ValueError):
                _apply(wt, agent_name="comparator_999")


# ---------------------------------------------------------------------------
# App-level: o-on-GroupRow output access (bare app — __init__ bypassed)
# ---------------------------------------------------------------------------

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    OperationDetailScreen,
)


def _bare_app(session_path="/tmp/x"):
    app = BrainstormApp.__new__(BrainstormApp)
    app.session_path = session_path
    app.pushed = []
    app.notices = []
    app.push_screen = lambda screen, *a, **k: app.pushed.append(screen)
    app.notify = lambda msg, **kw: app.notices.append((msg, kw))
    return app


def _stub_row(group_name=GROUP, has_completed_agent=True):
    return types.SimpleNamespace(
        group_name=group_name, has_completed_agent=has_completed_agent,
    )


class OpenGroupOperationTests(unittest.TestCase):
    def test_completed_group_pushes_operation_detail(self):
        app = _bare_app()
        app._open_group_operation(_stub_row(has_completed_agent=True))
        self.assertEqual(len(app.pushed), 1)
        self.assertIsInstance(app.pushed[0], OperationDetailScreen)
        self.assertEqual(app.pushed[0].group_name, GROUP)

    def test_waiting_group_is_gated_notify_no_push(self):
        app = _bare_app()
        app._open_group_operation(_stub_row(has_completed_agent=False))
        self.assertEqual(app.pushed, [])
        self.assertTrue(app.notices)


if __name__ == "__main__":
    unittest.main()
