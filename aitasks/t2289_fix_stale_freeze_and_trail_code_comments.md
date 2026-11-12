---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2258
followup_kind: upstream_defect
created_at: 2026-11-12 23:18
updated_at: 2026-11-13 01:14
---

## Origin

Spawned from t2258_9 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_freeze.py:13` — the module docstring says reconcile is "run after every freeze", but no freeze or restore path calls it (only the CLI verb, agent_freeze.py:1983, and `monitor_shared.py:1719` do).
- `.aitask-scripts/monitor/monitor_shared.py:1675-1678` — the docstring says "the coordinator runs it after every freeze/restore"; the same false claim.
- `.aitask-scripts/aitask_session_hook.sh:67` — the comment says the freeze-time Codex session capture is "Linux only", but `lib/agent_sessions.py` (t2048) and the docs (development/framework-session, commands/setup-install) cover Linux and macOS.
- `.aitask-scripts/lib/implementation_trail.schema.json:95` — the `digest` description lists "boardcol/boardidx presence", but the digest in `lib/trail_gather.py:487-495` does not include them. The docs are right ("board column and position are not part of a trail's freshness"); the schema text is stale.

## Diagnostic context

t2258_9 audited the Parallel (local) workflow pages and checked every moved fact against the code. Two independent survival agents and a review agent confirmed that reconcile's only callers are the `reconcile` verb and the monitor maintenance pass (first at 60 s, then every 600 s: monitor_shared.py:496, 511). The docs were corrected (development/framework-session § The freeze engine, § Cleanup rules), but these comments still carry the old claim, which a future doc writer could copy back. The trail-schema mismatch surfaced while verifying "moving cards never stales a trail".

## Suggested fix

Comment and description text only: reword the two reconcile docstrings to name the real callers, update the hook comment to "Linux and macOS" (after checking agent_sessions.py), and drop "boardcol/boardidx presence" from the schema description (or add them to the digest, if that was the intent — check trail_gather.py history first). No behaviour change.
