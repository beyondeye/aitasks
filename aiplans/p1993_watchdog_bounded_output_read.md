---
Task: t1993_watchdog_bounded_output_read.md
Base branch: main
Output branch: main
---

# t1993 — Bounded read of the watchdog's subprocess output

## Context

`runChild` (`goengines/internal/testmap/runner/watchdog_unix_test.go:303`)
captures an isolated test's subprocess output to a file, then
`os.ReadFile`s the whole file, converts it to a string (a second full copy)
and only then caps the *reported* text at `outputCap` (64 KiB). The cap bounds
what is reported, not the memory used to read it: a noisy test makes the
parent allocate ~2× its whole log on every isolated test. The full read exists
only so the outcome markers `"\n--- PASS: <name> ("` / `"\n--- SKIP: <name> ("`
are found anywhere in the output.

Outcome: the output is read in fixed chunks, markers are detected over the
whole stream (including across chunk boundaries), only the first `outputCap`
bytes are kept, and every current outcome semantic is unchanged.

Files: `watchdog_unix_test.go` (scanner + runChild + pure unit test),
`watchdog_linux_test.go` (end-to-end noisy control). No docs reference
these internals (grep of `aidocs/`, `goengines/**/*.md`: none).

## Implementation

### 1. `scanOutput` — `watchdog_unix_test.go`

Add `readChunk = 32 << 10 // subprocess output read at a time` to the const
block, and, next to `runChild`:

```go
// scanOutput reads a subprocess's output from r, chunk bytes at a time, and
// returns its first outputCap bytes (with a note of how many more there were)
// and whether the whole output holds name's PASS or SKIP line. Each search
// runs over the previous chunk's last len(marker)-1 bytes plus the new chunk,
// so a marker split across reads is still found, and memory stays bounded by
// outputCap and the chunk whatever the output's size.
func scanOutput(r io.Reader, name string, chunk int) (output string, passed, skipped bool, err error) {
	pass, skip := []byte("\n--- PASS: "+name+" ("), []byte("\n--- SKIP: "+name+" (")
	keep := len(pass) - 1 // PASS and SKIP are the same length
	var head []byte
	var total int64
	buf, win := make([]byte, chunk), make([]byte, 0, keep+chunk)
	for {
		n, rerr := r.Read(buf)
		if n > 0 {
			total += int64(n)
			if room := outputCap - len(head); room > 0 {
				head = append(head, buf[:min(n, room)]...)
			}
			win = append(win, buf[:n]...)
			passed = passed || bytes.Contains(win, pass)
			skipped = skipped || bytes.Contains(win, skip)
			if len(win) > keep {
				win = append(win[:0], win[len(win)-keep:]...)
			}
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			return "", false, false, rerr
		}
	}
	output = string(head)
	if total > outputCap {
		output += fmt.Sprintf("\n[truncated %d bytes]", total-outputCap)
	}
	return output, passed, skipped, nil
}
```

Correctness argument (pinned by Step 3): `win` always ends with the last
`min(total, ≥keep)` stream bytes before the new chunk is appended, so any
marker whose last byte lands in the current chunk starts inside `win`; `win`
only ever holds a contiguous substring of the stream, so there are no false
positives. Works for chunks smaller than the marker (multi-chunk straddle) and
for short reads / data returned together with `io.EOF`. Read until EOF, as
`os.ReadFile` did. Imports: add `bytes`, `io`.

### 2. `runChild` uses it

Replace the `os.ReadFile` … `full[:outputCap]` block
(`watchdog_unix_test.go:362-373`) with:

```go
	f, err := os.Open(outPath) // its own offset: the child's fd shares the writer's
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	c.output, c.passed, c.skipped, err = scanOutput(f, name, readChunk)
	if err != nil {
		t.Fatal(err)
	}
```

`childRun` field comments (`capped at outputCap`, `read from the whole
output`) stay accurate. `problems()`, `isolated()`'s verbose relay and
`t.Skip` path are untouched — they consume the same three fields.

### 3. Pure unit test `TestScanOutput` — `watchdog_unix_test.go`

Placed after `TestChildRunPattern` (pure, so not a t1998 tripwire subject).
Differential against the **old code verbatim** as the reference:

