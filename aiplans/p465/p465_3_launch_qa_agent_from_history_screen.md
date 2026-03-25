---
Task: t465_3_launch_qa_agent_from_history_screen.md
Parent Task: aitasks/t465_launch_qa_from_codebrowser.md
Sibling Tasks: aitasks/t465/t465_1_*.md, aitasks/t465/t465_2_*.md, aitasks/t465/t465_4_*.md
Archived Sibling Plans: aiplans/archived/p465/p465_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Add "launch QA" shortcut from history screen

## Step 1: Create agent_utils.py

File: `.aitask-scripts/codebrowser/agent_utils.py` (new)

Extract shared functions from `codebrowser_app.py`:

```python
"""Shared utilities for launching code agents from TUI screens."""

import os
import shutil
import subprocess
from pathlib import Path


def find_terminal() -> str | None:
    """Find an available terminal emulator, or return None."""
    terminal = os.environ.get("TERMINAL")
    if terminal and shutil.which(terminal):
        return terminal
    for term in [
        "alacritty", "kitty", "ghostty", "foot",
        "x-terminal-emulator", "xdg-terminal-exec", "gnome-terminal",
        "konsole", "xfce4-terminal", "lxterminal", "mate-terminal", "xterm",
    ]:
        if shutil.which(term):
            return term
    return None


def resolve_agent_binary(
    project_root: Path, operation: str
) -> tuple[str, str | None] | None:
    """Resolve agent name and binary for an operation.

    Returns (agent_name, binary) on success, None on failure.
    Sets resolve_error attribute on the returned tuple (not possible with plain tuple,
    so instead return None and caller handles error message).
    """
    codeagent = project_root / ".aitask-scripts" / "aitask_codeagent.sh"
    if not codeagent.exists():
        return None
    try:
        result = subprocess.run(
            [str(codeagent), "resolve", operation],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_root),
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "unavailable" in stderr.lower():
                msg = stderr.split("ERROR:")[-1].strip() if "ERROR:" in stderr else stderr
                return None  # caller can check stderr separately
            return None
        info = {}
        for line in result.stdout.strip().splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                info[key] = val
        binary = info.get("BINARY", "")
        agent = info.get("AGENT", "unknown")
        return (agent, binary) if binary else None
    except (subprocess.TimeoutExpired, OSError):
        return None
```

Note: Keep the error message handling simple. The `_resolve_error` pattern from codebrowser_app.py can stay in the app (it's UI state), while the utility function just returns None on failure.

## Step 2: Refactor codebrowser_app.py to use agent_utils

File: `.aitask-scripts/codebrowser/codebrowser_app.py`

- Add import: `from agent_utils import find_terminal, resolve_agent_binary`
- Replace `_find_terminal()` method body to delegate to `find_terminal()`
- Replace `_resolve_agent_binary()` method body to delegate to `resolve_agent_binary(self._project_root, operation)`, keeping the `_resolve_error` handling

Alternatively, inline the calls directly in `action_launch_agent()` and remove the methods. Keep it simple.

## Step 3: Add QA launch binding and action to HistoryScreen

File: `.aitask-scripts/codebrowser/history_screen.py`

Add to BINDINGS (after `l` binding):
```python
Binding("a", "launch_qa", "Launch QA"),
```

Add method:
```python
@work(exclusive=True)
async def action_launch_qa(self) -> None:
    """Launch QA agent for the currently viewed task."""
    try:
        detail = self.query_one("#history_detail", HistoryDetailPane)
    except Exception:
        return
    if not detail._nav_stack:
        self.notify("No task selected", severity="warning")
        return
    task_id = detail._nav_stack[-1]

    from agent_utils import find_terminal, resolve_agent_binary

    resolved = resolve_agent_binary(self._project_root, "qa")
    if not resolved:
        self.notify("Could not resolve QA agent configuration", severity="error")
        return
    agent_name, binary = resolved

    import shutil as _shutil
    if not _shutil.which(binary):
        self.notify(f"{agent_name} CLI ({binary}) not found in PATH", severity="error")
        return

    wrapper = str(self._project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    terminal = find_terminal()

    self.notify(f"Launching QA for t{task_id} via {agent_name}...")

    import subprocess
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

Also add import at top of file:
```python
from history_detail import HistoryDetailPane  # if not already imported
```

## Verification

- Open history, select task, press `a` → agent spawns in terminal
- Press `a` with no task → "No task selected" warning
- Existing `e` key in main screen still works after refactoring
- `ait codeagent --dry-run invoke qa 42` returns expected command (from t465_1)

## Step 9: Post-Implementation

Follow standard archival workflow.
