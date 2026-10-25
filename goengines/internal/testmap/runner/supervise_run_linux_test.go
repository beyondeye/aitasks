//go:build linux

package runner

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// The engine side of supervised execution (M3.2c): every runner process runs
// under its own procsup supervisor.

// parallelExec runs every invocation at once — the overlap an M3.3 executor
// may start.
type parallelExec struct{}

func (parallelExec) Execute(ctx context.Context, invs []*Invocation, invoke InvokeFunc) ([]Outcome, error) {
	out := make([]Outcome, len(invs))
	var wg sync.WaitGroup
	for i, inv := range invs {
		wg.Add(1)
		go func() { defer wg.Done(); out[i] = invoke(ctx, inv) }()
	}
	wg.Wait()
	return out, nil
}

// supervisors records each started command's supervisor.
type supervisors struct {
	mu  sync.Mutex
	pid map[int]int // command pid → supervisor pid
}

func watchSupervisors(t *testing.T) *supervisors {
	t.Helper()
	s := &supervisors{pid: map[int]int{}}
	t.Cleanup(procsup.OnStartForTesting(func(sup, cmd int) { s.mu.Lock(); s.pid[cmd] = sup; s.mu.Unlock() }))
	return s
}

// kill SIGKILLs the supervisor of the runner whose pid the fixture wrote at
// path, and makes sure the runner itself — left behind by its supervisor's
// death, the stated residual — does not outlive the test.
func (s *supervisors) kill(t *testing.T, path string) {
	t.Helper()
	cmd := waitPid(t, path)
	t.Cleanup(func() { _ = syscall.Kill(cmd, syscall.SIGKILL) })
	s.mu.Lock()
	sup := s.pid[cmd]
	s.mu.Unlock()
	if sup == 0 {
		t.Fatalf("no supervisor recorded for runner %d", cmd)
	}
	if err := syscall.Kill(sup, syscall.SIGKILL); err != nil {
		t.Fatal(err)
	}
}

// waitPid polls for a pid file and reads it.
func waitPid(t *testing.T, path string) int {
	t.Helper()
	waitFile(t, path)
	for end := time.Now().Add(5 * time.Second); time.Now().Before(end); time.Sleep(10 * time.Millisecond) {
		if b, err := os.ReadFile(path); err == nil && strings.HasSuffix(string(b), "\n") {
			return readPid(t, path)
		}
	}
	t.Fatalf("%s never completed", path)
	return 0
}

func recordOf(t *testing.T, rep *RunReport, runner string) Record {
	t.Helper()
	for _, rec := range rep.Invocations {
		if rec.Runner == runner {
			return rec
		}
	}
	t.Fatalf("no invocation of %s in %+v", runner, rep.Invocations)
	return Record{}
}

func runQuiet(t *testing.T, r *fixture.Repo, id string) *RunReport {
	t.Helper()
	rep, err := Run(bg, r.Dir, Options{All: true, RunID: id})
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	return rep
}

// A runner that leaves a setsid double-forked daemon behind: the daemon is
// gone the moment Run returns — the supervisor holds it, whatever session it
// moved to — and the record says what contained it.
func TestSupervisedSetsidDaemonDiesWithRun(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{"tests/a.sh": ""})
	st := stateOf(t, r)
	put(t, r, "shell", spec{describe: "unit: file", list: "tests/a.sh|file|a\n", run: `setsid sh -c 'sleep 300 & echo $! > "$0/daemon.pid"' "$D" &
wait $!; while [ ! -s "$D/daemon.pid" ]; do sleep 0.01; done
row tests/a.sh pass; exit 0`})
	runners(t, r, "runners:\n  - name: shell\n    timeout_s: 5\n")
	commitAll(t, r)
	rep := timedRun(t, r, 10*time.Second)
	daemon := readPid(t, filepath.Join(st, "daemon.pid"))
	if alive(daemon) {
		t.Fatalf("setsid daemon %d alive after Run", daemon)
	}
	rec := rep.Invocations[0]
	if rec.Cause != "" || rep.Exit() != 0 || rec.Containment != procsup.Supervisor || rec.Boundary != procsup.Supervisor {
		t.Fatalf("%+v exit %d", rec, rep.Exit())
	}
}

