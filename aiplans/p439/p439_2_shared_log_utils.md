---
Task: t439_2_shared_log_utils.md
Parent Task: aitasks/t439_agentcrew_logging.md
Sibling Tasks: aitasks/t439/t439_1_runner_log_capture.md, aitasks/t439/t439_3_dashboard_log_browser.md, aitasks/t439/t439_4_brainstorm_status_tab.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Plan: Shared Log Utilities

### Context
Both the AgentCrew dashboard TUI and brainstorm TUI need to list and read agent log files. Rather than duplicating code, create a shared module that both can import. Agent log files follow the naming convention `<agent>_log.txt` in the crew worktree root.

### New file: `.aitask-scripts/agentcrew/agentcrew_log_utils.py`

```python
"""Shared utilities for reading and listing agent log files.

Used by both agentcrew_dashboard.py and brainstorm_app.py to provide
log browsing functionality.
"""

from __future__ import annotations

import glob
import os
from datetime import datetime, timezone


def list_agent_logs(worktree: str) -> list[dict]:
    """List all agent log files in a crew worktree.

    Returns list of dicts sorted by mtime (most recent first):
        [{"name": "agent_name", "path": "/full/path/agent_log.txt",
          "size": 1234, "mtime": 1711234567.0,
          "mtime_str": "2026-03-23 14:30:00"}]
    """
    pattern = os.path.join(worktree, "*_log.txt")
    logs = []
    for path in glob.glob(pattern):
        basename = os.path.basename(path)
        # Strip _log.txt suffix to get agent name
        name = basename[:-8]  # len("_log.txt") == 8
        stat = os.stat(path)
        mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        logs.append({
            "name": name,
            "path": path,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "mtime_str": mtime_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })
    logs.sort(key=lambda x: x["mtime"], reverse=True)
    return logs


def read_log_tail(path: str, lines: int = 50) -> str:
    """Read last N lines of a log file.

    Returns empty string if file doesn't exist or is empty.
    """
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as f:
            # Seek from end for efficiency on large files
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return ""
            # Read up to 64KB from end (enough for ~50 lines)
            chunk_size = min(size, 65536)
            f.seek(-chunk_size, 2)
            data = f.read().decode("utf-8", errors="replace")
        result_lines = data.splitlines()
        if len(result_lines) > lines:
            result_lines = result_lines[-lines:]
        return "\n".join(result_lines)
    except OSError:
        return ""


def read_log_full(path: str, max_bytes: int = 500_000) -> str:
    """Read full log content, capped at max_bytes from the end.

    If file exceeds max_bytes, returns truncated content with a notice.
    """
    if not os.path.isfile(path):
        return ""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, 2)
                data = f.read().decode("utf-8", errors="replace")
                return f"... (truncated, showing last {format_log_size(max_bytes)})\n{data}"
            else:
                return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def format_log_size(size_bytes: int) -> str:
    """Format bytes as human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
```

### Verification
1. Import and test each function:
   ```python
   from agentcrew.agentcrew_log_utils import list_agent_logs, read_log_tail, read_log_full, format_log_size
   ```
2. `list_agent_logs()` on a worktree with log files → returns sorted list
3. `read_log_tail()` → returns last N lines
4. `read_log_full()` with a large file → truncation works
5. `format_log_size(1536)` → `"1.5 KB"`

### Step 9: Post-Implementation
Archive task, commit, push per standard workflow.
