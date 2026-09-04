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

#: status: ok | refused | failed
#:
#: `states` maps each requested path to clean|dirty|untracked|ignored|absent.
#: `midop` is the in-progress git state the destination is stuck in, or None.
#: `branch` is the data branch's name, or None when detached.
#:
#: A `failed` result NEVER carries usable states: an old or missing helper, an
#: unparseable answer and a timeout all land there, and treating any of them as
#: "clean" is how a fail-closed check silently becomes fail-open.
PreflightResult = namedtuple(
    "PreflightResult", "status mode branch midop states detail"
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


def preflight_metadata(
    paths,
    *,
    root=None,
    env=None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> PreflightResult:
    """Inspect a repo's metadata paths without writing anything (t1704).

    Same subprocess shape and same never-raises contract as `commit_metadata`,
    and deliberately the same helper: the scope / ignore / tracked resolution
    ladder lives once, in shell, so a preflight can never classify a path
    differently from the commit that follows it.

    Built for the cross-repo config push, which writes ANOTHER repo's tracked
    config and must decide what is safe there BEFORE writing. Pass that repo as
    `root` and its scrubbed environment as `env`.

    An unparseable, old, or missing helper returns ``failed`` — never ``ok``.
    That direction is the whole point: a destination we could not inspect must
    be refused, not written to on the assumption it was clean.

    Raises ValueError on an empty path list, mirroring `commit_metadata`.
    """
    paths = [str(p) for p in paths]
    if not paths:
        raise ValueError("preflight_metadata requires at least one path")

    if root is None:
        argv = [str(Path(".") / _SCRIPT)]
        cwd = None
    else:
        argv = [str(Path(root) / _SCRIPT)]
        cwd = str(root)
    argv.append("--preflight")
    argv.extend(paths)

    def _failed(detail):
        return PreflightResult("failed", None, None, None, {}, detail)

    try:
        proc = subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return _failed(f"timed out after {timeout}s")
    except (FileNotFoundError, PermissionError, NotADirectoryError) as exc:
        return _failed(f"cannot run {argv[0]}: {exc}")

    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]

    for ln in lines:
        if ln.startswith("REFUSED:"):
            return PreflightResult("refused", None, None, None, {}, ln)
        if ln.startswith("FAILED:"):
            return _failed(ln.partition(":")[2])

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        return _failed(detail)

    mode = branch = midop = None
    states: dict[str, str] = {}
    for ln in lines:
        if ln.startswith("MODE:"):
            mode = ln.partition(":")[2]
        elif ln.startswith("BRANCH:"):
            value = ln.partition(":")[2]
            branch = None if value == "DETACHED" else value
        elif ln.startswith("MIDOP:"):
            midop = ln.partition(":")[2]
        elif ln.startswith("STATE:"):
            # STATE:<path>:<state> — the state is the LAST field, because a
            # path may itself contain ':'.
            body = ln.partition(":")[2]
            path, _, state = body.rpartition(":")
            if path:
                states[path] = state

    # A helper too old to know --preflight exits 0 having printed its usage, so
    # "exit 0" alone is not evidence that an inspection happened. Requiring the
    # protocol's own mandatory line is what turns version skew into `failed`.
    if mode is None:
        return _failed(
            "no MODE: line — the destination's aitask_metadata_commit.sh does "
            "not support --preflight"
        )
    missing = [p for p in paths if p not in states]
    if missing:
        return _failed(f"no STATE: line for {', '.join(missing)}")

    return PreflightResult("ok", mode, branch, midop, states, None)


def commit_metadata(
    paths,
    *,
    allow_new: bool = False,
    root=None,
    env=None,
    expect=None,
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

    ``expect`` is a compare-and-commit guard (t1704): a mapping of
    ``{repo_relative_path: local_file_holding_the_bytes we just wrote}``,
    forwarded as ``--expect`` pairs. If the worktree no longer holds those bytes
    at commit time the helper commits nothing and this returns status ``raced``
    — distinct from ``refused``, because a race is a retryable fact about the
    world and a refusal is a fact about the request. It is fail-closed in the
    helper: once given, every committable path needs an entry, and an
    incomplete set comes back as ``failed`` (a programmer error, not a race).

    ``env`` is forwarded to the subprocess; ``None`` inherits, which is what the
    pre-existing callers get. Pass a scrubbed environment when targeting a
    foreign ``root``: the helper's ``METADATA_PREFIX`` reads ``${TASK_DIR}``, so
    a ``TASK_DIR``/``METADATA_DIR`` leaking from the calling session would aim
    it at the wrong tree.

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
    if expect:
        # `commit_command` puts the paths last, so the flags go in front of that
        # tail: the shape stays `<script> [--allow-new] [--expect ...] <paths>`.
        # commit_command itself is left alone — it is the pure resolution seam
        # that `remedy_command` also builds on, and the remedy must stay the
        # command a USER can run, which no --expect ever is.
        flags = []
        for path, holder in expect.items():
            flags += ["--expect", f"{path}={holder}"]
        argv = argv[: len(argv) - len(paths)] + flags + paths
    try:
        proc = subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
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
    if last.startswith("REFUSED:changed:"):
        # A race, not a refusal: the request was well-formed and the world moved
        # under it. Callers treat the two differently — a race is retryable and
        # must NOT be reported to the user as a rejected request.
        return _r("raced", None, last)
    if last.startswith("REFUSED:expect_incomplete"):
        # A programmer error (a partially-guarded commit was requested), which
        # is a bug in the caller rather than anything the user can act on.
        return _r("failed", None, last)
    if last.startswith("REFUSED:"):
        return _r("refused", None, last)
    if last.startswith("FAILED:"):
        return _r("failed", None, last.partition(":")[2])

    detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
    return _r("failed", None, detail)
