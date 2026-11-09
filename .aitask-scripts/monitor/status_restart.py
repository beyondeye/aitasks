"""status_restart - stop a monitor status server through its VERIFIED process (stdlib only).

The restart procedure shared by ``status_server.py restart`` (the operator verb
behind ``ait monitor --restart-server``) and the ``ait upgrade`` hook
(``aitask_setup.sh:report_monitor_server_restart``). Specification:
``aidocs/framework/monitor_status_protocol.md`` ("Restart").

It is a PROCESS contract, not Python internals, so it applies to whichever
implementation serves the socket (the Python server today, ``ait-monitord``
later). A server process must:

- run with ``serve --socket <sock>`` adjacent in its argv;
- exit gracefully on SIGTERM (close its connections and control client, unlink
  its own socket); exit releases its flock.

For one socket the procedure is:

1. find the ONE process whose args contain ``serve --socket <sock>`` (``ps``);
   none and nothing accepts on the socket → ``STALE``; none but something
   accepts → ``RETIRE_FAILED|unverified``; several → ``RETIRE_FAILED|ambiguous_pids``;
2. with ``owner``, skip unless the args name that script/binary right before
   ``serve`` (``SKIPPED``);
3. re-read that pid's args, then send SIGTERM;
4. wait (default 5 s) until the pid is gone — no such process, or its args no
   longer match (a zombie, a recycled pid);
5. report ``RETIRED:<sock>|pid=<p>`` or ``RETIRE_FAILED:<sock>|pid=<p>|still_running``.

Evidence is always the process. Socket silence and the lock are never used: a
reconnecting client may legitimately take the lock for a fresh server while this
runs. There is deliberately no SIGKILL escalation: a server that ignores SIGTERM
is reported and recovered by hand.

Stdlib only (with ``status_paths``): the upgrade hook may run it before the
framework venv can import ``status_server``.

CLI (the upgrade hook's entry point; every scope flag is mandatory, so this
entry point never performs an unscoped retire)::

    python3 .aitask-scripts/monitor/status_restart.py retire --all-keys --all-versions --owner-path P [--runtime-dir D] [--wait S]
"""
from __future__ import annotations

import argparse
import math
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

try:  # imported as part of the `monitor` package
    from .status_paths import list_server_sockets, runtime_dir
except ImportError:  # run as a script, or imported top-level
    from status_paths import list_server_sockets, runtime_dir  # noqa: E402

#: Seconds a ``ps`` call may take.
PS_TIMEOUT = 5.0
#: Seconds to wait for a signalled server to be gone.
DEFAULT_WAIT = 5.0
#: Seconds a connect attempt may take when classifying an unmatched socket.
CONNECT_TIMEOUT = 1.0
_POLL = 0.1


@dataclass(frozen=True)
class Proc:
    pid: int
    args: str


def run_ps(argv) -> str | None:
    """``ps`` stdout on a zero exit, else ``None`` (unknown).

    A nonzero exit is never read as "no such process": ``ps -p`` exits nonzero
    both for a missing pid and for its own failure, and only ``kill(pid, 0)``
    (``ProcessLookupError``) tells the two apart. Absence is proven there."""
    try:
        out = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                             timeout=PS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def server_processes(ps=run_ps) -> list[Proc] | None:
    """Every process with its full args (``ps -ww``: never truncated), or
    ``None`` when ``ps`` is unavailable."""
    out = ps(["ps", "-ww", "-eo", "pid=,args="])
    if out is None:
        return None
    procs = []
    for line in out.splitlines():
        head, _, args = line.strip().partition(" ")
        if head.isdigit():
            procs.append(Proc(int(head), args.strip()))
    return procs


def process_args(pid: int, ps=run_ps) -> str | None:
    """The current args of ``pid``, or ``None`` when ``ps`` could not tell
    (failed, or the pid is gone — the caller proves absence with ``kill``)."""
    out = ps(["ps", "-ww", "-o", "args=", "-p", str(pid)])
    if out is None:
        return None
    lines = out.strip().splitlines()
    return lines[0].strip() if lines else ""


def _ends_token(args: str, end: int) -> bool:
    return end == len(args) or args[end].isspace()


def args_match(args: str, sock, owner=None) -> bool:
    """``args`` belong to the server of ``sock``: they contain
    ``serve --socket <sock>`` ending a token. With ``owner``, the token right
    before ``serve`` must be exactly that script or binary path."""
    needle = f"serve --socket {sock}"
    start = 0
    while True:
        i = args.find(needle, start)
        if i < 0:
            return False
        start = i + 1
        if (i > 0 and not args[i - 1].isspace()) or not _ends_token(args, i + len(needle)):
            continue
        if owner is None:
            return True
        prefix = args[:i].rstrip()
        if prefix == str(owner) or prefix.endswith(f" {owner}"):
            return True


def socket_connectable(sock, timeout: float = CONNECT_TIMEOUT) -> bool:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(sock))
    except OSError:
        return False
    finally:
        s.close()
    return True


