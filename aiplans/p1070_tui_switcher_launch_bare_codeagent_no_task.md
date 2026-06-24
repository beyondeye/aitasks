---
Task: t1070_tui_switcher_launch_bare_codeagent_no_task.md
Worktree: (none — profile 'fast', working on current branch)
Branch: main
Base branch: main
---

# Plan: TUI-switcher command to launch a bare code agent (no task)

## Context

From the TUI switcher (`j` overlay) the user wants a command that launches a
**bare code agent with no task** — an interactive agent started with *no*
`/aitask-*` slash command (just `claude --model <id>`, or the codex/opencode
equivalent), via the **shared agent command dialog** so the user can pick
agent / model / tmux target first.

The two building blocks already exist and connect cleanly:

- **The dialog** — `AgentCommandScreen` (`.aitask-scripts/lib/agent_command_screen.py:132`)
  requires no task: `operation`, `skill_name`, `operation_args` are all optional.
  The **syncer** already drives it with `operation="raw"`
  (`syncer_app.py:496`); the **board** shows the `push_screen(...)` + result
  callback pattern (`aitask_board.py:5415`, `:5458`).
- **The command** — `resolve_dry_run_command(project_root, "raw")` with *no* args
  resolves to the bare agent: `aitask_codeagent.sh`'s `raw` op appends no prompt
  (`aitask_codeagent.sh:443-444`), yielding `claude --model <id>` (and the
  per-agent equivalent for codex/opencode at `:450`, `:492`).
- **The switcher** already launches agents from quick-jump shortcuts
  (`action_shortcut_explore`, key `x`, `tui_switcher.py:1033`;
  `action_shortcut_create`, key `n`, `:1056`) and already pushes modals from the
  overlay (`self.app.push_screen(StaleEntryModal(...))`, `:548`).

The gap: those existing switcher shortcuts **direct-spawn** (`_spawn_in_session`)
and never open the dialog. This adds a **new dialog-based** launch to the
switcher — the board's pattern, applied in the overlay.

## Decisions (confirmed with user)

- **Key:** `e` (mnemonic "agEnt"), **user-rebindable** via the
  `shared.tui_switcher` shortcut scope (same as explore/create).
- **Empty prompt row:** hide the dialog's "Prompt only:" / "Copy Prompt" row
  when `prompt_str` is empty (guarded — affects only the empty-prompt case).

## Changes

### 1. `.aitask-scripts/lib/agent_command_screen.py` — hide empty prompt row

In `on_mount` (`:437-444`), guard the prompt-row mount on a non-empty
`prompt_str`:

```python
def on_mount(self) -> None:
    # Populate direct tab
    direct = self.query_one("#direct_content")
    if self.prompt_str:
        direct.mount(Label("Prompt only:"))
        row = Horizontal(classes="agent-cmd-copy-row")
        direct.mount(row)
        row.mount(Label(self.prompt_str, id="agent_cmd_prompt_label"))
        row.mount(Button(self.label("copy_prompt", "Copy Prompt"),
                         variant="primary", id="btn_copy_prompt"))
    buttons = Horizontal(classes="agent-cmd-buttons")
    ...
```

Safe because nothing does an unconditional `query_one("#agent_cmd_prompt_label")`
or `"#btn_copy_prompt"` — the only references are CSS (`:191`, `:280`, which
simply won't match) and the `copy_prompt` handler/`p`/`P` binding (`:313-314`,
`:669-672`), which copies `self.prompt_str` (empty string → harmless no-op).
The agent/profile-override paths that reassign `prompt_str` (`:956`, `:989`)
only fire when `skill_name`/profile override is set, which the raw launch never
passes. Existing callers all pass a non-empty prompt, so their behavior is
unchanged.

### 2. `.aitask-scripts/lib/tui_switcher.py` — new rebindable shortcut + action

**a. Register the binding** — add to `_QUICK_JUMP_BINDINGS` (`:364`):

```python
    Binding("e", "shortcut_agent", "Code Agent", show=False),
```

