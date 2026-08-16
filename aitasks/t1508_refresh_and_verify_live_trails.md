---
priority: high
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [artifacts, task_metadata]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1468_5]
assigned_to: dario-e@beyond-eye.com
anchor: 1468
followup_kind: risk_mitigation
created_at: 2026-08-13 14:02
updated_at: 2026-08-16 18:20
---

## Origin

Risk-mitigation ("after") follow-up for t1468_5, created at Step 8d after
implementation landed.

## Risk addressed

`addresses:` goal-achievement — the agent-authored snapshot producer is
undrivable by tests, and the two live artifacts stay invalid until a human
refreshes them.

From t1468_5's plan `## Risk` section:

- The trail's snapshot producer is an agent-authored skill instruction, not
  code. A schema property with a correct enum and a correct gatherer can still
  carry nothing if the writer never populates it, and no automated test can
  drive the writer — so "it works" rests on a prose contract plus manual
  verification. · severity: medium (residual) · → mitigation:
  refresh_and_verify_live_trails
- The two live trail artifacts become invalid on landing and are refreshed only
  by a human re-running the trail skill. A verbal "tell the user" instruction
  leaves nothing tracked, and t1470's acceptance criteria depend on the refresh
  having happened. · severity: medium (residual) · → mitigation:
  refresh_and_verify_live_trails

## Goal

t1468_5 bumped the implementation-trail schema to **1.1.0** (adding the optional
`entry.snapshot.followup_kind`). The trail is single-version by design, so every
stored 1.0.0 trail now fails validation as `ERROR:invalid_trail` until it is
refreshed. That is expected, not a defect.

Two things must happen here, and only a human can do them:

1. **Refresh both live artifacts** so they validate at 1.1.0 again.
2. **Inspect the stored documents** to prove the *producer* is real. This is the
   only end-to-end check that exists: the snapshot producer is an instruction in
   `.claude/skills/aitask-trail/SKILL.md.j2`, not code, so no unit test can
   drive it. The committed guards (gatherer unit test, skill-contract pin across
   all three goldens, schema round-trip) all pass against a writer that never
   populates anything.

**Both halves of the writer rule must be checked**, because the second is the
common path:

- a member task carrying a real `followup_kind` → the value is **stored** in its
  `entry.snapshot`;
- an ordinary member with no kind → the key is **absent**, never the literal
  string `unknown` or `invalid`. Those are transport sentinels, not values, and
  neither is in the schema enum — a stored sentinel would invalidate the whole
  document. Most tasks are genuine new work, so this is the majority case.

## Blocks

**t1470** (`surface_intrawave_parallel_safety_in_bytrail_view`) depends on this
task: its acceptance criteria are written against both artifacts, and until they
are refreshed the `ERROR:invalid_trail` they return is a consequence of t1468_5,
not a t1470 regression.

## Verification Checklist

- [x] `/aitask-trail refresh art:trail-gates-framework-landing` completes and the stored document reports `schema_version: "1.1.0"` — PASS 2026-08-16 18:20 auto: refresh written as v6 (sha256:90d678a0f9ee); stored doc reports schema_version 1.1.0
- [x] `/aitask-trail refresh art:trail-shadow-review-loop` completes and the stored document reports `schema_version: "1.1.0"` — PASS 2026-08-16 18:20 auto: refresh written as v5 (sha256:6c64559cd3c3); stored doc reports schema_version 1.1.0
- [x] Both artifacts end at `freshness.state: current` — neither returns `ERROR:invalid_trail` — PASS 2026-08-16 18:20 auto: both fetched docs report freshness.state=current; neither returns ERROR:invalid_trail (validated CURRENT twice pre-write)
- [x] PRODUCER, present case: a member task carrying a real `followup_kind` has that exact value stored in its `entry.snapshot.followup_kind` — PASS 2026-08-16 18:20 auto: 18 live entries store followup_kind matching the task file exactly, across 6 kinds (risk_mitigation, manual_verification, upstream_defect, review_finding, verification_failure)
- [x] PRODUCER, absent case (the common path): an ordinary member with no `followup_kind` has NO `followup_kind` key in its `entry.snapshot` — not the literal `unknown`, not `invalid` — PASS 2026-08-16 18:20 auto: 24 live entries whose task file has no followup_kind omit the key entirely; whole-document scan finds no 'unknown'/'invalid' at any nesting level
- [ ] `./.aitask-scripts/aitask_trail_gather.sh drift --trail <fetched doc>` reports `CURRENT` for both artifacts
- [ ] Re-read t1470's "Live hazard" paragraph and confirm it names this task; drop the `depends` edge only deliberately