// twoRunners is a repository with runners a and b, one unit each.
func twoRunners(t *testing.T, a, b string) (*fixture.Repo, string) {
	t.Helper()
	r := newRepo(t, map[string]string{"tests/a.sh": "", "tests/b.sh": ""})
	put(t, r, "a", spec{describe: "unit: file", list: "tests/a.sh|file|a\n", run: a})
	put(t, r, "b", spec{describe: "unit: file", list: "tests/b.sh|file|b\n", run: b})
	runners(t, r, "runners:\n  - name: a\n    bind: ['tests/a.sh']\n    timeout_s: 15\n  - name: b\n    bind: ['tests/b.sh']\n    timeout_s: 15\n")
	commitAll(t, r)
	return r, stateOf(t, r)
}

// A supervisor's death halts the run: its own invocation is a mechanism
// failure that claims no cleanup, and the queued invocation starts nothing.
func TestHaltInSerialRun(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	sups := watchSupervisors(t)
	r, st := twoRunners(t,
		`echo $$ > "$D/a.pid"; exec sleep 300`,
		`touch "$D/b.started"; row tests/b.sh pass`)
	done := make(chan *RunReport, 1)
	go func() { done <- runQuiet(t, r, "halt-serial") }()
	sups.kill(t, filepath.Join(st, "a.pid"))
	rep := <-done
	a, b := recordOf(t, rep, "a"), recordOf(t, rep, "b")
	if a.Cause != CauseMechanism || !strings.HasPrefix(a.CauseDetail, "cleanup_unverified:supervisor_died:") {
		t.Fatalf("a: %+v", a)
	}
	if b.Cause != CauseMechanism || !strings.HasPrefix(b.CauseDetail, "halted:supervisor_died:") || statuses(rep)["tests/b.sh"] != StatusNotStarted {
		t.Fatalf("b: %+v %v", b, statuses(rep))
	}
	if _, err := os.Stat(filepath.Join(st, "b.started")); err == nil {
		t.Fatal("the queued invocation started a runner after the halt")
	}
	if rep.Exit() != 3 {
		t.Fatalf("exit %d", rep.Exit())
	}
}

// A halt cancels a concurrently running invocation: its daemon is cleaned
// up and it is recorded halted — a mechanism interruption, not a timeout.
func TestHaltCancelsConcurrentInvocation(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	withExecutor(t, parallelExec{})
	sups := watchSupervisors(t)
	r, st := twoRunners(t,
		`echo $$ > "$D/a.pid"; exec sleep 300`,
		`setsid sleep 300 & echo $! > "$D/bd.pid"; echo $$ > "$D/b.pid"; while :; do sleep 0.05; done`)
	done := make(chan *RunReport, 1)
	go func() { done <- runQuiet(t, r, "halt-parallel") }()
	waitPid(t, filepath.Join(st, "b.pid"))
	sups.kill(t, filepath.Join(st, "a.pid"))
	rep := <-done
	b := recordOf(t, rep, "b")
	if b.Cause != CauseMechanism || !strings.HasPrefix(b.CauseDetail, "halted:supervisor_died:") || b.TimedOut != "" || b.Killed {
		t.Fatalf("b: %+v", b)
	}
	if s := statuses(rep)["tests/b.sh"]; s != StatusMissing {
		t.Fatalf("b's unit %s", s)
	}
	if d := readPid(t, filepath.Join(st, "bd.pid")); alive(d) {
		t.Fatal("the cancelled invocation's daemon survived")
	}
}

