#!/usr/bin/env python3
"""Freeze engine for frozen code agents (t1705_4).

Turns a live code-agent pane into a **frozen stand-in**: capture its scrollback,
stamp the pane, drive the store's lease-owned states, and `respawn-pane -k` the
agent's own pane into the stand-in viewer command — while the companion
minimonitor and the window survive.

Three entry points, all reachable through `aitask_frozen.sh`:

* :func:`freeze_pane`  — one pane, the §C transaction below;
* :func:`freeze_all`   — every agent-facing pane on every aitasks tmux session;
* :func:`reconcile`    — the §C repair table, run after every freeze, from the
  monitor maintenance tick, and by hand.

Two hard boundaries, both load-bearing, are **enforced in
`lib/agent_frozen_ops.py`** — the module this engine shares with the restore
coordinator (`lib/agent_restore.py`, t1705_5) so the two cannot fork the store's
wire protocol (t1738):

1. **Every tmux call goes through `TmuxClient`** (`lib/tmux_exec.py`), the
   sanctioned gateway, reached here as `frozen_ops.run(...)`.
   `tests/test_no_raw_tmux.sh` enforces it.
2. **Every store WRITE goes through the shell wrapper**
   (`aitask_agent_sessions.sh`), never by importing `agent_sessions`' mutators.
   The wrapper is the store's sole writer because it holds the mutex around the
   read-modify-write; importing the transition functions here would write
   unlocked and lose updates. Reads (`show` / `list`) go through the same
   wrapper for one parsing path, even though they take no lock.

The shared helpers are called **through the module** (`frozen_ops.store(...)`,
never `from agent_frozen_ops import store`): the tests swap
`agent_frozen_ops.store` and `agent_frozen_ops._TMUX` in place, and an
import-time alias would bind the original object and miss the swap. See that
module's docstring for the full seam rule.

THE STAND-IN VIEWER is `ait frozenagent --record <id>` (t1705_6), which is what
`standin_command()` names; `AITASKS_FROZEN_STANDIN_CMD` remains a test seam for
suites that want a harmless process instead. Reconcile still treats "stamped, no
ready mark, no known pid" as **indeterminate** rather than as failure: a viewer
that boots slowly looks exactly like one that never will, and only positive
evidence (`@aitask_standin_ready`, or a pid match) distinguishes them.

Test seams, honoured **only** under ``AITASKS_TEST_MODE=1``. They are built from
`agent_frozen_ops`' shared factory, so the restore coordinator's
``AITASKS_RESTORE_FAIL_AT`` cannot fire in this engine and vice versa:

* ``AITASKS_FREEZE_FAIL_AT=capture|begin|stamp|respawn|commit`` — raise at that
  stage so the rollback branch can be exercised
  (`frozen_ops.make_fail_at`, bound below as ``_fail_at``);
* ``AITASKS_FROZEN_PAUSE_AT=<stage>`` — ``SIGSTOP`` this process at that stage,
  so a test can run a concurrent ``reconcile`` against a held lease and then
  ``SIGCONT``;
* ``AITASKS_STALE_OP_GRACE`` (in ``lib/agent_sessions.py``) — shorten the lease
  grace so takeover races finish in seconds.
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _LIB_DIR.parent
for _p in (str(_SCRIPTS_DIR), str(_LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_frozen_ops as frozen_ops  # noqa: E402
import agent_sessions  # noqa: E402
# Re-exported names only — never swapped, so an import alias is safe. Every
# shared FUNCTION is called as `frozen_ops.<name>(...)` instead (seam rule).
from agent_frozen_ops import (  # noqa: E402,F401
    EXIT_LEASE_HELD,
    EXIT_LOCK_BUSY,
    EXIT_NONCE_MISMATCH,
    EXIT_TRANSITION_REFUSED,
    SESSIONS_SH,
    StageFailure as _StageFailure,
)
from agent_launch_utils import (  # noqa: E402
    discover_aitasks_sessions,
    tmux_session_target,
)
from config_utils import load_yaml_config  # noqa: E402
from monitor.ansi_utils import strip_ansi  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    FROZEN_AWARE_PANE_FORMAT,
    classify_window_panes,
    count_other_real_agents,
    FROZEN_OPTION,
    PaneCategory,
    RECORD_OPTION,
    STANDIN_READY_OPTION,
    AGENT_SESSION_OPTION,
    TmuxMonitor,
)

#: This engine's failure-injection seam, bound to its own environment variable
#: so the restore coordinator's `AITASKS_RESTORE_FAIL_AT` cannot fire here.
_fail_at = frozen_ops.make_fail_at("AITASKS_FREEZE_FAIL_AT")

#: `drop`'s own failure seam, bound to its own variable so a test injecting into
#: the freeze transaction cannot trip the drop protocol (the two run in the same
#: process during a freeze-then-drop sequence).
_drop_fail_at = frozen_ops.make_fail_at("AITASKS_DROP_FAIL_AT")

#: `drop`'s stages, in order. Named so the seams and the wire lines agree on one
#: vocabulary, exactly as :data:`STAGES` does for freeze.
DROP_STAGES = ("claim", "preflight", "kill", "verify", "store")

#: Default scrollback cap. Overridden by `frozen.capture_max_lines` in the
#: project's `aitasks/metadata/project_config.yaml`; the shipped config has no
#: `frozen:` section, so this default is the normal path.
DEFAULT_CAPTURE_MAX_LINES = 50000

# The restore ack grace lives in `agent_frozen_ops` (t1705_5, amendment B6), not
# here: the restore COORDINATOR needs it too, and hosting it in this module would
# make the coordinator import the repair engine for one accessor — the one-way
# dependency arrow the shared module exists to protect. Read it as
# `frozen_ops.restore_ack_grace()`.

#: `reconcile`'s own list-panes format. Deliberately NOT `_LIST_PANES_FORMAT`:
#: reconcile must observe EVERY pane of a window — companions, stand-ins and
#: dead panes included — to emit complete `PANE` observation rows, whereas
#: `_LIST_PANES_FORMAT` feeds an agent-facing view that filters helpers out.
#: The two passes have opposite requirements; do not unify them.
_RECONCILE_FORMAT = "\t".join([
    "#{session_name}", "#{window_name}", "#{pane_id}", "#{pane_pid}",
    "#{pane_dead}", "#{pane_current_path}",
    f"#{{{FROZEN_OPTION}}}", f"#{{{STANDIN_READY_OPTION}}}",
    f"#{{{RECORD_OPTION}}}",
])
_RECONCILE_ARITY = 9

#: Stages of the §C freeze transaction, in order. Named so the fail/pause seams
#: and the `FREEZE_FAILED:<stage>` wire line agree on one vocabulary.
STAGES = ("resolve", "capture", "begin", "stamp", "respawn", "commit")


@dataclass
class FreezeResult:
    """One pane's outcome. ``line`` is the wire line callers print."""

    record_id: str
    ok: bool
    stage: str
    line: str


