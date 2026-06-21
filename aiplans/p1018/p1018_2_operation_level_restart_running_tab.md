---
Task: t1018_2_operation_level_restart_running_tab.md
Parent Task: aitasks/t1018_brainstorm_op_restart_dblclick_footer_hygiene.md
Sibling Tasks: aitasks/t1018/t1018_*.md
Archived Sibling Plans: aiplans/archived/p1018/p1018_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# p1018_2 — Operation/group-level restart on the Running tab

Depends on **t1018_1** (per-screen binding model + the gated retry-apply
actions). Adds operation-level recovery on the Running tab using the per-row
`on_key` + render-hint pattern (NOT a footer Binding — user decision).

## Verified current state (read before coding — confirm line numbers)

- **Operation/group model:** `GROUP_OPERATIONS` = explore/compare/synthesize/
  module_decompose/_merge/_sync (`brainstorm_schemas.py:78-85`). A group entry in
  `br_groups.yaml`: `operation`, `agents`, `status` (**Waiting|Completed only**),
  `created_at`, `head_at_creation`, `nodes_created`, `subgraph`. Written by
  `record_operation()` (`brainstorm_session.py:232-264`), patched by
  `update_operation()` (`:282-309`).
- **Failure is agent-level, not operation-level:** `_TERMINAL_AGENT_STATES =
  {"Error","Aborted","Completed"}` (`brainstorm_app.py:199`);
  `_AGENT_FAILED_STATUSES = ("Error","Aborted")` (`brainstorm_session.py:640`).
  A group stays `Waiting` while its agents fail. "An aborted operation" = a
  `Waiting` group whose `AgentStatusRow`s are in `Error`/`Aborted`.
- **Running tab:** `_refresh_status_tab()` (`:7435-7591`) mounts `GroupRow`
  (`:3115-3150`, renders `arrow group_name op status agents:N progress created_at`),
  expands to `AgentStatusRow`s via `_mount_group_agents()` (`:7761-7778`). Focus
  dispatch / `on_key` for Running rows at `:5837-5899` (GroupRow Enter =
  expand/collapse `:5838-5847`; AgentStatusRow `w`/`R` `:5869-5899`).
- **Launch path:** `_execute_design_op(result)` (`:8354-8368`) seeds a worker and
  calls `_run_design_op()` (`:8370-8538`), which per op-type calls
  `register_explorer/comparator/synthesizer/...` (`brainstorm_crew.py:579-703`) →
  `_run_addwork()` (`:125-175`, subprocess `ait crew addwork`), then
  `record_operation()`. **No CLI restart command** exists.
- **Config-recovery gap:** per-operation config (explore mandate, compare
  dimensions, synthesize merge-rules) is NOT in `br_groups.yaml`; it lives in
  `<agent>_input.md`. So "re-run fresh" cannot rebuild config from the group
  entry alone.
- **Retry-apply actions** (gated by t1018_1, methods retained):
  `action_retry_explorer_apply` (`:7237-7251`), `action_retry_synthesizer_apply`
  (`:7387-7398`) — both `_try_apply_*_if_needed(agent, force=True)`;
  `action_retry_initializer_apply` (`:6727-6729`).

## Implementation steps

### Step 1 — Extract a reusable, headless-testable launch helper
Pull the per-op agent-registration loop out of `_run_design_op()` (`:8401-8514`)
into a helper that takes `(op, config, subgraph, head, crew_id)` and returns the
launched agent names + records the operation. Pure-ish (subprocess via
`_run_addwork` is the side effect) — unit-test the payload assembly with the
subprocess mocked. (testing_conventions.md: pull headless units out early.)