// A halted cases invocation keeps what it provably finished and its
// attributable errors; everything else is missing, never timeout.
func TestHaltedCasesReconciliation(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	withExecutor(t, parallelExec{})
	sups := watchSupervisors(t)
	list := "tests/u1.py|file|u1\ntests/u1.py|case|a\n" +
		"tests/u2.py|file|u2\ntests/u2.py|case|a\ntests/u2.py|case|b\n" +
		"tests/u3.py|file|u3\ntests/u3.py|case|a\n" +
		"tests/u4.py|file|u4\ntests/u4.py|case|a\n"
	r := scenRepo(t, []scen{
		{name: "c", describe: casesDescribe + "\ntimeouts: batch", list: list, entry: "    batch_timeout_s: 30\n", run: `start tests/u1.py; crow tests/u1.py a pass
start tests/u2.py; crow tests/u2.py a pass
start tests/u4.py; crow tests/u4.py a pass; crow tests/u4.py a pass; printf '{"unit":"tests/u4.py","ca' >> "$C"
echo $$ > "$D/c.pid"; while :; do sleep 0.05; done`},
		{name: "d", describe: "unit: file", list: "tests/d.sh|file|d\n", run: `echo $$ > "$D/d.pid"; exec sleep 300`},
	})
	st := stateOf(t, r)
	done := make(chan *RunReport, 1)
	go func() { done <- runQuiet(t, r, "halt-cases") }()
	waitPid(t, filepath.Join(st, "c.pid"))
	sups.kill(t, filepath.Join(st, "d.pid"))
	rep := <-done
	c := recordOf(t, rep, "c")
	if c.Cause != CauseMechanism || !strings.HasPrefix(c.CauseDetail, "halted:supervisor_died:") || c.TimedOut != "" {
		t.Fatalf("c: %+v", c)
	}
	if u1 := resultOf(t, rep, "tests/u1.py"); u1.Status != StatusPass || u1.Cases == nil || u1.Cases.Passed != 1 {
		t.Fatalf("u1 (complete): %+v", u1)
	}
	if u2 := resultOf(t, rep, "tests/u2.py"); u2.Status != StatusMissing || !u2.Started {
		t.Fatalf("u2 (partial): %+v", u2)
	}
	if u3 := resultOf(t, rep, "tests/u3.py"); u3.Status != StatusMissing || u3.Started {
		t.Fatalf("u3 (untouched): %+v", u3)
	}
	u4 := resultOf(t, rep, "tests/u4.py")
	if u4.Status != StatusError || !strings.Contains(u4.Reason, ReasonDuplicateCase) {
		t.Fatalf("u4 (duplicate, truncated last line): %+v", u4)
	}
	found := false
	for _, e := range c.ProtocolErrors {
		found = found || e == ReasonDuplicateCase+":tests/u4.py"
	}
	if !found {
		t.Fatalf("protocol errors %v", c.ProtocolErrors)
	}
}

// Where invocations may not overlap (no supervisor: darwin), Run serializes
// an executor's overlap and reports it.
func TestParallelRefusedWithoutContainment(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	old := overlappable
	overlappable = func() bool { return false }
	t.Cleanup(func() { overlappable = old })
	withExecutor(t, parallelExec{})
	span := `date +%s%N >> "$D/$0.span"; sleep 0.3; date +%s%N >> "$D/$0.span"; row tests/$0.sh pass`
	r, st := twoRunners(t, strings.ReplaceAll(span, "$0", "a"), strings.ReplaceAll(span, "$0", "b"))
	rep := runQuiet(t, r, "serialized")
	if rep.ParallelRefused != "containment" || rep.Exit() != 0 {
		t.Fatalf("parallel_refused %q exit %d", rep.ParallelRefused, rep.Exit())
	}
	read := func(n string) (int64, int64) {
		b, err := os.ReadFile(filepath.Join(st, n+".span"))
		if err != nil {
			t.Fatal(err)
		}
		f := strings.Fields(string(b))
		s, _ := strconv.ParseInt(f[0], 10, 64)
		e, _ := strconv.ParseInt(f[1], 10, 64)
		return s, e
	}
	as, ae := read("a")
	bs, be := read("b")
	if as < be && bs < ae {
		t.Fatalf("invocations overlapped: a [%d,%d] b [%d,%d]", as, ae, bs, be)
	}
}

