---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-14 15:56
updated_at: 2026-05-14 16:01
---

## Origin

Spawned from t749_6 during Step 8b review.

## Upstream defect

`.aitask-scripts/brainstorm/brainstorm_app.py:3849-3858 — pre-existing on_dag_display_node_selected/on_dag_display_head_changed handlers were dead due to Textual auto-dispatch name mismatch (camel_to_snake("DAGDisplay") = "dagdisplay"). Fixed inline in t749_6 by adding @on(...) decorators. Worth a separate follow-up audit pass: grep .aitask-scripts/ for other on_<snake>_<msg> handlers where the widget class name contains adjacent uppercase characters (DAG, UI, URL, API, …) — they may also be dead.`

## Diagnostic context

Textual's `camel_to_snake()` (from `textual/case.py`) uses the regex
`[a-z][A-Z]` to find word boundaries. For widget class names that contain
adjacent uppercase letters (`DAG`, `URL`, `API`, `UI`, `HTTP`, etc.), no
boundary is detected inside the run of capitals — `DAGDisplay` collapses to
`dagdisplay`, not `dag_display`. The auto-resolved Message handler name for
`DAGDisplay.OperationOpened` is therefore `on_dagdisplay_operation_opened`.

Any hand-written handler `on_dag_display_*` against such a class is dead
code — Textual will silently skip it. The handler appears wired (the
function signature uses the message class, the IDE shows no warnings), but
the message never invokes it. The first symptom is that the keystroke /
event does nothing in production; nobody notices until someone tries to
write an integration test.

In t749_6 this manifested as: pressing Enter on a focused DAG node never
opened the NodeDetailModal, and pressing `h` never updated HEAD from the
DAG view — both pre-existing, silently broken in production for as long as
DAGDisplay's hand-rolled message classes have existed (pre-t749_5).
Fixed inline by switching to `@on(DAGDisplay.NodeSelected)` etc. — the
decorator matches by message class, not by name.

## Suggested fix

1. Audit `.aitask-scripts/` (especially the brainstorm and other TUI
   modules) for `on_<snake>_<msg>` handler definitions. For each, compute
   what `camel_to_snake(SenderClass)` actually returns:
   ```bash
   python3 -c "from textual.case import camel_to_snake; print(camel_to_snake('YourClassName'))"
   ```
   If the result has no underscore where the handler name has one (i.e.
   adjacent caps in the source class name), the handler is dead.

2. For any dead handler discovered, either:
   - Convert to `@on(MessageClass)` decorator form (preferred — robust to
     class renames and unambiguous about the wiring), OR
   - Rename the handler to match `camel_to_snake(SenderClass)` exactly.

3. Cross-check by writing a smoke test for each affected handler that
   posts the message and asserts the handler ran.

## Why low effort

This is a mechanical grep + fix sweep. Each handler conversion is a
two-line patch (`@on(MessageClass)` line plus signature). The risk is
catching false positives where the snake-case name happens to coincide
with the correct auto-name; those need no change.
