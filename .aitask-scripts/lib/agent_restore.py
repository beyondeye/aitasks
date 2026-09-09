#!/usr/bin/env python3
"""Restore coordinator for frozen code agents (t1705_5).

Turns a frozen stand-in pane back into a running code agent: relaunch the
captured session with `claude --resume <sid>` / `codex resume <sid>` (or, with
``--repick``, a fresh `/aitask-pick <task_id>`), then wait for a **verified
acknowledgement** that the agent which came up is the one that was asked for.

Two entry points, both reached through `aitask_frozen.sh restore`:

* :func:`restore`     — one record, the §D two-phase transaction below;
* :func:`restore_all` — every `frozen` record, sequentially; one failure never
  stops the batch.

THREE PROPERTIES MAKE THIS SAFE, and each one is easy to break:

1. **A restore never runs inside the pane it replaces.** The caller detaches it
   with ``run-shell -b``, which t1705_1 measured to outlive the pane that
   started it, so this process survives respawning the very pane its caller was
   in. There is deliberately no ``setsid``: ``run-shell -b`` already detaches,
   and staying in the foreground means a shell user sees the result line.
2. **tmux accepting the respawn proves nothing.** `respawn-pane` succeeds
   whether the agent starts, exits instantly, or resumes the *wrong* session.
   Only the replacement's own SessionStart hook — which forwards the record id
   and nonce and lets the store compare the resumed session id — is evidence.
   That is why the captures are deleted **only** on ``ack=hook``; a liveness
   confirm keeps them.
3. **A REFUSED store verb is not a failure.** Every transitional verb is
   state-guarded, and the replacement agent's hook can legitimately win the race
   and move the record `restoring -> live` before this process finishes its
   `display-message` round-trip. `restore-launched` is then refused with
   ``TRANSITION_REFUSED``. Reading that as failure would send this code down the
   rollback branch and ``respawn-pane -k`` the pane back to the stand-in —
   **killing an agent that was just successfully restored**, which is strictly
   worse than never restoring at all. So: check the exit status of every store
   verb, and on any non-zero exit RE-READ the record before deciding anything.

The store's wire protocol and all tmux plumbing come from the SHARED module
`lib/agent_frozen_ops.py` (t1738), which the freeze engine imports too, so the
two engines cannot fork the protocol. Those helpers are called **through the
module** (``frozen_ops.store(...)``) and never import-aliased: the tests swap
``agent_frozen_ops.store`` and ``agent_frozen_ops._TMUX`` in place, and an alias
would bind the original object and miss the swap. `tests/test_agent_frozen_ops.py`
enforces that rule against this module by name.

This module must NOT import `agent_freeze`. Reconcile is the repair side and has
to settle abandoned restores with no coordinator present; the dependency arrow
runs one way, into `agent_frozen_ops` only. (That is also why the ack grace lives
there — parent-plan amendment B6.)

Test seams, honoured **only** under ``AITASKS_TEST_MODE=1``:

* ``AITASKS_RESTORE_FAIL_AT=begin|respawn|ack`` — raise at that stage. Bound from
  the shared factory to THIS engine's variable so a freeze-engine injection
  cannot fire here and vice versa;
* ``AITASKS_FROZEN_PAUSE_AT=respawn|ack|aborting`` — ``SIGSTOP`` this process
  there, so a test can run a concurrent ``reconcile`` against a held lease. The
  ``ack`` stage is the strongest of the three: `launch_pid` is already recorded
  and the replacement is running, so reconcile's liveness row genuinely wants to
  act and must be refused by the live owner alone;
* ``AITASKS_RESTORE_ACK_GRACE`` — shorten the acknowledgement window
  (`agent_frozen_ops.restore_ack_grace`).
"""

from __future__ import annotations

import os
import shlex
import sys
import time
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
    StageFailure as _StageFailure,
)
from agent_launch_utils import (  # noqa: E402
    TmuxLaunchConfig,
    discover_aitasks_sessions,
    launch_in_tmux,
    pick_launch_argv,
    resolve_dry_run_command,
    resolve_pane_id_by_pid,
    unique_window_name,
)
from monitor.monitor_core import (  # noqa: E402
    FROZEN_OPTION,
    STANDIN_READY_OPTION,
)

#: This engine's failure-injection seam, bound to its own environment variable
#: so the freeze engine's `AITASKS_FREEZE_FAIL_AT` cannot fire here.
_fail_at = frozen_ops.make_fail_at("AITASKS_RESTORE_FAIL_AT")

