"""Unit tests for code_viewer control-character sanitization (t940).

Regression coverage for the codebrowser hang on captured-ANSI files: Rich's
line truncation (set_cell_size / split_graphemes) hangs on long lines that
embed raw control bytes such as ESC (0x1b). CodeViewer.load_file sanitizes
those bytes to printable "control picture" glyphs before highlighting.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))

from code_viewer import _sanitize_control_chars  # noqa: E402


class SanitizeControlCharsTests(unittest.TestCase):
    def test_esc_becomes_control_picture(self):
        # ESC (0x1b) -> U+241B ␛
        self.assertEqual(_sanitize_control_chars("\x1b"), "␛")

    def test_sgr_sequence_becomes_visible(self):
        self.assertEqual(
            _sanitize_control_chars("\x1b[48;2;40;42;54m"),
            "␛[48;2;40;42;54m",
        )

    def test_del_becomes_control_picture(self):
        # DEL (0x7f) -> U+2421 ␡
        self.assertEqual(_sanitize_control_chars("\x7f"), "␡")

    def test_tab_and_newline_preserved(self):
        self.assertEqual(_sanitize_control_chars("a\tb\nc"), "a\tb\nc")

    def test_plain_text_unchanged(self):
        text = "def foo(x):\n    return x + 1  # café ☕\n"
        self.assertEqual(_sanitize_control_chars(text), text)

    def test_other_c0_controls_converted(self):
        # NUL is normally caught as binary upstream, but the table still maps it.
        self.assertEqual(_sanitize_control_chars("\x00\x07\x1f"), "␀␇␟")


class RenderDoesNotHangTests(unittest.TestCase):
    """End-to-end: sanitized content renders through Rich without hanging.

    Mirrors footer.ansi line 24 — a long line mixing ESC sequences and text —
    which hangs Rich's truncation when fed raw. Guarded by SIGALRM so a hang
    fails loudly instead of stalling the suite; skipped where SIGALRM is
    unavailable (e.g. Windows).
    """

    def test_long_control_char_line_renders(self):
        import signal

        if not hasattr(signal, "SIGALRM"):
            self.skipTest("SIGALRM not available on this platform")

        from rich.console import Console
        from rich.syntax import Syntax
        from rich.table import Table
        from rich.text import Text

        # A long line (>120 cols) densely interleaving ESC sequences and text.
        raw = "--- capture ---\n" + (
            "\x1b[38;2;255;121;198m\x1b[48;2;49;52;66mq\x1b[39m\x1b[49m " * 12
        ) + "\n"
        content = _sanitize_control_chars(raw).expandtabs(4)
        self.assertNotIn("\x1b", content)

        lexer = Syntax.guess_lexer("footer.ansi", code=content)
        highlighted = Syntax(content, lexer, theme="monokai").highlight(content)
        lines = highlighted.split("\n")

        table = Table(show_header=False, show_edge=False, box=None, pad_edge=False)
        table.add_column(width=5, no_wrap=True)
        table.add_column(no_wrap=True, width=100)
        table.add_column(width=0, no_wrap=True)
        for i, line in enumerate(lines):
            table.add_row(Text(str(i + 1)), line, Text(""))

        console = Console(width=120, file=io.StringIO())

        def _timeout(signum, frame):
            raise TimeoutError("render hung on control-char content")

        old = signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(15)
        try:
            console.print(table)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)


if __name__ == "__main__":
    unittest.main()
