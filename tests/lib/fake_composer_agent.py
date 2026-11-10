#!/usr/bin/env python3
"""A scripted, Claude-shaped agent pane for the sitrep request-delivery live test.

Renders the composer grammar measured from claude 2.1.322 (t2211_4 spike):
a full-width ``─`` rule, ``❯`` + NBSP + the composer text (the dim placeholder
hint when empty), continuation rows indented two spaces, content width =
pane width - 4 (a word wraps iff row + 1 + word > content; a word wider than
the row is broken in place), another rule, then status rows. History echoes
use ``❯`` + a plain space, as Claude's do.

Every byte received is appended to ``--log`` (binary, flushed per read), so
the test can assert exactly what reached the "agent".

Modes:
  ready           empty composer; typed bytes fill it; Enter submits (the
                  text moves to history, the composer empties).
  dialog          shows a Claude permission dialog; input is only logged.
  draft           the composer starts with an unsent user draft; typed bytes
                  append to it; Enter submits it.
  stuck           like ready, but Enter never submits (the composer keeps
                  its text) -- an Enter that was swallowed.
  resubmit_draft  like ready for the first Enter, after which the composer
                  holds an unrelated user draft and further Enters are only
                  logged (the user typing right after the submit).

Usage: fake_composer_agent.py --mode <mode> --log <file>
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import termios
import tty
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import review_loop_fixtures as rlf  # noqa: E402

NBSP = " "
HINT = '\x1b[2mTry "fix lint errors"\x1b[0m'
DRAFT = "half-typed user draft"
FOREIGN = "an unrelated draft the user is typing"


def wrap(text: str, content: int) -> list:
    """Claude's measured composer wrap (see the module docstring)."""
    rows, row = [], ""
    for word in text.split(" "):
        cand = f"{row} {word}" if row else word
        if len(cand) <= content:
            row = cand
        elif len(word) > content:          # wider than a row: broken in place
            row = cand
            while len(row) > content:
                rows.append(row[:content])
                row = row[content:]
        else:
            rows.append(row)
            row = word
    rows.append(row)
    return rows


class Agent:
    def __init__(self, mode: str, log: str) -> None:
        self.mode = mode
        self.log = open(log, "ab", buffering=0)
        self.composer = DRAFT if mode == "draft" else ""
        self.history: list = []
        self.submits = 0

    def frame(self) -> str:
        width = shutil.get_terminal_size((120, 30)).columns
        if self.mode == "dialog":
            return rlf.CLAUDE_DIALOG_RAW
        rule = "\x1b[38;5;244m" + "─" * width + "\x1b[39m"
        rows = [*self.history[-6:], "", rule]
        if self.composer:
            text_rows = wrap(self.composer, width - 4)
            rows.append(f"❯{NBSP}{text_rows[0]}")
            rows += [f"  {r}" for r in text_rows[1:]]
        else:
            rows.append(f"❯{NBSP}{HINT}")
        rows += [rule, "  [Fake | Claude-shaped]", "  proj"]
        return "\n".join(rows)

    def draw(self) -> None:
        sys.stdout.write("\x1b[H\x1b[2J\x1b[3J" + self.frame().replace("\n", "\r\n"))
        sys.stdout.flush()

    def enter(self) -> None:
        if self.mode in ("dialog", "stuck"):
            return
        if self.mode == "resubmit_draft" and self.submits:
            return
        if self.composer:
            self.history += [f"❯ {self.composer}", "", "● OK", ""]
            self.submits += 1
            self.composer = FOREIGN if self.mode == "resubmit_draft" else ""

    def feed(self, data: bytes) -> None:
        self.log.write(data)
        for ch in data.decode("utf-8", "replace"):
            if ch == "\r":
                self.enter()
            elif ch.isprintable() and self.mode != "dialog":
                if self.mode == "resubmit_draft" and self.submits:
                    continue
                self.composer += ch

    def run(self) -> None:
        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        tty.setraw(fd)
        try:
            self.draw()
            while True:
                data = os.read(fd, 4096)
                if not data:
                    return
                self.feed(data)
                self.draw()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True,
                    choices=("ready", "dialog", "draft", "stuck", "resubmit_draft"))
    ap.add_argument("--log", required=True)
    args = ap.parse_args()
    Agent(args.mode, args.log).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
