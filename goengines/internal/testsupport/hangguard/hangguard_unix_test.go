//go:build unix

package hangguard

import (
	"errors"
	"fmt"
	"io"
	"runtime"
	"strings"
	"testing"
	"testing/iotest"
)

// childRunPattern against the rows the settings differential runs through
// real launches, plus the cases no launch may run (an empty or unanchored
// pattern selects the whole package) and the splitter's edges.
func TestChildRunPattern(t *testing.T) {
	const ic = "TestIsolationControls"
	for _, tc := range []struct{ name, run, want string }{
		{"TestX", "", "^TestX$"},
		{"TestX", "TestX", "^TestX$"},
		{ic, "Controls", "^TestIsolationControls$"},
		{ic, "^TestIsolationControls$/b", "^TestIsolationControls$/b"},
		{ic, "^TestIsolationControls$/b/c", "^TestIsolationControls$/b/c"},
		{ic, "^TestIsolationControls$/a|^TestIsolationControls$/b/c", "^TestIsolationControls$/a|^TestIsolationControls$/b/c"},
		{ic, "^TestNoSuchTestExists$/x|^TestIsolation(Controls)$/[b]", "^TestIsolationControls$/[b]"},
		{ic, "TestNoSuch/x|Isolation.*/[b]", "^TestIsolationControls$/[b]"},
		{ic, "^TestIsolationControls$/(a|b)$", "^TestIsolationControls$/(a|b)$"},
		{"TestX", "TestY|TestX/sub", "^TestX$/sub"},
		{"TestX", "TestX/sub|TestX", "^TestX$"},
		{"TestX", "TestX/[/]", "^TestX$/[/]"},
		{"TestX", "TestX/(x/y)", "^TestX$/(x/y)"},
		{"TestX", `TestX/a\/b`, `^TestX$/a\/b`},
		{"TestX", "TestX/", "^TestX$/"},
		{"TestX", "TestX/[]a]/b", "^TestX$/[]a]/b"},
		{"TestA_B", "TestA B/x y", "^TestA_B$/x y"},
	} {
		got, err := childRunPattern(tc.name, tc.run)
		if err != nil || got != tc.want {
			t.Errorf("childRunPattern(%q, %q) = %q, %v; want %q", tc.name, tc.run, got, err, tc.want)
		}
	}
	for _, run := range []string{"TestY", "TestY/x|TestZ", "Test(X"} {
		if got, err := childRunPattern("TestX", run); err == nil {
			t.Errorf("childRunPattern(TestX, %q) = %q, want an error", run, got)
		}
	}
}

// xs yields 'x' forever without holding what it has yielded.
type xs struct{}

func (xs) Read(p []byte) (int, error) {
	for i := range p {
		p[i] = 'x'
	}
	return len(p), nil
}

// scanOutput against the read it replaced — the whole output in memory,
// searched with strings.Contains, the report capped afterwards — under every
// way a reader may split the output, each marker split at every position
// across a read boundary; and its memory does not grow with the output.
func TestScanOutput(t *testing.T) {
	const name = "TestX"
	pass, skip := "\n--- PASS: "+name+" (", "\n--- SKIP: "+name+" ("
	ref := func(full string) (string, bool, bool) {
		out := full
		if len(full) > outputCap {
			out = full[:outputCap] + fmt.Sprintf("\n[truncated %d bytes]", len(full)-outputCap)
		}
		return out, strings.Contains(full, pass), strings.Contains(full, skip)
	}
	readers := map[string]func(string) io.Reader{
		"chunk-sized":   func(s string) io.Reader { return strings.NewReader(s) },
		"one byte":      func(s string) io.Reader { return iotest.OneByteReader(strings.NewReader(s)) },
		"half":          func(s string) io.Reader { return iotest.HalfReader(strings.NewReader(s)) },
		"data with EOF": func(s string) io.Reader { return iotest.DataErrReader(strings.NewReader(s)) },
	}
	check := func(full string, chunk int) {
		t.Helper()
		wantOut, wantPass, wantSkip := ref(full)
		for rn, rd := range readers {
			out, p, s, err := scanOutput(rd(full), name, chunk)
			if err != nil || out != wantOut || p != wantPass || s != wantSkip {
				t.Errorf("%s reads, chunk %d, %d bytes ending %q: passed %v skipped %v, want %v %v; output %d bytes, want %d; err %v",
					rn, chunk, len(full), full[max(0, len(full)-40):], p, s, wantPass, wantSkip, len(out), len(wantOut), err)
			}
		}
	}

	long := strings.Repeat("x", outputCap+100)
	for _, in := range []string{
		"",
		"--- PASS: TestX (0.00s)\n", // at offset 0 no newline precedes it
		"=== RUN   TestX\n--- PASS: TestX (0.00s)\nPASS\n",
		"=== RUN   TestX\n    x_test.go:1: skipping\n--- SKIP: TestX (0.00s)\nPASS\n",
		"=== RUN   TestXY\n--- PASS: TestXY (0.00s)\n",
		"=== RUN   TestX\n--- PASS: TestX",
		"=== RUN   TestX\n=== RUN   TestX/sub\n    --- PASS: TestX/sub (0.00s)\n",
		"=== RUN   TestX\n--- FAIL: TestX (0.00s)\n",
		strings.Repeat("x", outputCap-1),
		strings.Repeat("x", outputCap),
		strings.Repeat("x", outputCap+1),
		long + pass + "0.00s)\n", // the markers lie past the cap
		long + skip + "0.00s)\n",
	} {
		for _, chunk := range []int{1, 7, len(pass) - 1, readChunk} {
			check(in, chunk)
		}
	}

	// The marker starts pad bytes in, so with chunk-sized reads a read
	// boundary falls after each of its prefixes, and a chunk shorter than the
	// marker puts several boundaries inside it.
	for _, marker := range []string{pass, skip} {
		for chunk := 1; chunk <= len(marker)+1; chunk++ {
			for pad := 0; pad <= chunk; pad++ {
				check(strings.Repeat("x", pad)+marker+"0.00s)\n", chunk)
			}
		}
	}

	e := errors.New("read failed")
	if _, _, _, err := scanOutput(io.MultiReader(strings.NewReader("abc"), iotest.ErrReader(e)), name, readChunk); !errors.Is(err, e) {
		t.Errorf("read error: got %v, want %v", err, e)
	}

	// The stream is generated, so the measured region holds the scan alone:
	// what it allocates — the report and two chunks — does not grow with the
	// output, where a whole read holds all of it.
	line := pass + "0.00s)\n"
	for _, n := range []int64{1 << 20, 32 << 20} {
		r := io.MultiReader(io.LimitReader(xs{}, n), strings.NewReader(line))
		var before, after runtime.MemStats
		runtime.ReadMemStats(&before)
		out, p, s, err := scanOutput(r, name, readChunk)
		runtime.ReadMemStats(&after)
		alloc := after.TotalAlloc - before.TotalAlloc
		total := n + int64(len(line))
		if want := strings.Repeat("x", outputCap) + fmt.Sprintf("\n[truncated %d bytes]", total-outputCap); err != nil || !p || s || out != want {
			t.Fatalf("%d bytes: passed %v skipped %v err %v; output %d bytes ending %q, want %d",
				total, p, s, err, len(out), out[max(0, len(out)-40):], len(want))
		}
		if alloc >= 4<<20 {
			t.Errorf("scanning %d bytes allocated %d bytes; the bound is 4 MiB whatever the size", total, alloc)
		}
		t.Logf("scanning %d bytes allocated %d bytes", total, alloc)
	}
}
