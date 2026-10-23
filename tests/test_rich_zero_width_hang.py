"""Regression tests for the rich split_graphemes hang (t2133).

rich 14.3.2's ``rich.cells.split_graphemes`` loops forever when a zero-width
character (U+200E LEFT-TO-RIGHT MARK, U+FE0F, raw ESC, ...) comes before any
visible one, so every Textual surface that truncates such text freezes at 100%
CPU — observed in the minimonitor pick dialog on an RTL task body. rich 14.3.3
fixed it; ``aitask_setup.sh`` pins ``rich>=14.3.3``.

Each case runs in a child interpreter under a subprocess timeout, so a
regression is killed and FAILS instead of hanging the suite. The child is
``sys.executable`` — the suite interpreter, i.e. the framework venv the TUIs
run on — so a venv still holding a buggy rich fails here.

Run: python -m unittest tests.test_rich_zero_width_hang -v
"""

from __future__ import annotations

import subprocess
import sys
import unittest

LRM = "‎"

# Truncation entry points that hung on rich 14.3.2.
_CELLS_SCRIPT = f"""
from rich.cells import set_cell_size, split_graphemes
split_graphemes({LRM!r})
split_graphemes("\\ufe0f")
set_cell_size({LRM!r} + "____ are you going?", 4)
print("done")
"""

# The minimonitor TaskDetailDialog body shape: VerticalScroll(Markdown(...)) in
# a ~40-column pane. The LRM-prefixed cells must be long enough to need
# truncation in the narrowed table column — a short cell wraps without
# truncating and never reaches split_graphemes.
_MARKDOWN_SCRIPT = f"""
import asyncio
from textual.app import App
from textual.containers import VerticalScroll
from textual.widgets import Markdown

cell = {LRM!r} + "_" * 25 + " are you going?"
long = "verylongunbreakablewordhere"
body = (
    "| a | b | c | d | e |\\n|---|---|---|---|---|\\n"
    f"| {{long}} | {{long}} | {{long}} | x | y |\\n"
    f"| r19 | {{cell}} | {{cell}} | x | y |\\n"
)

class _App(App):
    def compose(self):
        yield VerticalScroll(Markdown(body))

async def _main():
    async with _App().run_test(size=(40, 30)) as pilot:
        await pilot.pause()
    print("done")

asyncio.run(_main())
"""


def _rich_version() -> str:
    try:
        from importlib.metadata import version
        return version("rich")
    except Exception:  # noqa: BLE001 - reporting only
        return "unknown"


class RichZeroWidthHangTests(unittest.TestCase):
    def _run_bounded(self, script: str, timeout: float) -> None:
        hint = (f"rich {_rich_version()} in {sys.executable} hangs on a leading "
                "zero-width character; the framework needs rich>=14.3.3 — run "
                "'ait setup' to upgrade the venv")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", script],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            self.fail(f"timed out after {timeout}s: {hint}")
        self.assertEqual(proc.returncode, 0, f"{hint}\nstderr:\n{proc.stderr}")
        self.assertIn("done", proc.stdout, hint)

    def test_cells_truncation_returns_on_leading_zero_width(self):
        self._run_bounded(_CELLS_SCRIPT, timeout=20)

    def test_markdown_table_with_lrm_cell_renders_at_40_columns(self):
        self._run_bounded(_MARKDOWN_SCRIPT, timeout=30)


if __name__ == "__main__":
    unittest.main()
