---
Task: t521_2_wire_agent_picker_into_launch_dialog.md
Parent Task: aitasks/t521_change_default_codeagent_at_run_time.md
Sibling Tasks: aitasks/t521/t521_1_extract_agent_model_picker_to_lib.md, aitasks/t521/t521_3_update_agent_command_screen_callers.md
Archived Sibling Plans: (none — all siblings pending)
Worktree: (none — working on current branch per fast profile)
Branch: main
Base branch: main
---

# p521_2 — Wire per-run agent/model picker into AgentCommandScreen

## Context

Add a "Change agent/model" control to the shared launch dialog
(`AgentCommandScreen` in `.aitask-scripts/lib/agent_command_screen.py`) so
users can pick any `<agent>/<model>` combo for a single invocation of
pick/explain/qa, without modifying the global defaults in
`codeagent_config.json`.

**Scope confirmed by user:**
- One-shot only (no disk persistence).
- Last override **per operation** remembered in a class-level
  `dict[str, str]` for the process lifetime.
- Status row under the title: `Agent: <current>` + `(A)gent` button +
  optional `(U)se last: <last>` button.
- Re-resolve command by re-shelling `aitask_codeagent.sh --agent-string
  <new> --dry-run invoke <op> <args>`.

**Depends on:** t521_1 (needs `lib/agent_model_picker.py`).
**Blocks:** t521_3 (call-site updates).

## Files to Modify

1. `.aitask-scripts/lib/agent_launch_utils.py`
   - Extend `resolve_dry_run_command` with keyword `agent_string` param.
   - Add new `resolve_agent_string(project_root, operation)` helper.

2. `.aitask-scripts/lib/agent_command_screen.py`
   - New constructor params: `project_root`, `operation`, `operation_args`,
     `default_agent_string`.
   - New class-level `_last_agent_override: dict[str, str]`.
   - New `#agent_row` in `compose()` (conditional on `self.operation`).
   - New CSS for `#agent_row`.
   - New key bindings: `a`/`A`/`u`/`U`.
   - New actions: `action_change_agent`, `action_use_last_agent`.
   - New helpers: `_apply_agent_override`, `_refresh_agent_row`,
     `_btn_change_agent`, `_btn_use_last_agent`.

## Implementation Steps

### 1. `agent_launch_utils.py` — extend `resolve_dry_run_command`

```python
def resolve_dry_run_command(
    project_root: Path,
    operation: str,
    *args: str,
    agent_string: str | None = None,
) -> str | None:
    wrapper = str(project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    cmd = [wrapper]
    if agent_string:
        cmd += ["--agent-string", agent_string]
    cmd += ["--dry-run", "invoke", operation] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output.startswith("DRY_RUN: "):
                return output[len("DRY_RUN: "):]
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
```

Verify `aitask_codeagent.sh` supports `--agent-string STR` before `--dry-run` — it does (see `.aitask-scripts/aitask_codeagent.sh:687-689`, global flag, order-independent).

### 2. `agent_launch_utils.py` — add `resolve_agent_string`

```python
def resolve_agent_string(project_root: Path, operation: str) -> str | None:
    """Call `aitask_codeagent.sh resolve <op>` and parse AGENT_STRING:... line."""
    wrapper = str(project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    try:
        result = subprocess.run(
            [wrapper, "resolve", operation],
            capture_output=True, text=True, timeout=10,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("AGENT_STRING:"):
                    return line[len("AGENT_STRING:"):].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None
```

Used by t521_3 callers to obtain the baseline agent string to display.

### 3. `agent_command_screen.py` — constructor

```python
def __init__(
    self,
    title: str,
    full_command: str,
    prompt_str: str,
    default_window_name: str = "",
    project_root: Path | None = None,
    operation: str | None = None,
    operation_args: list[str] | None = None,
    default_agent_string: str | None = None,
):
    super().__init__()
    self.title_text = title
    self.full_command = full_command
    self.prompt_str = prompt_str
    self.default_window_name = default_window_name
    self._project_root = project_root or Path.cwd()
    self.operation = operation
    self.operation_args: list[str] = list(operation_args or [])
    self.current_agent_string: str | None = default_agent_string
    self._tmux_available = is_tmux_available()
    self._tmux_defaults = load_tmux_defaults(project_root or Path.cwd())
    self._split_horizontal = self._tmux_defaults["default_split"] == "horizontal"
    self._selected_session: str | None = None
    self._selected_window: str | None = None
```

Note: the existing code already has `project_root` as a param (used for
`load_tmux_defaults`), but it's *not stored on self*. This change stores
it as `self._project_root` for reuse by the override flow.

### 4. Class-level override memory

After the existing `_last_session` / `_last_window` lines (around line 173):

```python
_last_agent_override: dict[str, str] = {}
```

### 5. CSS — append to `DEFAULT_CSS`

```css
#agent_row {
    height: 3;
    width: 100%;
    align: left middle;
    margin: 0 0 1 0;
}
#agent_row Label {
    padding: 0 1;
}
#agent_row Button {
    margin: 0 1;
    width: auto;
    min-width: 10;
}
```

### 6. `compose()` — conditional agent row

Insert after `yield Label(self.title_text, id="agent_cmd_title")` and
before `yield Label("Command:")`:

```python
if self.operation:
    with Horizontal(id="agent_row"):
        yield Label(
            f"Agent: {self.current_agent_string or '(unknown)'}",
            id="agent_row_label",
        )
        yield Button("(A)gent", variant="primary", id="btn_change_agent")
        yield Button(
            "",
            variant="default",
            id="btn_use_last_agent",
            classes="hidden",
        )
```

### 7. Key bindings

Add to `BINDINGS`:

