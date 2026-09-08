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
