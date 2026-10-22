//go:build unix

// Package hangguard is the hang watchdog for process-starting tests.
//
// A test that starts processes (a runner invocation, a list scan, a session
// sweep) asserts its bounds only once the call returns, so a regression that
// makes it hang — a blocking report read, a sweep that never terminates, a
// lost WaitDelay — never reaches an assertion and the suite waits for go
// test's own timeout. Isolated re-executes the test binary for one top-level
// test, under that test's own deadline, in a subprocess leading its own
// session; past the deadline the subprocess is killed and the test fails with
// HANG:<test>|<limit>.
//
// Cleanup is by environment marker, not by session: the code under test may
// start processes in sessions of their own (the runner package starts every
// runner with Setsid), so killing the subprocess's session misses them, and
// once the subprocess dies they are orphaned out of any process-tree walk.
// They do inherit its environment, so each launch carries a unique isolateEnv
// entry and, after the subprocess ends, every process whose environment holds
// that exact entry is killed (reapMarked). A marked process alive after a
// normal exit is a LEAK. The watchdog reads /proc itself and calls nothing of
// the code under test: a sweep that never terminates is one of the
// regressions it must survive.
//
// Residuals: a process that clears its environment or execs a setuid binary
// escapes the marker scan. Outside Linux there is no scan, so a hang still
// fails fast but its cleanup is reported unverified. Profiles, traces, the
// coverage profile and the test log (-test.cpuprofile, -test.coverprofile,
// -test.testlogfile, …) are the parent's alone: forwarding them would let the
// subprocess overwrite the parent's files.
//
// The package is test support: it is imported only from _test.go files.
// tripwire_test.go enforces that (TestIsolationTripwireImports), and it fails
// a test of a listed package (tripwirePackages) that reaches a process start
// without the guard as its first statement; ci/preflight.sh runs it before
// the suite. TestIsolationControls and TestReapMarkedUncertainty start
// processes but are not isolated: they are the watchdog's own controls, this
// package's allowlist.
//
// Debugging: the subprocess path is plain in-process execution, so
//
//	AIT_HANGGUARD_ISOLATE='TestX|debug' go test -run '^TestX$' ./<pkg>/
//
// (or the same environment under dlv test) runs TestX's body in-process.
package hangguard

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
	"time"
)

const (
	// isolateEnv carries `<test name>|<launch token>`: it names the test the
	// subprocess runs and, being unique per launch, marks every process the
	// launch starts.
	isolateEnv = "AIT_HANGGUARD_ISOLATE"
	quitGrace  = 2 * time.Second // for the goroutine dump SIGQUIT asks for
	reapBound  = 5 * time.Second // for killing the marked processes left over
	outputCap  = 64 << 10        // subprocess output kept for a report
	readChunk  = 32 << 10        // subprocess output read at a time
)

// errNoEnumeration is reapMarked where processes cannot be enumerated.
var errNoEnumeration = errors.New("no process enumeration on this platform")

// Isolated runs the calling top-level test's body in a subprocess under
// limit and reports whether this process should run the body itself: true
// in that subprocess, false in the parent, which has already reported the
// outcome. A guarded test starts with
//
//	if !hangguard.Isolated(t, limit) {
//		return
//	}
//
// or with a package-local wrapper named isolated, called the same way.
func Isolated(t *testing.T, limit time.Duration) bool {
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