#: How often the ack poll re-reads the record. Small enough that a hook ack is
#: noticed promptly, large enough not to spin on the store's lock.
POLL_INTERVAL = 0.5

#: The four identity variables handed to the replacement agent. Only RECORD and
#: NONCE are actually consumed — `aitask_session_hook.sh` forwards them as
#: `--restore-of` / `--nonce`, and the store reads the mode and the expected
#: session id off the RECORD, not off the environment (parent amendment B3).
#: MODE and EXPECT_SESSION are exported anyway, as **diagnostics**: they cost two
#: extra `-e` flags and they make a restoring pane's environment self-describing
#: when someone has to debug a restore by hand.
ENV_RECORD = "AITASK_RESTORE_RECORD"
ENV_NONCE = "AITASK_RESTORE_NONCE"
ENV_MODE = "AITASK_RESTORE_MODE"
ENV_EXPECT_SESSION = "AITASK_RESTORE_EXPECT_SESSION"


@dataclass
class RestoreResult:
    """One record's outcome. ``line`` is the wire line callers print."""

    record_id: str
    ok: bool
    outcome: str
    line: str


# --- argv construction ------------------------------------------------------


def build_resume_argv(rec: dict) -> str | None:
    """`invoke raw --resume-session <sid>` for this record's agent.

    ``--resume-session`` is a **global** wrapper flag, so it travels in
    ``extra_global_flags`` rather than in ``*args``: positional arguments land
    after ``invoke raw``, where the wrapper reads them as operation arguments.

    Returns None when the wrapper cannot resolve a command — a missing binary, an
    unknown model, or opencode (which has no resume surface). The caller turns
    that into a failure *before* touching the store.
    """
    session_id = rec.get("codeagent_session_id", "")
    if not session_id:
        return None
    return resolve_dry_run_command(
        Path(rec["root"]), "raw",
        agent_string=rec.get("agent_string") or None,
        extra_global_flags=["--resume-session", session_id],
    )


def build_repick_argv(rec: dict) -> str | None:
    """`/aitask-pick <task_id>` for this record's agent.

    Shares `pick_launch_argv` with both TUIs rather than forking the shape. It is
    called WITH the record's agent string so a restored agent comes back as the
    agent it was, which is exactly the case the helper's parameter exists for.
    """
    task_id = rec.get("task_id", "")
    if not task_id:
        return None
    cmd, _window = pick_launch_argv(
        Path(rec["root"]), task_id, agent_string=rec.get("agent_string") or None)
    return cmd


def _restore_env(record_id: str, nonce: str, mode: str, expect_session: str) -> dict:
    return {
        ENV_RECORD: record_id,
        ENV_NONCE: nonce,
        ENV_MODE: mode,
        ENV_EXPECT_SESSION: expect_session,
    }


def _env_prefixed(command: str, env: dict) -> str:
    """``env A=1 B=2 <command>`` — the fallback delivery mechanism.

    Used where tmux's native ``-e`` is not available to us: `launch_in_tmux`
    (the gone-pane branch) takes a command string, not respawn flags. Measured
    safe by spike Case 3: ``env`` **execs into** the agent, so ``#{pane_pid}``
    is still the agent's pid and the task-lock liveness anchor holds (t1465).
    A wrapper that *outlived* the agent would not be acceptable here.
    """
    assignments = " ".join(
        f"{name}={shlex.quote(value)}" for name, value in env.items())
    return f"env {assignments} {command}"


# --- the transaction --------------------------------------------------------


def _reread(record_id: str) -> dict:
    return frozen_ops.store_show(record_id)


def _clear_frozen_stamp(pane_id: str) -> None:
    if pane_id:
        frozen_ops.unset_option(pane_id, FROZEN_OPTION)


