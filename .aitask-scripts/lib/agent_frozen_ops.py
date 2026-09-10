#!/usr/bin/env python3
"""Store-wrapper and tmux plumbing shared by the frozen-agent engines (t1738).

Imported by `lib/agent_freeze.py` (the freeze transaction + the §C reconcile
repair table) and by `lib/agent_restore.py` (the restore coordinator, t1705_5).
It exists so the two engines *share* the store's wire protocol rather than
forking it: the verb names, the argument shapes, the `NONCE_MISMATCH` /
`TRANSITION_REFUSED` / `LEASE_HELD` exit codes and the failure-injection seam
names are defined once, here.

**The dependency arrow runs ONE way.** This module must never import
`agent_freeze` or `agent_restore` — and it deliberately does not import
`agent_sessions` either. `agent_freeze.py`'s reconcile has to keep settling
abandoned restores with **no coordinator present**, so nothing it depends on may
reach back toward the coordinator.

Two hard boundaries, both load-bearing, are owned here:

1. **Every tmux call goes through `TmuxClient`** (`lib/tmux_exec.py`), the
   sanctioned gateway. `tests/test_no_raw_tmux.sh` enforces it.
2. **Every store WRITE goes through the shell wrapper**
   (`aitask_agent_sessions.sh`), never by importing `agent_sessions`' mutators.
   The wrapper is the store's sole writer because it holds the mutex around the
   read-modify-write; importing the transition functions would write unlocked
   and lose updates. Reads (`show` / `list`) go through the same wrapper for one
   parsing path, even though they take no lock.

THE SEAM RULE — state and behaviour through the module; pure names by import.
:data:`_TMUX` and :func:`store` are **swapped in place** by the unit tests
(`tests/test_agent_frozen_ops.py`, `tests/test_agent_freeze.py`) so the engines
can run with no tmux and no store file. Both are looked up as *this* module's
globals at call time, so one swap redirects every consumer — including
:func:`store_show`, which calls `store(...)`, and every helper that calls
:func:`run`.

Consequently an engine must call these functions **through the module**::

    import agent_frozen_ops as frozen_ops
    rc, out = frozen_ops.store("show", record_id)     # correct

and must NEVER import-alias the swapped names::

    from agent_frozen_ops import store as _store      # WRONG: binds the
                                                      # original object and
                                                      # silently misses the swap

`tests/test_agent_frozen_ops.py` enforces that rule directly: it fails if any
engine module holds a global bound to the original `store` / `_TMUX` object.
Constants (:data:`SESSIONS_SH`, the `EXIT_*` codes, :data:`PANE_FACT_FORMAT`,
:data:`PANE_FACT_KEYS`) and the :class:`StageFailure` class are never swapped and
may be imported by name.

Test seams, honoured **only** under ``AITASKS_TEST_MODE=1``:

* :func:`make_fail_at` builds a per-engine ``fail_at`` bound to one environment
  variable — ``AITASKS_FREEZE_FAIL_AT`` for the freeze engine,
  ``AITASKS_RESTORE_FAIL_AT`` for the restore coordinator — so each engine's
  injected failures cannot fire in the other;
* :func:`pause_at` reads the shared ``AITASKS_FROZEN_PAUSE_AT``, which names a
  stage in whichever engine is running.
"""

from __future__ import annotations

