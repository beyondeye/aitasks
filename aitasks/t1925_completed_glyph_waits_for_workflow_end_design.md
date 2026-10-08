---
priority: medium
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [monitor, minimonitor, task_workflow]
gates: [risk_evaluated]
anchor: 1913
created_at: 2026-10-08 23:19
updated_at: 2026-10-08 23:19
---

## Problem

The monitor/minimonitor COMPLETED badge fires as soon as `aitask_archive.sh`
writes `status: Done` or moves the task file to `aitasks/archived/`.
`is_task_completed()` (`.aitask-scripts/monitor/monitor_shared.py:132`) is used
by both apps' `_compute_completed_panes`. Archival happens partway through
task-workflow Step 9, so the blue DONE badge lights while the agent still has to
handle issue/PR follow-ups, the push, Step 9b and the Step 10 end banner.

The user reported: "the completed glyph mark in the agent list is triggered
BEFORE the task workflow actual last step".

t1913 split this goal off and shipped the user-facing complete/stopped banners
only, with the monitor logic deliberately unchanged. This task designs a
**reliable** signal for "the workflow reached its last step".

## Rejected approaches (t1913 plan review, with reasons)

1. **Archived and pane idle** (`snap.is_idle and not awaiting_input`).
   Rejected: `is_idle` only means the pane content has not changed for
   `idle_threshold` (5 s, `monitor_core.py` ~L2819). A quiet push, a metadata
   update, or an agent with animations disabled satisfies it mid-run. Idle is
   not evidence of completion.
2. **Matching the end banner on screen** (`aitask workflow complete — t<id>` in
   the capture tail). Rejected: a substring in the tail cannot tell an emitted
   ending from a quoted example, from tool output, or from a stale banner left by
   an earlier run of the same task.
3. **A per-pane end record** (`.aitask-gates/<id>/workflow_end`, `pending`
   before archival and `complete` at Step 10, with idle-window fallbacks for
   legacy and crashed runs: 60 s / 600 s). Rejected as still leaning on idle
   heuristics for the fallbacks. The user then descoped detection from t1913
   entirely: "A reliable glyph change needs a separate design."

## Constraints to respect

- Keep a working signal for runs that never reach the new step (older rendered
  skills, other code agents, crashed sessions) without reintroducing idle or
  screen heuristics as completion evidence.
- No declared gate may be added. Keep the `resume-point`, `workflow-phase` and
  `archive-ready` consumers unchanged (`lib/gate_ledger.py`,
  `lib/workflow_phase.py`, `board/board_workflow_phase.py`,
  `monitor/review_loop.py`, `lib/trail_gather.py`).
- The completed set must remain the sole source for cards, bars and auto-switch
  in both apps (`aidocs/framework/monitor_idle_and_prompt_detection.md`, "Where
  completed comes from").
- The user-facing docs currently describe DONE as tracking archival:
  `website/content/docs/tuis/monitor/how-to.md` and
  `website/content/docs/tuis/minimonitor/how-to.md`. Update them only once
  behaviour actually changes.

## Starting points

- `.claude/skills/task-workflow/workflow-end.md` is the run's single final
  step, both its `## Complete` display and its Step 10 call site. It is a natural
  place to emit any durable evidence the design chooses.
- Also relevant: the task window name → task id mapping
  (`monitor_core.task_id_from_window_name`), the session → project-root mapping
  (see t1922 for a discovery bug there), and `TaskInfoCache` freshness rules.
