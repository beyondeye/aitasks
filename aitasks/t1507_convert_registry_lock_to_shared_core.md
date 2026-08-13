---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1171
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-08-13 11:57
updated_at: 2026-08-13 14:37
---

## Origin

Risk-mitigation ("after") follow-up for t1496, created at Step 8d after implementation landed.

## Risk addressed

`addresses: code-health "second mutex lib beside registry_lock.sh"` — from t1496's plan:
"A second mutex lib lands beside `registry_lock.sh`, which keeps the same latent `mv` race — deliberate blast-radius containment, debt until converted. · severity: low"

The same defect is recorded in that plan's Upstream defects identified bullet:
`.aitask-scripts/lib/registry_lock.sh:52-58 — same observe-then-destruct steal shape t1496 fixed (holder observed dead, then mv acts on whatever is at the path); latent two-holder window under contention for ait projects / ait attach`.

## Goal

Convert `lib/registry_lock.sh` onto the shared `lib/stale_lock.sh` core so one mutex
implementation remains, closing registry_lock's identical latent steal race:

- `registry_lock_acquire`'s dead-holder steal renames (`mv`) a dir it observed earlier —
  the observation and the destructive act are not serialized, so a contender can displace
  a freshly re-published live lock (the exact race t1496 fixed for the gate/child locks).
- Rebuild `registry_lock_acquire` / `registry_lock_release` as wrappers over
  `stale_lock_acquire` / `stale_lock_release` (guarded `.gc` mutations, owner-token
  release, verified removals), preserving the current API and the timeout-based
  fail-safe contract (return 1 on a live holder past the deadline — never proceed
  unlocked; note stale_lock has retry-count budgets, so map timeout ≈ retries×sleep).
- Note the semantic deltas to preserve or consciously change: registry_lock steals
  dead-pid holders with NO age gate (stale_lock does the same for pid-carrying locks);
  registry_lock has no tokenless-age reclaim (its locks always carry pid files);
  registry_lock installs an EXIT trap on acquire (callers rely on it — keep that in
  the wrapper).
- Revalidate the two consumer families under contention: `ait projects` (tmux bootstrap
  bursts, t1073 scenario) and `ait attach` / artifact-manifest transactions
  (`lib/attachment_lock.sh` with_attach_lock).
- Lock paths: registry/attach locks live at fixed shared locations (e.g.
  `~/.config/aitasks/…`, data-worktree `attachments/.attach.lock`) — they are NOT
  candidates for `ait_lock_dir` per-repo scoping; only the mutex protocol converges.

## Reference

t1496's plan (`aiplans/archived/p1496_fix_gate_lock_stale_reclaim_race_and_scoping.md`
after archival) documents the protocol invariants, and `tests/test_stale_lock.sh` +
`tests/test_gate_lock_single_winner.sh` show the test patterns (deterministic
guard-replacement shims, live/dead-holder cases) to replicate for registry_lock.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T11:37:59Z status=pass attempt=1 type=human