// On Linux the engine never signals by session number — not after a clean
// supervision, not after a supervisor death, not after a supervisor that
// died once its cleanup was complete.
func TestNoSessionSignallingWhenSupervised(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	var mu sync.Mutex
	calls := 0
	old := sweepSession
	sweepSession = func(int, time.Duration) error { mu.Lock(); calls++; mu.Unlock(); return nil }
	t.Cleanup(func() { sweepSession = old })
	count := func() int { mu.Lock(); defer mu.Unlock(); return calls }

	// (1) clean.
	r, _ := twoRunners(t, `row tests/a.sh pass`, `row tests/b.sh pass`)
	if rep := runQuiet(t, r, "clean"); rep.Exit() != 0 || count() != 0 {
		t.Fatalf("clean: exit %d, sweep calls %d", rep.Exit(), count())
	}
	// (3) a supervisor that dies after its cleanup reached ECHILD: the
	// unrelated session started before the run must survive.
	other := exec.Command("sleep", "300")
	other.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := other.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = other.Process.Kill(); _ = other.Wait() })
	t.Setenv(dieAfterCleanupEnv, "run")
	rep := runQuiet(t, r, "die-after-cleanup")
	if a := recordOf(t, rep, "a"); a.Cause != CauseMechanism || !strings.HasPrefix(a.CauseDetail, "cleanup_unverified:supervisor_died:") {
		t.Fatalf("die after cleanup: %+v", a)
	}
	if h, _ := procsup.Halted(); !h {
		t.Fatal("not halted")
	}
	if count() != 0 || !alive(other.Process.Pid) {
		t.Fatalf("sweep calls %d, unrelated session alive %v", count(), alive(other.Process.Pid))
	}
}

// (2) of the same: a supervisor SIGKILLed mid-run.
func TestNoSessionSignallingAfterSupervisorDeath(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	calls := 0
	var mu sync.Mutex
	old := sweepSession
	sweepSession = func(int, time.Duration) error { mu.Lock(); calls++; mu.Unlock(); return nil }
	t.Cleanup(func() { sweepSession = old })
	sups := watchSupervisors(t)
	r, st := twoRunners(t, `echo $$ > "$D/a.pid"; exec sleep 300`, `row tests/b.sh pass`)
	done := make(chan *RunReport, 1)
	go func() { done <- runQuiet(t, r, "killed") }()
	sups.kill(t, filepath.Join(st, "a.pid"))
	<-done
	mu.Lock()
	defer mu.Unlock()
	if calls != 0 {
		t.Fatalf("sweep calls %d after a supervisor death", calls)
	}
}

// Without a supervisor (darwin, forced here) the runner runs as in M3.1:
// its own session, swept afterwards, containment none.
func TestUnsupervisedPath(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	defer procsup.SetUnavailableForTesting()()
	calls := 0
	old := sweepSession
	sweepSession = func(sid int, b time.Duration) error { calls++; return old(sid, b) }
	t.Cleanup(func() { sweepSession = old })
	r, _ := twoRunners(t, `row tests/a.sh pass`, `row tests/b.sh pass`)
	rep := runQuiet(t, r, "unsupervised")
	if rep.Exit() != 0 || calls < 2 || Overlappable() { // every describe, list and run is swept
		t.Fatalf("exit %d sweep calls %d overlappable %v", rep.Exit(), calls, Overlappable())
	}
	for _, rec := range rep.Invocations {
		if rec.Containment != procsup.None || rec.Boundary != procsup.None {
			t.Fatalf("%+v", rec)
		}
	}
}

