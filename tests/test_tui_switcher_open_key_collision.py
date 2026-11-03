"""The switcher's open/close toggle under a remapped key: dispatch and hint (t2180).

The open key (`shortcuts: shared: tui_switcher`) also closes the overlay, unless
it collides with a key the overlay already uses. In that case structural keys
and quick-jumps win, the toggle gets no close binding, and the hint advertises
only `Esc close`. One module constant, `_OVERLAY_TOGGLE_CLOSES`, decides both.

Both halves are built at **import**: `BINDINGS` is a class attribute, and the
key it binds comes from userconfig.yaml through `resolve_key` /
`register_app_bindings`. Patching a module constant at render time therefore
cannot exercise them. So every case here runs a **fresh interpreter** whose
`TASK_DIR` holds that case's `userconfig.yaml`, imports `tui_switcher` exactly
as a TUI does, mounts the real `TuiSwitcherOverlay` with Pilot and presses real
keys. Only the I/O seams are stubbed: session discovery, the desync line, the
TUI list, and the companion probe.

Why the cases are what they are:

* Open key `[` with two groups: `[` is bound with `priority=True` to
  prev_group, which consumes it whenever there is a group to move to. A close
  binding on `[` could never fire there, so the hint must not advertise one.
  Before t2180 the overlay could not even mount (MarkupError in the hint).
* Open key `[` in single mode: prev_group raises `SkipAction` and the key
  falls through, so an unreserved toggle WOULD close here. That is the case
  that proves `[` is reserved and not merely shadowed.
* Default config: `j` closes. This is the control that proves the harness can
  see a close, so the "still open" results above are not vacuous.
* Rebound quick-jump: the reserved set must hold the LIVE (override-applied)
  quick-jump keys, not their defaults.

Run: python3 tests/test_tui_switcher_open_key_collision.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"

#: Child program: import with the case's overrides in effect, mount, press keys,
#: report one JSON line. Stubs are installed on the module/class AFTER import —
#: they replace I/O seams only and never touch BINDINGS.
_CHILD = r"""
import asyncio, json, os, sys
from pathlib import Path

sys.path.insert(0, os.environ["CASE_LIB"])
import tui_switcher as ts
from agent_launch_utils import AitasksSession
from textual.app import App
from textual.content import Content

groups = json.loads(os.environ["CASE_GROUPS"])
keys = json.loads(os.environ["CASE_KEYS"])
root = Path(os.environ["CASE_ROOT"])
sessions = [
    AitasksSession(session=f"s{i + 1}", project_root=root / f"p{i + 1}",
                   project_name=f"p{i + 1}", project_group=group)
    for i, group in enumerate(groups)
]
switched = []
ts.discover_aitasks_sessions = lambda include_registered=True: list(sessions)
ts.TuiSwitcherOverlay._render_desync_line = lambda self, project_root: None
ts.TuiSwitcherOverlay._populate_list_for = lambda self, session: None
ts.TuiSwitcherOverlay._resolve_companion_target = lambda self: None
ts.TuiSwitcherOverlay._shortcut_switch = lambda self, name: switched.append(name)


class Host(App):
    def on_mount(self):
        self.push_screen(ts.TuiSwitcherOverlay(session="s1"))


out = {
    "open_key": ts._OVERLAY_OPEN_KEY,
    "toggle_closes": getattr(ts, "_OVERLAY_TOGGLE_CLOSES", None),
    "steps": [],
}


async def main():
    app = Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        overlay = app.screen
        out["mounted"] = isinstance(overlay, ts.TuiSwitcherOverlay)
        if not out["mounted"]:
            return
        hint = overlay.query_one("#switcher_hint")
        out["hint"] = Content.from_markup(str(hint.content)).plain
        out["multi_mode"] = overlay._multi_mode
        out["initial_group"] = overlay._selected_group
        for key in keys:
            await pilot.press(key)
            await pilot.pause()
            out["steps"].append({
                "key": key,
                "open": app.screen is overlay,
                "group": overlay._selected_group,
            })


try:
    asyncio.run(main())
except BaseException as exc:  # a mount crash is a verdict, not a harness error
    out["error"] = f"{type(exc).__name__}: {exc}"
