---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent]
gates: [risk_evaluated]
anchor: 1171
followup_kind: upstream_defect
created_at: 2026-08-11 18:51
updated_at: 2026-08-11 18:51
---

## Origin

Spawned from t1207 during Step 8b review. t1207 made eleven test files actually
enforce their assertions; both defects below were invisible until then, or were
surfaced while triaging its regression sweep.

This task also **absorbs t1207's confirmed `after` risk-mitigation
`triage_enforced_crew_test_failures`** (per user decision at Step 8d): that
mitigation existed to repair whatever genuine failures the new enforcement
exposed, and exactly one surfaced — defect 1 below. It is recorded here rather
than spawned as a second task covering the same defect.

## Upstream defect

- `.aitask-scripts/aitask_brainstorm_archive.sh:74 — the NO_PLAN fallback greps finalize's output for "has no plan_file", a string that exists nowhere in the codebase except that grep; finalize_session (brainstorm_session.py:375-421) raises only "No HEAD node set — cannot finalize." and the module-sync message, so the branch is unreachable and `ait brainstorm archive` never warns on a no-plan session. Newly visible because test_brainstorm_cli.sh's assertion is now enforced; that file is left red on purpose.`
- `tests/test_gate_lock_characterization.sh:1 — hard-coded lock paths (/tmp/aitask_gate_lock_987652, _987654, _987657) and fixed task ids make two concurrent runs of the file collide, each treating the other's lock as foreign; fails 4/4 concurrently, passes 8/8 sequentially. Pre-existing, unrelated to t1207.`

## Diagnostic context

**Defect 1 — unreachable NO_PLAN branch.** `tests/test_brainstorm_cli.sh` Test 11
("brainstorm archive handles no-plan HEAD gracefully") asserts the archive
output contains `NO_PLAN`. That assertion has been failing since it was written;
nothing noticed, because the file's footer read an orphaned `COUNTER_FILE` and
the script exited 0 regardless. With t1207's fix the file now exits 1 and the
failure is visible. It was deliberately **not** silenced: the assertion is
reporting something true.

The shell guard:

```bash
finalize_output=$("$PYTHON" .../brainstorm_cli.py finalize --task-num "$TASK_NUM" 2>&1) || {
    if echo "$finalize_output" | grep -q "has no plan_file"; then
        warn "HEAD node has no plan file — skipping plan finalize"
        echo "NO_PLAN"
    else
        die "Failed to finalize session: $finalize_output"
    fi
}
```

`grep -rn 'has no plan_file' .aitask-scripts/` returns exactly one hit: the grep
itself. So either the Python error message was changed without updating the
guard, or finalize now succeeds for a no-plan session and the NO_PLAN concept is
obsolete. Decide which before fixing — the fix is either the trigger string, or
removing the branch and the test's expectation together.

Same defect class as the "fallback needs a reachable trigger" pattern: a
recovery branch whose trigger condition can no longer occur is dead code that
reads as working.

**Defect 2 — lock-test isolation.** Found while triaging the single `CHANGED:`
line in t1207's 245-file regression sweep. Evidence: identical code produced
rc=1/2-fails then rc=0/0-fails back-to-back; 8 sequential runs passed (5 on the
new asserts.sh, 3 at HEAD); 4 concurrent runs failed 4/4 with assertions like
"die leaves the foreign lock dir intact (dir not found: /tmp/aitask_gate_lock_987652)"
and "2 contenders through a stale lock -> 2 ledger blocks (expected '2', got '1')".
Two simultaneous runs of the file share the same fixed lock directories, so each
sees the other's lock as the "foreign" lock its characterization asserts about.

This matters beyond flakiness: the repo runs several coding agents on one box,
and `tests/run_all_python_tests.sh:38-43` already records that `tests/*.sh` owns
the real git index, so concurrent test execution is a real condition.

## Suggested fix

- **Defect 1:** determine the intended behaviour for a no-plan session first
  (does finalize succeed, or should it fail?), then align the three sites —
  `finalize_session`'s error, the shell guard's trigger string, and Test 11's
  expectation. Do not fix by deleting the assertion.
- **Defect 2:** derive the lock paths and task ids from `$$` or a `mktemp -d`
  per run instead of fixed constants, so two concurrent runs cannot collide.
