//go:build linux

package runner

import (
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
)

// alive reports whether pid runs: absent or a zombie counts as gone.
func alive(pid int) bool {
	data, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		return false
	}
	p, _, ok := parseStat(pid, string(data))
	return ok && !p.Zombie
}

// statOf returns pid's process group and session.
func statOf(t *testing.T, pid int) (pgid, sid int) {
	t.Helper()
	data, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		t.Fatalf("pid %d: %v", pid, err)
	}
	p, s, ok := parseStat(pid, string(data))
	if !ok {
		t.Fatalf("unparsable stat for %d", pid)
	}
	return p.Pgid, s
}

// waitFile polls for a file the fixture runner writes.
func waitFile(t *testing.T, path string) {
	t.Helper()
	for end := time.Now().Add(10 * time.Second); time.Now().Before(end); time.Sleep(10 * time.Millisecond) {
		if _, err := os.Stat(path); err == nil {
			return
		}
	}
	t.Fatalf("%s never appeared", path)
}

// The supported arrangement a group-only kill misses: a per_unit runner puts
// its unit in a separate process group (job control), the unit forks a
// descendant, and the engine's max_invocation_s fires while both are alive.
// Both must be gone the moment Run returns — no polling.
func TestCleanupSeparateTestGroupOnInvocationTimeout(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{"tests/a.sh": ""})
	st := stateOf(t, r)
	put(t, r, "shell", spec{describe: "unit: file\ntimeouts: per_unit", list: "tests/a.sh|file|a\n", run: `echo $$ > "$D/runner.pid"
start tests/a.sh
set -m
( sleep 300 & echo $! > "$D/desc.pid"; exec sleep 300 ) &
echo $! > "$D/unit.pid"
wait`})
	runners(t, r, "max_invocation_s: 2\nrunners:\n  - name: shell\n    timeout_s: 1\n")
	commitAll(t, r)
	done := make(chan *RunReport, 1)
	go func() {
		rep, err := Run(bg, r.Dir, Options{All: true, RunID: "cleanup"})
		if err != nil {
			t.Error(err)
		}
		done <- rep
	}()
	waitFile(t, filepath.Join(st, "desc.pid"))
	waitFile(t, filepath.Join(st, "unit.pid"))
	runnerPid := readPid(t, filepath.Join(st, "runner.pid"))
	unitPid := readPid(t, filepath.Join(st, "unit.pid"))
	descPid := readPid(t, filepath.Join(st, "desc.pid"))
	rg, rs := statOf(t, runnerPid)
	ug, us := statOf(t, unitPid)
	dg, ds := statOf(t, descPid)
	if ug == rg || dg != ug {
		t.Fatalf("fixture shape: runner pgid %d, unit pgid %d, descendant pgid %d (want a separate unit group holding the descendant)", rg, ug, dg)
	}
	if rs != runnerPid || us != rs || ds != rs {
		t.Fatalf("fixture shape: sessions runner %d unit %d descendant %d (runner pid %d)", rs, us, ds, runnerPid)
	}
	rep := <-done
	if rep == nil {
		t.Fatal("no report")
	}
	if alive(unitPid) || alive(descPid) || alive(runnerPid) {
		t.Fatalf("survivors after Run returned: unit %v descendant %v runner %v", alive(unitPid), alive(descPid), alive(runnerPid))
	}
	if rec := rep.Invocations[0]; rec.TimedOut != BoundInvocationMax || rec.Cause != CauseTimeout || statuses(rep)["tests/a.sh"] != StatusTimeout {
		t.Fatalf("record %+v %v", rec, statuses(rep))
	}
}

// A runner that exits 0 but leaves processes behind — in its own group and
// in a separate one — has them swept before Run returns, and the clean sweep
// adds no cause.
func TestCleanupAfterNormalExit(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{"tests/a.sh": ""})
	st := stateOf(t, r)
	put(t, r, "shell", spec{describe: "unit: file", list: "tests/a.sh|file|a\n", run: `sleep 300 & echo $! > "$D/same.pid"
set -m; sleep 300 & echo $! > "$D/own.pid"; set +m
row tests/a.sh pass; exit 0`})
	runners(t, r, "runners:\n  - name: shell\n    timeout_s: 5\n")
	commitAll(t, r)
	rep := timedRun(t, r, 10*time.Second)
	same, own := readPid(t, filepath.Join(st, "same.pid")), readPid(t, filepath.Join(st, "own.pid"))
	if alive(same) || alive(own) {
		t.Fatalf("leftovers alive: same-group %v own-group %v", alive(same), alive(own))
	}
	if rec := rep.Invocations[0]; rec.Cause != "" || rep.Exit() != 0 {
		t.Fatalf("%+v exit %d", rec, rep.Exit())
	}
}

