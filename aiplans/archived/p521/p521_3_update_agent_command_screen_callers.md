---
Task: t521_3_update_agent_command_screen_callers.md
Parent Task: aitasks/t521_change_default_codeagent_at_run_time.md
Sibling Tasks: aitasks/t521/t521_1_extract_agent_model_picker_to_lib.md, aitasks/t521/t521_2_wire_agent_picker_into_launch_dialog.md
Archived Sibling Plans: aiplans/archived/p521/p521_1_extract_agent_model_picker_to_lib.md, aiplans/archived/p521/p521_2_wire_agent_picker_into_launch_dialog.md
Worktree: (none — working on current branch per fast profile)
Branch: main
Base branch: main
---

# p521_3 — Update AgentCommandScreen callers to pass operation + agent override hooks

## Context

Third and final step of t521. Sibling t521_2 added per-run agent/model
picker hooks to the shared launch dialog `AgentCommandScreen` behind new
optional constructor params (`project_root`, `operation`, `operation_args`,
`default_agent_string`) and introduced a `resolve_agent_string(project_root,
operation)` helper in `agent_launch_utils.py`. This task threads those
params through every **code-agent** call site so the picker becomes usable
from the board, codebrowser, and monitor TUIs.

**Depends on:** t521_1 (lib/agent_model_picker.py) and t521_2
(AgentCommandScreen param additions, `resolve_agent_string`).

## Plan verification findings (vs. original draft)

Plan was verified at task pick time (2026-04-12). Findings:

- `AgentCommandScreen.__init__` signature confirmed at
  `.aitask-scripts/lib/agent_command_screen.py:193–203`.
- `resolve_agent_string` confirmed at
  `.aitask-scripts/lib/agent_launch_utils.py:90–109`.
- 5 actual `AgentCommandScreen(` call sites exist in the codebase:
  - `aitask_board.py:3331` — TaskDetailScreen pick callback (UPDATE)
  - `aitask_board.py:3413` — `action_pick_task` (UPDATE)
  - `aitask_board.py:3443` — `_launch_brainstorm` (**LEAVE UNCHANGED** —
    brainstorm is not a code-agent operation; agent row hidden)
  - `aitask_board.py:3597` — `action_create_task` (**LEAVE UNCHANGED** per
    original plan)
  - `codebrowser_app.py:693` — explain (UPDATE)
  - `history_screen.py:284` — qa (UPDATE)
- **monitor_app.py:978 has NO `AgentCommandScreen` call.** The next-sibling
  pick flow currently resolves the dry-run command and launches directly via
  `launch_in_tmux`, bypassing the launch dialog entirely. Per user direction,
  this task **inserts** a new `AgentCommandScreen` modal wrapping the
  launch, mirroring the board pick pattern.

Net scope: **4 updates to existing call sites + 1 new dialog insertion in
monitor** + import additions in 4 files.

## Files to Modify

| File | What changes |
|------|--------------|
| `.aitask-scripts/board/aitask_board.py` | Extend agent_launch_utils import with `resolve_agent_string`; update 2 pick call sites (3331, 3413). Leave 3443 (brainstorm) and 3597 (create_task) unchanged. |
| `.aitask-scripts/codebrowser/codebrowser_app.py` | Extend agent_launch_utils import; update explain call site (693). |
| `.aitask-scripts/codebrowser/history_screen.py` | Extend agent_launch_utils import; update qa call site (284). |
| `.aitask-scripts/monitor/monitor_app.py` | Add `from agent_command_screen import AgentCommandScreen`; extend agent_launch_utils import; refactor `_on_next_sibling_result` to push a launch dialog instead of launching directly. |

All four files already import `from pathlib import Path`.

## Implementation Steps

### 1. `board/aitask_board.py` — two pick call sites

Extend the existing `agent_launch_utils` import (line 16) to add
`resolve_agent_string`:

```python
from agent_launch_utils import (
    find_terminal,
    find_window_by_name,
    resolve_dry_run_command,
    resolve_agent_string,
    TmuxLaunchConfig,
    launch_in_tmux,
    maybe_spawn_minimonitor,
)
```

At **line 3331** (TaskDetailScreen pick callback), replace:

