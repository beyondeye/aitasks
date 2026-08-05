"""Characterization of the work-report column surface (t1377_1 pre-phase).

**Why this file exists.** t1377_1 moves `DEFAULT_COLUMNS` / `DEFAULT_ORDER` /
`UNORDERED_ID` / `UNORDERED_TITLE` out of `lib/work_report_gather.py` into a new
`lib/board_columns.py`, and rewires `work_report_gather.load_columns()` into a
delegate. That function sits on a **fail-closed protocol path** consumed by
`/aitask-work-report`: callers parse its `COLUMN:` lines and branch on its exit
status. A de-dup that merely *compiles* is not good enough — the observable
contract has to be byte-identical afterwards.

So this suite pins the CLI's behaviour **before** the extraction and must stay
green after it, unedited. It deliberately drives the real
`aitask_work_report_gather.sh` as a subprocess rather than importing the module:
the exit code and the stderr prefix are only observable at that boundary, and the
boundary is what the report protocol actually depends on.

What is pinned:

* the exact `COLUMN:<id>|<title>` line shape and board ordering;
* that the synthetic `unordered` row is prepended **only** when a task sits
  there (it is not a configured column, so it cannot come from `column_order`);
* exit status **3** (`EXIT_INFRA`) on a column id carrying `|`, CR or LF;
* the literal `work_report_gather:` stderr message prefix.

The last one has a **negative control** (`test_prefix_assertion_discriminates`).
Without it, the prefix assertion would pass vacuously if the extracted module
started emitting its own `board_columns:` prefix through a differently-named
helper — which is precisely the regression the extraction could introduce.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

import board_fixture as bf  # noqa: E402

GATHER_SH = REPO_ROOT / ".aitask-scripts" / "aitask_work_report_gather.sh"

#: `EXIT_INFRA` in lib/work_report_gather.py — the fail-closed status the report
#: protocol distinguishes from a usage error (2) and success (0).
EXIT_INFRA = 3

#: Mirrors lib/work_report_gather.py `_RECORD_BREAKING`. Kept as an independent
#: literal on purpose: importing the module's own tuple would make this suite
#: agree with whatever the module does rather than with the protocol contract.
RECORD_BREAKING = ("|", "\r", "\n")


class _GatherCase(unittest.TestCase):
    """Builds a fixture tree and runs the gatherer CLI inside it."""

    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="ait-wr-columns-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.tree = bf.build_fixture_tree(root, self.topology())

    def topology(self):
        return bf.DEFAULT_TOPOLOGY

    def run_gather(self, *args):
        """Run the gatherer with cwd inside the fixture tree.

        `TASK_DIR` is explicitly cleared rather than merely left alone: the
        gatherer resolves its metadata path through `config_utils.task_dir()`,
        which honours the env var, so an ambient value from the developer's
        shell would silently redirect the run out of the fixture.
        """
        env = {k: v for k, v in __import__("os").environ.items()
               if k != "TASK_DIR"}
        return subprocess.run(
            [str(GATHER_SH), *args],
            cwd=str(self.tree), env=env,
            capture_output=True, text=True,
        )

    def column_lines(self, *args):
        proc = self.run_gather("--list-columns", *args)
        self.assertEqual(proc.returncode, 0,
                         f"--list-columns should succeed; stderr={proc.stderr!r}")
        return [ln for ln in proc.stdout.splitlines() if ln.startswith("COLUMN:")]

    def write_board_config(self, columns, order):
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        path.write_text(
            json.dumps({"columns": columns, "column_order": order}, indent=2) + "\n",
            encoding="utf-8")


class ListColumnsFormatTests(_GatherCase):
    """The `COLUMN:<id>|<title>` protocol line and its ordering."""

    def test_lines_are_the_configured_columns_in_board_order(self):
        self.assertEqual(
            self.column_lines(),
            [f"COLUMN:{c['id']}|{c['title']}" for c in bf.COLUMNS],
        )

    def test_ordering_follows_column_order_not_the_columns_list(self):
        """`column_order` is the ordering authority, not the definition list."""
        reversed_order = list(reversed(bf.COLUMN_ORDER))
        self.write_board_config(bf.COLUMNS, reversed_order)
        self.assertEqual(
            [ln.split("|", 1)[0] for ln in self.column_lines()],
            [f"COLUMN:{cid}" for cid in reversed_order],
        )

    def test_column_order_entry_without_a_definition_is_dropped(self):
        self.write_board_config(bf.COLUMNS, bf.COLUMN_ORDER + ["ghost"])
        self.assertNotIn("COLUMN:ghost|ghost", self.column_lines())

    def test_title_defaults_to_the_id_when_absent(self):
        self.write_board_config([{"id": "solo"}], ["solo"])
        self.assertEqual(self.column_lines(), ["COLUMN:solo|solo"])


class UnorderedEmptyTests(_GatherCase):
    """`unordered` is synthetic: absent while no task sits in it."""

    def test_absent_when_no_task_is_unordered(self):
        self.assertNotIn(
            "COLUMN:unordered|Unsorted / Inbox",
            self.column_lines(),
            "unordered is not a configured column; it must not be listed empty",
        )


class UnorderedPopulatedTests(_GatherCase):
    """...and present, first, as soon as one does.

    Deliberately a sibling of `UnorderedEmptyTests` rather than a subclass:
    subclassing would silently re-run the base's tests under a second name, and
    overriding one with the opposite assertion makes the suite unreadable.
    """

    def topology(self):
        return bf.DEFAULT_TOPOLOGY + (
            bf.FixtureTask(task_id="9005", col="unordered", idx=10, slug="loose"),
        )

    def test_present_when_a_task_is_unordered(self):
        self.assertIn("COLUMN:unordered|Unsorted / Inbox", self.column_lines())

    def test_unordered_is_prepended_before_every_configured_column(self):
        self.assertEqual(self.column_lines()[0],
                         "COLUMN:unordered|Unsorted / Inbox")


class RecordBreakingIdTests(_GatherCase):
    """A column id that cannot round-trip the protocol is fatal, not silent."""

    def _run_with_id(self, col_id):
        self.write_board_config([{"id": col_id, "title": "Bad"}], [col_id])
        return self.run_gather("--list-columns")

    def test_each_record_breaking_character_exits_infra(self):
        for ch in RECORD_BREAKING:
            with self.subTest(char=repr(ch)):
                proc = self._run_with_id(f"ba{ch}d")
                self.assertEqual(proc.returncode, EXIT_INFRA)
                self.assertEqual(
                    [ln for ln in proc.stdout.splitlines()
                     if ln.startswith("COLUMN:")], [],
                    "a fatal id must not emit a partial column listing")

    def test_message_carries_the_work_report_gather_prefix(self):
        proc = self._run_with_id("ba|d")
        self.assertTrue(
            proc.stderr.startswith("work_report_gather: "),
            f"stderr must keep its module prefix; got {proc.stderr!r}")

    def test_prefix_assertion_discriminates(self):
        """Negative control for the assertion above.

        If the extraction let the new module's own `_die` (or any renamed
        helper) own this message, the prefix would change. Asserting only
        `startswith("work_report_gather: ")` cannot by itself prove the check is
        live — so pin the *absence* of the plausible replacement too. A run in
        which BOTH assertions hold is the only passing state.
        """
        proc = self._run_with_id("ba|d")
        self.assertNotIn("board_columns:", proc.stderr)
        self.assertNotEqual(proc.stderr.strip(), "")

    def test_a_valid_id_is_not_rejected(self):
        """Positive control: the fatal path is reached by bad ids only."""
        proc = self._run_with_id("fine_id")
        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr!r}")


if __name__ == "__main__":
    unittest.main()