### Step 2 — GroupRow `on_key` actions + render hints
On the Running-tab focus dispatch (`:5837-5899`), add two keys handled when a
`GroupRow` is focused (mirroring the `w`/`R`/`x` AgentStatusRow pattern):
- **Re-run whole operation fresh** — see Step 3.
- **Retry only the failed step** — see Step 4.
Pick deliverable, non-colliding keys per t1018_1's model (the Running tab uses
plain letters in `on_key`; avoid clashing with `p`/`k`/`K`/`w`/`R`/`x`/`e`/`L`).
Add the hints to `GroupRow.render()` (`:3132-3150`).

### Step 3 — "Re-run whole operation fresh" (recommended: pre-filled wizard)
- On the focused GroupRow, re-open `ActionsWizardScreen` pre-populated for
  `group_info["operation"]` at `head_at_creation`, so the user re-confirms/edits
  the recovered config, then dispatch via `_execute_design_op()`. This reuses ALL
  launch logic and is the destructive-action confirm (no missing-config problem).
- Offer to clean up the old failed group (reuse the existing `x` cleanup /
  `CleanupAgentModal` pattern, `:867`).
- Document the rejected alternative (parse `<agent>_input.md` to silently
  re-register — fragile reverse-engineering).
- **Confirm** the wizard truly supports pre-population for every op-type; if not,
  add a minimal confirm modal for the unsupported types and file a follow-up.

### Step 4 — "Retry only the failed step" (re-home retry-apply)
- Call the retained `_try_apply_explorer_if_needed` / `_try_apply_synthesizer_if_needed`
  (`force=True`) for the focused group's agents from the GroupRow `on_key` action.
- **Remove the now-dead global `ctrl+shift+x`/`ctrl+shift+y` bindings** (`:5546`,
  `:5548`) and their footer labels; keep/relocate the underlying methods. (t1018_1
  gated them and kept the methods alive specifically for this re-home.)
- Decide initializer-retry (`ctrl+r`): if it fits the GroupRow surface, re-home it
  too; otherwise leave it gated (t1018_1) and note rationale.

### Step 5 — State transition
Decide whether to add an explicit failed/aborted operation status to
`brainstorm_schemas.py` or to key purely off agent states. Prefer keying off
agent states (no schema change) unless the UI needs a group-level failed badge —
decide in-task and document. If "re-run fresh" creates a new group, ensure the
old group can be cleaned up (Step 3); if it resets the same group, transition it
back to `Waiting` and clear `nodes_created` via `update_operation`.

### Step 6 — Tests (this child owns them)
- Pure-unit: extracted launch helper (payload assembly per op-type, subprocess
  mocked); any restart/state-transition helper.
- `pilot.press(...)` on a fixture session: a `br_groups.yaml` group whose
  `<agent>_status.yaml` fixtures are in `Error` → assert "retry step" calls the
  apply path and "re-run fresh" opens the pre-filled wizard / dispatches.
- Structural/grep assertion: no `ctrl+shift+x`/`ctrl+shift+y` binding survives.

## Risk
### Code-health risk: medium
- Extracting the launch loop from `_run_design_op` (a worker-thread body) risks
  subtle threading/state differences. · mitigation: parity unit test new-vs-old
  payload; pull the helper as pure as possible.
### Goal-achievement risk: medium
- "Re-run fresh" via pre-filled wizard depends on the wizard supporting
  pre-population for all op-types. · mitigation: confirm per op-type in Step 3;
  live verification in t1018_4.

## Verification
- Pure-unit launch-helper + state-transition tests green.
- `pilot.press` GroupRow restart tests on failed-operation fixtures green.
- No global retry-apply chord survives (structural assertion).
- Full brainstorm suite green.
- Live: real session, real failed agent → re-run fresh relaunches and produces
  output; retry-step re-applies — covered by t1018_4.

## Notes for sibling tasks
- Records the extracted launch helper's signature/location for future reuse.
- Confirms whether an explicit operation failed-state was added to schemas.

## Step 9 — Post-implementation
Archive via `./.aitask-scripts/aitask_archive.sh 1018_2`. Parent stays active
until t1018_3 + t1018_4 land.
