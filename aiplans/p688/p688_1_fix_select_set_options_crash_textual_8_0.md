---
Task: t688_1_fix_select_set_options_crash_textual_8_0.md
Parent Task: aitasks/t688_board_pick_crash_and_starter_tmux_conf_in_setup.md
Sibling Tasks: aitasks/t688/t688_2_surface_textual_upgrade_in_setup.md, aitasks/t688/t688_3_starter_tmux_conf_in_setup.md
Archived Sibling Plans: aiplans/archived/p688/p688_*_*.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 10:10
---

# Plan — t688_1: Fix `AgentCommandScreen` Select crash on Textual 8.0

## Context

`ait board` press-`p` crashes the TUI on macOS where the venv holds Textual 8.0.0. The crash path is `_populate_tmux_tab → _update_window_options → win_select.set_options(options)` at `agent_command_screen.py:402`, which on Textual 8.0 raises `NoMatches: No nodes match 'SelectOverlay'` because the just-mounted `Select` widget has not yet mounted its internal `SelectOverlay` child.

The bug is consistently reproducible only when at least one tmux session is live (which is virtually always the case when running `ait board` inside tmux via `ait ide`). Outside tmux the bug still triggers at the parallel call site `_show_new_session_input → set_options([])` at line 422, but that path is wrapped in `try/except Exception: pass` (lines 417/427) and silently leaves the tab partially broken — no visible crash, just a non-functional tmux tab.

The Textual 8.1.x release fixed the internal timing dependency, which is why Linux users on the user's other machine (Textual 8.1.1) do not see the crash.

## Approach

Defer both initial-mount calls into the next refresh cycle via `self.call_after_refresh(...)`. By the next tick, `Select` has finished mounting `SelectOverlay`, so `set_options(...)` succeeds on Textual 8.0 AND 8.1.x. The deferral applies only to the initial-mount call sites in `_populate_tmux_tab`; the event-driven callers in `on_session_changed` (lines 474, 478) remain direct because they execute well after mount completes.

`call_after_refresh` is the established in-tree idiom for deferring widget mutations until after mount — used in `aitask_board.py:3497, 3534, 3541, 3561, 3956, 4391`.

## Critical Files

- `.aitask-scripts/lib/agent_command_screen.py` — modify lines 380–385 inside `_populate_tmux_tab`.

## Implementation Steps

### Step 1 — Replace direct calls with deferred calls

In `_populate_tmux_tab`, change the existing block:

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
# If a session is pre-selected, populate windows.
# Defer set_options on the just-mounted Select until its internal
# SelectOverlay child has mounted — required for Textual 8.0,
# safe and idempotent on 8.1.x.
if initial_session != _NEW_SESSION_SENTINEL:
    self._selected_session = initial_session
    self.call_after_refresh(self._update_window_options, initial_session)
else:
    self.call_after_refresh(self._show_new_session_input)
```

### Step 2 — Audit only (no edits)

Confirm the two helper bodies (`_update_window_options`, `_show_new_session_input`) need no changes — their later (event-driven) callers at lines 474 and 478 already execute after mount, so direct invocation there is safe. The only timing-sensitive callers are the two initial-mount ones we just deferred.

Confirm consumers in `aitask_board.py`, `monitor_app.py`, `history_screen.py` push the screen via `app.push_screen(AgentCommandScreen(...), callback)` — no per-caller patches needed.

## Verification

1. **Headless reproducer on Textual 8.0** (the original crash path):

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

   Run from a directory where `tmux` is on PATH and at least one tmux session exists (so `_update_window_options` is the path taken). Expected: exit 0, no `NoMatches`.

2. **Regression check on Textual 8.1.x:** Same script using the existing `~/.aitask/venv/bin/python`. Expected: exit 0.

3. **Live UI smoke test:** Run `ait board` inside tmux, focus a Ready task, press `p` → `AgentCommandScreen` opens cleanly with the tmux tab populated. Repeat with `ait monitor` (Run-agent flow) and `ait codebrowser` (history Run-agent flow) — same expectation.

4. **Outside-tmux UX recovery (bonus):** Run `ait board` in a tmux-less environment (or with `tmux` in PATH but no sessions). Open `AgentCommandScreen` → tmux tab is shown but takes the `_show_new_session_input` branch. Pre-fix this branch silently broke; post-fix it should populate cleanly.

## Final Implementation Notes

- **Actual work done:** Refactored `_populate_tmux_tab` to pre-populate the window-select Select widget at construction time (options + value passed to `Select(...)`) instead of mounting an empty Select and then mutating it via `set_options(...)` and `value = ...`. Extracted the option/value computation into a new private helper `_compute_window_options(session)` that is shared between the initial-mount path and the event-driven `_update_window_options` path. Initial-mount calls now defer only `_on_window_changed` (visibility toggles) and `_show_new_session_input` (visibility toggles + already-empty set_options) via `self.call_after_refresh(...)`.

- **Deviations from plan:** The original plan proposed a minimal 2-line change — wrapping the existing `_update_window_options(initial_session)` and `_show_new_session_input()` calls in `self.call_after_refresh(...)`. Verification on Textual 8.1.1 (Linux user's venv) caught a second timing race not anticipated by the plan: even with `call_after_refresh` deferring `_update_window_options`, the inner `win_select.value = ...` triggered `Select._watch_value` which called `select_current.update(prompt)` → `query_one("#label", Static)` on `SelectCurrent`, raising `NoMatches` because `SelectCurrent`'s `#label` child had not yet been mounted. The full fix moves all initial-mount Select-state mutations into the constructor (where `_watch_value` does NOT fire — Textual reactive convention is that `__init__` sets via internal storage), eliminating the race entirely. Total diff grew from ~2 lines to ~30 lines, but stays within a single file.

- **Issues encountered:** The original plan's "minimal" fix was discovered to be incomplete during the verification step (running the headless reproducer on the user's existing Textual 8.1.1 venv). Caught before commit — corrected in-place.

- **Key decisions:**
  - Chose the pre-construct approach over alternatives (e.g., multiple-tick `call_later`, `await mount_complete`) because it is the existing pattern already used by the session select on the same screen (line 339: `Select(session_options, value=initial_session, ...)`) — consistent with surrounding code, no new idiom introduced.
  - Extracted `_compute_window_options` as a shared helper so the event-driven `_update_window_options` path (called from `on_session_changed` line 478) and the initial-mount path use identical priority logic for default-window selection.
  - Did NOT change line 422 (`set_options([])` inside `_show_new_session_input`) — that path is still wrapped in `try/except Exception: pass` and runs via `call_after_refresh` on initial mount, which is sufficient given `set_options([])` on an already-empty Select is a no-op.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:** None of the t688_2 / t688_3 changes interact with this file or the Textual widget mount lifecycle. This child is independent and complete — siblings can proceed without dependency.

## Step 9 (Post-Implementation) reference

After Step 8 (commit code + plan separately), run:

```bash
./.aitask-scripts/aitask_archive.sh 688_1
./ait git push
```
