---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [test]
created_at: 2026-06-16 19:06
updated_at: 2026-06-16 19:06
---

## Context

Two PRE-EXISTING test failures were surfaced (not caused) during t635_11 work.
Neither is related to the gate framework; both should be fixed independently.

## Failures

1. **Board-load failures** — `tests/test_settings_shortcuts_tab.py` and
   `tests/test_shortcut_scopes.py` fail with:
   `could not load aitask_board (.aitask-scripts/board/aitask_board.py):
   AttributeError: 'NoneType' object has no attribute '__dict__'`.
   The shortcut-sweep cannot import the board TUI module (likely a Textual/import
   environment issue). Diagnose why `aitask_board.py` fails to load under the test
   harness and fix so the shortcut-coverage sweep registers the board's scope.

2. **task-workflown parity drift** — `tests/test_skill_render_task_workflown.sh`
   Test 1 ("source file list parity") fails: `.claude/skills/task-workflow/` has
   `gate-recording.md` (added by t635_2) but the staging copy
   `.claude/skills/task-workflown/` does not. Either sync `gate-recording.md` (and
   re-check for other drift) into task-workflown, or retire task-workflown if it is
   obsolete leftover staging from the t777_6 pilot.

## Verification

`python3 tests/test_settings_shortcuts_tab.py`, `python3 tests/test_shortcut_scopes.py`,
and `bash tests/test_skill_render_task_workflown.sh` all green.
