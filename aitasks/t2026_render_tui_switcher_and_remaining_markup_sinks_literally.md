---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
anchor: 1326
followup_kind: upstream_defect
created_at: 2026-10-16 00:46
updated_at: 2026-10-16 00:46
---

## Origin

Spawned from t2017 during Step 8b review.

## Upstream defect

Line numbers are as of t2017's code commit `287ed97a9`.

- `.aitask-scripts/lib/tui_switcher.py:816-841` — session labels are interpolated raw before `[/]` / ` (stale)[/]`, so a session named `[/]` raises MarkupError in every TUI's switcher. The same file also inserts a window name raw at `:387` and in the "Failed to switch to {name}" toast at `:1388`.
- `.aitask-scripts/monitor/monitor_shared.py:3686` — `_escape_markup` and the other remaining `escape()` users are built on `rich.markup.escape`, which is wrong under Textual: it doubles a backslash before a bracket and a trailing backslash. The other users are concern entry meta `:4955`, block meta `:5259`, stale detail `:5287`/`:5295`, the column picker `:3182`, column move `:3333`, and draft paths `:1596`.
- `.aitask-scripts/monitor/minimonitor_app.py:3377` — the "Not a task number: {raw!r}" toast puts typed input into a markup-parsed toast raw.

## Diagnostic context

t2017 migrated every monitor/minimonitor sink that carries a window name, session name, task title or frontmatter field, or pane command. The user scoped it to that data class inside `.aitask-scripts/monitor/`, so the sinks above were recorded and left alone. The behaviour of Textual 8.2.7's parser (pinned by `tests/test_monitor_markup_escape.py` and `tests/test_monitor_markup_literal_sinks.py`):

- Textual opens a tag at any `[` not preceded by a backslash, un-escapes only `\[`, and keeps every other backslash literal.
- `rich.markup.escape` doubles a backslash before a bracket and a trailing backslash. It also leaves a lone `[` alone, which then swallows the next tag.
- A value ending in `\` directly before a real tag turns that tag into text; no string escaping can express this case.

## Suggested fix

Apply t2017's four rules, chosen by what follows the value:
- a toast with no styling → `notify(..., markup=False)`;
- a value followed by text or ending the markup → `markup_literal()` (in `monitor_shared.py`), leaving an ending style open;
- a value directly before a tag in a widget built once → `Content.from_markup(template, **variables)`, with every user field a `$variable`;
- a Static with no markup → `Content(text)`.

For `_escape_markup`, `markup_literal` already escapes every `[`, so it can likely replace the escape-then-patch loop. Its tests in `tests/test_concern_picker_modal.py` measure with Rich and must move to Textual's parser. Write hostile fixtures so that no single literal holds a named closing tag (t2021's convention), or Rule C in `tests/test_textual_markup_colours.py` flags them.
