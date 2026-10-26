---
priority: medium
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [go_engine, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 15:56
updated_at: 2026-10-26 16:35
---

## Origin

Risk-mitigation ("after") follow-up for t2148, created at Step 8d after implementation landed.

## Risk addressed

hosted-only shell/timing differences invisible on bash-/bin/sh dev boxes

- The container reproduces dash, but not the runner's exact kernel or scheduling. Another
  timing-only leak in a procsup test could still appear only on hosted runners · severity: low ·
  → mitigation: dash_parity_local_tests

## Goal

Let the Go engines suite (or at least the process-starting packages and `ci/preflight.sh`) run
under dash locally, so fork-vs-exec differences between `/bin/sh` implementations surface before a
push instead of only on GitHub-hosted runners (Ubuntu: `/bin/sh` → dash; this dev box: bash).

t2148's root cause was exactly this: `dash -c "sleep 300"` forks `sleep` instead of exec'ing it, so
a pid-only kill of the shell left `sleep` behind and hangguard reported a LEAK on every hosted run
while every local run passed.

The recipe that reproduced it (from t2148's plan,
`aiplans/archived/p2148_procsup_tests_leak_on_hosted_runner.md`):

```bash
CGO_ENABLED=0 go test -c -o <dir>/procsup.test ./internal/procsup/
docker run --rm --init -v <dir>:/t:ro -w /tmp ubuntu:24.04 /t/procsup.test -test.count=5
# race amplification: add --cpus 1 and a few `(while :; do :; done) &` busy loops
```

Options to evaluate (pick one, justify):
- a `goengines/ci/` script (e.g. `dashcheck.sh`) that builds static test binaries for every package
  whose tests start processes and runs them in `ubuntu:24.04 --init`, opt-in when docker is absent
  (report "not run", never pass);
- a `bwrap` variant that binds dash over `/bin/sh` without docker;
- a CI matrix leg is not needed for dash itself (hosted runners already are dash) — the gap is
  local feedback before the push.

Document the entry point in `goengines/README.md` (testing section) and in CLAUDE.md's Go engine
notes only if it becomes part of the routine pre-push check.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-26T14:35:29Z status=pass attempt=1 type=human