This single edit also propagates to the two **derived** sites automatically:
`_OVERLAY_RESERVED_KEYS` (`:383`, comprehended from `_QUICK_JUMP_BINDINGS`, so
the open-key toggle won't swallow `e`) and `register_app_bindings(...)` in
`BINDINGS` (`:452`, which makes it rebindable). `_TUI_SHORTCUTS` (`:190`) is
**not** touched — it holds TUI-registry switches only; explore/create/agent are
not in it.

**b. Bottom-hint entry** — add to `_HINT_ITEMS` (`:217`, the hand-maintained
hint list that parallels `_QUICK_JUMP_BINDINGS` — they are intentionally
separate: the hint omits applink and uses lowercase labels):

```python
    ("shortcut_agent", "agent", "e"),
```

**c. New action method** — add near the existing agent-launch actions
(after `action_shortcut_create`, ~`:1074`), following the board's
`_launch_brainstorm` callback pattern (`aitask_board.py:5458-5470`) but with
`operation="raw"` (so the agent-override row renders and the user can switch
agent/model) and an empty prompt:

```python
def action_shortcut_agent(self) -> None:
    """Open the agent command dialog to launch a bare code agent (no task)."""
    if self._handle_stale_selection():
        return
    if not self._ensure_session_live():
        return
    project_root = self._project_root_for_session(self._session)
    full_cmd = resolve_dry_run_command(project_root, "raw")
    if not full_cmd:
        self.app.notify(
            "Could not resolve agent command — check model configuration.",
            severity="error",
        )
        return
    agent_string = resolve_agent_string(project_root, "raw")
    n = 1
    while f"agent-raw-{n}" in self._running_names:
        n += 1
    window_name = f"agent-raw-{n}"
    from agent_command_screen import AgentCommandScreen
    from agent_launch_utils import (
        TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor,
        find_terminal, spawn_in_terminal,
    )
    screen = AgentCommandScreen(
        "Launch Code Agent (no task)",
        full_cmd,
        "",  # empty prompt — no task / no slash command
        default_window_name=window_name,
        project_root=project_root,
        operation="raw",
        operation_args=[],
        default_agent_string=agent_string,
    )

    def on_result(result):
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
                spawn_in_terminal(terminal, ["sh", "-c", screen.full_command])
                self.dismiss(window_name)
            else:
                self.app.notify("No terminal emulator found", severity="error")
        # result is None (cancelled) → leave the overlay open

    self.app.push_screen(screen, on_result)
```

Notes:
- Imports of `resolve_dry_run_command` / `resolve_agent_string` already exist at
  the top of `tui_switcher.py` (`:48`); the `AgentCommandScreen` /
  `launch_in_tmux` / `maybe_spawn_minimonitor` / `find_terminal` /
  `spawn_in_terminal` imports are done locally inside the method (mirroring the
  existing `from agent_launch_utils import maybe_spawn_minimonitor` local import
  at `:1046`) to avoid a module-load cost / potential import cycle. Confirm exact
  symbol names against `agent_launch_utils.py` during implementation
  (`find_terminal`/`spawn_in_terminal` exist per `agent_launch_utils.py:152`).
- The `agent-raw-{n}` window name uses the `agent-` prefix (`_AGENT_PREFIXES`,
  `:175`) so the launched window is classified under the switcher's "Code Agents"
  group, exactly like `agent-explore-{n}`.
- The dialog provides its own session/window picker (tmux tab), so the user
  chooses the target there; we pass the SELECTED session's `project_root` so
  command resolution and the default window name are correct.

## Tests

Mirror the existing test style for these modules (bash harness under `tests/`,
plus any Python unit tests). Concretely:

- **`tui_switcher`** — locate the existing switcher test(s)
  (`grep -rl tui_switcher tests/`) and add coverage that:
  - `_QUICK_JUMP_BINDINGS` and `_HINT_ITEMS` both contain a `shortcut_agent`
    entry bound to `e` (guards the two-list-sync hazard).
  - `action_shortcut_agent` resolves the raw command and calls
    `self.app.push_screen` with an `AgentCommandScreen` whose `prompt_str` is
    empty and `operation == "raw"` (use a stubbed app/`push_screen`, as existing
    switcher tests stub tmux). Assert the `on_result` callback routes a
    `TmuxLaunchConfig` to `launch_in_tmux` and `"run"` to `spawn_in_terminal`.
- **`agent_command_screen`** — add a unit test asserting that with
  `prompt_str=""` no `#agent_cmd_prompt_label` / `#btn_copy_prompt` widget is
  mounted, and that with a non-empty prompt they still are (regression guard for
  existing callers). Follow whatever async Textual test harness the repo already
  uses for this module (`grep -rl agent_command_screen tests/`); if none exists,
  a minimal `App.run_test()` pilot test is acceptable.

Run: `bash tests/<switcher_test>.sh` and the agent_command_screen test;
`shellcheck` is N/A (pure Python change). No `.j2`/skill/golden surfaces are
touched, so `aitask_skill_verify.sh` is not required.

## Verification (manual, end-to-end)

1. In a tmux session, open any TUI that mounts the switcher (e.g. `ait board`),
   press `j`, then `e`.
2. Confirm the dialog opens titled "Launch Code Agent (no task)" with: a
   resolved bare-agent command in the Command field, the agent-override row
   present (switchable), the **Profile row absent**, and the **"Prompt only:"
   row absent**.
3. On the Tmux tab, pick a new window and launch; confirm an interactive agent
   starts in a new `agent-raw-N` window running **no** slash command, with a
   minimonitor companion as for other agent launches.
4. Re-open the switcher; confirm the `(e) agent` hint shows in the bottom row
   and the new window appears under "Code Agents".
5. Switch the agent/model in the dialog and confirm the command updates.

## Cross-agent note

Pure-Python TUI change (`tui_switcher.py` / `agent_command_screen.py`) — not a
skill surface — so no Claude/Codex/OpenCode skill port is implied.

## Risk

### Code-health risk: low
- The only shared-surface edit (`agent_command_screen.py` `on_mount`, used by
  board/monitor/syncer/codebrowser) is guarded to the empty-`prompt_str` case;
  all existing callers pass a non-empty prompt and are provably unchanged ·
  severity: low · → mitigation: in-plan (conditional guard + regression test
  asserting non-empty prompts still mount the row), no separate task needed.
- Two parallel lists (`_QUICK_JUMP_BINDINGS`, `_HINT_ITEMS`) must both gain the
  `shortcut_agent` entry · severity: low · → mitigation: in-plan (test asserts
  both lists contain it).

### Goal-achievement risk: low
- None identified. The dialog-based raw launch is exactly the requested
  behavior; every building block (raw op → bare command, no-task dialog,
  overlay→modal push) was verified during exploration.

_No before/after risk-mitigation follow-up tasks proposed — both dimensions are
low and the single code-health concern is mitigated within this plan._

## Step 9 (Post-Implementation)

Profile 'fast' works on the current branch (no worktree/branch cleanup). After
review/commit, archive via `./.aitask-scripts/aitask_archive.sh 1070` and push.
