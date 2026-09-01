---
priority: medium
effort: medium
depends: [1597]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1597]
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: manual_verification
created_at: 2026-09-01 16:47
updated_at: 2026-09-01 16:57
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1597

## Verification Checklist

- [ ] With resource_admission_command unset, pick a task and reach Step 7: nothing is displayed, nothing changes, and no .aitask-gates/<id>/ directory appears
- [ ] Point resource_admission_command at `sh -c 'echo "ADMISSION_REASON: no memory"; exit 2'`: the picked task plans to approval, parks with the reason shown, status returns to Ready, plan_approved_at is stamped, `ait ls --plan-approved` lists it, and no aitask/<task_name> branch or aiwork/ worktree exists
- [ ] Re-pick the parked task under the fast profile (plan_preference: use_current) with the hook now exiting 0: drift check -> worktree fork -> implementation, with no re-planning
- [ ] Point resource_admission_command at a missing binary (helper exit 2): the task parks with the "could not be evaluated" wording, quoting exit 127 and the log path
- [ ] Give resource_admission_command a LIST value (helper exit 3, the only path with no VERDICT: line): the same park, with the message built from DIAG:
- [ ] Confirm the deferred-plan marker survives the resource_admission park and is consumed on the admitted re-pick - the stop_reason grouping in plan-approved-stop.md is the riskiest edit in this task
- [ ] TODO: verify .aitask-scripts/settings/settings_app.py end-to-end in tmux - the new resource_admission_command row renders in `ait settings` -> Project Config, edits with the plain string editor, and saves back to project_config.yaml losslessly
