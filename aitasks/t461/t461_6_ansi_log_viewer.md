---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [ui, agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-13 11:46
updated_at: 2026-04-14 11:11
---

## Context

Parent task t461 adds interactive launch mode for agentcrew code agents.
When an agent runs interactively inside a tmux window, its output is
mirrored to `<agent>_log.txt` via `tmux pipe-pane -O`. The captured
stream contains **ANSI escape codes** (cursor moves, colors, screen
redraws) because it's the raw output of a TUI application. A plain
`cat` or `less` of that file looks like noise.

This child task adds a dedicated **log viewer** that renders both plain
text logs (headless agents) and ANSI-laden logs (interactive agents) in
a readable form. It is a **sibling** to t461_1-t461_5 with no code
dependencies — it consumes log files those tasks produce but can be
developed in parallel.

## Key Files to Modify / Create

### New

- `.aitask-scripts/logview/logview_app.py` — Textual app, ~200 LOC.
  Mirrors the module layout of `.aitask-scripts/monitor/monitor_app.py`.
- `.aitask-scripts/aitask_logview.sh` — dispatcher script. Entry for
  `ait logview <crew> <agent>` OR `ait logview <path>`. Routes into the
  Python app.

### Modified

- `ait` — register the new `logview` subcommand next to `monitor`,
  `brainstorm`, etc. (around lines 180-220).
- `.aitask-scripts/brainstorm/brainstorm_app.py` — on a focused
  `AgentStatusRow`, bind `L` to open the log viewer for that agent.
  Launch via `subprocess.Popen` so the brainstorm TUI stays alive.
- `.aitask-scripts/monitor/monitor_app.py` — similar `L` keybinding on
  tmux monitor rows, so users can jump from a monitored window to its
  historical log file after the agent dies.

## Reference Files for Patterns

- `.aitask-scripts/monitor/monitor_app.py` — overall Textual app layout,
  key binding conventions, tmux interaction for live views.
- `.aitask-scripts/board/aitask_board.py` — CSS/layout patterns for
  Textual apps in this project (~2400 LOC, follow its conventions).
- `.aitask-scripts/lib/terminal_compat.sh` — error helpers (`die`,
  `warn`, `info`) for the dispatcher script.
- Python stdlib `rich.text.Text.from_ansi()` and Textual's `RichLog`
  widget — the renderer pieces.

## Implementation Plan

1. **Viewer app (`logview_app.py`)**:
   - `class LogViewApp(App)` extending Textual's App.
   - Accepts CLI args: `--path <file>`, `--crew <id> --agent <name>`
     (resolves to `.aitask-crews/crew-<id>/<name>_log.txt`), and
     optional `--tail` to stream updates live.
   - Main widget: `RichLog(highlight=False, markup=False, wrap=False)`.
   - Render: read the log in chunks; for each chunk, convert via
     `Text.from_ansi(chunk.decode("utf-8", errors="replace"))` and
     write to the RichLog.
   - Full terminal emulation (redraw-in-place) is **out of scope** —
     the viewer scrolls linearly, so redraws appear as successive
     states. This is acceptable for log review.
   - Tail mode: use a worker thread that `os.stat`s the file every
     200ms, reads any new bytes from the last read position, and
     writes them through `Text.from_ansi`. No external deps
     (`watchdog`) to keep the install footprint small.
   - Keybindings (match Textual conventions):
     - `q` quit
     - `/` search (prompt for text, highlight next match)
     - `g` top, `G` bottom
     - `p` pause/resume tail
     - `r` toggle raw mode (show escape sequences literally for
       debugging)
   - Header bar shows: log file path, byte count, live/paused status,
     agent name if launched via `--crew --agent`.

2. **Dispatcher (`aitask_logview.sh`)**:
   - `#!/usr/bin/env bash`, `set -euo pipefail`, sources
     `terminal_compat.sh`.
   - Arg parsing: either `<crew> <agent>` positional OR `--path <file>`.
   - Resolves crew/agent to a log file path. `die` if file missing.
   - Execs the Python app: `exec python3
     .aitask-scripts/logview/logview_app.py --path "$log_path" [--tail]`.

3. **ait dispatcher integration**: add `logview)` case routing to
   `aitask_logview.sh`. Update help strings.

4. **Brainstorm integration**:
   - Add `Binding("L", "open_log", "Open log")` on `AgentStatusRow`.
   - `action_open_log()` launches
     `subprocess.Popen(["./ait", "logview", crew_id, agent_name])`
     detached, so the brainstorm TUI continues to run. If the log file
     does not yet exist (agent still Waiting), show a toast
     "No log yet for this agent".

5. **Monitor integration**:
   - Similar `L` binding on monitored pane rows. Resolve the agent
     name from the tmux window name (`agent-<name>` → `<name>`) and
     shell out the same way. For rows that don't map to an agent
     (TUI panes), disable the binding.

6. **Fallback for environments without Textual**: if `import textual`
   fails, fall back to printing via `rich.console.Console().print(
   Text.from_ansi(contents))`. This keeps the subcommand usable in
   headless CI / over SSH without TUI.

## Verification Steps

1. Generate a headless agent run (any existing crew). Run
   `./ait logview <crew> <agent>`; confirm the viewer opens and plain
   text is readable.
2. Generate an interactive agent run (requires t461_1 merged): use the
   brainstorm wizard or `ait crew addwork --launch-mode interactive`
   to start an agent, let it write some output, then open the viewer.
   Confirm Claude Code's colored prompt renders with colors (not as
   `\e[...` noise).
3. Run the viewer in `--tail` mode during a live interactive session;
   confirm new output appears as it streams (watch byte count tick up).
4. From brainstorm status tab, focus an agent row and press `L`.
   Confirm the viewer opens with the correct log file.
5. From the monitor TUI, focus an `agent-*` pane row and press `L`.
   Confirm the viewer opens with that agent's log file.
6. Uninstall / rename `textual` locally and re-run the dispatcher.
   Confirm the fallback rich.Console render still works.
7. `shellcheck .aitask-scripts/aitask_logview.sh` — must pass.

## Dependencies

- **No hard dependency** on the other t461 children. Log file formats
  (both plain and ANSI) can be produced by this task using any handy
  input, e.g. piping `vim` or `htop` output into a file for testing.
- The brainstorm/monitor integration steps DO require the agent rows
  to exist (they already do today), but do NOT require interactive
  launch to be merged.

## Out of scope

- Full terminal emulation (cursor-positioning redraws overwriting
  previous content). The linear scroll behavior is acceptable.
- Editing / deleting log files from within the viewer.
- Multi-pane log comparison.
