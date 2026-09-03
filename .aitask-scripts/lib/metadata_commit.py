"""metadata_commit.py - commit shared `aitasks/metadata` files from Python (t1677).

Thin wrapper over ``.aitask-scripts/aitask_metadata_commit.sh``. It is a wrapper
and not a reimplementation on purpose: the scoped-commit rules
(``commit -o -- <paths>``, which takes worktree content and bypasses the shared
index; branch-mode vs legacy routing; staging only untracked paths and unstaging
exactly those on failure) live once, in shell, in
``lib/task_utils.sh::task_git_commit_scoped`` and its caller. Every pre-existing
Python commit site in this tree — ``settings_app._commit_profile``,
``aitask_board._do_git_commit_tasks`` — is a pathspec-less ``git commit``, i.e.
the index-wide swallow t1599 exists to eliminate. Copying one of those was the
alternative; wrapping the shell seam is the fix.

Callers are TUI event handlers, so this NEVER raises on a git failure: the
config edit has already landed on disk, and losing it to a commit error would be
worse than a dirty file. The failure is returned, and every caller is required to
surface it with the remedy command (see `aidocs/framework/tui_conventions.md`).
"""
from __future__ import annotations

import subprocess
from collections import namedtuple
from pathlib import Path

#: status: committed | nochange | skipped | refused | failed
#:
#: `allow_new` carries the admission this invocation actually used, so a caller
#: rendering the remedy cannot advertise a command weaker than the one that
#: failed. It rides on the RESULT rather than being threaded as a second
#: argument through every notify callback for the same reason the commit lives
#: inside the writer: a parameter each surface has to remember to pass is one a
#: surface eventually forgets.
CommitResult = namedtuple(
    "CommitResult", "status subject detail allow_new", defaults=(False,)
)

_SCRIPT = Path(".aitask-scripts") / "aitask_metadata_commit.sh"

DEFAULT_TIMEOUT_SECONDS = 15


def commit_command(paths, *, allow_new: bool = False, root=None):
    """Build the argv/cwd for a commit invocation.

    Pure resolution seam (no subprocess) so targeting is unit-testable without
    live git, mirroring ``sync_action_runner.sync_batch_command``.
    """
    if root is None:
        argv = [str(Path(".") / _SCRIPT)]
        cwd = None
    else:
        argv = [str(Path(root) / _SCRIPT)]
        cwd = str(root)
    if allow_new:
        argv.append("--allow-new")
    argv.extend(str(p) for p in paths)
    return argv, cwd


def remedy_command(paths, *, allow_new: bool = False) -> str:
    """The exact command a user can run to clear a failed commit.

    Every surface's error message must carry this, so the advice a user sees is
    the same one `ait sync`'s ownerless report gives them.

    `allow_new` MUST match the failed invocation's admission -- pass
    ``result.allow_new``. The failure path unstages exactly the entries it
    staged, so a file this run created is left UNTRACKED; a remedy without the
    flag then answers `REFUSED:untracked` and clears nothing, which is worse
    than no advice because the user reasonably concludes the file is unfixable.

    Built through `commit_command` rather than assembled separately, so the
    advertised command cannot drift from the one actually run.
    """
    argv, _ = commit_command(paths, allow_new=allow_new)
    return " ".join(argv)


def commit_metadata(
    paths,
    *,
    allow_new: bool = False,
    root=None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CommitResult:
    """Commit tracked ``aitasks/metadata`` paths through the shell seam.

    ``allow_new=True`` forwards ``--allow-new``, permitting a path that is not
    tracked yet. It defaults to False and must always be *derived* from an
    existence check taken BEFORE the caller's own write — it means "I created
    this", never "creation is allowed here". A hard-coded True is a standing
    relaxation that the next edit to that call site inherits without noticing.

    Paths the user layer owns (``*.local.json``, ``userconfig.yaml``,
    ``profiles/local/``) come back as ``skipped``, so a caller may pass a whole
    layer pair without filtering.

    Never raises on a git failure. Raises ValueError on an empty path list,
    which is a programmer error: an empty pathspec is exactly what makes
    ``git commit`` commit the whole index.
    """
    paths = [str(p) for p in paths]
    if not paths:
        raise ValueError("commit_metadata requires at least one path")

    def _r(status, subject, detail):
        # Every exit stamps the admission this call used -- see CommitResult.
        return CommitResult(status, subject, detail, allow_new)

    argv, cwd = commit_command(paths, allow_new=allow_new, root=root)
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return _r("failed", None, f"timed out after {timeout}s")
    except (FileNotFoundError, PermissionError) as exc:
        return _r("failed", None, f"cannot run {argv[0]}: {exc}")

    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    # The terminal line is the verdict; SKIPPED lines may precede it.
    last = lines[-1] if lines else ""

    if last.startswith("COMMITTED:"):
        # COMMITTED:<n>:<subject> — the subject may itself contain ':'.
        _, _, rest = last.partition(":")
        _, _, subject = rest.partition(":")
        return _r("committed", subject, None)
    if last == "NOCHANGE":
        # Everything given was either clean or user-layer. Report `skipped` when
        # a SKIPPED line explains why, so a caller can tell "nothing to do"
        # from "that layer is not mine to commit".
        if any(ln.startswith("SKIPPED:") for ln in lines):
            return _r("skipped", None, lines[0])
        return _r("nochange", None, None)
    if last.startswith("SKIPPED:"):
        return _r("skipped", None, last)
    if last.startswith("REFUSED:"):
        return _r("refused", None, last)
    if last.startswith("FAILED:"):
        return _r("failed", None, last.partition(":")[2])

    detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
    return _r("failed", None, detail)
