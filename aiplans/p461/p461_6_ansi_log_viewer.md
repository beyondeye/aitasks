---
Task: t461_6_ansi_log_viewer.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_1_*.md, aitasks/t461/t461_2_*.md, aitasks/t461/t461_3_*.md, aitasks/t461/t461_4_*.md, aitasks/t461/t461_5_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_6 — ANSI-aware agent log viewer

## Goal

Build a Textual log viewer that renders both plain-text headless logs
and ANSI-laden interactive logs (produced by `tmux pipe-pane -O` in
t461_1). Exposed as `ait logview <crew> <agent>` and reachable with
`L` keybindings from the brainstorm status tab and the monitor TUI.

## Files

### New

1. `.aitask-scripts/logview/logview_app.py` — Textual app (~200 LOC)
2. `.aitask-scripts/aitask_logview.sh` — dispatcher shell script

### Modified

3. `ait` — register `logview` subcommand (next to `monitor`,
   `brainstorm`)
4. `.aitask-scripts/brainstorm/brainstorm_app.py` — add `L` keybinding
   on `AgentStatusRow`
5. `.aitask-scripts/monitor/monitor_app.py` — add `L` keybinding on
   agent pane rows

## Implementation steps

### 1. `logview_app.py`

```python
#!/usr/bin/env python3
"""Agent log viewer — renders plain text and ANSI escape sequences."""

import argparse
import os
import threading
import time
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, RichLog, Static
    from textual.containers import Vertical
    from textual.binding import Binding
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from rich.text import Text
from rich.console import Console


class LogViewApp(App):
    TITLE = "Log Viewer"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_pause", "Pause tail"),
        Binding("r", "toggle_raw", "Raw"),
        Binding("g", "scroll_top", "Top"),
        Binding("G", "scroll_bottom", "Bottom"),
        Binding("slash", "search", "Search"),
    ]
    CSS = """
    #header-info { background: $boost; padding: 0 1; }
    RichLog { background: $background; }
    """

    def __init__(self, log_path: Path, tail: bool = True):
        super().__init__()
        self.log_path = log_path
        self.tail = tail
        self.paused = False
        self.raw_mode = False
        self._last_pos = 0
        self._poll_thread: threading.Thread | None = None
        self._stop = threading.Event()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"File: {self.log_path}  [size: 0]", id="header-info")
        yield RichLog(highlight=False, markup=False, wrap=False, id="log")
        yield Footer()

    def on_mount(self) -> None:
        self._read_and_append()
        if self.tail:
            self._poll_thread = threading.Thread(target=self._tail_loop, daemon=True)
            self._poll_thread.start()

    def _read_and_append(self) -> None:
        if not self.log_path.exists():
            return
        with open(self.log_path, "rb") as f:
            f.seek(self._last_pos)
            data = f.read()
            self._last_pos = f.tell()
        if not data:
            return
        log = self.query_one("#log", RichLog)
        text_obj = (
            Text(data.decode("utf-8", errors="replace"))
            if self.raw_mode
            else Text.from_ansi(data.decode("utf-8", errors="replace"))
        )
        log.write(text_obj)
        info = self.query_one("#header-info", Static)
        info.update(f"File: {self.log_path}  [size: {self._last_pos}]  [{'paused' if self.paused else 'live'}]")

    def _tail_loop(self) -> None:
        while not self._stop.is_set():
            time.sleep(0.2)
            if self.paused:
                continue
            try:
                size = os.stat(self.log_path).st_size
            except FileNotFoundError:
                continue
            if size > self._last_pos:
                self.call_from_thread(self._read_and_append)

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused

    def action_toggle_raw(self) -> None:
        self.raw_mode = not self.raw_mode
        self._last_pos = 0
        log = self.query_one("#log", RichLog)
        log.clear()
        self._read_and_append()

    def action_scroll_top(self) -> None:
        self.query_one("#log", RichLog).scroll_home()

    def action_scroll_bottom(self) -> None:
        self.query_one("#log", RichLog).scroll_end()

    def on_unmount(self) -> None:
        self._stop.set()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path)
    parser.add_argument("--crew")
    parser.add_argument("--agent")
    parser.add_argument("--tail", action="store_true", default=True)
    parser.add_argument("--no-tail", dest="tail", action="store_false")
    args = parser.parse_args()

    if args.path is None:
        if args.crew and args.agent:
            args.path = Path(f".aitask-crews/crew-{args.crew}/{args.agent}_log.txt")
        else:
            parser.error("either --path or --crew/--agent is required")

    if not TEXTUAL_AVAILABLE:
        # Fallback: one-shot print
        console = Console()
        if args.path.exists():
            with open(args.path, "rb") as f:
                data = f.read()
            console.print(Text.from_ansi(data.decode("utf-8", errors="replace")))
        else:
            console.print(f"[red]Log file not found: {args.path}[/red]")
        return 0

    LogViewApp(args.path, tail=args.tail).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 2. `aitask_logview.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
