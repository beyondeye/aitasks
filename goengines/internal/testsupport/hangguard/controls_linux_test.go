//go:build linux

package hangguard

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
)

// hangLimit bounds the controls' own subprocesses, as the runner package
// bounds its tests.
const hangLimit = 20 * time.Second

// readPid reads a pid file a fixture wrote.
func readPid(t *testing.T, path string) int {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(b)))
	if err != nil {
		t.Fatal(err)
	}
	return pid
}

// controlEnv puts TestIsolationControls in fixture mode: `<mode>|<dir>`.
const controlEnv = "AIT_HANGGUARD_CONTROL"

// noisyBytes is what the noisy fixture writes before its PASS line: far past
// outputCap.
const noisyBytes = 10 << 20

// procLive reads /proc directly (not through the injectable readers): pid
// exists and is not a zombie.
func procLive(pid int) bool {
	b, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		return false
	}
	_, state, ok := parseWdStat(pid, b)
	return ok && state != "Z" && state != "X"
}

// sessionOf is pid's session id, -1 when it cannot be read.
func sessionOf(pid int) int {
	b, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		return -1
	}
	p, _, ok := parseWdStat(pid, b)
	if !ok {
		return -1
	}
	return p.sid
}

func readLines(t *testing.T, path string) []string {
	t.Helper()
	b, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil
	}
	if err != nil {
		t.Fatal(err)
	}
	return strings.Fields(string(b))
}

func appendLine(t *testing.T, path, line string) {
	t.Helper()
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if _, err := f.WriteString(line + "\n"); err != nil {
		t.Fatal(err)
	}
}

// spawnEscaped starts, leading a session of its own, a shell that forks a
// background sleep and then becomes a sleep itself — the shape execRunner's
// Setsid leaves behind — records both pids in dir, never waits for them, and
// writes dir/ready: "shape ok" when both sit outside this process's session.
func spawnEscaped(t *testing.T, dir string) {
	t.Helper()
	cmd := exec.Command("sh", "-c", `sleep 300 & echo $! > "$1/bg.tmp" && mv "$1/bg.tmp" "$1/bg.pid"
echo $$ > "$1/leader.tmp" && mv "$1/leader.tmp" "$1/leader.pid"
exec sleep 300`, "sh", dir)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	for end := time.Now().Add(5 * time.Second); ; time.Sleep(5 * time.Millisecond) {
		_, e1 := os.Stat(filepath.Join(dir, "bg.pid"))
		_, e2 := os.Stat(filepath.Join(dir, "leader.pid"))
		if e1 == nil && e2 == nil {
			break
		}
		if time.Now().After(end) {
			t.Fatal("the escaped processes never recorded their pids")
		}
	}
	leader, bg := readPid(t, filepath.Join(dir, "leader.pid")), readPid(t, filepath.Join(dir, "bg.pid"))
	own, ls, bs := sessionOf(os.Getpid()), sessionOf(leader), sessionOf(bg)
	shape := "shape ok"
	if ls != leader || ls == own || bs != ls {
		shape = fmt.Sprintf("shape: leader %d session %d, background session %d, own session %d", leader, ls, bs, own)
	}
	if err := os.WriteFile(filepath.Join(dir, "ready"), []byte(shape), 0o644); err != nil {
		t.Fatal(err)
	}
}

// recordSubtests records every subtest it actually runs (a, b, b/c) and the
// GOMAXPROCS of the pass.
func recordSubtests(t *testing.T, dir string) {
	appendLine(t, filepath.Join(dir, "procs"), strconv.Itoa(runtime.GOMAXPROCS(0)))
	for _, n := range []string{"a", "b"} {
		t.Run(n, func(t *testing.T) {
			appendLine(t, filepath.Join(dir, "ran"), t.Name())
			if n == "b" {
				t.Run("c", func(t *testing.T) { appendLine(t, filepath.Join(dir, "ran"), t.Name()) })
			}
		})
	}
}