import os
import secrets
import signal
import subprocess
import sys
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _LIB_DIR.parent
for _p in (str(_SCRIPTS_DIR), str(_LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from monitor.monitor_core import (  # noqa: E402
    FROZEN_OPTION,
    RECORD_OPTION,
    RESPAWN_TOKEN_OPTION,
    STANDIN_READY_OPTION,
    AGENT_SESSION_OPTION,
)
from tmux_exec import TmuxClient  # noqa: E402
from config_utils import load_yaml_config  # noqa: E402

#: The gateway client. SWAPPED BY TESTS — read it through :func:`run` (or as a
#: module global from inside this file), never by import-aliasing it elsewhere.
_TMUX = TmuxClient()

#: The store's sole writer. Invoked as a subprocess, never imported (see the
#: module docstring).
SESSIONS_SH = _SCRIPTS_DIR / "aitask_agent_sessions.sh"

#: Wrapper exit codes the engines branch on. The full table is in
#: `aitask_agent_sessions.sh`'s header.
EXIT_LOCK_BUSY = 3
EXIT_TRANSITION_REFUSED = 5
EXIT_NONCE_MISMATCH = 6
EXIT_LEASE_HELD = 8


class StageFailure(Exception):
    """Injected failure at a named stage (test seam only)."""

    def __init__(self, stage: str) -> None:
        super().__init__(f"injected failure at {stage}")
        self.stage = stage


# --- the restore acknowledgement grace --------------------------------------

#: Seconds a `restoring` record is given to be acknowledged by its replacement
#: agent's SessionStart hook before it may be liveness-confirmed instead (§C/§D).
#: The hook ack is strictly better evidence — it verifies the resumed session id,
#: which is what permits deleting the only copy of the capture — so confirming
#: early would trade the strong signal for the weak one.
RESTORE_ACK_GRACE = 20.0


def restore_ack_grace(root: "str | os.PathLike | None" = None) -> float:
    """`frozen.restore_ack_grace`, with a TEST-ONLY env seam (t1705_5).

    Precedence: ``AITASKS_RESTORE_ACK_GRACE`` (only under
    ``AITASKS_TEST_MODE=1``) > ``frozen.restore_ack_grace`` in the project's
    ``aitasks/metadata/project_config.yaml`` > :data:`RESTORE_ACK_GRACE`.
    Non-positive and unparseable values at either layer fall back to the default.

    **It lives here, in the SHARED module, on purpose.** Both the restore
    coordinator (`agent_restore`) and reconcile (`agent_freeze`) read it, and
    they must not be able to disagree: if reconcile used a longer grace than the
    coordinator, it could liveness-confirm a record the coordinator is still
    polling for, moving it to `live` behind the coordinator's back so its next
    verb fails `NONCE_MISMATCH` and the user's restore is silently lost. Hosting
    it in `agent_freeze` instead would force the coordinator to import the repair
    module for one function — the exact one-way-arrow violation this module
    exists to prevent (t1738; parent-plan amendment B6).

    The env seam is gated on test mode for the same reason
    ``agent_sessions._stale_op_grace`` is: a stray variable in a developer's
    shell must never reconfigure a real coordinator's ack window. It shortens
    only the *waiting* half — it is not a way to skip the hook ack, which is
    still strictly preferred whenever it arrives first.
    """
    if test_mode():
        raw = os.environ.get("AITASKS_RESTORE_ACK_GRACE", "")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value

    base = Path(root) if root else Path.cwd()
    cfg_path = base / "aitasks" / "metadata" / "project_config.yaml"
    try:
        cfg = load_yaml_config(cfg_path, {})
    except Exception:
        # Broad on purpose, mirroring `agent_freeze.capture_max_lines`: this runs
        # mid-restore, and a malformed or unreadable project config must degrade
        # to the default rather than abort a transaction that has already
        # respawned the user's agent pane.
        return RESTORE_ACK_GRACE
    section = cfg.get("frozen") if isinstance(cfg, dict) else None
    if not isinstance(section, dict):
        return RESTORE_ACK_GRACE
    try:
        configured = float(section.get("restore_ack_grace", RESTORE_ACK_GRACE))
    except (TypeError, ValueError):
        return RESTORE_ACK_GRACE
    return configured if configured > 0 else RESTORE_ACK_GRACE


#: Slack added on top of dispatch + ack grace before a watcher gives up on a
#: restore. It absorbs the store write and the watcher's own poll cadence, not
#: the coordinator's waiting — that part is :func:`restore_ack_grace`.
RESTORE_SETTLE_SLACK = 10.0


def restore_settle_timeout(root: "str | os.PathLike | None" = None, *,
                           dispatch_grace: float) -> float:
    """How long a UI may watch a dispatched restore before reporting a stall.

    A watcher's deadline must be derived from the coordinator's OWN waiting,
    never fixed: `agent_restore` gives a `restoring` record up to
    :func:`restore_ack_grace` seconds to be acknowledged by its replacement
    agent's SessionStart hook before it may be liveness-confirmed instead. A
    watcher whose deadline is shorter than that grace warns and stops its timer
    while the restore is still legitimately in flight, so a project that raised
    the grace gets a spurious "still restoring" on every successful restore and
    never sees the success.

    At the default grace this returns exactly the 40.0s the first watcher
    hardcoded (10 dispatch + 20 ack + 10 slack) — the value was right for the
    default and wrong as a constant.
    """
    return dispatch_grace + restore_ack_grace(root) + RESTORE_SETTLE_SLACK


# --- seams ------------------------------------------------------------------


def test_mode() -> bool:
    return os.environ.get("AITASKS_TEST_MODE") == "1"


def make_fail_at(env_var: str):
    """Build a ``fail_at(stage)`` seam bound to ``env_var``.

    Each engine gets its own variable (`AITASKS_FREEZE_FAIL_AT`,
    `AITASKS_RESTORE_FAIL_AT`) so a test injecting a failure into one engine
    cannot trip the other — the two run in the same process during a live
    freeze-then-restore sequence.
    """

    def fail_at(stage: str) -> None:
        """Raise when the fail seam names this stage. No-op outside test mode."""
        if test_mode() and os.environ.get(env_var) == stage:
            raise StageFailure(stage)

    fail_at.env_var = env_var       # introspectable; nothing branches on it
    return fail_at


def pause_at(stage: str) -> None:
    """SIGSTOP self when the pause seam names this stage.

    Stopping THIS process (rather than sleeping) is what makes the paused-owner
    lease case honest: `_pid_alive` is fail-closed and a stopped process is
    alive, so a concurrent `reconcile` must refuse takeover no matter how much
    grace has elapsed. A sleep would prove the same thing only by accident.
    """
    if test_mode() and os.environ.get("AITASKS_FROZEN_PAUSE_AT") == stage:
        os.kill(os.getpid(), signal.SIGSTOP)


# --- tmux gateway -----------------------------------------------------------


def run(args: list[str], timeout: float | None = None) -> tuple[int, str]:
    """`TmuxClient.run` through the swappable module-level client.

    The one place the engines reach tmux. Passing ``timeout=None`` uses the
    client's own default rather than forcing a value, so the gateway keeps
    ownership of that policy.
    """
    if timeout is None:
        return _TMUX.run(args)
    return _TMUX.run(args, timeout=timeout)


# --- store wrapper ----------------------------------------------------------


def store(*argv: str, timeout: float = 20.0) -> tuple[int, str]:
    """Run the store wrapper. Returns ``(rc, output)``; never raises.

    The wrapper folds its stderr into stdout already, so one stream carries both
    the success line and the refusal line. A spawn failure is reported as
    ``(1, "ERROR:...")`` rather than propagating, because every caller is
    mid-transaction and needs to reach its rollback rather than a traceback.
    """
    try:
        proc = subprocess.run(
            [str(SESSIONS_SH), *argv],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"ERROR:{exc}"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def store_show(record_id: str) -> dict[str, str]:
    """``show <id>`` as a dict; ``{}`` when the record is gone or unreadable."""
    rc, out = store("show", record_id)
    if rc != 0:
        return {}
    fields: dict[str, str] = {}
    for line in out.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def nonce_from(line: str) -> str:
    """The nonce in a ``FREEZING:<id>|<nonce>`` / ``LEASED:<id>|<nonce>`` line."""
    _, _, tail = line.partition("|")
    return tail.strip()


# --- tmux helpers -----------------------------------------------------------

PANE_FACT_FORMAT = "\t".join([
    "#{session_name}", "#{window_name}", "#{pane_id}", "#{pane_pid}",
    "#{pane_dead}", "#{pane_current_path}",
    f"#{{{RECORD_OPTION}}}", f"#{{{FROZEN_OPTION}}}",
    f"#{{{STANDIN_READY_OPTION}}}", f"#{{{AGENT_SESSION_OPTION}}}",
])
PANE_FACT_KEYS = (
    "session", "window", "pane_id", "pane_pid", "pane_dead", "path",
    "record", "frozen", "standin_ready", "agent_session",
)


def pane_facts(pane_id: str) -> dict[str, str]:
    """Every fact a transaction needs about a pane, in ONE round trip.

    `display-message -p` against a specific `-t` target is the shape
    `aitask_shadow_capture.sh` established for self-identification: one call, a
    tab-joined format, positional read. Returns ``{}`` when the pane is gone —
    which is a legitimate observation, not an error.
    """
    rc, out = run(["display-message", "-p", "-t", pane_id, PANE_FACT_FORMAT])
    if rc != 0:
        return {}
    line = out.splitlines()[0] if out.splitlines() else ""
    parts = line.split("\t")
    if len(parts) != len(PANE_FACT_KEYS):
        return {}
    return {k: v.strip() for k, v in zip(PANE_FACT_KEYS, parts)}


def pane_location(pane_id: str) -> tuple[str, int]:
    """``(pane_id, pane_pid)`` after a respawn; ``("", 0)`` when the pane is gone.

    ``("", 0)`` is exactly the gone-pane pair `freeze-commit` documents, so the
    caller can pass this through unmodified.
    """
    rc, out = run(["display-message", "-p", "-t", pane_id,
                   "#{pane_id}\t#{pane_pid}"])
    if rc != 0:
        return "", 0
    parts = (out.splitlines() or [""])[0].split("\t")
    if len(parts) != 2 or not parts[0].strip():
        return "", 0
    try:
        return parts[0].strip(), int(parts[1].strip())
    except ValueError:
        return "", 0


def set_option(pane_id: str, option: str, value: str) -> bool:
    rc, _ = run(["set-option", "-p", "-t", pane_id, option, value])
    return rc == 0


def unset_option(pane_id: str, option: str) -> bool:
    rc, _ = run(["set-option", "-pu", "-t", pane_id, option])
    return rc == 0


#: `TmuxClient.run`'s rc when tmux could not be reached AT ALL —
#: `FileNotFoundError` / `OSError` / timeout. Distinct from a non-zero rc, which
#: is tmux answering "no such pane". See :func:`probe_pane`.
TMUX_UNREACHABLE = -1

#: The three facts :func:`probe_pane` reads, as one tab-joined format.
PROBE_PANE_FORMAT = "\t".join(
    ["#{pane_id}", f"#{{{FROZEN_OPTION}}}", "#{pane_dead}"])
PROBE_PANE_KEYS = ("pane_id", "frozen", "dead")


def probe_pane(pane_id: str) -> tuple[str, dict[str, str] | None]:
    """Ask tmux about ONE pane. Returns ``(verdict, facts)``.

    Verdicts: ``"present"`` (facts are the pane's), ``"gone"`` (tmux answered
    that no such pane exists — including "no server running", which means the
    same thing), or ``"unknown"`` (tmux could not be reached at all).

    The three are kept apart deliberately. Collapsing ``unknown`` into ``gone``
    is the mistake that reintroduces V9: a coordinator that cannot reach tmux
    would conclude the stand-in is already gone, skip the kill, and delete the
    record and its only capture while a live stamped viewer is still sitting in
    that pane — the one state `reconcile` cannot repair, because it iterates
    records and that pane no longer has one. The restore router (t1773) needs
    the same distinction for the mirror-image reason: reading an unreachable
    tmux as "gone" would launch a SECOND agent into a new window while the
    original stand-in is still alive.

    Asking about the pane directly, rather than looking for it in a window
    listing, also means the answer does not depend on the record's `session` /
    `window` fields still being current: those are display values, and a tmux
    restart or a rename makes a window-scoped lookup miss a pane that is very
    much alive.

    Shared surface (t1773): `agent_freeze.drop_record` preflights its
    destructive kill with this, and `agent_restore.restore` routes on it. It
    lives here because `agent_restore` must not import `agent_freeze`.
    """
    rc, out = run(["display-message", "-p", "-t", pane_id, PROBE_PANE_FORMAT])
    if rc == TMUX_UNREACHABLE:
        return "unknown", None
    if rc != 0:
        return "gone", None
    parts = (out.splitlines() or [""])[0].split("\t")
    if len(parts) != len(PROBE_PANE_KEYS) or not parts[0].strip():
        return "gone", None
    return "present", {k: v.strip() for k, v in zip(PROBE_PANE_KEYS, parts)}


def tmux_quote(s: str) -> str:
    r"""Quote a command string for tmux's OWN lexer.

    `if-shell` takes its branch as a single string that the tmux server then
    parses as commands, so a command that has already been shell-quoted needs
    one more level. The double-quote form with backslash escaping of ``\``,
    ``"`` and ``$`` was measured (t1773) to round-trip a command containing
    ``'``, ``"``, ``$``, ``;`` and ``>`` into the pane's `pane_start_command`
    unchanged. tmux single-quotes are fully literal with no escape, so they
    cannot carry a command that itself contains a single quote — which the
    agent command strings routinely do.
    """
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$") + '"'


#: The four after-facts :func:`respawn_if_stamped` reads in ONE round trip.
RESPAWN_PROBE_FORMAT = "\t".join(
    [f"#{{{RESPAWN_TOKEN_OPTION}}}", "#{pane_id}", "#{pane_pid}", "#{pid}"])


def respawn_if_stamped(
    pane_id: str,
    command: str,
    *,
    option: str,
    expect: str,
    env: dict[str, str] | None = None,
    unset: str | None = None,
) -> tuple[bool, str, int, str]:
    """`respawn-pane -k`, but ONLY if the pane still carries ``option == expect``.

    Returns ``(fired, pane_id, pane_pid, reason)``.

    THE CHECK AND THE KILL TRAVEL AS ONE DISPATCH. `if-shell -F` makes the
    server evaluate the stamp and run the branch inside a single command-queue
    execution, so nothing can interleave between them. A two-call
    probe-then-respawn leaves a window a tmux SERVER RESTART can slip through:
    pane ids are monotonic within a server and never reused, but a restarted
    server renumbers from ``%0``, so a recorded ``%N`` can come back owned by an
    unrelated live agent — and `respawn-pane -k` would kill it.

    `if-shell` exits 0 whether or not its branch ran, so "did it fire" needs
    evidence. **A pid delta is NOT that evidence.** The same restart window
    makes the before-read describe the old stamped pane and the after-read an
    unrelated recycled ``%N``, so a correctly REJECTED dispatch still shows a
    changed pid. A caller that read that as success would record a stranger's
    pid as `launch_pid`, and `restore-confirm` would then liveness-confirm
    somebody else's agent as the restored one.

    The evidence is therefore POSITIVE and BRANCH-SPECIFIC: a fresh per-call
    token written by a `set-option` that is the LAST command of the matched
    branch. Pane options die with the pane, so a recycled ``%N`` cannot carry
    it; a rejected branch never runs it; and an `if-shell` sequence aborts after
    a failing command, so the token also proves the respawn ahead of it
    succeeded. **Absent token ⇒ nothing was touched**, and the caller is handed
    no location at all — ``("", 0)`` — so it cannot adopt a stranger's pane even
    by accident.

    ``reason`` names why a non-firing dispatch did not fire —
    ``stamp-mismatch``, ``server-restarted`` or ``pane-gone``. It is diagnostic
    only; the token alone decides.

    ``unset`` clears one pane option inside the same branch, ahead of the
    respawn (the stand-in-ready mark, which survives `respawn-pane` and would
    otherwise read as "this cycle's viewer is already up").
    """
    rc, out = run(["display-message", "-p", "-t", pane_id, "#{pid}"])
    if rc != 0:
        return False, "", 0, "pane-gone"
    server_before = (out.splitlines() or [""])[0].strip()

    token = secrets.token_hex(8)
    inner: list[str] = []
    if unset:
        inner.append(f"set-option -pu -t {pane_id} {unset}")
    respawn_cmd = ["respawn-pane", "-k"]
    for name, value in (env or {}).items():
        respawn_cmd += ["-e", f"{name}={value}"]
    respawn_cmd += ["-t", pane_id, tmux_quote(command)]
    inner.append(" ".join(respawn_cmd))
    # LAST, so its presence also proves the respawn ahead of it succeeded.
    inner.append(f"set-option -p -t {pane_id} {RESPAWN_TOKEN_OPTION} {token}")

    pause_at("respawn_dispatch")
    run(["if-shell", "-F", "-t", pane_id,
         f"#{{==:#{{{option}}},{expect}}}", " ; ".join(inner)])

    rc, out = run(["display-message", "-p", "-t", pane_id, RESPAWN_PROBE_FORMAT])
    if rc != 0:
        return False, "", 0, "pane-gone"
    parts = (out.splitlines() or [""])[0].split("\t")
    if len(parts) != 4:
        return False, "", 0, "pane-gone"
    seen_token, new_pane, new_pid, server_after = (p.strip() for p in parts)
    if seen_token and seen_token == token:
        unset_option(pane_id, RESPAWN_TOKEN_OPTION)
        return True, new_pane, int_or_zero(new_pid), ""
    if server_after != server_before:
        return False, "", 0, "server-restarted"
    return False, "", 0, "stamp-mismatch"


def respawn(pane_id: str, command: str, env: dict[str, str] | None = None) -> bool:
    """`respawn-pane -k` the pane into ``command``.

    ``-k`` kills whatever is running there first. t1705_1 measured that this
    fires NO `pane-died` hook — window, companion pane and the pane id all
    survive — which is why the freeze can reuse the agent's own pane at all.

    ``env`` adds one ``-e NAME=value`` flag per entry (t1705_5), which is how the
    restore coordinator delivers the four ``AITASK_RESTORE_*`` identity variables
    to the replacement agent. tmux sets them in the spawned process's own
    environment, so the command string carries no wrapper and nothing execs
    through ``env`` — and crucially ``#{pane_pid}`` still names the agent itself,
    which is the property the task-lock liveness anchor depends on (t1465).
    Measured for one variable by spike Case 3b and for four repeated flags by
    Case 3c; the ``env VAR=… <cmd>`` command-string prefix remains the proven
    fallback for a tmux build without ``-e``.
    """
    args = ["respawn-pane", "-k"]
    for name, value in (env or {}).items():
        args += ["-e", f"{name}={value}"]
    args += ["-t", pane_id, command]
    rc, _ = run(args)
    return rc == 0


# --- record-field parsing ---------------------------------------------------


def int_or_zero(value) -> int:
    """Coerce a store record's numeric field; ``0`` for missing or malformed.

    Zero is the store's own "not recorded" pid, so an unparsable field and an
    absent one degrade to the same value the state machine already treats as
    "no evidence".
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
