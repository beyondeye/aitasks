"""task_commit.py - commit task / plan files from Python (t1702).

Thin wrapper over ``.aitask-scripts/aitask_task_commit.sh``, shaped exactly like
its sibling ``metadata_commit.py``. It is a wrapper and not a reimplementation
for the same reason: the scoped-commit rules (``commit -o -- <paths>``, which
takes worktree content and bypasses the shared index; branch-mode vs legacy
routing; staging only untracked paths and unstaging exactly those on failure)
live once, in shell, in ``lib/task_utils.sh``.

The three board sites this replaces — ``_do_delete``, ``_do_rename_task``,
``_do_git_commit_tasks`` — each ran a pathspec-less ``git commit`` against the
shared ``.aitask-data`` index, publishing whatever a concurrent session had
staged under the board's own message.

Callers are TUI event handlers, so this NEVER raises on a git failure: the files
have already been written (or deleted) on disk, and losing that to a commit error
would be worse than a dirty tree. The failure is returned, and every caller is
required to surface it with the remedy command (see
`aidocs/framework/tui_conventions.md`).
"""
from __future__ import annotations

import shlex
import subprocess
from collections import namedtuple
from pathlib import Path

#: status: committed | nochange | skipped | refused | failed
CommitResult = namedtuple("CommitResult", "status subject detail")

_SCRIPT = Path(".aitask-scripts") / "aitask_task_commit.sh"

DEFAULT_TIMEOUT_SECONDS = 15


def commit_command(message, paths, *, root=None):
    """Build the argv/cwd for a commit invocation.

    Pure resolution seam (no subprocess) so targeting is unit-testable without
    live git, mirroring ``metadata_commit.commit_command``.
    """
    if root is None:
        argv = [str(Path(".") / _SCRIPT)]
        cwd = None
    else:
        argv = [str(Path(root) / _SCRIPT)]
        cwd = str(root)
    argv += ["-m", str(message), "--"]
    argv.extend(str(p) for p in paths)
    return argv, cwd


def remedy_command(message, paths) -> str:
    """The exact command a user can run to clear a failed commit.

    Every surface's error message must carry this, so the advice a user sees is
    the same one `ait sync`'s ownerless report gives them.

    Built through `commit_command` rather than assembled separately, so the
    advertised command cannot drift from the one actually run, and quoted with
    `shlex` because the message is free text a user typed into the commit dialog.
    """
    argv, _ = commit_command(message, paths)
    return " ".join(shlex.quote(a) for a in argv)


def commit_task_paths(
    message,
    paths,
    *,
    root=None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CommitResult:
    """Commit task / plan paths through the shell seam.

    `paths` must be repo-relative and under ``aitasks/`` or ``aiplans/``; the
    helper refuses anything else. A path that is neither tracked nor on disk is
    skipped rather than aborting the commit.

    **Name every path the operation wrote**, not only the ones it deleted — a
    write left out of the pathspec becomes an ownerless dirty file that blocks
    task-data sync.

    Never raises on a git failure. Raises ValueError on an empty path list or an
    empty message, both of which are programmer errors: an empty pathspec is
    exactly what makes ``git commit`` commit the whole shared index.
    """
    paths = [str(p) for p in paths]
    if not paths:
        raise ValueError("commit_task_paths requires at least one path")
    if not str(message).strip():
        raise ValueError("commit_task_paths requires a non-empty message")

    argv, cwd = commit_command(message, paths, root=root)
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return CommitResult("failed", None, f"timed out after {timeout}s")
    except (FileNotFoundError, PermissionError) as exc:
        return CommitResult("failed", None, f"cannot run {argv[0]}: {exc}")

    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    # The terminal line is the verdict; SKIPPED lines may precede it.
    last = lines[-1] if lines else ""

    if last.startswith("COMMITTED:"):
        # COMMITTED:<n>:<subject> — the subject may itself contain ':'.
        _, _, rest = last.partition(":")
        _, _, subject = rest.partition(":")
        return CommitResult("committed", subject, None)
    if last == "NOCHANGE":
        # Report `skipped` when a SKIPPED line explains why, so a caller can tell
        # "nothing to do" from "none of those paths were ours to commit".
        if any(ln.startswith("SKIPPED:") for ln in lines):
            return CommitResult("skipped", None, lines[0])
        return CommitResult("nochange", None, None)
    if last.startswith("SKIPPED:"):
        return CommitResult("skipped", None, last)
    if last.startswith("REFUSED:"):
        return CommitResult("refused", None, last)
    if last.startswith("FAILED:"):
        return CommitResult("failed", None, last.partition(":")[2])

    detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
    return CommitResult("failed", None, detail)
