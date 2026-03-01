---
priority: high
effort: medium
depends: [268_1, 268_4]
issue_type: feature
status: Ready
labels: [modelwrapper, board, codebrowser]
created_at: 2026-03-01 09:00
updated_at: 2026-03-01 09:00
---

## Context

This is child task 5 of t268 (Code Agent Wrapper). It replaces hardcoded `"claude"` CLI calls in board and codebrowser TUIs with `aitask_codeagent.sh invoke` calls, making both TUIs agent-agnostic.

## Key Files

- **Modify:** `aiscripts/board/aitask_board.py` (`run_aitask_pick` method, ~lines 2750-2753)
- **Modify:** `aiscripts/codebrowser/codebrowser_app.py` (`action_launch_claude`, ~lines 481-503)
- **Create:** `seed/codebrowser_config.json`

## Implementation Plan

### 1. Board TUI — replace hardcoded claude calls

In `aitask_board.py` around lines 2750, 2753:

**Before:**
```python
["claude", f"/aitask-pick {num}"]
```

**After:**
```python
["./aiscripts/aitask_codeagent.sh", "invoke", "task-pick", str(num)]
```

If a model is configured in board settings, pass `--agent-string` flag:
```python
cmd = ["./aiscripts/aitask_codeagent.sh"]
if agent_string:
    cmd += ["--agent-string", agent_string]
cmd += ["invoke", "task-pick", str(num)]
```

### 2. Codebrowser TUI — replace hardcoded claude calls

In `codebrowser_app.py` around lines 481-503:

- Replace `shutil.which("claude")` check with checking script existence
- Replace `["claude", f"/aitask-explain {arg}"]` with `["./aiscripts/aitask_codeagent.sh", "invoke", "explain", arg]`
- Pass `--agent-string` if configured
- Rename `action_launch_claude` → `action_launch_agent`

### 3. Create codebrowser config pair

Create `seed/codebrowser_config.json` using common config library pattern:
```json
{
  "default_agent": null
}
```

Per-user overrides go to `codebrowser_config.local.json` (gitignored).

## Verification Steps

1. Board TUI "pick" action invokes via wrapper (manual test)
2. Codebrowser TUI "explain" action invokes via wrapper (manual test)
3. Agent string from config is passed to wrapper when configured
4. TUIs work correctly with default config (no agent string override)
5. No hardcoded `"claude"` references remain in board or codebrowser code