# --- capture ----------------------------------------------------------------


def capture_max_lines(root: str | os.PathLike | None = None) -> int:
    """`frozen.capture_max_lines` from the project config, else the default.

    Read with the real YAML parser (`config_utils.load_yaml_config`), never
    hand-parsed. A missing file, a missing section, or a non-positive value all
    resolve to :data:`DEFAULT_CAPTURE_MAX_LINES` — a cap of 0 would capture
    nothing and silently make every freeze lossy.
    """
    base = Path(root) if root else Path.cwd()
    cfg_path = base / "aitasks" / "metadata" / "project_config.yaml"
    try:
        cfg = load_yaml_config(cfg_path, {})
    except Exception:
        # Broad on purpose: this runs mid-freeze, and a malformed or unreadable
        # project config must degrade to the default cap rather than abort a
        # transaction that is about to respawn the user's agent pane.
        return DEFAULT_CAPTURE_MAX_LINES
    section = cfg.get("frozen") if isinstance(cfg, dict) else None
    if not isinstance(section, dict):
        return DEFAULT_CAPTURE_MAX_LINES
    try:
        value = int(section.get("capture_max_lines", DEFAULT_CAPTURE_MAX_LINES))
    except (TypeError, ValueError):
        return DEFAULT_CAPTURE_MAX_LINES
    return value if value > 0 else DEFAULT_CAPTURE_MAX_LINES


def _capture(pane_id: str, record_id: str, cap: int) -> tuple[str, str, int]:
    """Capture the pane's scrollback. Returns ``(ansi_path, txt_path, lines)``.

    ``-e`` keeps escape sequences (the viewer replays colour), ``-J`` rejoins
    wrapped lines, ``-S -<cap>`` starts ``cap`` lines back in history. The
    stripped ``.txt`` sibling is what greps and diffs read.

    Both files are written 0600 inside the 0700 per-record directory: a capture
    is a verbatim transcript of someone's coding session, including whatever
    secrets scrolled past.
    """
    rc, out = frozen_ops.run(
        ["capture-pane", "-p", "-e", "-J", "-t", pane_id, "-S", f"-{cap}"],
        timeout=30.0,
    )
    if rc != 0:
        raise OSError(f"capture-pane failed for {pane_id}")
    directory = agent_sessions.ensure_capture_dir(record_id)
    ansi_path = directory / "capture.ansi"
    txt_path = directory / "capture.txt"
    _write_private(ansi_path, out)
    _write_private(txt_path, strip_ansi(out))
    # tmux ends the buffer with a newline; count real lines, not the split's
    # trailing empty element.
    return str(ansi_path), str(txt_path), len(out.splitlines())


