---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [codebrowser, tui]
created_at: 2026-04-14 10:13
updated_at: 2026-04-14 10:13
---

t540_2: give `ait codebrowser` a first-class way to be told "open this
file at these lines", both from a cold CLI launch and from a hot handoff
while a codebrowser window is already running. Mirrors minimonitor's "m"
shortcut handoff pattern. Used by t540_5 (board → codebrowser jump
action) and usable by any future tool that wants to surface a file range
in the codebrowser.

## Context

`.aitask-scripts/codebrowser/codebrowser_app.py` is a Textual TUI that
currently has no argparse and no inbound focus-request channel. At the
same time, `.aitask-scripts/monitor/minimonitor_app.py:510-549` already
demonstrates a clean tmux-env-var handoff pattern that
`.aitask-scripts/monitor/monitor_app.py:548-572` consumes via
`_consume_focus_request()`. t540_2 ports that pattern to codebrowser.

## Design decisions (from parent plan)

- **Env var name:** `AITASK_CODEBROWSER_FOCUS`.
- **Value format:** the same `PATH[:START[-END]]` string the rest of
  t540 uses (so it round-trips without parsing rules).
- **Consume on startup AND periodic poll** — startup handles the
  cold-launch / new-window case, poll handles the hot-handoff case.
- **CLI flag mirror** — `--focus PATH[:START[-END]]` on the codebrowser
  app; plumbed through `aitask_codebrowser.sh`. Cold-launch callers can
  use the flag instead of (or in addition to) the env var.
- **Launch helper lives in lib** — new
  `launch_or_focus_codebrowser(session, focus_value)` in
  `.aitask-scripts/lib/agent_launch_utils.py`, alongside the existing
  `maybe_spawn_minimonitor` / `launch_in_tmux` helpers.

## Key files to modify

1. `.aitask-scripts/codebrowser/codebrowser_app.py`
   - Add a `main()` with argparse supporting `--focus`. Currently the
     module just runs `CodeBrowserApp().run()`.
   - Add `_consume_codebrowser_focus()` method on `CodeBrowserApp`,
     mirroring `monitor_app.py:548-572`. It reads
     `AITASK_CODEBROWSER_FOCUS` from the tmux session env (via
     `tmux show-environment -t <session> <var>` or the same helper
     monitor_app uses), processes it once, and calls
     `tmux set-environment -t <session> -u <var>` to unset.
   - Hook into `on_mount()` for startup, and wire a
     `set_interval(INTERVAL, self._consume_codebrowser_focus)` poll
     (use the same interval monitor_app uses, likely 1-2 seconds —
     read it from there rather than hardcoding).
   - When a focus value arrives, parse it into
     `(path, start, end)`, select the file in `ProjectFileTree`,
     load it into `CodeViewer`, move the cursor and establish a
     selection in the same way shift+up/down currently does
     (re-use `CodeViewer.move_cursor()` and the internal selection
     state the existing `get_selected_range()` reads from).

2. `.aitask-scripts/aitask_codebrowser.sh`
   - Pass through any CLI args to `codebrowser_app.py` (currently it
     hardcodes the invocation — add `"$@"` to the python exec line
     if not already present).

3. `.aitask-scripts/lib/agent_launch_utils.py`
   - New function `launch_or_focus_codebrowser(session, focus_value,
     window_name='codebrowser')`. Logic mirrors minimonitor's "m"
     handler at `minimonitor_app.py:510-549`:
     1. `tmux set-environment -t <session>
        AITASK_CODEBROWSER_FOCUS <focus_value>`.
     2. Check if a `codebrowser` window already exists in the
        session (`tmux list-windows -t <session>`).
     3. If yes → `tmux select-window -t <session>:codebrowser`.
     4. If no → `tmux new-window -t <session>:codebrowser -n
        codebrowser -- "./ait codebrowser --focus <focus_value>"`.
        The `--focus` flag primes the cold launch so the new
        process doesn't need to wait for its first poll.

## Reference files for patterns

- `.aitask-scripts/monitor/minimonitor_app.py` lines 101 (binding),
  510-549 (`action_switch_to_monitor`) — the exact handoff pattern
  to mirror.
- `.aitask-scripts/monitor/monitor_app.py` lines 548-572
  (`_consume_focus_request`) — the consumer-side pattern to port.
- `.aitask-scripts/lib/agent_launch_utils.py` lines 162-279 for the
  `launch_in_tmux` / `maybe_spawn_minimonitor` helpers whose
  signature and error handling `launch_or_focus_codebrowser` must
  match.

## Implementation plan

1. Add `main()` + argparse to `codebrowser_app.py` (gated on
   `__name__ == "__main__"`; preserve existing entry behavior when
   called without args).
2. Add `_consume_codebrowser_focus()` mirroring monitor_app's
   consumer.
3. Wire it into `on_mount()` and a `set_interval` poll.
4. Extend `aitask_codebrowser.sh` to forward `"$@"` to the python
   process.
5. Add `launch_or_focus_codebrowser()` to
   `lib/agent_launch_utils.py`.
6. Manual smoke test (see Verification).
7. Document the env var in the codebrowser module docstring.

## Verification

- Cold path: run `./ait codebrowser --focus
  ./.aitask-scripts/aitask_create.sh:100-150` — the codebrowser
  should open directly on that file with lines 100-150 selected.
- Hot path: open codebrowser in one tmux window; in another shell
  run `tmux set-environment -t <session>
  AITASK_CODEBROWSER_FOCUS tests/test_terminal_compat.sh:10-20`
  — the running codebrowser should jump to that range within one
  poll interval.
- Window-reuse path: from a third shell, import
  `agent_launch_utils` and call
  `launch_or_focus_codebrowser("<session>",
  "aiplans/p540_task_creation_from_codebrowser.md:1-10")` —
  the existing codebrowser window should come to foreground and
  land on that range.
- No regressions: the existing codebrowser TUI must still work
  when launched with no args (`./ait codebrowser`).

## Out of scope

- The actual "create task from selection" keybinding in codebrowser
  — t540_4 handles that.
- The board `FileReferencesField` widget that will call
  `launch_or_focus_codebrowser` — t540_5 handles that.
