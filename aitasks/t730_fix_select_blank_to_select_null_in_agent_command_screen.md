---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tmux, tui, agent_chooser]
created_at: 2026-05-03 08:05
updated_at: 2026-05-03 08:05
---

## Symptom

`ait board` crashes when launching the pick-command dialog (and any other dialog
that lands on the "no live tmux session matches defaults" branch of
`AgentCommandScreen`):

```
InvalidSelectValueError: Illegal select value False.
  at textual/widgets/_select.py:594  (_validate_value)
  via _on_mount → _init_selected_option(self._value)
  on Select(id='tmux_window_select')
```

## Root cause

`.aitask-scripts/lib/agent_command_screen.py` uses `Select.BLANK` as the
"unselected" sentinel in 5 places. In current textual (verified against both
8.1.1 in `~/.aitask/venv` and 8.2.5 in `~/.aitask/pypy_venv`), `Select` no
longer defines `BLANK` — the attribute resolves via MRO to
`Widget.BLANK: ClassVar[bool] = False` (an unrelated CSS-ish flag meaning
"is this widget a blank/no-border container").

So `Select.BLANK` is `False`, not a `NoSelection` sentinel. The current
unselected-state sentinel is `Select.NULL` (instance of
`textual.widgets._select.NoSelection`).

The crash fires on the new-session-sentinel branch: `pick_initial_session`
returns `_NEW_SESSION_SENTINEL` (no live tmux sessions, or none matching
defaults / last-used) → `compose` enters the `else` at `agent_command_screen.py:362`
→ `win_value = Select.BLANK` (line 364) → `Select(value=False, ...)` (line 369)
→ on mount, textual's `_validate_value(False)` rejects it because
`False not in self._legal_values`.

This is **not PyPy-related** — confirmed reproducible under CPython textual
8.1.1 with a minimal `Select([("a","a")], value=Select.BLANK, allow_blank=True)`
test inside `App.run_test`. The user only noticed it now because their tmux
state changed (e.g., launching the board outside tmux, or with no live session
matching `default_session` / last-used), making the new-session branch reachable.

## Fix

Replace `Select.BLANK` with `Select.NULL` at all 5 sites in
`.aitask-scripts/lib/agent_command_screen.py`:

- `:364` `win_value = Select.BLANK` — primary crash; `value=False` fails Select validation
- `:482` `elif value and value != Select.BLANK:`
- `:505` `elif value and value != Select.BLANK:`
- `:762` `elif sess_select.value and sess_select.value != Select.BLANK:`
- `:783` `elif win_select and win_select.value and win_select.value != Select.BLANK:`

The four guard sites (482/505/762/783) are latent wrong-behavior bugs even
without a crash: comparing a real string sentinel (or `Select.NULL`) to
`False` always evaluates True, so "no selection" was being mis-classified as
"has selection". Fixing all five together restores correct semantics.

## Verification

1. Reproduce the crash before the fix:
   ```bash
   tmux kill-server  # ensure no live sessions
   ./ait board       # navigate to a task, press the pick key — should crash
   ```
2. Apply the fix (5-line replacement).
3. Re-run the same flow — pick dialog should open with the "+ Create new
   session" option preselected and the window selector blank.
4. Repeat with a live session present (normal path) to confirm no regression.
5. Grep the repo for any remaining `Select.BLANK` occurrences:
   `grep -rn 'Select\.BLANK' .aitask-scripts/` should return nothing.

## Out of scope

- No need to bump the textual version or pin a different range — `Select.NULL`
  is the correct, current API in both installed textual versions (8.1.1, 8.2.5).
- No changes needed in monitor/codebrowser/syncer callers of `AgentCommandScreen`
  — they don't reference `Select.BLANK` themselves; the fix lives entirely
  inside `agent_command_screen.py`.