def _write_private(path: Path, text: str) -> None:
    """Write 0600. The mode is set explicitly — `open` is masked by the umask."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
    except Exception:
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# --- record resolution ------------------------------------------------------


def _walk_up_to_project(path: str) -> str:
    """Nearest ancestor of ``path`` holding `aitasks/metadata/project_config.yaml`.

    Falls back to the realpath of ``path`` itself: an `upsert` still needs a
    root, and a wrong-but-stable root produces a record that reconcile can find
    and purge, whereas no root at all loses the agent entirely.
    """
    try:
        current = Path(os.path.realpath(path or os.getcwd()))
    except OSError:
        return os.path.realpath(os.getcwd())
    for candidate in [current, *current.parents]:
        if (candidate / "aitasks" / "metadata" / "project_config.yaml").is_file():
            return str(candidate)
    return str(current)


def _resolve_record(facts: dict[str, str]) -> tuple[str, str]:
    """``(record_id, wire_line)`` for the pane described by ``facts``.

    Two paths, in the §C order:

    1. the pane carries `@aitask_record` and the store still knows that id —
       use it. This is the normal case: the SessionStart hook (t1705_3) recorded
       the agent at launch.
    2. otherwise `upsert` a record and stamp the pane (amendment A8). The hook
       may never have fired (an agent started before the hook shipped, a CLI
       without hook support), and freezing an unrecorded agent must still work.

    A stamped id the store does NOT know falls through to (2) deliberately: the
    stamp is a dangling join — the record was dropped, or the store was reset —
    and reusing the id would `freeze-begin` a record that does not exist.
    """
    stamped = facts.get("record", "")
    if stamped and agent_sessions.valid_id(stamped) and frozen_ops.store_show(stamped):
        return stamped, f"RECORD:{stamped}|stamped"

    root = _walk_up_to_project(facts.get("path", ""))
    session_id = facts.get("agent_session", "")
    rc, out = frozen_ops.store(
        "upsert",
        "--root", root,
        "--window", facts.get("window", ""),
        "--pane", facts.get("pane_id", ""),
        "--pane-pid", facts.get("pane_pid", "0"),
        "--session", facts.get("session", ""),
        "--session-id", session_id,
        "--agent-string", "",
    )
    if rc != 0:
        raise OSError(f"upsert failed: {out}")
    # `UPSERTED:<id>|<how>`
    payload = out.splitlines()[-1] if out.splitlines() else ""
    _, _, rest = payload.partition(":")
    record_id = rest.partition("|")[0].strip()
    if not agent_sessions.valid_id(record_id):
        raise OSError(f"upsert returned no usable record id: {out!r}")

    # A8: the store never touches tmux, so establishing the join is the
    # caller's obligation — and only after a success line, which is why this
    # sits below the rc check rather than beside the upsert.
    frozen_ops.set_option(facts.get("pane_id", ""), RECORD_OPTION, record_id)
    return record_id, f"RECORD:{record_id}|created"


# --- freeze -----------------------------------------------------------------


def freeze_pane(pane_id: str, *, cap: int | None = None) -> FreezeResult:
    """Freeze one agent pane. Implements §C 1-6 in order.

    Each step is persisted before the next irreversible one, so every crash
    point leaves a state `reconcile` can settle from server-observable facts
    alone. The rollback for each stage is stated inline; the shape is always
    "undo what this process did, leave the agent running".
    """
    facts = frozen_ops.pane_facts(pane_id)
    if not facts:
        return FreezeResult("", False, "resolve",
                            f"FREEZE_FAILED:resolve|{pane_id}|pane not found")
    if facts.get("frozen"):
        return FreezeResult(facts["frozen"], False, "resolve",
                            f"FREEZE_SKIPPED:{facts['frozen']}|already frozen")

    # --- 1. resolve the record ---------------------------------------------
    try:
        _fail_at("resolve")
        record_id, _line = _resolve_record(facts)
    except (_StageFailure, OSError) as exc:
        return FreezeResult("", False, "resolve",
                            f"FREEZE_FAILED:resolve|{pane_id}|{exc}")
    frozen_ops.pause_at("resolve")

    # --- 2. capture ---------------------------------------------------------
    # BEFORE `freeze-begin`, because `freeze-begin` persists the capture paths
    # and the line count. A failure here has nothing to undo but temp files.
    if cap is None:
        cap = capture_max_lines(_walk_up_to_project(facts.get("path", "")))
    try:
        _fail_at("capture")
        ansi_path, txt_path, lines = _capture(pane_id, record_id, cap)
    except (_StageFailure, OSError, ValueError) as exc:
        agent_sessions.remove_captures(record_id)
        return FreezeResult(record_id, False, "capture",
                            f"FREEZE_FAILED:capture|{record_id}|{exc}")
    frozen_ops.pause_at("capture")

    # --- 3. freeze-begin: state `freezing`, lease minted --------------------
    # `--owner-pid` is THIS process (A7): the coordinator that outlives the
    # respawn. Never a subshell's `$$` — a pid that is already dead collapses
    # the lease's staleness test to a bare timer and lets a later reconcile
    # seize this very freeze.
    try:
        _fail_at("begin")
    except _StageFailure as exc:
        agent_sessions.remove_captures(record_id)
        return FreezeResult(record_id, False, "begin",
                            f"FREEZE_FAILED:begin|{record_id}|{exc}")
    rc, out = frozen_ops.store(
        "freeze-begin", record_id,
        "--owner-pid", str(os.getpid()),
        "--capture-ansi", ansi_path,
        "--capture-txt", txt_path,
        "--lines", str(lines),
    )
    if rc != 0:
        agent_sessions.remove_captures(record_id)
        return FreezeResult(record_id, False, "begin",
                            f"FREEZE_FAILED:begin|{record_id}|{out}")
    nonce = frozen_ops.nonce_from(out.splitlines()[-1])
    frozen_ops.pause_at("begin")

    # --- 4. stamp the pane --------------------------------------------------
    # `@aitask_frozen` is the authoritative classifier; clearing
    # `@aitask_standin_ready` first matters because pane options SURVIVE
    # `respawn-pane`, so a ready mark from a previous freeze/restore cycle
    # would read as "this cycle's viewer is already up".
    try:
        _fail_at("stamp")
        if not frozen_ops.set_option(pane_id, FROZEN_OPTION, record_id):
            raise OSError(f"could not stamp {FROZEN_OPTION} on {pane_id}")
        frozen_ops.unset_option(pane_id, STANDIN_READY_OPTION)
    except (_StageFailure, OSError) as exc:
        # Unlike the shadow spawner (which kills the pane when its stamp
        # fails), the freeze must leave the AGENT RUNNING: nothing has been
        # respawned yet, and the user's session is still live in that pane.
        frozen_ops.unset_option(pane_id, FROZEN_OPTION)
        frozen_ops.store("freeze-abort", record_id, "--nonce", nonce)
        return FreezeResult(record_id, False, "stamp",
                            f"FREEZE_FAILED:stamp|{record_id}|{exc}")
    frozen_ops.pause_at("stamp")

    # --- 5. respawn into the stand-in --------------------------------------
    try:
        _fail_at("respawn")
        command = agent_sessions.standin_command(record_id)
        if not frozen_ops.respawn(pane_id, command):
            raise OSError(f"respawn-pane refused for {pane_id}")
    except (_StageFailure, OSError, ValueError) as exc:
        frozen_ops.unset_option(pane_id, FROZEN_OPTION)
        frozen_ops.unset_option(pane_id, STANDIN_READY_OPTION)
        frozen_ops.store("freeze-abort", record_id, "--nonce", nonce)
        return FreezeResult(record_id, False, "respawn",
                            f"FREEZE_FAILED:respawn|{record_id}|{exc}")
    frozen_ops.pause_at("respawn")

    # --- 6. freeze-commit ---------------------------------------------------
    # The stand-in's location is read AFTER the respawn: `respawn-pane`
    # preserves the pane id but replaces the process, so `#{pane_pid}` is the
    # only thing that proves the swap happened.
    new_pane, new_pid = frozen_ops.pane_location(pane_id)
    frozen_ops.pause_at("commit")
    try:
        _fail_at("commit")
    except _StageFailure as exc:
        # Deliberately NO rollback: the agent is already gone (step 5 killed
        # it), so aborting here would strand a `live` record with no agent.
        # Leaving the record `freezing` is the correct state — reconcile
        # commits it once the lease goes stale.
        return FreezeResult(record_id, False, "commit",
                            f"FREEZE_FAILED:commit|{record_id}|{exc}")
    rc, out = frozen_ops.store(
        "freeze-commit", record_id,
        "--nonce", nonce,
        "--pane", new_pane,
        "--pane-pid", str(new_pid),
    )
    if rc == EXIT_NONCE_MISMATCH:
        # reconcile already resolved this record. Report and exit WITHOUT
        # touching the pane: whatever settled it owns the pane's state now, and
        # a second actor writing here is exactly what the nonce prevents.
        return FreezeResult(record_id, False, "commit",
                            f"NONCE_MISMATCH:{record_id}")
    if rc != 0:
        # LOCK_BUSY and friends: the record stays `freezing` and reconcile
        # finishes it. Not a rollback — the swap already happened.
        return FreezeResult(record_id, False, "commit",
                            f"FREEZE_FAILED:commit|{record_id}|{out}")
    return FreezeResult(record_id, True, "commit", f"FROZEN:{record_id}")


# --- freeze all -------------------------------------------------------------


def _agent_panes_for(session: str) -> list:
    """Agent-facing panes of one session, via the documented discovery contract.

    **`TmuxMonitor.discover_panes()`, never `list-panes` + `classify_pane`.**
    `classify_pane` reads only the WINDOW NAME, so every pane in an `agent-*`
    window classifies as AGENT — including the companion minimonitor that
    `maybe_spawn_minimonitor` splits into that same window. Selecting on the
    category alone would make Freeze-All `respawn-pane -k` the companion of
    every agent it froze, destroying the exact pane the freeze design goes out
    of its way to preserve. Companion exclusion is a separate identity check
    (`_is_companion_pane`) applied inside `_parse_list_panes`, and
    `discover_panes()` is the contract that applies both it and the shadow
    filter — plus the correct `-t tmux_session_target()` targeting.
    """
    monitor = TmuxMonitor(session=session, multi_session=False, exclude_pane="")
    return monitor.discover_panes()


def freeze_all() -> list[FreezeResult]:
    """Freeze every live agent pane on every aitasks session.

    Sequential: each freeze is one `respawn-pane`, and parallel respawns are not
    worth the tmux churn. Per-pane failures are reported and the batch
    continues — one unfreezable agent must not strand the rest.
    """
    results: list[FreezeResult] = []
    for session in discover_aitasks_sessions():
        try:
            panes = _agent_panes_for(session.session)
        except Exception as exc:   # a session that vanished mid-scan
            results.append(FreezeResult(
                "", False, "resolve",
                f"FREEZE_FAILED:resolve|{session.session}|{exc}"))
            continue
        for pane in panes:
            if pane.category != PaneCategory.AGENT:
                continue
            if pane.frozen_record:
                continue          # already a stand-in
            results.append(freeze_pane(pane.pane_id))
    return results


# --- reconcile --------------------------------------------------------------


@dataclass
class _Observed:
    """One pane as reconcile saw it."""

    session: str
    window: str
    pane_id: str
    pane_pid: int
    pane_dead: bool
    path: str
    frozen: str
    standin_ready: str
    record: str


def _enumerate_session(session: str) -> tuple[bool, list[_Observed]]:
    """``(ok, panes)`` for one session's EXPLICITLY TARGETED `list-panes -s`.

    **`-t` is not optional.** An untargeted `list-panes -s` resolves to the
    *current* session, and reconcile runs detached (`run-shell -b`, or a plain
    shell with no attached client) where "current" is arbitrary or absent — so
    the loop would enumerate one session N times. The consequence is data loss,
    not merely missed repair: `purge` drops any `live` record whose root is in
    `observed.roots` but whose window was not observed, so a `ROOT` row written
    for an unenumerated root deletes every live record in every other project.

    ``ok`` is the rc of that call and nothing else. It is what the caller uses
    to decide whether the root may be asserted as covered.
    """
    rc, out = frozen_ops.run([
        "list-panes", "-s", "-t", tmux_session_target(session),
        "-F", _RECONCILE_FORMAT,
    ])
    if rc != 0:
        return False, []
    panes: list[_Observed] = []
    # NOT `out.strip().splitlines()`: the format's last field is an option that
    # is empty on every unstamped pane, and a whole-buffer strip would eat the
    # final tab and drop the last record (the t1686 shape).
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != _RECONCILE_ARITY:
            continue
        try:
            pane_pid = int(parts[3])
        except ValueError:
            continue
        panes.append(_Observed(
            session=parts[0], window=parts[1], pane_id=parts[2],
            pane_pid=pane_pid, pane_dead=parts[4].strip() == "1",
            path=parts[5], frozen=parts[6].strip(),
            standin_ready=parts[7].strip(), record=parts[8].strip(),
        ))
    return True, panes


def _write_observation(
    roots: dict[str, bool], panes_by_root: dict[str, list[_Observed]]
) -> str:
    """Write the observation file `purge --observed` consumes.

    Protocol (a superset of the marks one): ``ROOT``, ``WINDOW``, ``PANE``,
    ``INCOMPLETE``.

    **Fail-closed rule.** A ``ROOT`` row is an ASSERTION OF COVERAGE, not a list
    of roots we meant to visit. It is emitted only for a root every one of whose
    sessions returned ``rc == 0``; any failure suppresses the row and writes
    ``INCOMPLETE`` instead, which suppresses every sweep. Without this, a
    targeting regression would not merely under-report — it would present an
    unenumerated root as fully observed and let `purge`'s `dead_window` rule
    delete another project's live records.
    """
    fd, path = tempfile.mkstemp(prefix="ait_reconcile_", suffix=".obs")
    incomplete = any(not ok for ok in roots.values())
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for root, ok in sorted(roots.items()):
            if not ok:
                continue
            handle.write(f"ROOT\t{root}\n")
            windows: dict[str, list[_Observed]] = {}
            for pane in panes_by_root.get(root, []):
                windows.setdefault(pane.window, []).append(pane)
            for window, panes in sorted(windows.items()):
                handle.write(f"WINDOW\t{root}\t{window}\n")
                for pane in panes:
                    handle.write(
                        f"PANE\t{root}\t{window}\t{pane.pane_id}"
                        f"\t{pane.pane_pid}\t{1 if pane.pane_dead else 0}\n"
                    )
        if incomplete:
            handle.write("INCOMPLETE\n")
    return path


class _LeaseUnavailable(Exception):
    """A lease could not be taken; ``line`` is what reconcile should report."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.line = line


