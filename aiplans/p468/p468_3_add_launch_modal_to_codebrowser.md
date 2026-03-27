---
Task: t468_3_add_launch_modal_to_codebrowser.md
Parent Task: aitasks/t468_better_codeagent_launching.md
Sibling Tasks: aitasks/t468/t468_1_shared_agent_command_screen_and_utils.md, aitasks/t468/t468_2_migrate_board_to_shared_components.md
Archived Sibling Plans: aiplans/archived/p468/p468_1_*.md, aiplans/archived/p468/p468_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Add Launch Modal to Codebrowser Explain and QA

## Overview

Add the `AgentCommandScreen` modal to the codebrowser TUI's explain and QA agent launches, replacing the current direct-launch pattern with the same modal dialog used by the board.

## Files to modify

1. `.aitask-scripts/codebrowser/codebrowser_app.py` — Explain launch
2. `.aitask-scripts/codebrowser/history_screen.py` — QA launch

## Part A: Codebrowser Explain (`codebrowser_app.py`)

### Step 1: Add lib path and imports

Near the top, after existing imports (around line 8):

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from agent_command_screen import AgentCommandScreen
from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command
```

Note: `sys` is already imported. The existing `from agent_utils import find_terminal, resolve_agent_binary` on line 18 stays — `resolve_agent_binary` is still needed for validation.

### Step 2: Refactor `action_launch_agent()` (lines 647-683)

Remove `@work(exclusive=True)` decorator and `async` keyword. The method now shows a modal (must be on main thread).

New logic:
1. Keep validation: check `_current_file_path`, call `resolve_agent_binary`, check `shutil.which(binary)`
2. Construct `arg` as before (rel_path or rel_path:line_start-line_end)
3. Call `resolve_dry_run_command(self._project_root, "explain", arg)`
4. If dry-run succeeds: construct title and show `AgentCommandScreen`
5. If dry-run fails: fall back to direct launch (current behavior)

```python
def action_launch_agent(self) -> None:
    """Launch the configured code agent with the explain skill for the current file."""
    if not self._current_file_path:
        self.notify("No file selected", severity="warning")
        return

    agent_name, binary, error_msg = resolve_agent_binary(self._project_root, "explain")
    if not binary:
        self.notify(error_msg or "Could not resolve code agent configuration", severity="error")
        return
    if not shutil.which(binary):
        self.notify(f"{agent_name} CLI ({binary}) not found in PATH", severity="error")
        return

    rel_path = self._current_file_path.relative_to(self._project_root)
    code_viewer = self.query_one("#code_viewer", CodeViewer)
    selected = code_viewer.get_selected_range()

    if selected:
        arg = f"{rel_path}:{selected[0]}-{selected[1]}"
        title = f"Explain {rel_path} (lines {selected[0]}-{selected[1]})"
    else:
        arg = str(rel_path)
        title = f"Explain {rel_path}"

    full_cmd = resolve_dry_run_command(self._project_root, "explain", arg)
    if full_cmd:
        prompt_str = f"/aitask-explain {arg}"
        def on_result(result):
            if result == "run":
                self._run_agent_command("explain", arg)
        self.push_screen(
            AgentCommandScreen(title, full_cmd, prompt_str),
            on_result,
        )
    else:
        # Fallback: direct launch without modal
        self._run_agent_command("explain", arg)