. "$SCRIPT_DIR/lib/terminal_compat.sh"

usage() {
    cat <<EOF
Usage:
  ait logview --path <file> [--no-tail]
  ait logview <crew_id> <agent_name> [--no-tail]
EOF
}

ARGS=()
if [[ $# -ge 2 && "$1" != --* ]]; then
    ARGS+=(--crew "$1" --agent "$2")
    shift 2
fi
ARGS+=("$@")

exec python3 "$SCRIPT_DIR/logview/logview_app.py" "${ARGS[@]}"
```

### 3. `ait` dispatcher

Add next to `monitor)`:
```bash
logview)
    exec "$SCRIPT_DIR/.aitask-scripts/aitask_logview.sh" "$@"
    ;;
```

### 4. Brainstorm integration

In `AgentStatusRow`:
```python
Binding("L", "open_log", "Open log"),
...
def action_open_log(self) -> None:
    log_path = self.app.session_dir / f"{self.agent_name}_log.txt"
    if not log_path.exists():
        self.app.notify("No log yet for this agent")
        return
    subprocess.Popen(["./ait", "logview", "--path", str(log_path)],
                     cwd=str(self.app.repo_root))
```

### 5. Monitor integration

Similar `L` keybinding on agent pane rows. Only enable for rows whose
window name matches `agent-*`. Derive agent name from window name and
resolve the log path via the crew directory.

### 6. Fallback

If `import textual` fails in `logview_app.py`, the script already falls
back to a one-shot rich.Console print (see main()). This keeps the
subcommand usable over SSH or in a dumb terminal.

## Verification

1. Generate a headless agent run; `./ait logview <crew> <agent>`;
   confirm plain text renders readably.
2. Generate an interactive agent run (requires t461_1). Open the
   viewer; confirm colored TUI output renders with colors (not as
   `\e[...` noise).
3. While an interactive agent is running, watch the viewer in tail
   mode; confirm new output streams in and the size indicator updates.
4. Press `p` to pause tail; confirm new bytes stop appearing. Press
   again to resume.
5. Press `r` to toggle raw mode; confirm escape sequences appear
   literally. Toggle back.
6. From `ait brainstorm`, focus an agent row, press `L`; confirm the
   viewer opens on the right log file.
7. From `ait monitor`, focus an `agent-*` pane, press `L`; same check.
8. Uninstall textual locally (`pip uninstall textual`) or rename the
   import path; run the dispatcher; confirm the rich.Console fallback
   renders the log.
9. `shellcheck .aitask-scripts/aitask_logview.sh` passes.

## Dependencies

- **No hard dependency** on t461_1-t461_5. Can be developed in parallel
  using any ANSI-laden input file (e.g., `htop > test_log.txt` or a
  recorded `asciinema` session decoded to raw text) for testing.

## Notes for sibling tasks

- Viewer is scroll-linear, not a terminal emulator. Redraws (e.g.,
  Claude Code's spinner) accumulate as successive lines rather than
  overwriting. This is acceptable for log review and keeps the
  implementation simple. If a future task wants full terminal
  emulation, look at `pyte` or `textual-terminal`.
