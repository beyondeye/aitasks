---
Task: t521_3_update_agent_command_screen_callers.md
Parent Task: aitasks/t521_change_default_codeagent_at_run_time.md
Sibling Tasks: aitasks/t521/t521_1_extract_agent_model_picker_to_lib.md, aitasks/t521/t521_2_wire_agent_picker_into_launch_dialog.md
Archived Sibling Plans: (none — all siblings pending)
Worktree: (none — working on current branch per fast profile)
Branch: main
Base branch: main
---

# p521_3 — Update AgentCommandScreen callers to pass operation + agent override hooks

## Context

Third and final step of t521. Sibling task t521_2 added the agent/model
picker to the shared launch dialog `AgentCommandScreen` behind new optional
constructor params (`project_root`, `operation`, `operation_args`,
`default_agent_string`). This task threads those params through every call
site so the picker becomes usable from all TUIs (board, codebrowser, monitor).

**Depends on:** t521_1 (lib/agent_model_picker.py) and t521_2
(AgentCommandScreen param additions, `resolve_agent_string` helper).

**One call site is intentionally left alone:**
`aitask_board.action_create_task` (around line 3597) — it uses the dialog to
launch `./aitask_create.sh`, not a code agent. The dialog must stay unchanged
there (no `operation` param → agent row hidden).

## Files to Modify

| File | Call site(s) | Operation | Args source |
|------|--------------|-----------|-------------|
| `.aitask-scripts/board/aitask_board.py` | ~3331 (task detail pick) | `"pick"` | `num` (task number string) |
| `.aitask-scripts/board/aitask_board.py` | ~3413 (`action_pick_task`) | `"pick"` | `num` |
| `.aitask-scripts/board/aitask_board.py` | ~3597 (`action_create_task`) | — | **LEAVE UNCHANGED** |
| `.aitask-scripts/codebrowser/codebrowser_app.py` | ~693 (explain) | `"explain"` | existing arg passed to `resolve_dry_run_command` |
| `.aitask-scripts/codebrowser/history_screen.py` | ~284 (qa) | `"qa"` | `task_id` |
| `.aitask-scripts/monitor/monitor_app.py` | ~978 (pick) | `"pick"` | `target_id` |

Line numbers are approximate — grep each file for `AgentCommandScreen(`
before editing.

## Implementation Steps

### 0. Discovery

```bash
grep -rn "AgentCommandScreen(" .aitask-scripts/
```

Confirm the 6 call sites in the table above. If additional sites exist,
update them with the appropriate `operation` (or leave them unchanged if
they don't invoke a code agent).

### 1. `board/aitask_board.py` — two pick sites

At the top of the file, update the existing agent_launch_utils import to
include `resolve_agent_string`:

```python
from agent_launch_utils import (
    find_terminal,
    find_window_by_name,
    resolve_dry_run_command,
    resolve_agent_string,  # NEW
    TmuxLaunchConfig,
    launch_in_tmux,
    maybe_spawn_minimonitor,
)
```

At the two pick call sites (inside TaskDetailScreen callback and inside
`action_pick_task`), replace:

```python
screen = AgentCommandScreen(
    f"Pick Task t{num}", full_cmd, prompt_str,
    default_window_name=f"agent-pick-{num}",
)
```

with:

```python
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

`Path` is already imported in `aitask_board.py`; confirm via grep before
adding a fresh import.

**Do NOT touch** the `action_create_task` site at line ~3597.

### 2. `codebrowser/codebrowser_app.py` — explain

Update the import:

```python
from agent_launch_utils import (
    find_terminal as _find_terminal,
    resolve_dry_run_command,
    resolve_agent_string,  # NEW
    TmuxLaunchConfig,
    launch_in_tmux,
    maybe_spawn_minimonitor,
)
```

At the explain call site (~line 693):

```python
full_cmd = resolve_dry_run_command(self._project_root, "explain", arg)
# ... existing code ...
agent_string = resolve_agent_string(self._project_root, "explain")
screen = AgentCommandScreen(
    title, full_cmd, prompt_str,
    default_window_name=window_name,
    project_root=self._project_root,
    operation="explain",
    operation_args=[arg],
    default_agent_string=agent_string,
)
```

Copy the existing `arg` value used in `resolve_dry_run_command` as the
`operation_args` entry — don't re-derive it.

### 3. `codebrowser/history_screen.py` — qa

Update the import (same pattern). At the qa call site (~line 284):

```python
full_cmd = resolve_dry_run_command(self._project_root, "qa", task_id)
# ... existing code ...
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

### 4. `monitor/monitor_app.py` — pick

Update the import (same pattern). At the pick call site (~line 978):

```python
full_cmd = resolve_dry_run_command(self._project_root, "pick", target_id)
# ... existing code ...
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

### 5. Verify `Path` is imported

For each file modified, confirm `from pathlib import Path` is already
imported (needed for `Path(".")` in aitask_board.py). All other files use
`self._project_root` which is already a Path.

## Verification

### Syntax
```bash
python3 -m py_compile .aitask-scripts/board/aitask_board.py
python3 -m py_compile .aitask-scripts/codebrowser/codebrowser_app.py
python3 -m py_compile .aitask-scripts/codebrowser/history_screen.py
python3 -m py_compile .aitask-scripts/monitor/monitor_app.py
```

### End-to-end smoke test (all TUIs)

1. **`ait board` pick (task detail path)**
   - Open a task detail → press pick → dialog shows `Agent: claudecode/opus4_6` status row.
   - Press `a` → picker opens → pick `claudecode/sonnet4_6` → command Input updates.
   - Close dialog. Re-open pick on another task → `(U)se last: claudecode/sonnet4_6` button visible.
   - Press `u` → command refreshes to sonnet.

2. **`ait board` pick (action_pick_task keyboard path)**
   - Focus a task card, press the pick shortcut directly → same behavior as above.

3. **`ait codebrowser` explain**
   - Run explain on a source file → status row shows explain's default agent (e.g. `claudecode/sonnet4_6`).
   - Picker + use-last work.

4. **`ait codebrowser` history_screen qa**
   - Open history → run qa on a task → same behavior with qa's default.

5. **`ait monitor` pick**
   - Pick a task from monitor → same behavior.

6. **`ait board` create task — no regression**
   - Open create dialog → **no** agent row. Dialog behaves identically to before.

7. **No disk persistence**
   - Open `ait settings` → Agent Defaults tab → pick row still shows original global default (`claudecode/opus4_6`).
   - Quit all TUIs, restart `ait board`, open pick dialog → `(U)se last` button gone.

### Git sanity
```bash
./ait git status
```
Expected: 4 modified files (`aitask_board.py`, `codebrowser_app.py`, `history_screen.py`, `monitor_app.py`). No new files.

## Step 9 reference

Per task-workflow Step 9: after implementation + review, run
`./.aitask-scripts/aitask_archive.sh 521_3`. This is the last sibling, so
the archive script will auto-archive the parent t521 as well.
