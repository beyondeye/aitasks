//go:build linux

package runner

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

// proc is one process's state, process group and session as /proc reports
// them (the session code itself lives in procsup).
type proc struct {
	Pid, Pgid int
	Zombie    bool
}

// parseStat reads state, process group and session from a stat line; the
// command name is in parentheses and may itself contain spaces or ')'.
func parseStat(pid int, line string) (proc, int, bool) {
	i := strings.LastIndexByte(line, ')')
	if i < 0 {
		return proc{}, 0, false
	}
	f := strings.Fields(line[i+1:])
	if len(f) < 4 {
		return proc{}, 0, false
	}
	pgid, err1 := strconv.Atoi(f[2])
	sid, err2 := strconv.Atoi(f[3])
	if err1 != nil || err2 != nil {
		return proc{}, 0, false
	}
	return proc{Pid: pid, Pgid: pgid, Zombie: f[0] == "Z" || f[0] == "X"}, sid, true
}

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
