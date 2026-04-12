---
priority: medium
effort: medium
depends: [t521_1]
issue_type: feature
status: Ready
labels: [codeagent, aitask_board]
created_at: 2026-04-12 09:47
updated_at: 2026-04-12 09:47
---

## Context

Second step of t521: add a per-run agent/model picker to the shared launch dialog (`AgentCommandScreen` in `.aitask-scripts/lib/agent_command_screen.py`). When users trigger pick/explain/qa from `ait board`, `ait codebrowser`, or `ait monitor`, the dialog currently displays the pre-built command using the **global default** model; this task lets users override the model for that specific run.

**User-confirmed design:**
- **Scope:** one-shot only — no disk persistence.
- **Memory:** dialog remembers the last override **per operation** (dict keyed by `"pick"`, `"explain"`, `"qa"`) in a class-level variable. Persists for the lifetime of the TUI process only.
- **UI:** status row under the title showing `Agent: <current>` with an "(A)gent change" button and an optional "(U)se last: <last>" button that appears when a remembered override exists.
- **Re-resolution:** on override, re-shell `aitask_codeagent.sh --agent-string <new> --dry-run invoke <op> <args>` and update the command Input.

Part of t521 (parent) — see `aiplans/p521/` for the full design and sibling tasks.

## Key Files to Modify

- `.aitask-scripts/lib/agent_command_screen.py` — add constructor params, class-level state, status row, key bindings, and picker wiring.
- `.aitask-scripts/lib/agent_launch_utils.py` — extend `resolve_dry_run_command` with an `agent_string` kwarg and add a new `resolve_agent_string(project_root, op)` helper.

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_model_picker.py` — **sibling task t521_1 must be done first.** Provides `AgentModelPickerScreen`, `FuzzySelect`, `load_all_models()`.
- `.aitask-scripts/lib/agent_command_screen.py:176–194` — existing `__init__` pattern for constructor params.
- `.aitask-scripts/lib/agent_command_screen.py:229–250` — existing `on_mount` for reference on mounting widgets dynamically.
- `.aitask-scripts/lib/agent_command_screen.py:481–517` — existing `on_key` handler showing how to guard against Input/Select focus.
- `.aitask-scripts/lib/agent_command_screen.py:172–174` — `_last_session` / `_last_window` pattern for class-level remembered state (mirror this for `_last_agent_override`).
- `.aitask-scripts/aitask_codeagent.sh:124–157` (`resolve_agent_string`) and `:687–689` (`--agent-string` flag parsing) confirm the wrapper already supports the override; no script changes needed.

## Implementation Plan

### 1. Extend `resolve_dry_run_command` in `agent_launch_utils.py`

Add a keyword-only `agent_string` param (default `None`). When set, prepend `--agent-string <value>` to the wrapper args **before** `--dry-run`:

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

All existing callers work unchanged because `agent_string` defaults to `None`.

### 2. Add `resolve_agent_string` helper in `agent_launch_utils.py`

```python
def resolve_agent_string(project_root: Path, operation: str) -> str | None:
    """Call `aitask_codeagent.sh resolve <op>` and parse the AGENT_STRING:... line."""
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

Export it alongside the other helpers.

### 3. Update `AgentCommandScreen.__init__` signature

Add keyword-only params (all optional, backward compatible):

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
    self.operation_args = list(operation_args or [])
    self.current_agent_string: str | None = default_agent_string
    # ... existing tmux init ...
```

### 4. Add class-level override memory

```python
class AgentCommandScreen(ModalScreen):
    # ... existing class vars ...
    _last_agent_override: dict[str, str] = {}  # operation -> agent_string
```

Keyed by operation so pick/explain/qa each have their own remembered choice.

### 5. Add CSS for the new row

Append to `DEFAULT_CSS`:

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

### 6. Mount the agent row in `on_mount`

Only when `self.operation` is set. Mount after the title label, before the Command Input. Use `self.query_one("#agent_cmd_dialog", Container)` and `.mount(..., before=self.query_one("#agent_cmd_input"))` if Textual supports relative positioning, otherwise restructure `compose()` to conditionally yield the row.

**Simpler approach:** add the conditional yield inside `compose()`:

```python
def compose(self):
    with Container(id="agent_cmd_dialog"):
        yield Label(self.title_text, id="agent_cmd_title")
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
        yield Label("Command:")
        yield Input(value=self.full_command, id="agent_cmd_input")
        # ... existing tabs ...
```

Then `on_mount` updates the "Use last" button visibility/label by calling `self._refresh_agent_row()`.

### 7. `_refresh_agent_row()` helper

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

### 8. Key bindings + actions

Add to `BINDINGS`:

```python
Binding("a", "change_agent", "Change agent", show=False),
Binding("A", "change_agent", "Change agent", show=False),
Binding("u", "use_last_agent", "Use last agent", show=False),
Binding("U", "use_last_agent", "Use last agent", show=False),
```

Extend `on_key` to intercept `a`/`u` only when no Input/Select focused (same guard as existing `t`/`s`/`n`/`w`/`m`).

### 9. `action_change_agent` — open picker

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
```

### 10. `action_use_last_agent`

```python
def action_use_last_agent(self) -> None:
    if not self.operation:
        return
    last = AgentCommandScreen._last_agent_override.get(self.operation)
    if last and last != self.current_agent_string:
        self._apply_agent_override(last)
        self._refresh_agent_row()
```

### 11. `_apply_agent_override` — re-resolve command

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

### 12. Button handlers for the new buttons

```python
@on(Button.Pressed, "#btn_change_agent")
def _btn_change_agent(self) -> None:
    self.action_change_agent()

@on(Button.Pressed, "#btn_use_last_agent")
def _btn_use_last_agent(self) -> None:
    self.action_use_last_agent()
```

## Verification Steps

1. Syntax check:
   ```bash
   python3 -m py_compile .aitask-scripts/lib/agent_command_screen.py
   python3 -m py_compile .aitask-scripts/lib/agent_launch_utils.py
   ```
2. Existing callers still work (smoke test): launch `ait board`, open pick dialog on a task. The dialog must still render correctly (status row visible because callers from t521_3 will set `operation`; before t521_3 is done, pass `operation=None` from a local test or skip this until t521_3 lands — acceptable either way).
3. **Manual interactive test** (requires the current TUI caller to pass the new params, which is t521_3's responsibility). A minimal test is to edit **one** call site (e.g., `aitask_board.py:3331`) temporarily to pass `operation="pick"`, `operation_args=[num]`, `project_root=Path(".")`, `default_agent_string=resolve_agent_string(Path("."), "pick")`, then:
   - Open pick dialog — status row visible with the global default agent string.
   - Press `a` — picker opens. Select a different model.
   - Dialog's Command Input updates to the re-resolved command.
   - Close dialog, open again on another task — "(U)se last: …" button appears with the previously chosen override.
   - Press `u` — command refreshes without opening the picker.
4. Create-task dialog (`aitask_board.py:3597`, `operation=None`) — agent row is **not** shown. No regression.

## Dependencies

- **Depends on:** t521_1 (needs `lib/agent_model_picker.py`).
- **Must be completed before:** t521_3 (updates all callers to pass the new params).
