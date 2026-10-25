//go:build linux

package builtin

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

// hangLimit bounds one isolated test of this package.
const hangLimit = 30 * time.Second

// echoTool is the echo adapter's tool. `run` of a file whose first line is
// @daemon leaves a setsid double-forked daemon and blocks.
const echoTool = `#!/bin/sh
verb=$1 f=$2
case "$verb" in
list) cat "$f" ;;
run)
  while read -r c; do
    case "$c" in
    @daemon)
      setsid sh -c 'sleep 300 & echo $! > "$0/daemon.pid"' "$AIT_TEST_STATE" & wait $!
      while [ ! -s "$AIT_TEST_STATE/daemon.pid" ]; do sleep 0.01; done
      echo $$ > "$AIT_TEST_STATE/tool.pid"
      exec sleep 300 ;;
    *) echo "$c pass" ;;
    esac
  done < "$f" ;;
esac
`

// newRepo is a fixture repository with the echo tool, the given files and
// runners.yaml, committed; state is a scratch directory outside it, exported
// to the builtins as AIT_TEST_STATE.
func newRepo(t *testing.T, files map[string]string, runners string) (r *fixture.Repo, state string) {
	t.Helper()
	r = fixture.New(t)
	all := map[string]string{
		registry.ConfigPath:  "contract: 1\n",
		".gitignore":         runner.StateDir + "/\n",
		runner.RunnersPath:   "contract: 1\nrunners:\n" + runners,
		"tools/echo-tool.sh": echoTool,
	}
	for k, v := range files {
		all[k] = v
	}
	for p, c := range all {
		r.Write(t, p, c)
	}
	for p := range all {
		if strings.HasSuffix(p, ".sh") {
			if err := os.Chmod(filepath.Join(r.Dir, filepath.FromSlash(p)), 0o755); err != nil {
				t.Fatal(err)
			}
		}
	}
	r.Commit(t, "1", "test", "fixture")
	state = t.TempDir()
	t.Setenv(stateEnv, state)
	return r, state
}

// echoEntry is a runners.yaml entry for a builtin echo runner bound to glob.
func echoEntry(name, adapter, glob string) string {
	return "  - name: " + name + "\n    builtin: " + adapter + "\n    command: tools/echo-tool.sh\n    bind: ['" + glob + "']\n    timeout_s: 30\n    batch_timeout_s: 30\n"
}

func alive(pid int) bool {
	b, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		return false
	}
	s := string(b)
	f := strings.Fields(s[strings.LastIndexByte(s, ')')+1:])
	return len(f) > 0 && f[0] != "Z" && f[0] != "X"
}

func waitPid(t *testing.T, path string) int {
	t.Helper()
	for end := time.Now().Add(10 * time.Second); time.Now().Before(end); time.Sleep(10 * time.Millisecond) {
		if b, err := os.ReadFile(path); err == nil && strings.HasSuffix(string(b), "\n") {
			pid, err := strconv.Atoi(strings.TrimSpace(string(b)))
			if err != nil {
				t.Fatal(err)
			}
			return pid
		}
	}
	t.Fatalf("%s never appeared", path)
	return 0
}

func waitDead(pid int, limit time.Duration) bool {
	for end := time.Now().Add(limit); time.Now().Before(end); time.Sleep(10 * time.Millisecond) {
		if !alive(pid) {
			return true
		}
	}
	return !alive(pid)
}

func run(t *testing.T, r *fixture.Repo, id string) *runner.RunReport {
	t.Helper()
	rep, err := runner.Run(context.Background(), r.Dir, runner.Options{All: true, RunID: id})
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	return rep
}

func record(t *testing.T, rep *runner.RunReport, name string) runner.Record {
	t.Helper()
	for _, rec := range rep.Invocations {
		if rec.Runner == name {
			return rec
		}
	}
	t.Fatalf("no invocation of %s", name)
	return runner.Record{}
}

func result(t *testing.T, rep *runner.RunReport, id string) runner.Result {
	t.Helper()
	for _, res := range rep.Results {
		if !res.Child && res.ID.String() == id {
			return res
		}
	}
	t.Fatalf("no result for %s", id)
	return runner.Result{}
}