```python
screen = AgentCommandScreen(f"Pick Task t{num}", full_cmd, prompt_str, default_window_name=f"agent-pick-{num}")
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

At **line 3413** (`action_pick_task`), apply the same transformation
(identical local variables: `num`, `full_cmd`, `prompt_str`).

**Do NOT touch** the brainstorm call site at line 3443 or the create_task
site at 3597 — both are non-codeagent and should keep the agent row hidden
(`operation=None`).

### 2. `codebrowser/codebrowser_app.py` — explain

Extend the import (line 13):

```python
from agent_launch_utils import (
    find_terminal as _find_terminal,
    resolve_dry_run_command,
    resolve_agent_string,
    TmuxLaunchConfig,
    launch_in_tmux,
    maybe_spawn_minimonitor,
)
```

At **line 693** replace the one-line call with:

```python
agent_string = resolve_agent_string(self._project_root, "explain")
screen = AgentCommandScreen(
    title, full_cmd, prompt_str,
    default_window_name=f"agent-explain-{rel_path.name}",
    project_root=self._project_root,
    operation="explain",
    operation_args=[arg],
    default_agent_string=agent_string,
)
```

`arg` is the exact value already passed to
`resolve_dry_run_command(self._project_root, "explain", arg)` at line 690
— copy it, do not re-derive.

### 3. `codebrowser/history_screen.py` — qa

Extend the import (line 11) with `resolve_agent_string`. At **line 284**:

```python
agent_string = resolve_agent_string(self._project_root, "qa")
screen = AgentCommandScreen(
    f"QA for t{task_id}", full_cmd, prompt_str,
    default_window_name=f"agent-qa-{task_id}",
    project_root=self._project_root,
    operation="qa",
    operation_args=[task_id],
    default_agent_string=agent_string,
)
```

### 4. `monitor/monitor_app.py` — insert launch dialog around direct launch

Current code at lines 977–1006 resolves the dry-run command and immediately
launches via `launch_in_tmux`. Refactor to show the `AgentCommandScreen`
dialog first and move the tmux launch into the screen callback (mirroring
the board pick pattern).

**Import additions.** Extend the `from agent_launch_utils import ...`
at line 38 with `resolve_agent_string`, and add an
`AgentCommandScreen` import:

```python
from agent_launch_utils import (
    resolve_dry_run_command,
    resolve_agent_string,
    TmuxLaunchConfig,
    launch_in_tmux,
    maybe_spawn_minimonitor,
)  # noqa: E402
from agent_command_screen import AgentCommandScreen  # noqa: E402
```

`sys.path` already contains `_SCRIPT_DIR / "lib"` (line 22), so the
`agent_command_screen` module resolves without further setup.

**Refactor `_on_next_sibling_result`** (lines 960–1006). Existing
side-effects — killing the old pane when appropriate, spawning the
minimonitor after launch — must be preserved. Replace the direct-launch
block starting at line 977 with:

```python
# Resolve pick command: specific child or parent for selection
full_cmd = resolve_dry_run_command(self._project_root, "pick", target_id)
if not full_cmd:
    self.notify(f"Failed to resolve pick command for t{target_id}", severity="error")
    return

# Kill current pane if task is Done, archived (info is None), or a
# parent task whose implementation has moved to its children.
is_parent_with_children = "_" not in task_id
if is_parent_with_children or not current_info or current_info.status == "Done":
    old_name = snap.pane.window_name
    self._monitor.kill_pane(pane_id)
    self._focused_pane_id = None
    self.notify(f"Killed {old_name}")

prompt_str = f"/aitask-pick {target_id}"
window_name = f"agent-pick-{target_id}"
agent_string = resolve_agent_string(self._project_root, "pick")
screen = AgentCommandScreen(
    f"Pick Task t{target_id}", full_cmd, prompt_str,
    default_window_name=window_name,
    project_root=self._project_root,
    operation="pick",
    operation_args=[target_id],
    default_agent_string=agent_string,
)

def on_pick_result(pick_result):
    if isinstance(pick_result, TmuxLaunchConfig):
        _, err = launch_in_tmux(screen.full_command, pick_result)
        if err:
            self.notify(f"Launch failed: {err}", severity="error")
            return
        if pick_result.new_window:
            maybe_spawn_minimonitor(pick_result.session, pick_result.window)
        self.notify(f"Launched agent for t{target_id}")
    self.call_later(self._refresh_data)