class _Lease:
    """A LAZY ``lease-take``, taken at most once, only when a verb is due.

    Leasing every non-`live` record up front looks tidier and is wrong in two
    ways. `lease-take` WRITES — it mints a nonce, stamps this process as owner
    and resets `op_started_at` — so a reconcile pass that merely observes a
    healthy `frozen` record and reports ``KEEP`` would still rewrite it every
    600 s. Worse, nothing clears that lease: reconcile exits, its pid dies, and
    the record is left leased by a dead owner. Any real coordinator needing a
    nonce for that record (a `standin-respawned` on a `frozen` record, say) then
    gets `LEASE_HELD` until the grace elapses — reconcile would be locking out
    the very work it exists to enable.

    So the §C rule "every reconcile ACTION on a leased record is preceded by
    `lease-take`" is read literally: no action, no lease. Each handler asks for
    the nonce at the point it is about to issue a verb.
    """

    def __init__(self, record_id: str) -> None:
        self._record_id = record_id
        self._nonce: str | None = None
        self.taken = False

    def __call__(self) -> str:
        """The nonce, taking the lease on first use.

        Raises :class:`_LeaseUnavailable` when the lease is held by a live
        coordinator (`LEASE_HELD`, exit 8 — a normal outcome, not a failure) or
        when the store refused for any other reason.
        """
        if self._nonce is not None:
            return self._nonce
        rc, out = frozen_ops.store("lease-take", self._record_id,
                         "--owner-pid", str(os.getpid()))
        if rc == EXIT_LEASE_HELD:
            raise _LeaseUnavailable(f"LEASE_HELD:{self._record_id}")
        if rc != 0:
            raise _LeaseUnavailable(
                f"RECONCILE_FAILED:{self._record_id}|{out}")
        self._nonce = frozen_ops.nonce_from(out.splitlines()[-1])
        self.taken = True
        return self._nonce