// controlFixture is TestIsolationControls inside a subprocess (or a direct
// launch).
func controlFixture(t *testing.T, mode, dir string) {
	switch mode {
	case "hang":
		spawnEscaped(t, dir)
		time.Sleep(time.Hour)
	case "leak":
		spawnEscaped(t, dir)
	case "fail":
		t.Fatal("control failure")
	case "noisy":
		block := bytes.Repeat(append(bytes.Repeat([]byte("x"), 1023), '\n'), 64)
		for range noisyBytes / len(block) {
			if _, err := os.Stdout.Write(block); err != nil {
				t.Fatal(err)
			}
		}
	case "subtests":
		recordSubtests(t, dir)
	case "guarded":
		if !Isolated(t, hangLimit) {
			return
		}
		recordSubtests(t, dir)
	case "gorace":
		if err := os.WriteFile(filepath.Join(dir, "gorace"), []byte(os.Getenv("GORACE")), 0o644); err != nil {
			t.Fatal(err)
		}
	default:
		t.Fatalf("unknown control mode %q", mode)
	}
}

// The watchdog's negative controls: a hang is killed within its bound with a
// goroutine dump, and the processes it left outside the subprocess's session
// are killed by the marker sweep; a leak after a passing run is reported and
// killed; a failure and a run that selected nothing are reported; a PASS line
// far past the report cap still reads as a pass, with the report capped; the
// subprocess's GORACE turns the race runtime's exit sleep off and keeps the
// parent's options; and the subprocess selects subtests and runs at the CPU
// setting exactly as the parent's own testing flags would.
func TestIsolationControls(t *testing.T) {
	if v, ok := os.LookupEnv(controlEnv); ok {
		mode, dir, _ := strings.Cut(v, "|")
		controlFixture(t, mode, dir)
		return
	}
	const name = "TestIsolationControls"
	settings := childSettings{cpu: runtime.GOMAXPROCS(0)}
	escaped := func(t *testing.T, dir string) (leader, bg int) {
		t.Helper()
		if b, _ := os.ReadFile(filepath.Join(dir, "ready")); string(b) != "shape ok" {
			t.Fatalf("fixture not ready or wrongly shaped: %q", b)
		}
		return readPid(t, filepath.Join(dir, "leader.pid")), readPid(t, filepath.Join(dir, "bg.pid"))
	}
	reaped := func(t *testing.T, c childRun, pids ...int) {
		t.Helper()
		for _, pid := range pids {
			if !slices.ContainsFunc(c.leftover, func(s string) bool { return strings.HasPrefix(s, strconv.Itoa(pid)+":") }) {
				t.Errorf("pid %d not among the reaped %v", pid, c.leftover)
			}
			if procLive(pid) {
				t.Errorf("pid %d alive after the reap", pid)
			}
		}
		if c.cleanupErr != nil {
			t.Errorf("cleanup: %v", c.cleanupErr)
		}
	}

	t.Run("hang", func(t *testing.T) {
		dir, limit := t.TempDir(), 500*time.Millisecond
		c := runChild(t, name, limit, settings, controlEnv+"=hang|"+dir)
		if !c.hung || c.elapsed > limit+quitGrace+2*time.Second {
			t.Fatalf("hung %v after %v\n%s", c.hung, c.elapsed, c.output)
		}
		// The processes sat outside the subprocess's session, so killing
		// that session could not have removed them: the marker sweep did.
		leader, bg := escaped(t, dir)
		reaped(t, c, leader, bg)
		if !strings.Contains(c.output, "goroutine ") || !strings.Contains(c.output, "controlFixture") {
			t.Errorf("no goroutine dump naming the fixture:\n%s", c.output)
		}
		if p := c.problems(name, limit); len(p) != 1 || !strings.HasPrefix(p[0], "HANG:TestIsolationControls|500ms\n") {
			t.Errorf("problems %q", p)
		}
	})
	t.Run("leak", func(t *testing.T) {
		dir := t.TempDir()
		c := runChild(t, name, hangLimit, settings, controlEnv+"=leak|"+dir)
		if c.hung || !c.state.Success() || !c.passed {
			t.Fatalf("hung %v state %v passed %v\n%s", c.hung, c.state, c.passed, c.output)
		}
		leader, bg := escaped(t, dir)
		reaped(t, c, leader, bg)
		if len(c.leftover) != 2 {
			t.Errorf("leftover %v", c.leftover)
		}
		if p := c.problems(name, hangLimit); len(p) != 1 || !strings.HasPrefix(p[0], "LEAK:TestIsolationControls|") {
			t.Errorf("problems %q", p)
		}
	})
	t.Run("fail", func(t *testing.T) {
		c := runChild(t, name, hangLimit, settings, controlEnv+"=fail|"+t.TempDir())
		p := c.problems(name, hangLimit)
		if c.hung || c.state.Success() || !strings.Contains(c.output, "control failure") ||
			len(p) != 1 || !strings.Contains(p[0], "failed in its subprocess") {
			t.Fatalf("hung %v state %v problems %q", c.hung, c.state, p)
		}
	})
	t.Run("ran nothing", func(t *testing.T) {
		c := runChild(t, "TestNoSuchTestExists", hangLimit, settings)
		p := c.problems("TestNoSuchTestExists", hangLimit)
		if c.hung || !c.state.Success() || len(p) != 1 || !strings.Contains(p[0], "ran no such test") {
			t.Fatalf("hung %v state %v problems %q", c.hung, c.state, p)
		}
	})
	// No allocation claim here: runChild's reap scans every process's
	// environment, a cost set by the host. TestScanOutput bounds the read.
	t.Run("noisy", func(t *testing.T) {
		c := runChild(t, name, hangLimit, settings, controlEnv+"=noisy|"+t.TempDir())
		end := c.output[max(0, len(c.output)-80):]
		if c.hung || !c.state.Success() || !c.passed || c.skipped {
			t.Fatalf("hung %v state %v passed %v skipped %v; output %d bytes ending %q", c.hung, c.state, c.passed, c.skipped, len(c.output), end)
		}
		if p := c.problems(name, hangLimit); len(p) != 0 {
			t.Errorf("%d problems, the first starting %.200q", len(p), p[0])
		}
		var rest string
		if len(c.output) > outputCap {
			rest = c.output[outputCap:]
		}
		var n int
		_, err := fmt.Sscanf(rest, "\n[truncated %d bytes]", &n)
		if err != nil || rest != fmt.Sprintf("\n[truncated %d bytes]", n) || n+outputCap < noisyBytes ||
			!strings.HasPrefix(c.output, "=== RUN   "+name+"\n") {
			t.Errorf("report not the output's first %d bytes plus a truncation note: %d bytes ending %q", outputCap, len(c.output), end)
		}
	})
	// The subprocess's GORACE is atexit_sleep_ms=0 followed by the parent's
	// options, kept verbatim: a misleading value is still prefixed, and an
	// explicit atexit_sleep_ms of the parent's comes after the prefix, where
	// the runtime's last assignment wins.
	t.Run("gorace", func(t *testing.T) {
		for _, row := range []struct {
			parent string
			unset  bool
			want   string
		}{
			{unset: true, want: "atexit_sleep_ms=0"},
			{parent: "halt_on_error=1", want: "atexit_sleep_ms=0 halt_on_error=1"},
			{parent: "strip_path_prefix=/work/atexit_sleep_ms=demo/", want: "atexit_sleep_ms=0 strip_path_prefix=/work/atexit_sleep_ms=demo/"},
			{parent: "halt_on_error=1,atexit_sleep_ms=250", want: "atexit_sleep_ms=0 halt_on_error=1,atexit_sleep_ms=250"},
			{parent: "atexit_sleep_ms=1000", want: "atexit_sleep_ms=0 atexit_sleep_ms=1000"},
		} {
			t.Setenv("GORACE", row.parent) // restored after the subtest, set or not
			if row.unset {
				os.Unsetenv("GORACE")
			}
			dir := t.TempDir()
			c := runChild(t, name, hangLimit, settings, controlEnv+"=gorace|"+dir)
			if c.hung || !c.state.Success() || !c.passed {
				t.Fatalf("parent %q: hung %v state %v passed %v\n%s", row.parent, c.hung, c.state, c.passed, c.output)
			}
			if b, err := os.ReadFile(filepath.Join(dir, "gorace")); err != nil || string(b) != row.want {
				t.Errorf("parent %q (unset %v): child GORACE %q, %v; want %q", row.parent, row.unset, b, err, row.want)
			}
		}
	})

	// Each row launches the test binary directly, twice with the same
	// flags: the body in-process (the testing package's own selection) and
	// through isolated (this launch is a real parent). Both must record the
	// row's subtests and GOMAXPROCS. Every row anchors its top level: an
	// empty or unanchored -test.run would run the whole package per launch.
	t.Run("settings", func(t *testing.T) {
		exe, err := os.Executable()
		if err != nil {
			t.Fatal(err)
		}
		abc := []string{name + "/a", name + "/b", name + "/b/c"}
		for _, row := range []struct {
			run, skip, cpu string
			ran, procs     []string
		}{
			{"^TestIsolationControls$", "", "1", abc, []string{"1"}},
			{"^TestIsolationControls$/b", "", "1", abc[1:], []string{"1"}},
			{"^TestIsolationControls$/b/c", "", "1", abc[1:], []string{"1"}},
			{"^TestIsolationControls$", "TestIsolationControls/b/c", "1", abc[:2], []string{"1"}},
			{"^TestIsolationControls$/a|^TestIsolationControls$/b/c", "", "1", abc, []string{"1"}},
			{"^TestNoSuchTestExists$/x|^TestIsolation(Controls)$/[b]", "Controls/b/c", "3", abc[1:2], []string{"3"}},
			{"^TestIsolationControls$/(a|b)$", "", "1,3", append(slices.Clone(abc), abc...), []string{"1", "3"}},
		} {
			for _, mode := range []string{"subtests", "guarded"} {
				dir := t.TempDir()
				args := []string{"-test.run=" + row.run, "-test.count=1", "-test.v=true", "-test.cpu=" + row.cpu}
				if row.skip != "" {
					args = append(args, "-test.skip="+row.skip)
				}
				ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
				cmd := exec.CommandContext(ctx, exe, args...)
				cmd.Env = append(os.Environ(), controlEnv+"="+mode+"|"+dir)
				out, err := cmd.CombinedOutput()
				cancel()
				if err != nil {
					t.Fatalf("%s %q: %v\n%s", mode, row.run, err, out)
				}
				for _, line := range strings.Split(string(out), "\n") {
					if test, ok := strings.CutPrefix(strings.TrimSpace(line), "=== RUN   "); ok {
						if top, _, _ := strings.Cut(test, "/"); top != name {
							t.Fatalf("%s %q: the launch ran %s", mode, row.run, test)
						}
					}
				}
				ran, procs := readLines(t, filepath.Join(dir, "ran")), readLines(t, filepath.Join(dir, "procs"))
				if !slices.Equal(ran, row.ran) || !slices.Equal(procs, row.procs) {
					t.Errorf("%s run=%q skip=%q cpu=%s: ran %v procs %v, want %v %v\n%s",
						mode, row.run, row.skip, row.cpu, ran, procs, row.ran, row.procs, out)
				}
			}
		}
	})
}

