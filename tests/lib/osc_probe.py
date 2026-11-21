#!/usr/bin/env python3
"""Ask the terminal this runs in for its default colours (t2051).

Runs INSIDE a tmux pane: writes the OSC 10 (foreground) and OSC 11 (background)
queries to the pane's tty in raw mode and records what comes back. Inside tmux
it is tmux that answers, from the colours of the first client attached to the
pane's session — which is exactly the value a coding agent reads at startup.

``ESC [ c`` (primary device attributes) is sent last as an end marker: tmux
always answers it, so the reader can stop as soon as it arrives instead of
waiting out the timeout, and its presence proves the pane was read at all.

Usage:  osc_probe.py <output-file>

The reply bytes are written as a Python ``repr`` to ``<output-file>`` (via a
rename, so a reader never sees a partial file). It needs a real tty, so run it
in a tmux window, never through a pipe. Parsed by
``tests/lib/fake_terminal.py::parse_probe``.
"""
import os
import select
import sys
import termios
import time
import tty

QUERY = b"\x1b]10;?\x1b\\" b"\x1b]11;?\x1b\\" b"\x1b[c"


def main() -> int:
    out = sys.argv[1]
    fd = os.open("/dev/tty", os.O_RDWR)
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    buf = b""
    try:
        os.write(fd, QUERY)
        end = time.time() + 2.0
        while time.time() < end:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                buf += os.read(fd, 4096)
                if b"\x1b[?" in buf and buf.rstrip().endswith(b"c"):
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)
    with open(out + ".tmp", "w") as f:
        f.write(repr(buf))
    os.rename(out + ".tmp", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
