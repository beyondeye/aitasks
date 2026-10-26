//go:build linux

package builtin

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

// The bash-file builtin's real-tool tests (G10): GNU bash >= 4.4 on linux,
// the supported configuration. Without it a test is skipped (the adapter is
// pending there) unless AIT_TESTMAP_REQUIRE_REAL_TOOLS=1, where the skip is
// a failure.
//
// Test-only environment the fixture scripts read:
//
//	AIT_TEST_STATE      scratch directory outside the fixture (newRepo)
//	AIT_TEST_ENGINE     this test binary: `$AIT_TEST_ENGINE __nested_engine check|run`
//	AIT_TEST_OTHER      a second fixture repository
//	AIT_TEST_REAL_GIT   the real git, for the git shim
//	AIT_TEST_SHIM_MODE  the git shim's mode for a runner's own ls-files: nest | warn
//	AIT_TEST_SHIM_NEST  the repository the shim's nested check runs in

// bashHangLimit bounds one isolated bash-file test. These tests chain two or
// three engine loads and runs, each starting supervised describe / list / run
// processes of this (possibly race-instrumented) binary: under -race on a
// loaded host TestBashFileInventory measured 28.3 s against the package's 30 s
// hangLimit. A hang still fails, at this bound.
const bashHangLimit = 120 * time.Second

// nestedEngineArg makes this test binary a minimal engine: `<test binary>
// __nested_engine check|run` loads (check) or runs every unit (run) of the
// repository in its working directory. TestMain dispatches it.
const nestedEngineArg = "__nested_engine"

// nestedEngine prints the refusal line and VIA:<detector>, or
// NESTED_OK:<exit>, on stderr and exits as the engine would.
func nestedEngine(verb string) int {
	root, err := os.Getwd()
	if err != nil {
		fmt.Fprintln(os.Stderr, "NESTED_ERROR:"+err.Error())
		return 3
	}
	code := 0
	switch verb {
	case "check":
		_, err = runner.Load(context.Background(), root)
	case "run":
		var rep *runner.RunReport
		rep, err = runner.Run(context.Background(), root, runner.Options{All: true, RunID: "nested-" + strconv.Itoa(os.Getpid())})
		if err == nil {
			code = rep.Exit()
		}
	default:
		return 64
	}
	var re *runner.RecursionError
	switch {
	case errors.As(err, &re):
		line, _ := re.Line()
		fmt.Fprintln(os.Stderr, line)
		fmt.Fprintln(os.Stderr, "VIA:"+re.Via)
		return re.ExitCode()
	case err != nil:
		fmt.Fprintln(os.Stderr, "NESTED_ERROR:"+oneLine(err.Error()))
		return 3
	}
	fmt.Fprintf(os.Stderr, "NESTED_OK:%d\n", code)
	return code
}

// requireBash skips (or, with real tools required, fails) unless bash is GNU
// bash >= 4.4 and setsid is on PATH.
func requireBash(t *testing.T) {
	t.Helper()
	miss := func(why string) {
		if os.Getenv("AIT_TESTMAP_REQUIRE_REAL_TOOLS") == "1" {
			t.Fatal("bash-file real-tool test: " + why)
		}
		t.Skip("bash-file pending here: " + why)
	}
	if _, err := exec.LookPath("setsid"); err != nil {
		miss("no setsid")
	}
	out, err := exec.Command("bash", "-c", `echo "${BASH_VERSINFO[0]} ${BASH_VERSINFO[1]}"; bash --version | head -n1`).Output()
	if err != nil {
		miss("no bash: " + err.Error())
	}
	lines := strings.Split(strings.TrimSpace(string(out)), "\n")
	var major, minor int
	if len(lines) < 2 || !strings.HasPrefix(lines[1], "GNU bash") {
		miss(fmt.Sprintf("not GNU bash: %q", out))
	}
	if _, err := fmt.Sscan(lines[0], &major, &minor); err != nil || major < 4 || (major == 4 && minor < 4) {
		miss(fmt.Sprintf("bash %q is older than 4.4", lines[0]))
	}
}

