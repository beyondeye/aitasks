//go:build unix

package runner

// The hang watchdog for this package's process-starting tests.
//
// A test that drives Run (or Load, a list scan, a session sweep) asserts its
// bounds only once the call returns, so a regression that makes it hang — a
// blocking report read, a sweep that never terminates, a lost WaitDelay —
// never reaches an assertion and the suite waits for go test's own timeout.
// isolated re-executes the test binary for one top-level test, under that
// test's own deadline, in a subprocess leading its own session; past the
// deadline the subprocess is killed and the test fails with
// HANG:<test>|<limit>.
//
// Cleanup is by environment marker, not by session: execRunner starts every
// runner with Setsid, so runner processes and their fixtures live in sessions
// of their own — killing the subprocess's session misses them, and once the
// subprocess dies they are orphaned out of any process-tree walk. They do
// inherit its environment (the runner gets os.Environ()), so each launch
// carries a unique isolateEnv entry and, after the subprocess ends, every
// process whose environment holds that exact entry is killed (reapMarked). A
// marked process alive after a normal exit is a LEAK. The watchdog reads
// /proc itself and never calls sweepSession, sessionProcs or parseStat: a
// sweep that never terminates is one of the regressions it must survive.
//
// Residuals: a process that clears its environment or execs a setuid binary
// escapes the marker scan (the runner contract forbids both; no fixture does
// either). Outside Linux there is no scan, so a hang still fails fast but its
// cleanup is reported unverified. Profiles, traces, the coverage profile and
// the test log (-test.cpuprofile, -test.coverprofile, -test.testlogfile, …)
// are the parent's alone: forwarding them would let the subprocess overwrite
// the parent's files.
//
// TestIsolationControls and TestReapMarkedUncertainty start processes but
// are not isolated: they are the watchdog's own controls. The convention is
// enforced by isolation_tripwire_test.go, which fails a test that reaches a
// process start without the guard as its first statement — these two are its
// allowlist — and which ci/preflight.sh runs before the suite.
//
// Debugging: the subprocess path is plain in-process execution, so
//
//	AIT_RUNNER_TEST_ISOLATE='TestX|debug' go test -run '^TestX$' ./internal/testmap/runner/
//
// (or the same environment under dlv test) runs TestX's body in-process.

import (
	"bytes"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"testing/iotest"
	"time"
)

const (
	// isolateEnv carries `<test name>|<launch token>`: it names the test the
	// subprocess runs and, being unique per launch, marks every process the
	// launch starts.
	isolateEnv = "AIT_RUNNER_TEST_ISOLATE"
	// hangLimit bounds one isolated test. The slowest runs in about 3 s; the
	// limit stays under the fixtures' `sleep 30` so that a lost deadline
	// reads as a hang rather than a slow pass.
	hangLimit = 20 * time.Second
	quitGrace = 2 * time.Second // for the goroutine dump SIGQUIT asks for
	reapBound = 5 * time.Second // for killing the marked processes left over
	outputCap = 64 << 10        // subprocess output kept for a report
	readChunk = 32 << 10        // subprocess output read at a time
)

// errNoEnumeration is reapMarked where processes cannot be enumerated.
var errNoEnumeration = errors.New("no process enumeration on this platform")

// isolated runs the calling top-level test's body in a subprocess under
// limit and reports whether this process should run the body itself: true
// in that subprocess, false in the parent, which has already reported the
// outcome. A guarded test starts with
//
//	if !isolated(t, hangLimit) {
//		return
//	}
func isolated(t *testing.T, limit time.Duration) bool {
	t.Helper()
	if v, ok := os.LookupEnv(isolateEnv); ok {
		if name, _, _ := strings.Cut(v, "|"); name != t.Name() {
			t.Fatalf("isolated: %s runs inside the subprocess of %s", t.Name(), name)
		}
		return true
	}
	c := runChild(t, t.Name(), limit, parentSettings())
	for _, p := range c.problems(t.Name(), limit) {
		t.Error(p)
	}
	if testing.Verbose() {
		t.Log(c.output)
	}
	if c.skipped && !t.Failed() {
		t.Skip("skipped in its subprocess")
	}
	return false
}

// childSettings are the parent's testing flags as the subprocess receives
// them, so that it runs the body the way the parent would have.
type childSettings struct {
	run, skip, coverdir       string
	cpu, parallel             int
	short, failfast, fullpath bool
}

