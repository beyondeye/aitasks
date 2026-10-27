---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-27 08:49
updated_at: 2026-10-27 08:49
---

## Origin

Spawned from t1854_12 (M3.2i suite adapter) during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/runner/builtin/pytest_linux_test.go:827` — `TestPytestFakeEvidence` deterministically exceeds its 2 min hang guard (`HANG:TestPytestFakeEvidence|2m0s`) under `go test -race`. It stops in the final `noitems` / writer-less-FIFO `Load` phase, after the `nullmessage` subtest. Without `-race` the whole test takes 0.5 s. It reproduces on a pristine `git archive HEAD` export (main `65c887ba9`, which predates t1854_12). The root cause is not proven.

## Diagnostic context

- Found while verifying t1854_12: `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1 go test -race -count=1 -timeout 45m ./internal/testmap/runner/builtin/` failed only on this test. The run's leftover processes were `builtin.test` ×2, killed by the guard.
- It reproduced three times, each at the same point:
  - with the run alone;
  - with only this test (`-run TestPytestFakeEvidence`) on the current tree;
  - on a pristine HEAD export without any suite files.

  Host load averaged about 6–8 from other sessions.
- All 12 `t.Run` modes (`stale` … `nullmessage`) start, and their non-race runs take about 0.03 s each. The hang follows them, in the test's tail (`pytest_linux_test.go` around 850–859):
  - `AIT_TEST_FAKE=noitems` → `loadErr(t, r, "no items record")`;
  - `AIT_TEST_FAKE=fifo` → `loadErr(t, r, "not a regular file")`, with its own 30 s bound.
- The FIFO case comes from t1854_9's Change Request 2: `pytestReadOwn` opens with `O_RDONLY|O_NONBLOCK|O_NOFOLLOW`. Its archived plan (`aiplans/archived/p1854/p1854_9_m3_2f_pytest_adapter.md`) records CR2's verification as preflight + builtin/cmd + `ait engine test`, with **no `-race` rerun**. The earlier race-green figure (builtin 666 s) predates CR2.
- Unknown: which of the two tail Loads blocks, and whether it is the adapter (`pytestReadOwn` / the fake's `mkfifo`) or the test harness. Start by running the test under `-race` with `-v` plus a goroutine dump at the guard (`SIGQUIT` output is in the hang report), and bisect the tail.

## Suggested fix

Find which tail phase blocks under `-race` (likely the writer-less FIFO path), fix the open or read so it cannot block, then rerun `go test -race` on the builtin package to green. Add a race-mode note to the pytest README row if the fix is environment-specific.
