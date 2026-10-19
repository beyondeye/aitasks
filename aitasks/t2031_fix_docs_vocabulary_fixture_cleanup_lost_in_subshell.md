---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1989
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 01:29
updated_at: 2026-10-19 09:29
---

## Origin

Spawned from t2023 during Step 8b review.

## Upstream defect

- `tests/test_docs_vocabulary_coverage.sh:71` — `make_fixture` appends its dir to `CLEANUP_DIRS`, but it is always called as `$(make_fixture)` (lines 120, 137, 156). The append dies with the subshell, so the EXIT cleanup never sees the fixtures, and each run leaks about 12 fixture repos into TMPDIR.

## Diagnostic context

From t2023's Final Implementation Notes:

- t2023 ran its bundle-related bash suites with a per-suite probe `TMPDIR` to measure leftovers. `test_docs_vocabulary_coverage.sh` passed, but left 12 `tmp.*` dirs behind.
- Each leftover is one of the test's own fixture roots. They hold `AGENTS.md`, `.agents/`, and the other files the scanner reads; they are not archive extraction dirs.
- `make_fixture` runs `dir="$(mktemp -d)"; CLEANUP_DIRS+=("$dir")` and then echoes `$dir`. Its callers capture that with `FIXTURE="$(make_fixture)"` / `dir="$(make_fixture)"`, so the array append happens only in the command-substitution subshell. The file's `trap cleanup EXIT` iterates over a `CLEANUP_DIRS` that never received the entries.
- This is the same `$( )` state-loss class t2023 fixed in `lib/archive_utils.sh`: state set inside a command substitution never reaches the parent shell.

## Suggested fix

Have `make_fixture` set a result variable instead of echoing (e.g. `make_fixture; FIXTURE="$_FIXTURE_DIR"`), or register the dir in the parent after the call (`dir="$(make_fixture)"; CLEANUP_DIRS+=("$dir")`). Then re-run the test with a probe `TMPDIR` and confirm nothing is left.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T06:29:22Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-19T06:38:24Z status=pass attempt=1 type=human
