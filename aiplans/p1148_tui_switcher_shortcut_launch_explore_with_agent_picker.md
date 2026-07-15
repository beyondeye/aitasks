---
Task: t1148_tui_switcher_shortcut_launch_explore_with_agent_picker.md
Base branch: main
plan_verified: []
---

# Plan: Add `X` "explore + pick agent" shortcut to the TUI switcher (t1148)

## Context

The TUI switcher (`.aitask-scripts/lib/tui_switcher.py`) has an `x` shortcut
(`action_shortcut_explore`) that launches an explore agent **fire-and-forget**:
it immediately spawns `ait codeagent invoke explore` in a new window using the
wrapper's default code agent / model, with no chance to change either.

This task adds a sibling **`X` (shift-x)** shortcut that launches the explore
agent **but first opens the existing `AgentCommandScreen` dialog**, so the user
can confirm / change the code agent and model (and tmux target) before the
explore session starts. The existing `x` fire-and-forget behavior is left
untouched. Outcome: a user who wants a non-default agent/model for an explore
session gets a picker instead of having to pre-set the wrapper default.

The new handler mirrors the existing `action_shortcut_agent` (`e` "Code Agent")
handler, which already does the dialog-then-launch flow — the only differences
are `operation="explore"` (vs `"raw"`), the `agent-explore-N` window base, and
a non-empty prompt string.

## Source verification notes

- **`explore` is a valid codeagent operation** — `SUPPORTED_OPERATIONS` in
  `aitask_codeagent.sh:28` includes `explore` (maps to `/aitask-explore`), so
  `resolve_dry_run_command(project_root, "explore")` and
  `resolve_agent_string(project_root, "explore")` both work.
- **The task's claim that `explore` is in `_FRESH_WINDOW_OPERATIONS` is
  inaccurate** — `agent_command_screen.py:63-65` lists
  `{"pick", "raw", "explain", "qa", "resume", "syncfix"}`, which does **not**
  include `explore`. The dialog still defaults to "+ New window" anyway, because
  `_prefers_fresh_window` (`agent_command_screen.py:147-152`) *also* returns
  True when `default_window_name` starts with a `_FRESH_WINDOW_PREFIXES` prefix
  (`("agent-", "create-")`), and our window base is `agent-explore-N`. So the
  task's **conclusion** ("no change needed in `agent_command_screen.py`") is
  correct, but for the prefix reason, not the operation-whitelist reason. **No
  edit to `_FRESH_WINDOW_OPERATIONS` is needed.**
- **Binding auto-registration** — `TuiSwitcherOverlay.BINDINGS`
  (`tui_switcher.py:458`) splats `register_app_bindings(_TUI_SWITCHER_SCOPE,
  _QUICK_JUMP_BINDINGS)`, so adding a `Binding` to `_QUICK_JUMP_BINDINGS`
  registers the new action and wires override-awareness automatically. Shift-`X`
  is a distinct Textual key from `x` — no collision.

## Change surface (all in `.aitask-scripts/lib/tui_switcher.py`)

### 1. New binding in `_QUICK_JUMP_BINDINGS` (`:368-382`)

Add directly after the existing explore binding:

```python
    Binding("x", "shortcut_explore", "Explore", show=False),
    Binding("X", "shortcut_explore_pick", "Explore (pick agent)", show=False),
```

### 2. New hint segment in `_HINT_ITEMS` (`:220-232`)

Add after the existing explore hint (AC calls for it to appear in the hint row):

```python
    ("shortcut_explore", "explore", "x"),
    ("shortcut_explore_pick", "explore+", "X"),
```

### 3. New handler `action_shortcut_explore_pick`

Add immediately after `action_shortcut_explore` (`:1103-1124`). It copies the
shape of `action_shortcut_agent` (`:1146-1218`) — same stale-selection /
`_ensure_session_live` guards, same local imports, same result callback routing
(tmux → `launch_in_tmux` + `maybe_spawn_minimonitor`; `"run"` → terminal;
`None` → leave overlay open) — with these differences:

- `operation="explore"`, `operation_args=[]`.
- `full_cmd = resolve_dry_run_command(project_root, "explore")` (abort-with-notify
  if it returns None, exactly like the raw handler).
- `agent_string = resolve_agent_string(project_root, "explore")`.
- Window base `agent-explore-{n}` with the same uniqueness loop against
  `self._running_names` as `action_shortcut_explore` (`:1109-1112`).
- `prompt_str = "/aitask-explore"` (non-empty, so the dialog shows a copyable
  "Prompt only:" row — consistent with the board Pick-Task operation launch at
  `aitask_board.py:5481-5492`; purely cosmetic, the launched command comes from
  `screen.full_command`).
- `narrow=self._narrow`.
- Dialog title e.g. `"Launch Explore (pick agent)"`.

Sketch:

