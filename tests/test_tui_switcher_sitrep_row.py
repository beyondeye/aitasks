"""The TUI switcher's Sitrep row (t2338).

Sitrep is not a `TUI_REGISTRY` entry (a registry row would make `spawn_tui` and
the applink router launch it in a stray `sitrep` window), so the switcher adds
the row itself and opens it through the `S` path — `action_shortcut_sitrep`,
the stamp-matching `ait sitrep open` — never `_switch_to`.

Pinned here:
- the row is listed, its dot follows `SITREP_WINDOW_RE` (near-misses do not
  count), and it is never current or disabled — not even under the standalone
  `ait sitrep tui`, whose `current_tui_name` is also `sitrep_tui`;
- `agent-sitrep*` windows stay listed under Code Agents as direct rows;
- activating the row dispatches the open for the SELECTED root and session,
  while normal rows and a plain window named `sitrep` still go to `_switch_to`;
- the row's key hint reads `(Shift+S)`, so it is not confused with Settings.

Run: python3 tests/test_tui_switcher_sitrep_row.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import tui_switcher as ts  # noqa: E402


def _populate(windows, *, current_tui="", attached="s1", session="s1"):
    """Run `_populate_list_for` over scripted windows; return (overlay, rows)."""
    overlay = ts.TuiSwitcherOverlay(session=session, current_tui=current_tui)
    overlay._attached_session = attached
    appended = []
    list_view = mock.MagicMock()
    list_view.append = appended.append
    overlay.query_one = lambda *a, **k: list_view
    with mock.patch.object(ts, "_session_windows", return_value=list(windows)), \
            mock.patch.object(ts, "_build_tui_list",
                              return_value=[("board", "Task Board", "ait board")]), \
            mock.patch.object(ts, "_discover_brainstorm_sessions", return_value=[]):
        overlay._populate_list_for(session)
    return overlay, appended


def _sitrep_row(rows):
    found = [r for r in rows
             if isinstance(r, ts._TuiListItem) and r.tui_name == ts._SITREP_ROW]
    assert len(found) == 1, f"expected one Sitrep row, got {len(found)}"
    return found[0]


def _window_rows(rows):
    return {r.window_name: r.window_id for r in rows
            if isinstance(r, ts._WindowListItem)}


class SitrepRowListingTests(unittest.TestCase):

    def test_the_row_is_listed_after_the_registry_rows(self):
        _ov, rows = _populate([])
        names = [r.tui_name for r in rows if isinstance(r, ts._TuiListItem)]
        self.assertEqual(names, ["board", ts._SITREP_ROW])
        self.assertEqual(_sitrep_row(rows).tui_label, "Sitrep")

    def test_the_dot_follows_the_sitrep_window_grammar(self):
        cases = {
            (): False,
            ("agent-sitrep",): True,
            ("agent-sitrep-3",): True,
            ("agent-sitrepx",): False,
            ("agent-pick-sitrep",): False,
            ("sitrep",): False,
        }
        for names, running in cases.items():
            with self.subTest(names=names):
                wins = [(f"@{i + 1}", str(i), n) for i, n in enumerate(names)]
                _ov, rows = _populate(wins)
                self.assertIs(_sitrep_row(rows).running, running)

    def test_the_standalone_sitrep_tui_does_not_make_the_row_current(self):
        # `ait sitrep tui` in a spare pane sets the same current_tui_name as
        # the TUI inside the real sitrep window: neither proves the row's
        # destination is where the user is.
        ov, rows = _populate([], current_tui="sitrep_tui")
        row = _sitrep_row(rows)
        self.assertFalse(row.is_current)
        self.assertFalse(row.disabled)
        dispatched = []
        ov.action_shortcut_sitrep = lambda: dispatched.append(True)
        ov._activate_item(row)
        self.assertEqual(dispatched, [True])

    def test_a_sole_sitrep_window_stays_a_direct_row(self):
        # A lone (e.g. frozen) agent-sitrep window: the launcher would skip it
        # and open a new window, so the switcher must not hide it.
        _ov, rows = _populate([("@4", "1", "agent-sitrep")])
        self.assertTrue(_sitrep_row(rows).running)
        self.assertEqual(_window_rows(rows), {"agent-sitrep": "@4"})

    def test_two_sitrep_windows_are_both_listed(self):
        _ov, rows = _populate([("@4", "1", "agent-sitrep"),
                               ("@6", "2", "agent-sitrep-2")])
        self.assertEqual(_window_rows(rows),
                         {"agent-sitrep": "@4", "agent-sitrep-2": "@6"})


class SitrepRowActivationTests(unittest.TestCase):

    def _overlay(self, windows):
        ov, rows = _populate(windows)
        switched = []
        ov._switch_to = lambda *a: switched.append(a)
        return ov, rows, switched

    def test_the_row_opens_the_selected_root_and_session(self):
        ov, rows, switched = self._overlay([])
        ov._selected_entry = lambda: None
        ov._selected_key = "other"
        ov._handle_stale_selection = lambda: False
        ov._ensure_session_live = lambda: True
        ov._selected_project_root = lambda: Path("/selected/repo")
        dismissed, sent = [], []
        ov.dismiss = lambda result=None: dismissed.append(result)
        ov._dispatch_sitrep_open = (
            lambda app, root, session: sent.append((app, root, session)))
        host = object()
        with mock.patch.object(ts.TuiSwitcherOverlay, "app",
                               new_callable=mock.PropertyMock, return_value=host):
            ov._activate_item(_sitrep_row(rows))
        self.assertEqual(sent, [(host, "/selected/repo", "other")])
        self.assertEqual(dismissed, [None])
        self.assertEqual(switched, [])

    def test_enter_and_click_share_the_route(self):
        ov, rows, _switched = self._overlay([])
        seen = []
        ov._activate_item = lambda item: seen.append(item)
        row = _sitrep_row(rows)
        list_view = mock.MagicMock()
        list_view.highlighted_child = row
        ov.query_one = lambda *a, **k: list_view
        ov.action_select_tui()
        ov.on_list_view_selected(mock.MagicMock(item=row))
        self.assertEqual(seen, [row, row])

    def test_a_normal_row_still_switches(self):
        ov, rows, switched = self._overlay([])
        ov.action_shortcut_sitrep = lambda: self.fail("routed to sitrep")
        board = next(r for r in rows
                     if isinstance(r, ts._TuiListItem) and r.tui_name == "board")
        ov._activate_item(board)
        self.assertEqual(switched, [("board", False)])

    def test_a_plain_window_named_sitrep_switches_by_its_id(self):
        ov, rows, switched = self._overlay([("@9", "3", "sitrep")])
        ov.action_shortcut_sitrep = lambda: self.fail("routed to sitrep")
        win = next(r for r in rows if isinstance(r, ts._WindowListItem))
        ov._activate_item(win)
        self.assertEqual(switched, [("sitrep", True, "@9")])

    def test_a_current_row_does_nothing(self):
        ov, _rows, switched = self._overlay([])
        current = ts._TuiListItem("board", "Task Board", True, True)
        ov._activate_item(current)
        self.assertEqual(switched, [])


class SitrepRowKeyHintTests(unittest.TestCase):

    def test_row_key_label_spells_shift(self):
        self.assertEqual(ts._row_key_label("S"), "Shift+S")
        self.assertEqual(ts._row_key_label("s"), "S")
        self.assertEqual(ts._row_key_label("ctrl+r"), "Ctrl+R")
        self.assertEqual(ts._row_key_label("["), "[")

    def test_the_sitrep_shortcut_is_the_S_quick_jump(self):
        self.assertEqual(ts._TUI_SHORTCUTS["sitrep"], "S")
        keys = {b.action: b.key for b in ts._QUICK_JUMP_BINDINGS}
        self.assertEqual(keys["shortcut_sitrep"], "S")

    def test_the_rows_read_differently_for_settings_and_sitrep(self):
        keys = {"settings": "s", "sitrep": "S"}
        with mock.patch.object(ts, "_resolve_tui_shortcut",
                               lambda name: keys.get(name)):
            texts = {}
            for name, label in (("settings", "Settings"), ("sitrep", "Sitrep")):
                static = next(iter(ts._TuiListItem(name, label, False, False).compose()))
                texts[name] = str(static.content)
        self.assertIn("(S)", texts["settings"])
        self.assertIn("(Shift+S)", texts["sitrep"])
        self.assertNotIn("(S)", texts["sitrep"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
