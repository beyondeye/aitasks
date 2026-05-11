---
priority: high
effort: high
depends: [t749_4]
issue_type: feature
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-05 10:43
updated_at: 2026-05-11 09:42
---

## Context

Largest child of t749. Adds a new `OperationDetailScreen(ModalScreen)`
that shows everything about the operation that generated a node:
type, status, when it ran, what HEAD it was based on, what nodes it
produced, the user's input parameters (resolved via `OpDataRef`), and
each agent's input/output/log.

Depends on t749_1 (br_groups.yaml populated) and t749_2
(`brainstorm_op_refs.py` providing the reference primitives).

The 'o' key binding that opens this screen is wired up in t749_6.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — add a new
  `OperationDetailScreen` class (place it near `NodeDetailModal`,
  around line 380). Wire its CSS into the App's CSS section.

## Reference Files for Patterns

- `brainstorm_app.py:380-600` — `NodeDetailModal` is the closest
  template: same `ModalScreen` + `Header` + `TabbedContent` +
  `VerticalScroll(Markdown)` + `Close` button pattern.
- `brainstorm_app.py:2753-2840` — `_mount_agent_row` already renders
  per-agent status lines; the Overview tab can reuse it for the
  agent-status table.
- `.aitask-scripts/brainstorm/brainstorm_op_refs.py` (from t749_2) —
  use `list_op_inputs`, `list_op_outputs`, `list_op_logs`,
  `list_op_definition`, and `resolve_ref` here.
- `.aitask-scripts/section_viewer.py` (`SectionMinimap`,
  `SectionViewerScreen`) — reuse for navigating long input/output
  Markdown documents the same way `NodeDetailModal` does.

## Implementation Plan

1. New class signature:
   ```python
   class OperationDetailScreen(ModalScreen):
       BINDINGS = [
           Binding("escape", "close", "Close", show=True),
           Binding("q", "close", "Close", show=False),
       ]
       DEFAULT_CSS = """  ...modal sized like NodeDetailModal... """

       def __init__(self, group_name: str, session_path: Path):
           super().__init__()
           self.group_name = group_name
           self.session_path = session_path
           self.group_info: dict = {}
   ```

2. `compose()`:
   ```python
   yield Container(
       Label("", id="op_detail_title"),
       TabbedContent(id="op_detail_tabs"),
       Horizontal(
           Button("Close", id="btn_close_op_detail"),
           id="op_detail_buttons",
       ),
       id="op_detail_dialog",
   )
   ```

3. `on_mount()`:
   - Load `br_groups.yaml`. If missing or `group_name` not present,
     show a "No group entry recorded" placeholder (single label) and
     return early.
   - Set the title: `Operation: <op> (<group_name>) [<status>]` with
     the op-color from `OP_BADGE_STYLES`.
   - Build the Overview tab (see step 4).
   - For each agent in `group_info["agents"]`, build a `TabPane`
     (see step 5).

4. Overview tab:
   - Created at: `<created_at>`
   - HEAD at creation: `<head_node_id>` (with a `Static` link styled
     as a hint — clicking does nothing in v1; future could push
     NodeDetailModal).
   - Nodes created: list of node ids resolved from
     `list_op_definition(group_info)` (skip the head_at_creation,
     show only nodes_created).
   - User input: render `resolve_ref(session_path,
     list_op_inputs(group_info)[0])` as a `Markdown` widget. Above
     it, a label "Input: \<section title from the ref\>". If
     `list_op_inputs` returns empty, show a dim placeholder
     "(no agents registered yet — input pending)".
   - Agent statuses: a small table (re-emit `_mount_agent_row` calls
     by sharing the helper or extracting it to a free function).

5. Per-agent tab (one per agent in `group_info["agents"]`):
   - `TabPane(label=name, id=f"tab_agent_{name}")`.
   - Inside: `VerticalScroll` containing three blocks separated by
     bold-section headers:
     - `Input` — `Markdown(resolve_ref(session_path,
       OpDataRef("agent_input", name)))` (whole file).
       Optional `SectionMinimap` for nav (reuse the
       `NodeDetailModal._proposal_minimap` pattern).
     - `Output` — `Markdown(resolve_ref(session_path,
       OpDataRef("agent_output", name)))`. If file is missing
       (agent still running), show a dim placeholder "(agent has
       not produced output yet)".
     - `Log` — `RichLog` populated via `read_log_tail(...)` from
       `agentcrew_log_utils` for the last 200 lines. Or `Static` with
       the same content if `RichLog` isn't necessary.

6. `action_close()` and `@on(Button.Pressed, "#btn_close_op_detail")`
   both `self.dismiss(None)`.

7. Add modal CSS to the App's main CSS section, sized roughly like
   `NodeDetailModal` (90% width, 90% height).

## Verification Steps

1. Add a smoke test `tests/test_brainstorm_operation_detail_screen.py`
   that uses `Pilot` (Textual's testing harness) to:
   - Create a tmp session, run `record_operation` with two agents
     and write fixture `<agent>_input.md` / `_output.md` / `_log.txt`.
   - Push `OperationDetailScreen("explore_001", session_path)`.
   - Assert: title contains "Operation: explore (explore_001)", tab
     count == agent count + 1 (Overview), Overview shows the user's
     mandate text from the input.md ref.
   - Press `escape` and assert the screen dismisses.

2. Manually run an explore in a real brainstorm session, then (after
   t749_6 lands) press 'o' on a focused node — verify all tabs
   render, content is correct, and Esc closes the screen.

3. Run on `n000_init` of a session started via `--proposal-file`:
   verify the bootstrap group's initializer agent tab shows the
   initializer input and output. For a blank-init session, verify
   the Overview tab shows the `initial_spec` (resolved via a
   `session_spec` ref — see step 4 user-input fallback when agents
   list is empty for bootstrap).

## Notes for Sibling Tasks

- t749_6 wires the 'o' key binding to push this screen — it depends
  on this child but does NOT depend on the per-agent layout details.
- If a future task wants to navigate from a node id in the Overview
  tab back to that node's NodeDetailModal, add a click handler on
  the node-id labels — out of scope for this child.
- The Markdown widgets in per-agent tabs can become large for long
  log files. Use `read_log_tail(path, max_lines=200)` (already in
  `agentcrew_log_utils`) instead of `read_text()` for `_log.txt`.