// The scaffold end to end through runner.Run: describe, native discovery
// through Supervise, run with start and case rows, the engine reconciling the
// cases.
func TestScaffoldEndToEnd(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	r, _ := newRepo(t, map[string]string{"tests/one.echo": "a\nb\n"}, echoEntry("e", "echo", "tests/*.echo"))
	rep := run(t, r, "e2e")
	res := result(t, rep, "tests/one.echo")
	rec := record(t, rep, "e")
	if res.Status != runner.StatusPass || res.Cases == nil || res.Cases.Expected != 2 || res.Cases.Passed != 2 || rec.Cause != "" || rep.Exit() != 0 {
		t.Fatalf("result %+v cases %+v record %+v exit %d", res, res.Cases, rec, rep.Exit())
	}
	if rec.Containment != procsup.Supervisor || rec.Accounting != runner.AccountingCases {
		t.Fatalf("record %+v", rec)
	}
}

// A builtin SIGKILLed mid-unit while its tool holds a setsid descendant:
// nothing is left once Run returns — the tool's supervisor sees its parent
// die, and the invocation's supervisor kills whatever reparents to it.
func TestBuiltinCrashLeavesNothing(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	r, st := newRepo(t, map[string]string{"tests/crash.echo": "@daemon\n"}, echoEntry("a", "echo", "tests/*.echo"))
	done := make(chan *runner.RunReport, 1)
	go func() { done <- run(t, r, "crash") }()
	builtinPid := waitPid(t, filepath.Join(st, "a.builtin.pid"))
	daemon := waitPid(t, filepath.Join(st, "daemon.pid"))
	tool := waitPid(t, filepath.Join(st, "tool.pid"))
	if err := syscall.Kill(builtinPid, syscall.SIGKILL); err != nil {
		t.Fatal(err)
	}
	rep := <-done
	if alive(daemon) || alive(tool) || alive(builtinPid) {
		t.Fatalf("left behind: daemon %v tool %v builtin %v", alive(daemon), alive(tool), alive(builtinPid))
	}
	if rec := record(t, rep, "a"); rec.Cause == "" {
		t.Fatalf("the crashed invocation has no cause: %+v", rec)
	}
}

// bRunner is a script runner B: it starts a helper of its own, waits until
// the test says invocation A has been cleaned up, and passes only if its
// helper is still alive.
const bRunner = `#!/usr/bin/env bash
case "$1" in
describe) echo "unit: file" ;;
list) printf 'tests/b.sh\tfile\tb\n' ;;
run)
  R=$(sed -n 's/^  "results": "\(.*\)",$/\1/p' "$3")
  sleep 300 & helper=$!
  echo $helper > "$AIT_TEST_STATE/b.helper.pid"
  for i in $(seq 1 1500); do [ -e "$AIT_TEST_STATE/b.go" ] && break; sleep 0.01; done
  if kill -0 $helper 2>/dev/null; then st=pass; else st=fail; fi
  kill $helper
  printf '{"id":"tests/b.sh","status":"%s","duration_ms":1}\n' "$st" >> "$R"
  [ "$st" = pass ] ;;
*) exit 64 ;;
esac
`

