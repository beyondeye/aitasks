---
priority: low
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [gates, task_workflow]
verifies: ['635_15']
anchor: 635
created_at: 2026-07-01 14:54
updated_at: 2026-07-26 00:00
boardidx: 40
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
real task and the real headless lane.

Coordinate with t635_17 (autonomous-lane rigor) to avoid overlap — t635_17 owns
the auto-completion policy; this MV only verifies the stop-clean + sign + record
+ stale-repend behavior t635_15 shipped.

## Verification Checklist

- [ ] Construct a task that declares `gates: [review_approved]` (or add the gate to a
  throwaway task), on a scratch branch.
- [ ] Drive the headless lane (`aitask-pickrem`) through implementation + auto-commit;
  confirm Step 9.5 runs `ait gates run` and **stops cleanly at pending-human**
  (review_approved pending), leaving the task in-flight with the code committed
  and NO self-signalled signal.
- [ ] Run `ait gate pass <id> review_approved`; confirm the code-bound witness is
  created under `.aitask-gates/` and the orchestrator records the ledger `pass`
  with a `signed_digest:` note.
- [ ] Change a code file, hand-create/replay a witness stamped against the old
  digest, run `ait gates run`; confirm the **stale signature** re-pends (not
  pass).
- [ ] Re-sign the current state and confirm the task archives cleanly.

## Premise refresh (2026-07-26 — t635_33 active-gates model) — READ BEFORE RUNNING

This MV was written 2026-07-01 around the observation that "remote.yaml declares
no `default_gates`". **t635_33 landed 2026-07-19** and changed the mechanism:
**the steps above are not runnable as written.**

- `remote.yaml` now declares **`rendered_gates: []`** — an explicit
  render-nothing ceiling (and it still has no `default_gates` / `record_gates`).
- Under t635_33 a task's enforced set is the derived `active_gates` tuple
  materialized at claim from `declared ∩ profile ceiling`. With an empty
  ceiling, a task declaring `gates: [review_approved]` materializes
  `active_gates: []`.
- So **Step 2 cannot happen**: there is nothing to pend on, the lane will not
  stop at pending-human, and by t635_33's invariant that filtering is *correct*
  behavior ("invisible, or at most 'skipped: execution profile' — never a hard
  error"), not a defect. Steps 3-5 are unreachable in turn.

**Re-premise before running — pick one:**

1. **Run under a non-empty ceiling.** Use (or add) a headless profile whose
   `rendered_gates` / `default_gates` includes `review_approved`, so the gate
   actually enters `active_gates`. This preserves the MV's original intent —
   verifying t635_15's stop-clean / sign / record / stale-repend behavior — and
   is the recommended option.
2. **Restate it as a ceiling-filtering verification**, confirming that a
   declared gate is correctly filtered and invisible under `rendered_gates: []`.
   This is a *different* MV and would leave t635_15's behavior unverified, so
   prefer option 1 unless the filtering path is what you want covered.

**Sequencing:** run **t1224** first — it verifies the active-gates
materialization in the remote/web lane and settles exactly which empty-set
behavior is live, which determines how these steps must be restated. **t635_17**
depends on this MV's result for its auto-completion policy; see its own premise
refresh.
