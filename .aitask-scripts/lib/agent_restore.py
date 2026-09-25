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

WHERE A GONE-PANE RESTORE LANDS (t1784). With the recorded pane gone, the
replacement starts in a new window of the project's own tmux session. After a
server restart there may be none, so `_launch_into_new_window` creates it
through `tmux_bootstrap.sh --create-only` — and uses only a session discovery
attributed to the root before anything changed, or one this call created. A
session name already held by another project is refused and left untouched,
never adopted: discovery's registry fallback would otherwise let a clobbered
`AITASKS_PROJECT_<session>` entry hand this restore a stranger's session.

PARTIAL LAUNCHES AND SURVIVORS (t1875). A new-window launch can half-succeed:
tmux creates the window but its `-P` answer is lost, or the gateway times out
(rc -1) after the server already acted. So the window is created under a
per-attempt NAME, identified by that name when the answer is unusable, then
stamped and given a per-attempt MARK before it is renamed — see the protocol
comment above `_launch_into_new_window`. Once identified, the new pane IS the
attempt's pane: a rollback puts the stand-in back into it, as on the same-pane
branch. Anything a failure still leaves behind is a *restore survivor* — an
agent no record tracks — and `restore` refuses to launch past one (a
whole-server scan, before the recorded-pane probe and again under the lease),
as do `agent_reopen` and `agent_freeze.drop_record`: acting past a survivor
would either start a second agent on its session or mistake it for a viewer.

Test seams, honoured **only** under ``AITASKS_TEST_MODE=1``:

* ``AITASKS_RESTORE_FAIL_AT=begin|respawn|ack`` — raise at that stage. Bound from
  the shared factory to THIS engine's variable so a freeze-engine injection
  cannot fire here and vice versa;
* ``AITASKS_RESTORE_FAIL_AT=<stage>[,<stage>…]`` for the gone-pane launch —
  ``launch_uncertain`` (dispatch ``new-window``, then report rc -1 with no
  output), ``identify`` (discard the ``-P`` answer), ``lookup`` (the name lookup
  reports tmux unreachable), ``stamp`` (the stamp+mark dispatch does not run),
  ``cleanup`` (the guarded kill is skipped and reported ``present``) and
  ``abandon`` (return an error after the rename with NO cleanup — the end state
  of a coordinator that died there);
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
import secrets
import shlex
import subprocess
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
    discover_aitasks_sessions,
    discover_aitasks_sessions_checked,
    maybe_spawn_minimonitor,
    pick_launch_argv,
    resolve_dry_run_command,
    tmux_window_target,
    unique_window_name,
)
from monitor.monitor_core import (  # noqa: E402
    FROZEN_OPTION,
    STANDIN_READY_OPTION,
)

#: This engine's failure-injection seam, bound to its own environment variable
#: so the freeze engine's `AITASKS_FREEZE_FAIL_AT` cannot fire here.
_fail_at = frozen_ops.make_fail_at("AITASKS_RESTORE_FAIL_AT")

_FAIL_ENV = "AITASKS_RESTORE_FAIL_AT"


def _seam(stage: str) -> bool:
    """The gone-pane launch's seams (t1875): a COMMA-SEPARATED stage set.

    A live test needs pairs (``identify,lookup``), which `_fail_at`'s equality
    cannot express. The stage names are disjoint from `_fail_at`'s
    (begin/respawn/ack), so the two readings of the one variable never collide.
    """
    if not frozen_ops.test_mode():
        return False
    return stage in {s.strip() for s in os.environ.get(_FAIL_ENV, "").split(",")}


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

#: The fifth variable is not an identity variable: it is the one the wrapper
#: exports on a real launch (`aitask_codeagent.sh` `cmd_invoke`). The
#: replacement runs the argv the wrapper's `--dry-run` resolved, which returns
#: BEFORE that export. Since t1850 `resolve_dry_run_command` asks for it back
#: (`--with-agent-env`), so the argv already starts with `env
#: AITASK_AGENT_STRING=…`. This delivery stays as a second line of defence: it
#: carries the RECORD's value, which is the same one the argv was resolved
#: with. Without either, the hook acks with `--agent-string ""` and the
#: restored agent's own model self-detection loses its authoritative source
#: (t1802). Delivered only for a well-formed value; see `_restore_env`.
ENV_AGENT_STRING = "AITASK_AGENT_STRING"


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