```

### Step 3: Create `_run_agent_command()` helper

Extracted from the current subprocess launch logic:

```python
@work(exclusive=True)
async def _run_agent_command(self, operation: str, arg: str) -> None:
    """Launch code agent in a terminal or inline."""
    wrapper = str(self._project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    terminal = _find_terminal()
    if terminal:
        subprocess.Popen([terminal, "--", wrapper, "invoke", operation, arg],
                         cwd=str(self._project_root))
    else:
        with self.suspend():
            subprocess.call([wrapper, "invoke", operation, arg],
                            cwd=str(self._project_root))
```

## Part B: Codebrowser QA (`history_screen.py`)

### Step 1: Add lib path and imports

Near the top of `history_screen.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from agent_command_screen import AgentCommandScreen
from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command
```

Check what's already imported — `sys`, `Path`, `shutil`, `subprocess` may already be present.

### Step 2: Refactor `action_launch_qa()` (lines 255-292)

Remove `@work(exclusive=True)` and `async`. Same pattern as explain:

```python
def action_launch_qa(self) -> None:
    """Launch QA agent for the currently viewed task."""
    try:
        detail = self.query_one("#history_detail", HistoryDetailPane)
    except Exception:
        return
    if not detail._nav_stack:
        self.notify("No task selected", severity="warning")
        return
    task_id = detail._nav_stack[-1]

    from agent_utils import resolve_agent_binary

    agent_name, binary, error_msg = resolve_agent_binary(self._project_root, "qa")
    if not binary:
        self.notify(error_msg or "Could not resolve QA agent configuration", severity="error")
        return
    if not shutil.which(binary):
        self.notify(f"{agent_name} CLI ({binary}) not found in PATH", severity="error")
        return

    full_cmd = resolve_dry_run_command(self._project_root, "qa", task_id)
    if full_cmd:
        prompt_str = f"/aitask-qa {task_id}"
        def on_result(result):
            if result == "run":
                self._run_qa_command(task_id)
        self.push_screen(
            AgentCommandScreen(f"QA for t{task_id}", full_cmd, prompt_str),
            on_result,
        )
    else:
        self._run_qa_command(task_id)
```

### Step 3: Create `_run_qa_command()` helper

```python
@work(exclusive=True)
async def _run_qa_command(self, task_id: str) -> None:
    """Launch QA agent in a terminal or inline."""
    wrapper = str(self._project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    terminal = _find_terminal()
    if terminal:
        subprocess.Popen(
            [terminal, "--", wrapper, "invoke", "qa", task_id],
            cwd=str(self._project_root),
        )
    else:
        with self.app.suspend():
            subprocess.call(
                [wrapper, "invoke", "qa", task_id],
                cwd=str(self._project_root),
            )
```

Note: history_screen uses `self.app.suspend()` (not `self.suspend()`) since it's a Screen, not the App.

## Verification

1. `ait codebrowser` starts without import errors
2. Select file → `e` → modal shows "Explain path/to/file" with full command and prompt
3. Select range → `e` → modal shows line range
4. `c` copies command, `p` copies prompt, `r` launches, `escape` cancels
5. History screen → select task → `a` → modal shows "QA for tN"
6. Fallback: if dry-run fails, explain/QA launch directly without modal

## Final Implementation Notes

- **Actual work done:** Implemented the plan as written, plus two additions not in the original plan: (1) escape key handling via a priority escape binding on `CodeBrowserApp` with delegation to `handle_escape()`, and (2) `TmuxLaunchConfig` handling in the callback (run-in-tmux support alongside direct run).
- **Deviations from plan:** The plan didn't account for the escape handling protocol required by `AgentCommandScreen` (which has no escape binding itself — the host app must delegate). Added `action_handle_escape_key()` on `CodeBrowserApp` with priority escape binding. Also added `TmuxLaunchConfig` and `launch_in_tmux` imports/handling to match the board's callback pattern (the plan only mentioned `"run"` result, not tmux).
- **Issues encountered:** None — the shared components from t468_1/t468_2 worked as expected.
- **Key decisions:** Used `self.app.push_screen()` in HistoryScreen (not `self.push_screen()`) to push `AgentCommandScreen` onto the App's screen stack, ensuring the App-level escape binding intercepts it. The escape handler also handles `GoToLineScreen` (ModalScreen fallback) and `HistoryScreen` (via `action_dismiss_screen`).
- **Notes for sibling tasks:** The `action_handle_escape_key` on `CodeBrowserApp` now handles escape for any screen with `handle_escape()`, any ModalScreen (dismiss with None), or any screen with `action_dismiss_screen`. Future modal screens pushed in the codebrowser will automatically benefit. The `_find_terminal` alias (from `agent_launch_utils`) avoids shadowing the existing `agent_utils.find_terminal`.