```go
ref := func(full string) (string, bool, bool) { /* strings.Contains ×2 + old cap formula */ }
```

- Inputs: `""`; `"--- PASS: TestX (0.00s)\n"` at offset 0 (no leading `\n` →
  not a pass, as before); a normal RUN/PASS/PASS log; a SKIP line; the
  prefix-sharing `"\n--- PASS: TestXY ("`; a marker truncated at EOF
  (`"\n--- PASS: TestX"`); a subtest line `"\n    --- PASS: TestX/sub ("`;
  lengths `outputCap-1`, `outputCap`, `outputCap+1` and `outputCap+100` with
  the PASS marker placed **past** the cap.
- **Straddle sweep:** for every `chunk` in `1..len(marker)+1` and every
  `pad` in `0..chunk`, input `strings.Repeat("x", pad) + marker + "0.00s)\n"`
  for both PASS and SKIP — so each split position of the marker across a
  chunk boundary (and multi-chunk spans for tiny chunks) is exercised.
- Every input is fed through four readers — `bytes.NewReader` (exact chunk
  boundaries), `iotest.OneByteReader`, `iotest.HalfReader`,
  `iotest.DataErrReader` (last data arrives with `io.EOF`) — and must equal
  the reference on output, passed and skipped.
- A read error after some data (`io.MultiReader(strings.NewReader("abc"),
  iotest.ErrReader(e))`) is returned as `e`.
