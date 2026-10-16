#!/usr/bin/env python3
"""bounded_run.py - run a command under a hard time bound that owns its process tree.

Library::

    from bounded_run import run_bounded, noninteractive_env

CLI (used by the shell crew helpers in lib/agentcrew_utils.sh)::

    python3 bounded_run.py --timeout <seconds> [--noninteractive] -- <cmd> [args...]

The command runs in a NEW SESSION, so it has no controlling terminal: nothing it
starts (ssh, plink, a configured transport script) can open /dev/tty to prompt.
Its stdin is /dev/null and its stdout/stderr go to temporary files rather than
pipes, so a descendant that outlives it (an ssh ControlPersist master) cannot
block the reader.

On expiry the session's process group is killed: SIGTERM (git removes its
*.lock files), SIGCONT (a stopped member must run to see the TERM), then SIGKILL
for whatever is left after a grace period. On a normal exit the group is never
signalled, so a ControlPersist master survives.

Nested runners get strictly ordered graces. A runner whose child starts another
runner (brainstorm -> ait crew addwork -> this CLI -> git) cannot reach the inner
command's separate session, so the inner cleanup must finish before the outer
SIGKILL lands. Each runner exports AIT_BOUNDED_RUN_GRACE = max(1, own - 2) to
its child, and a runner that finds the variable uses it as its own grace. With
the defaults the top level waits 5s and the nested CLI 3s. The 2s margin covers
signal delivery, the handler, the poll and the reap. Two levels are guaranteed;
a third floors at 1s.

Stdlib only: the shell side runs it with whatever python3 the crew scripts
already resolve (launch_modes_sh.sh).
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

KILL_GRACE_SECONDS = 5.0
NESTING_MARGIN_SECONDS = 2.0
MIN_GRACE_SECONDS = 1.0
MAX_GRACE_SECONDS = 60.0
GRACE_ENV = "AIT_BOUNDED_RUN_GRACE"

TIMED_OUT = 124  # coreutils timeout's code
NOT_EXECUTABLE = 126
NOT_FOUND = 127

_POLL_SECONDS = 0.1

# The non-interactive policy (noninteractive_env). Set-but-empty GIT_ASKPASS is
# load-bearing: git's prompt code tries GIT_ASKPASS, then core.askPass, then
# SSH_ASKPASS, and only an EMPTY GIT_ASKPASS stops it reaching the other two —
# GIT_TERMINAL_PROMPT=0 alone still runs a configured askpass program.
# SSH_ASKPASS_REQUIRE=never covers OpenSSH >= 8.4; older OpenSSH falls back to a
# default askpass whenever DISPLAY is set, hence the removals.
_PROMPT_ENV_SET = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS_REQUIRE": "never",
    "GCM_INTERACTIVE": "never",
}
_PROMPT_ENV_REMOVED = ("SSH_ASKPASS", "DISPLAY", "WAYLAND_DISPLAY")


class BoundedResult(subprocess.CompletedProcess):
    """A CompletedProcess that also says whether it ended after a stop request."""

    def __init__(self, args, returncode, stdout, stderr, stopped=False):
        super().__init__(args, returncode, stdout, stderr)
        self.stopped = stopped


def effective_grace(env=None) -> float:
    """This runner's kill grace: AIT_BOUNDED_RUN_GRACE when sane, else the default."""
    raw = (os.environ if env is None else env).get(GRACE_ENV, "")
    try:
        value = float(raw)
    except ValueError:
        return KILL_GRACE_SECONDS
    # `not (… <= …)` also rejects nan and inf.
    if not (0 < value <= MAX_GRACE_SECONDS):
        return KILL_GRACE_SECONDS
    return value


def child_grace(grace: float) -> float:
    """The grace handed to a nested runner: strictly smaller, with a margin."""
    return max(MIN_GRACE_SECONDS, grace - NESTING_MARGIN_SECONDS)


def noninteractive_env(base=None) -> dict:
    """A copy of ``base`` (default: os.environ) in which nothing can prompt.

    Configured SSH commands (core.sshCommand, GIT_SSH_COMMAND, GIT_SSH) are left
    alone: injecting ``-o BatchMode=yes`` would break plink-variant commands.
    With no controlling terminal (run_bounded's new session), no askpass program
    and no display, no transport has a channel to prompt through. Credentials
    must come from ssh-agent or a credential helper.
    """
    env = dict(os.environ if base is None else base)
    for name in _PROMPT_ENV_REMOVED:
        env.pop(name, None)
    env.update(_PROMPT_ENV_SET)
    return env


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def kill_process_group(proc: subprocess.Popen, grace: float) -> None:
    """SIGTERM + SIGCONT the child's process group, SIGKILL it after ``grace`` seconds.

    Polls the GROUP, not the leader: a member that ignores SIGTERM outlives a
    leader that died at once. Reaps the leader.
    """
    pgid = proc.pid  # start_new_session: the leader's pid is the group id
    _signal_group(pgid, signal.SIGTERM)
    _signal_group(pgid, signal.SIGCONT)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        proc.poll()  # reap the leader, so a zombie does not keep the group "alive"
        if not _group_alive(pgid):
            break
        time.sleep(_POLL_SECONDS)
    else:
        _signal_group(pgid, signal.SIGKILL)
    proc.wait()


