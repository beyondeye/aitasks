"""The sitrep TUI's trail membership and trail picker (t2211_10).

* ``membership_from_export`` (pure): ownership by ``project.name``, waves, the
  fail-closed states -- a failed blob or a partial scan keeps the positive
  evidence and turns "in no trail" into "unknown", never "none";
* ``scan_membership``: never raises; and once end to end, over a real fixture
  repository whose two trails are stored with the real artifact CLI (the
  ``tests/test_trail_links.py`` end-to-end helpers);
* ``TrailPickerDialog``: a click only selects, Enter returns the row's handle,
  Esc returns None, and the list fits a short pane.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_sitrep_tui_trails.py -q
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (REPO_ROOT / "tests", REPO_ROOT / ".aitask-scripts",
           REPO_ROOT / ".aitask-scripts" / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from textual.app import App  # noqa: E402
from textual.widgets import OptionList  # noqa: E402

from sitrep_tui import sitrep_tui_trails as tt  # noqa: E402

A, B, C = "art:trail-a", "art:trail-b", "art:trail-c"


def _trail(handle, members, waves=None, name=None, load_error=""):
    return {"handle": handle, "name": name or handle.upper(), "members": members,
            "waves": waves or {}, "load_error": load_error}


def _data(trails, local="aitasks", **extra):
    return {"format": 1, "local_project": local, "unreadable": [], "scan_errors": [],
            "trails": trails, "tasks": {}, **extra}


class MembershipTests(unittest.TestCase):

    def test_zero_one_and_two_trails(self):
        m = tt.membership_from_export(_data([
            _trail(A, ["aitasks#1", "aitasks#2"], {"aitasks#1": [1], "aitasks#2": [2]},
                   name="Alpha"),
            _trail(B, ["aitasks#2"], {"aitasks#2": [1]}, name="Beta"),
        ]), [])
        self.assertTrue(m.ok)
        self.assertEqual(m.lookup("3"), tt.TaskTrails(tt.NONE))
        one = m.lookup("1")
        self.assertEqual(one.state, tt.IN)
        self.assertEqual(one.trails, (tt.TrailRef(A, "Alpha", (1,)),))
        two = m.lookup("2")
        self.assertEqual(two.handles(), (A, B))
        self.assertEqual(two.reason, "")

    def test_child_ids_t_spelling_and_foreign_refs(self):
        m = tt.membership_from_export(_data([
            _trail(A, ["aitasks#t2211_3", "other#5", "garbage", "aitasks#5"],
                   {"aitasks#t2211_3": [2, 1]}),
        ]), [])
        self.assertEqual(m.lookup("2211_3").trails[0].waves, (1, 2))
        self.assertEqual(m.lookup("5").state, tt.IN)       # aitasks#5, not other#5
        self.assertEqual(m.lookup("2211").state, tt.NONE)

    def test_labels(self):
        ref = tt.TrailRef("art:trail-sitrep-followups", "Sitrep follow-ups", (1,))
        self.assertEqual(ref.label(), "In trail: Sitrep follow-ups "
                                      "(art:trail-sitrep-followups) — wave 1")
        self.assertEqual(ref.short(), "Sitrep follow-ups (w1)")
        two = tt.TrailRef(A, "Alpha", (1, 3))
        self.assertTrue(two.label().endswith("— waves 1, 3"))
        self.assertEqual(tt.TrailRef(A, "Alpha").label(), f"In trail: Alpha ({A})")
        self.assertEqual(tt.TrailRef(A, "Alpha").short(), "Alpha")

    def test_a_failed_blob_keeps_positive_evidence_and_never_says_none(self):
        m = tt.membership_from_export(_data([
            _trail(A, ["aitasks#1"]),
            _trail(B, [], load_error="manifest unreadable"),
        ]), [SimpleNamespace(kind="partial", detail="unloadable trail(s): art:trail-b")])
        known = m.lookup("1")
        self.assertEqual(known.state, tt.IN)
        self.assertIn(B, known.reason)
        unlisted = m.lookup("2")
        self.assertEqual(unlisted.state, tt.UNKNOWN)
        self.assertIn(B, unlisted.reason)

    def test_unreadable_task_files_make_it_partial(self):
        m = tt.membership_from_export(_data([_trail(A, ["aitasks#1"])],
                                            unreadable=["t9_x.md"]), [])
        self.assertEqual(m.lookup("1").state, tt.IN)
        self.assertEqual(m.lookup("2").state, tt.UNKNOWN)

    def test_an_export_failure_is_unknown_for_every_task(self):
        m = tt.membership_from_export(None, [SimpleNamespace(
            kind="timeout", detail="export exceeded 30s")])
        self.assertFalse(m.ok)
        for task in ("1", "2"):
            got = m.lookup(task)
            self.assertEqual(got.state, tt.UNKNOWN)
            self.assertIn("exceeded", got.reason)

    def test_no_project_name_is_unknown(self):
        m = tt.membership_from_export(_data([_trail(A, ["aitasks#1"])], local=""), [])
        got = m.lookup("1")
        self.assertEqual(got.state, tt.UNKNOWN)
        self.assertIn("project.name", got.reason)

    def test_malformed_rows_are_skipped(self):
        m = tt.membership_from_export(_data([
            "junk", {"handle": 5}, _trail(A, ["aitasks#1"], {"aitasks#1": ["x", True, 2]}),
        ]), [])
        self.assertEqual(m.lookup("1").trails[0].waves, (2,))

    def test_scan_membership_never_raises(self):
        import trail_links
        with patch.object(trail_links, "export_project", side_effect=OSError("boom")):
            m = tt.scan_membership("/nowhere")
        self.assertFalse(m.ok)
        self.assertEqual(m.lookup("1").state, tt.UNKNOWN)
        self.assertIn("boom", m.lookup("1").reason)


import test_trail_links as _tle  # noqa: E402


class EndToEndTests(unittest.TestCase):
    """The real export subprocess over a real fixture repo with two trails
    stored by the real artifact CLI (the trail_links end-to-end helpers)."""

    NAME = "t2211tui"
    # Borrowed through __dict__ so staticmethods stay static.
    _E = _tle.EndToEndTests.__dict__
    setUp = _E["setUp"]
    _restore_env = _E["_restore_env"]
    _git = _E["_git"]
    _repo = _E["_repo"]
    _task = _E["_task"]
    _store_trail = _E["_store_trail"]
    X_PROJECT = _tle.EndToEndTests.X_PROJECT

    def test_a_task_in_two_trails(self):
        y = self._repo("y", self.NAME)
        for tid in ("5", "7"):
            self._task(y, tid)
        self._store_trail(y, "5", f"{self.NAME}#5",
                          [f"{self.NAME}#5", f"{self.NAME}#7"], "art:fixa-trail")
        # `_store_trail` commits the task tree first; give it a change to commit.
        self._task(y, "9")
        self._store_trail(y, "7", f"{self.NAME}#7",
                          [f"{self.NAME}#7", "other#3"], "art:fixb-trail")
        import trail_links
        export, errors = trail_links.export_project(str(y))
        self.assertEqual(errors, [])
        by_handle = {t["handle"]: t for t in export.data["trails"]}
        self.assertEqual(by_handle["art:fixa-trail"]["waves"],
                         {f"{self.NAME}#5": [1], f"{self.NAME}#7": [1]})
        m = tt.scan_membership(str(y))
        self.assertTrue(m.ok, m.reason)
        self.assertEqual(m.lookup("5").handles(), ("art:fixa-trail",))
        self.assertEqual(sorted(m.lookup("7").handles()),
                         ["art:fixa-trail", "art:fixb-trail"])
        self.assertEqual(m.lookup("7").trails[0].waves, (1,))
        self.assertEqual(m.lookup("9").state, tt.NONE)


class _PickerApp(App):
    def __init__(self, trails):
        super().__init__()
        self.trails = trails
        self.result = "unset"

    def on_mount(self):
        self.push_screen(tt.TrailPickerDialog("12", self.trails), self._done)

    def _done(self, value):
        self.result = value


class PickerTests(unittest.TestCase):
    TRAILS = (tt.TrailRef(A, "Alpha", (1,)), tt.TrailRef(B, "Beta", (2,)),
              tt.TrailRef(C, "Gamma"))

    def _run(self, body, size=(100, 30)):
        async def go():
            app = _PickerApp(self.TRAILS)
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                await body(app, pilot)
                await pilot.pause()
            return app
        return asyncio.run(go())

    def test_rows_enter_returns_the_highlighted_handle(self):
        async def body(app, pilot):
            lst = app.screen.query_one("#tp-list", OptionList)
            self.assertEqual([lst.get_option_at_index(i).id
                              for i in range(lst.option_count)],
                             [f"trail:{A}", f"trail:{B}", f"trail:{C}"])
            self.assertEqual(lst.highlighted, 0)
            await pilot.press("down")
            await pilot.press("enter")
        self.assertEqual(self._run(body).result, B)

    def test_a_click_only_selects(self):
        async def body(app, pilot):
            lst = app.screen.query_one("#tp-list", OptionList)
            await pilot.click("#tp-list", offset=(4, 3))
            await pilot.pause()
            self.assertIsInstance(app.screen, tt.TrailPickerDialog)
            self.assertEqual(lst.highlighted, 2)
            await pilot.press("enter")
        self.assertEqual(self._run(body).result, C)

    def test_escape_and_cancel_return_none(self):
        async def esc(app, pilot):
            await pilot.press("escape")
        self.assertIsNone(self._run(esc).result)

        async def cancel(app, pilot):
            await pilot.click("#tp-cancel")
        self.assertIsNone(self._run(cancel).result)

    def test_the_list_and_button_fit_a_short_pane(self):
        # LabelFilterDialog's sizes; 9 rows is the smallest that fits at all.
        for height in (10, 12, 16, 30):
            with self.subTest(height=height):
                async def body(app, pilot, height=height):
                    lst = app.screen.query_one("#tp-list", OptionList)
                    button = app.screen.query_one("#tp-cancel")
                    self.assertLessEqual(lst.region.bottom, button.region.y)
                    self.assertLessEqual(button.region.bottom, height)
                    await pilot.click("#tp-cancel")
                self.assertIsNone(self._run(body, size=(80, height)).result)


if __name__ == "__main__":
    unittest.main()
