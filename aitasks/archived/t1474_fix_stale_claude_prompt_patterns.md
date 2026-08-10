---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_monitormini, monitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1477]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-10 16:19
updated_at: 2026-08-10 18:43
completed_at: 2026-08-10 18:43
---

## Origin

Spawned from t1420 during Step 8b review. All three defects were **measured
live** against Claude Code 2.1.226 while t1420's pre-phase captured four real
prompt widgets through the monitor's own capture path
(`capture-pane -p -e` + `ansi_utils.strip_ansi`).

## Upstream defect

- `.aitask-scripts/monitor/prompt_patterns.py:28` — `claude_proceed`
  (`Do you want to proceed\?`) matches **no current Claude Code dialog**.
  ExitPlanMode says "Would you like to proceed?" and tool permission says
  "Do you want to create <file>?". The pattern is dead, and its comment claiming
  it covers "Plan-mode and tool-permission confirmation prompt" is wrong.
- `.aitask-scripts/monitor/prompt_patterns.py:25` — the first-run
  **workspace-trust dialog** ("Quick safety check: Is this a project you created
  or one you trust?", footer `Enter to confirm · Esc to cancel`) is matched by
  nothing, so an agent blocked on it reads as **idle** in `ait monitor` /
  `ait minimonitor` — the user is never told it is waiting on them.
- `.aitask-scripts/monitor/ansi_utils.py:13` — `ANSI_CSI_RE` strips only CSI
  sequences. OSC 8 hyperlinks (`ESC]8;id=..;URL\text ESC]8;;\`) survive stripping
  and appear verbatim in captured pane text (observed in the tool-permission and
  Write-tool captures), polluting `compare_value` and any text matching built on
  it — including idle detection, which compares stripped content.

## Diagnostic context

t1420 needed a reliable "is this pane blocked on a question?" marker and probed
four live widgets. The measurement table it produced:

| widget | footer line | matched by |
|---|---|---|
| `AskUserQuestion` | `Enter to select · ↑/↓ to navigate · Esc to cancel` | nothing (t1420 added `claude_askuserquestion`) |
| workspace trust | `Enter to confirm · Esc to cancel` | **nothing — still unfixed** |
| tool permission | `Esc to cancel · Tab to amend` | `claude_help_bar` |
| ExitPlanMode | `ctrl+g to edit in …` / `Yes, auto-accept edits` | nothing (t1420 added `claude_plan_approval`) |

t1420 fixed only the two rows its own feature required and deliberately left
`claude_proceed` untouched (additive-only, to keep a stale long-running
minimonitor degrading rather than misreporting — see t1116).

## Suggested fix

Retire or re-target `claude_proceed` to the wording it is meant to catch, add a
`claude_trust_folder` pattern for the workspace-trust footer, and extend
`strip_ansi` to drop OSC sequences (`ESC]…BEL` / `ESC]…ESC\`) alongside CSI.
Note `awaiting_input_kind` reaches the applink wire (`applink/pusher.py:420-421`),
so document any value change. Coordinate with t1467, which owns the
Codex/OpenCode prompt-surface inventory.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-10T15:20:59Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-10T15:40:44Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-10T15:43:47Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:76b2efd7c1deaaeb

> **✅ gate:risk_evaluated** run=2026-08-10T15:43:47Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1474/risk_evaluated_2026-08-10T15:43:47Z-risk_evaluated-a1.log`
