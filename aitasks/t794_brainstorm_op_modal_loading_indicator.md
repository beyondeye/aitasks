---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-19 09:34
updated_at: 2026-05-19 09:54
---

In the brainstorm TUI, pressing `o` on a node (either in the node list
or in the DAG view) opens the `OperationDetailScreen` modal showing
operation details. The modal can take a few seconds to open during
which the TUI shows no visual feedback — the user can't tell whether
the keypress was registered. Surfaced during t792 manual verification.

## Goal

Show a loading/progress indicator while `OperationDetailScreen` is
preparing so the user has immediate visual feedback after pressing `o`.

## Suggested approach

- `OperationDetailScreen` is at `.aitask-scripts/brainstorm/brainstorm_app.py`
  around line 1047+ (`OperationDashboardScreen`/`OperationDetailScreen`).
- Two reasonable directions:
  1. Show a brief Textual `notify("Opening operation details…", timeout=2)`
     in the calling code path before `push_screen(OperationDetailScreen(...))`
     — minimal change, zero risk.
  2. Mount a small `Static("Loading…")` or `PollingIndicator` inside
     the modal's compose method, then populate the real widgets in
     `on_mount` / via `call_after_refresh`. Cleaner UX but requires
     refactoring how the modal builds its initial widget tree.
- Calling sites that trigger the modal:
  - `NodeRow.action_open_operation` → `on_node_row_operation_opened`
    (`brainstorm_app.py:4339`)
  - `DAGDisplay.action_open_operation` → `on_dag_display_operation_opened`
    (`brainstorm_app.py:4243`)

## Acceptance

- Pressing `o` produces some visible feedback (notification or
  in-modal loading indicator) within < 200ms.
- No regression to existing modal functionality.
- Manual TUI smoke verifies the indicator appears and disappears at
  the right time.

## Origin

Surfaced by user during t792 review (graph-tab drift fix). See
`aiplans/archived/p792_brainstorm_explore_progress.md` "Follow-up
tasks identified during implementation".