out["switched"] = switched
print(json.dumps(out))
"""


def _run_case(userconfig: str | None, groups: list[str], keys: list[str]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        task_dir = Path(tmp) / "aitasks"
        (task_dir / "metadata").mkdir(parents=True)
        if userconfig is not None:
            (task_dir / "metadata" / "userconfig.yaml").write_text(
                userconfig, encoding="utf-8"
            )
        env = {
            **os.environ,
            "TASK_DIR": str(task_dir),
            "CASE_LIB": str(LIB_DIR),
            "CASE_ROOT": tmp,
            "CASE_GROUPS": json.dumps(groups),
            "CASE_KEYS": json.dumps(keys),
        }
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        proc = subprocess.run(
            [sys.executable, "-c", _CHILD], cwd=tmp, env=env,
            capture_output=True, text=True, timeout=120,
        )
    lines = proc.stdout.strip().splitlines()
    if proc.returncode != 0 or not lines:
        raise AssertionError(
            f"child failed (exit {proc.returncode})\nstdout:\n{proc.stdout}"
            f"\nstderr:\n{proc.stderr}"
        )
    return json.loads(lines[-1])


OPEN_KEY_BRACKET = 'shortcuts:\n  shared:\n    tui_switcher: "["\n'
TWO_GROUPS = ["ga", "gb"]
ONE_SESSION = ["ga"]


class OpenKeyCollisionTests(unittest.TestCase):

    def assertMountedCleanly(self, result: dict) -> None:
        self.assertNotIn("error", result)
        self.assertTrue(result.get("mounted"), result)

    def test_bracket_open_key_with_two_groups_navigates_and_advertises_only_esc(self):
        result = _run_case(OPEN_KEY_BRACKET, TWO_GROUPS, ["[", "escape"])
        # Self-check: the override reached import, where BINDINGS is built.
        self.assertEqual(result["open_key"], "[")
        self.assertIs(result["toggle_closes"], False)
        self.assertMountedCleanly(result)
        self.assertTrue(result["multi_mode"])
        self.assertIn("[/] group", result["hint"])
        self.assertTrue(result["hint"].endswith("Esc close"), result["hint"])
        self.assertNotIn("[/Esc", result["hint"])
        bracket, escape = result["steps"]
        self.assertTrue(bracket["open"], "`[` must navigate groups, not close")
        self.assertNotEqual(bracket["group"], result["initial_group"])
        self.assertFalse(escape["open"], "Esc must still close")

    def test_bracket_open_key_in_single_mode_does_not_close(self):
        """prev_group skips here, so only the reservation stops a close."""
        result = _run_case(OPEN_KEY_BRACKET, ONE_SESSION, ["["])
        self.assertMountedCleanly(result)
        self.assertFalse(result["multi_mode"])
        self.assertTrue(result["hint"].endswith("Enter switch  Esc close"),
                        result["hint"])
        (bracket,) = result["steps"]
        self.assertTrue(bracket["open"])

    def test_control_default_open_key_closes_and_is_advertised(self):
        result = _run_case(None, TWO_GROUPS, ["[", "j"])
        self.assertEqual(result["open_key"], "j")
        self.assertIs(result["toggle_closes"], True)
        self.assertMountedCleanly(result)
        self.assertTrue(result["hint"].endswith("J/Esc close"), result["hint"])
        bracket, j = result["steps"]
        self.assertTrue(bracket["open"])
        self.assertNotEqual(bracket["group"], result["initial_group"])
        self.assertFalse(j["open"], "the harness must observe a close")


class LiveQuickJumpReservationTests(unittest.TestCase):
    """The reserved set holds the override-applied quick-jump keys."""

    def test_a_quick_jumps_vacated_default_key_is_free_for_the_toggle(self):
        config = (
            "shortcuts:\n"
            "  shared:\n    tui_switcher: b\n"
            "  shared.tui_switcher:\n    shortcut_board: k\n"
        )
        result = _run_case(config, ONE_SESSION, ["b"])
        self.assertIs(result["toggle_closes"], True)
        self.assertNotIn("error", result)
        self.assertTrue(result["hint"].endswith("B/Esc close"), result["hint"])
        (b,) = result["steps"]
        self.assertFalse(b["open"])
        self.assertEqual(result["switched"], [])

    def test_a_quick_jumps_live_key_is_reserved_from_the_toggle(self):
        config = (
            "shortcuts:\n"
            "  shared:\n    tui_switcher: k\n"
            "  shared.tui_switcher:\n    shortcut_board: k\n"
        )
        result = _run_case(config, ONE_SESSION, ["k"])
        self.assertIs(result["toggle_closes"], False)
        self.assertNotIn("error", result)
        self.assertTrue(result["hint"].endswith("Esc close"), result["hint"])
        self.assertNotIn("K/Esc", result["hint"])
        (k,) = result["steps"]
        self.assertTrue(k["open"])
        self.assertEqual(result["switched"], ["board"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
