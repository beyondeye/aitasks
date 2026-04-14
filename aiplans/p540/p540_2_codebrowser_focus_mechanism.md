---
Task: t540_2_codebrowser_focus_mechanism.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_6_*.md, aitasks/t540/t540_7_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_2: codebrowser focus mechanism

## Scope

Give `ait codebrowser` a first-class way to be told "open this file
at these lines", both via a cold CLI launch and via a hot tmux-env-var
handoff while it is already running. Mirrors minimonitor's "m"
shortcut pattern. Consumed by t540_5 (board → codebrowser action).

## Exploration results (from parent planning)

- **Pattern to mirror — minimonitor "m" handler:**
  `.aitask-scripts/monitor/minimonitor_app.py:510-549`
  (`action_switch_to_monitor`). Logic: set
  `tmux set-environment -t <session> <VAR> <value>`, then check
  `tmux list-windows` to decide between `select-window`
  (existing) and `new-window` (cold launch).

- **Pattern to mirror — monitor's consumer:**
  `.aitask-scripts/monitor/monitor_app.py:548-572`
  (`_consume_focus_request`). Reads the env var, processes once,
  unsets via `tmux set-environment -u`. Called from both
  `on_mount` (startup) and a `set_interval` poll.

- **Codebrowser entry point:**
  `.aitask-scripts/codebrowser/codebrowser_app.py` — currently
  runs `CodeBrowserApp().run()` without argparse. Need to add a
  real `main()` with `--focus PATH[:START[-END]]`.

- **Codebrowser shell wrapper:**
  `.aitask-scripts/aitask_codebrowser.sh` — at ~line 36 it
  spawns Python. Add `"$@"` pass-through if missing.

- **Existing codebrowser widgets to drive:**
  - `ProjectFileTree` (`file_tree.py`) — select a path.
  - `CodeViewer` (`code_viewer.py`) —
    `move_cursor()` (~line 358), `get_selected_range()`
    (~line 394), internal selection state. Lines are 1-indexed in
    the public API.

- **Shared launch lib:**
  `.aitask-scripts/lib/agent_launch_utils.py:162-279` —
  `launch_in_tmux()` and `maybe_spawn_minimonitor()`. Add
  `launch_or_focus_codebrowser(session, focus_value)` here so
  the board (t540_5) can call it.

## Design

- **Env var:** `AITASK_CODEBROWSER_FOCUS`.
- **Value format:** `PATH[:START[-END]]` — same as all t540
  file-ref strings.
- **Consumer wiring:** add `_consume_codebrowser_focus()` to
  `CodeBrowserApp`. Call from `on_mount` and from
  `set_interval(1.0, ...)` (match monitor's interval).
- **CLI:** `aitask_codebrowser.sh --focus ...` → argparse in
  `main()` → pre-populate `CodeBrowserApp` with a pending focus
  request that gets consumed on mount.
- **Launcher helper semantics:** set the env var FIRST (so both
  hot and cold paths find it), then decide window reuse vs
  creation. Cold launch also passes `--focus` on the command line
  for belt-and-braces.

## Implementation sequence

1. Add `main()` + argparse to `codebrowser_app.py`.
2. Implement `_consume_codebrowser_focus()` with the one-shot
   processing and unset.
3. Hook into `on_mount` and `set_interval`.
4. Plumb `"$@"` in `aitask_codebrowser.sh` if needed.
5. Add `launch_or_focus_codebrowser()` in
   `lib/agent_launch_utils.py`.
6. Manual smoke test (see Verification).

## Verification

- **Cold CLI:** `./ait codebrowser --focus
  .aitask-scripts/aitask_create.sh:100-150` — opens with the
  file and range pre-selected.
- **Hot env-var:** while codebrowser is running, run
  `tmux set-environment -t <session> AITASK_CODEBROWSER_FOCUS
  tests/test_terminal_compat.sh:10-20` from another shell — the
  running codebrowser jumps to the range within one poll
  interval.
- **Window reuse via helper:** import
  `agent_launch_utils` in a Python shell and call
  `launch_or_focus_codebrowser(session, "aiplans/p540_*.md:1-10")`
  — existing codebrowser window comes foreground and lands on
  the range.
- **No regression:** `./ait codebrowser` without args still
  launches the plain TUI.

## Post-implementation

Archival via `./.aitask-scripts/aitask_archive.sh 540_2`.
