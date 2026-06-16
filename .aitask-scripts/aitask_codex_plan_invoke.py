#!/usr/bin/env python3
"""Launch Codex CLI and enter plan mode with an aitask skill prompt."""

from __future__ import annotations

import argparse
import errno
import os
import re
import select
import shutil
import signal
import sys
import termios
import time
import tty


_ANSI_RE = re.compile(
    rb"\x1b\[[0-?]*[ -/]*[@-~]"
    rb"|\x1b\][^\a]*(?:\a|\x1b\\)"
    rb"|\x1b[()][A-Za-z0-9]"
)

_DEFAULT_READY_PATTERNS = (
    "Explain this codebase",
    "Summarize recent commits",
    "Implement {feature}",
    "Find and fix a bug in @filename",
    "Write tests for @filename",
    "Improve documentation in @filename",
    "Run /review on my current changes",
)

_KNOWN_BLOCKING_PATTERNS = (
    "Do you trust the contents of this directory?",
    "Press enter to continue",
    "Finish App Setup",
    "Open sign-in URL",
    "Select provider?",
)


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
        help=(
            "Minimum seconds to wait after spawning Codex before sending the "
            "prompt once the composer is ready. Defaults to 2; retained as a "
            "diagnostic throttle, not as readiness detection."
        ),
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=float(os.environ.get("AITASK_CODEX_PLAN_READY_TIMEOUT", "120")),
        help=(
            "Seconds to wait for a Codex composer-ready marker before giving "
            "up and leaving the interactive session untouched."
        ),
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


def _screen_text(screen_bytes: bytes) -> str:
    stripped = _ANSI_RE.sub(b"", screen_bytes)
    text = stripped.decode("utf-8", errors="ignore")
    return "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)


def _load_ready_pattern() -> re.Pattern[str] | None:
    pattern = os.environ.get("AITASK_CODEX_PLAN_READY_PATTERN", "").strip()
    if not pattern:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as exc:
        print(
            f"Warning: ignoring invalid AITASK_CODEX_PLAN_READY_PATTERN: {exc}",
            file=sys.stderr,
        )
        return None


def _composer_is_ready(screen: str, extra_pattern: re.Pattern[str] | None) -> bool:
    if extra_pattern is not None and extra_pattern.search(screen):
        return True
    return any(pattern in screen for pattern in _DEFAULT_READY_PATTERNS)


def _blocking_state(screen: str) -> str:
    for pattern in _KNOWN_BLOCKING_PATTERNS:
        if pattern in screen:
            return pattern
    return ""


def _safe_write(fd: int, data: bytes) -> bool:
    while data:
        try:
            written = os.write(fd, data)
        except OSError as exc:
            if exc.errno == errno.EINTR:
                continue
            return False
        if written <= 0:
            return False
        data = data[written:]
    return True


def _relay_until_exit(child, args: argparse.Namespace) -> None:
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    child_fd = child.child_fd
    prompt = f"/plan {args.prompt}\r".encode("utf-8")
    started_at = time.monotonic()
    min_send_at = started_at + max(args.startup_delay, 0)
    timeout_at = started_at + max(args.ready_timeout, 0)
    ready_seen = False
    prompt_sent = False
    timed_out = False
    screen_tail = b""
    extra_ready_pattern = _load_ready_pattern()
    previous_tty_attrs = termios.tcgetattr(stdin_fd)

    def maybe_send_prompt() -> None:
        nonlocal prompt_sent
        if prompt_sent or timed_out or not ready_seen:
            return
        if time.monotonic() < min_send_at:
            return
        _sync_child_size(child)
        _safe_write(child_fd, prompt)
        prompt_sent = True

    tty.setraw(stdin_fd)
    try:
        while True:
            maybe_send_prompt()
            now = time.monotonic()
            if (
                not ready_seen
                and not timed_out
                and args.ready_timeout > 0
                and now >= timeout_at
            ):
                screen = _screen_text(screen_tail)
                blocking = _blocking_state(screen)
                detail = f" Last visible blocking prompt: {blocking}" if blocking else ""
                _safe_write(
                    stdout_fd,
                    (
                        "\r\nError: timed out waiting for Codex composer readiness; "
                        "leaving this session interactive without injecting /plan."
                        f"{detail}\r\n"
                    ).encode("utf-8"),
                )
                timed_out = True

            try:
                readable, _, _ = select.select([child_fd, stdin_fd], [], [], 0.1)
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise

            if child_fd in readable:
                try:
                    data = os.read(child_fd, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not data:
                    break
                if not _safe_write(stdout_fd, data):
                    break
                if not ready_seen and not timed_out:
                    screen_tail = (screen_tail + data)[-65536:]
                    screen = _screen_text(screen_tail)
                    if _composer_is_ready(screen, extra_ready_pattern):
                        ready_seen = True
                        maybe_send_prompt()

            if stdin_fd in readable:
                try:
                    data = os.read(stdin_fd, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not data:
                    break
                if not _safe_write(child_fd, data):
                    break
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, previous_tty_attrs)


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
        encoding=None,
        timeout=None,
    )

    def _handle_resize(_signum, _frame) -> None:
        _sync_child_size(child)

    previous_winch = signal.getsignal(signal.SIGWINCH)
    signal.signal(signal.SIGWINCH, _handle_resize)

    try:
        _relay_until_exit(child, args)
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