def _respawn_standin(pane_id: str, record_id: str, lease: _Lease) -> str:
    """Clear the ready mark, respawn the stand-in, record the new location.

    The order is fixed: `@aitask_standin_ready` must be cleared BEFORE the
    respawn, or the previous viewer's mark would make the next pass believe the
    new one is already up.

    The lease is taken FIRST, before anything is touched: a respawn we cannot
    then acknowledge would leave the record describing a stand-in that no longer
    exists.
    """
    nonce = lease()
    frozen_ops.unset_option(pane_id, STANDIN_READY_OPTION)
    try:
        command = agent_sessions.standin_command(record_id)
    except ValueError as exc:
        return f"RECONCILE_FAILED:{record_id}|{exc}"
    if not frozen_ops.respawn(pane_id, command):
        return f"RECONCILE_FAILED:{record_id}|respawn refused"
    new_pane, new_pid = frozen_ops.pane_location(pane_id)
    rc, out = frozen_ops.store("standin-respawned", record_id, "--nonce", nonce,
                     "--pane", new_pane, "--pane-pid", str(new_pid))
    if rc != 0:
        return f"RECONCILE_FAILED:{record_id}|{out}"
    return f"STANDIN:{record_id}"


def _reconcile_freezing(rec: dict, observed: _Observed | None, lease: _Lease) -> str:
    """The `freezing` rows of the §C table.

    Three of the table's rows deliberately make NO transition. That is the
    contract, not an oversight: a stamped pane with no ready mark and no
    recognisable pid may be a viewer that is still booting, and transitioning it
    would either abort a freeze that is about to succeed or commit one whose
    viewer never arrives. They are re-checked on the next pass.
    """
    record_id = rec["id"]
    if observed is None:
        # Pane gone (the whole window was closed): commit with the gone-pane
        # pair so the record becomes restorable into a NEW window.
        rc, out = frozen_ops.store("freeze-commit", record_id, "--nonce", lease(),
                         "--pane", "", "--pane-pid", "0")
        return (f"FROZEN:{record_id}|pane_gone" if rc == 0
                else f"RECONCILE_FAILED:{record_id}|{out}")

    stamped = observed.frozen == record_id
    ready = observed.standin_ready == record_id
    agent_alive = observed.pane_pid == frozen_ops.int_or_zero(rec.get("pane_pid"))

    if stamped and ready:
        rc, out = frozen_ops.store("freeze-commit", record_id, "--nonce", lease(),
                         "--pane", observed.pane_id,
                         "--pane-pid", str(observed.pane_pid))
        return (f"FROZEN:{record_id}" if rc == 0
                else f"RECONCILE_FAILED:{record_id}|{out}")

    if stamped and observed.pane_dead:
        return _respawn_standin(observed.pane_id, record_id, lease)

    if agent_alive and not ready:
        # The agent is still running: the freeze died before the respawn. Undo
        # both stamps and put the record back to `live` — captures deleted.
        # The lease FIRST: the two unstamps below are visible to every other
        # observer, so taking them before we know we may act would leave a pane
        # unstamped under a live coordinator's freeze.
        nonce = lease()
        frozen_ops.unset_option(observed.pane_id, FROZEN_OPTION)
        frozen_ops.unset_option(observed.pane_id, STANDIN_READY_OPTION)
        rc, out = frozen_ops.store("freeze-abort", record_id, "--nonce", nonce)
        return (f"LIVE:{record_id}" if rc == 0
                else f"RECONCILE_FAILED:{record_id}|{out}")

    return f"INDETERMINATE:{record_id}|freezing"


def _reconcile_frozen(rec: dict, observed: _Observed | None, lease: _Lease) -> str:
    """The `frozen` rows: keep a gone pane, respawn a dead stand-in."""
    record_id = rec["id"]
    if observed is None:
        return f"KEEP:{record_id}|pane_gone"
    if observed.frozen == record_id and observed.pane_dead:
        return _respawn_standin(observed.pane_id, record_id, lease)
    return f"KEEP:{record_id}|frozen"


