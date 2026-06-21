---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: high
depends: [t1018_1]
issue_type: enhancement
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
anchor: 1018
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 10:19
updated_at: 2026-06-21 11:36
---

## Context
Child of t1018. Add **operation/group-level restart** on the Running tab so a
brainstorm operation (e.g. `synthesize_001`) whose agents failed can be
recovered without dropping to the CLI. Today the only recovery surfaces are the
apply-retry actions (which only re-ingest already-produced output) and `w`
(resets a single *agent*). There is **no operation-level restart** — an
operation that aborted before producing output is stuck.

Builds on the per-screen binding model and deliverable-key approach from
**t1018_1** (depends on it). Uses the **per-row `on_key` + render-hint** pattern
(matching the landed `w`/`R`/`x` Running-tab row actions, t983_9's decision) —
NOT a footer Binding. (User decision during t1018 planning.)

### Verified current state (corrects stale task-body premises)
- **Operations have NO `Error`/`Aborted` state.** `_TERMINAL_AGENT_STATES =
  {"Error","Aborted","Completed"}` (`brainstorm_app.py:199`) is **agent-level**;
  a group's `status` in `br_groups.yaml` is only `Waiting`/`Completed`
  (`brainstorm_session.py` `record_operation` `:232-264`, `update_operation`
  `:282-309`). `GROUP_OPERATIONS` (`brainstorm_schemas.py:78-85`) is the list of
  operation *types* (explore/compare/synthesize/module_decompose/_merge/_sync),
  NOT states. So "an aborted operation" = **a group still `Waiting` whose agents
  are in `Error`/`Aborted`**. A focused `GroupRow` exposes `group_name` +
  `group_info` (operation, agents, status, head_at_creation, nodes_created,
  subgraph) — but the agent failure state lives on the child `AgentStatusRow`s.
- **No CLI restart command exists.** Launch logic is in-process:
  `_run_design_op()` (`brainstorm_app.py:8370-8538`, worker thread) dispatches to
  `register_explorer/comparator/synthesizer/...` in `brainstorm_crew.py:579-703`,
  which call `_run_addwork()` (`:125-175`, subprocess to `ait crew addwork`),
  then `record_operation()`. The umbrella's "prefer shelling out to existing
  `ait crew`/`ait brainstorm` commands" only partly applies — there is no
  operation-restart subcommand to shell out to; reuse the in-process launch path.
- **Config-recovery gap:** `br_groups.yaml` stores operation/agents/status/
  head_at_creation/nodes_created/subgraph but **NOT** the per-operation config
  (explore mandate, compare dimensions, synthesize merge-rules). That config
  lives in `<agent>_input.md`. So "re-run fresh" cannot reconstruct the original
  config from `br_groups.yaml` alone.

## Two actions to add (offered as a choice on the focused operation/group row)
1. **Re-run whole operation fresh** — reset to a clean state and relaunch the
   operation's agents from scratch. **Recommended approach (confirm in plan):**
   re-open the `ActionsWizardScreen` pre-populated for that operation type at the
   group's `head_at_creation`, so the user re-confirms/edits the config, then
   dispatch through the existing `_execute_design_op()` path (`:8354-8368`). This
   reuses ALL launch logic, solves the missing-config problem, and the wizard
   serves as the destructive-action confirm. Offer to clean up the old failed
   group (reuse the existing `x` cleanup). (Alternative — parsing `<agent>_input.md`
   to silently re-register — is fragile; document why it is rejected.)
2. **Retry only the failed step** — resume/re-apply just the part that failed.
   Re-home the existing `action_retry_explorer_apply` (`:7237-7251`) /
   `action_retry_synthesizer_apply` (`:7387-7398`) logic — which re-ingests a
   Completed agent's output via `_try_apply_*_if_needed(..., force=True)` — onto
   the focused `GroupRow` as an `on_key` action. **After re-homing, remove the
   now-dead global `ctrl+shift+x`/`ctrl+shift+y` chord bindings** (`:5546`,`:5548`)
   that t1018_1 gated (this child owns their removal; t1018_1 kept the action
   methods alive for exactly this re-home).

Confirm destructive re-runs with a modal (or the wizard's own confirm for #1).

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Running-tab `on_key` dispatch
  (`:5837-5899`, where GroupRow/AgentStatusRow focus is handled); `GroupRow`
  (`:3115-3150`, add render-hint for the new keys); `_run_design_op()` /
  `_execute_design_op()` (extract a reusable "launch agents for this operation
  group" helper rather than duplicating); the retry-apply actions (`:7237-7398`).
- `.aitask-scripts/brainstorm/brainstorm_session.py` — `record_operation` /
  `update_operation` (group state transitions); a possible `restart_operation`
  helper (pure, headless-testable — pull it out early per testing conventions).
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — if operation status needs
  an explicit failed/aborted state (decide in plan; may be unnecessary if we key
  off agent states).

## Reference Files for Patterns
- The landed `w`/`R`/`x` row actions and `CleanupAgentModal` confirm
  (`brainstorm_app.py` `_retry_agent` `:7609-7631`, `_reset_agent` `:7593-7607`,
  `CleanupAgentModal` `:867`) — the exact per-row `on_key` + render-hint + confirm
  pattern this child mirrors.
- `aiplans/archived/p983/p983_9_running_strip_deconflict_docs.md` — the landed
  Running-tab work + the explicit "row actions are on_key, not footer Bindings"
  decision.
- `aidocs/framework/tui_conventions.md`, `aidocs/framework/tmux_gateway.md`,
  `aidocs/framework/testing_conventions.md` (pull pure restart/state-transition
  logic into a headless-testable unit early).

## Implementation Plan (detail in aiplans/p1018/p1018_2_*.md)
1. Pull the agent-registration loop out of `_run_design_op()` into a reusable,
   headless-testable helper.
2. Add GroupRow `on_key` handlers: one key for "re-run fresh" (→ pre-filled
   wizard), one for "retry failed step" (→ re-homed retry-apply). Add render-time
   hints to `GroupRow.render()`.
3. Wire "re-run fresh" through `_execute_design_op()` with config recovered via
   the pre-filled wizard; offer old-group cleanup.
4. Remove the dead `ctrl+shift+x`/`ctrl+shift+y` global chord bindings.
5. Tests (this child owns them) — see Verification.

## Verification
- Pure-unit tests for the extracted restart/state-transition helper (clean reset,
  relaunch payload assembly, idempotency).
- `pilot.press(...)` tests driving the GroupRow `on_key` actions on a fixture
  session with a failed operation group (artificial `br_groups.yaml` +
  `<agent>_status.yaml` fixtures — ephemeral).
- Assert the old `ctrl+shift+x`/`ctrl+shift+y` bindings are gone and no global
  retry-apply chord survives (grep + structural assertion).
- Full brainstorm suite green.
- **Live behavioral verification** (real session, real failed agent → re-run
  fresh actually relaunches and produces output; retry-step re-applies) is
  covered by the aggregate **t1018_4** manual-verification sibling.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-21T08:36:18Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-21T08:36:20Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-21T08:59:04Z status=pass attempt=1 type=human
