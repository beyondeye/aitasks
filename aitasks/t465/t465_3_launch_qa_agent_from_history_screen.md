---
priority: medium
effort: medium
depends: [t465_1]
issue_type: feature
status: Ready
labels: [codebrowser, qa]
created_at: 2026-03-25 12:57
updated_at: 2026-03-25 12:57
---

## Context

The codebrowser main screen has `e` to launch `/aitask-explain` for the current file. The history screen needs an analogous feature: pressing `a` to launch `/aitask-qa` for the currently selected completed task. This lets users run QA analysis on any completed task directly from the history browser.

Depends on t465_1 (which adds "qa" as a supported codeagent operation).

## Key Files to Modify

- `.aitask-scripts/codebrowser/agent_utils.py` — **New file**: extract `find_terminal()` and `resolve_agent_binary(project_root, operation)` as module-level functions from codebrowser_app.py
- `.aitask-scripts/codebrowser/codebrowser_app.py` — Refactor `_find_terminal()` and `_resolve_agent_binary()` methods to use shared `agent_utils` functions, simplify `action_launch_agent()`
- `.aitask-scripts/codebrowser/history_screen.py` — Add `Binding("a", "launch_qa", "Launch QA")` and `action_launch_qa()` async worker method

## Reference Files for Patterns

- `codebrowser_app.py` lines 596-637: `_find_terminal()` and `_resolve_agent_binary()` — extract these into `agent_utils.py`
- `codebrowser_app.py` lines 639-678: `action_launch_agent()` — the QA launch action follows the exact same pattern (resolve agent, check binary, find terminal, spawn in terminal or suspend)
- `history_detail.py` line 592: `HistoryDetailPane._nav_stack` — the current task_id is `detail._nav_stack[-1]`

## Implementation Plan

1. Create `.aitask-scripts/codebrowser/agent_utils.py` with:
   - `find_terminal() -> str | None` — extracted from `CodeBrowserApp._find_terminal()`
   - `resolve_agent_binary(project_root: Path, operation: str) -> tuple[str, str] | tuple[None, str | None]` — extracted from `CodeBrowserApp._resolve_agent_binary()`
2. Refactor `codebrowser_app.py`:
   - Import `find_terminal, resolve_agent_binary` from `agent_utils`
   - Replace `_find_terminal` and `_resolve_agent_binary` methods with thin wrappers or direct calls in `action_launch_agent()`
   - Keep `_resolve_error` handling pattern
3. Add to `history_screen.py`:
   - Add `Binding("a", "launch_qa", "Launch QA")` to BINDINGS
   - Add `action_launch_qa()` as `@work(exclusive=True)` async method:
     - Get current task_id from `detail._nav_stack[-1]`
     - If no task selected, show warning notification
     - Call `resolve_agent_binary(self._project_root, "qa")`
     - Check binary exists with `shutil.which()`
     - Build wrapper path: `self._project_root / ".aitask-scripts" / "aitask_codeagent.sh"`
     - Spawn in terminal: `subprocess.Popen([terminal, "--", wrapper, "invoke", "qa", task_id])`
     - Fallback: `self.app.suspend()` + `subprocess.call([wrapper, "invoke", "qa", task_id])`

## Edge Cases
- No task selected in detail pane — show "No task selected" notification
- QA agent binary not found — show error notification with agent name
- No terminal available — use suspend mode (same as explain does)
- "qa" operation not configured (if t465_1 not done) — resolve will fail gracefully with error notification

## Verification Steps

- Open history screen, select a completed task, press `a` — should spawn QA agent in terminal
- Press `a` with no task selected — should show warning notification
- Verify existing `e` key still works in main screen after refactoring