def pid_gone(pid: int, sock, *, ps=run_ps, kill=os.kill) -> bool:
    """True only on positive evidence: no such process, or a process whose args
    no longer match ``sock`` (a zombie reports ``[name] <defunct>``; a recycled
    pid runs something else). An unreadable ``ps`` is never "gone"."""
    try:
        kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        pass
    args = process_args(pid, ps)
    if args is None:
        return False          # inspection failed while the pid exists: unknown
    return not args_match(args, sock)


def find_server(sock, *, ps=run_ps) -> tuple[str, list[Proc]]:
    """``("ok"|"ps_unavailable", matches)`` — the processes serving ``sock``,
    never this process itself."""
    procs = server_processes(ps)
    if procs is None:
        return "ps_unavailable", []
    me = os.getpid()
    return "ok", [p for p in procs if p.pid != me and args_match(p.args, sock)]


def retire_one(sock, *, owner=None, wait: float = DEFAULT_WAIT, ps=run_ps,
               kill=os.kill, clock=time.monotonic, sleep=time.sleep,
               connectable=socket_connectable) -> str:
    """Stop the server of ``sock`` (see the module docstring). One status line."""
    if not math.isfinite(wait) or wait <= 0:
        raise ValueError(f"wait must be a finite number > 0, got {wait!r}")
    sock = str(sock)
    owner = os.path.realpath(owner) if owner is not None else None
    state, matches = find_server(sock, ps=ps)
    if state != "ok":
        return f"RETIRE_FAILED:{sock}|{state}"
    if len(matches) > 1:
        pids = ",".join(str(p.pid) for p in matches)
        return f"RETIRE_FAILED:{sock}|ambiguous_pids:{pids}"
    if not matches:
        if not connectable(sock):
            return f"STALE:{sock}"
        # Something answers that no verifiable server process owns: never signalled.
        return f"SKIPPED:{sock}|unverified" if owner else f"RETIRE_FAILED:{sock}|unverified"
    proc = matches[0]
    if owner is not None and not args_match(proc.args, sock, owner=owner):
        return f"SKIPPED:{sock}|other_owner"
    # Re-verify right before the signal, with the SAME owner scope: the listing
    # may be a moment old, and an exec or a recycled pid can now be another
    # installation's server on the same socket.
    args = process_args(proc.pid, ps)
    if args is None:
        try:
            kill(proc.pid, 0)
        except ProcessLookupError:
            return f"STALE:{sock}"
        except PermissionError:
            pass
        return f"RETIRE_FAILED:{sock}|ps_unavailable"
    if not args_match(args, sock):
        return f"STALE:{sock}"
    if owner is not None and not args_match(args, sock, owner=owner):
        return f"SKIPPED:{sock}|other_owner"
    try:
        kill(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return f"STALE:{sock}"
    except PermissionError:
        return f"RETIRE_FAILED:{sock}|pid={proc.pid}|not_permitted"
    end = clock() + wait
    while True:
        if pid_gone(proc.pid, sock, ps=ps, kill=kill):
            return f"RETIRED:{sock}|pid={proc.pid}"
        if clock() >= end:
            return f"RETIRE_FAILED:{sock}|pid={proc.pid}|still_running"
        sleep(_POLL)


def describe(sock, *, ps=run_ps) -> dict:
    """``{pid, started, script}`` for the ``status`` verb; ``-`` where unknown."""
    state, matches = find_server(sock, ps=ps)
    info = {"pid": "-", "started": "-", "script": "-"}
    if state != "ok" or len(matches) != 1:
        if len(matches) > 1:
            info["pid"] = ",".join(str(p.pid) for p in matches)
        return info
    proc = matches[0]
    info["pid"] = str(proc.pid)
    before = proc.args[:proc.args.find(f"serve --socket {sock}")].split()
    if before:
        info["script"] = before[-1]
    out = ps(["ps", "-o", "lstart=", "-p", str(proc.pid)])
    if out and out.strip():
        info["started"] = " ".join(out.split())
    return info


def failed(lines) -> bool:
    return any(line.startswith("RETIRE_FAILED:") for line in lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _positive(text: str) -> float:
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"must be a finite number > 0, got {text!r}")
    return value


def _cmd_retire(args) -> int:
    if not (args.all_keys and args.all_versions):
        print("retire: --all-keys and --all-versions are both required "
              "(this entry point is owner-scoped only)", file=sys.stderr)
        return 2
    directory = Path(args.runtime_dir) if args.runtime_dir else runtime_dir()
    sockets = list_server_sockets(directory)
    if not sockets:
        print("NO_SERVER", flush=True)
        return 0
    lines = []
    for entry in sockets:
        line = retire_one(entry.path, owner=args.owner_path, wait=args.wait)
        lines.append(line)
        print(line, flush=True)
    return 1 if failed(lines) else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="status_restart.py",
                                description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("retire", help="SIGTERM the verified servers started from one path")
    r.add_argument("--all-keys", action="store_true",
                   help="consider every tmux server's sockets (required)")
    r.add_argument("--all-versions", action="store_true",
                   help="consider every VERSION's sockets (required)")
    r.add_argument("--owner-path", required=True,
                   help="only servers whose argv names this script/binary before 'serve'")
    r.add_argument("--runtime-dir", default=None)
    r.add_argument("--wait", type=_positive, default=DEFAULT_WAIT)
    r.set_defaults(func=_cmd_retire)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
