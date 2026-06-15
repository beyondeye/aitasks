---
priority: high
effort: high
depends: [t635_2]
issue_type: feature
status: Implementing
labels: [gates, task_workflow, crash_recovery]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 18:53
updated_at: 2026-06-15 10:55
---

## Context

Phase 2 of `aidocs/gates/integration-roadmap.md` — the #1 priority pain
point (decision D3): resuming a half-done task (crash, session loss,
multi-day work, gates left pending at workflow end) should skip what is
already done and continue from the first unmet checkpoint. Today re-entry
state lives only in the conversation; the existing crash-recovery procedure
covers only the lock-reclaim case.

## Scope

- task-workflow Step 3 learns to read the Gate Runs ledger (recorded by
  t635_2): a task with ledger entries + status Implementing resumes at the
  right step instead of restarting at planning — e.g. "review approved,
  merge pending" lands directly in the Step 9 region.
- Generalize the existing crash-recovery procedure
  (`.claude/skills/task-workflow/crash-recovery.md`) to use the ledger as
  its source of truth where applicable.
- Re-entry must respect the framework doc's derivation rule (scan
  back-to-front, first block per gate/checkpoint name = current state).
- Regenerate goldens + `aitask_skill_verify.sh` in the same commit.

## Out of scope

The standalone resume skill (t635_6) and pick integration (t635_7) — this
child makes task-workflow itself re-entrant when it is (re)entered with an
in-flight task.

## Coordination (from t635_4)

Gate-guarded archival (t635_4) landed: when Step 9 archival is deferred because a
declared gate is not yet `pass`, the task stays **`Implementing`** with its
`## Gate Runs` ledger entries and its **lock held** — that state IS the in-flight
resume signal this task keys on. t635_4 deliberately does NOT touch lock/resume
semantics (it leaves the lock held and defers); generalizing crash-recovery to be
ledger-driven and deciding lock handling on resume are THIS task's job. The
all-gates-pass archival is already handled by t635_4 (Step 9 immediate offer +
Step 3 Check 4 backstop) — re-entry should resume from the first unmet
checkpoint, not re-archive. See `aidocs/gates/gate-guarded-archival.md`.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 2)
- `aidocs/gates/aitask-gate-framework.md` ("Decision tree (re-entry)",
  "Re-entry contract")

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T10:05:46Z status=pass attempt=1 type=human
