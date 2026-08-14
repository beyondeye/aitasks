---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1449
followup_kind: risk_mitigation
created_at: 2026-08-14 10:24
updated_at: 2026-08-14 10:24
---

## Origin

Risk-mitigation ("after") follow-up for t1510, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — min-estimator evidence gathered on one box only.

From t1510's plan `## Risk` section:

- The `min`-estimator evidence is from this box only; the real lane's scheduling
  behaviour could still differ · severity: low · → mitigation: full_suite_triple_run

## Goal

t1510 replaced the board-movement attribution negative control's contention-sensitive
median statistic with a per-span **minimum** (`tree_self_min_ms`), so that the
neighbour-localisation bound survives the suite's own `-n 4 --dist loadfile` lane.
It was verified with one full-suite run plus a targeted 4-worker lane and a pinned
2-cpu oversubscription run — all on a single box. This follow-up re-runs the exact
protocol that surfaced the original defect in t1500.

**Protocol** — on a quiet box (no other agent sessions competing for CPU):

```bash
log=$(mktemp); rm -f "$log"
for i in 1 2 3; do
  AITASK_BOARD_ATTR_VERDICT_LOG="$log" bash tests/run_all_python_tests.sh
  echo "run $i suite rc=$?"
done
total=$(wc -l < "$log")                            # MUST be 3
ok=$(grep -cE '^localised[[:space:]]' "$log")      # MUST be 3
```

**Acceptance:** exactly 3 records, all three matching `^localised[[:space:]]`, and
`PYTHON SUITE: PASSED` each time.

**Why the log rather than the suite's exit status:** pytest captures stderr for
passing tests, and an `undecidable` `skipTest` leaves the aggregate suite GREEN.
The `PYTHON SUITE:` line therefore cannot distinguish "the localisation claim was
evaluated and satisfied" from "the claim declined to evaluate" from "the test never
ran". Only the verdict log can. An `undecidable` record is **not** acceptance — it
means the precondition declined to evaluate, and t1510's design must be revisited
rather than the result recorded as a pass.

**Matcher note:** the pattern is `^localised[[:space:]]`, **not** `^localised\t`.
POSIX ERE has no `\t` escape — GNU grep warns "stray \ before t" and matches
nothing (while degrading `\t` to a literal `t`, so it spuriously matches
`localisedt`). This is pinned by `tests/test_attribution_verdict_log.sh`; do not
"simplify" it back.

If any run yields `leaked`, the attribution accounting has a real defect. If any
run yields `undecidable`, report the recorded `refocus` delta — the injected cost
is a contention-immune `time.sleep`, so that outcome would itself be new
information.
