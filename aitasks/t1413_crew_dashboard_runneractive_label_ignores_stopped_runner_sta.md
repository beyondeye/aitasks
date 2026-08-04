---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, agentcrew]
anchor: 1046
created_at: 2026-08-04 17:28
updated_at: 2026-08-04 17:28
---

## Problem

`get_runner_info` (`.aitask-scripts/agentcrew/agentcrew_runner_control.py:49-67`)
decides runner liveness from **heartbeat age alone**:

```python
elapsed = _elapsed_since(str(hb)) if hb else None
stale = elapsed is None or elapsed > RUNNER_STALE_SECONDS   # 120s
```

It never reads the file's own `status:` field. A runner that shut down cleanly
writes `status: stopped` with a **fresh** `last_heartbeat` (`write_runner_alive`,
`agentcrew_runner.py:232-251`, called at runner.py:790 / 953), so for the next
~2 minutes the dashboard renders it as live:

```
killlive  killlive  Aborted  ░░░░░░░░░░░░░░░ 0%  Agents: 1  Runner active (omg16, 5s ago)
```

Observed directly during t1046 verification: `_runner_alive.yaml` said
`status: stopped`, the CrewCard said `Runner active`.

## Why it matters

This is a **second, divergent definition of "runner is live"** alongside
`agentcrew_utils.runner_is_live` (`agentcrew_utils.py:168-179`), added by t1041:

| predicate | reads `status:` | heartbeat window |
|---|---|---|
| `runner_is_live` (rollup gate) | yes — must be `running` | `RUNNER_LIVE_STALE_SECONDS = 180` |
| `get_runner_info` (display) | **no** | `RUNNER_STALE_SECONDS = 120` |

Two predicates, two thresholds, one concept — so the crew status and the runner
label on the *same* CrewCard can disagree about whether a runner is running. The
rollup side is correct; the display side is the one that lies.

## Suggested fix

Have `get_runner_info` treat `status != "running"` as not-live (report
`stale`/stopped) rather than inferring purely from heartbeat age — ideally by
delegating to `runner_is_live`, or by extracting one shared liveness predicate
both call. If the two thresholds must stay distinct, name and document why;
otherwise collapse them onto one constant.

## Acceptance criteria

- A `_runner_alive.yaml` with `status: stopped` and a fresh heartbeat is NOT
  rendered as "Runner active" by `CrewCard` or the detail runner bar.
- `status: running` + fresh heartbeat still renders as active (no regression).
- `status: running` + heartbeat older than the threshold still renders stale.
- The liveness rule lives in one place (or the two-threshold split is documented
  with its rationale).
- Regression test covering the `stopped`-with-fresh-heartbeat case.

## Provenance

Found during t1046 (manual verification of t1041). Pre-existing — t1041 added
`runner_is_live` but did not touch `get_runner_info`. Display-only; does not
affect the crew status/progress rollup, which verified correct.
See `aiplans/archived/p1046_manual_verification_auto.md` ("Upstream defects
identified").