def _rollback(record_id: str, nonce: str, pane_id: str, reason: str = "") -> str:
    """Abort the attempt and put the stand-in back. Returns a detail suffix.

    ``reason`` is PERSISTED on the record by `restore-abort` (t1705_6). This
    coordinator's own wire line goes to a detached `run-shell` job that nobody
    reads, and the viewer that asked for the restore is replaced by the stand-in
    this function respawns — so the record is the only channel by which the user
    can ever learn why their restore failed.

    **Never called without first confirming the store actually moved the record
    to `aborting`.** `restore-abort` is state-guarded exactly like
    `restore-launched`, so a refusal here means someone else already settled the
    record — and respawning over it would destroy whatever is now in the pane.
    """
    abort_argv = ["restore-abort", record_id, "--nonce", nonce]
    if reason:
        abort_argv += ["--error", reason]
    rc, out = frozen_ops.store(*abort_argv)
    if rc == EXIT_NONCE_MISMATCH:
        return "nonce_mismatch"
    if rc != 0:
        # The record did not move to `aborting`. Do NOT respawn: reconcile owns
        # it now, and it has the same server-observable facts we do.
        return f"abort_refused:{out.strip()}"

    # Pause AFTER the transition, not before it: the stage is named `aborting`
    # and a test that waits for that state would otherwise wait forever, because
    # the record is still `restoring` until the verb above returns.
    frozen_ops.pause_at("aborting")

    # Clear the ready mark BEFORE the respawn: pane options survive
    # `respawn-pane`, so a mark left from a previous cycle would read as "this
    # cycle's viewer is already up" and stop reconcile from repairing it.
    if pane_id:
        frozen_ops.unset_option(pane_id, STANDIN_READY_OPTION)
        try:
            frozen_ops.respawn(pane_id, agent_sessions.standin_command(record_id))
        except ValueError:
            pass
        new_pane, new_pid = frozen_ops.pane_location(pane_id)
    else:
        new_pane, new_pid = "", 0
    frozen_ops.store("standin-respawned", record_id, "--nonce", nonce,
                     "--pane", new_pane, "--pane-pid", str(new_pid))
    return ""


def _settle(decided: "RestoreResult", record_id: str, nonce: str,
            pane_id: str) -> "RestoreResult":
    """Apply the rollback a failing verdict owes, then return it.

    Every failing outcome this coordinator can still act on is settled HERE, so
    the poll loop and the refused-verb re-read cannot drift into treating the
    same verdict differently — which is how one of them ends up leaving a
    `restoring` record with no stand-in for reconcile to find, and the user
    staring at a dead pane until the lease goes stale.

    A SUCCESS is returned untouched: rolling back a restore that worked is the
    single worst thing this module can do.
    """
    if decided.ok or decided.outcome not in ("session_mismatch", "agent_exited"):
        return decided
    detail = _rollback(record_id, nonce, pane_id, decided.outcome)
    if detail:
        return RestoreResult(record_id, False, decided.outcome,
                             f"{decided.line}|{detail}")
    return decided


def _launch_into_new_window(rec: dict, command: str, env: dict) -> tuple[str, int, str]:
    """Gone-pane branch: start the replacement in a NEW window.

    Returns ``(pane_id, pane_pid, error)``. The record keeps its identity, so the
    acknowledgement still selects the *old* record rather than creating a second
    one — the record id travels in the environment, not on the (nonexistent) pane.
    """
    root = os.path.realpath(rec.get("root", ""))
    target = None
    for session in discover_aitasks_sessions():
        if os.path.realpath(str(session.project_root)) == root:
            target = session
            break
    if target is None:
        return "", 0, "no_session_for_root"

    rc, out = frozen_ops.run(
        ["list-windows", "-t", target.session, "-F", "#{window_name}"])
    existing = set(out.split()) if rc == 0 else set()
    window = unique_window_name(existing, rec.get("window") or "agent-restore")

    # `launch_in_tmux` takes a command STRING and has no `-e`, so the identity
    # variables ride the proven `env` prefix here (spike Case 3) rather than
    # tmux's native flag. Both preserve `#{pane_pid} == agent pid`.
    pane_pid, error = launch_in_tmux(
        _env_prefixed(command, env),
        TmuxLaunchConfig(session=target.session, window=window,
                         new_session=False, new_window=True,
                         cwd=rec.get("root") or None),
    )
    if error:
        return "", 0, error

    # `launch_in_tmux` returns only the pid, but `restore-launched` needs the
    # pane id too — and the store REFUSES the pair `--pane "" --pane-pid <n>`,
    # because ("", 0) is reserved to mean "the pane is gone". Returning the pid
    # without its pane would therefore fail the very verb that records the
    # launch, leaving a `restoring` record with `launch_pid = 0` that reconcile
    # can only abort. Resolve the id back from the pid.
    pane_pid = int(pane_pid or 0)
    pane_id = resolve_pane_id_by_pid(target.session, pane_pid) if pane_pid else None
    if not pane_id:
        return "", 0, "launched_pane_unresolvable"
    return pane_id, pane_pid, ""