// parentSettings reads the live testing flags. cpu is the effective
// GOMAXPROCS, not -test.cpu: the testing package applies each -test.cpu
// value with runtime.GOMAXPROCS in this process, and a re-executed binary
// would start at its default.
func parentSettings() childSettings {
	s := childSettings{
		run:      flagValue("test.run"),
		skip:     flagValue("test.skip"),
		coverdir: flagValue("test.gocoverdir"),
		cpu:      runtime.GOMAXPROCS(0),
		short:    flagValue("test.short") == "true",
		failfast: flagValue("test.failfast") == "true",
		fullpath: flagValue("test.fullpath") == "true",
	}
	s.parallel, _ = strconv.Atoi(flagValue("test.parallel"))
	return s
}

func flagValue(name string) string {
	if f := flag.Lookup(name); f != nil {
		return f.Value.String()
	}
	return ""
}

// args is the subprocess's command line. -test.run keeps the parent's
// subtest selection for this test only; -test.skip is the parent's,
// verbatim; one count, since the parent repeats; verbose, since the outcome
// is read from the output; the timeout is a backstop for a parent that dies
// before it can kill the subprocess.
func (s childSettings) args(name string, limit time.Duration) ([]string, error) {
	run, err := childRunPattern(name, s.run)
	if err != nil {
		return nil, err
	}
	args := []string{
		"-test.run=" + run,
		"-test.count=1",
		"-test.v=true",
		"-test.paniconexit0",
		"-test.timeout=" + (2 * limit).String(),
		"-test.short=" + strconv.FormatBool(s.short),
		"-test.failfast=" + strconv.FormatBool(s.failfast),
		"-test.fullpath=" + strconv.FormatBool(s.fullpath),
	}
	if s.cpu > 0 {
		args = append(args, "-test.cpu="+strconv.Itoa(s.cpu))
	}
	if s.parallel > 0 {
		args = append(args, "-test.parallel="+strconv.Itoa(s.parallel))
	}
	if s.skip != "" {
		args = append(args, "-test.skip="+s.skip)
	}
	if s.coverdir != "" {
		args = append(args, "-test.gocoverdir="+s.coverdir)
	}
	return args, nil
}

// childRunPattern rewrites the parent's -test.run for a subprocess that runs
// only name: the top level is pinned to name and the deeper levels of every
// alternative that selects name are kept, so a subtest selection survives.
// An alternative selecting name at the top level alone selects all of its
// subtests. A pattern that does not select name is an error — the parent is
// running name, so this port disagrees with the testing package's matcher;
// it fails closed instead of widening the selection.
func childRunPattern(name, parentRun string) (string, error) {
	top := "^" + regexp.QuoteMeta(name) + "$"
	if parentRun == "" {
		return top, nil
	}
	var alts []string
	for _, alt := range splitRunPattern(parentRun) {
		ok, err := regexp.MatchString(rewrite(alt[0]), name)
		if err != nil {
			return "", fmt.Errorf("isolated: -test.run %q: %v", parentRun, err)
		}
		if !ok {
			continue
		}
		if len(alt) == 1 {
			return top, nil
		}
		alts = append(alts, top+"/"+strings.Join(alt[1:], "/"))
	}
	if len(alts) == 0 {
		return "", fmt.Errorf("isolated: -test.run %q does not select %s", parentRun, name)
	}
	return strings.Join(alts, "|"), nil
}

// splitRunPattern splits a -test.run pattern into its alternatives, each a
// list of per-level elements — a port of the testing package's splitRegexp
// (Go 1.27 testing/match.go): `|` separates alternatives and `/` levels,
// neither inside brackets or parentheses, and a backslash escapes the next
// byte. Elements are kept as written.
func splitRunPattern(s string) [][]string {
	var alts [][]string
	var cur []string
	cs, cp := 0, 0
	for i := 0; i < len(s); {
		switch s[i] {
		case '[':
			cs++
		case ']':
			if cs--; cs < 0 { // an unmatched ']' is legal
				cs = 0
			}
		case '(':
			if cs == 0 {
				cp++
			}
		case ')':
			if cs == 0 {
				cp--
			}
		case '\\':
			i++
		case '/':
			if cs == 0 && cp == 0 {
				cur = append(cur, s[:i])
				s, i = s[i+1:], 0
				continue
			}
		case '|':
			if cs == 0 && cp == 0 {
				alts = append(alts, append(cur, s[:i]))
				cur = nil
				s, i = s[i+1:], 0
				continue
			}
		}
		i++
	}
	return append(alts, append(cur, s))
}

// rewrite is the testing package's rewrite of a pattern element (Go 1.27
// testing/match.go): spaces become underscores, unprintable runes their
// quoted form.
func rewrite(s string) string {
	var b []byte
	for _, r := range s {
		switch {
		case isSpace(r):
			b = append(b, '_')
		case !strconv.IsPrint(r):
			q := strconv.QuoteRune(r)
			b = append(b, q[1:len(q)-1]...)
		default:
			b = append(b, string(r)...)
		}
	}
	return string(b)
}

