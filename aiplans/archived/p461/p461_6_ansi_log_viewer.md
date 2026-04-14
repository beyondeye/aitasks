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
t461_1). Exposed as **`ait crew logview <crew> <agent>`** (a
sub-subcommand under `ait crew`, next to `status`, `runner`, etc.) and
reachable with `L` keybindings from the brainstorm status tab and the
monitor TUI.

## Files

### New

1. `.aitask-scripts/logview/logview_app.py` — Textual app (~200 LOC)
2. `.aitask-scripts/aitask_crew_logview.sh` — dispatcher shell script

### Modified

3. `ait` — register `logview` as a sub-subcommand under `crew` (next to
   `status`, `runner`, `report`, etc.)
4. `.aitask-scripts/brainstorm/brainstorm_app.py` — add `L` keybinding
   on `AgentStatusRow` (dispatched via `BrainstormApp.on_key()`)
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

### 2. `aitask_crew_logview.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
. "$SCRIPT_DIR/lib/terminal_compat.sh"

usage() {
    cat <<EOF
Usage:
  ait crew logview --path <file> [--no-tail]
  ait crew logview <crew_id> <agent_name> [--no-tail]
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

Add `logview` as a new sub-subcommand under `crew)` (ait lines 180-213).
Add the case entry next to `dashboard)`:
```bash
logview)   exec "$SCRIPTS_DIR/aitask_crew_logview.sh" "$@" ;;
```
Also:
- Add `logview` to the help text list printed when
  `ait crew --help` is invoked (next to `dashboard`).
- Update the trailing error message "Available: init, addwork, ..." to
  include `logview`.
- NO entry in `show_usage` TUI/Tools sections (it stays under `crew`).
- NO change to the top-level `case` whitelist on line 151 (unrelated
  command).

### 4. Brainstorm integration

`brainstorm_app.py` does not use row-level `BINDINGS`. It dispatches keys
via the main `BrainstormApp.on_key()` method (lines 1257-1286) using
`isinstance(self.focused, AgentStatusRow)` — see the `w` (reset) and `e`
(edit mode) handlers as canonical patterns.

Add an `L` handler block immediately after the `e` block in `on_key`:

```python
# L: open log viewer for focused agent row
if event.key == "L":
    focused = self.focused
    if isinstance(focused, AgentStatusRow):
        crew_dir = crew_worktree(focused.crew_id)
        log_path = Path(crew_dir) / f"{focused.agent_name}_log.txt"
        if not log_path.exists():
            self.notify(
                f"No log yet for {focused.agent_name}",
                severity="warning",
            )
        else:
            subprocess.Popen(
                ["./ait", "crew", "logview", "--path", str(log_path)],
                cwd=str(Path.cwd()),
            )
        event.prevent_default()
        event.stop()
        return
```

Also extend the focus-hint in `AgentStatusRow.render()` (line 600-607) so
the `(L: open log)` hint appears alongside the existing reset/edit hints
when a log file is present.

### 5. Monitor integration

`monitor_app.py` keys are dispatched via the class-level `BINDINGS` list
(lines 329-344) and corresponding `action_*` methods — add
`Binding("L", "open_log", "Open log")` to the list and implement
`action_open_log(self)` next to `action_show_task_info` (line 1042):

```python
def action_open_log(self) -> None:
    pane_id = self._focused_pane_id
    if pane_id is None:
        return
    snap = self._snapshots.get(pane_id)
    if not snap:
        return
    window_name = snap.pane.window_name
    # Agent windows are named "agent-<name>" (see agentcrew_runner
    # interactive branch) or "agent-pick-<taskid>" (pick launcher).
    if not window_name.startswith("agent-"):
        self.notify("Not an agent pane", severity="warning")
        return
    agent_name = window_name.removeprefix("agent-")
    # Window name doesn't encode the crew. Scan .aitask-crews/crew-*/
    # for a matching <agent>_log.txt — first hit wins. For the pick
    # launcher window (agent-pick-<taskid>) no log exists; skip.
    if agent_name.startswith("pick-"):
        self.notify("Pick launcher panes have no agent log")
        return
    log_path = None
    for crew_dir in Path(".aitask-crews").glob("crew-*"):
        candidate = crew_dir / f"{agent_name}_log.txt"
        if candidate.exists():
            log_path = candidate
            break
    if log_path is None:
        self.notify(f"No log file found for {agent_name}", severity="warning")
        return
    subprocess.Popen(
        ["./ait", "crew", "logview", "--path", str(log_path)],
        cwd=str(self._project_root),
    )
```

### 6. Fallback

If `import textual` fails in `logview_app.py`, the script already falls
back to a one-shot rich.Console print (see main()). This keeps the
subcommand usable over SSH or in a dumb terminal.

## Verification

1. Generate a headless agent run; `./ait crew logview <crew> <agent>`;
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
9. `shellcheck .aitask-scripts/aitask_crew_logview.sh` passes.
10. `./ait crew --help` includes `logview` in the listed subcommands.

## Dependencies

- **No hard dependency** on t461_1-t461_5. Can be developed in parallel
  using any ANSI-laden input file (e.g., `htop > test_log.txt` or a
  recorded `asciinema` session decoded to raw text) for testing.

## Plan verification (2026-04-14)

Verified against current code before implementation:
- t461_1 is merged — `.aitask-scripts/agentcrew/agentcrew_runner.py` has
  the interactive branch with `tmux pipe-pane -O` writing to
  `<worktree>/<name>_log.txt` (lines ~485-553). Worktree is the crew dir
  `.aitask-crews/crew-<id>/`.
- `.aitask-scripts/logview/` does not exist yet — new module.
- `ait` dispatcher pattern: add `logview` to the TUI section of
  `show_usage` (line 28 area), to the whitelist on line 151, and a
  `logview) shift; exec "$SCRIPTS_DIR/aitask_logview.sh" "$@" ;;` case
  near the existing `monitor)` line (166).
- `brainstorm_app.py` `on_key` pattern was updated above — the original
  plan's row-level Binding approach does not fit this codebase.
- `monitor_app.py` uses class-level BINDINGS; the `L` key is free
  alongside existing `q/s/i/r/z/b/t/k/n/a/enter`.
- No `l` or `L` collisions in either app.

## Notes for sibling tasks

- Viewer is scroll-linear, not a terminal emulator. Redraws (e.g.,
  Claude Code's spinner) accumulate as successive lines rather than
  overwriting. This is acceptable for log review and keeps the
  implementation simple. If a future task wants full terminal
  emulation, look at `pyte` or `textual-terminal`.

## Final Implementation Notes

- **Actual work done:**
  - **New module** `.aitask-scripts/logview/` with `__init__.py` (empty)
    and `logview_app.py`. The app uses Textual's `RichLog` +
    `rich.text.Text.from_ansi()` for rendering. Tail loop polls
    `os.stat` at 200ms, handles file truncation (if size decreases,
    reset `_last_pos = 0` and reload from start).
  - **Search** is implemented via a hidden `Input` widget toggled by
    `/`. On submit, it scans `log.lines` for the substring starting at
    the current scroll row and wraps around. `n` repeats the last
    search. This is simple sub-string search — adequate for log
    review, no regex.
  - **Header bar** displays path, byte count, live/paused/static state,
    and `[raw]` tag when raw mode is active.
  - **Fallback path** (`_fallback_render`) is reached when
    `import textual` fails — prints the decoded ANSI via
    `rich.Console().print(Text.from_ansi(...))` and returns `0`
    (or `1` if the file is missing).
  - **Dispatcher** `.aitask-scripts/aitask_crew_logview.sh` follows the
    exact pattern of `aitask_crew_status.sh` — sources
    `lib/terminal_compat.sh`, prefers `$HOME/.aitask/venv/bin/python`
    over system python, handles `--help`, and rewrites positional
    `<crew> <agent>` to `--crew / --agent` flags before exec'ing the
    Python app.
  - **`ait` dispatcher** gained one case line
    (`logview) exec "$SCRIPTS_DIR/aitask_crew_logview.sh" "$@" ;;`) in
    the `crew)` block plus matching entries in the help text and the
    "unknown subcommand" error message.
  - **Brainstorm integration** — `L` handler added in
    `BrainstormApp.on_key()` immediately after the `e` block, using
    `isinstance(self.focused, AgentStatusRow)`. Resolves the log path
    via `crew_worktree(focused.crew_id) / f"{focused.agent_name}_log.txt"`
    and launches the viewer via `subprocess.Popen(["./ait", "crew",
    "logview", "--path", ...])`. `AgentStatusRow.render()` was
    extended to show a combined focus hint (`w: reset | L: log`,
    `e: edit mode | L: log`, or `L: log` alone) only when the log
    file exists.
  - **Monitor integration** — `Binding("L", "open_log", "Log")` added
    to the class-level `BINDINGS`. `action_open_log()` lives next to
    `action_show_task_info()`. Window-name resolution: strip the
    `agent-` prefix, reject `pick-*` (pick-launcher panes have no
    log), then iterate `.aitask-crews/crew-*/` under `_project_root`
    looking for a matching `<agent>_log.txt`. First hit wins.

- **Deviations from plan:**
  - The plan's draft for brainstorm integration used a row-level
    `Binding` on `AgentStatusRow`. That is not how `brainstorm_app.py`
    dispatches keys — it uses a central `on_key()` with
    `isinstance(self.focused, ...)` checks. Updated the plan during
    verification and implemented against the correct pattern. Same
    applies to `monitor_app.py` which uses class-level `BINDINGS` +
    `action_*` methods; that one matched the original plan fairly
    closely.
  - The plan sketched the monitor integration with
    "derive agent name from window name and resolve via the crew
    directory" without specifying how. Since window names are
    `agent-<name>` (from `agentcrew_runner.py` interactive branch) and
    don't encode the crew id, the implementation scans
    `.aitask-crews/crew-*/` for any matching `<name>_log.txt` — first
    hit wins. This is O(crews) per press, which is fine for the
    typical 1-3 crew directories seen in practice.
  - Search feature was included in this first pass even though the
    plan listed `/` as "prompt for text, highlight next match". The
    implementation scrolls to the next matching line rather than
    highlighting — simpler and sufficient for log review. Extending
    to highlighting would require writing a custom RichLog subclass
    that re-renders matched tokens.

- **Issues encountered:** None. `python3 -m py_compile` succeeded on
  all three modules on the first pass. The Textual app launched
  correctly in a throwaway `timeout 2 ...` test against a nonexistent
  path and showed the expected "Log file not found" notification.

- **Key decisions:**
  - Log file resolution in brainstorm uses the already-imported
    `crew_worktree(crew_id)` — no need to invent a new helper. This
    means the brainstorm viewer launch is self-contained (no scan
    required) because the row already knows its `crew_id`.
  - The monitor integration deliberately surfaces a warning when no
    matching log file is found rather than silently failing — helps
    users understand that the window is an agent pane but pre-dates
    the interactive-launch pipe-pane feature (or the agent is still
    Waiting).
  - Tail loop polling interval is 200ms, matching the plan. No
    `watchdog` dependency — the import footprint stays small.
  - Search is line-level substring (not regex, not tokenized). A
    future task could swap in `re` search if needed.

- **Verification results:**
  - `python3 -m py_compile .aitask-scripts/logview/logview_app.py`
    → OK
  - `python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py`
    → OK
  - `python3 -m py_compile .aitask-scripts/monitor/monitor_app.py`
    → OK
  - `./ait crew --help` → includes `logview` line
  - `./ait crew logview --help` → prints usage text
  - `./ait crew logview --path /nonexistent/log.txt --no-tail`
    (killed by timeout 2s) → TUI starts, notification shown
  - Python fallback path test (force `TEXTUAL_AVAILABLE = False`) on
    a synthetic `\e[31mred\e[0m` file → colored output via
    `rich.Console`, exit 0
  - `shellcheck .aitask-scripts/aitask_crew_logview.sh` → only the
    pre-existing `SC1091` info (sibling scripts share this)
  - **Not verified in this session** (require a live tmux session and
    a running interactive agent): plan steps 2-3 (ANSI-laden tail),
    6 (brainstorm L keypress), 7 (monitor L keypress). Documented
    here for the human reviewer.

- **Notes for sibling tasks:**
  - The dispatcher lives under `ait crew logview`, not `ait logview`.
    Any future sibling that wants to open the viewer programmatically
    should use `["./ait", "crew", "logview", "--path", ...]`.
  - `AgentStatusRow.render()` now composes focus hints via a list
    rather than a fixed if/elif. If `t461_7` or later siblings add
    another key (e.g., `d` for dashboard drill-down), append to the
    same `hints` list — don't fall back to a chain of `if/else`.
  - `crew_worktree(crew_id)` is the canonical way to resolve a crew
    directory from a brainstorm session — reuse it rather than
    building paths manually.
  - Search is intentionally line-level substring. A future task could
    extend to regex with minimal changes (swap `self._search_term in`
    for `re.search(self._search_term, ...)`).
