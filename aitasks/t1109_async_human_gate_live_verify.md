---
priority: low
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [gates, task_workflow]
verifies: [635_15]
anchor: 635
created_at: 2026-07-01 14:54
updated_at: 2026-07-01 14:54
---

## Origin

Risk-mitigation ("after") follow-up for t635_15 (async human gates), created at
Step 8d after implementation landed.

## Risk addressed

Goal-achievement: the headless run-gates + stop-clean path is dormant by default
(remote.yaml declares no `default_gates`), so it was validated against a
constructed fixture rather than a live autonomous run.

## Goal

Autonomous manual-verification of the end-to-end async human-gate flow against a
real task and the real headless lane:

1. Construct a task that declares `gates: [review_approved]` (or add the gate to a
   throwaway task), on a scratch branch.
2. Drive the headless lane (`aitask-pickrem`) through implementation + auto-commit;
   confirm Step 9.5 runs `ait gates run` and **stops cleanly at pending-human**
   (review_approved pending), leaving the task in-flight with the code committed
   and NO self-signalled signal.
3. Run `ait gate pass <id> review_approved`; confirm the code-bound witness is
   created under `.aitask-gates/` and the orchestrator records the ledger `pass`
   with a `signed_digest:` note.
4. Change a code file, hand-create/replay a witness stamped against the old
   digest, run `ait gates run`; confirm the **stale signature** re-pends (not
   pass).
5. Re-sign the current state and confirm the task archives cleanly.

Coordinate with t635_17 (autonomous-lane rigor) to avoid overlap — t635_17 owns
the auto-completion policy; this MV only verifies the stop-clean + sign + record
+ stale-repend behavior t635_15 shipped.
