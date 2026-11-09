"""A stand-in monitor status server PROCESS for the restart tests (t2246).

    python3 fake_status_server.py serve --socket SOCK [--mode graceful|hung]

Its argv carries ``serve --socket <sock>`` exactly as the real server's does, so
``status_restart`` identifies it through the real ``ps``. It listens on SOCK
(nothing it accepts is ever answered: the restart procedure never talks to a
server) and prints ``READY`` once bound.

- ``graceful`` — on SIGTERM unlink its own socket and exit 0 (the real
  server's exit path).
- ``hung`` — ignore SIGTERM (a server the procedure must report, not force).

The restart-hook test also copies this file to a scratch tree's
``monitor/status_server.py``, so its argv names that path as the owner.
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import time


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--socket", required=True)
    s.add_argument("--mode", choices=("graceful", "hung"), default="graceful")
    args, _unknown = p.parse_known_args()

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(args.socket)
    srv.listen(8)

    def stop(_signo, _frame):
        try:
            os.unlink(args.socket)
        except FileNotFoundError:
            pass
        os._exit(0)

    if args.mode == "hung":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    else:
        signal.signal(signal.SIGTERM, stop)
    print("READY", flush=True)
    while True:
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
