---
priority: medium
effort: medium
depends: [1104]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1104]
created_at: 2026-07-02 13:36
updated_at: 2026-07-02 13:36
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1104

## Verification Checklist

- [ ] In tmux, launch an agent and `ait minimonitor`; press `e` to spawn a shadow, and have the shadow read the followed agent (any /aitask-shadow flow) so it stamps @aitask_shadow_analyzed_at.
- [ ] Right after the shadow reads an IDLE followed agent (e.g. sitting at a plan-approval prompt), confirm NO stale warning appears (the render-jitter false-positive regression that drove the timestamp pivot).
- [ ] Make the followed agent emit new output after the shadow read it → within ~6s the `⚠ shadow feedback is stale — agent moved on (analyzed Ns ago)` line appears under the session bar.
- [ ] Confirm the concern auto-offer notification carries the "(⚠ STALE — agent moved on)" marker when stale, and the `c` concern picker shows the red "may be stale" banner.
- [ ] Kill the shadow (or with no shadow bound) → the `#mini-shadow-stale` warning line clears.
- [ ] With several followed agents in parallel, confirm each minimonitor's staleness reflects its OWN followed agent (no cross-talk).
- [ ] Confirm the staleness compare runs ~every other refresh tick (≈6s) and does not add noticeable latency.
