"""Resolve ``$EDITOR`` to an argv prefix for the TUIs' open-in-editor actions.

One rule shared by ``KanbanApp.run_editor`` (board) and
``CodeBrowserApp.action_open_in_editor`` (codebrowser), so the two cannot
drift. Only the argv resolution lives here: each caller keeps its own
suspend / notify containment, because what follows a launch differs.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys


def resolve_editor_argv() -> list[str]:
    """Return the argv prefix for the user's ``$EDITOR``.

    Unset or blank → ``nano`` (``notepad`` on Windows). A value that already
    names a whole executable (an unquoted path with spaces,
    ``/opt/my editor/bin/ed``) launches as one argv[0]; otherwise it is
    shlex-split so values carrying arguments (``code -w``) work. Windows always
    keeps one argv: POSIX shlex would also eat path backslashes.

    Raises ``ValueError`` — with a message naming the value, ready to show the
    user — when the value cannot be shlex-parsed (an unterminated quote).
    """
    default = "notepad" if sys.platform == "win32" else "nano"
    editor = os.environ.get("EDITOR", "").strip() or default
    if sys.platform == "win32" or shutil.which(editor):
        return [editor]
    try:
        return shlex.split(editor)
    except ValueError as exc:
        raise ValueError(f"Invalid $EDITOR {editor!r}: {exc}") from exc