// bashEntry is a runners.yaml entry for a bash-file runner; bind "" leaves
// the adapter's default. extra lines are appended verbatim.
func bashEntry(name, bind string, extra ...string) string {
	s := "  - name: " + name + "\n    builtin: bash-file\n"
	if !slices.ContainsFunc(extra, func(x string) bool { return strings.HasPrefix(x, "timeout_s:") }) {
		s += "    timeout_s: 30\n"
	}
	if bind != "" {
		s += "    bind: ['" + bind + "']\n"
	}
	for _, x := range extra {
		s += "    " + x + "\n"
	}
	return s
}

// bashRepo is newRepo with bash-file runners, and requires bash.
func bashRepo(t *testing.T, files map[string]string, runners string) (*fixture.Repo, string) {
	t.Helper()
	requireBash(t)
	return newRepo(t, files, runners)
}

// unitLog is the content of a unit's stdout or stderr log: its invocation's
// report directory, at the unit's manifest position.
func unitLog(t *testing.T, rep *runner.RunReport, id, stream string) string {
	t.Helper()
	res := result(t, rep, id)
	n := 0
	for _, r := range rep.Results {
		if r.Invocation != res.Invocation || r.Child {
			continue
		}
		if r.ID.String() == id {
			break
		}
		n++
	}
	for _, rec := range rep.Invocations {
		if rec.Invocation == res.Invocation {
			b, err := os.ReadFile(filepath.Join(rec.ReportDir, fmt.Sprintf("unit-%04d.%s", n, stream)))
			if err != nil {
				t.Fatalf("%s %s log: %v", id, stream, err)
			}
			return string(b)
		}
	}
	t.Fatalf("no invocation %d", res.Invocation)
	return ""
}

func status(t *testing.T, rep *runner.RunReport, id, want, msgPrefix string) {
	t.Helper()
	r := result(t, rep, id)
	if r.Status != want || !strings.HasPrefix(r.Message, msgPrefix) {
		t.Errorf("%s: status %q message %q, want %q %q…", id, r.Status, r.Message, want, msgPrefix)
	}
}

func readState(t *testing.T, st, name string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(st, name))
	if err != nil {
		t.Fatalf("state %s: %v", name, err)
	}
	return strings.TrimSpace(string(b))
}

// describe is a valid inventory / unit / per_unit document whose comments
// carry the inventory rule and the support claim.
func TestBashFileDescribe(t *testing.T) {
	b, err := bashFileDescribe(nil)
	if err != nil {
		t.Fatal(err)
	}
	d, err := runner.ParseDescribe(b)
	if err != nil {
		t.Fatal(err)
	}
	if err := d.Validate(); err != nil {
		t.Fatal(err)
	}
	if d.Unit != "file" || d.Accounting != runner.AccountingUnit || d.Discovery != runner.DiscoveryInventory || d.Timeouts != runner.TimeoutsPerUnit || !d.Batch {
		t.Fatalf("describe %+v", d)
	}
	for _, s := range []string{"git-visible regular file", "default **/test_*.sh", "./<cwd-relative path>", "GNU bash >= 4.4 on linux", "darwin and bash 3.2 are pending", "unit-<n>.stdout"} {
		if !strings.Contains(string(b), s) {
			t.Errorf("describe docs do not state %q", s)
		}
	}
}

