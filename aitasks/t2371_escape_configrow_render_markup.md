---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, execution_profiles]
gates: [risk_evaluated]
anchor: 2363
followup_kind: upstream_defect
created_at: 2026-11-27 01:18
updated_at: 2026-11-27 01:18
---

## Origin

Spawned from t2363 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/profile_editor.py:639-641` — `ConfigRow.render` (the non-compact form, used by the settings TUI Profiles tab and by the wide `ProfileEditScreen`) interpolates `self.key` / `self.value` into Rich markup unescaped. A profile string value containing markup such as `[/bold]` raises `MarkupError` on render. `CycleField.render` already escapes its label and options for exactly this reason (see its comment).

## Diagnostic context

t2363 added a compact `ConfigRow` render for the narrow profile editor, which wraps key and value in `escape()`. The wide and subordinate forms were left unchanged, out of t2363's scope. Values come straight from profile YAML (`default_email`, `description`, CSV lists), so any of them can carry text that the renderer parses as markup.

## Suggested fix

Wrap `self.key`, `self.value` (and the subordinate form's `self.value`) in `rich.markup.escape` inside `ConfigRow.render`. Add a test that renders a row whose value is `"[/bold]x"` in both the settings TUI and `ProfileEditScreen`. Also check `settings_app.py` for its own `ConfigRow` uses.
