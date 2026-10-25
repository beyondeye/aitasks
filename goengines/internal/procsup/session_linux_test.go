//go:build linux

package procsup

import (
	"os"
	"os/exec"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

// hangLimit bounds one isolated test of this package.
const hangLimit = 20 * time.Second

// alive reports whether pid runs: absent or a zombie counts as gone.
func alive(pid int) bool {
	data, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		return false
	}
	p, _, ok := parseStat(pid, string(data))
	return ok && !p.Zombie
}

// SessionProcs finds a session's members (a zombie reported as such) and
// nothing outside it; SweepSession leaves none alive.
func TestSweepEnumeration(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	cmd := exec.Command("sh", "-c", "sleep 0.05 & exec sleep 300")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL); _ = cmd.Wait() })
	sid := cmd.Process.Pid
	var procs []SessionProc
	for end := time.Now().Add(5 * time.Second); time.Now().Before(end); time.Sleep(20 * time.Millisecond) {
		var err error
		if procs, err = SessionProcs(sid); err != nil {
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
	if err := SweepSession(sid, SweepTimeout); err != nil {
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
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	t.Run("member", func(t *testing.T) {
		target := startSession(t)
		injectStat(t, syscall.EACCES, nil, target)
		if err := SweepSession(target, SweepTimeout); err != nil {
			t.Fatal(err)
		}
		if alive(target) {
			t.Fatal("uninspectable member survived the sweep")
		}
	})
	t.Run("unrelated", func(t *testing.T) {
		target, other := startSession(t), startSession(t)
		injectStat(t, syscall.EACCES, nil, other)
		if err := SweepSession(target, SweepTimeout); err != nil {
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
		err := SweepSession(target, SweepTimeout)
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
		procs, err := SessionProcs(target)
		if err != nil || len(procs) != 0 {
			t.Fatalf("%v %v", procs, err)
		}
	})
}
