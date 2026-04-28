---
priority: high
effort: low
depends: []
issue_type: bug
status: Done
labels: [ui, macos]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-28 09:59
updated_at: 2026-04-28 10:26
completed_at: 2026-04-28 10:26
---

## Context

Pressing `p` (pick) on a focused task in `ait board` crashes the TUI on macOS when running inside tmux (or with any tmux session live). Reproducible from a headless test that mounts `AgentCommandScreen`. Linux users with Textual 8.1.1 do not see the crash; macOS users on Python 3.9.6 with Textual 8.0.0 do.

Stack trace:

```
File "agent_command_screen.py", line 402, in _update_window_options
    win_select.set_options(options)
File ".../textual/widgets/_select.py", line 546, in _setup_options_renderables
    option_list = self.query_one(SelectOverlay)
NoMatches: No nodes match 'SelectOverlay' on Select(id='tmux_window_select')
```

`_populate_tmux_tab()` mounts an empty `Select(allow_blank=True, id="tmux_window_select")` and immediately calls `_update_window_options(initial_session)` → `set_options(options)`. With Textual 8.0 the `Select` widget has not yet mounted its internal `SelectOverlay` child, so the internal `query_one(SelectOverlay)` raises `NoMatches`.

The same anti-pattern exists at line 422 (`_show_new_session_input` → `set_options([])`), but a surrounding `try/except Exception: pass` silently swallows the failure outside tmux (no live sessions → that branch). Inside tmux there's always ≥1 live session so the crash path at line 402 is taken.

## Why split here

This is an independent, file-isolated bug fix — single file, ~2-line change, verifiable with the headless reproducer. It is the highest-priority piece of t688 (unblocks Mac users immediately) and can ship before the other two children.

## Key Files to Modify

- `.aitask-scripts/lib/agent_command_screen.py` — replace direct calls at lines 380–385 with `self.call_after_refresh(...)` wrappers.

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py:3497, 3534, 3541, 3561, 3956, 4391` — in-tree precedent for `self.call_after_refresh(<method>, <args>)` to defer post-mount widget mutations.
- Same file (`agent_command_screen.py`):
  - `_update_window_options` body (lines 387–415) — uses `set_options` and `query_one(...)` on the Select.
  - `_show_new_session_input` body (lines 417–427) — same pattern, currently swallowed by `try/except Exception: pass`.
  - Event-driven callers at lines 474 and 478 (`on_session_changed`) — these run AFTER mount completes; no change needed there.

## Implementation Plan

In `_populate_tmux_tab`, change lines 380–385 from:

```python
# If a session is pre-selected, populate windows
if initial_session != _NEW_SESSION_SENTINEL:
    self._selected_session = initial_session
    self._update_window_options(initial_session)
else:
    self._show_new_session_input()
```

to:

```python
# If a session is pre-selected, populate windows
# (Defer set_options on the just-mounted Select widget until its
# internal SelectOverlay child has mounted — required for Textual 8.0,
# safe and idempotent on 8.1.x.)
if initial_session != _NEW_SESSION_SENTINEL:
    self._selected_session = initial_session
    self.call_after_refresh(self._update_window_options, initial_session)
else:
    self.call_after_refresh(self._show_new_session_input)
```

No edits to `_update_window_options` or `_show_new_session_input` themselves — their later (event-driven) call sites already run after mount completes.

## Other consumers (audit only — no code changes expected)

- `.aitask-scripts/board/aitask_board.py` (lines 3904, 4005, 4046, 4200) — push the screen.
- `.aitask-scripts/codebrowser/history_screen.py` (line 390) — pushes the screen.
- `.aitask-scripts/monitor/monitor_app.py` (line 1561) — pushes the screen.
- `.aitask-scripts/brainstorm/` — `grep` shows no `AgentCommandScreen` usage; unaffected.

All callers use `app.push_screen(AgentCommandScreen(...), callback)`. Fixing the screen itself fixes every consumer.

## Verification Steps

1. **Headless reproducer on Textual 8.0** (the crash path):

   ```bash
   python3 -m venv /tmp/textual80
   /tmp/textual80/bin/pip install --quiet 'textual==8.0.0' pyyaml linkify-it-py tomli
   /tmp/textual80/bin/python - <<'PY'
   import sys
   sys.path.insert(0, '.aitask-scripts/lib')
   sys.path.insert(0, '.aitask-scripts/board')
   from textual.app import App
   from agent_command_screen import AgentCommandScreen
   from pathlib import Path
   class Dummy(App):
       def on_mount(self):
           self.push_screen(
               AgentCommandScreen('Pick Task t42', 'echo hi', '/aitask-pick 42',
                   default_window_name='agent-pick-42', project_root=Path('.'),
                   operation='pick', operation_args=['42']),
               lambda r: self.exit())
   import asyncio
   async def run():
       async with Dummy().run_test(headless=True) as pilot:
           await pilot.pause(); await pilot.pause()
   asyncio.run(run())
   PY
   ```

   Should exit 0 — no `NoMatches` traceback. (Run from a directory where `tmux` is on PATH and at least one tmux session is live, to reproduce the crash path.)

2. **Regression check on Textual 8.1.1+:** Same script in the existing project venv (`~/.aitask/venv/bin/python`). Should also exit 0 — `call_after_refresh` is supported on both versions.

3. **Live UI smoke:** Run `ait board`, focus a Ready task, press `p` → `AgentCommandScreen` opens cleanly, tmux tab populates the window selector. Repeat in `ait monitor` (Run-agent flow) and `ait codebrowser` (history Run-agent flow) to confirm no per-consumer regression.

## Acceptance Criteria

- Pressing `p` on a focused task in `ait board` opens `AgentCommandScreen` without a `NoMatches` crash on Textual 8.0.0 AND 8.1.1.
- Headless reproducer exits 0 on both Textual versions.
- Other consumers (monitor, codebrowser) inherit the fix without per-caller changes.
