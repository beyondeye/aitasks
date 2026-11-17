"""A stand-in code agent for docs screenshots. Never a real agent.

The ``agents`` dataset (``sample_project.py``) installs this as
``<project>/.standin/bin/claude``, first on the pinned ``PATH`` of every pane
(``session.py``), so the framework's real launch paths (board pick,
``ait sitrep``, the shadow key) start this instead of a code agent.

It draws a fixed, invented transcript for the sample project, word-wrapped to
the pane's width and redrawn when the pane is resized, and the composer
Claude Code draws (measured in ``tests/lib/fake_composer_agent.py``: a
full-width ``─`` rule, ``❯`` + NBSP, another rule, a status row). There is no
clock and no random text, so a replay shows the same screen.

On start it appends one identity record to ``<project>/.standin/log``::

    <role>|<argv joined by spaces>|<$TMUX_PANE>|<pid>

which is how a caller proves that a pane runs the stand-in and not something
else that happened to be called ``claude``.

Self-contained on purpose: no import from ``tests/`` or from framework code.
"""
from __future__ import annotations

import os
import re
import select
import shutil
import signal
import sys
from pathlib import Path

NBSP = " "
VERSION = "2.1.322 (Claude Code)"
#: C-c (0x03) and C-d (0x04) end the stand-in.
EXIT_BYTES = frozenset(b"\x03\x04")
STANDIN_DIR = Path(__file__).resolve().parent

BOLD, DIM, RESET = "\x1b[1m", "\x1b[2m", "\x1b[0m"
GREEN, GREY, ORANGE = "\x1b[38;5;114m", "\x1b[38;5;244m", "\x1b[38;5;215m"

TITLES = {
    "14": "fix login redirect loop",
    "15": "cache product images",
    "12_1": "cart summary widget",
}

DOT = f"{GREEN}●{RESET}"
OUT = f"  {GREY}⎿{RESET}  "


def _pick(task: str) -> list[str]:
    title = TITLES.get(task, f"task {task}")
    if task == "14":
        return [
            f"{GREY}>{RESET} /aitask-pick 14",
            "",
            f"{DOT} Reading the task: t14 {title}.",
            "",
            f"{DOT} The loop comes from the session check in {BOLD}auth/middleware.py{RESET}: "
            "an expired session redirects to /login, and /login sends the user back "
            "because the stale cookie still parses.",
            "",
            f"{DOT} {BOLD}Update{RESET}(auth/middleware.py)",
            f"{OUT}Updated auth/middleware.py with 4 additions and 1 removal",
            "",
            f"{DOT} {BOLD}Bash{RESET}(pytest tests/auth -q)",
            f"{OUT}12 passed in 1.84s",
            "",
            f"{DOT} The stale cookie is now cleared before the redirect, and the auth "
            "tests pass. Shall I commit the fix?",
        ]
    return [
        f"{GREY}>{RESET} /aitask-pick {task}",
        "",
        f"{DOT} Reading the task: t{task} {title}.",
        "",
        f"{DOT} {BOLD}Read{RESET}(catalog/images.py)",
        f"{OUT}Read 214 lines",
        "",
        f"{DOT} Planning the change: keep resized product images in a disk cache keyed "
        "by size, so a page load stops resizing on every request.",
    ]


def _shadow(task: str) -> list[str]:
    title = TITLES.get(task, f"task {task}")
    return [
        f"{GREY}>{RESET} /aitask-shadow",
        "",
        f"{DOT} Following the agent on t{task} {title}.",
        "",
        f"{DOT} The fix clears the stale cookie before the redirect. One gap: logout "
        "does not clear it either, so the loop can come back after a sign-out. "
        "Worth a test.",
    ]


def _sitrep() -> list[str]:
    return [
        f"{GREY}>{RESET} /aitask-sitrep",
        "",
        f"{DOT} Sitrep for lumen: one follow-up from t11, one question about the "
        "image cache, and one watch on the checkout children.",
        "",
        f"{DOT} Nothing needs you right now. Ask me about any item, or press a key "
        "in the list below.",
    ]


