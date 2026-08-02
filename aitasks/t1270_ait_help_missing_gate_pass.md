---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [gates, cli]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-07-27 23:27
updated_at: 2026-07-27 23:27
boardidx: 220
---

## Problem

`ait gate pass <task-id> <gate>` is dispatched (`ait:320` → `aitask_gate_pass.sh`)
and is the HUMAN's tool for signing an async human gate (t635_15) — but it is
missing from the top-level `show_usage` "Gates:" list (`ait:51-58`), so
`ait --help` never advertises it. The neighbouring `gate append` / `gate fail` /
`gate log` are all listed.

Found while adding `gates sync-registry` to the same usage block (t635_34); left
unfixed there because it is unrelated to that task's surface.

## Fix

Add one line to the "Gates:" section of `show_usage` in `ait`, matching the
block's fixed 15-character verb padding:

```
  gate pass      Sign a human gate (writes the code-bound witness)
```

Place it with the other `gate ` verbs. Note `ait gate --help` (`ait:323`) DOES
already document `pass`; only the top-level usage omits it.

## Verification

- `./ait --help` lists `gate pass` under "Gates:".
- Column alignment matches the surrounding entries.
- `bash tests/test_gate_cli_wiring.sh` still passes.
