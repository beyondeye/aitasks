---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: review_finding
implemented_with: claudecode/opus5_5
created_at: 2026-10-14 22:01
updated_at: 2026-10-15 14:46
---

## Context

Review finding from t1985 (the hang watchdog for the runner package's
process-starting tests), dispositioned by the reviewer as a separable
follow-up.

`runChild` in `goengines/internal/testmap/runner/watchdog_unix_test.go`
captures each isolated test's subprocess output to a file, then reads the
whole file with `os.ReadFile`, converts it to a string, and only then applies
`outputCap` (64 KiB). The cap bounds the text that is reported. It does not
bound the memory used to read it. A noisy future test (heavy `t.Log`, a
runaway runner fixture writing to stdout) makes the parent allocate memory
proportional to its entire log, on every isolated test.

The full read exists for one reason: the outcome markers
(`\n--- PASS: <name> (` / `\n--- SKIP: <name> (`) are detected over the whole
output, so a PASS line beyond the cap is never mistaken for "ran no such
test".

## Goal

Read the subprocess output in a bounded way:
- scan the file incrementally for the outcome markers, across chunk
  boundaries, so a marker split between two reads is still found;
- keep only the first `outputCap` bytes (plus a `[truncated N bytes]` note) for
  the reported text;
- preserve the current outcome semantics exactly: PASS/SKIP detection over the
  whole output, the HANG/LEAK/failure/"ran no such test" problems, and the
  verbose relay.

## Verification

- A control that writes well over `outputCap` (e.g. 10 MiB) before the PASS
  line: the parent still reads it as a pass, the reported output is capped,
  and peak memory stays bounded (e.g. measure with
  `runtime.ReadMemStats` around `runChild`, or assert that no read buffer
  exceeds a small multiple of the chunk size).
- A marker straddling a chunk boundary is detected.
- `TestIsolationControls` and the full runner package stay green.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T11:45:59Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T12:01:24Z status=pass attempt=1 type=human
