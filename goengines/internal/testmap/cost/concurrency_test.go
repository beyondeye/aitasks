package cost

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync/atomic"
	"syscall"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// TestHelperAppend is the second process of TestConcurrentAppendDuringUpdate:
// it appends one run to the ledger at $COST_HELPER_ROOT. It does nothing in
// an ordinary test run.
func TestHelperAppend(t *testing.T) {
	root := os.Getenv("COST_HELPER_ROOT")
	if root == "" {
		return
	}
	appendLocks = os.Getenv("COST_HELPER_LOCK") == "1"
	newRB("test-helper", "ci", at2).inv(1, "g", 2, 1, "", false).result(1, "helper.sh", "pass", 1, "", "s", true).append(t, root)
}

// flockWaiting reports whether /proc/locks shows a process blocked on a
// flock of the file with inode ino.
func flockWaiting(t *testing.T, ino uint64) bool {
	data, err := os.ReadFile("/proc/locks")
	if err != nil {
		t.Fatal(err)
	}
	suffix := ":" + strconv.FormatUint(ino, 10)
	for _, line := range strings.Split(string(data), "\n") {
		if !strings.Contains(line, "-> FLOCK") {
			continue
		}
		for _, f := range strings.Fields(line) {
			if strings.HasSuffix(f, suffix) {
				return true
			}
		}
	}
	return false
}

// A run appended while `costs --update` holds the lock is neither folded
// twice nor lost: the second process blocks (proved through /proc/locks, not
// timing) until the truncation is done, then lands in the emptied ledger.
// The red control bypasses the append lock and must lose the row.
func TestConcurrentAppendDuringUpdate(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("proves the wait through /proc/locks")
	}
	for _, locked := range []bool{true, false} {
		t.Run(map[bool]string{true: "locked", false: "red-control-unlocked"}[locked], func(t *testing.T) {
			root := t.TempDir()
			newRB("test-1", "ci", at1).inv(1, "g", 2, 1, "", false).result(1, "first.sh", "pass", 1, "", "s", true).append(t, root)
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, os.Args[0], "-test.run=^TestHelperAppend$", "-test.count=1")
			cmd.Env = append(os.Environ(), "COST_HELPER_ROOT="+root, "COST_HELPER_LOCK="+map[bool]string{true: "1", false: "0"}[locked])
			var helperErr error
			waited := false
			testUpdateHeld = func() {
				if err := cmd.Start(); err != nil {
					t.Fatal(err)
				}
				if !locked {
					helperErr, waited = cmd.Wait(), true
					return
				}
				var st syscall.Stat_t
				if err := syscall.Stat(filepath.Join(root, LockPath), &st); err != nil {
					t.Fatal(err)
				}
				deadline := time.Now().Add(20 * time.Second)
				for !flockWaiting(t, st.Ino) {
					if time.Now().After(deadline) {
						t.Fatal("the helper never blocked on the ledger lock")
					}
					time.Sleep(10 * time.Millisecond)
				}
			}
			t.Cleanup(func() { testUpdateHeld = nil })
			if _, err := Update(root); err != nil {
				t.Fatal(err)
			}
			testUpdateHeld = nil
			if !waited {
				helperErr = cmd.Wait()
			}
			if helperErr != nil {
				t.Fatalf("helper: %v", helperErr)
			}
			ledger, _ := os.ReadFile(filepath.Join(root, LedgerPath))
			kept := strings.Contains(string(ledger), `"run_id":"test-helper"`)
			tb := load(t, root, "ci")
			if _, ok := tb.ID("first.sh"); !ok {
				t.Fatal("the run before the update was not folded")
			}
			if locked && (!kept || tb.Pending != 1) {
				t.Fatalf("the concurrent append was lost: ledger %q pending %d", ledger, tb.Pending)
			}
			if !locked && kept {
				t.Fatalf("red control: an unlocked append survived the truncation: %q", ledger)
			}
		})
	}
}

// waitFlockWaiter fails the test unless some process (this one included)
// blocks on a flock of path within the deadline.
func waitFlockWaiter(t *testing.T, path string) {
	t.Helper()
	var st syscall.Stat_t
	if err := syscall.Stat(path, &st); err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(5 * time.Second)
	for !flockWaiting(t, st.Ino) {
		if time.Now().After(deadline) {
			t.Fatalf("nothing ever blocked on %s", path)
		}
		time.Sleep(5 * time.Millisecond)
	}
}

// A read that starts while `costs --update` holds the lock sees the run the
// update is folding — never the old table with the truncated ledger. The
// reader is proved blocked (/proc/locks) before the update writes the table
// and truncates; Load and LoadAll both.
func TestLoadConsistentWithConcurrentUpdate(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("proves the wait through /proc/locks")
	}
	for _, all := range []bool{false, true} {
		t.Run(map[bool]string{false: "Load", true: "LoadAll"}[all], func(t *testing.T) {
			root := t.TempDir()
			newRB("test-1", "ci", at1).inv(1, "g", 2, 1, "", false).result(1, "folded.sh", "pass", 1, "", "s", true).append(t, root)
			got := make(chan *Table, 1)
			testUpdateHeld = func() {
				go func() {
					if all {
						tables, err := LoadAll(root)
						if err != nil {
							t.Error(err)
						}
						got <- tables["ci"]
						return
					}
					tb, err := Load(root, "ci")
					if err != nil {
						t.Error(err)
					}
					got <- tb
				}()
				waitFlockWaiter(t, filepath.Join(root, LockPath))
			}
			t.Cleanup(func() { testUpdateHeld = nil })
			if _, err := Update(root); err != nil {
				t.Fatal(err)
			}
			testUpdateHeld = nil
			tb := <-got
			if tb == nil {
				t.Fatal("the reader saw no ci table")
			}
			if _, ok := tb.ID("folded.sh"); !ok {
				t.Fatalf("the run the update folded is in neither view: %+v", tb)
			}
		})
	}
}

// Two concurrent appends of distinct scored runs both land: the second
// blocks (proved through /proc/locks) on the stores lock while the first is
// between its read and its write.
func TestAppendPredictionInterleaving(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("proves the wait through /proc/locks")
	}
	root := fixture.New(t).Dir
	done := make(chan error, 1)
	var once atomic.Bool
	testPredictionsRead = func() {
		if !once.CompareAndSwap(false, true) {
			return
		}
		go func() {
			_, err := AppendPrediction(root, map[string]any{"run_id": "full-b"})
			done <- err
		}()
		waitFlockWaiter(t, filepath.Join(root, ".git", "ait-testmap", "costs.lock"))
	}
	t.Cleanup(func() { testPredictionsRead = nil })
	if _, err := AppendPrediction(root, map[string]any{"run_id": "full-a"}); err != nil {
		t.Fatal(err)
	}
	if err := <-done; err != nil {
		t.Fatal(err)
	}
	p, err := ReadPredictions(root)
	if err != nil || len(p.Scored) != 2 || p.Scored[0]["run_id"] != "full-a" || p.Scored[1]["run_id"] != "full-b" {
		t.Fatalf("predictions %+v %v", p, err)
	}
}