def _reconcile_restoring(
    rec: dict, observed: _Observed | None, lease: _Lease, now: float
) -> str:
    """The `restoring` rows of the §C table.

    The restore COORDINATOR is t1705_5; this is only the repair side, and it is
    here because reconcile owns the whole §C table — a `restoring` record whose
    coordinator died has to be settled by somebody, and until t1705_5 lands that
    somebody is the only thing that runs.

    Every branch that gives up ends the same way: `restore-abort` (→ `aborting`,
    still owned by this nonce), then get the STAND-IN back and
    `standin-respawned` (→ `frozen`). The record stays restorable and the
    capture survives — a failed restore must never cost the user the session it
    was trying to bring back.

    Confirming requires POSITIVE evidence: `launch_pid` must be set and must
    equal the observed pid. A viewer, a shell, or an unrelated process in that
    pane is not a restored agent, and the store refuses to treat it as one.
    """
    record_id = rec["id"]
    launch_pid = frozen_ops.int_or_zero(rec.get("launch_pid"))
    standin_pid = frozen_ops.int_or_zero(rec.get("standin_pid"))
    agent_pid = frozen_ops.int_or_zero(rec.get("pane_pid"))
    last_error = rec.get("last_error", "")
    # `last_error` is stamped with the ORIGINAL coordinator's nonce, which is
    # why `rec` must be the PRE-lease read: after `lease-take` the record's
    # `op_nonce` is ours and the prefix would never match.
    mismatch = bool(last_error) and last_error.startswith(
        f"{rec.get('op_nonce', '')}:")

    def _abort_back_to_frozen(pane_id: str | None) -> str:
        nonce = lease()
        rc, out = frozen_ops.store("restore-abort", record_id, "--nonce", nonce)
        if rc != 0:
            return f"RECONCILE_FAILED:{record_id}|{out}"
        if pane_id is None:
            rc, out = frozen_ops.store("standin-respawned", record_id, "--nonce", nonce,
                             "--pane", "", "--pane-pid", "0")
            return (f"STANDIN:{record_id}|pane_gone" if rc == 0
                    else f"RECONCILE_FAILED:{record_id}|{out}")
        return _respawn_standin(pane_id, record_id, lease)

    if observed is None:
        # The window is gone. Abort and record the gone-pane location so the
        # record stays restorable into a NEW window.
        return _abort_back_to_frozen(None)

    if mismatch:
        # The hook reported a DIFFERENT session in `resume` mode. The record is
        # the coordinator's only return channel, and this is what it said:
        # never liveness-confirm past it.
        return _abort_back_to_frozen(observed.pane_id)

    if observed.pane_dead:
        return _abort_back_to_frozen(observed.pane_id)

    if standin_pid and observed.pane_pid == standin_pid:
        # The viewer is still in the pane: the coordinator died before or during
        # its respawn, whether or not the ready mark survived.
        return _abort_back_to_frozen(observed.pane_id)

    if launch_pid and observed.pane_pid == launch_pid:
        # The replacement agent is here. Confirm only once the ack grace has
        # elapsed — before that the hook may still be about to ack, and a
        # liveness confirm would discard the stronger evidence.
        # Through the shared module (t1705_5, amendment B6): the restore
        # coordinator reads the SAME accessor, so the two engines cannot
        # disagree about how long the hook has to ack. A longer grace here would
        # let reconcile confirm a record its coordinator is still polling for.
        if _epoch(rec.get("state_at", "")) + frozen_ops.restore_ack_grace() > now:
            return f"INDETERMINATE:{record_id}|restoring_ack_grace"
        rc, out = frozen_ops.store("restore-confirm", record_id, "--nonce", lease(),
                         "--pane", observed.pane_id,
                         "--pane-pid", str(observed.pane_pid))
        return (f"LIVE:{record_id}|liveness" if rc == 0
                else f"RECONCILE_FAILED:{record_id}|{out}")

    if not launch_pid and observed.pane_pid not in (standin_pid, agent_pid):
        # Nothing was recorded as launched and the pane holds something we do
        # not recognise: the respawn may be mid-flight. Indeterminate until
        # TWICE the grace, then give up and put the viewer back.
        if _epoch(rec.get("state_at", "")) + 2 * _stale_grace() > now:
            return f"INDETERMINATE:{record_id}|restoring"
        return _abort_back_to_frozen(observed.pane_id)

    return f"INDETERMINATE:{record_id}|restoring"


def _reconcile_aborting(rec: dict, observed: _Observed | None, lease: _Lease) -> str:
    """The `aborting` rows: get the stand-in back, then `frozen`."""
    record_id = rec["id"]
    if observed is not None and observed.standin_ready == record_id:
        rc, out = frozen_ops.store("standin-respawned", record_id, "--nonce", lease(),
                         "--pane", observed.pane_id,
                         "--pane-pid", str(observed.pane_pid))
        return (f"STANDIN:{record_id}" if rc == 0
                else f"RECONCILE_FAILED:{record_id}|{out}")
    if observed is None:
        rc, out = frozen_ops.store("standin-respawned", record_id, "--nonce", lease(),
                         "--pane", "", "--pane-pid", "0")
        return (f"STANDIN:{record_id}|pane_gone" if rc == 0
                else f"RECONCILE_FAILED:{record_id}|{out}")
    return _respawn_standin(observed.pane_id, record_id, lease)


def _epoch(iso: str) -> float:
    """`agent_sessions`' timestamp parser, reused rather than re-derived."""
    return agent_sessions._epoch(iso or "")


def _stale_grace() -> float:
    """The store's lease grace, honouring its test seam (t1705_4 step 4a)."""
    return agent_sessions._stale_op_grace()


# --- drop -------------------------------------------------------------------


#: `display-message` could not reach tmux at all (`TmuxClient.run` returns -1 on
#: FileNotFoundError / OSError / timeout). Distinct from tmux ANSWERING that the
#: pane does not exist, which is exit 1 — see :func:`_probe_pane`.
_TMUX_UNREACHABLE = -1