// The real-process overlap: A and B run in parallel; A's builtin is
// SIGKILLed while its tool holds a setsid double-forked daemon. A's daemon
// is killed and A carries a cause; every one of B's processes survives until
// B's normal exit, and B passes with no cause. On every Linux host.
func TestOverlapIsolatesInvocations(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	plan.parallel.Store(true)
	t.Cleanup(func() { plan.parallel.Store(false) })
	if !runner.Overlappable() {
		t.Fatal("Linux with a supervisor must be overlappable")
	}
	r, st := newRepo(t, map[string]string{"tests/crash.echo": "@daemon\n", "tests/b.sh": "", runner.RunnersDir + "/b.sh": bRunner},
		echoEntry("a", "echo", "tests/*.echo")+"  - name: b\n    bind: ['tests/b.sh']\n    timeout_s: 30\n")
	done := make(chan *runner.RunReport, 1)
	go func() { done <- run(t, r, "overlap") }()
	builtinPid := waitPid(t, filepath.Join(st, "a.builtin.pid"))
	daemon := waitPid(t, filepath.Join(st, "daemon.pid"))
	helper := waitPid(t, filepath.Join(st, "b.helper.pid"))
	if err := syscall.Kill(builtinPid, syscall.SIGKILL); err != nil {
		t.Fatal(err)
	}
	if !waitDead(daemon, 10*time.Second) {
		t.Fatal("A's daemon survived A's cleanup")
	}
	if !alive(helper) {
		t.Fatal("A's cleanup killed B's helper")
	}
	if err := os.WriteFile(filepath.Join(st, "b.go"), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	rep := <-done
	if a := record(t, rep, "a"); a.Cause == "" {
		t.Fatalf("A: %+v", a)
	}
	b := record(t, rep, "b")
	if b.Cause != "" || result(t, rep, "tests/b.sh").Status != runner.StatusPass || rep.ParallelRefused != "" {
		t.Fatalf("B: %+v %+v parallel_refused %q", b, result(t, rep, "tests/b.sh"), rep.ParallelRefused)
	}
}

// Where containment is unavailable a production adapter refuses before
// doing anything (CONTAINMENT_UNAVAILABLE, exit 3); a test-only one runs.
func TestContainmentUnavailableRefusesProductionAdapters(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	defer procsup.SetUnavailableForTesting()()
	var out, errb bytes.Buffer
	if code := Main([]string{"prodecho", "describe"}, &out, &errb); code != 3 || errb.String() != "CONTAINMENT_UNAVAILABLE:linux\n" || out.Len() != 0 {
		t.Fatalf("production adapter: code %d stdout %q stderr %q", code, out.String(), errb.String())
	}
	out.Reset()
	errb.Reset()
	if code := Main([]string{"echo", "describe"}, &out, &errb); code != 0 || !strings.Contains(out.String(), "accounting: cases") {
		t.Fatalf("test-only adapter: code %d stdout %q stderr %q", code, out.String(), errb.String())
	}
}

// Through the engine: a production builtin in a process without
// containment makes Load fail with the refusal, before any unit runs.
func TestContainmentUnavailableThroughTheEngine(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	r, _ := newRepo(t, map[string]string{"tests/one.echo": "a\n"}, echoEntry("p", "prodecho", "tests/*.echo"))
	t.Setenv(unavailableEnv, "1") // reaches the builtin process, not this one
	_, err := runner.Run(context.Background(), r.Dir, runner.Options{All: true, RunID: "unavailable"})
	if err == nil || !strings.Contains(err.Error(), "CONTAINMENT_UNAVAILABLE:linux") {
		t.Fatalf("Run: %v", err)
	}
}

// Usage and an unknown builtin are 64.
func TestMainUsage(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	for _, tc := range []struct {
		args []string
		want string
	}{
		{nil, "USAGE:" + Usage + "\n"},
		{[]string{"echo"}, "USAGE:" + Usage + "\n"},
		{[]string{"echo", "run"}, "USAGE:" + Usage + "\n"},
		{[]string{"echo", "describe", "x"}, "USAGE:" + Usage + "\n"},
		{[]string{"nope", "describe"}, "UNKNOWN_BUILTIN:nope\n"},
	} {
		var out, errb bytes.Buffer
		if code := Main(tc.args, &out, &errb); code != 64 || errb.String() != tc.want {
			t.Errorf("%v: code %d stderr %q", tc.args, code, errb.String())
		}
	}
}

// The argv splitter refuses every shell metacharacter and quoting.
func TestSplitCommand(t *testing.T) {
	got, err := SplitCommand("  go  test -v\t./... ")
	if err != nil || strings.Join(got, "|") != "go|test|-v|./..." {
		t.Fatalf("%q %v", got, err)
	}
	for _, c := range []string{"$", "`", ";", "|", "&", "<", ">", "\n", "\r", "'", "\"", "\\"} {
		if _, err := SplitCommand("tool a" + c + "b"); err == nil {
			t.Errorf("%q accepted", c)
		}
	}
	if _, err := SplitCommand(" \t "); err == nil {
		t.Error("an empty command was accepted")
	}
}

// ReadManifest is strict.
func TestReadManifestStrict(t *testing.T) {
	d := t.TempDir()
	for name, body := range map[string]string{
		"unknown":  `{"contract":1,"bogus":1}`,
		"trailing": `{"contract":1} {}`,
		"contract": `{"contract":99}`,
	} {
		p := filepath.Join(d, name)
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
		if _, err := ReadManifest(p); err == nil {
			t.Errorf("%s accepted", name)
		}
	}
	if _, err := ReadManifest(filepath.Join(d, "missing")); !errorsAs[*os.PathError](err) {
		t.Errorf("missing: %v", err)
	}
}
