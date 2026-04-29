#!/usr/bin/env python3
"""Launch Codex CLI and enter plan mode with an aitask skill prompt."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import sys
import time


def _load_pexpect():
    try:
        import pexpect  # type: ignore
    except ImportError:
        print(
            "Error: Python package 'pexpect' is required for Codex plan-mode "
            "skill launches. Run 'ait setup' to install project Python "
            "dependencies, or install pexpect for the Python used here.",
            file=sys.stderr,
        )
        return None
    return pexpect


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start Codex in an interactive PTY, then send /plan plus the "
            "provided aitask skill prompt as one composer submission."
        )
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Aitask skill prompt to send with /plan.",
    )
    parser.add_argument(
        "--pre-spawn-delay",
        type=float,
        default=float(os.environ.get("AITASK_CODEX_PLAN_PRE_SPAWN_DELAY", "0")),
        help=(
            "Seconds to wait before spawning Codex. Defaults to 0; retained "
            "only as a diagnostic override."
        ),
    )
    parser.add_argument(
        "--startup-delay",
        type=float,
        default=float(os.environ.get("AITASK_CODEX_PLAN_STARTUP_DELAY", "2")),
        help="Seconds to wait after spawning Codex before sending the prompt.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Codex command to run, prefixed by --.",
    )
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("missing Codex command after --")
    return args


def _terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(120, 40))
    return size.lines, size.columns


def _sync_child_size(child) -> None:
    rows, cols = _terminal_size()
    child.setwinsize(rows, cols)


def main() -> int:
    args = _parse_args()
    pexpect = _load_pexpect()
    if pexpect is None:
        return 127

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "Error: Codex plan-mode skill launch requires an interactive TTY.",
            file=sys.stderr,
        )
        return 2

    time.sleep(max(args.pre_spawn_delay, 0))

    rows, cols = _terminal_size()
    child = pexpect.spawn(
        args.command[0],
        args.command[1:],
        dimensions=(rows, cols),
        encoding="utf-8",
        timeout=None,
    )

    def _handle_resize(_signum, _frame) -> None:
        _sync_child_size(child)

    previous_winch = signal.getsignal(signal.SIGWINCH)
    signal.signal(signal.SIGWINCH, _handle_resize)

    try:
        time.sleep(max(args.startup_delay, 0))
        _sync_child_size(child)
        child.sendline(f"/plan {args.prompt}")
        child.interact()
    finally:
        signal.signal(signal.SIGWINCH, previous_winch)
        child.close()

    if child.exitstatus is not None:
        return child.exitstatus
    if child.signalstatus is not None:
        return 128 + child.signalstatus
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
