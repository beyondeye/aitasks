---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [claudeskills]
created_at: 2026-06-03 09:39
updated_at: 2026-06-03 09:39
boardidx: 30
boardcol: now
---

## Origin

Spawned from t778 during Step 8b review.

## Upstream defect

- `tests/test_codeagent.sh:30` — `assert_contains` (and `assert_not_contains`
  at :41) implement the match with `echo "$actual" | grep -qi "$expected"`.
  Because the `grep` call has no `--` end-of-options guard, any needle that
  begins with `-` or `--` is misparsed as a grep option rather than a search
  string. Result: `assert_contains "... --print ..."` errors out and reports a
  false FAIL, while `assert_not_contains "--print"` errors out and reports a
  false PASS (silently masking a real regression).

## Diagnostic context

While adding Test 11e in t778 (asserting `claudecode batch-review` gates
`--print` behind `--headless`), the assertion `assert_contains "... adds
--print" "--print" "$output"` failed even though the dry-run output plainly
contained `--print`. Root cause was the unguarded `grep` in the assert helper.
t778 worked around it by switching the test needles to dash-free forms
(`print` / `print review-me`), but the helper itself remains fragile: future
tests that legitimately need to assert on flag strings will hit the same trap,
and `assert_not_contains` failures are especially dangerous because they pass
silently.

## Suggested fix

Add a `--` end-of-options guard to the grep calls (e.g.
`grep -qi -- "$expected"`), or switch to a pure-bash substring test
(`[[ "$actual" == *"$expected"* ]]`, with a `tr` to lowercase if the
case-insensitive behavior must be preserved). Audit other test files in
`tests/` for the same unguarded-grep assert pattern and fix uniformly.