- **Bounded allocation (the memory assertion lives here, not in a subprocess
  control).** A generated stream that never holds what it yields:

  ```go
  // xs yields 'x' forever without holding what it has yielded.
  type xs struct{}

  func (xs) Read(p []byte) (int, error) {
  	for i := range p {
  		p[i] = 'x'
  	}
  	return len(p), nil
  }
  ```

  For `n` in `{1 << 20, 32 << 20}`: build
  `io.MultiReader(io.LimitReader(xs{}, n), strings.NewReader("\n--- PASS: TestX (0.00s)\n"))`
  **before** the first `runtime.ReadMemStats`, then bracket only
  `scanOutput(r, "TestX", readChunk)` with `ReadMemStats` and take the
  `TotalAlloc` delta (cumulative, so it bounds peak growth too). Assert:
  `passed`; the output is exactly `outputCap` `x`s + `"\n[truncated N bytes]"`
  with the exact `N = n + len(tail) − outputCap`; and the delta is
  `< 4 MiB` at **both** sizes — expected ≈ 0.3 MiB (two 32 KiB buffers,
  `head`'s growth to 64 KiB, the 64 KiB string), independent of `n`. The
  measured region contains no process start, no `/proc` scan and no cleanup,
  so nothing host-dependent is inside it; a whole-stream read allocates
  ≥ 32 MiB at the large size (≥ 64 MiB for `ReadAll` growth + `string()`).
  `t.Logf` the two raw deltas (for P1).

### 4. End-to-end noisy control — `watchdog_linux_test.go`

Proves the real parent path — file capture, `runChild`, `problems()` — keeps
the outcome semantics when the PASS line sits far beyond the cap. It makes
**no** allocation claim (its region includes `reapMarked`'s `/proc` scans,
whose cost is host-dependent).

- `controlFixture` gains mode `"noisy"`: writes `noisyBytes = 10 << 20` of
  1 KiB `x…\n` lines to `os.Stdout` in 64 KiB writes, then returns (passes) —
  the PASS line lands ~10 MiB past the cap.
- New subtest `t.Run("noisy", …)` in `TestIsolationControls`:
  `c := runChild(t, name, hangLimit, settings, controlEnv+"=noisy|"+t.TempDir())`;
  assert `!c.hung`, `c.state.Success()`, `c.passed`, `!c.skipped`,
  `c.problems(name, hangLimit)` empty, and the report capped: it ends with
  `"\n[truncated N bytes]"`, `len(c.output) == outputCap + len(that note)`,
  and `N + outputCap ≥ noisyBytes`. Failure messages print sizes and the
  output's tail, never 64 KiB of `x`.
- Extend `TestIsolationControls`' doc comment with the new control in one
  clause.

Red proofs (uncommitted throughout; guard and fix land in one commit): the
allocation subtest has no pre-fix code to run against, so its red proof is
mutant (d) below — the old algorithm behind `scanOutput`'s signature — which
must fail it while the differential stays green. The noisy control passes
pre-fix by design (the old code read everything); its discriminating power is
mutant (c).

### Post-phase (risk mitigations)

1. [measure_alloc_margin] Run `TestScanOutput` with `-count=5 -v` and record
   the raw deltas at both sizes (from its `t.Logf`); run mutant (d) once and
   record its large-size delta. Accept only: every real value far under the
   4 MiB bound (target < 1 MiB) and equal-order at 1 MiB and 32 MiB (size
   independence), and mutant (d) ≥ 32 MiB. Record the raw values in the plan's
   Final Implementation Notes. (The measured region holds no
   host-dependent work, so this records the margin rather than
   establishing it.)
2. [notify_t1998] After the code commit, run
   `./ait note 1998 --from 1993 --with-live --file -` stating: commit SHA;
   `TestScanOutput` added to `watchdog_unix_test.go` (pure — calls only
   `scanOutput` over in-memory readers, starts no process); a `noisy` subtest
   and a `noisy` fixture mode added inside the allowlisted
   `TestIsolationControls` (starts processes via `runChild`, as its siblings
   do); so a hardcoded survey of "20 pure unguarded" tests becomes 21. Hedged:
   the claims are tree-relative at that SHA. Expect `NOTE_APPENDED:`.

## Verification

From `goengines/`:

1. `go test -count=1 -run '^TestScanOutput$' -v ./internal/testmap/runner/`
   and `go test -count=1 -run '^TestIsolationControls$/^noisy$' -v ./internal/testmap/runner/`
   pass.
2. Mutants, each in an isolated scratch copy of `goengines/` (never the live
   tree), each mutation's presence verified (grep) before trusting its run:
   (a) `keep := 0` → straddle sweep fails; (b) `keep := len(pass) - 2` →
   straddle sweep fails; (c) search `head` instead of `win` → past-the-cap
   cases and the noisy control's `passed` fail; (d) `scanOutput` body replaced
   by the old algorithm (`io.ReadAll`, `strings.Contains` ×2, old cap
   formula) → only the bounded-allocation subtest fails (differential and
   noisy control green — proving the allocation assertion is what
   discriminates).
3. `TestIsolationControls` and the whole runner package green:
   `go test -count=1 ./internal/testmap/runner/`; then `go vet ./...`,
   `gofmt -l internal/testmap/runner/` empty, and `ait engine test` once.

## Risk

### Code-health risk: low
- t1998 (in flight in another session) adds a go/ast tripwire over this package's `_test.go` files; the new pure `TestScanOutput` and the new subtest/fixture modes inside the allowlisted `TestIsolationControls` can shift its survey counts (e.g. "20 pure unguarded") · severity: low (residual — addressed by inline post-phase notify_t1998) · → mitigation: inline post-phase notify_t1998

### Goal-achievement risk: low
- The memory bound is asserted on process-wide `TotalAlloc`; a measured region that included `runChild`'s `/proc` reap scans would carry host-dependent allocation no baseline subtraction removes · severity: low (residual — the region now brackets only `scanOutput` over a generated stream, and inline post-phase measure_alloc_margin records the margin) · → mitigation: inline post-phase measure_alloc_margin
- `runChild`'s own wiring (the single `scanOutput(f, name, readChunk)` call) carries no allocation assertion: a later edit that read the file wholesale inside `runChild` would pass the noisy control. The call site is one line, verified by review · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: measure_alloc_margin | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: TotalAlloc threshold reliability | desc: n=5 raw scanOutput allocation deltas at 1 MiB and 32 MiB plus mutant (d), recorded against the 4 MiB bound
- timing: post-phase | name: notify_t1998 | type: chore | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: t1998 tripwire survey drift | desc: ait note to t1998 naming the new pure test and the new control subtest, with the commit SHA

## Step 9 (Post-Implementation)

Current-branch mode: commit code (`test: … (t1993)`) naming only the two
`_test.go` paths (other sessions' dirty files must not ride along), plan via
`aitask_task_commit.sh`, then archival per Step 9.
