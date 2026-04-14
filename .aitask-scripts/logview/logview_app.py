#!/usr/bin/env python3
"""Agent log viewer — renders plain text and ANSI escape sequences.

Reads agent log files produced by agentcrew runners (both headless
Popen redirects and interactive tmux pipe-pane mirrors). Renders ANSI
escape sequences via rich's Text.from_ansi so colored TUI output is
readable. Falls back to a one-shot rich.Console print when Textual is
not installed.
"""

from __future__ import annotations

import argparse
import os
import threading
import time
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import Footer, Header, Input, RichLog, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    App = object  # type: ignore[assignment,misc]

from rich.console import Console
from rich.text import Text


class LogViewApp(App):  # type: ignore[misc]
    TITLE = "Log Viewer"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("r", "toggle_raw", "Raw"),
        Binding("g", "scroll_top", "Top"),
        Binding("G", "scroll_bottom", "Bottom"),
        Binding("slash", "search", "Search"),
        Binding("n", "search_next", "Next"),
        Binding("escape", "cancel_search", "", show=False),
    ] if TEXTUAL_AVAILABLE else []

    CSS = """
    #header-info { background: $boost; padding: 0 1; height: 1; }
    #search-box { display: none; height: 1; }
    #search-box.visible { display: block; }
    RichLog { background: $background; }
    """

    def __init__(self, log_path: Path, tail: bool = True) -> None:
        super().__init__()
        self.log_path = log_path
        self.tail = tail
        self.paused = False
        self.raw_mode = False
        self._last_pos = 0
        self._stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self._search_term: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._header_text(), id="header-info")
        yield Input(placeholder="Search (Enter to confirm, Esc to cancel)", id="search-box")
        yield RichLog(highlight=False, markup=False, wrap=False, id="log")
        yield Footer()

    def _header_text(self) -> str:
        state = "paused" if self.paused else ("live" if self.tail else "static")
        mode = " [raw]" if self.raw_mode else ""
        return f"File: {self.log_path}  [size: {self._last_pos}]  [{state}]{mode}"

    def on_mount(self) -> None:
        if not self.log_path.exists():
            self.notify(f"Log file not found: {self.log_path}", severity="warning")
            return
        self._read_and_append()
        log = self.query_one("#log", RichLog)
        log.scroll_end(animate=False)
        if self.tail:
            self._poll_thread = threading.Thread(target=self._tail_loop, daemon=True)
            self._poll_thread.start()

    def _read_and_append(self) -> None:
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, "rb") as f:
                f.seek(self._last_pos)
                data = f.read()
                self._last_pos = f.tell()
        except OSError as exc:
            self.notify(f"Read error: {exc}", severity="error")
            return
        if not data:
            return
        decoded = data.decode("utf-8", errors="replace")
        text_obj = Text(decoded) if self.raw_mode else Text.from_ansi(decoded)
        log = self.query_one("#log", RichLog)
        log.write(text_obj)
        self.query_one("#header-info", Static).update(self._header_text())

    def _tail_loop(self) -> None:
        while not self._stop.is_set():
            time.sleep(0.2)
            if self.paused:
                continue
            try:
                size = os.stat(self.log_path).st_size
            except FileNotFoundError:
                continue
            if size < self._last_pos:
                self._last_pos = 0
                self.call_from_thread(self._reload_from_start)
            elif size > self._last_pos:
                self.call_from_thread(self._read_and_append)

    def _reload_from_start(self) -> None:
        self.query_one("#log", RichLog).clear()
        self._read_and_append()

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused
        self.query_one("#header-info", Static).update(self._header_text())

    def action_toggle_raw(self) -> None:
        self.raw_mode = not self.raw_mode
        self._last_pos = 0
        self.query_one("#log", RichLog).clear()
        self._read_and_append()

    def action_scroll_top(self) -> None:
        self.query_one("#log", RichLog).scroll_home()

    def action_scroll_bottom(self) -> None:
        self.query_one("#log", RichLog).scroll_end()

    def action_search(self) -> None:
        box = self.query_one("#search-box", Input)
        box.add_class("visible")
        box.focus()

    def action_cancel_search(self) -> None:
        box = self.query_one("#search-box", Input)
        box.remove_class("visible")
        box.value = ""
        self.query_one("#log", RichLog).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "search-box":
            return
        self._search_term = event.value
        event.input.remove_class("visible")
        self.query_one("#log", RichLog).focus()
        if self._search_term:
            self.action_search_next()

    def action_search_next(self) -> None:
        if not self._search_term:
            return
        log = self.query_one("#log", RichLog)
        lines = [str(ln) for ln in log.lines]
        start = min(log.scroll_offset.y + 1, max(len(lines) - 1, 0))
        for i in range(start, len(lines)):
            if self._search_term in lines[i]:
                log.scroll_to(y=i, animate=False)
                return
        for i in range(0, start):
            if self._search_term in lines[i]:
                log.scroll_to(y=i, animate=False)
                self.notify("Search wrapped to top")
                return
        self.notify(f"Not found: {self._search_term}", severity="warning")

    def on_unmount(self) -> None:
        self._stop.set()


def _fallback_render(path: Path) -> int:
    console = Console()
    if not path.exists():
        console.print(f"[red]Log file not found: {path}[/red]")
        return 1
    with open(path, "rb") as f:
        data = f.read()
    console.print(Text.from_ansi(data.decode("utf-8", errors="replace")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render agent log files with ANSI escape support.",
    )
    parser.add_argument("--path", type=Path, help="Direct path to a log file.")
    parser.add_argument("--crew", help="Crew id (resolved with --agent).")
    parser.add_argument("--agent", help="Agent name (resolved with --crew).")
    parser.add_argument(
        "--tail",
        action="store_true",
        default=True,
        help="Follow the file for new output (default).",
    )
    parser.add_argument("--no-tail", dest="tail", action="store_false")
    args = parser.parse_args()

    if args.path is None:
        if args.crew and args.agent:
            args.path = Path(f".aitask-crews/crew-{args.crew}/{args.agent}_log.txt")
        else:
            parser.error("either --path or both --crew and --agent are required")

    if not TEXTUAL_AVAILABLE:
        return _fallback_render(args.path)

    LogViewApp(args.path, tail=args.tail).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
