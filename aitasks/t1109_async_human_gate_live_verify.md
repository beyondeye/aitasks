---
priority: low
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [gates, task_workflow]
verifies: [t635_15]
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-01 14:54
updated_at: 2026-08-04 12:53
boardidx: 121856
---

## Origin

Risk-mitigation ("after") follow-up for t635_15 (async human gates), created at
Step 8d after implementation landed.

## Risk addressed

Goal-achievement: the headless run-gates + stop-clean path is dormant by default
(no shipped profile renders `review_approved`), so it was validated against a
constructed fixture rather than a live autonomous run.

## Goal

Autonomous manual-verification of the end-to-end async human-gate flow against a
real task and the real headless lane.

Coordinate with t635_17 (autonomous-lane rigor) to avoid overlap — t635_17 owns
the auto-completion policy; this MV only verifies the stop-clean + sign + record
+ stale-repend behavior t635_15 shipped.

## Premise: resolved 2026-08-04 (t1224 complete)

This task was written 2026-07-01, then blocked 2026-07-26 when t635_33's
active-gates model made its original steps unrunnable. **t1224 ran and archived
2026-08-04** and settles the open question. The checklist below has been
restated accordingly and is now runnable as written — the 2026-07-26 "pick one
of two options" note is retired.

**What t1224 found** (evidence: `aiplans/archived/p1224_manual_verification_auto.md`):
the `remote` profile's `rendered_gates: []` ceiling filters a declared gate down
to an enforced `active_gates: []` on both the pickrem claim path and the
web-merge marker path, and that filtering is *correct* behavior, not a defect.
So the empty-ceiling case is already covered — the former "option 2" (restating
this MV as a ceiling-filtering verification) is now redundant and is dropped.

**Resolution — former "option 1".** This MV runs under a **non-empty ceiling**
so `review_approved` genuinely enters `active_gates`, preserving the original
intent of verifying t635_15's stop-clean / sign / record / stale-repend
behavior.

**No shipped profile can host this run** — the ceiling is `rendered_gates` when
that key is present (even `[]`), else `default_gates`, else `[]`
(`gate_ledger.py:605-623`), which gives: `default` → `[]` (neither key),
`fast` → `[risk_evaluated]`, `remote` → `[]`. None contains `review_approved`.
Step 1 below therefore **creates** a throwaway profile rather than selecting an
existing one.

**The profile must be headless.** `review_approved` is a dual-transport gate
(`gates.yaml:190-201`): an attended session records the pass directly from the
interactive Step 8 review approval, and only the headless lane pends and waits
for a signature. Running this under an attended profile would record the pass
through the wrong transport and verify nothing.

## Verification Checklist

- [ ] **Setup — throwaway headless profile with a non-empty ceiling.** Create
  `aitasks/metadata/profiles/local/gatetest_async_human.yaml` as a copy of
  `remote.yaml` with `name: gatetest_async_human` and `rendered_gates:
  [review_approved]` (keep `headless: true`). Confirm
  `./.aitask-scripts/aitask_scan_profiles.sh` lists it as
  `local/gatetest_async_human.yaml`. Both `profiles/local/` and
  `.aitask-gates/` are gitignored, so this run leaves no repo trace.
- [ ] **Precondition — the gate actually enters the active set.** Create a
  throwaway task declaring `gates: [review_approved]`
  (`aitask_create.sh --batch … --gates review_approved --commit`). Before
  claiming, confirm the negative control `aitask_gate.sh archive-ready <id>` →
  `BLOCKED:review_approved`. Then run `aitask_gate.sh materialize-active <id>
  --profile aitasks/metadata/profiles/local/gatetest_async_human.yaml` and
  confirm `MATERIALIZED:review_approved`, with frontmatter `active_gates:
  [review_approved]` and `active_gates_profile: gatetest_async_human`. **If this
  materializes `[]`, stop — the ceiling is wrong and every step below is
  unreachable.** This is the precondition the pre-t635_33 checklist silently
  assumed.
- [ ] **Stop-clean at pending-human.** Drive the headless lane
  (`/aitask-pickrem <id>`) through implementation + auto-commit. Confirm Step 9.5
  runs `ait gates run`, reports `review_approved: pending`, and **stops cleanly**:
  task left in-flight (`Implementing`), code committed, **not** archived and
  **not** pushed, and **no** witness file at
  `.aitask-gates/t<id>/review_approved.signed` — the agent must never self-signal.
- [ ] **Sign and record.** Run `ait gate pass <id> review_approved`. Confirm the
  witness is created at `.aitask-gates/t<id>/review_approved.signed` carrying a
  `code_digest=` line matching the current code state, and that the orchestrator
  records a ledger `pass` with a `signed_digest:<digest>` note
  (`gate_orchestrator.py:432`).
- [ ] **Stale signature re-pends.** Change a **code** file — not anything under
  `aitasks/` or `aiplans/`, which are excluded from the digest so ledger appends
  do not flip it (`gate_orchestrator.py:79`). Then rewrite the witness so its
  `code_digest=` line holds a **wrong (old) value**, and run `ait gates run <id>`.
  Confirm it re-pends rather than passing, with the note `stale signature: signed
  against <old>, code now <new> — re-sign with 'ait gate pass'`. **The witness
  must carry a wrong digest, not no digest:** an *unstamped* witness is accepted
  as a pass for backward compatibility (`gate_orchestrator.py:406-408,419`), so a
  merely touched/empty file would pass and this check would silently fail to
  discriminate.
- [ ] **Re-sign and archive.** Run `ait gate pass <id> review_approved` against
  the current state, confirm `aitask_gate.sh archive-ready <id>` → `ALL_PASS`,
  and confirm the task archives cleanly (exit 0, no `GATE_PENDING`).
- [ ] **Cleanup.** Remove the throwaway profile
  (`aitasks/metadata/profiles/local/gatetest_async_human.yaml`), the
  `.aitask-gates/t<id>/` witness directory, and any scratch code file touched in
  the stale-signature step. The throwaway task is removed by its own archival in
  the previous step.

## Sequencing

**t1224 — done** (archived 2026-08-04); its result is folded into the premise
section above. **t635_17** depends on this MV's result for its auto-completion
policy; see its own premise refresh.
