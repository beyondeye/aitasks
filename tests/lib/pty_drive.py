#!/usr/bin/env python3
"""Drive an interactive command under a real PTY, answering its prompts.

WHY THIS EXISTS
---------------
Every `ait setup` prompt is gated on ``[[ -t 0 ]]``. Pipe something into setup
and it takes the *non-interactive auto-accept* branch and never reads the
answer -- so a scripted stdin can exercise the ACCEPT path and nothing else.
The DECLINE path of every one of those prompts was therefore untestable, a gap
recorded verbatim in tests/test_agent_instructions.sh:

    "The legacy-mode DECLINE branch cannot be driven at all: it needs
     [[ -t 0 ]] true and tests/ has no pty harness."

t1705_3 added a consent prompt for the SessionStart hook, and a consent prompt
whose "no" branch no test can reach is consent in name only. This is that
harness. It is deliberately GENERAL -- nothing here knows about session hooks.

USAGE
-----
    python3 tests/lib/pty_drive.py --answers 'n,Y' -- ./ait setup

Answers are sent in order, one per prompt detected. A prompt is "the child is
waiting for input": the harness writes the next answer once the child's output
has been quiet for --settle seconds. That is more robust than matching prompt
text, which would couple every test to exact wording.

Prints the child's full transcript to stdout and exits with the child's status.
Requires only the standard library (the ``pty`` module ships on macOS and
Linux), so it adds no dependency and needs no ``expect``.
"""

from __future__ import annotations

import argparse
import errno
import os
import pty
import select
import signal
import sys
import time


def drive(
    argv: list[str],
    answers: list[str],
    settle: float = 0.4,
    timeout: float = 120.0,
    echo_answers: bool = True,
) -> tuple[int, str]:
    """Run ``argv`` under a PTY, feeding ``answers`` when it goes quiet.

    Returns ``(exit_status, transcript)``.
    """
    pid, fd = pty.fork()
    if pid == 0:  # child
        try:
            os.execvp(argv[0], argv)
        except Exception:  # noqa: BLE001 - child must never return
            os._exit(127)

    chunks: list[str] = []
    pending = list(answers)
    last_output = time.monotonic()
    started = time.monotonic()
    status = 0

    try:
        while True:
            if time.monotonic() - started > timeout:
                os.kill(pid, signal.SIGKILL)
                chunks.append(f"\n[pty_drive] TIMEOUT after {timeout}s\n")
                break
            try:
                ready, _, _ = select.select([fd], [], [], 0.1)
            except (OSError, ValueError):
                break
            if ready:
                try:
                    data = os.read(fd, 4096)
                except OSError as exc:
                    # EIO is the normal end-of-stream on a PTY master.
                    if exc.errno in (errno.EIO, errno.EBADF):
                        break
                    raise
                if not data:
                    break
                chunks.append(data.decode("utf-8", errors="replace"))
                last_output = time.monotonic()
                continue

            # No output. If the child is still alive and has been quiet long
            # enough, treat it as waiting at a prompt.
            done_pid, done_status = os.waitpid(pid, os.WNOHANG)
            if done_pid == pid:
                status = done_status
                # Drain whatever is left.
                while True:
                    try:
                        data = os.read(fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    chunks.append(data.decode("utf-8", errors="replace"))
                break

            if pending and (time.monotonic() - last_output) >= settle:
                answer = pending.pop(0)
                if echo_answers:
                    chunks.append(f"[pty_drive] -> {answer!r}\n")
                try:
                    os.write(fd, (answer + "\n").encode())
                except OSError:
                    break
                last_output = time.monotonic()
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            done_pid, done_status = os.waitpid(pid, 0)
            if done_pid == pid:
                status = done_status
        except (ChildProcessError, OSError):
            pass

    if os.WIFEXITED(status):
        code = os.WEXITSTATUS(status)
    elif os.WIFSIGNALED(status):
        code = 128 + os.WTERMSIG(status)
    else:
        code = 1
    return code, "".join(chunks)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--answers",
        default=None,
        help="Comma-separated answers, sent in order as the child goes quiet. "
        "Use an empty element for a bare Enter (e.g. 'n,,Y'). NOTE: --answers '' "
        "means NO answers, not one bare Enter -- use --answer '' for that.",
    )
    ap.add_argument(
        "--answer",
        action="append",
        default=[],
        dest="answer_list",
        help="A single answer, repeatable, sent in order. Unlike --answers this "
        "is unambiguous for an empty answer: --answer '' sends one bare Enter, "
        "which is how a default-accepting prompt is tested.",
    )
    ap.add_argument("--settle", type=float, default=0.4,
                    help="Seconds of child silence that count as 'at a prompt'.")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--no-echo-answers", action="store_true",
                    help="Do not annotate the transcript with the answers sent.")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- followed by the command to run")
    args = ap.parse_args()

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        ap.error("no command given (use: --answers 'n,Y' -- ./ait setup)")

    answers = list(args.answer_list)
    if args.answers is not None:
        answers += args.answers.split(",") if args.answers else []
    code, transcript = drive(
        cmd, answers,
        settle=args.settle,
        timeout=args.timeout,
        echo_answers=not args.no_echo_answers,
    )
    sys.stdout.write(transcript)
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
