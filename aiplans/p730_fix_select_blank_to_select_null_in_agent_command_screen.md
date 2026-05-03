---
Task: t730_fix_select_blank_to_select_null_in_agent_command_screen.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Replace `Select.BLANK` with `Select.NULL` in `agent_command_screen.py`

## Context

`ait board` crashes when launching the pick-command dialog (and any other AgentCommandScreen flow) on the path where no live tmux session matches the project's defaults / last-used. The crash is `InvalidSelectValueError: Illegal select value False.` raised inside textual's `Select._validate_value` for widget `#tmux_window_select`.

Root cause: `.aitask-scripts/lib/agent_command_screen.py` uses `Select.BLANK` as the unselected-state sentinel in 5 places. In current textual (verified on both 8.1.1 in `~/.aitask/venv` and 8.2.5 in `~/.aitask/pypy_venv`) `Select` no longer defines `BLANK`. The attribute resolves via MRO to `Widget.BLANK: ClassVar[bool] = False` (an unrelated CSS-ish flag). So `Select.BLANK` is the bool `False`. The current unselected sentinel is `Select.NULL` (a `NoSelection()` instance).

The crash fires when `pick_initial_session` returns `_NEW_SESSION_SENTINEL` → `compose` enters the `else` at line 362 → `win_value = Select.BLANK` (line 364) → `Select(value=False, ...)` (line 369) → on mount, textual's `_validate_value(False)` rejects it because `False not in self._legal_values`. Reproduced under CPython textual 8.1.1 with a minimal `Select([("a","a")], value=Select.BLANK, allow_blank=True)` test inside `App.run_test` — confirms this is **not** PyPy-related; the user noticed it after a tmux state change made the new-session branch reachable.

The four guard sites (482, 505, 762, 783) using `value != Select.BLANK` are latent wrong-behavior bugs even without a crash: comparing real string sentinels (or a hypothetical `Select.NULL`) against `False` mis-classifies "no selection" as "has selection". Fixing all five sites together restores correct semantics.

Intended outcome: `ait board` opens the pick dialog cleanly even with no live tmux session matching defaults, and the four guards correctly recognize `Select.NULL` as "unselected".

## Critical file

- `/home/ddt/Work/aitasks/.aitask-scripts/lib/agent_command_screen.py`
  - `Select` already imported at line 38 (`from textual.widgets import ... Select ...`); `Select.NULL` resolves with no extra import needed.

## Implementation

Replace `Select.BLANK` with `Select.NULL` at all 5 occurrences in `agent_command_screen.py`. Use `Edit` with `replace_all=True` (the literal `Select.BLANK` does not occur elsewhere in the codebase — verified).

| Line | Function | Before | After |
|------|----------|--------|-------|
| 364  | `_populate_tmux_tab` | `win_value = Select.BLANK` | `win_value = Select.NULL` |
| 482  | `_on_window_changed` | `elif value and value != Select.BLANK:` | `elif value and value != Select.NULL:` |
| 505  | `on_session_changed` | `elif value and value != Select.BLANK:` | `elif value and value != Select.NULL:` |
| 762  | `_get_tmux_launch_config` (session) | `elif sess_select.value and sess_select.value != Select.BLANK:` | `elif sess_select.value and sess_select.value != Select.NULL:` |
| 783  | `_get_tmux_launch_config` (window) | `elif win_select and win_select.value and win_select.value != Select.BLANK:` | `elif win_select and win_select.value and win_select.value != Select.NULL:` |

No other files need changes. Cross-TUI audit confirms the blast radius is contained:

- `grep -rn 'Select\.BLANK' .aitask-scripts/` → only the 5 sites listed above; no other file in the tree references the broken sentinel.
- `grep -rn 'Select(' .aitask-scripts/` → only **two** real `textual.widgets.Select(...)` constructions exist in the entire framework: lines 342 and 369 of `agent_command_screen.py`. Line 342 receives `value=initial_session` from `pick_initial_session()`, which always returns a string — no falsy-value risk. Line 369 is the one being fixed. (The settings TUI uses a custom `FuzzySelect(Container)` class — not `textual.widgets.Select`, no `BLANK`/`NULL` semantics.)
- `grep -rn 'select\.value\|Select.NULL\|NoSelection' .aitask-scripts/` (excluding the file under fix) → no hits. No other code in the framework reads a `Select`'s value or compares against `NoSelection`.
- Sibling private textual imports used by the framework (`SelectOverlay`, `DirEntry`, `FooterKey/Label`, `KeyGroup`) still resolve in both installed textual versions (8.1.1, 8.2.5) — verified by import probe. No other obsolete-textual-API drift surfaces in this audit.

Conclusion: `agent_command_screen.py` is the only file in the framework affected by this `Select.BLANK` API drift — fixing the 5 sites listed completes the work.

## Verification

1. **Static check** — repo-wide grep returns nothing:
   ```bash
   grep -rn 'Select\.BLANK' /home/ddt/Work/aitasks/.aitask-scripts/
   ```

2. **Reproduction-style smoke test** — confirm a minimal Select with `value=Select.NULL` mounts cleanly under both textual versions:
   ```bash
   /home/ddt/.aitask/venv/bin/python    - <<'PY'
   import asyncio
   from textual.app import App
   from textual.widgets import Select
   class T(App):
       def compose(self):
           yield Select([("a","a")], value=Select.NULL, allow_blank=True, id="x")
   async def main():
       async with T().run_test() as pilot:
           await pilot.pause()
       print("OK")
   asyncio.run(main())
   PY
   /home/ddt/.aitask/pypy_venv/bin/python - <<'PY'
   # same body
   PY
   ```
   Both should print `OK`.

3. **End-to-end manual verification** (the crash repro): the user runs `ait board` in a state where no live tmux session matches `default_session` / last-used (e.g., outside tmux entirely, or after `tmux kill-session -t <default>`), navigates to a task, presses the pick key. Pre-fix this crashes with `InvalidSelectValueError: Illegal select value False.`. Post-fix the dialog opens with the "+ Create new session" option preselected and the window selector blank.

4. **Regression check** — repeat with a live session matching defaults: pick dialog should still open with the existing session/window preselected.

A standalone manual-verification follow-up task for step 3 and 4 will be offered at Step 8c.

## Step 9 (Post-Implementation)

- No worktree to clean up (current branch).
- No `verify_build` configured for this project (single-line bash/Python edits).
- Run `./.aitask-scripts/aitask_archive.sh 730` to archive the task and plan.
- `./ait git push` after archival.