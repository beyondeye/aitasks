"""The chatlink wizard's save commits its config AND completes the flow (t1677).

Two things `SummaryScreen._do_save` must do, and a regression that took both out
at once: t1677 added a commit to the end of the method and orphaned the two
statements that followed it -- ``btn_wiz_next`` becoming "Close", and
``_start_preflight()``. A successful save then committed the config but never
transitioned the wizard into its completed state, and because the preflight pane
is what renders ``_commit_hint()``, the commit outcome never reached the user
either. Both were unreachable code after a ``return``.

So this pins the **whole tail of the save**, in order:

    commit -> render -> clear error -> button label -> preflight

Order is load-bearing, not incidental: ``_start_preflight`` renders
``_commit_hint()``, which reports ``self._commit_result``. Starting preflight
before the commit is recorded shows the pre-t1677 "review & commit it yourself"
text after a successful commit.

`SummaryScreen` is a Textual widget, so it is instantiated with
``object.__new__`` and given the attributes the method actually reads. That
exercises the REAL method body -- the thing that broke -- rather than a copy of
it, without standing up an app for a flow-ordering assertion.

Run: python3 tests/test_chatlink_wizard_save_flow.py
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from chatlink import wizard  # noqa: E402
from metadata_commit import CommitResult  # noqa: E402


class _Button:
    def __init__(self):
        self.label = "Save"


class SaveFlow(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ait_chatlink_save_")
        self.addCleanup(self._tmp.cleanup)
        self.cfg = Path(self._tmp.name) / "chatlink_config.yaml"

        self.events: list[str] = []
        self.button = _Button()

        seams = SimpleNamespace(
            config_path=self.cfg,
            token_writer=lambda tok: None,
            token_reader=lambda: None,
        )
        s = object.__new__(wizard.SummaryScreen)
        # The wizard's OWN state builder, so this fixture cannot drift from the
        # key set `build_edits` reads (it names every key explicitly).
        s.state = wizard.initial_state(seams)
        s.state["token"] = ""
        s.seams = seams
        s._config_written = False
        s._token_written = False
        s._allow_replace = False
        s._commit_result = None
        s._config_was_tracked = False

        # Seams. Each records its call so ORDER is assertable, which is the
        # property the regression violated.
        s.query_one = lambda sel, cls=None: self.button
        s._render_save_state = lambda **kw: self.events.append("render")
        s._error = lambda msg: self.events.append(f"error({msg!r})")
        s._start_preflight = lambda: self.events.append("preflight")
        s._commit_config = self._fake_commit
        self.screen = s

    def _fake_commit(self):
        self.events.append("commit")
        return CommitResult("committed", "ait: Update chatlink_config.yaml", None)

    def _run_save(self):
        # config_write is exercised for real: the save must actually write.
        wizard.SummaryScreen._do_save(self.screen)

    # --- the regression ---------------------------------------------------

    def test_a_successful_save_completes_the_flow(self):
        self._run_save()
        self.assertEqual(self.button.label, "Close",
                         "the Next button must become Close after a save")
        self.assertIn("preflight", self.events,
                      "_start_preflight must run after a successful save")

    def test_the_tail_runs_in_order_commit_before_preflight(self):
        self._run_save()
        self.assertEqual(
            self.events,
            ["commit", "render", "error('')", "preflight"],
            "the commit must be recorded BEFORE preflight renders _commit_hint()",
        )

    def test_the_commit_result_is_recorded_for_the_hint(self):
        self._run_save()
        self.assertEqual(self.screen._commit_result.status, "committed")

    def test_the_config_is_actually_written(self):
        self._run_save()
        self.assertTrue(self.cfg.is_file())
        self.assertTrue(self.screen._config_written)

    # --- the hint reports what happened -----------------------------------

    def test_the_hint_reports_a_successful_commit(self):
        self.screen._commit_result = CommitResult(
            "committed", "ait: Update chatlink_config.yaml", None)
        hint = wizard.SummaryScreen._commit_hint(self.screen)
        self.assertIn("committed", hint)
        self.assertIn("ait: Update chatlink_config.yaml", hint)

    def test_the_hint_degrades_to_a_remedy_on_failure(self):
        """A failed commit must never be silent -- it names the command."""
        self.screen._commit_result = CommitResult("failed", None, "hook refused")
        hint = wizard.SummaryScreen._commit_hint(self.screen)
        self.assertIn("NOT committed", hint)
        self.assertIn("aitask_metadata_commit.sh", hint)

    def test_the_hint_is_the_legacy_instruction_before_any_save(self):
        hint = wizard.SummaryScreen._commit_hint(self.screen)
        self.assertIn("./ait git add", hint)


if __name__ == "__main__":
    unittest.main(verbosity=2)