// Every engine-kill path sweeps: the unit bound (none), the batch bound and
// the invocation ceiling (per_unit).
func TestCleanupEveryKillPath(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	for _, tc := range []struct{ describe, yaml, bound string }{
		{"unit: file", "runners:\n  - name: shell\n    timeout_s: 0.5\n", BoundUnit},
		{"unit: file\ntimeouts: batch", "runners:\n  - name: shell\n    timeout_s: 0.5\n    batch_timeout_s: 0.5\n", BoundBatch},
		{"unit: file\ntimeouts: per_unit", "max_invocation_s: 0.5\nrunners:\n  - name: shell\n    timeout_s: 0.5\n", BoundInvocationMax},
	} {
		r := newRepo(t, map[string]string{"tests/a.sh": ""})
		st := stateOf(t, r)
		put(t, r, "shell", spec{describe: tc.describe, list: "tests/a.sh|file|a\n",
			run: `start tests/a.sh; set -m; sleep 300 & echo $! > "$D/bg.pid"; set +m; exec sleep 30`})
		runners(t, r, tc.yaml)
		commitAll(t, r)
		rep := timedRun(t, r, 10*time.Second)
		if pid := readPid(t, filepath.Join(st, "bg.pid")); alive(pid) {
			t.Errorf("%s: background process %d alive", tc.bound, pid)
		}
		if rec := rep.Invocations[0]; rec.TimedOut != tc.bound || rec.Cause != CauseTimeout {
			t.Errorf("%s: %+v", tc.bound, rec)
		}
	}
}

// sessionProcs finds a session's members (a zombie reported as such) and
// nothing outside it; sweepSession leaves none alive.
func TestSweepEnumeration(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	cmd := exec.Command("sh", "-c", "sleep 0.05 & exec sleep 300")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL); _ = cmd.Wait() })
	sid := cmd.Process.Pid
	var procs []proc
	for end := time.Now().Add(5 * time.Second); time.Now().Before(end); time.Sleep(20 * time.Millisecond) {
		var err error
		if procs, err = sessionProcs(sid); err != nil {
			t.Fatal(err)
		}
		if len(procs) == 2 && (procs[0].Zombie || procs[1].Zombie) {
			break
		}
	}
	if len(procs) != 2 || procs[0].Zombie == procs[1].Zombie {
		t.Fatalf("want the leader and one zombie, got %+v", procs)
	}
	for _, p := range procs {
		if p.Pid == os.Getpid() {
			t.Fatal("the test process is in the swept session")
		}
	}
	if err := sweepSession(sid); err != nil {
		t.Fatal(err)
	}
	if alive(sid) {
		t.Fatal("session leader alive after the sweep")
	}
}

// startSession starts `sleep 300` as the leader of a new session.
func startSession(t *testing.T) int {
	t.Helper()
	cmd := exec.Command("sleep", "300")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	done := make(chan struct{})
	go func() { _ = cmd.Wait(); close(done) }() // reap as soon as it dies, so "gone" is observable
	t.Cleanup(func() { _ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL); <-done })
	return cmd.Process.Pid
}

// injectStat makes /proc/<pid>/stat unreadable with errno for the given
// pids, and optionally replaces getsid — what a restricted process (another
// uid under a hidepid /proc, an LSM) answers.
func injectStat(t *testing.T, errno syscall.Errno, sidFn func(int) (int, error), pids ...int) {
	t.Helper()
	oldRead, oldSid := readStat, getsid
	readStat = func(pid int) ([]byte, error) {
		for _, p := range pids {
			if pid == p {
				return nil, &os.PathError{Op: "open", Path: "/proc/" + strconv.Itoa(pid) + "/stat", Err: errno}
			}
		}
		return oldRead(pid)
	}
	if sidFn != nil {
		getsid = sidFn
	}
	t.Cleanup(func() { readStat, getsid = oldRead, oldSid })
}

// An uninspectable member of the swept session is identified through
// getsid(2) and killed; an uninspectable process of another session is left
// alone; an uninspectable process whose session cannot be established makes
// the sweep cleanup_unverified, never a false clean.
func TestSweepUninspectableProcesses(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	t.Run("member", func(t *testing.T) {
		target := startSession(t)
		injectStat(t, syscall.EACCES, nil, target)
		if err := sweepSession(target); err != nil {
			t.Fatal(err)
		}
		if alive(target) {
			t.Fatal("uninspectable member survived the sweep")
		}
	})
	t.Run("unrelated", func(t *testing.T) {
		target, other := startSession(t), startSession(t)
		injectStat(t, syscall.EACCES, nil, other)
		if err := sweepSession(target); err != nil {
			t.Fatal(err)
		}
		if alive(target) || !alive(other) {
			t.Fatalf("target alive %v, unrelated alive %v", alive(target), alive(other))
		}
	})
	t.Run("unverifiable", func(t *testing.T) {
		target, other := startSession(t), startSession(t)
		realSid := getsid
		injectStat(t, syscall.EACCES, func(pid int) (int, error) {
			if pid == other {
				return 0, syscall.EPERM
			}
			return realSid(pid)
		}, other)
		err := sweepSession(target)
		if err == nil || !strings.HasPrefix(err.Error(), "cleanup_unverified:") {
			t.Fatalf("sweep: %v", err)
		}
		if !alive(other) {
			t.Fatal("a process of unknown session was killed")
		}
	})
	t.Run("vanished", func(t *testing.T) {
		target := startSession(t)
		injectStat(t, syscall.ENOENT, nil, target) // reads as exited: skipped
		procs, err := sessionProcs(target)
		if err != nil || len(procs) != 0 {
			t.Fatalf("%v %v", procs, err)
		}
	})
}
