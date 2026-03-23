---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 12:53
updated_at: 2026-03-23 14:27
---

## Shared log utilities module for TUI log browsing

### Context
Both the AgentCrew dashboard TUI and brainstorm TUI need to list and read agent log files (`<agent>_log.txt`). This task creates a shared utilities module that both TUIs import. Depends on t439_1 (runner log capture) being implemented so log files actually exist.

### Key Files to Create
- `.aitask-scripts/agentcrew/agentcrew_log_utils.py` — **New file**

### Reference Files for Patterns
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — Existing shared utilities pattern (read_yaml, list_agent_files, etc.)
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` lines 80-91 — `_read_file_preview()` for similar file reading pattern

### Implementation Plan

Create `.aitask-scripts/agentcrew/agentcrew_log_utils.py` with these functions:

#### 1. `list_agent_logs(worktree: str) -> list[dict]`
- Glob for `*_log.txt` files in the worktree directory
- For each file, extract agent name (strip `_log.txt` suffix)
- Return list of dicts sorted by mtime (most recent first):
  ```python
  {"name": "agent_name", "path": "/full/path", "size": 1234,
   "mtime": 1711234567.0, "mtime_str": "2026-03-23 14:30:00"}
  ```
- Use `os.stat()` for size and mtime

#### 2. `read_log_tail(path: str, lines: int = 50) -> str`
- Read last N lines of a log file efficiently
- Use a seek-from-end approach for large files
- Return empty string if file doesn't exist

#### 3. `read_log_full(path: str, max_bytes: int = 500_000) -> str`
- Read full log content, capped at max_bytes from the end
- If file exceeds max_bytes, prefix with `"... (truncated, showing last {max_bytes} bytes)\n"`

#### 4. `format_log_size(size_bytes: int) -> str`
- Format bytes as human-readable: `"12.3 KB"`, `"1.5 MB"`, `"256 B"`

### Verification Steps
1. Import the module and call `list_agent_logs()` on a crew worktree that has log files from t439_1
2. Verify logs are sorted by mtime, newest first
3. Verify `read_log_tail()` returns correct last N lines
4. Verify `read_log_full()` truncation works for large content
5. Test `format_log_size()` with various byte counts
