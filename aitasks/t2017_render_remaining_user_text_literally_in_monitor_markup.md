---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1326
followup_kind: upstream_defect
created_at: 2026-10-15 23:07
updated_at: 2026-10-15 23:10
---

## Origin

Spawned from t2006 during Step 8b review.

## Upstream defect

Markup sinks that interpolate user-derived text (tmux window names, session names, task titles) raw. They were deliberately left out of t2006's selected surfaces, which were the monitor card rows, the preview header and `KillConfirmDialog`. Line numbers are as of t2006's commit `337d0f6e0`:

- `.aitask-scripts/monitor/monitor_app.py:2977` — the `Switched to {name}` toast. This is one of several window-name toasts in this file, also including `No log file found for` / `Opening log for {agent_name}`, `Killed` / `Failed to kill {name}`, `Killed {old_name}`, and `Killed {old_window_name}` at :3842. None of them crash: Textual's toast tolerates bad markup. A `[dim]`-style name is swallowed, though.
- `.aitask-scripts/monitor/monitor_app.py:356` — the `RestartConfirmDialog` "Current:" row interpolates the task title raw into a Static. `[/]` raises MarkupError.
- `.aitask-scripts/monitor/monitor_shared.py:2272` — the `TaskDetailDialog` title Static interpolates `info.title` raw. The header `update` at :2313 does the same.
- `.aitask-scripts/monitor/monitor_shared.py:2855` — the `NextSiblingDialog` current and suggested rows (:2855, :2857) interpolate task titles raw.
- `.aitask-scripts/monitor/monitor_shared.py:2929` — `_SiblingRow.render` interpolates the sibling title raw.
- `.aitask-scripts/monitor/monitor_app.py:1728` — the status bar interpolates session names raw (`session: …`, and `(attached: …)` at :1715). The `Session renamed to` toast at :800 does the same.
- `.aitask-scripts/monitor/monitor_shared.py:361` — `format_session_divider` uses `rich.markup.escape`, which is wrong under Textual's parser (see below). The same applies to `monitor_shared.py:1158`, `monitor_app.py:3577`, minimonitor's `_row_name` / title row / `_own_header_text`, and minimonitor's own window-name toasts (`Killed` / `Failed to kill {name}`, `Switched to {name}`).

## Diagnostic context

t2006 established the following through probes against the installed Textual 8.2.7 and Rich 14.3.2. They are pinned by `tests/test_monitor_markup_escape.py`, which includes a negative control that fails if Textual's parser changes:

- Textual's tokenizer opens a tag at any `[` not preceded by a backslash (`(?<!\\)\[`). In text it un-escapes exactly `\[` → `[`, and it keeps every other backslash literal.
- `rich.markup.escape` and `textual.markup.escape`, which are identical, double the backslashes that precede a bracket. That is right for Rich, which collapses `\\`. It is wrong for Textual, which does not collapse them: `agent-\[bold]y` displays with two backslashes.
- A value ending in `\` that sits directly before a real tag turns that tag into literal text. No string escaping can express this case.
- Rich's `Text.from_markup` renders all of these correctly. So a test that parses with Rich cannot see the defect; parse with `textual.content.Content.from_markup` or read a mounted widget's `render()`.

## Suggested fix

Reuse t2006's two primitives:
- `markup_literal()` in `monitor_shared.py` (prefix each `[`, never double a backslash) for values that are followed by non-tag text or end the markup.
- `Content.from_markup(template, **variables)` (`$name` values are substituted after tokenizing, so they are always literal) wherever a user value sits directly before a tag.

Migrate the existing `escape()` users onto them. For the toasts, `notify(..., markup=False)` is an option when the toast carries no styling. Add Textual-parser tests that mirror `tests/test_monitor_markup_escape.py` and the hostile-field case in `tests/test_kill_confirm_dialog.py`.