// The supervised start path refuses an already-cancelled context before
// launching anything, as exec.CommandContext did.
func TestExecRunnerRefusesCancelledContext(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	marker := filepath.Join(t.TempDir(), "started")
	ctx, cancel := context.WithCancel(bg)
	cancel()
	res := execRunner(ctx, command{Path: "/bin/sh", Args: []string{"-c", "touch " + marker}}, 5*time.Second)
	if !errors.Is(res.StartErr, context.Canceled) {
		t.Fatalf("%+v", res)
	}
	if _, err := os.Stat(marker); err == nil {
		t.Fatal("the runner started with a cancelled context")
	}
}

// A describe the halt cancelled is refused, through Load, with the halt's
// detail (the engine's zero grace means the runner is killed; the zero-exit
// variant is TestDiscoveryResultClassification's).
func TestHaltedDiscoveryRefused(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	sups := watchSupervisors(t)
	r := newRepo(t, map[string]string{"tests/a.sh": ""})
	st := stateOf(t, r)
	p := RunnersDir + "/shell.sh"
	r.Write(t, p, "#!/usr/bin/env bash\nD="+strconv.Quote(st)+"\ncase \"$1\" in\n"+
		"describe) trap 'echo \"unit: file\"; exit 0' TERM; echo $$ > \"$D/desc.pid\"; sleep 300 & wait ;;\n"+
		"list) printf 'tests/a.sh\\tfile\\ta\\n' ;;\n*) exit 64 ;;\nesac\n")
	if err := os.Chmod(filepath.Join(r.Dir, filepath.FromSlash(p)), 0o755); err != nil {
		t.Fatal(err)
	}
	runners(t, r, "runners:\n  - name: shell\n")
	commitAll(t, r)
	other, err := procsup.Start(bg, procsup.Spec{Path: "/bin/sh", Args: []string{"-c", "exec sleep 300"}})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = syscall.Kill(other.Pid(), syscall.SIGKILL) }) // left by its supervisor's death
	done := make(chan error, 1)
	go func() { _, err := Load(bg, r.Dir); done <- err }()
	waitPid(t, filepath.Join(st, "desc.pid"))
	sups.mu.Lock()
	sup := sups.pid[other.Pid()]
	sups.mu.Unlock()
	if err := syscall.Kill(sup, syscall.SIGKILL); err != nil {
		t.Fatal(err)
	}
	if r := other.Wait(); !r.SupervisorDied {
		t.Fatalf("other: %+v", r)
	}
	err = <-done
	var le *LineError
	if !errors.As(err, &le) || le.Class != ClassProtocol || !strings.Contains(err.Error(), "describe") || !strings.Contains(err.Error(), "halted:supervisor_died:") {
		t.Fatalf("Load: %v", err)
	}
}

// A describe / list result is usable only when it ran to a clean exit 0
// with all its output: a halted or output-losing result is refused even with
// exit 0 — the halt's cancel can land after the runner exited on its own.
func TestDiscoveryResultClassification(t *testing.T) {
	for name, tc := range map[string]struct {
		r    execResult
		fail bool
	}{
		"clean":               {execResult{Exit: 0}, false},
		"halted, exit 0":      {execResult{Exit: 0, Halted: true, HaltDetail: "supervisor_died:x"}, true},
		"output lost, exit 0": {execResult{Exit: 0, OutputErr: errors.New("copy")}, true},
		"killed":              {execResult{Exit: -1, Killed: true}, true},
		"exit 1":              {execResult{Exit: 1}, true},
		"overflow":            {execResult{Exit: 0, Overflow: true}, true},
		"start":               {execResult{Exit: -1, StartErr: errors.New("x")}, true},
	} {
		if got := tc.r.failed(); got != tc.fail {
			t.Errorf("%s: failed() = %v", name, got)
		}
	}
	if got := (execResult{Exit: 0, Halted: true, HaltDetail: "d"}).exitText(); got != "halted:d" {
		t.Errorf("exitText %q", got)
	}
}