// The inventory: git-visible regular files matching the bind, under the
// cwd; ids root-relative, lowerings cwd-relative.
func TestBashFileInventory(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, st := bashRepo(t, map[string]string{
		".gitignore":          runner.StateDir + "/\ntests/test_ign.sh\n",
		"tests/test_a.sh":     "exit 0\n",
		"tests/test_gone.sh":  "exit 0\n",
		"tests/helper.sh":     "exit 0\n",
		"sub/tests/test_s.sh": "pwd -P > \"$AIT_TEST_STATE/s.pwd\"\n",
	}, bashEntry("sub", "sub/tests/test_*.sh", "cwd: sub")+bashEntry("root", ""))
	r.Write(t, "tests/test_u.sh", "exit 0\n")   // untracked, not ignored
	r.Write(t, "tests/test_ign.sh", "exit 1\n") // ignored
	r.Remove(t, "tests/test_gone.sh")           // tracked, deleted
	if err := os.Symlink("test_a.sh", filepath.Join(r.Dir, "tests", "test_link.sh")); err != nil {
		t.Fatal(err)
	}
	repo, err := runner.Load(context.Background(), r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	var listed []string
	for _, row := range repo.Runner("root").Listed {
		listed = append(listed, row.Unit.ID.String()+"="+row.Unit.Lowering)
	}
	if want := []string{"sub/tests/test_s.sh=sub/tests/test_s.sh", "tests/test_a.sh=tests/test_a.sh", "tests/test_u.sh=tests/test_u.sh"}; !slices.Equal(listed, want) {
		t.Fatalf("root lists %v, want %v", listed, want)
	}
	units := map[string]string{}
	for _, u := range repo.Units {
		units[u.ID.String()] = u.Runner + ":" + u.Lowering
	}
	if units["sub/tests/test_s.sh"] != "sub:tests/test_s.sh" || len(units) != 3 {
		t.Fatalf("units %v", units)
	}
	rep := run(t, r, "inventory")
	status(t, rep, "sub/tests/test_s.sh", runner.StatusPass, "")
	if got, want := readState(t, st, "s.pwd"), filepath.Join(r.Dir, "sub"); got != want {
		if real, _ := filepath.EvalSymlinks(want); got != real {
			t.Fatalf("cwd %q, want %q", got, want)
		}
	}
}

// Exit 0 passes, a non-zero exit or a signal fails; the run is contained,
// unit-accounted, and every unit has its logs.
func TestBashFilePassFail(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := bashRepo(t, map[string]string{
		"tests/test_fail.sh": "exit 3\n",
		"tests/test_pass.sh": "echo hello-out\necho hello-err >&2\n",
		"tests/test_sig.sh":  "kill -USR1 $$\n",
	}, bashEntry("b", ""))
	rep := run(t, r, "passfail")
	status(t, rep, "tests/test_pass.sh", runner.StatusPass, "")
	status(t, rep, "tests/test_fail.sh", runner.StatusFail, "exit 3")
	status(t, rep, "tests/test_sig.sh", runner.StatusFail, "signal ")
	rec := record(t, rep, "b")
	if rec.Cause != "" || rec.ExitCode != 1 || rec.Containment != procsup.Supervisor || rec.Accounting != runner.AccountingUnit || rec.Discovery != runner.DiscoveryInventory || rec.UnitsStarted != 3 {
		t.Fatalf("record %+v", rec)
	}
	if out, errs := unitLog(t, rep, "tests/test_pass.sh", "stdout"), unitLog(t, rep, "tests/test_pass.sh", "stderr"); out != "hello-out\n" || errs != "hello-err\n" {
		t.Fatalf("logs %q %q", out, errs)
	}
}

// A unit over timeout_s is `timeout`; its background child is gone when the
// run returns, and the next unit of the invocation still runs.
func TestBashFileTimeoutKillsBackgroundChild(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, st := bashRepo(t, map[string]string{
		"tests/test_1_slow.sh":  "sleep 300 &\necho $! > \"$AIT_TEST_STATE/bg.pid\"\nwait $!\n",
		"tests/test_2_after.sh": "echo ran > \"$AIT_TEST_STATE/after\"\n",
	}, bashEntry("b", "", "timeout_s: 1"))
	rep := run(t, r, "timeout")
	status(t, rep, "tests/test_1_slow.sh", runner.StatusTimeout, "timeout after 1s")
	status(t, rep, "tests/test_2_after.sh", runner.StatusPass, "")
	bg, err := strconv.Atoi(readState(t, st, "bg.pid"))
	if err != nil {
		t.Fatal(err)
	}
	if alive(bg) {
		t.Fatalf("the timed-out unit's background child %d survived", bg)
	}
	if rec := record(t, rep, "b"); rec.Cause != "" || !result(t, rep, "tests/test_1_slow.sh").Started {
		t.Fatalf("record %+v", rec)
	}
}

// A unit that leaves a child in its own process group, and one that leaves a
// setsid daemon, both pass, and both leftovers are gone before the next unit
// of the same invocation starts: cleanup after every unit.
func TestBashFileOwnProcessGroupAndSetsid(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, st := bashRepo(t, map[string]string{
		"tests/test_1_pgrp.sh": `set -m
sleep 300 &
echo $! > "$AIT_TEST_STATE/pg.pid"
read -r _ _ _ _ pgid _ < /proc/$!/stat
read -r _ _ _ _ mine _ < /proc/$$/stat
[ "$pgid" = "$!" ] && [ "$pgid" != "$mine" ]
`,
		"tests/test_2_setsid.sh": `setsid sh -c 'echo $$ > "$AIT_TEST_STATE/sid.tmp"; mv "$AIT_TEST_STATE/sid.tmp" "$AIT_TEST_STATE/sid.pid"; exec sleep 300' &
for i in $(seq 1 200); do [ -s "$AIT_TEST_STATE/sid.pid" ] && break; sleep 0.01; done
p=$(cat "$AIT_TEST_STATE/sid.pid")
read -r _ _ _ _ _ sid _ < /proc/$p/stat
read -r _ _ _ _ _ mine _ < /proc/$$/stat
[ "$sid" = "$p" ] && [ "$sid" != "$mine" ]
`,
		"tests/test_3_check.sh": `for f in pg sid; do
  p=$(cat "$AIT_TEST_STATE/$f.pid")
  if kill -0 "$p" 2>/dev/null; then echo "$f $p alive"; exit 1; fi
done
`,
	}, bashEntry("b", ""))
	rep := run(t, r, "groups")
	for _, id := range []string{"tests/test_1_pgrp.sh", "tests/test_2_setsid.sh", "tests/test_3_check.sh"} {
		status(t, rep, id, runner.StatusPass, "")
	}
	if rec := record(t, rep, "b"); rec.UnitsExpected != 3 {
		t.Fatalf("the three units must share one invocation: %+v", rec)
	}
	for _, f := range []string{"pg.pid", "sid.pid"} {
		p, err := strconv.Atoi(readState(t, st, f))
		if err != nil {
			t.Fatal(err)
		}
		if alive(p) {
			t.Fatalf("%s %d survived", f, p)
		}
	}
}

// Strict-mode failures are failures; a strict-mode script that succeeds
// passes.
func TestBashFileStrictMode(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := bashRepo(t, map[string]string{
		"tests/test_pipefail.sh": "set -euo pipefail\nfalse | true\nexit 0\n",
		"tests/test_unset.sh":    "set -euo pipefail\necho \"$AIT_TEST_NEVER_SET_X\"\nexit 0\n",
		"tests/test_ok.sh":       "set -euo pipefail\nx=$(printf 'a\\nb\\n' | sort | head -n1)\n[ \"$x\" = a ]\n",
	}, bashEntry("b", ""))
	rep := run(t, r, "strict")
	status(t, rep, "tests/test_pipefail.sh", runner.StatusFail, "exit ")
	status(t, rep, "tests/test_unset.sh", runner.StatusFail, "exit ")
	status(t, rep, "tests/test_ok.sh", runner.StatusPass, "")
}

// Ownership through bind: (first matching bind wins between two bash-file
// runners) and testmap:batch no making a unit a singleton invocation.
func TestBashFileBatchNoAndBindOwnership(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := bashRepo(t, map[string]string{
		"tests/slow/test_x.sh": "exit 0\n",
		"tests/test_y.sh":      "exit 0\n",
		"tests/test_b1.sh":     "# testmap:batch no\nexit 0\n",
		"tests/test_b2.sh":     "exit 0\n",
	}, bashEntry("slow", "tests/slow/**/test_*.sh")+bashEntry("all", "**/test_*.sh"))
	rep := run(t, r, "batch")
	owner := map[string]string{}
	size := map[int]int{}
	inv := map[string]int{}
	for _, rec := range rep.Invocations {
		size[rec.Invocation] = rec.UnitsExpected
	}
	for _, res := range rep.Results {
		inv[res.ID.String()] = res.Invocation
		for _, rec := range rep.Invocations {
			if rec.Invocation == res.Invocation {
				owner[res.ID.String()] = rec.Runner
			}
		}
		if res.Status != runner.StatusPass {
			t.Errorf("%s: %s %s", res.ID, res.Status, res.Message)
		}
	}
	if owner["tests/slow/test_x.sh"] != "slow" || owner["tests/test_y.sh"] != "all" || owner["tests/test_b1.sh"] != "all" {
		t.Fatalf("owners %v", owner)
	}
	if size[inv["tests/test_b1.sh"]] != 1 || inv["tests/test_y.sh"] != inv["tests/test_b2.sh"] || size[inv["tests/test_y.sh"]] != 2 {
		t.Fatalf("invocations %v sizes %v", inv, size)
	}
}

// The execution recursion test: a script that runs the engine on its own
// repository is refused through the inherited marker (VIA:marker — the
// ancestry backstop would refuse too, so the detector is what proves the
// marker reached the script); the same nested run on another repository
// succeeds.
func TestBashFileRecursionThroughExecution(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	other, _ := bashRepo(t, map[string]string{"tests/test_ok.sh": "exit 0\n"}, bashEntry("o", ""))
	r, _ := bashRepo(t, map[string]string{
		"tests/test_nest_self.sh":  "cd \"$AIT_TESTMAP_ROOT\" && exec \"$AIT_TEST_ENGINE\" " + nestedEngineArg + " run\n",
		"tests/test_nest_other.sh": "cd \"$AIT_TEST_OTHER\" && exec \"$AIT_TEST_ENGINE\" " + nestedEngineArg + " run\n",
	}, bashEntry("b", ""))
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("AIT_TEST_ENGINE", exe)
	t.Setenv("AIT_TEST_OTHER", other.Dir)
	rep := run(t, r, "nest")
	status(t, rep, "tests/test_nest_self.sh", runner.StatusFail, "exit 3")
	self := unitLog(t, rep, "tests/test_nest_self.sh", "stderr")
	if !strings.Contains(self, "RUN_ERROR:recursion|") || !slices.Contains(strings.Split(self, "\n"), "VIA:marker") {
		t.Fatalf("self-nested run: %q", self)
	}
	status(t, rep, "tests/test_nest_other.sh", runner.StatusPass, "")
	if o := unitLog(t, rep, "tests/test_nest_other.sh", "stderr"); !strings.Contains(o, "NESTED_OK:0") {
		t.Fatalf("nested run on another repository: %q", o)
	}
}

// gitShim is a git wrapper for a runner's own `git ls-files`: in mode nest it
// first runs a nested check in $AIT_TEST_SHIM_NEST (logged to
// discovery.err, a failure forwarded as git's), in mode warn it prints a
// warning and lets git exit 0. Every other git call — the engine's own
// `git -C …`, a process without AIT_TESTMAP_RUNNER — passes straight
// through.
const gitShim = `#!/bin/sh
if [ -n "$AIT_TESTMAP_RUNNER" ] && [ "$1" = ls-files ]; then
  case "$AIT_TEST_SHIM_MODE" in
  nest)
    (cd "$AIT_TEST_SHIM_NEST" && AIT_TEST_SHIM_MODE= exec "$AIT_TEST_ENGINE" __nested_engine check) 2>"$AIT_TEST_STATE/discovery.err"
    rc=$?
    if [ "$rc" -ne 0 ]; then cat "$AIT_TEST_STATE/discovery.err" >&2; exit "$rc"; fi ;;
  warn) echo "warning: synthetic" >&2 ;;
  esac
fi
exec "$AIT_TEST_REAL_GIT" "$@"
`

// shimGit puts gitShim first on PATH in the given mode.
func shimGit(t *testing.T, mode string) {
	t.Helper()
	real, err := exec.LookPath("git")
	if err != nil {
		t.Fatal(err)
	}
	d := t.TempDir()
	if err := os.WriteFile(filepath.Join(d, "git"), []byte(gitShim), 0o755); err != nil {
		t.Fatal(err)
	}
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("AIT_TEST_REAL_GIT", real)
	t.Setenv("AIT_TEST_ENGINE", exe)
	t.Setenv("AIT_TEST_SHIM_MODE", mode)
	t.Setenv("PATH", d+string(os.PathListSeparator)+os.Getenv("PATH"))
}

// The discovery recursion test: the inventory step's nested check of its own
// repository is refused through the marker gitx.Env() carries
// (VIA:marker), and the invocation — here Load — reports it; the same
// nested check of another repository succeeds.
func TestBashFileRecursionThroughDiscovery(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	other, _ := bashRepo(t, map[string]string{"tests/test_ok.sh": "exit 0\n"}, bashEntry("o", ""))
	r, st := bashRepo(t, map[string]string{"tests/test_a.sh": "exit 0\n"}, bashEntry("b", ""))
	shimGit(t, "nest")

	t.Setenv("AIT_TEST_SHIM_NEST", r.Dir)
	_, err := runner.Load(context.Background(), r.Dir)
	if err == nil || !strings.Contains(err.Error(), "RUNNER_PROTOCOL:b|list|") || !strings.Contains(err.Error(), "RUN_ERROR:recursion") {
		t.Fatalf("self-nested discovery: %v", err)
	}
	if log := readState(t, st, "discovery.err"); !slices.Contains(strings.Split(log, "\n"), "VIA:marker") {
		t.Fatalf("self-nested discovery detector: %q", log)
	}

	t.Setenv("AIT_TEST_SHIM_NEST", other.Dir)
	if _, err := runner.Load(context.Background(), r.Dir); err != nil {
		t.Fatalf("discovery nesting another repository: %v", err)
	}
	if log := readState(t, st, "discovery.err"); !strings.Contains(log, "NESTED_OK:0") {
		t.Fatalf("nested check of another repository: %q", log)
	}
}

// command: replaces the interpreter (split, no shell); an unsplittable one
// is a usage error the engine records as a mechanism failure.
func TestBashFileCommandOverride(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := bashRepo(t, map[string]string{
		"tests/e/test_e.sh":   "false\nexit 0\n",
		"tests/d/test_d.sh":   "false\nexit 0\n",
		"tests/bad/test_x.sh": "exit 0\n",
	}, bashEntry("e", "tests/e/**", "command: bash --norc -e")+bashEntry("d", "tests/d/**")+bashEntry("bad", "tests/bad/**", "command: bash;x"))
	rep := run(t, r, "command")
	status(t, rep, "tests/e/test_e.sh", runner.StatusFail, "exit 1")
	status(t, rep, "tests/d/test_d.sh", runner.StatusPass, "")
	if rec := record(t, rep, "bad"); rec.Cause != runner.CauseMechanism || rec.CauseDetail != "runner_exit:64" || rec.UnitsStarted != 0 {
		t.Fatalf("bad command: %+v", rec)
	}
}

// Where containment is unavailable bash-file refuses before doing anything.
func TestBashFileContainmentUnavailable(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	defer procsup.SetUnavailableForTesting()()
	for _, verb := range []string{"describe", "list"} {
		var out, errb bytes.Buffer
		if code := Main([]string{bashFileName, verb}, &out, &errb); code != 3 || errb.String() != "CONTAINMENT_UNAVAILABLE:linux\n" || out.Len() != 0 {
			t.Fatalf("%s: code %d stdout %q stderr %q", verb, code, out.String(), errb.String())
		}
	}
}

// The aitasks test shape: `bash tests/test_x.sh` from the root, the script
// locating its helpers through its own path and sourcing them.
func TestBashFileAitasksShape(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := bashRepo(t, map[string]string{
		"tests/lib/asserts.sh":       "assert_eq() { [ \"$1\" = \"$2\" ] || { echo \"FAIL: $1 != $2\"; exit 1; }; }\n",
		"tests/lib/test_scaffold.sh": "exit 1\n", // a helper the aitasks bind must exclude
		"tests/test_shape.sh": `#!/usr/bin/env bash
# Run: bash tests/test_shape.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
. "$SCRIPT_DIR/lib/asserts.sh"
assert_eq "$PROJECT_DIR" "$(pwd -P)"
assert_eq "$0" ./tests/test_shape.sh
echo "PASS: 2 passed, 0 failed"
`,
	}, bashEntry("t", "tests/test_*.sh"))
	rep := run(t, r, "shape")
	status(t, rep, "tests/test_shape.sh", runner.StatusPass, "")
	if len(rep.Results) != 1 {
		t.Fatalf("results %+v (the bind must leave tests/lib out)", rep.Results)
	}
}

// An option-shaped path is still a script operand: the unit runs its body
// and is judged by its exit, never by the interpreter's own option.
func TestBashFileOptionShapedPaths(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, st := bashRepo(t, map[string]string{
		"--version":        "echo ran > \"$AIT_TEST_STATE/version.ran\"\nexit 7\n",
		"-tests/test_a.sh": "echo ran > \"$AIT_TEST_STATE/dash.ran\"\nexit 5\n",
	}, bashEntry("opt", "--version")+bashEntry("dash", ""))
	rep := run(t, r, "options")
	status(t, rep, "--version", runner.StatusFail, "exit 7")
	status(t, rep, "-tests/test_a.sh", runner.StatusFail, "exit 5")
	for _, f := range []string{"version.ran", "dash.ran"} {
		if readState(t, st, f) != "ran" {
			t.Errorf("%s: the script did not run", f)
		}
	}
}

// An inventory that exits 0 with a warning on stderr may be incomplete and
// fails the listing. Both variants are scoped to the adapter: Load's own
// later git calls (annotations, bindings) reject a repository-wide warning
// by themselves, so Load is not the oracle for a real-git warning.
func TestBashFileInventoryWarningFailsClosed(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	t.Run("real git, in-process", func(t *testing.T) {
		if os.Geteuid() == 0 {
			t.Skip("euid 0 reads an unreadable directory: no warning to provoke")
		}
		r, _ := bashRepo(t, map[string]string{"tests/test_a.sh": "exit 0\n"}, bashEntry("b", ""))
		locked := filepath.Join(r.Dir, "tests", "locked")
		if err := os.MkdirAll(locked, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(locked, "test_hidden.sh"), nil, 0o644); err != nil {
			t.Fatal(err)
		}
		if err := os.Chmod(locked, 0); err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { os.Chmod(locked, 0o755) })
		var buf bytes.Buffer
		err := bashFileList(context.Background(), &Env{Root: r.Dir, Runner: "b"}, &buf)
		if err == nil || !strings.Contains(err.Error(), "could not open directory") || buf.Len() != 0 {
			t.Fatalf("err %v rows %q", err, buf.String())
		}
	})
	t.Run("synthetic, through the engine", func(t *testing.T) {
		r, _ := bashRepo(t, map[string]string{"tests/test_a.sh": "exit 0\n"}, bashEntry("b", ""))
		shimGit(t, "warn")
		_, err := runner.Load(context.Background(), r.Dir)
		if err == nil || !strings.Contains(err.Error(), "RUNNER_PROTOCOL:b|list|") || !strings.Contains(err.Error(), "warning: synthetic") {
			t.Fatalf("Load: %v", err)
		}
	})
}

