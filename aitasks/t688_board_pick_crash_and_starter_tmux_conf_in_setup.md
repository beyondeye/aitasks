---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [ui, macos]
children_to_implement: [t688_2, t688_3]
created_at: 2026-04-28 00:03
updated_at: 2026-04-28 10:26
boardidx: 10
boardcol: now
---

## Symptom

On macOS, pressing `p` (pick) on a task in `ait board` crashes the TUI. Reproducible from a clean Python repro inside the project root with the user's existing venv (Python 3.9.6 system, Textual 8.0.0). Linux users with Textual 8.1.1 do not see the crash, so it has gone unnoticed until now.

Stack trace from a headless reproducer that mounts `AgentCommandScreen`:

```
File "agent_command_screen.py", line 312, in on_mount
    self._populate_tmux_tab()
File "agent_command_screen.py", line 383, in _populate_tmux_tab
    self._update_window_options(initial_session)
File "agent_command_screen.py", line 402, in _update_window_options
    win_select.set_options(options)
File ".../textual/widgets/_select.py", line 546, in _setup_options_renderables
    option_list = self.query_one(SelectOverlay)
NoMatches: No nodes match 'SelectOverlay' on Select(id='tmux_window_select')
```

`_populate_tmux_tab()` mounts `Select([], allow_blank=True, id="tmux_window_select")` and then immediately calls `_update_window_options(initial_session)` → `set_options(options)`. With Textual 8.0 the `Select` widget has not yet mounted its internal `SelectOverlay` child, so the internal `query_one(SelectOverlay)` raises `NoMatches`. The same pre-mount `set_options([])` anti-pattern also exists at `agent_command_screen.py:422` inside `_show_new_session_input`.

Other consumers of `AgentCommandScreen` (monitor, codebrowser, brainstorm) hit the same path and likely crash too on Textual 8.0.

## Fixes (combined task)

### 1. Bug fix — defensive code

`.aitask-scripts/lib/agent_command_screen.py:402` and `:422`. Make the post-mount `set_options(...)` call robust to a not-yet-fully-mounted `Select`. Options to evaluate during planning (pick the minimal change that works on both Textual 8.0 and 8.1.x):

- **Pre-populate at construction.** Build the window-select options list before the `Select(...)` constructor and pass them in directly; eliminates the timing dependency for the initial population. Likely the smallest diff.
- **Defer via `call_after_refresh(...)`.** Keep the existing two-phase code but move the second phase into the next refresh cycle.
- **Await Select mount.** Heavier; only if the above don't work.

Audit the rest of the file (and other Textual code paths in the repo) for the same `mount(Select(...))` immediately followed by `set_options(...)` pattern.

### 2. Existing-venv migration — bump textual to ≥8.1.1

`.aitask-scripts/aitask_setup.sh:502` already pins `textual>=8.1.1,<9`, but venvs created before that pin landed still hold 8.0.0. Verify that re-running `ait setup` on a stale venv actually upgrades textual (it should — `pip install 'textual>=8.1.1,<9'` will pull 8.1.1+). If quiet mode hides the upgrade decision, surface it. Document re-running `ait setup` as the recovery step in the changelog / release notes.

### 3. Setup expansion — optional starter `~/.tmux.conf`

Today `ait setup` configures only `aitasks/metadata/project_config.yaml`'s `tmux:` block (`default_session`, `git_tui`) — see `setup_tmux_default_session()` at `.aitask-scripts/aitask_setup.sh:2886`. It never touches `~/.tmux.conf`. On a fresh macOS install with no tmux config the user gets:

- No mouse mode, no right-click menu
- Default bottom status bar (the user expects a top status bar with window names)

Extend the setup flow with a new optional step. Suggested wording:

> "No `~/.tmux.conf` detected. Install a starter aitasks-recommended config? It enables: mouse on, right-click menu, status bar at top with window names, sensible color defaults. [y/N]"

The starter file should be small, well-commented, and ship from `seed/tmux.conf` (new file). Skip if `~/.tmux.conf` already exists unless the user explicitly opts to overwrite.

Plan-time decisions:

- **Slot in the flow.** Likely near `setup_tmux_default_session` (call site at `.aitask-scripts/aitask_setup.sh:3040`), so it runs only when tmux config is being touched.
- **Platform gating.** Offer on all platforms — only when no existing `~/.tmux.conf` (or `~/.config/tmux/tmux.conf`) is present, so Linux users who already have a config aren't disturbed.
- **File location.** Detect and respect the user's chosen path: prefer `~/.config/tmux/tmux.conf` if `~/.config/tmux/` already exists, else `~/.tmux.conf`. Default to `~/.tmux.conf` for a fresh install.

## Acceptance criteria

- Pressing `p` on a focused task in `ait board` on macOS opens `AgentCommandScreen` without crashing. Verified on Textual 8.0.0 AND 8.1.1.
- `ait setup` on an existing venv created before the textual-8.1.1 pin upgrades the installed textual to ≥8.1.1.
- After running `ait setup` on a Mac with no `~/.tmux.conf`, the user is offered a starter config; if accepted, a fresh `tmux` session yields mouse mode, right-click menu, and the recommended status bar.
- Other consumers of `AgentCommandScreen` (monitor, codebrowser, brainstorm) verified not to crash on the same flow on Textual 8.0.

## Out of scope

- Reworking the existing `default_session` / `git_tui` flow (already works).
- Forcing overwrite of an existing user `~/.tmux.conf` (always opt-in).

## Notes / repro

- macOS env: Darwin 24.6, Python 3.9.6 (`/usr/bin/python3`), Textual 8.0.0 in `~/.aitask/venv/`. Linux env (user's other machine): Textual 8.1.1.
- Headless reproducer (one-shot, not committed):

```python
import sys; sys.path.insert(0, '.aitask-scripts/lib'); sys.path.insert(0, '.aitask-scripts/board')
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
        await pilot.pause()
asyncio.run(run())
```

Inside the `aitasks` repo with `~/.aitask/venv/bin/python`, this reproduces the `NoMatches` crash on Textual 8.0.
