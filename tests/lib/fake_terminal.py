"""A pty-backed "real terminal" tmux client for live tests (t2051).

tmux learns a terminal's default colours by sending it OSC 10 / OSC 11 queries
when a client attaches. A test that wants to observe what tmux then answers to a
program inside a pane needs a client that behaves like a real terminal: a tty,
and replies to those queries. ``FakeTerminal`` is that client — ``pty.fork()``
running ``tmux attach``, plus a reader thread that answers the colour queries
with fixed, recognisable values.

It is a *real* (non-control) client as far as tmux is concerned, so it is also
the subject for anything tmux does to attached terminals: moving them when
their session is destroyed, detaching them, running hooks for them.

Use only against a private tmux server (an explicit ``-L`` socket and an
environment without ``TMUX`` / ``TMUX_PANE``); the caller passes both.
"""
from __future__ import annotations

import ast
import fcntl
import os
import pty
import re
import signal
import struct
import subprocess
import sys
import termios
import threading
import time
from pathlib import Path

#: What the fake terminal reports, and so what a correct probe reads back.
FG = "cccc/dddd/eeee"
BG = "2222/3333/4444"
REAL_COLOURS = {"fg": "rgb:" + FG, "bg": "rgb:" + BG}
#: What tmux answers when a control-mode client supplies the colours.
BLACK = {"fg": "rgb:0000/0000/0000", "bg": "rgb:0000/0000/0000"}

OSC_PROBE = Path(__file__).resolve().parent / "osc_probe.py"

#: A 16-colour palette for OSC 4 queries (``PALETTE[n % 16]``). tmux does not
#: answer OSC 4 itself; with ``allow-passthrough on`` a program's palette query
#: reaches the outer terminal, i.e. this client. OpenCode's ``system`` theme
#: needs those answers — without them it silently falls back to a built-in
#: theme and never uses the default colours this file exists to test.
PALETTE = ["1e1e/1e1e/2e2e", "f3f3/8b8b/a8a8", "a6a6/e3e3/a1a1", "f9f9/e2e2/afaf",
           "8989/b4b4/fafa", "f5f5/c2c2/e7e7", "9494/e2e2/d5d5", "baba/c2c2/dede",
           "5858/5b5b/7070", "f3f3/8b8b/a8a8", "a6a6/e3e3/a1a1", "f9f9/e2e2/afaf",
           "8989/b4b4/fafa", "f5f5/c2c2/e7e7", "9494/e2e2/d5d5", "a6a6/adad/c8c8"]

_QUERY_RE = re.compile(rb"\x1b\](10|11|4;\d+);\?(\x1b\\|\x07)")


class FakeTerminal:
    """``tmux attach -t =<session>`` under a pty, answering OSC 10/11."""

    def __init__(self, tmux_argv: list[str], env: dict, session: str,
                 answer: bool = True, palette: bool = False):
        self.answer = answer
        #: Also answer OSC 4 palette queries (see :data:`PALETTE`).
        self.palette = palette
        #: How many palette queries reached this terminal.
        self.palette_queries = 0
        self._stop = False
        self._reaped = False
        child_env = dict(env)
        child_env["TERM"] = "xterm-256color"
        # openpty + Popen, not pty.fork(): the tests that use this run backends
        # on other threads, and forking a multi-threaded process can deadlock
        # the child. tmux only needs a tty on stdin, in its own session.
        fd, slave = pty.openpty()
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        try:
            self._proc = subprocess.Popen(
                [*tmux_argv, "attach", "-t", "=" + session], env=child_env,
                stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        finally:
            os.close(slave)
        self.pid, self.fd = self._proc.pid, fd
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        tail = b""
        while not self._stop:
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                return
            if not data:
                return
            if not self.answer:
                continue
            tail = (tail + data)[-65536:]
            while True:
                m = _QUERY_RE.search(tail)
                if not m:
                    break
                key = m.group(1)
                tail = tail[m.end():]
                if key.startswith(b"4;"):
                    self.palette_queries += 1
                    if not self.palette:
                        continue
                    rgb = PALETTE[int(key[2:]) % 16]
                else:
                    rgb = FG if key == b"10" else BG
                try:
                    os.write(self.fd, b"\x1b]" + key + b";rgb:"
                             + rgb.encode() + b"\x1b\\")
                except OSError:
                    return

    def exited(self) -> bool:
        """Whether the tmux client process has ended (tmux detached it)."""
        if not self._reaped and self._proc.poll() is not None:
            self._reaped = True
        return self._reaped

    def close(self) -> None:
        self._stop = True
        if not self.exited():
            try:
                os.kill(self.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 3.0
            while not self.exited() and time.monotonic() < deadline:
                time.sleep(0.02)
            if not self.exited():
                self._proc.kill()
                self._proc.wait()
                self._reaped = True
        try:
            os.close(self.fd)
        except OSError:
            pass


def parse_probe(text: str) -> dict:
    """Parse an ``osc_probe.py`` output file into ``{"fg", "bg", "read"}``.

    ``fg`` / ``bg`` are ``rgb:…`` strings, or ``"no-reply"`` when tmux sent
    none. ``read`` says the end marker arrived, i.e. the probe really ran in a
    terminal — without it a ``no-reply`` proves nothing.
    """
    raw = ast.literal_eval(text)
    result = {}
    for key, pattern in (("fg", rb"\]10;(rgb:[0-9a-f/]+)"),
                         ("bg", rb"\]11;(rgb:[0-9a-f/]+)")):
        m = re.search(pattern, raw)
        result[key] = m.group(1).decode() if m else "no-reply"
    result["read"] = b"\x1b[?" in raw
    return result


def probe_command(out_path: str) -> str:
    """The shell command that runs the probe in a pane and then idles."""
    import shlex
    return (f"{shlex.quote(sys.executable)} {shlex.quote(str(OSC_PROBE))} "
            f"{shlex.quote(out_path)}; sleep 30")
