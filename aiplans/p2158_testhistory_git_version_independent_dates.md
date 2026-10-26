---
Task: t2158_testhistory_git_version_independent_dates.md
Base branch: main
Output branch: main
---

# t2158 — TestHistory: git-version-independent commit-date assertion

## Context

`goengines/internal/testmap/fixture/fixture_test.go:48-51` asserts the fixture's
commit dates by string-matching `git log --format=%cI` against
`2026-01-01T00:00:00Z\n2026-01-01T00:01:00Z\n`. git 2.43 (Ubuntu 24.04 stock)
renders a zero UTC offset as `+00:00`; newer git (2.56 here, PPA git on the
hosted runners) renders `Z`. The fixture dates are correct (fixture.go sets
`GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` from `Epoch + ticks·1min`), so only
the assertion is version-dependent. t2154 worked around it by pinning PPA git
in the dashcheck image; the test should simply not care.

Blast radius: this is the only `%cI`/`%aI` consumer in `goengines/` (grep of
`format=%`, `%cI`, `%aI`, `--date` over all Go files — production code uses
none). No other file changes.

## Implementation

Single file: `goengines/internal/testmap/fixture/fixture_test.go`.

Replace lines 48-51 with a Unix-seconds comparison derived from `Epoch`
(no hardcoded date string, and all three commits checked instead of a
two-line prefix):

```go
	// %ct is Unix seconds, which every git version renders the same way; %cI
	// writes a UTC offset as "Z" or "+00:00" depending on the git version.
	dates := r.Run(t, "log", "--format=%ct", "--reverse")
	var wantDates strings.Builder
	for i := range 3 {
		fmt.Fprintf(&wantDates, "%d\n", Epoch.Add(time.Duration(i)*time.Minute).Unix())
	}
	if dates != wantDates.String() {
		t.Fatalf("commit dates %q, want %q (Epoch + 1 min per commit)", dates, wantDates.String())
	}
```

Imports: add `fmt` and `time` (both stdlib; `Epoch` is in the same package).
`for i := range 3` is fine — go.mod declares `go 1.26.0`.

## Verification

1. Host (git 2.56): `cd goengines && go test -count=1 -run TestHistory ./internal/testmap/fixture/` → ok.
2. Full package + vet: `cd goengines && go vet ./internal/testmap/fixture/ && go test -count=1 ./internal/testmap/fixture/`.
3. Stock git 2.43: run the package's tests in the existing local image
   `ait-dashproto:1` (ubuntu:24.04, `git version 2.43.0` — checked), mounting the
   host Go toolchain/module cache read-only exactly as `goengines/ci/dashcheck.sh`
   does (lines 135-140), with a scratch GOCACHE and `-count=1`, offline:
   - **red control**: the pre-change test (from `git show HEAD:…` into a scratch
     copy of the module) fails with `dates "...+00:00..."` under 2.43;
   - **green**: the changed test passes under 2.43.
4. **Mutants** (scratch copy only; each applied alone, `Epoch` and the test's
   expectation left untouched). Shifting `Epoch` itself would prove nothing: the
   producer (`CommitMessage`) and the expectation both derive from it, so they
   move together and the test stays green. The mutants therefore perturb only
   the producer side, the `when` computation in `CommitMessage` (fixture.go:132):
   - offset: `Epoch.Add(time.Duration(r.ticks)*time.Minute + time.Second)` →
     TestHistory must fail on every commit's date;
   - step: `time.Duration(r.ticks) * time.Second` (wrong spacing, first commit
     still correct) → TestHistory must fail, which shows the check covers
     later commits and the spacing, not only the anchor date.
   Each mutant is applied with an exact-string replacement that asserts it hit
   (grep the mutated line before running), so a no-op mutation cannot pass as
   "detected".
5. `bash goengines/ci/dashcheck.sh -run TestHistory ./internal/testmap/fixture/` → `DASHCHECK:PASS`.

## Step 9

Commit `test: Make TestHistory's commit-date check git-version independent (t2158)`,
then post-implementation archival per task-workflow Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `TestHistory` (goengines/internal/testmap/fixture/fixture_test.go) now reads `git log --format=%ct --reverse` and compares it exactly against `Epoch + i·1min` (Unix seconds) for all three commits, built from `fixture.Epoch`; `fmt` and `time` imports added. Exactly as planned.
- **Deviations from plan:** Commit type is `bug:` (the task's issue_type, as the commit convention requires), not the `test:` the plan named. (Plan review before approval replaced an `Epoch`-shift mutant, which could not fail because producer and expectation both derive from `Epoch`, with two producer-only mutants of `CommitMessage`'s `when`.)
- **Issues encountered:** None.
- **Key decisions:** `%ct` over parsing `%cI` with `time.Parse`: integers render identically on every git version, so no parsing tolerance is needed; the expectation is derived from `Epoch` instead of a hardcoded date string.
- **Verification evidence** (run 2026-10-26, isolated scratch copies of the module from `git archive HEAD goengines`, host Go 1.27.2 mounted read-only, `--network none`, scratch GOCACHE, `-count=1`, `-run '^TestHistory$'`):

  | variant | ait-dashproto:1 (git 2.43.0) | ait-dashproto:2 (git 2.56.0) |
  |---|---|---|
  | old test (HEAD) | FAIL `dates "2026-01-01T00:00:00+00:00\n…"` | ok |
  | new test | ok | ok |
  | mutant offset (`+ time.Second` in `when`) | FAIL `1767225601…` vs `1767225600…` | FAIL |
  | mutant step (`ticks * time.Second`) | FAIL `…225601\n…225602` vs `…225660\n…225720` | FAIL |

  Mutants applied by exact-string replacement asserted to occur once and to be present afterwards. Also: full fixture package ok under git 2.43; host `go vet` + `go test -count=1 ./internal/testmap/fixture/` ok; `goengines/ci/dashcheck.sh -run TestHistory ./internal/testmap/fixture/` → `DASHCHECK:PASS`.
- **Upstream defects identified:** None