// A marked process the reap cannot inspect stays in its result until it is
// observed gone — never a clean result — while a process whose environment
// it may not read is not its to kill.
func TestReapMarkedUncertainty(t *testing.T) {
	// start runs `sleep 300` leading a session of its own, with entry (if
	// any) in its environment, reaped as soon as it dies.
	start := func(t *testing.T, entry string) int {
		t.Helper()
		cmd := exec.Command("sleep", "300")
		if entry != "" {
			cmd.Env = append(os.Environ(), entry)
		}
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		if err := cmd.Start(); err != nil {
			t.Fatal(err)
		}
		done := make(chan struct{})
		go func() { _ = cmd.Wait(); close(done) }()
		t.Cleanup(func() { _ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL); <-done })
		pid := cmd.Process.Pid
		// Start returns once the child is past execve's switch to the new
		// image, before its environment is set up: until then the
		// environment reads empty. The controls below fault-inject reads of
		// a process already known to carry its marker, so establish that
		// first, through the real reader.
		for end := time.Now().Add(5 * time.Second); entry != ""; time.Sleep(time.Millisecond) {
			if env, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/environ"); err == nil && hasEntry(env, []byte(entry)) {
				break
			}
			if time.Now().After(end) {
				t.Fatalf("pid %d never showed its marker", pid)
			}
		}
		return pid
	}
	marker := func(t *testing.T) string {
		return isolateEnv + "=" + t.Name() + "|" + strconv.FormatInt(time.Now().UnixNano(), 10)
	}
	inject := func(t *testing.T, environ, stat map[int]func() ([]byte, error)) {
		t.Helper()
		oldEnv, oldStat := wdReadEnviron, wdReadStat
		wdReadEnviron = func(pid int) ([]byte, error) {
			if f, ok := environ[pid]; ok {
				return f()
			}
			return oldEnv(pid)
		}
		wdReadStat = func(pid int) ([]byte, error) {
			if f, ok := stat[pid]; ok {
				return f()
			}
			return oldStat(pid)
		}
		t.Cleanup(func() { wdReadEnviron, wdReadStat = oldEnv, oldStat })
	}
	fail := func(pid int, op string, errno syscall.Errno) func() ([]byte, error) {
		return func() ([]byte, error) {
			return nil, &os.PathError{Op: "open", Path: "/proc/" + strconv.Itoa(pid) + "/" + op, Err: errno}
		}
	}
	// swallowKills makes the kill seam record, and not send, signals for pid
	// and its group, so the process outlives the reap.
	swallowKills := func(t *testing.T, pid int) *[]int {
		t.Helper()
		kills := &[]int{}
		old := wdKill
		wdKill = func(p int, sig syscall.Signal) error {
			if p == pid || p == -pid {
				*kills = append(*kills, p)
				return nil
			}
			return old(p, sig)
		}
		t.Cleanup(func() { wdKill = old })
		return kills
	}
	const bound = 100 * time.Millisecond

	// The process survives the kill (the kill seam swallows it, recording
	// the attempt), so it stays listed and uninspectable: the reap must end
	// in an error naming it, never in a clean result.
	for name, stat := range map[string]func(pid int) func() ([]byte, error){
		"stat unreadable persists": func(pid int) func() ([]byte, error) { return fail(pid, "stat", syscall.EACCES) },
		"malformed stat persists":  func(int) func() ([]byte, error) { return func() ([]byte, error) { return []byte("garbage"), nil } },
	} {
		t.Run(name, func(t *testing.T) {
			entry := marker(t)
			pid := start(t, entry)
			inject(t, nil, map[int]func() ([]byte, error){pid: stat(pid)})
			k := swallowKills(t, pid)
			seen, err := reapMarked(entry, bound)
			if err == nil || !strings.Contains(err.Error(), strconv.Itoa(pid)+" (uninspectable: ") {
				t.Fatalf("reap: %v (seen %v): an uninspectable marked process read as clean", err, seen)
			}
			if kills := *k; !slices.Equal(seen, []string{strconv.Itoa(pid) + ":?"}) || len(kills) == 0 || slices.Contains(kills, -pid) || !procLive(pid) {
				t.Fatalf("seen %v, kills %v (by pid only, never its unknown group), alive %v", seen, kills, procLive(pid))
			}
		})
	}
	t.Run("stat unreadable then exits", func(t *testing.T) {
		entry := marker(t)
		pid := start(t, entry)
		inject(t, nil, map[int]func() ([]byte, error){pid: fail(pid, "stat", syscall.EACCES)})
		seen, err := reapMarked(entry, 5*time.Second)
		if err != nil || !slices.Equal(seen, []string{strconv.Itoa(pid) + ":?"}) || procLive(pid) {
			t.Fatalf("reap: %v, seen %v, alive %v", err, seen, procLive(pid))
		}
	})
	t.Run("vanished", func(t *testing.T) {
		entry := marker(t)
		pid := start(t, entry)
		inject(t, nil, map[int]func() ([]byte, error){pid: fail(pid, "stat", syscall.ENOENT)})
		seen, err := reapMarked(entry, bound)
		if err != nil || len(seen) != 0 || !procLive(pid) {
			t.Fatalf("reap: %v, seen %v, alive %v (ENOENT reads as exited, nothing to kill)", err, seen, procLive(pid))
		}
	})
	t.Run("unrelated inaccessible", func(t *testing.T) {
		entry := marker(t)
		visible, hidden := start(t, entry), start(t, entry)
		inject(t, map[int]func() ([]byte, error){hidden: fail(hidden, "environ", syscall.EACCES)}, nil)
		seen, err := reapMarked(entry, 5*time.Second)
		if err != nil || !slices.Equal(seen, []string{strconv.Itoa(visible) + ":sleep"}) || procLive(visible) || !procLive(hidden) {
			t.Fatalf("reap: %v, seen %v, visible alive %v, hidden alive %v", err, seen, procLive(visible), procLive(hidden))
		}
	})
	// An environment it cannot read for an unexpected reason leaves the scan
	// incomplete — an error — but does not stop the reap of the processes
	// it did identify.
	t.Run("unexpected environ error", func(t *testing.T) {
		entry := marker(t)
		target, other := start(t, entry), start(t, "")
		inject(t, map[int]func() ([]byte, error){other: fail(other, "environ", syscall.EIO)}, nil)
		seen, err := reapMarked(entry, bound)
		if err == nil || !strings.HasPrefix(err.Error(), "cleanup_unverified: ") ||
			!strings.Contains(err.Error(), "scan incomplete: pid "+strconv.Itoa(other)+": environ: ") {
			t.Fatalf("reap: %v, seen %v: an unreadable environment read as clean", err, seen)
		}
		if !slices.Equal(seen, []string{strconv.Itoa(target) + ":sleep"}) || procLive(target) {
			t.Fatalf("seen %v, target alive %v: the readable marked process was not reaped", seen, procLive(target))
		}
	})
	// Once the marker has matched, losing access to the environment does not
	// release the process: it is tracked by identity until it is seen gone.
	lostAccess := func(t *testing.T, pid int) {
		t.Helper()
		reads := 0
		inject(t, map[int]func() ([]byte, error){pid: func() ([]byte, error) {
			if reads++; reads == 1 {
				return os.ReadFile("/proc/" + strconv.Itoa(pid) + "/environ")
			}
			return fail(pid, "environ", syscall.EACCES)()
		}}, nil)
	}
	t.Run("environ lost after a match, survives", func(t *testing.T) {
		entry := marker(t)
		pid := start(t, entry)
		lostAccess(t, pid)
		swallowKills(t, pid)
		seen, err := reapMarked(entry, bound)
		if err == nil || !strings.Contains(err.Error(), "still present after "+bound.String()+": "+strconv.Itoa(pid)) {
			t.Fatalf("reap: %v (seen %v): an owned process read as gone once its environment became unreadable", err, seen)
		}
		if !slices.Equal(seen, []string{strconv.Itoa(pid) + ":sleep"}) || !procLive(pid) {
			t.Fatalf("seen %v, alive %v", seen, procLive(pid))
		}
	})
	t.Run("environ lost after a match, then exits", func(t *testing.T) {
		entry := marker(t)
		pid := start(t, entry)
		lostAccess(t, pid)
		seen, err := reapMarked(entry, 5*time.Second)
		if err != nil || !slices.Equal(seen, []string{strconv.Itoa(pid) + ":sleep"}) || procLive(pid) {
			t.Fatalf("reap: %v, seen %v, alive %v", err, seen, procLive(pid))
		}
	})
	// A process inside execve reads an empty environment: a first empty scan
	// is confirmed by a second before the reap is clean.
	t.Run("environ not yet set up", func(t *testing.T) {
		entry := marker(t)
		pid := start(t, entry)
		reads := 0
		inject(t, map[int]func() ([]byte, error){pid: func() ([]byte, error) {
			if reads++; reads == 1 {
				return []byte{}, nil
			}
			return os.ReadFile("/proc/" + strconv.Itoa(pid) + "/environ")
		}}, nil)
		seen, err := reapMarked(entry, 5*time.Second)
		if err != nil || !slices.Equal(seen, []string{strconv.Itoa(pid) + ":sleep"}) || procLive(pid) {
			t.Fatalf("reap: %v, seen %v, alive %v: one empty scan read as clean", err, seen, procLive(pid))
		}
	})
	// A different start time under the same pid is another process: ours
	// exited, and the newcomer is never signalled.
	t.Run("pid reused", func(t *testing.T) {
		entry := marker(t)
		pid := start(t, entry)
		envReads, statReads := 0, 0
		inject(t, map[int]func() ([]byte, error){pid: func() ([]byte, error) {
			if envReads++; envReads == 1 {
				return os.ReadFile("/proc/" + strconv.Itoa(pid) + "/environ")
			}
			return []byte("OTHER=1\x00"), nil
		}}, map[int]func() ([]byte, error){pid: func() ([]byte, error) {
			b, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
			if statReads++; statReads == 1 || err != nil {
				return b, err
			}
			end := bytes.LastIndexByte(b, ')')
			f := strings.Fields(string(b[end+1:]))
			n, _ := strconv.ParseUint(f[19], 10, 64)
			f[19] = strconv.FormatUint(n+1, 10)
			return []byte(string(b[:end+1]) + " " + strings.Join(f, " ") + "\n"), nil
		}})
		kills := swallowKills(t, pid)
		seen, err := reapMarked(entry, 5*time.Second)
		if err != nil || !slices.Equal(seen, []string{strconv.Itoa(pid) + ":sleep"}) {
			t.Fatalf("reap: %v, seen %v", err, seen)
		}
		if !slices.Equal(*kills, []int{-pid, pid}) {
			t.Fatalf("kills %v: want only the first round's group and pid, none after the start time changed", *kills)
		}
	})
}