# Signals deferred while a process group is being killed.
_DEFERRED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def _shielded_kill(proc: subprocess.Popen, grace: float) -> None:
    """kill_process_group, with SIGINT/SIGTERM/SIGHUP deferred until it is done.

    A signal that lands mid-cleanup must not abort it: the TERM -> CONT -> KILL
    sequence is what ends the group, and for a nested runner a separate session
    nothing else can reach. So the three are recorded for the duration, and the
    first one is re-delivered afterwards through the handler that was in place,
    so the process still raises or exits the way that signal says. Python
    handlers run only on the main thread, so other threads need no shield.
    """
    if threading.current_thread() is not threading.main_thread():
        kill_process_group(proc, grace)
        return
    received: list[int] = []

    def _defer(signum, _frame):
        if not received:
            received.append(signum)

    previous = {sig: signal.signal(sig, _defer) for sig in _DEFERRED_SIGNALS}
    try:
        kill_process_group(proc, grace)
    finally:
        for sig, handler in previous.items():
            # None: a handler installed outside Python; restore the default.
            signal.signal(sig, signal.SIG_DFL if handler is None else handler)
    if received:
        signal.raise_signal(received[0])


class Cancelled(Exception):
    """run_bounded's ``cancelled()`` asked it to stop; the group is already dead."""


def _wait(proc: subprocess.Popen, timeout: float, cancelled) -> None:
    """proc.wait(timeout), also returning early through ``Cancelled`` if asked."""
    if cancelled is None:
        proc.wait(timeout=timeout)
        return
    deadline = time.monotonic() + timeout
    while proc.poll() is None:
        if cancelled():
            raise Cancelled
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(proc.args, timeout)
        time.sleep(min(_POLL_SECONDS, remaining))


def _read(fh) -> str:
    fh.seek(0)
    return fh.read().decode("utf-8", errors="replace")


def run_bounded(cmd, timeout, *, env=None, stop_grace=0.0, cwd=None,
                cancelled=None) -> BoundedResult:
    """Run ``cmd`` (capturing text output), killing its process group after ``timeout`` s.

    Raises ``subprocess.TimeoutExpired`` once the group is dead (subprocess.run's
    contract), with the output so far on the exception. ``stop_grace > 0`` makes
    the expiry a STOP REQUEST first: SIGTERM to the leader alone, which it may
    honour at a safe point, and up to ``stop_grace`` more seconds to exit; that
    result is returned with ``stopped=True``. Only a child still running after it
    is killed. ``cancelled`` (a callable, polled while waiting) ends the wait
    early: the group is killed and ``Cancelled`` raised. Any other exception
    (KeyboardInterrupt, a signal turned into an exception) also kills the group
    before propagating, and signals arriving during that cleanup are deferred
    until it is done (_shielded_kill).
    """
    grace = effective_grace()
    child_env = dict(os.environ if env is None else env)
    child_env[GRACE_ENV] = f"{child_grace(grace):g}"
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                env=child_env, cwd=cwd, start_new_session=True)
        stopped = False
        try:
            try:
                _wait(proc, timeout, cancelled)
            except subprocess.TimeoutExpired:
                if stop_grace <= 0:
                    raise
                stopped = True
                proc.send_signal(signal.SIGTERM)  # the leader alone: a stop request
                _wait(proc, stop_grace, cancelled)
        except BaseException as exc:
            _shielded_kill(proc, grace)
            if isinstance(exc, subprocess.TimeoutExpired):
                exc.output, exc.stderr = _read(out), _read(err)
            raise
        return BoundedResult(cmd, proc.returncode, _read(out), _read(err), stopped)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# The CLI's signal handlers only RECORD: no exception can ever cut into a
# cleanup, not even in the instant before _shielded_kill installs its deferral.
# run_bounded polls the record (``cancelled``) while it waits, and main() ends
# the CLI by the first recorded signal once the group is dead, so the calling
# shell still sees a signal death (and Ctrl-C still stops the script).
_received: list[int] = []


def _record_signal(signum, _frame):
    if not _received:
        _received.append(signum)


def _die_by(signum: int) -> int:
    sys.stdout.flush()
    sys.stderr.flush()
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)
    return 128 + signum  # only if the signal did not end us


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="bounded_run.py",
        description="Run a command under a hard time bound that owns its process tree.")
    parser.add_argument("--timeout", type=float, required=True,
                        help="seconds before the command's process group is killed")
    parser.add_argument("--noninteractive", action="store_true",
                        help="run with noninteractive_env(): nothing can prompt")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command [args...]")
    args = parser.parse_args(argv)
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        parser.error("no command given")
    if not args.timeout > 0:
        parser.error("--timeout must be positive")

    for sig in _DEFERRED_SIGNALS:
        signal.signal(sig, _record_signal)
    env = noninteractive_env() if args.noninteractive else None
    try:
        result = run_bounded(cmd, args.timeout, env=env,
                             cancelled=lambda: bool(_received))
    except Cancelled:
        return _die_by(_received[0])
    except subprocess.TimeoutExpired as exc:
        sys.stdout.write(exc.output or "")
        sys.stderr.write(exc.stderr or "")
        sys.stderr.write(f"bounded_run: timed out after {args.timeout:g}s\n")
        rc = TIMED_OUT
    except FileNotFoundError as exc:
        sys.stderr.write(f"bounded_run: {exc}\n")
        rc = NOT_FOUND
    except PermissionError as exc:
        sys.stderr.write(f"bounded_run: {exc}\n")
        rc = NOT_EXECUTABLE
    else:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        rc = result.returncode if result.returncode >= 0 else 128 - result.returncode
    # A signal that arrived during the timeout cleanup, or after the command
    # ended, still ends the CLI by that signal.
    if _received:
        return _die_by(_received[0])
    return rc


if __name__ == "__main__":
    sys.exit(main())