// A truncated inventory fails the listing, with no rows.
func TestBashFileInventoryTruncatedFailsClosed(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := bashRepo(t, map[string]string{"tests/test_a.sh": "exit 0\n", "tests/test_b.sh": "exit 0\n"}, bashEntry("b", ""))
	defer func(m int64) { bashFileListMax = m }(bashFileListMax)
	bashFileListMax = 8
	var buf bytes.Buffer
	err := bashFileList(context.Background(), &Env{Root: r.Dir, Runner: "b"}, &buf)
	if err == nil || !strings.Contains(err.Error(), "truncated") || buf.Len() != 0 {
		t.Fatalf("err %v rows %q", err, buf.String())
	}
}

// A bound path the id grammar reads as a member or variant ('#', '@') is not
// a plain file id: it refuses the listing, with no rows, rather than being
// listed as a unit whose run can never match it (missing_start). The valid
// script sorts first, so a row already accumulated must be withheld too.
func TestBashFileFragmentPathsRefused(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	for _, p := range []string{"tests/test_a#b.sh", "tests/test_a@v.sh"} {
		t.Run(p, func(t *testing.T) {
			r, _ := bashRepo(t, map[string]string{"tests/test_0_ok.sh": "exit 0\n", p: "exit 0\n"}, bashEntry("b", ""))
			var buf bytes.Buffer
			err := bashFileList(context.Background(), &Env{Root: r.Dir, Runner: "b"}, &buf)
			if err == nil || !strings.Contains(err.Error(), strconv.Quote(p)) || !strings.Contains(err.Error(), "no '#' member") || buf.Len() != 0 {
				t.Fatalf("err %v rows %q", err, buf.String())
			}
			loadErr(t, r, "RUNNER_PROTOCOL:b|list|", p)
		})
	}
}

