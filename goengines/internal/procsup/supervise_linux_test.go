//go:build linux

package procsup

import (
	"bufio"
	"bytes"
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

	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

// sh is a /bin/sh -c command.
func sh(script string) Spec { return Spec{Path: "/bin/sh", Args: []string{"-c", script}} }

// pidFile polls for a pid a fixture writes.
func pidFile(t *testing.T, path string) int {
	t.Helper()
	for end := time.Now().Add(10 * time.Second); time.Now().Before(end); time.Sleep(10 * time.Millisecond) {
		b, err := os.ReadFile(path)
		if s := strings.TrimSpace(string(b)); err == nil && s != "" {
			pid, err := strconv.Atoi(s)
			if err != nil {
				t.Fatalf("%s: %q", path, s)
			}
			return pid
		}
	}
	t.Fatalf("%s never appeared", path)
	return 0
}

// killAfter makes sure a fixture process the test deliberately leaves alive
// does not outlive it.
func killAfter(t *testing.T, pid int) {
	t.Cleanup(func() { _ = syscall.Kill(pid, syscall.SIGKILL) })
}

// resetHalt clears the process-wide halt state a test set.
func resetHalt(t *testing.T) {
	t.Cleanup(func() {
		admitMu.Lock()
		halted, haltDetail = false, ""
		admitMu.Unlock()
	})
}

func startWait(t *testing.T, s Spec) Result {
	t.Helper()
	p, err := Start(context.Background(), s)
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	return p.Wait()
}

// The command's exit status and output reach the caller, and every
// descendant that left by setsid() — a setsid child and a double-forked
// setsid daemon — is dead when Wait returns.
func TestSuperviseSetsidDescendants(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	d := t.TempDir()
	var out bytes.Buffer
	s := sh(`setsid sleep 300 & echo $! > ` + d + `/child.pid
setsid sh -c 'sleep 300 & echo $! > ` + d + `/daemon.pid' &
wait $!
while [ ! -s ` + d + `/daemon.pid ]; do sleep 0.01; done
echo hello; exit 7`)
	s.Stdout = &out
	r := startWait(t, s)
	child, daemon := pidFile(t, d+"/child.pid"), pidFile(t, d+"/daemon.pid")
	if r.Exit != 7 || r.Cleanup != nil || r.SupervisorDied || r.StartErr != nil || strings.TrimSpace(out.String()) != "hello" {
		t.Fatalf("result %+v output %q", r, out.String())
	}
	if alive(child) || alive(daemon) {
		t.Fatalf("setsid child alive %v, setsid daemon alive %v", alive(child), alive(daemon))
	}
	if r.Pid <= 0 {
		t.Fatalf("no command pid: %+v", r)
	}
}

// A double-forked orphan and a grandchild in its own process group are
// killed too.
func TestSuperviseOrphanAndOwnGroup(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	d := t.TempDir()
	r := startWait(t, sh(`( sleep 300 & echo $! > `+d+`/orphan.pid ) &
wait $!
set -m; sleep 300 & echo $! > `+d+`/group.pid; set +m
exit 0`))
	orphan, group := pidFile(t, d+"/orphan.pid"), pidFile(t, d+"/group.pid")
	if r.Exit != 0 || r.Cleanup != nil {
		t.Fatalf("%+v", r)
	}
	if alive(orphan) || alive(group) {
		t.Fatalf("orphan alive %v, own-group grandchild alive %v", alive(orphan), alive(group))
	}
}

// The cleanup ends only at ECHILD: a chain of live setsid parents three deep
// takes one kill round per level (each killed parent's child reparents to the
// supervisor), and none of it survives the command's exit.
func TestSuperviseCleanupEndsAtECHILD(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	d := t.TempDir()
	r := startWait(t, sh(`setsid sh -c 'setsid sh -c "sleep 300 & echo \$! > `+d+`/leaf.pid; wait" & wait' &
while [ ! -s `+d+`/leaf.pid ]; do sleep 0.01; done; exit 0`))
	leaf := pidFile(t, d+"/leaf.pid")
	if r.Cleanup != nil || alive(leaf) {
		t.Fatalf("%+v; leaf alive %v", r, alive(leaf))
	}
}

// A zombie the command never reaps does not hold the cleanup up.
func TestSuperviseZombie(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	start := time.Now()
	rr := Run(context.Background(), RunSpec{Path: "/bin/sh", Args: []string{"-c", "sleep 0.01 & exec sleep 300"}, Timeout: 300 * time.Millisecond})
	if !rr.TimedOut || rr.Cleanup != nil || rr.SupervisorDied {
		t.Fatalf("%+v", rr)
	}
	if el := time.Since(start); el > 3*time.Second {
		t.Fatalf("took %v", el)
	}
}

// Timeout: SIGTERM first; a command that honours it ends on its own; one
// that ignores it is killed after the grace.
func TestRunTimeoutSIGTERMThenKill(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	d := t.TempDir()
	honour := Run(context.Background(), RunSpec{Path: "/bin/sh", Args: []string{"-c", `trap 'echo term > ` + d + `/term; exit 3' TERM; sleep 300 & wait`},
		Timeout: 200 * time.Millisecond, Grace: 5 * time.Second})
	if _, err := os.Stat(d + "/term"); err != nil || !honour.TimedOut || honour.Exit != 3 || honour.Cleanup != nil {
		t.Fatalf("honouring: %+v (term file: %v)", honour, err)
	}
	start := time.Now()
	ignore := Run(context.Background(), RunSpec{Path: "/bin/sh", Args: []string{"-c", `trap '' TERM; sleep 300 & echo $! > ` + d + `/ign.pid; wait`},
		Timeout: 200 * time.Millisecond, Grace: 300 * time.Millisecond})
	if !ignore.TimedOut || ignore.Signal != syscall.SIGKILL.String() || ignore.Cleanup != nil {
		t.Fatalf("ignoring: %+v", ignore)
	}
	if el := time.Since(start); el < 500*time.Millisecond || el > 4*time.Second {
		t.Fatalf("ignoring took %v (want timeout + grace)", el)
	}
	if pid := pidFile(t, d+"/ign.pid"); alive(pid) {
		t.Fatal("the SIGTERM-ignoring grandchild survived")
	}
}

// Cancelling the caller's context stops the command the same way.
func TestRunCancellation(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	d := t.TempDir()
	ctx, cancel := context.WithCancel(context.Background())
	go func() { pidFile(t, d+"/run.pid"); cancel() }()
	rr := Run(ctx, RunSpec{Path: "/bin/sh", Args: []string{"-c", "sleep 300 & echo $! > " + d + "/run.pid; wait"}})
	if !rr.Cancelled || rr.TimedOut || rr.Cleanup != nil {
		t.Fatalf("%+v", rr)
	}
	if alive(pidFile(t, d+"/run.pid")) {
		t.Fatal("alive after cancellation")
	}
}

// Output past the cap is dropped, drained and flagged.
func TestRunOutputCap(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	d := t.TempDir()
	rr := Run(context.Background(), RunSpec{Path: "/bin/sh", Args: []string{"-c", "head -c 200000 /dev/zero; echo done >&2"},
		Stdout: d + "/out", Stderr: d + "/err", OutputMax: 1000})
	fi, err := os.Stat(d + "/out")
	if err != nil || fi.Size() != 1000 || !rr.Truncated || rr.Exit != 0 {
		t.Fatalf("%+v size %v %v", rr, fi.Size(), err)
	}
	if b, _ := os.ReadFile(d + "/err"); string(b) != "done\n" {
		t.Fatalf("stderr %q", b)
	}
}

// The parent's death (EOF on the control pipe) makes the supervisor clean up
// its subtree and exit.
func TestSuperviseParentDeath(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	d := t.TempDir()
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	parent := exec.Command(exe, parentArg, "setsid sleep 300 & echo $! > "+d+"/daemon.pid; wait")
	stdout, err := parent.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err := parent.Start(); err != nil {
		t.Fatal(err)
	}
	line, err := bufio.NewReader(stdout).ReadString('\n')
	if err != nil {
		t.Fatal(err)
	}
	f := strings.Fields(line)
	if len(f) != 2 {
		t.Fatalf("parent: %q", line)
	}
	sup, _ := strconv.Atoi(f[0])
	daemon := pidFile(t, d+"/daemon.pid")
	killAfter(t, daemon)
	killAfter(t, sup)
	_ = parent.Process.Kill()
	_ = parent.Wait()
	for end := time.Now().Add(SweepTimeout + 2*time.Second); time.Now().Before(end) && (alive(daemon) || alive(sup)); time.Sleep(20 * time.Millisecond) {
	}
	if alive(daemon) || alive(sup) {
		t.Fatalf("after the parent's death: daemon alive %v, supervisor alive %v", alive(daemon), alive(sup))
	}
}

// A supervisor's death halts: its own result says SupervisorDied (and its
// daemon is left — the stated residual), the other active supervisor is
// cancelled and cleans up, and a later Start launches nothing.
func TestSupervisorDeathHalts(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	resetHalt(t)
	d := t.TempDir()
	var mu sync.Mutex
	sups := map[int]int{} // command pid → supervisor pid
	defer OnStartForTesting(func(s, c int) { mu.Lock(); sups[c] = s; mu.Unlock() })()
	launches := 0
	defer OnLaunchForTesting(func() { mu.Lock(); launches++; mu.Unlock() })()
	s1, err := Start(context.Background(), sh("setsid sleep 300 & echo $! > "+d+"/d1.pid; wait"))
	if err != nil {
		t.Fatal(err)
	}
	s2, err := Start(context.Background(), sh("setsid sleep 300 & echo $! > "+d+"/d2.pid; wait"))
	if err != nil {
		t.Fatal(err)
	}
	d1, d2 := pidFile(t, d+"/d1.pid"), pidFile(t, d+"/d2.pid")
	killAfter(t, d1)
	killAfter(t, d2)
	mu.Lock()
	sup1 := sups[s1.Pid()]
	mu.Unlock()
	if err := syscall.Kill(sup1, syscall.SIGKILL); err != nil {
		t.Fatal(err)
	}
	r1 := s1.Wait()
	if !r1.SupervisorDied || !strings.Contains(r1.Detail, "killed") {
		t.Fatalf("s1: %+v", r1)
	}
	if h, detail := Halted(); !h || !strings.HasPrefix(detail, "supervisor_died:") {
		t.Fatalf("halted %v %q", h, detail)
	}
	r2 := s2.Wait()
	if !r2.Halted || !r2.Cancelled || r2.Cleanup != nil || r2.HaltDetail == "" || alive(d2) {
		t.Fatalf("s2: %+v; daemon alive %v", r2, alive(d2))
	}
	mu.Lock()
	before := launches
	mu.Unlock()
	_, err = Start(context.Background(), sh("echo $$ > "+d+"/late.pid"))
	var he *HaltedError
	if !errors.As(err, &he) || !strings.HasPrefix(he.Error(), "halted:supervisor_died:") {
		t.Fatalf("late start: %v", err)
	}
	mu.Lock()
	after := launches
	mu.Unlock()
	if _, serr := os.Stat(d + "/late.pid"); after != before || serr == nil {
		t.Fatalf("a halted Start launched (%d → %d, marker %v)", before, after, serr)
	}
	if !alive(d1) {
		t.Fatal("the dead supervisor's daemon is gone: the residual this test documents did not occur (the assertion is stale)")
	}
}

// A Start overlapping a halt is either refused or included in its
// cancellation: one paused after admission (P1) is cancelled at activation,
// one paused before admission (P2) is refused and launches nothing.
func TestHaltStartInterleavings(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	resetHalt(t)
	d := t.TempDir()
	var mu sync.Mutex
	sups := map[int]int{}
	launches := 0
	defer OnStartForTesting(func(s, c int) { mu.Lock(); sups[c] = s; mu.Unlock() })()
	defer OnLaunchForTesting(func() { mu.Lock(); launches++; mu.Unlock() })()
	s1, err := Start(context.Background(), sh("sleep 300"))
	if err != nil {
		t.Fatal(err)
	}
	killAfter(t, s1.Pid()) // left behind by its supervisor's death: the residual
	admits, atLaunch := 0, 0
	p1Paused, p2Paused := make(chan struct{}), make(chan struct{})
	releaseP1, releaseP2 := make(chan struct{}), make(chan struct{})
	defer BeforeAdmitForTesting(func() {
		mu.Lock()
		admits++
		n := admits
		mu.Unlock()
		if n == 2 { // P2
			close(p2Paused)
			<-releaseP2
		}
	})()
	defer BeforeLaunchForTesting(func() {
		mu.Lock()
		atLaunch++
		n := atLaunch
		mu.Unlock()
		if n == 1 { // P1
			close(p1Paused)
			<-releaseP1
		}
	})()
	type res struct {
		p   *Proc
		err error
	}
	c1, c2 := make(chan res, 1), make(chan res, 1)
	go func() { p, err := Start(context.Background(), sh("exec sleep 300")); c1 <- res{p, err} }()
	<-p1Paused
	go func() {
		p, err := Start(context.Background(), sh("echo $$ > "+d+"/p2.pid; exec sleep 300"))
		c2 <- res{p, err}
	}()
	<-p2Paused
	mu.Lock()
	sup1 := sups[s1.Pid()]
	mu.Unlock()
	_ = syscall.Kill(sup1, syscall.SIGKILL)
	if r := s1.Wait(); !r.SupervisorDied {
		t.Fatalf("s1: %+v", r)
	}
	if h, _ := Halted(); !h {
		t.Fatal("not halted")
	}
	close(releaseP1)
	close(releaseP2)
	r1 := <-c1
	if r1.err != nil {
		t.Fatalf("P1 (reserved before the halt) was refused: %v", r1.err)
	}
	if res := r1.p.Wait(); !res.Halted || res.Cleanup != nil || res.Pid <= 0 || alive(res.Pid) {
		t.Fatalf("P1: %+v (command alive %v)", res, alive(res.Pid))
	}
	r2 := <-c2
	var he *HaltedError
	if !errors.As(r2.err, &he) {
		t.Fatalf("P2 (admitted after the halt): %v", r2.err)
	}
	mu.Lock()
	n := launches
	mu.Unlock()
	if _, err := os.Stat(d + "/p2.pid"); n != 2 || err == nil {
		t.Fatalf("launches %d (want s1 and P1), P2 marker %v", n, err)
	}
}

// A test binary that forgot MaybeSupervise runs its suite instead of
// supervising; the bootstrap guard keeps it from launching another
// supervisor, and the missing handshake bounds it.
func TestOmittedDispatchIsBoundedAndNonRecursive(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	resetHalt(t)
	log := filepath.Join(t.TempDir(), "launches")
	defer OnLaunchForTesting(func() { appendLine(log, "outer") })()
	old := HandshakeTimeout
	HandshakeTimeout = time.Second
	t.Cleanup(func() { HandshakeTimeout = old })
	start := time.Now()
	r := startWait(t, Spec{Path: "/bin/true", Env: append(os.Environ(), omitDispatchEnv+"=1", launchLogEnv+"="+log)})
	if !r.SupervisorDied || r.Detail != "missing handshake" {
		t.Fatalf("%+v", r)
	}
	if el := time.Since(start); el > 4*time.Second {
		t.Fatalf("took %v", el)
	}
	b, _ := os.ReadFile(log)
	if lines := strings.Split(strings.TrimSpace(string(b)), "\n"); len(lines) != 1 || lines[0] != "outer" {
		t.Fatalf("launch log %q: the misdispatched binary launched a supervisor", b)
	}
}

// Start refuses before any launch inside an undispatched supervisor launch.
func TestDispatchGuard(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	t.Setenv(sentinelEnv, "1")
	launched := false
	defer OnLaunchForTesting(func() { launched = true })()
	if _, err := Start(context.Background(), sh("true")); !errors.As(err, new(*DispatchError)) || launched {
		t.Fatalf("err %v launched %v", err, launched)
	}
}

// The supervised command never sees the bootstrap sentinel, so a supervised
// builtin's own supervisors are not refused.
func TestSentinelScrubbed(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	var out bytes.Buffer
	s := sh("env")
	s.Stdout = &out
	if r := startWait(t, s); r.Exit != 0 || out.Len() == 0 {
		t.Fatalf("%+v %q", r, out.String())
	}
	if strings.Contains(out.String(), sentinelEnv) {
		t.Fatalf("%s reached the command", sentinelEnv)
	}
}

// A supervisor that dies after a complete cleanup, before its status, is
// still a death: nothing is known about its cleanup, and it halts.
func TestDieAfterCleanup(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	resetHalt(t)
	s := sh("exit 0")
	s.Env = append(os.Environ(), dieAfterEnv+"=1")
	r := startWait(t, s)
	if !r.SupervisorDied {
		t.Fatalf("%+v", r)
	}
	if h, _ := Halted(); !h {
		t.Fatal("not halted")
	}
}

// A supervisor that breaks the status protocol counts as dead.
func TestStatusProtocolViolations(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	resetHalt(t)
	d := t.TempDir()
	old, oldHS := SupervisorExe, HandshakeTimeout
	t.Cleanup(func() { SupervisorExe, HandshakeTimeout = old, oldHS })
	HandshakeTimeout = 300 * time.Millisecond
	for name, body := range map[string]string{
		"malformed status":  `echo '{"pid":1}' >&4; echo 'garbage' >&4`,
		"no final status":   `echo '{"pid":1}' >&4`,
		"missing handshake": `sleep 5`,
		"unknown field":     `echo '{"pid":1}' >&4; echo '{"exit":0,"cleanup":"ok","extra":1}' >&4`,
	} {
		fake := filepath.Join(d, strings.ReplaceAll(name, " ", "_"))
		if err := os.WriteFile(fake, []byte("#!/bin/sh\n"+body+"\nexit 0\n"), 0o755); err != nil {
			t.Fatal(err)
		}
		SupervisorExe = func() (string, error) { return fake, nil }
		admitMu.Lock()
		halted, haltDetail = false, "" // each case halts; the next one starts afresh
		admitMu.Unlock()
		if r := startWait(t, sh("true")); !r.SupervisorDied {
			t.Errorf("%s: %+v", name, r)
		}
	}
}

// The forced CONTAINMENT_UNAVAILABLE refusal: Start and Run refuse, and only
// an explicitly uncontained (test-only) Run executes, marked as such.
func TestContainmentUnavailable(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	defer SetUnavailableForTesting()()
	_, err := Start(context.Background(), sh("true"))
	var ue *UnavailableError
	if !errors.As(err, &ue) || ue.Line() != "CONTAINMENT_UNAVAILABLE:linux" {
		t.Fatalf("Start: %v", err)
	}
	if rr := Run(context.Background(), RunSpec{Path: "/bin/true"}); !errors.As(rr.StartErr, &ue) {
		t.Fatalf("Run: %+v", rr)
	}
	if rr := Run(context.Background(), RunSpec{Path: "/bin/true", AllowUncontained: true}); rr.StartErr != nil || rr.Exit != 0 || rr.Containment != None {
		t.Fatalf("uncontained Run: %+v", rr)
	}
}

// An already-done context is refused before anything is launched — by
// Start and by Run.
func TestStartRefusesDoneContext(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	launches := 0
	defer OnLaunchForTesting(func() { launches++ })()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if p, err := Start(ctx, sh("true")); !errors.Is(err, context.Canceled) || p != nil {
		t.Fatalf("Start: %v %v", p, err)
	}
	rr := Run(ctx, RunSpec{Path: "/bin/true"})
	if !errors.Is(rr.StartErr, context.Canceled) || !rr.Cancelled || launches != 0 {
		t.Fatalf("Run: %+v, launches %d", rr, launches)
	}
}

// A cancellation that arrives while the handshake is still pending is not
// lost and does not abandon the launched supervisor: it is delivered at
// activation, the command is stopped, and Wait reports the cleanup.
func TestCancelDuringHandshake(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer OnLaunchForTesting(cancel)() // cancelled just before the supervisor starts
	p, err := Start(ctx, sh("exec sleep 300"))
	if err != nil {
		t.Fatalf("Start after a launch must hand back the Proc: %v", err)
	}
	start := time.Now()
	r := p.Wait()
	if !r.Cancelled || r.Cleanup != nil || r.SupervisorDied || r.Pid <= 0 || alive(r.Pid) {
		t.Fatalf("%+v (command alive %v)", r, alive(r.Pid))
	}
	if el := time.Since(start); el > 5*time.Second {
		t.Fatalf("took %v", el)
	}
}

// Lost output is reported, never a clean result: a caller's writer that
// fails (the output copy error), and an output file whose writes fail.
func TestOutputLossReported(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	s := sh("echo hello")
	s.Stdout = failingWriter{}
	if r := startWait(t, s); r.OutputErr == nil || r.Exit != 0 {
		t.Fatalf("failing writer: %+v", r)
	}
}

type failingWriter struct{}

func (failingWriter) Write([]byte) (int, error) { return 0, errors.New("writer refused") }

// A capped output file keeps the first write error (and keeps draining)
// rather than hiding it, and close reports it.
func TestCappedFileKeepsWriteError(t *testing.T) {
	c, err := openCapped(filepath.Join(t.TempDir(), "out"), 100)
	if err != nil {
		t.Fatal(err)
	}
	if err := c.f.Close(); err != nil { // the next write fails
		t.Fatal(err)
	}
	if n, err := c.Write([]byte("hello")); n != 5 || err != nil {
		t.Fatalf("Write %d %v: must keep draining", n, err)
	}
	if err := c.close(); !errors.Is(err, os.ErrClosed) {
		t.Fatalf("close: %v", err)
	}
}

// Output setup never blocks and accepts only a regular file: a FIFO with no
// reader (directly or through a link), a link to a regular file and a device
// are refused at once, before anything is launched, whatever the deadline.
func TestRunRefusesNonRegularOutputs(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	d := t.TempDir()
	fifo := filepath.Join(d, "fifo")
	if err := syscall.Mkfifo(fifo, 0o644); err != nil {
		t.Fatal(err)
	}
	reg := filepath.Join(d, "regular")
	if err := os.WriteFile(reg, []byte("old"), 0o644); err != nil {
		t.Fatal(err)
	}
	for name, target := range map[string]string{"fifo": fifo, "regular": reg} {
		if err := os.Symlink(target, filepath.Join(d, "link-"+name)); err != nil {
			t.Fatal(err)
		}
	}
	launches := 0
	defer OnLaunchForTesting(func() { launches++ })()
	for _, out := range []string{fifo, filepath.Join(d, "link-fifo"), filepath.Join(d, "link-regular"), "/dev/null"} {
		for _, stream := range []string{"stdout", "stderr"} {
			s := RunSpec{Path: "/bin/true", Timeout: 30 * time.Millisecond}
			if stream == "stdout" {
				s.Stdout = out
			} else {
				s.Stderr = out
			}
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
			start := time.Now()
			rr := Run(ctx, s)
			cancel()
			if rr.StartErr == nil || time.Since(start) > time.Second {
				t.Errorf("%s %s: %+v after %v", stream, out, rr, time.Since(start))
			}
		}
	}
	// The refusal names why, also where the open itself succeeds: a device,
	// and a FIFO that does have a reader (the non-blocking open succeeds).
	rd, err := os.OpenFile(fifo, os.O_RDONLY|syscall.O_NONBLOCK, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer rd.Close()
	for _, out := range []string{"/dev/null", fifo} {
		if rr := Run(context.Background(), RunSpec{Path: "/bin/true", Stdout: out}); rr.StartErr == nil || !strings.Contains(rr.StartErr.Error(), "not a regular file") {
			t.Errorf("%s: %v", out, rr.StartErr)
		}
	}
	if launches != 0 {
		t.Fatalf("%d launches for refused outputs", launches)
	}
	if b, _ := os.ReadFile(reg); string(b) != "old" {
		t.Fatalf("the link's regular target was written: %q", b)
	}
	// A regular file is created, or truncated when it exists.
	out := filepath.Join(d, "fresh")
	if rr := Run(context.Background(), RunSpec{Path: "/bin/echo", Args: []string{"x"}, Stdout: out}); rr.StartErr != nil || rr.OutputErr != nil {
		t.Fatalf("regular: %+v", rr)
	}
	if rr := Run(context.Background(), RunSpec{Path: "/bin/true", Stdout: out}); rr.StartErr != nil {
		t.Fatalf("regular again: %+v", rr)
	}
	if b, _ := os.ReadFile(out); len(b) != 0 {
		t.Fatalf("not truncated: %q", b)
	}
}
