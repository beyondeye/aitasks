---
priority: medium
effort: low
depends: [t521_2]
issue_type: feature
status: Implementing
labels: [codeagent, aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-12 09:48
updated_at: 2026-04-12 11:39
---

## Context

Third and final step of t521: thread the new `operation`, `operation_args`, `project_root`, and `default_agent_string` params through every call site that instantiates `AgentCommandScreen`. After this task, the per-run agent/model picker from sibling t521_2 becomes usable from all TUIs (board, codebrowser, monitor).

**One call site is intentionally NOT updated:** `aitask_board.action_create_task` at `.aitask-scripts/board/aitask_board.py:3597` uses the dialog to launch `./aitask_create.sh`, which is not a code agent — there is no agent/model to pick. Leave the call unchanged (`operation=None`, agent row hidden).

Part of t521 (parent) — see `aiplans/p521/` for the full design and sibling tasks.

## Key Files to Modify

- `.aitask-scripts/board/aitask_board.py` — 2 pick call sites (lines ~3331 and ~3413).
- `.aitask-scripts/codebrowser/codebrowser_app.py` — 1 explain call site (~line 693).
- `.aitask-scripts/codebrowser/history_screen.py` — 1 qa call site (~line 284).
- `.aitask-scripts/monitor/monitor_app.py` — 1 pick call site (~line 978).

Line numbers are approximate — grep for `AgentCommandScreen(` in each file.

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_command_screen.py` — new constructor signature (from sibling t521_2).
- `.aitask-scripts/lib/agent_launch_utils.py` — new `resolve_agent_string(project_root, operation)` helper (from t521_2).
- `aiplans/p521_change_default_codeagent_at_run_time.md` (parent plan, if saved) — call-site table.

## Implementation Plan

### For each of the 5 codeagent call sites, update to match this template:

**1. `.aitask-scripts/board/aitask_board.py` — pick (TaskDetailScreen callback, ~line 3331):**

```python
# Existing local vars: task_num, focused, num, full_cmd, prompt_str
agent_string = resolve_agent_string(Path("."), "pick")
screen = AgentCommandScreen(
    f"Pick Task t{num}", full_cmd, prompt_str,
    default_window_name=f"agent-pick-{num}",
    project_root=Path("."),
    operation="pick",
    operation_args=[num],
    default_agent_string=agent_string,
)
```

Ensure `resolve_agent_string` is imported at the top of the file (alongside `resolve_dry_run_command`).

**2. `.aitask-scripts/board/aitask_board.py` — action_pick_task (~line 3413):**
Same pattern as above. Same import already covered.

**3. `.aitask-scripts/board/aitask_board.py` — action_create_task (~line 3597):**
**LEAVE UNCHANGED.** No `operation` param. Agent row stays hidden.

**4. `.aitask-scripts/codebrowser/codebrowser_app.py` — explain (~line 693):**

```python
agent_string = resolve_agent_string(self._project_root, "explain")
screen = AgentCommandScreen(
    title, full_cmd, prompt_str,
    default_window_name=window_name,
    project_root=self._project_root,
    operation="explain",
    operation_args=[arg],  # same arg currently passed to resolve_dry_run_command
    default_agent_string=agent_string,
)
```

Add `resolve_agent_string` to the existing `from agent_launch_utils import ...` line.

**5. `.aitask-scripts/codebrowser/history_screen.py` — qa (~line 284):**

```python
agent_string = resolve_agent_string(self._project_root, "qa")
screen = AgentCommandScreen(
    title, full_cmd, prompt_str,
    default_window_name=window_name,
    project_root=self._project_root,
    operation="qa",
    operation_args=[task_id],
    default_agent_string=agent_string,
)
```

Add `resolve_agent_string` to the existing `from agent_launch_utils import ...` line.

**6. `.aitask-scripts/monitor/monitor_app.py` — pick (~line 978):**

```python
agent_string = resolve_agent_string(self._project_root, "pick")
screen = AgentCommandScreen(
    title, full_cmd, prompt_str,
    default_window_name=window_name,
    project_root=self._project_root,
    operation="pick",
    operation_args=[target_id],
    default_agent_string=agent_string,
)
```

Add `resolve_agent_string` to the existing `from agent_launch_utils import ...` line.

### Discovery step (do this first)

Before editing, run:

```bash
grep -rn "AgentCommandScreen(" .aitask-scripts/
```

Confirm the 6 call sites in the files above are the complete set. If additional call sites exist (e.g., added after t521 was written), update them too (or leave `operation=None` if they aren't codeagent calls).

### Pick the exact `operation_args`

Each call site currently builds `full_cmd` via `resolve_dry_run_command(self._project_root, "<op>", <args>)`. The `<args>` passed there are the **same** args that should be passed as `operation_args` — they are the positional arguments after the operation name. Don't re-derive them; literally copy the values used by the existing `resolve_dry_run_command` call.

## Verification Steps

1. Syntax check all touched files:
   ```bash
   python3 -m py_compile .aitask-scripts/board/aitask_board.py
   python3 -m py_compile .aitask-scripts/codebrowser/codebrowser_app.py
   python3 -m py_compile .aitask-scripts/codebrowser/history_screen.py
   python3 -m py_compile .aitask-scripts/monitor/monitor_app.py
   ```
2. Full end-to-end smoke test (requires t521_1 and t521_2 completed):
   - `ait board` → focus a task → press pick shortcut. Dialog shows status row with current agent. Press `a` → picker opens. Pick a different model → dialog's Command Input updates. Press Esc to close. Open pick on another task — "(U)se last: …" button visible. Press `u` — command refreshes.
   - `ait board` → open task detail → pick from there (second call site). Same behavior.
   - `ait codebrowser` → run explain on a file. Status row shows `claudecode/sonnet4_6` (or whatever the explain default is). Picker + use-last work.
   - `ait codebrowser` → history screen → run qa on a task. Same.
   - `ait monitor` → pick a task. Same.
   - `ait board` → create task. **No agent row shown.** Dialog behaves as before.
3. Open `ait settings` → Agent Defaults tab → confirm the global `pick`/`explain`/`qa` defaults are unchanged after using an override in the launch dialog (one-shot scope).
4. Quit all TUIs and restart `ait board`. Open pick dialog — the `(U)se last` button is gone (class-level state is per-process).

## Dependencies

- **Depends on:** t521_1 (lib/agent_model_picker.py) and t521_2 (AgentCommandScreen + resolve_agent_string).
- **Must be completed before:** t521 parent task closure.