// A manifest unit whose lowering is not its id's cwd-relative path, or whose
// bound is not positive, is an error row and is never run.
func TestBashFileUnitCheck(t *testing.T) {
	for _, tc := range []struct {
		cwd  string
		u    runner.ManifestUnit
		fail bool
	}{
		{"", runner.ManifestUnit{ID: "tests/test_a.sh", Lowering: "tests/test_a.sh", TimeoutS: 1}, false},
		{"sub", runner.ManifestUnit{ID: "sub/tests/test_a.sh", Lowering: "tests/test_a.sh", TimeoutS: 1}, false},
		{"", runner.ManifestUnit{ID: "tests/test_a.sh", Lowering: "tests/test_b.sh", TimeoutS: 1}, true},
		{"sub", runner.ManifestUnit{ID: "tests/test_a.sh", Lowering: "tests/test_a.sh", TimeoutS: 1}, true},
		{"", runner.ManifestUnit{ID: "tests/test_a.sh", Lowering: "../tests/test_a.sh", TimeoutS: 1}, true},
		{"", runner.ManifestUnit{ID: "tests/test_a.sh", Lowering: "tests/test_a.sh", TimeoutS: 0}, true},
	} {
		if err := bashFileUnitCheck(tc.cwd, tc.u); (err != nil) != tc.fail {
			t.Errorf("%q %+v: %v", tc.cwd, tc.u, err)
		}
	}
}