```python
Binding("a", "change_agent", "Change agent", show=False),
Binding("A", "change_agent", "Change agent", show=False),
Binding("u", "use_last_agent", "Use last agent", show=False),
Binding("U", "use_last_agent", "Use last agent", show=False),
```

### 8. `on_key` update

Extend the existing `on_key` handler to intercept `a`/`u` when no Input/Select
is focused (same guard as the existing `t`/`s`/`n`/`w`/`m` handling).
Actually, Textual will automatically invoke `action_change_agent` for the
`a` binding — the `on_key` guard is only needed when the focused widget
would otherwise consume the key. Since we want `a`/`u` to work
irrespective of whether a Select is focused (e.g., session Select), check
the existing pattern and mirror it.

Safer approach: do NOT add `a`/`u` to `BINDINGS` — instead handle them
explicitly in `on_key` after the Input/Select guard, similar to `t`, `s`,
`n`, `w`, `m`. This gives consistent focus-aware behavior.

```python
elif event.key in ("a", "A"):
    if self.operation:
        self.action_change_agent()
    event.prevent_default()
elif event.key in ("u", "U"):
    if self.operation:
        self.action_use_last_agent()
    event.prevent_default()
```

### 9. Actions

```python
def action_change_agent(self) -> None:
    if not self.operation:
        return
    from agent_model_picker import AgentModelPickerScreen, load_all_models
    all_models = load_all_models(self._project_root)
    current_agent, current_model = "", ""
    if self.current_agent_string and "/" in self.current_agent_string:
        current_agent, current_model = self.current_agent_string.split("/", 1)
    picker = AgentModelPickerScreen(
        self.operation, current_agent, current_model, all_models=all_models,
    )
    self.app.push_screen(picker, self._on_agent_picked)

def _on_agent_picked(self, result) -> None:
    if not result or not isinstance(result, dict):
        return
    new_agent_string = result.get("value")
    if not new_agent_string:
        return
    self._apply_agent_override(new_agent_string)
    AgentCommandScreen._last_agent_override[self.operation] = new_agent_string
    self._refresh_agent_row()

def action_use_last_agent(self) -> None:
    if not self.operation:
        return
    last = AgentCommandScreen._last_agent_override.get(self.operation)
    if last and last != self.current_agent_string:
        self._apply_agent_override(last)
        self._refresh_agent_row()
```

### 10. `_apply_agent_override` — re-resolve command

```python
def _apply_agent_override(self, agent_string: str) -> None:
    self.current_agent_string = agent_string
    new_cmd = resolve_dry_run_command(
        self._project_root,
        self.operation,
        *self.operation_args,
        agent_string=agent_string,
    )
    if new_cmd:
        self.full_command = new_cmd
        try:
            self.query_one("#agent_cmd_input", Input).value = new_cmd
        except Exception:
            pass
    else:
        self.app.notify(
            f"Failed to resolve command for {agent_string}",
            severity="error",
        )
```

Add `resolve_dry_run_command` to the imports at the top of the file
(alongside `TmuxLaunchConfig`, `get_tmux_sessions`, etc.).

### 11. `_refresh_agent_row`

```python
def _refresh_agent_row(self) -> None:
    if not self.operation:
        return
    try:
        label = self.query_one("#agent_row_label", Label)
        label.update(f"Agent: {self.current_agent_string or '(unknown)'}")
    except Exception:
        return
    try:
        use_last_btn = self.query_one("#btn_use_last_agent", Button)
    except Exception:
        return
    last = AgentCommandScreen._last_agent_override.get(self.operation)
    if last and last != self.current_agent_string:
        use_last_btn.label = f"(U)se last: {last}"
        use_last_btn.remove_class("hidden")
    else:
        use_last_btn.add_class("hidden")
```

### 12. Button handlers

```python
@on(Button.Pressed, "#btn_change_agent")
def _btn_change_agent(self) -> None:
    self.action_change_agent()

@on(Button.Pressed, "#btn_use_last_agent")
def _btn_use_last_agent(self) -> None:
    self.action_use_last_agent()
```

### 13. `on_mount` — refresh agent row

At the end of the existing `on_mount`, call `self._refresh_agent_row()` so
the "(U)se last" button state is correct when the dialog opens.

## Verification

### Syntax
```bash
python3 -m py_compile .aitask-scripts/lib/agent_command_screen.py
python3 -m py_compile .aitask-scripts/lib/agent_launch_utils.py
```

### Unit test of `resolve_dry_run_command` with agent override
```bash
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, '.aitask-scripts/lib')
from agent_launch_utils import resolve_dry_run_command, resolve_agent_string
print('default pick:', resolve_dry_run_command(Path('.'), 'pick', '521'))
print('overridden:', resolve_dry_run_command(Path('.'), 'pick', '521', agent_string='claudecode/sonnet4_6'))
print('baseline:', resolve_agent_string(Path('.'), 'pick'))
"
```

Expected: default and overridden commands differ by the model flag value.

### Interactive smoke test (single call site)

Temporarily edit `aitask_board.py:3331` (or whichever pick site is
easiest) to pass the new params, then:
1. Open pick dialog → status row visible with current agent string.
2. Press `a` → `AgentModelPickerScreen` opens. Pick a different model.
3. Dialog's command Input updates to the re-resolved command.
4. Close the dialog. Open pick on a different task.
5. "(U)se last: …" button visible. Press `u` → command updates without
   picker.
6. Close the TUI, reopen — "(U)se last" button gone (per-process state).

Revert the temporary edit before committing — t521_3 will do the real
call-site updates.

### Non-regression
- `ait board` → create task → dialog has no agent row (create call site
  doesn't pass `operation`).

## Step 9 reference

Per task-workflow Step 9: after implementation + review, run
`./.aitask-scripts/aitask_archive.sh 521_2`.
