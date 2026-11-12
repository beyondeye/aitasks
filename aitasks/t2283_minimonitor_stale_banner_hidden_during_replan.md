---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, shadow, workflow_phase]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1573
implemented_with: claudecode/opus5_5
created_at: 2026-11-11 22:39
updated_at: 2026-11-12 08:59
---

## Symptom

The minimonitor's red `⚠ shadow feedback is stale` banner appears late during a
**re-plan**. When the user pastes the shadow's concerns into the followed agent and
presses Enter at once, the banner stays hidden the whole time the agent is thinking
and making tool calls. It only appears once the agent writes its revised plan and the
plan-approval dialog is back on screen. If the user pastes but does NOT press Enter,
the banner appears on the next refresh tick.

The banner should appear as soon as the agent starts working on the feedback (the
followed pane has changed after the shadow's last read), not when the new plan lands.

Observed live on 2026-11-11 in thinking_app, window `agent-pick-587_5`: followed
Claude pane `%891`, Codex shadow `%893`, minimonitor `%892`. The task carries a
`plan_approved` pass from the first plan round, and the agent was re-planning
after shadow concerns.

## Root cause (verified)

This is **not** the t2183 in-place list update. A headless probe of the real
`MiniMonitorApp` that sets the banner from a worker, with no list rebuild, reaches the
composited frame in ~12ms. `tests/test_minimonitor_top_chrome_render.py`,
`test_minimonitor_concern_smoke.py` and `test_minimonitor_incremental_list.py` pass.

The cause is t1573's phase-retire gate, `MiniMonitorApp._feedback_phase_retired`
(`.aitask-scripts/monitor/minimonitor_app.py`, called from `_record_banner_staleness`).
It retires the warning whenever the followed agent's current phase is KNOWN and differs
from the origin phase bound at first sighting of the block:

1. The shadow's block appears while the agent sits in Claude's plan-approval dialog.
   `workflow_phase.compose` takes the live tier (native dialog `claude_plan_approval`
   implies PLAN), so the feedback is bound as `(shadow_pane, block_key, "PLAN")`.
2. The user sends the feedback and the agent starts running. With
   `awaiting_input is not True`, `compose` suppresses the screen tiers and falls back
   to the **ledger half** (`GateSummaryCache.phase_for` → `phase_from_ledger_text`).
   The task's `## Gate Runs` holds yesterday's `gate:plan_approved status=pass`, so it
   resolves to IMPLEMENT (checked on the live task file:
   `('IMPLEMENT', 'ledger checkpoints resolve to IMPLEMENT')`).
3. IMPLEMENT is known and differs from PLAN, so the warning is retired and the banner cleared.
4. The revised plan brings the dialog back, so the phase is PLAN again, equal to the
   origin. The warning is no longer retired and the stale verdict shows.

Paste-without-Enter keeps the agent in the dialog (phase PLAN) while the pane content
changes. That is why the banner shows in that case.

The t1573 docstring accepts "a misclassified known phase flap" as cheap ("back in
the origin phase the warning returns"). Here the flap is **systematic**: every re-plan
after an approved plan reads IMPLEMENT from the ledger the entire time the agent works.
That is exactly the window in which the banner matters most.

## Fix design

Retire only on **new** evidence of a phase change, not on the same ledger state that
was already present when the feedback was bound:

- Extend the binding `_shadow_feedback_phase` from `(shadow_pane, key, phase)` with an
  identity of the task's ledger **content** at bind time, e.g. the parsed gate-run rows
  (`gate_ledger.parse_gate_run_blocks` / `parse_gate_runs`) as a count or a hash of the
  `## Gate Runs` section. Do **not** use the task file's mtime/size: notes, status edits
  and other frontmatter changes rewrite the file without changing the ledger.
  Prefer deriving it alongside the existing ledger half in `GateSummaryCache._entry_for`
  (`.aitask-scripts/monitor/monitor_core.py`), so it shares that mtime-gated cache
  rather than parsing the file a second time.
- In `_feedback_phase_retired`, branch on the current signal's `source`:
  - a **live/screen** source (`workflow-prompt`, `native-prompt`, …) that is known and
    differs from the origin retires, exactly as today;
  - a **ledger** source retires only when its phase is known, differs from the origin,
    AND the ledger identity differs from the one bound.
- An unreadable or underivable ledger identity must never retire. Fail toward showing
  the warning, the low-cost direction under the advisory anti-gating rule in
  `aidocs/framework/shadow_agent.md`.
- Keep the predicate derived, not latched (the t1573 recovery properties): flapping
  back to the origin restores the warning, UNKNOWN on either side shows it, a new round
  rebinds, and a replacement shadow pane starts unretired.

### Edge cases / acceptance criteria

1. **Re-plan after an approved plan (this bug):** feedback bound PLAN from the dialog,
   agent running with an unchanged ledger reading IMPLEMENT, so the warning is NOT
   retired and the banner shows as soon as the stale verdict is True.
2. **Real approval still retires:** the revised plan is approved, so Step 7 appends
   another `plan_approved` pass. The phase stays IMPLEMENT but the ledger content
   changed, so the warning retires once implementation really starts. This is why the
   key must be ledger CONTENT, not ledger PHASE: the phase does not change on
   re-approval. Confirm that the profiles which record gates do append a second row on
   re-approval (`task-workflow/gate-recording.md`, `aitask_gate.sh`). If some profile
   records nothing, the warning stays up until a screen phase or a new round arrives.
   That is the acceptable direction; document it.
3. **First-round PLAN → IMPLEMENT** (feedback raised before any approval): the ledger
   goes from no/older rows to a `plan_approved` row, so it changed, so the warning retires
   (t1573's `test_leaving_the_planning_phase_retires_the_warning` keeps passing).
4. **Implementation review → POSTIMPL:** a `review_approved` append changes the ledger,
   so the warning retires (keeps `test_leaving_implementation_review_retires_the_warning`).
5. **Feedback bound from a ledger-sourced phase** (agent was running when the block
   appeared): a later retirement still needs a ledger change or a differing screen phase.
6. **Ledger unreadable / task unresolved:** never retires.
7. Extend the t1573 tests in `tests/test_minimonitor_concern_action.py` (around
   `test_leaving_the_planning_phase_retires_the_warning` ..
   `test_a_replacement_shadow_pane_starts_unretired`). Add a negative control showing
   that the pre-fix predicate retires in case 1.

### Docs

Update `aidocs/framework/shadow_agent.md`, "The banner's two suppressions" (t1573):
the retire predicate now requires new evidence, with the re-plan rationale.

## Out of scope (separate follow-up candidates)

- The same ledger-vs-reality gap shows IMPLEMENT on the followed agent's card/phase line
  and in the advisory phase stamped onto the shadow (`_restamp_shadow_phase`,
  `@aitask_shadow_phase`) while the agent re-plans after an approved plan. That is a
  wider `workflow_phase` ledger-half issue, not a banner issue.
- Related but distinct: t1159_6 (always-on concern status line); t1564 (manual
  verification of the stale banner reaching the pane).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-12T07:00:02Z status=pass attempt=1 type=human
