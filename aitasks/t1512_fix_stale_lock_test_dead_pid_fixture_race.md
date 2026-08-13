---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1171
followup_kind: upstream_defect
created_at: 2026-08-13 15:52
updated_at: 2026-08-13 21:24
---

## Origin

Spawned from t1507 during Step 8b review.

## Upstream defect

- `tests/test_stale_lock.sh:111-113` — the dead-PID fixture is built as
  `sleep 60 &` / `kill "$dead_pid"` / `wait "$dead_pid"`. The `kill` fires
  microseconds after `&`, inside bash's fork→exec window, where the signal can
  be lost. The `wait` is load-bearing — only reaping makes the PID answer
  `kill -0` with failure, since a zombie still answers success — so when the
  signal is dropped the suite blocks for the child's full 60 s. It currently
  passes only by scheduling luck.

This is the same construction t1507 removed from `tests/test_registry_lock.sh`
(case 3, unmodified since t1073), where it was observed live: the suite took
2 m 4 s wall with 0.2 s of CPU, and a `PS4='+ $EPOCHREALTIME '` trace showed a
60.0 s gap immediately after `kill`/`wait`. A tree-wide sweep at that time found
`tests/test_stale_lock.sh:111` as the one remaining genuine instance.

## Diagnostic context

From t1507's plan (`## Final Implementation Notes`, "Issues encountered"): the
hang was not caused by the registry_lock → stale_lock conversion. The conversion
merely shifted timing enough to lose the race that had always been present. The
tell was near-zero CPU against multi-minute wall time, which rules out spinning
and points at a blocked `wait`.

## Suggested fix

Replace the construction with the helper t1507 introduced:

```bash
# A PID that has already exited AND been reaped: command substitution waits for
# the child, so there is no zombie and no signal to lose.
dead_pid_fixture() { bash -c 'echo $$'; }
```

Then re-sweep `tests/` for `sleep N &` followed within a few lines by `kill`,
since the shape travels in families. Note that a naive grep also matches prose
in comments — verify each hit is executable code.
