"""Identity of the process serving questions, and whether it still runs.

A question that falls back to the prompt is stamped with the server process
that holds it (`Store._stamp`). `start` fences pid reuse: a record whose pid
now belongs to another process is a closed session, not a waiting one.

Whether the ancestor chain reaches the client's terminal pane depends on how
the client was started (measured on codex 0.167.2):

  in-process   every framework launch: the server is a child of the codex
               process the pane runs, so the chain contains the pane's pid.
  daemon       a codex started by hand: the shared `codex app-server` daemon
               starts the server. The chain then says nothing about the pane -
               and while the pane that first started the daemon lives, the
               daemon is ITS child, so the chain would name the wrong pane.

`ancestors` therefore stops below an app-server process, and `detached` says
that it did. A detached server cannot be tied to one pane; the clients that
could be showing its question are found with `foreground`, `is_client`,
`hosts_sessions` and `inside` (waiting.py).
"""
from __future__ import annotations

import os
import subprocess

MAX_DEPTH = 32
DAEMON_PACKAGE = "/packages/app-server-daemon/"


def _argv(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            return [os.fsdecode(part) for part in handle.read().split(b"\0") if part]
    except OSError:
        pass
    try:  # no procfs: element boundaries are a guess, good enough for argv[1]
        done = subprocess.run(["ps", "-o", "args=", "-p", str(int(pid))],
                              capture_output=True, text=True, timeout=5, check=False)
        return done.stdout.split()
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def is_app_server(argv):
    """True for a codex app-server (the shared daemon, or any other host that
    runs sessions for clients in other processes)."""
    if not argv:
        return False
    return DAEMON_PACKAGE in argv[0] or (
        os.path.basename(argv[0]) == "codex" and len(argv) > 1 and argv[1] == "app-server")


SERVER_SCRIPT = "aitask_questions_server.py"
SESSION_HOST = "codex-code-mode"  # codex-code-mode-host, the per-client session host


def is_client(argv):
    """True for a codex terminal client (native binary or its node launcher)."""
    return bool(argv) and not is_app_server(argv) and any(
        os.path.basename(part).startswith("codex") for part in argv[:2])


def _children(pid):
    """Direct children of a process. Linux lists them per THREAD
    (`task/<tid>/children`): a child started from a worker thread is absent
    from the main thread's list, so every thread is read."""
    found = set()
    try:
        tasks = os.listdir(f"/proc/{pid}/task")
    except OSError:
        tasks = None
    if tasks is not None:
        for task in tasks:
            try:
                with open(f"/proc/{pid}/task/{task}/children", "rb") as handle:
                    found.update(int(part) for part in handle.read().split())
            except (OSError, ValueError):
                continue  # a thread that ended between the two reads
        return sorted(found)
    try:  # no procfs
        done = subprocess.run(["pgrep", "-P", str(int(pid))],
                              capture_output=True, text=True, timeout=5, check=False)
        return [int(part) for part in done.stdout.split()]
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def hosts_sessions(pid):
    """True when this client runs its conversations in its own process tree
    (in-process), False when a shared daemon runs them (a remote client).

    Measured on codex 0.166.0-0.168.0: an in-process client has a
    `codex-code-mode-host` child from startup, and the question server too
    when one is configured; a client of the shared daemon has no children at
    all. Like `describe`, the walk stops at an app-server: what a shared
    daemon runs belongs to the daemon's clients, also when this process
    happens to be the one that started the daemon."""
    seen, queue = set(), [pid]
    while queue and len(seen) < 512:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        for child in _children(current):
            argv = _argv(child)
            if is_app_server(argv):
                continue
            if argv and os.path.basename(argv[0]).startswith(SESSION_HOST) \
                    or any(part.endswith(SERVER_SCRIPT) for part in argv):
                return True
            queue.append(child)
    return False


def inside(pid, directory):
    """True when the process's working directory is `directory` or below it."""
    try:
        cwd = os.path.realpath(os.readlink(f"/proc/{pid}/cwd"))
    except OSError:
        try:  # no procfs
            done = subprocess.run(["lsof", "-a", "-p", str(int(pid)), "-d", "cwd", "-Fn"],
                                  capture_output=True, text=True, timeout=5, check=False)
            cwd = next((os.path.realpath(line[1:]) for line in done.stdout.splitlines()
                        if line.startswith("n")), "")
        except (OSError, subprocess.SubprocessError, ValueError):
            return False
    root = os.path.realpath(str(directory))
    return bool(cwd) and (cwd == root or cwd.startswith(root.rstrip(os.sep) + os.sep))


def foreground(pid):
    """The process in the foreground of `pid`'s terminal, as
    {"pid", "start"}, or None. For a pane's top-level process this is the
    program the pane is running now - a new identity each time one starts."""
    front = None
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            front = int(handle.read().rsplit(b")", 1)[1].split()[5])
    except (OSError, IndexError, ValueError):
        try:  # no procfs
            done = subprocess.run(["ps", "-o", "tpgid=", "-p", str(int(pid))],
                                  capture_output=True, text=True, timeout=5, check=False)
            front = int(done.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
    if front is None or front <= 1:
        return None
    probe = _probe(front)
    if probe is None or not probe[1]:
        return None
    return {"pid": front, "start": probe[1]}


def _probe(pid):
    """(parent pid, start token) of a live process, or None."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            fields = handle.read().rsplit(b")", 1)[1].split()
        return int(fields[1]), fields[19].decode()
    except (OSError, IndexError, ValueError):
        pass
    try:  # no procfs (macOS, BSD)
        done = subprocess.run(["ps", "-o", "ppid=", "-o", "lstart=", "-p", str(int(pid))],
                              capture_output=True, text=True, timeout=5, check=False)
        parent, start = done.stdout.strip().split(None, 1)
        return int(parent), start.strip()
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def describe():
    """This process: {"pid", "start", "ancestors", "detached"}.

    ancestors: nearest first, ending below the first app-server process.
    detached: True when the chain was cut there.
    """
    pid = os.getpid()
    probe = _probe(pid)
    ancestors, detached, current = [], False, probe[0] if probe else os.getppid()
    while current > 1 and len(ancestors) < MAX_DEPTH:
        if is_app_server(_argv(current)):
            detached = True
            break
        ancestors.append(current)
        parent = _probe(current)
        if parent is None:
            break
        current = parent[0]
    return {"pid": pid, "start": probe[1] if probe else "", "ancestors": ancestors,
            "detached": detached}


def alive(owner):
    """True while the described process is the one still running under its pid."""
    try:
        probe = _probe(int(owner["pid"]))
        return probe is not None and bool(owner["start"]) and probe[1] == owner["start"]
    except (KeyError, TypeError, ValueError):
        return False