func isSpace(r rune) bool {
	if r < 0x2000 {
		switch r {
		case '\t', '\n', '\v', '\f', '\r', ' ', 0x85, 0xA0, 0x1680:
			return true
		}
		return false
	}
	if r <= 0x200a {
		return true
	}
	switch r {
	case 0x2028, 0x2029, 0x202f, 0x205f, 0x3000:
		return true
	}
	return false
}

// childRun is how one isolated subprocess ended.
type childRun struct {
	hung            bool
	state           *os.ProcessState
	elapsed         time.Duration
	output          string   // capped at outputCap
	passed, skipped bool     // read from the whole output
	leftover        []string // "<pid>:<comm>" of marked processes found after it ended (killed)
	cleanupErr      error    // the leftovers could not be proven gone
}

// runChild runs the top-level test name in a subprocess under limit with
// settings s and the extra environment env, kills it past limit, then kills
// every process its launch marked.
func runChild(t *testing.T, name string, limit time.Duration, s childSettings, env ...string) childRun {
	t.Helper()
	if strings.Contains(name, "/") {
		t.Fatalf("isolated: %s is a subtest; isolate its top-level test", name)
	}
	args, err := s.args(name, limit)
	if err != nil {
		t.Fatal(err)
	}
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	tmp := filepath.Join(dir, "tmp")
	if err := os.Mkdir(tmp, 0o755); err != nil {
		t.Fatal(err)
	}
	// Output goes to a file, not a pipe: a leaked process holding a pipe
	// would keep Wait from returning.
	outPath := filepath.Join(dir, "output")
	out, err := os.Create(outPath)
	if err != nil {
		t.Fatal(err)
	}
	defer out.Close()
	marker := isolateEnv + "=" + name + "|" + strconv.Itoa(os.Getpid()) + "." + strconv.FormatInt(time.Now().UnixNano(), 10)
	cmd := exec.Command(exe, args...)
	// TMPDIR keeps the subprocess's t.TempDir() fixtures under this test's,
	// so a killed subprocess leaves nothing behind in the system temp dir.
	cmd.Env = append(append(os.Environ(), env...), "TMPDIR="+tmp, marker)
	cmd.Stdout, cmd.Stderr = out, out
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	start := time.Now()
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	done := make(chan struct{})
	go func() { _ = cmd.Wait(); close(done) }()
	var c childRun
	timer := time.NewTimer(limit)
	defer timer.Stop()
	select {
	case <-done:
	case <-timer.C:
		c.hung = true
		// The goroutine dump shows where the body hangs.
		_ = cmd.Process.Signal(syscall.SIGQUIT)
		select {
		case <-done:
			// Reaped: its pid may already be reused, so no group kill —
			// the marker scan below finds the rest of its group.
		case <-time.After(quitGrace):
			_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL) // unreaped: the group id is still its
			<-done
		}
	}
	c.elapsed = time.Since(start)
	c.state = cmd.ProcessState
	c.leftover, c.cleanupErr = reapMarked(marker, reapBound)
	f, err := os.Open(outPath) // its own offset: the child's fd shares the writer's
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	c.output, c.passed, c.skipped, err = scanOutput(f, name, readChunk)
	if err != nil {
		t.Fatal(err)
	}
	return c
}

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

// problems is what the parent reports for name, one entry per t.Error.
func (c childRun) problems(name string, limit time.Duration) []string {
	left := strings.Join(c.leftover, ",")
	if c.hung {
		switch {
		case c.cleanupErr != nil && left != "":
			left += " (killed); unverified: " + c.cleanupErr.Error()
		case c.cleanupErr != nil:
			left = "unverified: " + c.cleanupErr.Error()
		case left != "":
			left += " (killed)"
		default:
			left = "none"
		}
		return []string{fmt.Sprintf("HANG:%s|%v\nkilled after %v; leftover processes: %s\n--- subprocess output ---\n%s",
			name, limit, limit, left, c.output)}
	}
	var out []string
	if left != "" || (c.cleanupErr != nil && !errors.Is(c.cleanupErr, errNoEnumeration)) {
		if left == "" {
			left = "unverified"
		}
		msg := fmt.Sprintf("LEAK:%s|%s\nprocesses carrying the test's marker were alive after its subprocess exited (killed)", name, left)
		if c.cleanupErr != nil {
			msg += "; " + c.cleanupErr.Error()
		}
		out = append(out, msg)
	}
	switch {
	case !c.state.Success():
		out = append(out, fmt.Sprintf("%s failed in its subprocess (%v):\n%s", name, c.state, c.output))
	case !c.passed && !c.skipped:
		out = append(out, fmt.Sprintf("%s: the subprocess ran no such test:\n%s", name, c.output))
	}
	return out
}

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