def restore(record_id: str, *, repick: bool = False) -> RestoreResult:
    """Restore one frozen record. Implements §D 1-5 in order."""
    mode = "repick" if repick else "resume"

    rec = _reread(record_id)
    if not rec:
        return RestoreResult(record_id, False, "no_record",
                             f"RESTORE_FAILED:{record_id}|no_record")

    pane_id = rec.get("pane_id", "")
    agent_kind = rec.get("agent_kind", "")
    session_id = rec.get("codeagent_session_id", "")

    # --- preflight: everything that can fail WITHOUT touching the store -----
    if mode == "resume":
        if not session_id:
            # The common "codex was never hooked" case, and the reason
            # `--repick` exists. Nothing changes; the record stays frozen.
            return RestoreResult(record_id, False, "no_session",
                                 f"RESTORE_FAILED:{record_id}|no_session")
        if agent_kind == "opencode":
            return RestoreResult(
                record_id, False, "resume_unsupported",
                f"RESTORE_FAILED:{record_id}|resume_unsupported:opencode")
    elif not rec.get("task_id"):
        return RestoreResult(record_id, False, "no_task_id",
                             f"RESTORE_FAILED:{record_id}|no_task_id")

    command = build_repick_argv(rec) if repick else build_resume_argv(rec)
    if not command:
        # A failed `--dry-run` probe IS the binary check: the wrapper resolves
        # the binary and the model, so there is no second `shutil.which` path to
        # keep in sync with it.
        return RestoreResult(record_id, False, "binary",
                             f"RESTORE_FAILED:{record_id}|binary")

    transcript = rec.get("transcript_path", "")
    if transcript and not os.path.exists(transcript):
        # Advisory only: the transcript is not needed to resume, and refusing
        # here would block a restore that would otherwise work.
        print(f"WARNING:{record_id}|transcript missing: {transcript}",
              file=sys.stderr)

    # --- 1. restore-begin: state `restoring`, lease minted ------------------
    # `--owner-pid` is THIS process, and it is THIS process only because of the
    # exec chain `run-shell -b` -> aitask_frozen.sh -> `exec python`. The shell
    # replaces itself, so the Python process is the one tmux detached and the one
    # that outlives the respawn. A pid that is already dead would collapse the
    # lease to a bare timer and let reconcile abort this restore WHILE IT IS
    # STILL POLLING for the ack. If that exec chain ever becomes a fork, this
    # line has to change with it.
    try:
        _fail_at("begin")
    except _StageFailure as exc:
        return RestoreResult(record_id, False, "begin",
                             f"RESTORE_FAILED:{record_id}|begin:{exc}")
    rc, out = frozen_ops.store("restore-begin", record_id,
                               "--owner-pid", str(os.getpid()),
                               "--mode", mode)
    if rc != 0:
        return RestoreResult(record_id, False, "begin",
                             f"RESTORE_FAILED:{record_id}|{out.strip()}")
    nonce = frozen_ops.nonce_from(out.splitlines()[-1])
    env = _restore_env(record_id, nonce, mode, session_id)

    # --- 2. clear the ready mark, then respawn ------------------------------
    try:
        _fail_at("respawn")
        if pane_id:
            frozen_ops.unset_option(pane_id, STANDIN_READY_OPTION)
            if not frozen_ops.respawn(pane_id, command, env=env):
                raise OSError(f"respawn-pane refused for {pane_id}")
            new_pane, new_pid = frozen_ops.pane_location(pane_id)
        else:
            new_pane, new_pid, error = _launch_into_new_window(rec, command, env)
            if error:
                raise OSError(error)
    except (_StageFailure, OSError, ValueError) as exc:
        detail = _rollback(record_id, nonce, pane_id, "respawn")
        suffix = f"|{detail}" if detail else ""
        return RestoreResult(record_id, False, "respawn",
                             f"RESTORE_FAILED:{record_id}|respawn:{exc}{suffix}")
    frozen_ops.pause_at("respawn")

    # --- 3. restore-launched: the nonce-bound evidence of the respawn -------
    # THE HOOK CAN WIN THIS RACE. If the replacement already acked, the record is
    # `live` and this verb is refused — which is SUCCESS, not failure. Re-read
    # before deciding; see property 3 in the module docstring.
    rc, out = frozen_ops.store("restore-launched", record_id, "--nonce", nonce,
                               "--pane", new_pane, "--pane-pid", str(new_pid))
    if rc != 0:
        if rc == EXIT_NONCE_MISMATCH:
            return RestoreResult(record_id, False, "nonce_mismatch",
                                 f"RESTORE_FAILED:{record_id}|nonce_mismatch")
        current = _reread(record_id)
        decided = _decide_from_record(record_id, current, nonce, agent_kind)
        if decided is not None:
            return _settle(decided, record_id, nonce, pane_id)
        detail = _rollback(record_id, nonce, pane_id, "launch_refused")
        suffix = f"|{detail}" if detail else ""
        return RestoreResult(
            record_id, False, "launch_refused",
            f"RESTORE_FAILED:{record_id}|restore-launched:{out.strip()}{suffix}")

    # --- 4. wait for the acknowledgement ------------------------------------
    try:
        _fail_at("ack")
    except _StageFailure as exc:
        # Deliberately NO rollback: the replacement is running. Leaving the
        # record `restoring` is correct — reconcile liveness-confirms it via
        # `launch_pid` once the lease goes stale.
        return RestoreResult(record_id, False, "ack",
                             f"RESTORE_FAILED:{record_id}|ack:{exc}")

    # Pause HERE, not earlier, for the takeover test: by this point `launch_pid`
    # is recorded and the replacement is running, so reconcile's liveness row
    # genuinely wants to fire — and must still be refused because this owner is
    # alive. Pausing before `restore-launched` would only exercise the
    # indeterminate row, which declines to act for a different reason.
    frozen_ops.pause_at("ack")

    grace = frozen_ops.restore_ack_grace(rec.get("root") or None)
    deadline = time.time() + grace
    while True:
        current = _reread(record_id)
        decided = _decide_from_record(record_id, current, nonce, agent_kind)
        if decided is not None:
            return _settle(decided, record_id, nonce, pane_id)
        if time.time() >= deadline:
            break
        time.sleep(POLL_INTERVAL)

    # --- 5. liveness fallback ----------------------------------------------
    # Grace elapsed with no hook ack and no error. Confirm ONLY on positive
    # evidence that the process in the pane is the one we launched: the store
    # refuses `restore-confirm` unless `launch_pid` is set and matches.
    # The captures are KEPT — `ack=liveness` never verified the session id, and
    # deleting the only copy on that evidence is what this whole protocol exists
    # to prevent.
    observed_pane, observed_pid = frozen_ops.pane_location(pane_id or new_pane)
    if not observed_pane or not observed_pid:
        # The pane went away while we waited. Falling back to the values from
        # BEFORE the wait would confirm a replacement that is no longer there —
        # and because those stale values still equal `launch_pid`, the store
        # would accept it. Confirming on evidence that has expired is exactly
        # what the liveness path must not do.
        detail = _rollback(record_id, nonce, pane_id, "agent_exited")
        suffix = f"|{detail}" if detail else ""
        return RestoreResult(record_id, False, "agent_exited",
                             f"RESTORE_FAILED:{record_id}|agent_exited{suffix}")
    rc, out = frozen_ops.store("restore-confirm", record_id, "--nonce", nonce,
                               "--pane", observed_pane,
                               "--pane-pid", str(observed_pid))
    if rc == EXIT_NONCE_MISMATCH:
        return RestoreResult(record_id, False, "nonce_mismatch",
                             f"RESTORE_FAILED:{record_id}|nonce_mismatch")
    if rc != 0:
        current = _reread(record_id)
        decided = _decide_from_record(record_id, current, nonce, agent_kind)
        if decided is not None:
            return decided
        return RestoreResult(record_id, False, "confirm_refused",
                             f"RESTORE_FAILED:{record_id}|restore-confirm:{out.strip()}")
    _clear_frozen_stamp(pane_id)
    return RestoreResult(record_id, True, "liveness",
                         f"RESTORED:{record_id}|liveness{_liveness_note(agent_kind)}")