def resume_blocker(rec: dict) -> str:
    """Why `restore` (resume mode) would refuse ``rec`` before touching anything.

    ``""`` when a resume can be attempted. Shared with the `ait ide` offer
    (`agent_reopen gone`), which must advertise exactly what this module
    accepts — so the rules live here, once.

    ``no_session``: no captured session. Since t1804 a codex agent's id is
    captured at freeze time from the rollout its process held open, so this now
    means that correlation was unavailable: no `/proc` (macOS), the pane was not
    running codex directly, the agent had taken no turn yet (codex opens its
    rollout at the FIRST turn), its model is not in `models_codex.json`, or the
    freeze could not prove which of several rollouts was its own. The reason
    `--repick` exists; nothing changes and the record stays frozen.
    """
    if not rec.get("codeagent_session_id", ""):
        return "no_session"
    if rec.get("agent_kind", "") == "opencode":
        return "resume_unsupported:opencode"
    return ""


def repick_blocker(rec: dict) -> str:
    """Why `restore --repick` would refuse ``rec``; ``""`` when it can run."""
    return "" if rec.get("task_id", "") else "no_task_id"


def session_name_ok(name: str) -> bool:
    """`ait ide`'s own session-name rule (`_tmux_bootstrap_session_name_ok`).

    Non-empty, no `.` and no `:` (tmux target separators). A leading `-` is
    ALLOWED: `ait ide --session -n` opens a session literally named `-n`, and the
    frozen-agent commands it drives must be able to target that same session.
    """
    return bool(name) and "." not in name and ":" not in name


def take_session_arg(args: list[str]) -> tuple[list[str], str | None, str]:
    """Remove ``--session <value>`` from ``args``. Returns ``(rest, value, err)``.

    The token after ``--session`` is its value VERBATIM, even when it starts
    with ``-`` (see :func:`session_name_ok`). ``err`` is non-empty for a missing
    or invalid value, or a repeated flag.
    """
    rest: list[str] = []
    value: str | None = None
    i = 0
    while i < len(args):
        if args[i] == "--session":
            if value is not None:
                return args, None, "--session given twice"
            if i + 1 >= len(args):
                return args, None, "--session requires a name"
            value = args[i + 1]
            if not session_name_ok(value):
                return args, None, f"invalid session name: {value!r}"
            i += 2
            continue
        rest.append(args[i])
        i += 1
    return rest, value, ""


def _restore_env(record_id: str, nonce: str, mode: str, expect_session: str,
                 agent_string: str = "") -> dict:
    env = {
        ENV_RECORD: record_id,
        ENV_NONCE: nonce,
        ENV_MODE: mode,
        ENV_EXPECT_SESSION: expect_session,
    }
    # Only a well-formed value rides along. `respawn_if_stamped` joins every
    # `-e NAME=value` into the `if-shell` branch UNQUOTED, and the store keeps
    # whatever string a caller upserted; `agent_kind_of` is the store's own
    # well-formedness check, so nothing else can reach that command line. An
    # empty record has nothing to deliver, and a blank is a no-op in the store.
    if agent_sessions.agent_kind_of(agent_string):
        env[ENV_AGENT_STRING] = agent_string
    return env


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


