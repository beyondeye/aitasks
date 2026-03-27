---
priority: medium
effort: medium
depends: [t468_2]
issue_type: feature
status: Done
labels: [codebrowser, ui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-26 09:58
updated_at: 2026-03-27 15:46
completed_at: 2026-03-27 15:46
---

## Context

Child tasks 1-2 created shared components (`AgentCommandScreen`, `agent_launch_utils`) and migrated the board TUI to use them. This task adds the same launch modal to the codebrowser TUI for both explain and QA agent launches, which currently launch directly without any confirmation dialog.

## Key Files to Modify

1. **`.aitask-scripts/codebrowser/codebrowser_app.py`** — Main codebrowser TUI (explain launch)
2. **`.aitask-scripts/codebrowser/history_screen.py`** — History browsing screen (QA launch)

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_command_screen.py` — Shared `AgentCommandScreen` widget (created in t468_1)
- `.aitask-scripts/lib/agent_launch_utils.py` — Shared utilities (created in t468_1)
- `.aitask-scripts/board/aitask_board.py` — Board TUI using the shared components (migrated in t468_2) — reference for the push_screen + callback pattern
- `.aitask-scripts/codebrowser/agent_utils.py` — Existing `find_terminal()` and `resolve_agent_binary()` used by codebrowser
- `.aitask-scripts/codebrowser/codebrowser_app.py:647-683` — Current `action_launch_agent()` to refactor
- `.aitask-scripts/codebrowser/history_screen.py:255-292` — Current `action_launch_qa()` to refactor

## Implementation Plan

### Part A: Codebrowser Explain (codebrowser_app.py)

1. **Add imports** at the top of `codebrowser_app.py`:
   ```python
   import sys
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
   from agent_command_screen import AgentCommandScreen
   from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command
   ```
   Note: The file already has `from agent_utils import find_terminal, resolve_agent_binary` on line 18.

2. **Refactor `action_launch_agent()`** (lines 647-683):
   - Remove `@work(exclusive=True)` decorator and `async` keyword (push_screen must run on main thread)
   - Keep the validation logic: check `_current_file_path`, `resolve_agent_binary`, `shutil.which(binary)`
   - After validation, construct `arg` (rel_path or rel_path:line_start-line_end) as before
   - Call `resolve_dry_run_command(self._project_root, "explain", arg)` to get the full command
   - **If dry-run succeeds:** Show `AgentCommandScreen("Explain {rel_path}", full_cmd, "/aitask-explain {arg}")` with a callback that launches on `"run"`
   - **If dry-run fails (returns None):** Fall back to direct launch (current behavior), preserving backward compatibility
   - The callback on `"run"` does the terminal launch: find terminal, Popen or suspend+call

3. **Create a helper method `_run_agent_command()`** for the actual subprocess launch:
   ```python
   @work(exclusive=True)
   async def _run_agent_command(self, operation: str, arg: str) -> None:
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

### Part B: Codebrowser QA (history_screen.py)

1. **Add imports** at the top of `history_screen.py`:
   ```python
   import sys
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
   from agent_command_screen import AgentCommandScreen
   from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command
   ```

2. **Refactor `action_launch_qa()`** (lines 255-292):
   - Remove `@work(exclusive=True)` decorator and `async` keyword
   - Keep validation: check `detail._nav_stack`, `resolve_agent_binary`, `shutil.which(binary)`
   - Call `resolve_dry_run_command(self._project_root, "qa", task_id)`
   - **If dry-run succeeds:** Show `AgentCommandScreen("QA for t{task_id}", full_cmd, "/aitask-qa {task_id}")` with callback
   - **If dry-run fails:** Fall back to direct launch
   - Create `_run_qa_command()` helper (or a generic `_run_agent_command()`) for the subprocess launch

3. **Update `agent_utils.py` import in history_screen.py** (line 267):
   - The lazy import `from agent_utils import find_terminal, resolve_agent_binary` can stay since `resolve_agent_binary` is still needed from there
   - The `find_terminal` from agent_utils is no longer needed in the launch path (replaced by `_find_terminal` from lib)

## Verification Steps

1. Run `ait codebrowser` — verify it starts without import errors
2. Select a file, press `e` — verify modal appears with "Explain path/to/file" title, showing full command and prompt
3. Select text range, press `e` — verify modal shows line range in title
4. Press `c` to copy command, `p` to copy prompt, `r` to run — verify all work
5. Press escape — verify modal closes without launching
6. Navigate to history screen, select a task, press `a` — verify modal appears with "QA for tN" title
7. Test fallback: if `--dry-run` somehow fails, verify explain and QA still launch directly