def _liveness_note(agent_kind: str) -> str:
    """Why a codex restore can only ever reach `liveness`.

    Codex's SessionStart hook does not fire in the interactive TUI (t1705_1
    PINNED), which is the framework's launch path — so no hook ack can arrive and
    the captures are always kept. Saying so inline stops that reading as an
    unexplained downgrade from the `hook` outcome.
    """
    if agent_kind == "codex":
        return " (codex: no interactive hook — captures kept)"
    return " (captures kept: session id unverified)"


def _decide_from_record(record_id: str, rec: dict, nonce: str,
                        agent_kind: str) -> RestoreResult | None:
    """Read one of the four §D outcomes off the record, or None to keep waiting.

    The single place the record is interpreted, so the poll loop and every
    refused-verb re-read reach the same verdict from the same fields.
    """
    if not rec:
        return RestoreResult(record_id, False, "no_record",
                             f"RESTORE_FAILED:{record_id}|record vanished")

    # The hook acknowledged: state `live` with `ack=hook`. The store already
    # verified the session id and deleted the captures.
    if rec.get("state") == "live" and rec.get("ack") == "hook":
        _clear_frozen_stamp(rec.get("pane_id", ""))
        return RestoreResult(record_id, True, "hook",
                             f"RESTORED:{record_id}|hook")

    # A mismatch is persisted on the record because the hook has no return
    # channel to this detached process. It is nonce-scoped so a stale error from
    # an earlier attempt cannot abort this one.
    last_error = rec.get("last_error", "")
    if last_error.startswith(f"{nonce}:"):
        reason = last_error.split(":", 1)[1] or "session_mismatch"
        return RestoreResult(record_id, False, "session_mismatch",
                             f"RESTORE_FAILED:{record_id}|{reason}")

    # Someone else finished the transaction (reconcile, or a liveness confirm).
    if rec.get("state") == "live" and rec.get("ack") == "liveness":
        _clear_frozen_stamp(rec.get("pane_id", ""))
        return RestoreResult(record_id, True, "liveness",
                             f"RESTORED:{record_id}|liveness{_liveness_note(agent_kind)}")

    pane_id = rec.get("pane_id", "")
    if pane_id:
        facts = frozen_ops.pane_facts(pane_id)
        # BOTH shapes of "the replacement is gone" end the wait, and the second
        # is easy to miss: with `remain-on-exit` set the pane stays as a corpse
        # (`pane_dead=1`), but WITHOUT it the pane simply vanishes and
        # `pane_facts` returns {}. Treating only the first as an exit leaves the
        # poll running to the grace and then liveness-confirming a record whose
        # agent died seconds earlier — reporting success for nothing.
        if not facts:
            return RestoreResult(record_id, False, "agent_exited",
                                 f"RESTORE_FAILED:{record_id}|agent_exited")
        if frozen_ops.int_or_zero(facts.get("pane_dead")):
            return RestoreResult(record_id, False, "agent_exited",
                                 f"RESTORE_FAILED:{record_id}|agent_exited")
    return None


