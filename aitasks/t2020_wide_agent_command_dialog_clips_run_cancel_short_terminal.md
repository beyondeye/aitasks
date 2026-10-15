---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2013
followup_kind: upstream_defect
created_at: 2026-10-15 23:56
updated_at: 2026-10-16 00:02
---

## Origin

Spawned from t2013 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_command_screen.py:202` — the **wide** (non-narrow)
  `#agent_cmd_dialog` is a plain `Container` with `height: auto; max-height: 90%`
  and `overflow: hidden`, so on terminals shorter than ~40 rows its Run / Cancel
  buttons fall below the dialog's bottom edge and cannot be scrolled to.

## Diagnostic context

t2013 fixed the same defect class for the **narrow** dialog (minimonitor), with
every rule scoped under `AgentCommandScreen.narrow`; the task explicitly required
the wide dialog (board, monitor, codebrowser, trails, brainstorm) to render
exactly as before, so the wide case was left untouched and is pinned by
`tests/test_agent_command_dialog_narrow.py::test_wide_layout_unchanged`.

Measured after t2013 (Textual 8.2.7, `run_test`, pick dialog with Profile row,
tmux tab active, tmux helpers stubbed):

| terminal | dialog content rows (y) | `#btn_run_tmux` (y) | result |
|---|---|---|---|
| 120×44 | 2..36 | 31..33 | ok |
| 120×40 | 2..33 | 31..33 | ok (exactly fits) |
| 120×38 | 2..31 | 31..33 | **clipped** |
| 120×36 | 2..29 | 31..33 | **clipped** |
| 120×34 | 2..27 | 31..33 | **clipped** |
| 120×30 | 2..24 | 31..33 | **clipped** |

Wide-mode content: title 2 rows (incl. bottom padding) + Profile row 3+1 +
Agent row 3+1 + "Command:" 1 + Input 3+1 + `#agent_cmd_tabs` (max-height 20),
plus thick border and `padding: 1 2`. At 120×40 `#agent_cmd_tabs` already
extends past the dialog (y17..36 vs dialog bottom 35); only its unused tail is
clipped there. The `(U)se previous` button and the new-session row (shown after
open) push the buttons further down.

## Suggested fix

Mirror t2013's narrow fallback for the wide dialog: `overflow-y: auto` on
`#agent_cmd_dialog` (a focused control is scrolled into view by
`Screen.set_focus`), and size the tab content to its content
(`#tmux_content` / `#direct_content` default to `Container`'s `height: 1fr`).
Note `#agent_cmd_tabs { max-height: 20 }` clips the tab content internally once
the dialog itself can scroll — revisit it. This deliberately changes the wide
layout, so `test_wide_layout_unchanged`'s golden must be regenerated as part of
the fix, and a short-terminal reachability test added (cf. t2013's
`test_tallest_state_buttons_reachable`).