def _clear_frozen_stamp(pane_id: str, record_id: str, nonce: str) -> None:
    """Retire a restored pane's marks: the stamp, and this attempt's mark.

    Both are GUARDED single dispatches (t1875). A bare unset is a separate call
    a server restart can land on a recycled `%N` — another record's pane — and
    strip its stamp, or its attempt mark, which after the rename is the only
    claim a gone-pane attempt has. The mark's value is derived from THIS
    attempt's nonce, so it matches nothing else; on a same-pane restore no pane
    carries it and the dispatch is a no-op.
    """
    if pane_id:
        frozen_ops.clear_stamp_if(pane_id, record_id)
        frozen_ops.clear_restore_attempt(
            pane_id, frozen_ops.restore_attempt_value(record_id, nonce))


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

    # The ready mark is cleared BEFORE the respawn — `unset=` puts it first in
    # the dispatched branch. Pane options survive `respawn-pane`, so a mark left
    # from a previous cycle would read as "this cycle's viewer is already up"
    # and stop reconcile from repairing it. Being inside the branch also means
    # it is not cleared on a pane the dispatch declines to touch.
    new_pane, new_pid = "", 0
    if pane_id:
        try:
            # Same atomicity rule as the forward path: putting the stand-in back
            # is also a `respawn-pane -k`, so it must not fire on a `%N` that
            # stopped being ours. A miss returns no location, and the ("", 0)
            # below is exactly the gone-pane pair `_reconcile_restoring` commits
            # to keep a record restorable into a NEW window.
            fired, new_pane, new_pid, _why = frozen_ops.respawn_if_stamped(
                pane_id, agent_sessions.standin_command(record_id),
                option=FROZEN_OPTION, expect=record_id,
                unset=STANDIN_READY_OPTION)
            if fired:
                # A gone-pane attempt's mark (t1875) goes only NOW, after the
                # branch token proved the stand-in replaced the agent — never in
                # the pre-respawn `unset`, which runs even when the respawn then
                # fails and would strip the only claim of a still-running agent.
                frozen_ops.clear_restore_attempt(
                    new_pane, frozen_ops.restore_attempt_value(record_id, nonce))
            else:
                new_pane, new_pid = "", 0
        except ValueError:
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


#: Bound on one project-session bootstrap — the TUI switcher's, for the same
#: helper. It runs inside the lease `restore-begin` minted, well below the
#: stale-op grace (60 s by default) after which reconcile may take that lease.
BOOTSTRAP_TIMEOUT = 15

#: The canonical project-session bootstrap, shared with `ait ide` and the TUI
#: switcher. It owns the session's NAME (`tmux.default_session`), its seeded
#: `monitor` window and the registry entries — none of which is re-derived here.
_BOOTSTRAP_SH = _LIB_DIR / "tmux_bootstrap.sh"


def _session_for_root(root_real: str, *, name: str | None = None):
    """The first live session discovery attributes to ``root_real``, or None.

    With ``name`` the session must also carry that tmux session name — how a
    caller insists on the one session it created itself.
    """
    for session in discover_aitasks_sessions():
        if os.path.realpath(str(session.project_root)) != root_real:
            continue
        if name is None or session.session == name:
            return session
    return None