def restore_all(*, repick: bool = False) -> list[RestoreResult]:
    """Restore every `frozen` record, sequentially.

    One record's failure never stops the batch — a user with three frozen agents
    and one broken binary should get the other two back.
    """
    rc, out = frozen_ops.store("list", "--state", "frozen")
    if rc != 0:
        return []
    results: list[RestoreResult] = []
    for line in out.splitlines():
        if not line.startswith("SESSION:"):
            continue
        record_id = line[len("SESSION:"):].split("|", 1)[0].strip()
        if not record_id:
            continue
        try:
            results.append(restore(record_id, repick=repick))
        except Exception as exc:            # never abandon the rest of the batch
            results.append(RestoreResult(
                record_id, False, "error",
                f"RESTORE_FAILED:{record_id}|{exc}"))
    return results


# --- CLI --------------------------------------------------------------------


def main(argv: list[str]) -> int:
    """`restore <id> [--repick]` / `restore --all [--repick]`.

    Exit codes match `aitask_frozen.sh`'s documented contract: 0 all-ok,
    1 some-failed, 2 usage.
    """
    args = list(argv)
    if args and args[0] == "restore":
        args = args[1:]
    repick = "--repick" in args
    args = [a for a in args if a != "--repick"]

    if args and args[0] == "--all":
        if len(args) != 1:
            print("Usage: aitask_frozen.sh restore --all [--repick]", file=sys.stderr)
            return 2
        results = restore_all(repick=repick)
        for result in results:
            print(result.line)
        ok = sum(1 for r in results if r.ok)
        print(f"RESTORE_ALL:{ok}/{len(results)}")
        return 0 if ok == len(results) else 1

    if len(args) != 1 or not args[0] or args[0].startswith("-"):
        print("Usage: aitask_frozen.sh restore <id> [--repick] | restore --all",
              file=sys.stderr)
        return 2

    result = restore(args[0], repick=repick)
    print(result.line)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
