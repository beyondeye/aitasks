---
priority: medium
effort: medium
depends: [t1216_2]
issue_type: test
status: Ready
labels: [aitask_monitor, shadow, tui]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-28 11:52
updated_at: 2026-07-28 18:06
boardidx: 57344
---

## Origin

Risk-mitigation ("after") follow-up for t1216_1, created at Step 8d after
implementation landed.

## Risk addressed

From t1216_1's `## Risk` section:

- *Code-health:* "The `commit_snapshots` amendment (stamping + newer-wins merge)
  edits a per-tick hot path shared by monitor and minimonitor; a stamping error
  could silently drop shadow entries, resurrect a removed one, or corrupt the
  shadow's idle clock, with no user-visible signal until a glyph goes wrong."
- *Code-health:* "Plan review found four genuine correctness gaps in the first
  draft of this merge (undefined stamp origin, presence-vs-identity, bookkeeping
  ahead of the guards, unspecified failure policy) — evidence that this seam is
  easy to get subtly wrong and that a later edit could reintroduce any of them."
- *Goal-achievement:* "`refresh_shadow_snapshot` ships with **no production
  consumer** in this child (t1216_2's fast tick is the first). Its concurrency
  contract is proven only by scripted-coroutine unit tests, which cannot
  reproduce real event-loop interleaving, so a subtle ordering flaw could
  survive to t1216_2."

## Goal

Verify the shadow-snapshot merge contract under **real** event-loop interleaving,
once t1216_2 has wired the 0.3 s fast tick and the seam finally has a production
consumer. The unit tests in `tests/test_shadow_seam.py` script every await
deterministically, which is exactly what makes them reproducible — and exactly
why they cannot exercise genuine concurrency.

Depends on **t1216_2** — wired in `depends:` when that task landed
(2026-07-28). Its `_fast_shadow_refresh` is the production consumer that drives
`refresh_shadow_snapshot` on the 0.3 s tick, so the seam finally has real
event-loop interleaving to soak.

Scope:

- A soak/live harness driving `TmuxMonitor.refresh_shadow_snapshot` against a
  real (or realistically faked-with-jitter) capture path concurrently with the
  full `capture_all_classified_async` → `commit_snapshots` cycle, over enough
  iterations to shuffle the interleavings the scripted tests fix in place.
- Assert the five binding rules hold under that load — see the "Step 5" section
  of `aiplans/archived/p1216/p1216_1_shared_shadow_seam.md` for the authoritative
  statement of each:
  1. one total order over shadow writes, keyed by READ time;
  2. stamped per-key merge, newer read wins;
  3. existence is not identity — a rebound shadow is never overwritten by the
     pane it replaced (both the merge side and the commit side);
  4. `_apply_bookkeeping` runs only for an accepted write, so a rejected merge
     never disturbs `_last_content` / `_last_change_time`;
  5. a fast-refresh failure is "no update", never a hide.
- Assert the invariant that makes it safe: `refresh_shadow_snapshot` never bumps
  `capture_generation`, so it can never supersede a full refresh.
- Watch for the failure mode the unit tests cannot see: a shadow glyph or concern
  badge that goes stale and stays stale, or an idle clock that resets on a pane
  that did not change.

## Notes

This is **not** a duplicate of t1216_5 (the aggregate manual-verification
sibling): that one is human verification of the whole monitor-shadow feature;
this is an automated soak of one headless concurrency contract.
