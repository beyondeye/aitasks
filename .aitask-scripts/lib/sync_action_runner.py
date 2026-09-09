"""sync_action_runner - Shared task-data sync runner and conflict modal for Textual TUIs.

Encapsulates the parsing/dispatch glue around `.aitask-scripts/aitask_sync.sh --batch`
so multiple TUIs (board, syncer) can trigger a sync, classify the result, and offer
the same conflict-resolution UX without re-implementing it.

Three layers exposed:

- `parse_sync_output(stdout)` — pure string-to-`SyncResult` parser. No subprocess,
  no Textual import. Easy to unit-test.
- `run_sync_batch(timeout)` — blocking subprocess invocation that returns a
  `SyncResult`. Designed to be called from inside a `@work(thread=True)` worker.
- `SyncConflictScreen` (Textual `ModalScreen`) — modal listing conflicted files
  with "Resolve Interactively" / "Dismiss" buttons. Self-contained CSS.
- `run_interactive_sync(app, on_done)` — terminal-spawn-or-suspend fallback that
  runs `./ait sync` interactively.

Status-to-notification wording is left to each caller; this module only owns
parsing, dispatch, the modal, and the interactive fallback.

Usage (from a host App's worker):

    from sync_action_runner import (
        SyncConflictScreen, run_sync_batch, run_interactive_sync,
        STATUS_CONFLICT, STATUS_PUSHED, ...,
    )

    @work(thread=True, exclusive=True)
    def _sync_worker(self):
        result = run_sync_batch()
        if result.status == STATUS_CONFLICT:
            self.app.call_from_thread(
                self.push_screen, SyncConflictScreen(result.conflicted_files), on_resolve)
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label

_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from agent_launch_utils import find_terminal, spawn_in_terminal  # noqa: E402


# --- Wire-protocol status constants (must match aitask_sync.sh --batch exactly) ---
STATUS_SYNCED = "SYNCED"
STATUS_PUSHED = "PUSHED"
STATUS_PULLED = "PULLED"
STATUS_NOTHING = "NOTHING"
STATUS_AUTOMERGED = "AUTOMERGED"
STATUS_CONFLICT = "CONFLICT"
STATUS_NO_NETWORK = "NO_NETWORK"
STATUS_NO_REMOTE = "NO_REMOTE"
STATUS_DEFERRED = "DEFERRED"
STATUS_ERROR = "ERROR"

# Closed set of DEFERRED reasons. A `DEFERRED:` line is `DEFERRED:<reason>` or
# `DEFERRED:<reason>:<detail>`, split on the FIRST colon only — <detail> is free
# text and may itself contain colons. Pinned here (and asserted in
# tests/test_sync_action_runner.py) so a reason added on the shell side with no
# Python counterpart is caught rather than surfacing as raw text.
DEFERRED_REASONS = frozenset({
    "publication_blocked",   # a commit we cannot vouch for is being withheld
    "protected_dirty",       # files another session owns block the rebase
    "worktree_wedged",       # the data worktree is stuck mid-rebase/merge
})
# Deliberately three, not five. `locks_unavailable` and `lock_contended` are
# per-file SKIP reasons inside the sweep: they surface in the stderr report and
# roll up into `protected_dirty` on the wire, so they are not wire reasons and
# declaring them here would make this set untrue.

# The per-file SUB-reasons carried on `DEFERRED_FILE:` continuation lines. These
# are the `_protect "<reason>"` literals in aitask_sync.sh, and a scan test in
# tests/test_sync_action_runner.py holds the two sides together. They are a
# different vocabulary from DEFERRED_REASONS above -- that one names the wire
# STATUS, this one names why an individual file could not be committed -- and
# merging them would make the status set untrue.
DEFERRED_FILE_REASONS = frozenset({
    "scan_failed",
    "lock_contended",
    "locks_unavailable",
    "ownerless",
    "ambiguous_rename",
    "unverifiable",
    "live_lock",
    "unknown_liveness",
    "lock_acquired_during_scan",
    "staged_elsewhere",
    "content_changed",
    "commit_failed",
    "commit_scope_changed",
    "holder_not_waiting",
})

#: Closed vocabularies for the bare (un-encoded) record columns.
_TREE_STATES = frozenset({"tracked", "untracked", "unknown"})
_HOLDER_CLASSES = frozenset({"self", "other", "remote", "unverified", "none"})
_TASK_RE = re.compile(r"^[0-9]+(_[0-9]+)?$")
_PID_RE = re.compile(r"^[0-9]*$")
#: `waiting_<kind>` carries the monitor's prompt-pattern name, `active` means no
#: prompt was detected, and empty means not probed / unresolvable.
_PANE_STATE_RE = re.compile(r"^(waiting_[a-z0-9_]+|active|)$")

_DEFERRED_FILE_COLUMNS = 11


def _pct_decode(value: str) -> str:
    """Mirror `_pct_decode` in aitask_sync.sh, INCLUDING its order.

    `%25` is decoded LAST so a field that literally contained "%7C" (encoded as
    "%257C") does not decode twice into a delimiter.
    """
    value = value.replace("%0A", "\n")
    value = value.replace("%0D", "\r")
    value = value.replace("%7C", "|")
    value = value.replace("%25", "%")
    return value


@dataclass
class DeferredFile:
    """One file the pre-sync sweep could not commit, as reported on the wire.

    The record is the COMPLETE snapshot for that file: everything a consumer
    renders -- who holds it, where that session runs, what it is doing, and the
    exact action that would clear it -- is present here, so no caller has to
    re-derive locks, pane state or the dirty set for itself.

    TEXTUAL FIELDS USE PYTHON'S FILESYSTEM-SURROGATE CONVENTION. A git path may
    contain any byte but NUL, including bytes that are not valid UTF-8, so
    ``run_sync_batch`` decodes with ``errors="surrogateescape"``. ``path``,
    ``host``, ``email``, ``pane`` and ``action`` may therefore contain lone
    surrogates; recover the original bytes with
    ``value.encode("utf-8", "surrogateescape")``. Writing such a value to a
    strict-UTF-8 stream raises -- rendering one safely is the caller's job.
    """

    sub_reason: str
    task: str
    path: str
    tree_state: str
    holder: str
    email: str
    host: str
    pid: str
    pane: str
    pane_state: str
    action: str


def _parse_deferred_file(line: str) -> DeferredFile | None:
    """Parse one `DEFERRED_FILE:` line, or return None if it is malformed.

    FAILS CLOSED. Every bare column is validated against its closed vocabulary,
    because those columns are what a consumer branches on: a `holder` outside
    the known set would reach a UI that has no case for it, and a caller that
    silently dropped the row would render a deferral with files missing from it.
    """
    body = line[len("DEFERRED_FILE:"):]
    parts = body.split("|")
    if len(parts) != _DEFERRED_FILE_COLUMNS:
        return None
    (sub_reason, task, path, tree_state, holder,
     email, host, pid, pane, pane_state, action) = parts

    if sub_reason not in DEFERRED_FILE_REASONS:
        return None
    if task and not _TASK_RE.match(task):
        return None
    if tree_state not in _TREE_STATES:
        return None
    if holder not in _HOLDER_CLASSES:
        return None
    if not _PID_RE.match(pid):
        return None
    if not _PANE_STATE_RE.match(pane_state):
        return None

    return DeferredFile(
        sub_reason=sub_reason,
        task=task,
        path=_pct_decode(path),
        tree_state=tree_state,
        holder=holder,
        email=_pct_decode(email),
        host=_pct_decode(host),
        pid=pid,
        pane=_pct_decode(pane),
        pane_state=pane_state,
        action=_pct_decode(action),
    )


# --- Synthetic statuses owned by run_sync_batch ---
STATUS_TIMEOUT = "TIMEOUT"
STATUS_NOT_FOUND = "NOT_FOUND"

# Wall-clock cap on the whole batch invocation. The underlying aitask_sync.sh
# applies its own NETWORK_TIMEOUT=10 to each fetch/push, so 30s leaves headroom
# for auto-merge attempts on top of the network calls.
DEFAULT_SYNC_TIMEOUT_SECONDS = 30

_SYNC_SCRIPT = "./.aitask-scripts/aitask_sync.sh"


@dataclass
class SyncResult:
    status: str
    conflicted_files: list[str] = field(default_factory=list)
    error_message: str | None = None
    raw_output: str = ""
    #: Set only for STATUS_DEFERRED. Deliberately NOT folded into
    #: ``error_message``: a deferral is a benign outcome, and anything
    #: inspecting the dataclass would read a populated ``error_message`` as a
    #: failure. ``deferred_reason`` is one of :data:`DEFERRED_REASONS` when the
    #: shell and Python sides agree; ``deferred_detail`` is free text.
    deferred_reason: str | None = None
    deferred_detail: str | None = None
    #: Per-file records from the `DEFERRED_FILE:` continuation lines. Populated
    #: only when the status line was `DEFERRED:` -- see parse_sync_output.
    deferred_files: list["DeferredFile"] = field(default_factory=list)


def parse_sync_output(stdout: str) -> SyncResult:
    """Parse the first non-empty line of `aitask_sync.sh --batch` stdout.

    Pure function — no subprocess, no Textual. Mirrors the parsing previously
    inlined in `aitask_board.py:_run_sync` so behavior is identical for every
    documented status, including the bare `CONFLICT:` edge case (which yields
    `[""]` because `"".split(",")` does, matching the historical board path).
    """
    raw = stdout
    # SPLIT ON LF ALONE, never str.splitlines(). splitlines() also breaks on CR,
    # VT, FF, FS, GS, RS, NEL and (after decoding) U+2028/U+2029 -- every one of
    # which is a legal byte in a git path, and all of which travel inside the
    # percent-encoded fields of a DEFERRED_FILE: record. Using it would let a
    # hostile-but-valid filename split one record into two unparseable halves.
    # The shell encodes LF (and CR) precisely so this one rule is sufficient.
    lines = raw.split("\n")

    line = ""
    first_idx = -1
    for idx, candidate in enumerate(lines):
        stripped = candidate.strip()
        if stripped:
            line = stripped
            first_idx = idx
            break

    if not line:
        return SyncResult(
            status=STATUS_ERROR,
            error_message="empty output from sync script",
            raw_output=raw,
        )

    if line.startswith("CONFLICT:"):
        suffix = line[len("CONFLICT:"):]
        return SyncResult(
            status=STATUS_CONFLICT,
            conflicted_files=suffix.split(","),
            raw_output=raw,
        )

    if line.startswith("DEFERRED:"):
        suffix = line[len("DEFERRED:"):]
        reason, _, detail = suffix.partition(":")
        if reason not in DEFERRED_REASONS:
            # FAIL CLOSED, exactly like the unknown-status branch below. A
            # deferral renders as a benign warning in both TUIs and is
            # deliberately not captured as a failure — so accepting an
            # unrecognised reason would turn a shell-side typo into "all fine,
            # just deferred" and silently suppress a real sync failure. The
            # reason set is a closed protocol; an unknown one is a bug.
            return SyncResult(
                status=STATUS_ERROR,
                error_message=f"unknown deferral reason: {reason or '(empty)'}",
                raw_output=raw,
            )
        # Continuation lines are collected ONLY under a DEFERRED status line.
        # A DEFERRED_FILE: line in the first position is not a deferral with a
        # missing header, it is an unknown status -- and is handled as one by
        # the fallthrough below.
        deferred_files: list[DeferredFile] = []
        for candidate in lines[first_idx + 1:]:
            stripped = candidate.strip()
            if not stripped or not stripped.startswith("DEFERRED_FILE:"):
                continue
            record = _parse_deferred_file(stripped)
            if record is None:
                # FAIL CLOSED, same rule as an unknown deferral reason above. A
                # record we cannot parse is a file the user would never be told
                # about, and silently dropping it turns an actionable deferral
                # back into the opaque one this whole protocol replaced.
                return SyncResult(
                    status=STATUS_ERROR,
                    error_message=f"malformed DEFERRED_FILE record: {stripped[:120]}",
                    raw_output=raw,
                )
            deferred_files.append(record)

        return SyncResult(
            status=STATUS_DEFERRED,
            deferred_reason=reason,
            deferred_detail=detail or None,
            deferred_files=deferred_files,
            raw_output=raw,
        )

    if line.startswith("ERROR:"):
        return SyncResult(
            status=STATUS_ERROR,
            error_message=line[len("ERROR:"):],
            raw_output=raw,
        )

    if line in (
        STATUS_SYNCED,
        STATUS_PUSHED,
        STATUS_PULLED,
        STATUS_NOTHING,
        STATUS_AUTOMERGED,
        STATUS_NO_NETWORK,
        STATUS_NO_REMOTE,
    ):
        return SyncResult(status=line, raw_output=raw)

    return SyncResult(
        status=STATUS_ERROR,
        error_message=f"unknown status: {line}",
        raw_output=raw,
    )


def sync_batch_command(repo_root: Path | None = None) -> tuple[list[str], str | None]:
    """(argv, cwd) for the ``aitask_sync.sh --batch`` invocation.

    Pure command-resolution seam (no subprocess) so targeting is unit-testable
    without live git. ``None`` preserves the legacy CWD-relative invocation
    (the board caller); a root targets that repo's own installed script with
    ``cwd=<root>`` so its ``_AIT_DATA_WORKTREE`` resolution applies.
    """
    if repo_root is None:
        return [_SYNC_SCRIPT, "--batch"], None
    return [str(repo_root / ".aitask-scripts" / "aitask_sync.sh"), "--batch"], str(repo_root)


def run_sync_batch(
    timeout: float = DEFAULT_SYNC_TIMEOUT_SECONDS,
    repo_root: Path | None = None,
) -> SyncResult:
    """Invoke `aitask_sync.sh --batch` and return a parsed `SyncResult`.

    Blocking — designed to be called from inside a `@work(thread=True)` worker.
    Owns subprocess error mapping: timeouts become `STATUS_TIMEOUT`, missing
    script becomes `STATUS_NOT_FOUND`. Otherwise hands off to
    `parse_sync_output`. ``repo_root`` targets another repo's sync script
    (see `sync_batch_command`); ``None`` is the legacy CWD-relative behavior.
    """
    argv, cwd = sync_batch_command(repo_root)
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            # BYTE-PRESERVING, and pinned to one codec. A git path may contain
            # any byte but NUL, so a plain `text=True` (locale codec,
            # errors="strict") raises UnicodeDecodeError INSIDE subprocess.run
            # on a path like b"a\xffb" -- before parse_sync_output ever sees it,
            # and past the two excepts below, so it would escape this function
            # and crash the calling TUI. surrogateescape round-trips such bytes:
            # value.encode("utf-8", "surrogateescape") returns the original.
            # `encoding` is explicit so the convention does not depend on
            # whatever LC_ALL happens to be.
            encoding="utf-8",
            errors="surrogateescape",
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return SyncResult(
            status=STATUS_TIMEOUT,
            error_message=f"sync timed out after {timeout:g}s",
        )
    except FileNotFoundError:
        return SyncResult(
            status=STATUS_NOT_FOUND,
            error_message="sync script not found",
        )

    return parse_sync_output(result.stdout)


class SyncConflictScreen(ModalScreen):
    """Modal dialog shown when `ait sync` detects merge conflicts.

    Self-contained: ships its own CSS via `DEFAULT_CSS` so it renders correctly
    in any host App (board, syncer) without depending on app-level styling.
    """

    DEFAULT_CSS = """
    #sync_conflict_dialog {
        width: 60%;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #sync_conflict_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #sync_conflict_files {
        padding: 0 1;
        color: $text-muted;
    }
    #sync_conflict_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, conflicted_files: list[str]):
        super().__init__()
        self.conflicted_files = conflicted_files

    def compose(self):
        file_list = "\n".join(f"  - {f}" for f in self.conflicted_files)
        with Container(id="sync_conflict_dialog"):
            yield Label("Sync Conflict Detected", id="sync_conflict_title")
            yield Label(
                f"Conflicts between local and remote task data:\n\n{file_list}\n\n"
                "Open interactive terminal to resolve?",
                id="sync_conflict_files",
            )
            with Horizontal(id="sync_conflict_buttons"):
                yield Button("Resolve Interactively", variant="warning", id="btn_sync_resolve")
                yield Button("Dismiss", variant="default", id="btn_sync_dismiss")

    @on(Button.Pressed, "#btn_sync_resolve")
    def resolve(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_sync_dismiss")
    def dismiss_dialog(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


def run_interactive_sync(
    app,
    on_done: Callable[[], None] | None = None,
    repo_root: Path | None = None,
) -> None:
    """Launch interactive `./ait sync` for conflict resolution.

    Two paths:
    - If a terminal emulator is available (`find_terminal()`), spawn it
      detached running `./ait sync`. Fire-and-forget — `on_done` is NOT
      invoked because we cannot observe the spawned terminal's exit. This
      matches the board's pre-extraction behavior.
    - Otherwise, suspend the Textual app and run `./ait sync` inline. After
      the inline call returns, invoke `on_done` (if provided) so the host
      app can refresh its state.

    ``repo_root`` targets another repo's own ``ait`` dispatcher (the absolute
    path suffices — ``ait`` cds to its repo root itself); ``None`` keeps the
    legacy CWD-relative invocation.

    The no-terminal path uses `app.suspend()`, which blocks; call this from a
    worker context (e.g., `@work(exclusive=True)`) to avoid stalling the
    event loop. The terminal-spawn path is non-blocking and safe from any
    context.
    """
    if repo_root is None:
        ait_argv = ["./ait", "sync"]
        cwd = None
    else:
        ait_argv = [str(repo_root / "ait"), "sync"]
        cwd = str(repo_root)

    terminal = find_terminal()
    if terminal:
        spawn_in_terminal(terminal, ait_argv)
        return

    with app.suspend():
        subprocess.call(ait_argv, cwd=cwd)
    if on_done is not None:
        on_done()