```python
def action_shortcut_explore_pick(self) -> None:
    """Launch an explore agent after opening the agent/model picker dialog.

    Unlike ``action_shortcut_explore`` (fire-and-forget via ``_spawn_in_session``
    with the wrapper's default agent), this opens the shared
    ``AgentCommandScreen`` for ``operation="explore"`` so the user can confirm /
    change the code agent and model before the explore session starts.
    """
    if self._handle_stale_selection():
        return
    if not self._ensure_session_live():
        return
    project_root = self._selected_project_root()
    from agent_command_screen import AgentCommandScreen
    from agent_launch_utils import (
        TmuxLaunchConfig,
        find_terminal,
        launch_in_tmux,
        maybe_spawn_minimonitor,
        resolve_agent_string,
        resolve_dry_run_command,
        spawn_in_terminal,
    )
    full_cmd = resolve_dry_run_command(project_root, "explore")
    if not full_cmd:
        self.app.notify(
            "Could not resolve agent command — check model configuration.",
            severity="error",
        )
        return
    agent_string = resolve_agent_string(project_root, "explore")
    n = 1
    while f"agent-explore-{n}" in self._running_names:
        n += 1
    window_name = f"agent-explore-{n}"
    screen = AgentCommandScreen(
        "Launch Explore (pick agent)",
        full_cmd,
        "/aitask-explore",
        default_window_name=window_name,
        project_root=project_root,
        operation="explore",
        operation_args=[],
        default_agent_string=agent_string,
        narrow=self._narrow,
    )

    def on_result(result) -> None:
        if isinstance(result, TmuxLaunchConfig):
            _, err = launch_in_tmux(screen.full_command, result)
            if err:
                self.app.notify(err, severity="error")
            elif result.new_window:
                maybe_spawn_minimonitor(
                    result.session, result.window, project_root=project_root,
                )
            self.dismiss(window_name)
        elif result == "run":
            terminal = find_terminal()
            if terminal:
                spawn_in_terminal(
                    terminal, ["sh", "-c", screen.full_command],
                    cwd=str(project_root),
                )
                self.dismiss(window_name)
            else:
                self.app.notify(
                    "No terminal emulator found", severity="error",
                )
        # result is None (cancelled) → leave the overlay open

    self.app.push_screen(screen, on_result)
```

**Scope decision (agent-only, no profile row):** `action_shortcut_agent` does
**not** pass `skill_name`/`default_profile`, so no per-run profile-edit row is
rendered — only the `(A)gent` picker. The task's Acceptance says "confirm /
change the code agent and model", i.e. agent/model only, so I mirror the raw
handler and omit `skill_name`. (Passing `skill_name="explore"` would additionally
surface a profile-edit row; that is a deliberate non-goal here to keep the change
focused on the stated AC. Noting it explicitly per the "no silent AC deviation"
rule.)

## Files touched

- `.aitask-scripts/lib/tui_switcher.py` — one binding, one hint item, one handler.
- `tests/test_tui_switcher_agent_launch.py` — extend with an explore-pick test
  class (see below).

No changes to `keybinding_registry.py`, `agent_command_screen.py`, or
`agent_launch_utils.py`.

## Tests

Extend `tests/test_tui_switcher_agent_launch.py`, mirroring the existing
`QuickJumpRegistrationTests` and `AgentLaunchActionTests`:

1. **Registration** — assert exactly one `_QUICK_JUMP_BINDINGS` entry with
   `action == "shortcut_explore_pick"` and `key == "X"`; assert `_HINT_ITEMS`
   contains `("shortcut_explore_pick", "explore+", "X")`. Also assert the
   original `shortcut_explore`/`x` binding and hint are **still present**
   (negative control that the fire-and-forget path is untouched).
2. **Action behavior** — reuse the `_make_overlay()` helper pattern; patch
   `alu.resolve_dry_run_command` / `alu.resolve_agent_string` /
   `alu.launch_in_tmux` / `alu.maybe_spawn_minimonitor` / `alu.find_terminal` /
   `alu.spawn_in_terminal`. Call `ov.action_shortcut_explore_pick()` and assert:
   - one `push_screen` call; the pushed `screen` is an `AgentCommandScreen` with
     `screen.operation == "explore"` and `screen.prompt_str == "/aitask-explore"`;
   - `screen._narrow is False` on a wide overlay (negative control);
   - tmux result (`TmuxLaunchConfig(..., new_window=True)`) → `launch_in_tmux`
     called once + `maybe_spawn_minimonitor` called once + `dismiss` called;
   - `"run"` result → `find_terminal` + `spawn_in_terminal` called + `dismiss`;
   - `None` result → no dismiss (overlay left open).
3. **Abort path** — patch `resolve_dry_run_command` → `None`; assert no
   `push_screen`, and `notify` called.
4. **Narrow host** — `_make_overlay_narrow()`; assert the pushed screen has
   `screen._narrow is True`.

## Verification

- Unit: `python3 tests/test_tui_switcher_agent_launch.py` (also run via
  `bash tests/run_all_python_tests.sh`). All existing + new tests pass.
- Lint: `shellcheck` is N/A (Python change); the repo runs Python tests only for
  this file.
- Manual (Step 9 / optional): inside a tmux session, open the switcher (`j`),
  press `X` → the `AgentCommandScreen` opens pre-populated for explore with the
  current default agent shown and changeable via `(A)gent`; confirming launches
  an `agent-explore-N` window with the chosen agent; cancelling launches
  nothing; pressing `x` still fire-and-forgets as before. (This live-TUI check is
  a good candidate for a manual-verification follow-up at Step 8c.)

## Step 9 (Post-Implementation)

Standard cleanup/archival per task-workflow Step 9: run project build/gate
verification, then `./.aitask-scripts/aitask_archive.sh 1148`. Working on the
current branch (profile 'fast'), so no worktree merge.

## Risk

### Code-health risk: low
- Additive change: one new binding, one hint item, one handler that copies a
  well-established sibling (`action_shortcut_agent`). No existing code path is
  modified; the `x` fire-and-forget handler is untouched (asserted by a negative
  control test). Blast radius is a single file plus its test. · severity: low
  · → mitigation: none needed

### Goal-achievement risk: low
- The approach is the exact pattern the task prescribes and the codebase already
  proves out for `raw`/`pick`; `explore` is a verified codeagent operation and
  the fresh-window default is confirmed to fire via the `agent-` window prefix.
  Acceptance criteria map 1:1 to the change + tests. · severity: low
  · → mitigation: none needed