// Through Run: a forged unit is an error row, never a start row, and the
// run fails.
func TestBashFileRunRefusesForgedUnit(t *testing.T) {
	d := t.TempDir()
	if err := os.MkdirAll(filepath.Join(d, filepath.Dir(runner.RunnersPath)), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(d, runner.RunnersPath), []byte("contract: 1\nrunners:\n"+bashEntry("b", "")), 0o644); err != nil {
		t.Fatal(err)
	}
	m := &runner.Manifest{Results: filepath.Join(d, "results.jsonl"), ReportDir: d,
		Units: []runner.ManifestUnit{{ID: "tests/test_a.sh", Lowering: "tests/test_b.sh", TimeoutS: 1}}}
	res, err := OpenResults(m)
	if err != nil {
		t.Fatal(err)
	}
	code := bashFileRun(context.Background(), &Env{Root: d, Runner: "b"}, m, res)
	if err := res.Close(); err != nil {
		t.Fatal(err)
	}
	b, err := os.ReadFile(m.Results)
	if err != nil {
		t.Fatal(err)
	}
	if code != 1 || strings.Contains(string(b), `"event":"start"`) || !strings.Contains(string(b), `"status":"error"`) || !strings.Contains(string(b), "protocol:lowering") {
		t.Fatalf("code %d rows %s", code, b)
	}
}