self.push_screen(screen, on_pick_result)
```

Notes on the refactor:
- The pane-kill step stays **before** pushing the dialog so the old pane
  is gone whether or not the user confirms launch (matches current UX).
- The hardcoded tmux config construction disappears — the dialog now
  collects session/window/new_window choices and returns a
  `TmuxLaunchConfig`, same as the board pick flow.
- `self.call_later(self._refresh_data)` runs for every dialog outcome
  (launch, cancel, or run-in-current-terminal).
- "Run in current terminal" (`pick_result == "run"`) is unsupported in
  monitor: the dialog accepts the fall-through but only tmux launches
  actually do anything. Existing monitor code had no such path, so this
  preserves behaviour.

### 5. Verify `Path` availability

Already-imported in all four files. No changes needed.

## Verification

### Syntax
```bash
python3 -m py_compile .aitask-scripts/board/aitask_board.py
python3 -m py_compile .aitask-scripts/codebrowser/codebrowser_app.py
python3 -m py_compile .aitask-scripts/codebrowser/history_screen.py
python3 -m py_compile .aitask-scripts/monitor/monitor_app.py
```

### Grep confirmation

After edits, `grep -n "AgentCommandScreen(" .aitask-scripts/**/*.py`
should show 6 constructions (5 existing + 1 new monitor), and
`grep -n "resolve_agent_string" .aitask-scripts/**/*.py` should show 5
call sites (2 board pick + explain + qa + monitor pick).

### End-to-end smoke test

1. **`ait board` pick (task detail path)** — Open a task detail → press
   pick. Dialog shows `Agent: claudecode/opus4_6` status row. Press `a`
   → picker opens → pick `claudecode/sonnet4_6` → command Input updates.
   Close. Re-open pick on another task → `(U)se last: claudecode/sonnet4_6`
   button visible. Press `u` → command refreshes.
2. **`ait board` pick (`action_pick_task` keyboard)** — Same behavior.
3. **`ait board` brainstorm** — Open brainstorm dialog. **No agent row
   shown.** Regression check.
4. **`ait board` create task** — Open create dialog. **No agent row
   shown.** Regression check.
5. **`ait codebrowser` explain** — Run explain on a source file → status
   row with explain's default agent. Picker + use-last work.
6. **`ait codebrowser` history qa** — Open history → run qa on a task →
   status row with qa's default. Picker + use-last work.
7. **`ait monitor` next-sibling pick** — Trigger next-sibling. The new
   launch dialog appears (UX change — previously launched directly).
   Status row shows current agent. Press `a` → pick a model → command
   updates. Select a tmux session/window → launch. Verify new pane
   appears with the correct agent and minimonitor spawns.
8. **No disk persistence** — Open `ait settings` → Agent Defaults tab →
   pick row still shows the original global default. Quit all TUIs and
   restart `ait board` → `(U)se last` button gone.

### Git sanity
```bash
./ait git status
```
Expected: 4 modified files (`aitask_board.py`, `codebrowser_app.py`,
`history_screen.py`, `monitor_app.py`). No new files.

## Step 9 reference

Per task-workflow Step 9: after implementation + review, run
`./.aitask-scripts/aitask_archive.sh 521_3`. This is the last sibling of
t521, so the archive script will auto-archive the parent t521.

## Final Implementation Notes

- **Actual work done:** Extended the `agent_launch_utils` import with
  `resolve_agent_string` in 4 files. Threaded `project_root`, `operation`,
  `operation_args`, `default_agent_string` through 4 existing
  `AgentCommandScreen` call sites (2 pick in `aitask_board.py`, explain
  in `codebrowser_app.py`, qa in `history_screen.py`). For `monitor_app.py`
  — which previously launched directly via `launch_in_tmux` with no
  dialog — added a new `AgentCommandScreen` modal wrapper around the
  next-sibling pick flow, moving the tmux launch into the screen
  callback. Also applied a small CSS touch-up to
  `lib/agent_command_screen.py` to vertically center the agent row
  label against the (A)gent button (originally shipped with t521_2).
- **Deviations from plan:** Original draft plan claimed 6
  `AgentCommandScreen` call sites including one in `monitor_app.py` at
  line 978. Verification at pick time showed zero uses of
  `AgentCommandScreen` in monitor — it launched tmux directly. Per user
  direction during plan verification, the monitor change became a
  dialog **insertion** (not a thread-through), mirroring the board pick
  pattern. A second small deviation: the plan did not explicitly list
  the brainstorm call site at `aitask_board.py:3443`, which was left
  unchanged because brainstorm is not a code-agent operation and the
  agent row should stay hidden.
- **Issues encountered:** None technical. One small UX issue surfaced
  during user review (agent label vertically misaligned with button),
  fixed in the same commit (see Post-Review Changes below).
- **Key decisions:**
  - For monitor, the pane-kill step stays **before** pushing the
    dialog so the old pane is gone whether or not the user confirms
    launch — preserves current UX.
  - `pick_result == "run"` (run-in-current-terminal) is not supported
    in monitor's dialog callback since the previous direct-launch
    flow had no equivalent path.
  - For `aitask_board.py` call sites, used `Path(".")` for
    `project_root` (no `self._project_root` available), matching how
    existing `resolve_dry_run_command` calls work in that file.
- **Notes for sibling tasks:** This was the last sibling of t521 —
  parent will be auto-archived. Pattern for threading the picker
  through any future TUI that launches code agents: extend the
  `agent_launch_utils` import with `resolve_agent_string`, pass
  `operation`, `operation_args`, `project_root`, and
  `default_agent_string` to `AgentCommandScreen(...)`, and keep the
  existing tmux launch callback unchanged — the dialog handles
  everything. For TUIs that don't currently use the dialog (like
  monitor did), wrap the launch in a dialog and move the tmux call
  into the `on_pick_result` callback.

## Post-Review Changes

### Change Request 1 (2026-04-12 12:xx)
- **Requested by user:** Style fix — the single-line `Agent:` label in
  the dialog's agent row was top-aligned, while the `(A)gent` button
  occupies 3 rows. Label should be vertically centered against the
  button.
- **Changes made:** Updated `#agent_row Label` CSS in
  `.aitask-scripts/lib/agent_command_screen.py` to add `height: 3` and
  `content-align: left middle` so the label spans the row and centers
  its text vertically. This is a cross-task touch-up on t521_2's CSS,
  noted here because the issue was surfaced while reviewing t521_3.
- **Files affected:** `.aitask-scripts/lib/agent_command_screen.py`
