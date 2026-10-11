"""``resolve_editor_argv`` — the $EDITOR → argv rule shared by board and codebrowser (t1943)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import editor_argv  # noqa: E402
from editor_argv import resolve_editor_argv  # noqa: E402


def _resolve(value, platform=None):
    env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
    if value is not None:
        env["EDITOR"] = value
    with patch.dict(os.environ, env, clear=True), \
            patch.object(editor_argv.sys, "platform", platform or sys.platform):
        return resolve_editor_argv()


@unittest.skipIf(sys.platform == "win32", "POSIX shlex branch")
class ResolveEditorArgvTests(unittest.TestCase):
    def test_unset_defaults_to_nano(self):
        self.assertEqual(_resolve(None), ["nano"])

    def test_blank_defaults_to_nano(self):
        self.assertEqual(_resolve("  \t "), ["nano"])

    def test_arguments_are_split(self):
        self.assertEqual(_resolve("emacsclient -t"), ["emacsclient", "-t"])

    def test_quoted_path_with_arguments(self):
        self.assertEqual(_resolve("'/opt/my editor/bin/ed' --wait"),
                         ["/opt/my editor/bin/ed", "--wait"])

    def test_whole_executable_with_spaces_is_one_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            editor = Path(tmp) / "my editor" / "ed"
            editor.parent.mkdir()
            editor.write_text("#!/bin/sh\nexit 0\n")
            editor.chmod(0o755)
            self.assertEqual(_resolve(str(editor)), [str(editor)])

    def test_malformed_raises_with_the_value_named(self):
        with self.assertRaises(ValueError) as ctx:
            _resolve('vim "unterminated')
        self.assertTrue(str(ctx.exception).startswith(
            "Invalid $EDITOR 'vim \"unterminated': "))


class WindowsBranchTests(unittest.TestCase):
    def test_windows_defaults_to_notepad(self):
        self.assertEqual(_resolve(None, "win32"), ["notepad"])

    def test_windows_keeps_one_argv(self):
        value = r"C:\Program Files\Editor\ed.exe -w"
        self.assertEqual(_resolve(value, "win32"), [value])


if __name__ == "__main__":
    unittest.main(verbosity=2)
