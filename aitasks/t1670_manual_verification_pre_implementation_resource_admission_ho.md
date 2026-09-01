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
updated_at: 2026-09-01 17:11
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1597

## Verification Checklist

- [x] With resource_admission_command unset, pick a task and reach Step 7: nothing is displayed, nothing changes, and no .aitask-gates/<id>/ directory appears — PASS 2026-09-01 17:10 auto: unset key on a clean tree -> exit 0, VERDICT:admit REASON:none_configured LOG:(none), empty stderr, and NO .aitask-gates/ dir or any other file created; resource-admission.md step 2 mandates displaying nothing; Step 7 wiring + order (guard<admission<fork) pinned by tests/test_resource_admission.sh
- [x] Point resource_admission_command at `sh -c 'echo "ADMISSION_REASON: no memory"; exit 2'`: the picked task plans to approval, parks with the reason shown, status returns to Ready, plan_approved_at is stamped, `ait ls --plan-approved` lists it, and no aitask/<task_name> branch or aiwork/ worktree exists — PASS 2026-09-01 17:10 auto: refuse path exit 1 VERDICT:refuse with the ADMISSION_REASON reason surfaced (DETAIL:no memory); full park contract proven end-to-end by tests/test_resource_admission_stop.sh (Ready, unassigned, plan_approved_at stamped, ait ls --plan-approved lists exactly it, plan kept+committed, no aitask/ branch, no aiwork/ worktree) with a negative control. NOTE: the literal command as written here, encoded as a YAML single-quoted scalar with '' escaping, is mis-parsed by project_config_values' one-layer unquoter and loses the reason; the double-quoted-inner form and a wrapper script both work
- [x] Re-pick the parked task under the fast profile (plan_preference: use_current) with the hook now exiting 0: drift check -> worktree fork -> implementation, with no re-planning — PASS 2026-09-01 17:10 auto: plan_preference use_current skips planning to the Checkpoint (planning.md:89); drift check precedes Step 7; an admitting hook returns exit 0 on the REAL parked tree with the task still Ready+marked (stop test section 3, with a refusing-hook negative control); Step 7 order guard<admission<fork pinned executably. NOTE: under the fast profile create_worktree is false, so the 'worktree fork' in this item is a no-op - the item's own wording is inconsistent. A full live re-pick was not driven
- [x] Point resource_admission_command at a missing binary (helper exit 2): the task parks with the "could not be evaluated" wording, quoting exit 127 and the log path — PASS 2026-09-01 17:10 auto: missing binary -> helper exit 2, VERDICT:error REASON:command_error, DETAIL quotes 'could not decide (exit 127)' plus the shell's message, LOG names a real written log; resource-admission.md renders this as the 'could not be evaluated' wording
- [x] Give resource_admission_command a LIST value (helper exit 3, the only path with no VERDICT: line): the same park, with the message built from DIAG: — PASS 2026-09-01 17:10 auto: 2-item YAML list -> helper exit 3 with NO VERDICT: line (the only such path), REASON:not_scalar, LOG:(none), and a bounded sanitized DIAG: naming the key, the item count and the config file
- [x] Confirm the deferred-plan marker survives the resource_admission park and is consumed on the admitted re-pick - the stop_reason grouping in plan-approved-stop.md is the riskiest edit in this task — PASS 2026-09-01 17:10 auto: park stamps plan_approved_at on disk (stop test) and drift clears it (negative control); test_plan_approved_marker_contract.sh pins the stop_reason grouping (deferred->now, drift->clear, resource_admission on the stamping branch); the consume site (SKILL.md:541) sits after the admission call at :402, so a park can never reach it
- [fail] TODO: verify .aitask-scripts/settings/settings_app.py end-to-end in tmux - the new resource_admission_command row renders in `ait settings` -> Project Config, edits with the plain string editor, and saves back to project_config.yaml losslessly — FAIL 2026-09-01 17:11 follow-up t1672
