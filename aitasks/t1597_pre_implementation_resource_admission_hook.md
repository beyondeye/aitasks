---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [task-workflow, execution_profiles, gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1671]
assigned_to: dario-e@beyond-eye.com
anchor: 1595
implemented_with: claudecode/opus5
created_at: 2026-08-25 10:16
updated_at: 2026-09-01 16:48
---

# Pluggable pre-implementation resource admission hook in task-workflow

## Origin

Cross-repo exploration from thinking_app (thinking_app#320, "parallel task
workflow throughput", 2026-08-25). Downstream reality: planning is cheap, but
implementation/verification phases are memory-bound (Gradle test workers at
5.75+ GiB, emulators at 2.85 GiB, a 30.7 GiB host with 4 GiB zram swap and a
recorded 2026-08-18 OOM that killed both a test worker and its agent). The
downstream repo is building a memory admission gate that can refuse
(thinking_app t221_6, modeled on its emulator pre-spawn check) — but the
framework has no seam to call it from.

## Problem

The framework performs **no resource/capacity check anywhere in the task
path**. Verified by grep across `.claude/skills/` and `.aitask-scripts/lib/`:
no `MemAvailable`, `/proc/meminfo`, `free`, `psutil`, swap or PSI probes. The
only ceilings are unrelated: docker limits for chatlink sandboxes
(`sandbox_launch.py`), `max_parallel` for gate verifiers
(`gate_orchestrator.py`), `max_concurrent` for agentcrew. Step 7's
pre-implementation guards are ownership/lock, the deferred worktree fork, and
the risk-mitigation "before" stop — nothing about whether the host can afford
the phase.

Consequence: an operator running parallel planning cannot let the workflow
itself decide "safe to start implementing now?"; the decision is manual, and a
wrong call OOMs the host mid-verification.

## Deliverable sketch (final design in planning)

- A **project-pluggable admission hook** consulted at the Step 7 seam — after
  the Checkpoint approved the plan and the Remote Drift Check returned
  "Continue anyway", **before** the deferred worktree fork / implementation
  begins. Carrier: a `project_config.yaml` key (e.g. `admission_command`,
  sibling of `verify_build`/`test_command`) and/or a profile key — planning
  decides; unset ⇒ no-op (today's behavior).
- Contract: exit 0 ⇒ proceed; refusal exit code ⇒ take the existing
  **approve-and-stop path** (`plan-approved-stop.md`: plan committed, lock
  released, status back to Ready) so the task is cleanly parked and a later
  re-pick skips planning via the existing §6.0 plan-preference route. Refusal
  is a *defer*, never a task failure; structured output (reason line) should
  surface to the user and, once thinking_app#320's counterpart exists, into
  t1595's marker/board surfaces.
- Distinguish the skip semantics from gate verifiers: this is an admission
  decision at a workflow seam, not a recorded quality gate — decide in
  planning whether it should also appear in the ledger (e.g. a `skip`/note
  entry) or stay out of it.
- Downstream wiring (the actual memory probe/thresholds) stays in the
  downstream repo (thinking_app t221_6); the framework ships only the seam, a
  documented contract, and a trivial reference example.

## Acceptance sketch

- With `admission_command` unset, workflows behave byte-identically to today.
- With a hook that refuses: a picked task plans to approval, parks cleanly at
  the seam with the refusal reason shown, and a later re-pick under
  `plan_preference: use_current` goes drift-check → worktree fork → work
  without re-planning.
- With a hook that admits: no behavioral difference beyond the one call.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T12:25:08Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-01T13:41:12Z status=pass attempt=1 type=human