def _probe_pane(pane_id: str) -> tuple[str, dict[str, str] | None]:
    """Ask tmux about ONE pane. Returns ``(verdict, facts)``.

    Verdicts: ``"present"`` (facts are the pane's), ``"gone"`` (tmux answered
    that no such pane exists — including "no server running", which means the
    same thing), or ``"unknown"`` (tmux could not be reached at all).

    The three are kept apart deliberately. Collapsing ``unknown`` into ``gone``
    is the mistake that reintroduces V9: a coordinator that cannot reach tmux
    would conclude the stand-in is already gone, skip the kill, and delete the
    record and its only capture while a live stamped viewer is still sitting in
    that pane — the one state `reconcile` cannot repair, because it iterates
    records and that pane no longer has one.

    Asking about the pane directly, rather than looking for it in a window
    listing, also means the answer does not depend on the record's `session` /
    `window` fields still being current: those are display values, and a tmux
    restart or a rename makes a window-scoped lookup miss a pane that is very
    much alive.
    """
    rc, out = frozen_ops.run(
        ["display-message", "-p", "-t", pane_id,
         "\t".join(["#{pane_id}", f"#{{{FROZEN_OPTION}}}", "#{pane_dead}"])]
    )
    if rc == _TMUX_UNREACHABLE:
        return "unknown", None
    if rc != 0:
        return "gone", None
    parts = (out.splitlines() or [""])[0].split("\t")
    if len(parts) != 3 or not parts[0].strip():
        return "gone", None
    return "present", {
        "pane_id": parts[0].strip(),
        "frozen": parts[1].strip(),
        "dead": parts[2].strip(),
    }


def _other_real_agents(pane_id: str) -> int | None:
    """Sibling count for the kill rule; ``None`` when it could not be taken.

    **Enumerated from the TARGET PANE, never from the record's stored
    `session` / `window`.** Those two fields are display values: a pane can be
    moved (`break-pane`, `join-pane`) or its window renamed, and the old name
    can be taken by a different window entirely. Counting siblings in window A
    and then issuing `kill-window -t <pane in window B>` — which is what a
    stored-name lookup permits — reads "no siblings" for a window that is not
    the one about to die, and destroys the live agents in the one that is.
    `list-panes -t <pane-id>` resolves to that pane's own window, so the count
    and the kill can never disagree about which window they mean.

    `monitor_core.classify_window_panes` is the one definition of "does this
    pane keep the window alive". Calling it here makes the coordinator a second
    CALL SITE of that rule rather than a fourth implementation of it — there are
    already three (`aitask_companion_cleanup.sh`, `kill_agent_pane_smart`, and
    the fixture in `tests/test_cleanup_rule_parity.sh`, which exists *because*
    of that duplication).

    ``None`` is not 0. A failed listing that counted as "no siblings" would
    collapse a window that may still hold a live agent; the caller downgrades to
    `kill-pane` instead, which is the conservative half of the same rule.
    """
    rc, out = frozen_ops.run(
        ["list-panes", "-t", pane_id, "-F", FROZEN_AWARE_PANE_FORMAT]
    )
    if rc != 0:
        return None
    panes = classify_window_panes(out)
    if not any(wp.pane_id == pane_id for wp in panes):
        # The listing did not contain the pane we are about to kill, so it is
        # not that pane's window. Fail conservative rather than count it.
        return None
    return count_other_real_agents(
        [(wp.pane_id, wp.is_helper) for wp in panes], pane_id
    )


def drop_record(record_id: str) -> str:
    """Remove a frozen record, its capture, and its stand-in pane.

    THE ORDER IS THE DESIGN. `drop` deletes the only copy of an agent's output,
    so the irreversible step goes LAST and every intermediate state is one
    reconcile already repairs:

      0. **claim** the record (`lease-take`). Atomic under the store's write
         lock, and it already encapsulates the staleness rule — held by a live
         coordinator => `LEASE_HELD`, held by a dead one => taken over, so a
         crash can never make a record permanently undroppable.
      1. **preflight** the live pane inventory to resolve the target. The
         record's `pane_id` is durable but NOT authoritative: `_reconcile_frozen`
         returns `KEEP:<id>|pane_gone` and writes nothing, so after a tmux
         restart every retained record still names a `%N` that no longer exists.
         Keying "nothing to kill" on an empty `pane_id` would make exactly those
         records undroppable.
      2. **kill** the stand-in. Pane options are pane-scoped and die with the
         pane, so this retires all three stamps with no unstamp step to fail. A
         failed kill changes NOTHING: the user keeps a working viewer and an
         intact capture.
      3. **store**, and only after the target is verified gone, with the claimed
         nonce. A `NONCE_MISMATCH` here means somebody minted a new lease while
         we were killing — the record and capture survive, which is the point.

    The one residual, accepted deliberately: the kill cannot be made
    conditional, so a restore beginning between step 2 and step 3 costs the user
    the *stand-in pane* — never the record and never the capture. The record
    stays restorable into a fresh window (`_reconcile_frozen`'s
    `KEEP:<id>|pane_gone`). Losing a replaceable viewer is the right trade
    against losing the only copy of a session's output; do not "fix" it by
    reordering.
    """
    lease = _Lease(record_id)
    try:
        _drop_fail_at("claim")
        nonce = lease()
    except _LeaseUnavailable as exc:
        if exc.line.startswith("LEASE_HELD:"):
            return f"DROP_REFUSED:{record_id}|in_flight"
        return f"DROP_FAILED:{record_id}|claim:{exc.line}"
    except frozen_ops.StageFailure as exc:
        return f"DROP_FAILED:{record_id}|{exc.stage}"

    def _release() -> None:
        """Give the claim back so a retry is immediate, not grace-delayed."""
        frozen_ops.store("lease-release", record_id, "--nonce", nonce)

    try:
        _drop_fail_at("preflight")
        rec = frozen_ops.store_show(record_id)
        if not rec:
            _release()
            return f"DROP_FAILED:{record_id}|no_record"
        pane_id = rec.get("pane_id", "")

        # Resolve the target against what the SERVER says, never the record
        # alone: `pane_id` is durable but not authoritative (see the docstring).
        must_kill = False
        if pane_id:
            verdict, facts = _probe_pane(pane_id)
            if verdict == "unknown":
                _release()
                return f"DROP_FAILED:{record_id}|preflight:tmux unreachable"
            if verdict == "present":
                if facts and facts["frozen"] == record_id:
                    must_kill = True
                # else: a recycled `%N`. Pane options die with the pane, so a
                # recycled pane cannot carry our stamp — which is what makes the
                # stamp the authoritative identity join (§B). Leave it alone;
                # killing it would destroy somebody else's work.

        if must_kill:
            _drop_fail_at("kill")
            others = _other_real_agents(pane_id)
            # `None` (the listing failed) downgrades to kill-pane rather than
            # collapsing a window that may still hold a live agent.
            verb = "kill-window" if others == 0 else "kill-pane"
            rc, out = frozen_ops.run([verb, "-t", pane_id])
            if rc != 0:
                _release()
                return f"DROP_FAILED:{record_id}|kill:{out.strip() or verb}"

            _drop_fail_at("verify")
            verdict, _ = _probe_pane(pane_id)
            if verdict != "gone":
                _release()
                return (f"DROP_FAILED:{record_id}|kill:pane not verified gone "
                        f"({verdict})")

        frozen_ops.pause_at("drop_pre_store")
        _drop_fail_at("store")
        rc, out = frozen_ops.store("drop", record_id, "--nonce", nonce)
        if rc == EXIT_NONCE_MISMATCH:
            # Somebody minted a new lease over ours while we were killing. The
            # record and its capture SURVIVE — that is what the leased form
            # buys, and what a snapshotted `(state, op_nonce)` comparison could
            # not: an `aborting -> frozen` recovery clears the nonce and would
            # have restored the identical pair.
            return f"DROP_ABORTED:{record_id}|raced"
        if rc != 0:
            _release()
            return f"DROP_FAILED:{record_id}|store:{out.strip()}"
        return f"DROPPED:{record_id}"
    except frozen_ops.StageFailure as exc:
        _release()
        return f"DROP_FAILED:{record_id}|{exc.stage}"