def role_and_lines(argv: list[str]) -> tuple[str, list[str]]:
    """The role an argv asks for and the transcript it shows."""
    words = " ".join(argv[1:]).split()
    command = next((i for i, w in enumerate(words) if w.startswith("/aitask-")), None)
    if command is None:
        return "agent", [f"{DOT} Ready."]
    name, rest = words[command], words[command + 1:]
    if name == "/aitask-pick":
        task = rest[0] if rest else "?"
        return "pick", _pick(task)
    if name == "/aitask-shadow":
        # `/aitask-shadow <followed pane> [<task>]`: the pane id is never shown,
        # it changes from run to run.
        task = rest[1] if len(rest) > 1 else "14"
        return "shadow", _shadow(task)
    if name == "/aitask-sitrep":
        return "sitrep", _sitrep()
    return "agent", [f"{GREY}>{RESET} {name}", "", f"{DOT} Working on it."]


_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")


def visible_len(text: str) -> int:
    return len(_SGR_RE.sub("", text))


def wrap(line: str, width: int) -> list[str]:
    """``line`` word-wrapped to ``width`` visible cells, as an agent re-wraps
    its output when its pane is resized. Continuation rows keep the line's
    hanging indent (two spaces after a bullet, five after a ``⎿`` result)."""
    if width < 10 or visible_len(line) <= width:
        return [line]
    plain = _SGR_RE.sub("", line)
    if plain.lstrip().startswith("⎿"):
        indent = " " * (plain.index("⎿") + 3)
    elif plain.startswith("●"):
        indent = "  "
    else:
        indent = " " * (len(plain) - len(plain.lstrip(" ")))
    lead = len(line) - len(line.lstrip(" "))
    rows, current = [], " " * lead
    for word in line[lead:].split(" "):
        candidate = f"{current} {word}" if current.strip() else current + word
        if visible_len(candidate) <= width or not _SGR_RE.sub("", current).strip():
            current = candidate
        else:
            rows.append(current)
            current = indent + word
    rows.append(current)
    return rows


def frame(lines: list[str], width: int, height: int) -> str:
    rule = f"{GREY}{'─' * width}{RESET}"
    composer = [rule, f"❯{NBSP}", rule, f"  {DIM}? for shortcuts{RESET}"]
    room = max(0, height - len(composer) - 1)
    lines = [row for line in lines for row in wrap(line, width - 1)]
    body = lines[-room:] if room else []
    # Output sits right above the composer, as an agent's does: the empty
    # rows are at the top, so a preview of the pane's last rows shows text.
    body = [""] * (room - len(body)) + body
    return "\x1b[H\x1b[2J" + "\r\n".join(body + [""] + composer)


def log_identity(role: str, argv: list[str]) -> None:
    record = "|".join([role, " ".join(argv[1:]).replace("|", "/"),
                       os.environ.get("TMUX_PANE", ""), str(os.getpid())])
    with open(STANDIN_DIR / "log", "a", encoding="utf-8") as fh:
        fh.write(record + "\n")


def main(argv: list[str]) -> int:
    if "--version" in argv[1:] or "-v" in argv[1:]:
        print(VERSION)
        return 0
    role, lines = role_and_lines(argv)
    log_identity(role, argv)

    def draw(*_):
        size = shutil.get_terminal_size((100, 30))
        sys.stdout.write(frame(lines, size.columns, size.lines))
        sys.stdout.flush()

    signal.signal(signal.SIGWINCH, draw)
    draw()
    fd = sys.stdin.fileno() if sys.stdin and sys.stdin.isatty() else None
    old = None
    if fd is not None:
        import termios
        import tty
        old = termios.tcgetattr(fd)
        tty.setraw(fd)
    try:
        while True:
            if fd is None:
                signal.pause()
                continue
            ready, _, _ = select.select([fd], [], [], 3600)
            if not ready:
                continue
            data = os.read(fd, 1024)
            # Raw mode turns off the terminal's own SIGINT, so C-c arrives as
            # a byte: it ends the stand-in like C-d. An empty read is a closed
            # terminal.
            if not data or EXIT_BYTES.intersection(data):
                return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if old is not None:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