def _bootstrap_project_session(root: str) -> tuple[str, str]:
    """Create ``root``'s own tmux session. Returns ``(created_session, why)``.

    Runs the canonical `tmux_bootstrap.sh` in ``--create-only`` mode, which
    CREATES the session or changes NOTHING. Its default "ensure" mode would be
    wrong here: on a session name already held by another project it still
    writes `AITASKS_PROJECT_<session>` and a syncer window into that session,
    and discovery falls back to that registry entry — so a restore would
    re-point a stranger's session at this project and then launch into it.

    Only a non-empty ``created_session`` is ownership, and it comes only from the
    helper's own ``BOOTSTRAP_CREATED:<name>``. Every other outcome — an exit 0
    that reported no creation included — returns ``("", <reason>)``.

    An unreadable ``tmux.default_session`` is one of those refusals
    (``default_session_unreadable:<shape>``, t1811): `--create-only` will not
    create a session under the fallback name, because this detached restore has
    no way to warn about the fallback. The reason travels the ordinary failure
    path — `_launch_into_new_window` → `_rollback` → ``last_error`` →
    `restore_verdict` — so the viewer shows it and the record stays restorable.

    Why a new session rather than the invoking pane's: a project's agents live
    in that project's one session (`aidocs/framework/tui_conventions.md`), which
    `ait monitor` maps back to the project root; and a restore from a bare shell,
    or with no tmux server at all, has no invoking session to borrow — the
    bootstrap creates the server too.
    """
    try:
        done = subprocess.run(
            ["bash", str(_BOOTSTRAP_SH), "--create-only", root],
            capture_output=True, text=True, timeout=BOOTSTRAP_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "", "timeout"
    except OSError as exc:
        return "", str(exc)
    if done.returncode == 0:
        for line in (done.stdout or "").splitlines():
            if line.startswith("BOOTSTRAP_CREATED:"):
                return line[len("BOOTSTRAP_CREATED:"):].strip(), ""
        return "", "no creation reported"
    stderr = done.stderr or ""
    for line in stderr.splitlines():
        if line.startswith("BOOTSTRAP_FAILED:session_exists:"):
            return "", "session_name_taken:" + line.split(":", 2)[2].strip()
        if line.startswith("BOOTSTRAP_FAILED:stale_path"):
            return "", "stale_path"
        if line.startswith("BOOTSTRAP_FAILED:default_session_unreadable:"):
            return "", "default_session_unreadable:" + line.split(":", 2)[2].strip()
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    return "", lines[-1] if lines else f"rc={done.returncode}"


def _spawn_companion(session: str, window: str, pane_id: str, root: str) -> None:
    """Give a new-window restore the companion a normal launch gets (t1851).

    ``agent_pane`` is the replacement's own pane, so the companion follows the
    restored agent by identity rather than whichever pane is active by the time
    the helper looks. ``project_root`` because this process runs detached under
    `run-shell -b`, where the cwd is not guaranteed to be the project.

    Best-effort: the replacement is already running, so no companion failure may
    turn into a failed restore — `restore()` rolls back only on OSError /
    ValueError, and anything else escaping here would abandon a live agent
    mid-transaction.
    """
    try:
        maybe_spawn_minimonitor(session, window, agent_pane=pane_id,
                                project_root=Path(root) if root else None)
    except Exception as exc:
        print(f"WARNING:companion not spawned in {session}:{window} ({exc})",
              file=sys.stderr)


def _named_session_for_root(root_real: str, name: str):
    """``(target, error)``: the session ``name``, only if it belongs to the root.

    AUTHORIZATION, so it uses the checked discovery. The default discovery
    lists a session's panes with a bare ``=<name>`` target, which tmux resolves
    as a WINDOW first — from a client whose current session has a window called
    ``name``, it reads THAT session's panes and would attribute a foreign
    project's session to this root (t1874 owns that default). The checked
    variant targets ``=<name>:`` and says whether it saw everything; a scan that
    could not look is never read as "not ours" or as "ours".
    """
    sessions, complete = discover_aitasks_sessions_checked()
    for candidate in sessions:
        if candidate.session != name:
            continue
        if os.path.realpath(str(candidate.project_root)) == root_real:
            return candidate, ""
        return None, f"session_not_for_root:{name}"
    if not complete:
        return None, f"session_unverified:{name}"
    return None, f"session_not_for_root:{name}"


def _resolve_target_session(root: str, session: str | None = None):
    """The session a gone-pane launch for ``root`` goes into: ``(target, error)``.

    With ``session`` (how `ait ide` passes the session it is opening), ONLY that
    session, and only when the CHECKED discovery attributes it to ``root``
    (:func:`_named_session_for_root`). Anything else fails closed with
    ``session_not_for_root:<session>`` (or ``session_unverified:<session>`` when
    the scan could not look) — no bootstrap, and no
    fallback to another session of the same root: two sessions can share a
    project (`ait ide --session NAME`), and landing the agent in the one the user
    is not looking at is the failure this parameter exists to prevent.

    Without it, the first session attributed to the root, else one created for it
    (t1784) under the ownership rule `_launch_into_new_window` documents.
    """
    root_real = os.path.realpath(root)
    if session is not None:
        return _named_session_for_root(root_real, session)
    target = _session_for_root(root_real)
    if target is None:
        created, why = _bootstrap_project_session(root)
        # Only the session THIS call created. `--create-only` left any existing
        # one untouched, so nothing here can have re-pointed a foreign session's
        # registry entry at this root — and a refusal gets no second lookup: a
        # same-root session created concurrently by another restore of this
        # project is a lost race, fail-safe, and the retry finds it above.
        target = _session_for_root(root_real, name=created) if created else None
        if target is None:
            # Name the project AND the cause: `_rollback` persists this on the
            # record, the only channel by which the user learns why.
            detail = why or f"created {created} but no pane of it sits under the root"
            return None, f"no_session_for_root:{root}|bootstrap:{detail}"
    return target, ""


# --- the gone-pane launch: attempt identity (t1875) --------------------------
#
# The protocol of `agent_reopen._fresh`, applied to a window that runs an AGENT:
# the window is claimed at every instant from creation to settlement, so no
# partial launch can leave an agent nobody can identify.
#
#   1. created under the ATTEMPT NAME (`new-window -n`, atomic with the window);
#   2. identified from `-P` output, else by that name — an rc of -1 (the
#      gateway's timeout) or unparsed output is never read as "nothing exists";
#   3. marked, name-guarded, with the frozen STAMP (so `_rollback` can put the
#      stand-in back into THIS window) and the ATTEMPT MARK (so the window stays
#      identifiable as a restore-launched agent after step 4);
#   4. renamed, stamp-guarded, to the recorded `agent-…` name (monitor and the
#      companion key on the prefix). A failed rename is cosmetic.
#
# Any failure after the window exists either records it (the caller carries the
# pane into `restore-launched`) or removes it with a name-guarded kill, and a
# kill that cannot be verified is NAMED in the error, never hidden. Whatever
# survives is a restore survivor (`agent_frozen_ops.find_restore_survivors`),
# which restore, reopen and drop all refuse to act past.
#
# The tmux primitives — lookup by name, guarded kill, stamp-guarded rename, the
# window-facts read — are shared with `agent_reopen` in `agent_frozen_ops`
# (t1883); only this coordinator's seams stay here, as thin wrappers.


def _find_attempt_pane(session: str, name: str) -> tuple[str, str, int]:
    """`frozen_ops.find_pane_by_window_name`, behind the ``lookup`` seam."""
    if _seam("lookup"):
        return "unknown", "", 0
    return frozen_ops.find_pane_by_window_name(session, name)


def _kill_if_named(pane_id: str, name: str) -> tuple[str, str]:
    """The name-guarded cleanup kill, behind the ``cleanup`` seam.

    A window that survives is ``present`` / ``kill-failed`` whatever it is named
    by then — this label reaches `RESTORE_FAILED` (reopen labels the renamed case
    ``name-mismatch``; each coordinator keeps its own).
    """
    if _seam("cleanup"):
        return "present", "seam"
    return frozen_ops.kill_window_if(pane_id, frozen_ops.window_name_condition(name))


def _cleanup_suffix(verdict: str, reason: str, pane_id: str) -> str:
    if verdict == "gone":
        return ""
    return f"|cleanup:{verdict}:{reason}|pane:{pane_id}"


def _survivor_refusal(record_id: str) -> str:
    """``""`` when no restore survivor of ``record_id`` is alive, else the reason.

    The retry guard (t1875). A survivor — an agent an earlier gone-pane attempt
    launched and no record tracks — is invisible to the recorded-pane probe: it
    usually sits in another pane, and after a server restart it can sit at the
    very `%N` the record remembers, stamped as though it were the stand-in. So
    this is a whole-server scan (`frozen_ops.find_restore_survivors`) that ends
    in one of three answers, never a guess:

    * tmux cannot be read → ``preflight:tmux unreachable`` (fail closed);
    * a live survivor → ``restore_survivor:<session>:<window>|pane:<id>`` —
      launching now would put a second agent on the same session;
    * a DEAD one (the agent exited, the pane stayed) is removed with a kill
      guarded on its own attempt value AND on still being dead, and blocks
      unless that kill is verified.
    """
    hits = frozen_ops.find_restore_survivors(record_id)
    if hits is None:
        return "preflight:tmux unreachable"
    for hit in hits:
        if hit["dead"] == "1":
            if hit.get("mark"):
                claim = f"#{{==:#{{{frozen_ops.RESTORE_ATTEMPT_OPTION}}},{hit['mark']}}}"
            else:
                claim = frozen_ops.window_name_condition(hit["window"])
            verdict, _why = frozen_ops.kill_window_if(
                hit["pane_id"], f"#{{&&:#{{pane_dead}},{claim}}}")
            if verdict == "gone":
                continue
        return frozen_ops.survivor_detail(hit)
    return ""


def _launch_into_new_window(rec: dict, command: str, env: dict,
                            session: str | None = None) -> tuple[str, int, str]:
    """Gone-pane branch: start the replacement in a NEW window.

    Returns ``(pane_id, pane_pid, error)``. The record keeps its identity, so the
    acknowledgement still selects the *old* record rather than creating a second
    one — the record id travels in the environment, not on the (nonexistent) pane.

    The window goes into the project's own session. When none is attributed to
    the root — the ordinary state after a tmux server restart — that session is
    created first (t1784), under an OWNERSHIP rule: use only a session discovery
    attributed to the root before anything changed, or one this call created.

    The window is created and settled under the attempt-identity protocol above
    (t1875): a returned pane is stamped and marked, and an error means either
    that no window exists, or that the one which does is named in the error or
    identifiable by its attempt name.

    A successful launch also gets its minimonitor companion (t1851), as every
    other launch path does; the same-pane branch in `restore()` never comes
    here, so the companion its surviving window already has is never doubled.
    """
    target, error = _resolve_target_session(rec.get("root", ""), session)
    if target is None:
        return "", 0, error

    record_id = env.get(ENV_RECORD) or rec.get("id", "")
    # Always set on a real restore (`restore-begin` minted it); a direct caller
    # without one still gets a name unique to this attempt.
    nonce = env.get(ENV_NONCE) or secrets.token_hex(4)
    attempt = frozen_ops.restore_attempt_name(record_id, nonce)
    mark = frozen_ops.restore_attempt_value(record_id, nonce)
    root = rec.get("root", "")

    rc, out = frozen_ops.run(["list-windows", "-t", tmux_window_target(target.session, ""),
                              "-F", "#{window_name}"])
    existing = set(out.split()) if rc == 0 else set()
    final = unique_window_name(existing, rec.get("window") or "agent-restore")

    # --- 1. create, under the attempt name ---------------------------------
    # The command is handed over UNWRAPPED except for the proven `env` prefix
    # (spike Case 3), which execs into the agent: `#{pane_pid}` is the agent's
    # pid, the task-lock anchor (t1465). No `-d`: the window is selected, as
    # every restore has always done.
    argv = ["new-window", "-P", "-F", "#{pane_id}\t#{pane_pid}",
            "-t", tmux_window_target(target.session, ""), "-n", attempt]
    if root:
        argv += ["-c", root]
    rc, out = frozen_ops.run(argv + [_env_prefixed(command, env)])
    if _seam("launch_uncertain"):
        rc, out = frozen_ops.TMUX_UNREACHABLE, ""

    pane_id, pane_pid = "", 0
    if rc == 0 and not _seam("identify"):
        parts = (out.splitlines() or [""])[0].split("\t")
        if len(parts) == 2 and parts[0].strip().startswith("%"):
            pane_id = parts[0].strip()
            pane_pid = frozen_ops.int_or_zero(parts[1].strip())

    # --- 2. identify: an unparsed or uncertain answer is looked up by name --
    if not pane_id or not pane_pid:
        verdict, pane_id, pane_pid = _find_attempt_pane(target.session, attempt)
        if verdict == "none":
            # tmux answered and holds no window of this attempt.
            return "", 0, f"launch:rc={rc}"
        if verdict != "found":
            # Whether a window exists cannot be known. If one does, it carries
            # the attempt name, and the survivor guard finds it on the next run.
            return "", 0, f"launch_uncertain:{attempt}"

    # --- 3. stamp + mark, name-guarded, verified ---------------------------
    if not _seam("stamp"):
        frozen_ops.run([
            "if-shell", "-F", "-t", pane_id, f"#{{==:#{{window_name}},{attempt}}}",
            f"set-option -p -t {pane_id} {FROZEN_OPTION} {record_id} ; "
            f"set-option -p -t {pane_id} {frozen_ops.RESTORE_ATTEMPT_OPTION} {mark}"])
    facts = frozen_ops.window_facts(pane_id)
    if not facts or facts.get("frozen") != record_id or facts.get("mark") != mark:
        verdict, reason = _kill_if_named(pane_id, attempt)
        return "", 0, "stamp" + _cleanup_suffix(verdict, reason, pane_id)

    # --- 4. rename to the recorded name (cosmetic on failure) --------------
    window = final
    if not frozen_ops.rename_window_if_stamped(pane_id, record_id, final):
        window = attempt
        print(f"WARNING:{record_id}|window not renamed from {attempt} to {final}",
              file=sys.stderr)

    if _seam("abandon"):
        # The end state of a coordinator that died right here: a stamped,
        # marked, renamed agent that no record tracks. No cleanup, by design.
        return "", 0, "abandon"

    _spawn_companion(target.session, window, pane_id, root)
    return pane_id, pane_pid, ""


def restore(record_id: str, *, repick: bool = False,
            session: str | None = None) -> RestoreResult:
    """Restore one frozen record. Implements §D 1-5 in order.

    ``session`` pins a gone-pane restore to that tmux session (see
    `_resolve_target_session`); a same-pane restore never consults it, because
    its pane already sits where the user left it.
    """
    mode = "repick" if repick else "resume"

    rec = _reread(record_id)
    if not rec:
        return RestoreResult(record_id, False, "no_record",
                             f"RESTORE_FAILED:{record_id}|no_record")

    pane_id = rec.get("pane_id", "")
    agent_kind = rec.get("agent_kind", "")
    session_id = rec.get("codeagent_session_id", "")

    # --- preflight: everything that can fail WITHOUT touching the store -----
    # The rules live in `resume_blocker` / `repick_blocker` so the `ait ide`
    # offer (`agent_reopen gone`) reports exactly what this function accepts.
    blocker = resume_blocker(rec) if mode == "resume" else repick_blocker(rec)
    if blocker:
        outcome = blocker.split(":", 1)[0]
        return RestoreResult(record_id, False, outcome,
                             f"RESTORE_FAILED:{record_id}|{blocker}")

    command = build_repick_argv(rec) if repick else build_resume_argv(rec)
    if not command:
        # A failed `--dry-run` probe IS the binary check: the wrapper resolves
        # the binary and the model, so there is no second `shutil.which` path to
        # keep in sync with it.
        return RestoreResult(record_id, False, "binary",
                             f"RESTORE_FAILED:{record_id}|binary")

    # A restore survivor (t1875) is refused BEFORE the recorded-pane probe: a
    # survivor at the recorded `%N` carries this record's stamp and would pass
    # that probe as the stand-in — and the same-pane branch would then
    # `respawn-pane -k` a running agent. Nothing is written here.
    refusal = _survivor_refusal(record_id)
    if refusal:
        outcome = "preflight" if refusal.startswith("preflight:") else "restore_survivor"
        return RestoreResult(record_id, False, outcome,
                             f"RESTORE_FAILED:{record_id}|{refusal}")

    # The recorded `pane_id` is a HINT, not a target. A retained `frozen` record
    # keeps its old `%N` after the window is closed or the tmux server restarts
    # — `_reconcile_frozen` returns `KEEP:<id>|pane_gone` and writes NOTHING —
    # so branching on it respawns a corpse and the record can never be restored
    # again (t1773). Resolve it against the SERVER before choosing the branch,
    # exactly as `agent_freeze.drop_record()` preflights its own target.
    if pane_id:
        verdict, facts = frozen_ops.probe_pane(pane_id)
        if verdict == "unknown":
            # Fail CLOSED, before any write: reading an unreachable tmux as
            # "gone" would mint a lease and drive a new-window launch that
            # cannot work, while the original stand-in may still be alive.
            return RestoreResult(
                record_id, False, "preflight",
                f"RESTORE_FAILED:{record_id}|preflight:tmux unreachable")
        if verdict != "present" or not facts or facts["frozen"] != record_id:
            # Gone, or a recycled `%N` that now carries somebody else's stamp.
            # Pane options die with the pane, so a missing stamp means it is not
            # ours — and `respawn-pane -k` on it would kill a stranger's agent.
            pane_id = ""

    model_note = agent_sessions.unknown_model_note(rec.get("agent_string", ""))
    if model_note:
        # Advisory: the wrapper resolves the project default, so the restore
        # works, just possibly on a different model than the frozen agent ran.
        print(f"WARNING:{record_id}|{model_note}", file=sys.stderr)

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
    env = _restore_env(record_id, nonce, mode, session_id,
                       agent_string=rec.get("agent_string", ""))

    # The same scan again, now UNDER THE LEASE. Only a restore of this record
    # can create its survivor, and that needs this lease — so between here and
    # the launch none can appear. The pre-lease scan above cannot promise that:
    # a concurrent restore may have launched and abandoned an attempt in
    # between. The rollback restores the stand-in into the probed pane (if it
    # was ours) and persists the reason, exactly as any refused launch does.
    refusal = _survivor_refusal(record_id)
    if refusal:
        outcome = "preflight" if refusal.startswith("preflight:") else "restore_survivor"
        detail = _rollback(record_id, nonce, pane_id, refusal.split("|", 1)[0])
        suffix = f"|{detail}" if detail else ""
        return RestoreResult(record_id, False, outcome,
                             f"RESTORE_FAILED:{record_id}|{refusal}{suffix}")

    # --- 2. clear the ready mark, then respawn ------------------------------
    try:
        _fail_at("respawn")
        if pane_id:
            # ONE dispatch: the stamp check and the respawn cannot be separated,
            # so a server restart cannot slip between them and hand the kill an
            # unrelated pane. A miss touches nothing and yields no location.
            fired, new_pane, new_pid, why = frozen_ops.respawn_if_stamped(
                pane_id, command, option=FROZEN_OPTION, expect=record_id,
                env=env, unset=STANDIN_READY_OPTION)
            if not fired:
                print(f"WARNING:{record_id}|recorded pane {pane_id} not reused"
                      f" ({why}); restoring into a new window", file=sys.stderr)
                pane_id = ""
        if not pane_id:
            new_pane, new_pid, error = _launch_into_new_window(
                rec, command, env, session=session)
            if error:
                raise OSError(error)
            # From here the NEW window is this attempt's pane (t1875): every
            # rollback, settle, liveness read and stamp clear below must address
            # it. Left empty, a rollback would put the record back to `frozen`
            # while the resumed agent kept running in a window nobody tracks.
            # It is stamped, so `_rollback`'s guarded respawn puts the stand-in
            # back into it exactly as it would on the same-pane branch.
            pane_id = new_pane
    except (_StageFailure, OSError, ValueError) as exc:
        # The reason is PERSISTED as `last_error` — the only channel back to the
        # user — so it carries the failure itself, not just the stage (t1784).
        detail = _rollback(record_id, nonce, pane_id, f"respawn:{exc}")
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
    _clear_frozen_stamp(pane_id, record_id, nonce)
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
        _clear_frozen_stamp(rec.get("pane_id", ""), record_id, nonce)
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
        _clear_frozen_stamp(rec.get("pane_id", ""), record_id, nonce)
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


def restore_all(*, repick: bool = False,
                session: str | None = None) -> list[RestoreResult]:
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
            results.append(restore(record_id, repick=repick, session=session))
        except Exception as exc:            # never abandon the rest of the batch
            results.append(RestoreResult(
                record_id, False, "error",
                f"RESTORE_FAILED:{record_id}|{exc}"))
    return results


# --- CLI --------------------------------------------------------------------


def main(argv: list[str]) -> int:
    """`restore <id> [--repick] [--session S]` / `restore --all [--repick] [--session S]`.

    Exit codes match `aitask_frozen.sh`'s documented contract: 0 all-ok,
    1 some-failed, 2 usage.
    """
    args = list(argv)
    if args and args[0] == "restore":
        args = args[1:]
    # `--session` first: its value is taken verbatim and may itself start with
    # `-` (a session literally named `-n`), so it must leave `args` before any
    # other flag scan could mistake it for an option.
    args, session, err = take_session_arg(args)
    if err:
        print(f"ERROR:{err}", file=sys.stderr)
        return 2
    repick = "--repick" in args
    args = [a for a in args if a != "--repick"]

    if args and args[0] == "--all":
        if len(args) != 1:
            print("Usage: aitask_frozen.sh restore --all [--repick] [--session NAME]",
                  file=sys.stderr)
            return 2
        results = restore_all(repick=repick, session=session)
        for result in results:
            print(result.line)
        ok = sum(1 for r in results if r.ok)
        print(f"RESTORE_ALL:{ok}/{len(results)}")
        return 0 if ok == len(results) else 1

    if len(args) != 1 or not args[0] or args[0].startswith("-"):
        print("Usage: aitask_frozen.sh restore <id> [--repick] [--session NAME]"
              " | restore --all", file=sys.stderr)
        return 2

    result = restore(args[0], repick=repick, session=session)
    print(result.line)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