def reconcile() -> list[str]:
    """Resolve every non-`live` record from server-observable facts (§C).

    Idempotent and safe to call every 600 s (t1705_7 dispatches it from the
    monitor maintenance tick). Returns the wire lines it produced.

    The whole §C table is here, `restoring` rows included, even though the
    restore COORDINATOR is t1705_5: a `restoring` record whose coordinator died
    has to be settled by something, and reconcile is the only thing that runs.
    Nothing can produce such a record until t1705_5 ships `restore-begin`'s
    caller, so those rows are unreachable today — but they are unit-tested, and
    writing them later would mean re-deriving the table from the plan twice.
    """
    lines: list[str] = []
    now = agent_sessions._now()

    # 1. One explicitly targeted pass per session; remember which SUCCEEDED.
    roots: dict[str, bool] = {}
    panes_by_root: dict[str, list[_Observed]] = {}
    observed_by_pane: dict[str, _Observed] = {}
    for session in discover_aitasks_sessions():
        root = os.path.realpath(str(session.project_root))
        ok, panes = _enumerate_session(session.session)
        # A root covered by two sessions is fully observed only if BOTH
        # enumerations succeeded — `and` never upgrades a prior failure.
        roots[root] = roots.get(root, True) and ok
        if not ok:
            continue
        panes_by_root.setdefault(root, []).extend(panes)
        for pane in panes:
            observed_by_pane[pane.pane_id] = pane

    # 2. Apply the §C table to every non-`live` record whose lease is takeable.
    rc, out = frozen_ops.store("list")
    if rc != 0:
        lines.append(f"RECONCILE_FAILED:list|{out}")
    else:
        for line in out.splitlines():
            if not line.startswith("SESSION:"):
                continue
            fields = line[len("SESSION:"):].split("|")
            if len(fields) < 2:
                continue
            record_id, state = fields[0], fields[1]
            if state == agent_sessions.STATE_LIVE:
                continue
            # READ BEFORE LEASING. `lease-take` overwrites `op_nonce`, and the
            # `restoring` mismatch row matches `last_error` against the ORIGINAL
            # coordinator's nonce — after a lease that comparison can never
            # match, and a reported session mismatch would be silently ignored.
            rec = frozen_ops.store_show(record_id)
            if not rec:
                continue
            observed = observed_by_pane.get(rec.get("pane_id", ""))
            # LAZY: the handlers take the lease only if they are about to issue
            # a verb, so a healthy `frozen` record is observed and reported
            # without being written to. See `_Lease`.
            lease = _Lease(record_id)
            try:
                if state == agent_sessions.STATE_FREEZING:
                    lines.append(_reconcile_freezing(rec, observed, lease))
                elif state == agent_sessions.STATE_FROZEN:
                    lines.append(_reconcile_frozen(rec, observed, lease))
                elif state == agent_sessions.STATE_RESTORING:
                    lines.append(_reconcile_restoring(rec, observed, lease, now))
                elif state == agent_sessions.STATE_ABORTING:
                    lines.append(_reconcile_aborting(rec, observed, lease))
            except _LeaseUnavailable as exc:
                # A live coordinator owns this record (or the store refused).
                # Reported, never worked around.
                lines.append(exc.line)

    # 3. Retire dead records. LAST, so the repairs above are already reflected.
    obs_path = _write_observation(roots, panes_by_root)
    try:
        rc, out = frozen_ops.store("purge", "--observed", obs_path)
        if rc == 0:
            lines.extend(out.splitlines())
        else:
            lines.append(f"RECONCILE_FAILED:purge|{out}")
    finally:
        try:
            os.unlink(obs_path)
        except OSError:
            pass
    return lines


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: agent_freeze.py freeze <pane>|--all | drop <id> | reconcile",
              file=sys.stderr)
        return 2
    verb, rest = argv[0], argv[1:]

    if verb == "freeze":
        if rest and rest[0] == "--all":
            results = freeze_all()
        elif rest:
            results = [freeze_pane(rest[0])]
        else:
            print("usage: agent_freeze.py freeze <pane_id>|--all",
                  file=sys.stderr)
            return 2
        for result in results:
            print(result.line)
        # An empty batch is a success: there was nothing to freeze.
        return 0 if all(r.ok for r in results) else 1

    if verb == "drop":
        if len(rest) != 1:
            print("usage: agent_freeze.py drop <record-id>", file=sys.stderr)
            return 2
        line = drop_record(rest[0])
        print(line)
        return 0 if line.startswith("DROPPED:") else 1

    if verb == "reconcile":
        for line in reconcile():
            print(line)
        return 0

    print(f"unknown verb: {verb}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
