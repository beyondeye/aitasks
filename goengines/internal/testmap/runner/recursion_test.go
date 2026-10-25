package runner

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// recursionLimit bounds one isolated recursion test: each case builds
// fixtures and starts a nested engine.
const recursionLimit = 60 * time.Second

// recursionCase is one nested entry: the outer entry (an in-process Load or
// Run of a fixture repository) runs a runner whose list (discovery) or run
// (execution) starts the nested engine. The table is shared so t1854_6 can
// run every case under each of its boundary backends.
type recursionCase struct {
	group   string // the top-level test that runs it
	name    string
	origin  string // discovery | execution
	verb    string // check | run: what the nested engine does
	wrap    string // direct | sh | bash | python: how the runner starts it
	clear   bool   // the nested engine's environment is cleared (env -i, PATH kept)
	target  string // same | worktree | fixture
	refused bool
}

func recursionCases() []recursionCase {
	var cs []recursionCase
	add := func(c recursionCase) {
		env := "marker"
		if c.clear {
			env = "env-i"
		}
		c.name = strings.Join([]string{c.origin, c.verb, c.wrap, env, c.target}, "/")
		cs = append(cs, c)
	}
	for _, wrap := range []string{"sh", "bash", "python"} {
		for _, clear := range []bool{false, true} {
			add(recursionCase{group: "wrappers", origin: "execution", verb: "run", wrap: wrap, clear: clear, target: "same", refused: true})
		}
	}
	for _, verb := range []string{"check", "run"} {
		for _, clear := range []bool{false, true} {
			add(recursionCase{group: "discovery", origin: "discovery", verb: verb, wrap: "direct", clear: clear, target: "same", refused: true})
		}
	}
	for _, clear := range []bool{false, true} {
		add(recursionCase{group: "worktree", origin: "execution", verb: "check", wrap: "direct", clear: clear, target: "worktree", refused: true})
		add(recursionCase{group: "worktree", origin: "discovery", verb: "run", wrap: "direct", clear: clear, target: "worktree", refused: true})
	}
	for _, origin := range []string{"discovery", "execution"} {
		for _, clear := range []bool{false, true} {
			add(recursionCase{group: "fixture", origin: origin, verb: "run", wrap: "direct", clear: clear, target: "fixture"})
		}
	}
	// A setsid double fork orphans the nested engine out of the runner's
	// process tree, its environment cleared: only the containment's
	// subreaper keeps it below the outer engine, where the ancestry
	// backstop finds it (t1854_6).
	for _, origin := range []string{"discovery", "execution"} {
		add(recursionCase{group: "orphan", origin: origin, verb: "run", wrap: "orphan", clear: true, target: "same", refused: true})
	}
	return cs
}

// engineExe is the test binary, which TestMain turns into the nested engine.
func engineExe(t *testing.T) string {
	t.Helper()
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	return exe
}

// python3 is the interpreter for the python wrapper; without one the case is
// skipped, unless real tools are required.
func python3(t *testing.T) string {
	t.Helper()
	py, err := exec.LookPath("python3")
	if err != nil {
		if os.Getenv("AIT_TESTMAP_REQUIRE_REAL_TOOLS") == "1" {
			t.Fatal("python3 is required")
		}
		t.Skip("no python3")
	}
	return py
}

// nestCommand is the shell command a runner uses to start the nested engine
// in dir (a shell word: a quoted path, or "$AIT_TESTMAP_ROOT" for the
// runner's own repository): `$E` is the engine, `$PY` python.
func nestCommand(wrap, verb, dir string, clear bool) string {
	cd := "cd " + dir + " && "
	env := ""
	if clear {
		env = `env -i PATH="$PATH" `
	}
	switch wrap {
	case "sh", "bash":
		return cd + env + wrap + ` -c '"$0" ` + nestedEngineArg + ` "$1"' "$E" ` + verb
	case "python":
		call := "subprocess.call(sys.argv[1:])"
		if clear {
			call = `subprocess.call(sys.argv[1:], env={"PATH": os.environ["PATH"]})`
		}
		return cd + `"$PY" -c 'import os, subprocess, sys; sys.exit(` + call + `)' "$E" ` + nestedEngineArg + " " + verb
	case "noenv":
		return cd + `env -i "$E" ` + nestedEngineArg + " " + verb
	case "orphan":
		// setsid sh -c '( … ) &': the inner subshell is orphaned the moment
		// the setsid shell (its $$) exits and is reaped, and only then starts
		// the nested engine, so the ancestry it walks is the orphan's; the
		// runner waits for its result files.
		inner := `while kill -0 $$ 2>/dev/null; do sleep 0.01; done; ` +
			env + `"$0" ` + nestedEngineArg + ` "$1" >"$2/orphan.err" 2>&1; echo $? >"$2/orphan.rc"`
		return cd + `setsid sh -c '( ` + inner + ` ) &' "$E" ` + verb + ` "$D" & wait $!; ` +
			`while [ ! -s "$D/orphan.rc" ]; do sleep 0.01; done; cat "$D/orphan.err" >&2; exit "$(cat "$D/orphan.rc")"`
	}
	return cd + env + `"$E" ` + nestedEngineArg + " " + verb
}

// nestRepo is a fixture repository with one runner, shell, over tests/a.sh.
// Every call of it appends `<pid> <verb> <marker>` to <state>/calls.log; at
// verb at (list or run; "" never) it runs nest once — the mkdir makes a
// guard that fails yield a wrong exit, never a fork bomb — recording the
// nested stdout, stderr and exit status. wt, when set, is added as a linked
// worktree after the commit.
func nestRepo(t *testing.T, at, nest, py, wt string) (*fixture.Repo, string) {
	t.Helper()
	r := newRepo(t, map[string]string{"tests/a.sh": "#!/bin/sh\n"})
	d := stateOf(t, r)
	if nest == "" {
		nest = ":"
	}
	arm := func(verb string) string {
		if verb == at {
			return "nest; "
		}
		return ""
	}
	body := "#!/usr/bin/env bash\nset -u\n" +
		"D=" + strconv.Quote(d) + "\nE=" + strconv.Quote(engineExe(t)) + "\nPY=" + strconv.Quote(py) + "\n" +
		"echo \"$$ $1 ${" + ActiveEnv + "-}\" >> \"$D/calls.log\"\n" +
		"nest() {\n  mkdir \"$D/nest.once\" 2>/dev/null || return 0\n" +
		"  ( " + nest + " ) >\"$D/nested.out\" 2>\"$D/nested.err\"\n  echo $? >\"$D/nested.rc\"\n}\n" +
		"case \"$1\" in\n" +
		"describe) echo 'unit: file' ;;\n" +
		"list) " + arm("list") + "printf 'tests/a.sh\\tfile\\ta\\n' ;;\n" +
		"run) " + arm("run") + "R=$(sed -n 's/^  \"results\": \"\\(.*\\)\",$/\\1/p' \"$3\")\n" +
		"  printf '{\"id\":\"tests/a.sh\",\"status\":\"pass\",\"duration_ms\":1}\\n' >> \"$R\" ;;\n" +
		"*) exit 64 ;;\nesac\n"
	p := RunnersDir + "/shell.sh"
	r.Write(t, p, body)
	if err := os.Chmod(filepath.Join(r.Dir, filepath.FromSlash(p)), 0o755); err != nil {
		t.Fatal(err)
	}
	runners(t, r, "runners:\n  - name: shell\n    bind: ['tests/*.sh']\n")
	commitAll(t, r)
	if wt != "" {
		r.Run(t, "worktree", "add", "-q", wt)
	}
	return r, d
}

// calls are the logged runner calls: verb → the markers they saw.
func calls(t *testing.T, d string) map[string][]string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(d, "calls.log"))
	if errors.Is(err, os.ErrNotExist) {
		return map[string][]string{}
	}
	if err != nil {
		t.Fatal(err)
	}
	m := map[string][]string{}
	for _, l := range strings.Split(strings.TrimSpace(string(b)), "\n") {
		f := strings.SplitN(l, " ", 3)
		if len(f) < 2 {
			t.Fatalf("calls.log line %q", l)
		}
		m[f[1]] = append(m[f[1]], strings.Join(f[2:], ""))
	}
	return m
}

// nested is what the nested engine reported.
type nested struct {
	rc        int
	line, via string
	stderr    string
	ran       bool
}

func readNested(t *testing.T, d string) nested {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(d, "nested.rc"))
	if err != nil {
		t.Fatalf("the nested engine did not run: %v", err)
	}
	rc, err := strconv.Atoi(strings.TrimSpace(string(b)))
	if err != nil {
		t.Fatal(err)
	}
	e, _ := os.ReadFile(filepath.Join(d, "nested.err"))
	n := nested{rc: rc, stderr: string(e), ran: true}
	lines := strings.Split(strings.TrimSpace(n.stderr), "\n")
	n.line = lines[0]
	for _, l := range lines {
		if v, ok := strings.CutPrefix(l, "VIA:"); ok {
			n.via = v
		}
	}
	return n
}

// sameDir reports two paths naming one directory.
func sameDir(t *testing.T, a, b string) bool {
	t.Helper()
	ra, err1 := filepath.EvalSymlinks(a)
	rb, err2 := filepath.EvalSymlinks(b)
	return err1 == nil && err2 == nil && ra == rb
}

// refusedAt checks a refusal line for root.
func refusedAt(t *testing.T, line, class, root string) bool {
	t.Helper()
	rest, ok := strings.CutPrefix(line, "RUN_ERROR:"+class+"|")
	if !ok {
		return false
	}
	got, _, _ := strings.Cut(rest, "|")
	return sameDir(t, got, root)
}

// outerEntry is the in-process entry the case nests in.
func outerEntry(t *testing.T, origin, root string) {
	t.Helper()
	var err error
	if origin == "discovery" {
		_, err = Load(bg, root)
	} else {
		var rep *RunReport
		rep, err = Run(bg, root, Options{All: true, RunID: "outer"})
		if err == nil && rep.Exit() != 0 {
			t.Fatalf("outer run exit %d: %+v", rep.Exit(), rep.Invocations)
		}
	}
	if err != nil {
		t.Fatalf("outer %s: %v", origin, err)
	}
}

// checkRecursion runs one case end to end.
func checkRecursion(t *testing.T, c recursionCase) {
	t.Helper()
	py := ""
	if c.wrap == "python" {
		py = python3(t)
	}
	at := map[string]string{"discovery": "list", "execution": "run"}[c.origin]
	var target, word, wt, otherState string
	switch c.target {
	case "same":
		word = `"$AIT_TESTMAP_ROOT"`
	case "worktree":
		wt = filepath.Join(t.TempDir(), "wt")
		target, word = wt, strconv.Quote(wt)
	case "fixture":
		var other *fixture.Repo
		other, otherState = nestRepo(t, "", "", "", "")
		target, word = other.Dir, strconv.Quote(other.Dir)
	}
	r, d := nestRepo(t, at, nestCommand(c.wrap, c.verb, word, c.clear), py, wt)
	if c.target == "same" {
		target = r.Dir
	}
	outerEntry(t, c.origin, r.Dir)
	n := readNested(t, d)
	if !c.refused {
		if n.rc != 0 || !strings.Contains(n.stderr, "NESTED_OK:0") {
			t.Fatalf("nested entry into %s: rc %d %q", c.target, n.rc, n.stderr)
		}
		oc := calls(t, otherState)
		if len(oc["describe"]) != 1 || len(oc["run"]) != 1 {
			t.Fatalf("the allowed nested entry did not run its runner: %v", oc)
		}
		outerID, _ := Identity(bg, r.Dir)
		inherits := slices.Contains(mustParse(t, oc["describe"][0]), outerID)
		if inherits == c.clear {
			t.Fatalf("nested marker %q (cleared env %v) vs outer identity %s", oc["describe"][0], c.clear, outerID)
		}
		return
	}
	if n.rc != 3 || !refusedAt(t, n.line, "recursion", target) {
		t.Fatalf("nested entry: rc %d stderr %q, want RUN_ERROR:recursion|%s", n.rc, n.stderr, target)
	}
	want := "marker"
	if c.clear {
		want = "ancestor:" + strconv.Itoa(os.Getpid())
	}
	if n.via != want {
		t.Fatalf("refused via %q, want %q", n.via, want)
	}
	if got := calls(t, d); len(got["describe"]) != 1 {
		t.Fatalf("a runner process started after the refusal: %v", got)
	}
}

func mustParse(t *testing.T, marker string) []string {
	t.Helper()
	ids, err := ParseActive(marker)
	if err != nil {
		t.Fatalf("marker %q: %v", marker, err)
	}
	return ids
}

func runGroup(t *testing.T, group string) {
	t.Helper()
	n := 0
	for _, c := range recursionCases() {
		if c.group == group {
			n++
			t.Run(c.name, func(t *testing.T) { checkRecursion(t, c) })
		}
	}
	if n == 0 {
		t.Fatalf("no cases in group %s", group)
	}
}

// A nested run of the same repository through sh -c, bash and python — with
// the environment inherited (marker) and cleared (ancestry) — is refused.
func TestRecursionWrappers(t *testing.T) {
	if !isolated(t, recursionLimit) {
		return
	}
	runGroup(t, "wrappers")
}

// A project runner whose list calls check / run on its own repository is
// refused: discovery runs project code too.
func TestRecursionDiscovery(t *testing.T) {
	if !isolated(t, recursionLimit) {
		return
	}
	runGroup(t, "discovery")
}

// Another worktree of the same repository is the same repository.
func TestRecursionWorktree(t *testing.T) {
	if !isolated(t, recursionLimit) {
		return
	}
	runGroup(t, "worktree")
}

// A nested entry into another (fixture) repository is allowed, from both
// discovery and execution, and its runners see the outer identity only when
// the environment was inherited.
func TestRecursionFixtureAllowed(t *testing.T) {
	if !isolated(t, recursionLimit) {
		return
	}
	runGroup(t, "fixture")
}

// An orphaned (setsid double-forked) nested engine with a cleared
// environment is refused by the ancestry backstop, from discovery and from
// execution: the supervisor's subreaper keeps it below the outer engine.
func TestRecursionOrphan(t *testing.T) {
	if !isolated(t, recursionLimit) {
		return
	}
	runGroup(t, "orphan")
}

// recursionBackends prepares each procsup containment backend for the
// recursion invariant (G8a): under every backend the cleared-environment
// refusal and the fixture-repository allowance hold. A backend procsup
// adds (cgroup hardening, a PID namespace) must join this table —
// TestRecursionBackendsCovered fails until it does.
var recursionBackends = map[string]func(t *testing.T){
	procsup.Supervisor: func(*testing.T) {}, // the default on Linux
}

func TestRecursionBackendsCovered(t *testing.T) {
	var got []string
	for b := range recursionBackends {
		got = append(got, b)
	}
	slices.Sort(got)
	want := slices.Sorted(slices.Values(procsup.Backends()))
	if !slices.Equal(got, want) {
		t.Fatalf("recursion invariant backends %v, procsup.Backends() %v", got, want)
	}
}

// Every recursion case under the supervisor backend.
func TestRecursionBackendSupervisor(t *testing.T) {
	if !isolated(t, recursionLimit) {
		return
	}
	recursionBackends[procsup.Supervisor](t)
	for _, c := range recursionCases() {
		t.Run(c.group+"/"+c.name, func(t *testing.T) { checkRecursion(t, c) })
	}
}

// The refusal happens before any runner process starts, leaves no run
// directory and no holder record, and names the root.
func TestGuardRefusesBeforeAnyRunnerStarts(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r, d := nestRepo(t, "", "", "", "")
	id, err := Identity(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	check := func(what string, err error, via string) {
		t.Helper()
		var re *RecursionError
		if !errors.As(err, &re) || re.Via != via || re.Unverifiable {
			t.Fatalf("%s: %v", what, err)
		}
		if line, lerr := re.Line(); lerr != nil || line != "RUN_ERROR:recursion|"+r.Dir {
			t.Fatalf("%s: line %q %v", what, line, lerr)
		}
	}
	t.Setenv(ActiveEnv, FormatActive([]string{"/elsewhere/.git", id}))
	_, err = Load(bg, r.Dir)
	check("Load", err, "marker")
	_, err = Run(bg, r.Dir, Options{All: true, RunID: "refused"})
	check("Run", err, "marker")
	t.Setenv(ActiveEnv, "")
	_, err = Load(withActive(bg, []*ctxEntry{{id: id}}), r.Dir)
	check("Load in context", err, "context")
	_, err = Run(withActive(bg, []*ctxEntry{{id: id}}), r.Dir, Options{All: true, RunID: "refused"})
	check("Run in context", err, "context")
	if c := calls(t, d); len(c) != 0 {
		t.Fatalf("runner calls after a refusal: %v", c)
	}
	if _, err := os.Stat(filepath.Join(r.Dir, StateDir, "runs")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("run directory: %v", err)
	}
	if hs, _ := os.ReadDir(holdersDir(id)); len(hs) != 0 {
		t.Fatalf("holder records left: %v", hs)
	}
}

// describe, list and run all get the marker: the inherited identities and
// this repository's.
func TestMarkerReachesEveryRunnerProcess(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r, d := nestRepo(t, "", "", "", "")
	id, err := Identity(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	inherited := append(mustParse(t, os.Getenv(ActiveEnv)), "/with:colon%/.git")
	t.Setenv(ActiveEnv, FormatActive(inherited))
	if _, err := Run(bg, r.Dir, Options{All: true, RunID: "m"}); err != nil {
		t.Fatal(err)
	}
	want := FormatActive(append(slices.Clone(inherited), id))
	for _, verb := range []string{"describe", "list", "run"} {
		if got := calls(t, d)[verb]; len(got) != 1 || got[0] != want {
			t.Fatalf("%s saw %q, want %q", verb, got, want)
		}
	}
}

// An in-process Run(A) → Run(B) through the context is allowed, B's
// runner processes carry both identities, and a child of B entering A is
// refused by the marker — also when A's holder record is gone, so ancestry
// cannot be what refuses it.
func TestCrossRepositoryMarker(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	for _, dropHolder := range []bool{false, true} {
		t.Run(fmt.Sprintf("drop-holder=%v", dropHolder), func(t *testing.T) {
			a, _ := nestRepo(t, "", "", "", "")
			aID, err := Identity(bg, a.Dir)
			if err != nil {
				t.Fatal(err)
			}
			nest := nestCommand("direct", "check", strconv.Quote(a.Dir), false)
			if dropHolder {
				nest = "rm -f " + strconv.Quote(holdersDir(aID)) + "/h-* && " + nest
			}
			b, bState := nestRepo(t, "run", nest, "", "")
			bID, err := Identity(bg, b.Dir)
			if err != nil {
				t.Fatal(err)
			}
			withHooks(t)
			var inner error
			RegisterPostRunHook("cross", func(ctx context.Context, rep *RunReport) error {
				if rep.Root == a.Dir {
					_, inner = Run(ctx, b.Dir, Options{All: true, RunID: "inner"})
				}
				return nil
			})
			if _, err := Run(bg, a.Dir, Options{All: true, RunID: "outer"}); err != nil {
				t.Fatal(err)
			}
			if inner != nil {
				t.Fatalf("Run(B) inside Run(A): %v", inner)
			}
			for verb, ms := range calls(t, bState) {
				for _, m := range ms {
					ids := mustParse(t, m)
					if !slices.Contains(ids, aID) || !slices.Contains(ids, bID) {
						t.Fatalf("B's %s saw %q, want both %s and %s", verb, m, aID, bID)
					}
				}
			}
			n := readNested(t, bState)
			if n.rc != 3 || !refusedAt(t, n.line, "recursion", a.Dir) || n.via != "marker" {
				t.Fatalf("child of B entering A: rc %d via %q %q", n.rc, n.via, n.stderr)
			}
		})
	}
}

// blockingRepo is a repository whose run waits until released (a file it
// polls for, so neither side can block on the other).
func blockingRepo(t *testing.T) (*fixture.Repo, string, func()) {
	t.Helper()
	gate := filepath.Join(t.TempDir(), "go")
	r, d := nestRepo(t, "run", "while [ ! -e "+strconv.Quote(gate)+" ]; do sleep 0.05; done", "", "")
	release := func() {
		if err := os.WriteFile(gate, nil, 0o644); err != nil {
			t.Error(err)
		}
	}
	return r, d, release
}

// waitFor polls until cond holds (bounded by the isolation limit).
func waitFor(t *testing.T, what string, cond func() bool) {
	t.Helper()
	for deadline := time.Now().Add(10 * time.Second); time.Now().Before(deadline); time.Sleep(10 * time.Millisecond) {
		if cond() {
			return
		}
	}
	t.Fatalf("timed out waiting for %s", what)
}

// A run of the same repository in a process that is not an ancestor — a
// concurrent, independent engine — does not refuse this one.
func TestConcurrentNonAncestorUnaffected(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r, d, release := blockingRepo(t)
	id, err := Identity(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	child := exec.Command(engineExe(t), nestedEngineArg, "run")
	child.Dir = r.Dir
	var errb strings.Builder
	child.Stderr = &errb
	if err := child.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() {
		release()
		child.Wait()
	}()
	waitFor(t, "the concurrent run", func() bool { return len(calls(t, d)["run"]) == 1 })
	if hs, _ := os.ReadDir(holdersDir(id)); len(hs) != 1 {
		t.Fatalf("holder records of the concurrent run: %v", hs)
	}
	if _, err := Load(bg, r.Dir); err != nil {
		t.Fatalf("Load beside a non-ancestor run: %v", err)
	}
	release()
	if err := child.Wait(); err != nil {
		t.Fatalf("concurrent run: %v %s", err, errb.String())
	}
}

// A hook or an executor calling Load with the context it received is a
// nested entry; an independent in-process call of its own is not.
func TestInProcessReentry(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	t.Run("hook", func(t *testing.T) {
		r, d := nestRepo(t, "", "", "", "")
		withHooks(t)
		var got error
		RegisterPostRunHook("reenter", func(ctx context.Context, rep *RunReport) error {
			_, got = Load(ctx, r.Dir)
			return nil
		})
		if _, err := Run(bg, r.Dir, Options{All: true, RunID: "h"}); err != nil {
			t.Fatal(err)
		}
		var re *RecursionError
		if !errors.As(got, &re) || re.Via != "context" {
			t.Fatalf("hook Load: %v", got)
		}
		if c := calls(t, d); len(c["describe"]) != 1 {
			t.Fatalf("describe ran for the refused re-entry: %v", c)
		}
	})
	t.Run("executor", func(t *testing.T) {
		r, _ := nestRepo(t, "", "", "", "")
		var got error
		withExecutor(t, executorFunc(func(ctx context.Context, invs []*Invocation, invoke InvokeFunc) ([]Outcome, error) {
			_, got = Load(ctx, r.Dir)
			return serialExecutor{}.Execute(ctx, invs, invoke)
		}))
		if _, err := Run(bg, r.Dir, Options{All: true, RunID: "e"}); err != nil {
			t.Fatal(err)
		}
		var re *RecursionError
		if !errors.As(got, &re) || re.Via != "context" {
			t.Fatalf("executor Load: %v", got)
		}
	})
	t.Run("independent", func(t *testing.T) {
		r, d, release := blockingRepo(t)
		done := make(chan error, 1)
		go func() {
			_, err := Run(bg, r.Dir, Options{All: true, RunID: "i"})
			done <- err
		}()
		var runErr error
		finished := false
		finish := func() {
			if !finished {
				finished = true
				release()
				runErr = <-done
			}
		}
		defer finish()
		waitFor(t, "the blocked run", func() bool { return len(calls(t, d)["run"]) == 1 })
		if _, err := Load(context.Background(), r.Dir); err != nil {
			t.Fatalf("an independent Load beside the run: %v", err)
		}
		finish()
		if runErr != nil {
			t.Fatal(runErr)
		}
	})
}

type executorFunc func(context.Context, []*Invocation, InvokeFunc) ([]Outcome, error)

func (f executorFunc) Execute(ctx context.Context, invs []*Invocation, invoke InvokeFunc) ([]Outcome, error) {
	return f(ctx, invs, invoke)
}

// Holder records: one naming an ancestor refuses; one naming a live
// non-ancestor is kept and does not; provably stale ones are pruned; an
// entry's own record goes on release and on an error return.
func TestHolderRecords(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r, _ := nestRepo(t, "", "", "", "")
	id, err := Identity(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	dir := holdersDir(id)
	v, err := newProcView()
	if err != nil {
		t.Fatal(err)
	}
	fact := func(pid int) procFact {
		f, st, err := v.lookup(pid)
		if err != nil || st != procFound {
			t.Fatalf("pid %d: %v %v", pid, st, err)
		}
		return f
	}
	put := func(tag string, rec holderRecord) string {
		t.Helper()
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatal(err)
		}
		p := filepath.Join(dir, fmt.Sprintf("%s%d-%s", holderPrefix, rec.Pid, tag))
		if err := os.WriteFile(p, []byte(fmt.Sprintf(`{"pid":%d,"start":%q,"root":"x"}`, rec.Pid, rec.Start)), 0o644); err != nil {
			t.Fatal(err)
		}
		return p
	}
	exists := func(p string) bool { _, err := os.Stat(p); return err == nil }

	// An ancestor (this test process's parent) holding the repository.
	pp := os.Getppid()
	anc := put("ancestor", holderRecord{Pid: pp, Start: fact(pp).Start})
	var re *RecursionError
	if _, err := Load(bg, r.Dir); !errors.As(err, &re) || re.Via != "ancestor:"+strconv.Itoa(pp) {
		t.Fatalf("ancestor holder: %v", err)
	}
	os.Remove(anc)
	// The ancestor's pid with another start time is not that ancestor.
	recycled := put("recycled", holderRecord{Pid: pp, Start: "not-its-start"})
	if _, err := Load(bg, r.Dir); err != nil || exists(recycled) {
		t.Fatalf("recycled ancestor pid: %v, kept %v", err, exists(recycled))
	}

	sleep := exec.Command("sleep", "30")
	if err := sleep.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { sleep.Process.Kill(); sleep.Wait() }()
	live := put("live", holderRecord{Pid: sleep.Process.Pid, Start: fact(sleep.Process.Pid).Start})
	reused := put("reused", holderRecord{Pid: sleep.Process.Pid, Start: "not-its-start"})
	done := exec.Command("true")
	if err := done.Run(); err != nil {
		t.Fatal(err)
	}
	dead := put("dead", holderRecord{Pid: done.Process.Pid, Start: "1"})
	if _, err := Load(bg, r.Dir); err != nil {
		t.Fatalf("non-ancestor holders: %v", err)
	}
	if !exists(live) || exists(reused) || exists(dead) {
		t.Fatalf("after Load: live %v reused %v dead %v", exists(live), exists(reused), exists(dead))
	}
	if hs, _ := os.ReadDir(dir); len(hs) != 1 {
		t.Fatalf("own record not released: %v", hs)
	}
	os.Remove(live)

	// An error after the guard was entered releases the record too.
	runners(t, r, "runners:\n  - name: shell\n    bind: ['tests/*.sh']\n    cwd: missing\n")
	if _, err := Load(bg, r.Dir); err == nil {
		t.Fatal("Load with a missing cwd succeeded")
	}
	if hs, _ := os.ReadDir(dir); len(hs) != 0 {
		t.Fatalf("record left after an error: %v", hs)
	}
}

// A context kept past its call no longer holds the call's identity: a
// later entry through it is allowed, and runner processes started after the
// release do not carry it.
func TestReleasedContext(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	t.Run("saved", func(t *testing.T) {
		a, _ := nestRepo(t, "", "", "", "")
		b, bState := nestRepo(t, "", "", "", "")
		aID, _ := Identity(bg, a.Dir)
		withHooks(t)
		var saved context.Context
		RegisterPostRunHook("save", func(ctx context.Context, rep *RunReport) error {
			if rep.Root == a.Dir {
				saved = ctx
			}
			return nil
		})
		if _, err := Run(bg, a.Dir, Options{All: true, RunID: "a"}); err != nil {
			t.Fatal(err)
		}
		if _, err := Load(saved, a.Dir); err != nil {
			t.Fatalf("Load through a context whose call returned: %v", err)
		}
		if _, err := Run(saved, b.Dir, Options{All: true, RunID: "b"}); err != nil {
			t.Fatal(err)
		}
		for verb, ms := range calls(t, bState) {
			if slices.Contains(mustParse(t, ms[0]), aID) {
				t.Fatalf("B's %s carries released A: %q", verb, ms[0])
			}
		}
	})
	t.Run("outlived", func(t *testing.T) {
		a, _ := nestRepo(t, "", "", "", "")
		gate := filepath.Join(t.TempDir(), "go")
		b, bState := nestRepo(t, "list", "while [ ! -e "+strconv.Quote(gate)+" ]; do sleep 0.05; done", "", "")
		aID, _ := Identity(bg, a.Dir)
		withHooks(t)
		innerDone := make(chan error, 1)
		RegisterPostRunHook("outlive", func(ctx context.Context, rep *RunReport) error {
			if rep.Root == a.Dir {
				go func() {
					_, err := Run(ctx, b.Dir, Options{All: true, RunID: "b"})
					innerDone <- err
				}()
				// B's runners are loaded while A still holds: only what
				// starts after A's release must drop A.
				waitFor(t, "B's describe", func() bool { return len(calls(t, bState)["describe"]) == 1 })
			}
			return nil
		})
		if _, err := Run(bg, a.Dir, Options{All: true, RunID: "a"}); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(gate, nil, 0o644); err != nil {
			t.Fatal(err)
		}
		if err := <-innerDone; err != nil {
			t.Fatalf("Run(B) outliving Run(A): %v", err)
		}
		run := calls(t, bState)["run"]
		if len(run) != 1 || slices.Contains(mustParse(t, run[0]), aID) {
			t.Fatalf("B's run, started after A released, saw %q", run)
		}
	})
}

// A published record the guard cannot read is never silently skipped: one
// whose name names an ancestor refuses (unverifiable); one naming a live
// non-ancestor is irrelevant and kept; one naming a gone pid is pruned. No
// record can block the read.
func TestUnreadableHolderRecords(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r, d := nestRepo(t, "", "", "", "")
	id, err := Identity(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	dir := holdersDir(id)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	sleep := exec.Command("sleep", "30")
	if err := sleep.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { sleep.Process.Kill(); sleep.Wait() }()
	done := exec.Command("true")
	if err := done.Run(); err != nil {
		t.Fatal(err)
	}
	pp, live, gonePid := os.Getppid(), sleep.Process.Pid, done.Process.Pid
	v, _ := newProcView()
	liveFact, _, _ := v.lookup(live)
	name := func(pid int, tag string) string {
		return filepath.Join(dir, fmt.Sprintf("%s%d-%s", holderPrefix, pid, tag))
	}
	write := func(p, content string) {
		t.Helper()
		if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	fifo := func(p string) {
		t.Helper()
		if err := syscall.Mkfifo(p, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	refused := func(what string) {
		t.Helper()
		var re *RecursionError
		if _, err := Load(bg, r.Dir); !errors.As(err, &re) || !re.Unverifiable || !strings.HasPrefix(re.Detail, "holders: ") {
			t.Fatalf("%s: %v", what, err)
		}
	}
	allowed := func(what string) {
		t.Helper()
		if _, err := Load(bg, r.Dir); err != nil {
			t.Fatalf("%s: %v", what, err)
		}
	}
	clear := func() {
		t.Helper()
		os.RemoveAll(dir)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	exists := func(p string) bool { _, err := os.Lstat(p); return err == nil }

	for _, c := range []struct {
		name  string
		setup func()
	}{
		{"malformed", func() { write(name(pp, "x"), "{not json") }},
		{"fifo", func() { fifo(name(pp, "x")) }},
		{"symlink", func() { os.Symlink("/dev/null", name(pp, "x")) }},
		{"directory", func() { os.Mkdir(name(pp, "x"), 0o755) }},
		{"oversized", func() {
			write(name(pp, "x"), fmt.Sprintf(`{"pid":%d,"start":"s","root":"%s"}`, pp, strings.Repeat("x", int(holderMax))))
		}},
		{"pid disagrees with its name", func() { write(name(pp, "x"), fmt.Sprintf(`{"pid":%d,"start":%q,"root":"x"}`, live, liveFact.Start)) }},
		{"no start", func() { write(name(pp, "x"), fmt.Sprintf(`{"pid":%d,"root":"x"}`, pp)) }},
		{"unnamed holder", func() { write(filepath.Join(dir, holderPrefix+"garbage"), "{}") }},
	} {
		clear()
		c.setup()
		refused(c.name)
	}
	clear()
	irrelevant := name(live, "x")
	fifo(irrelevant)
	write(name(live, "y"), "{not json")
	staleRec := name(gonePid, "x")
	write(staleRec, "{not json")
	allowed("unreadable records of a live non-ancestor and of a gone pid")
	if !exists(irrelevant) || !exists(name(live, "y")) || exists(staleRec) {
		t.Fatalf("kept irrelevant %v/%v, pruned stale %v", exists(irrelevant), exists(name(live, "y")), !exists(staleRec))
	}
	if c := calls(t, d); len(c["describe"]) != 1 {
		t.Fatalf("describe ran for a refused entry: %v", c)
	}
}

// What the guard cannot establish is refused, never admitted.
func TestGuardUnverifiable(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r, d := nestRepo(t, "", "", "", "")
	unverifiable := func(what string, err error, detail string) {
		t.Helper()
		var re *RecursionError
		if !errors.As(err, &re) || !re.Unverifiable || !strings.HasPrefix(re.Detail, detail) {
			t.Fatalf("%s: %v", what, err)
		}
		line, _ := re.Line()
		if !strings.HasPrefix(line, "RUN_ERROR:recursion-unverifiable|"+re.Root+"|"+detail) {
			t.Fatalf("%s: line %q", what, line)
		}
	}
	old := newProcView
	newProcView = func() (procView, error) { return nil, errors.New("injected") }
	_, err := Load(bg, r.Dir)
	newProcView = old
	unverifiable("ancestry", err, "ancestry: injected")

	t.Setenv(ActiveEnv, "relative/.git")
	_, err = Load(bg, r.Dir)
	unverifiable("marker", err, ActiveEnv+": ")
	t.Setenv(ActiveEnv, "")

	plain := t.TempDir()
	for p, c := range map[string]string{registry.ConfigPath: "contract: 1\n", RunnersPath: "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n"} {
		if err := os.MkdirAll(filepath.Dir(filepath.Join(plain, p)), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(plain, p), []byte(c), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	_, err = Load(bg, plain)
	unverifiable("not a git checkout", err, "identity: ")
	if c := calls(t, d); len(c) != 0 {
		t.Fatalf("runner calls: %v", c)
	}

	// A nested engine with no PATH at all cannot find git: refused, not run.
	q, qd := nestRepo(t, "run", nestCommand("noenv", "check", `"$AIT_TESTMAP_ROOT"`, true), "", "")
	outerEntry(t, "execution", q.Dir)
	n := readNested(t, qd)
	if n.rc != 3 || !refusedAt(t, n.line, "recursion-unverifiable", q.Dir) || !strings.Contains(n.line, "|identity: ") {
		t.Fatalf("no PATH: rc %d %q", n.rc, n.stderr)
	}
	if c := calls(t, qd); len(c["describe"]) != 1 {
		t.Fatalf("a runner started after the unverifiable refusal: %v", c)
	}
}

// Every worktree of a repository has one identity; another repository has
// another.
func TestIdentity(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	wt := filepath.Join(t.TempDir(), "wt")
	r, _ := nestRepo(t, "", "", "", wt)
	link := filepath.Join(t.TempDir(), "link")
	if err := os.Symlink(r.Dir, link); err != nil {
		t.Fatal(err)
	}
	want, err := filepath.EvalSymlinks(filepath.Join(r.Dir, ".git"))
	if err != nil {
		t.Fatal(err)
	}
	for _, dir := range []string{r.Dir, wt, link, filepath.Join(r.Dir, "tests")} {
		if got, err := Identity(bg, dir); err != nil || got != want {
			t.Fatalf("Identity(%s) = %q %v, want %q", dir, got, err, want)
		}
	}
	other, _ := nestRepo(t, "", "", "", "")
	if got, _ := Identity(bg, other.Dir); got == want {
		t.Fatal("another repository has the same identity")
	}
}

func TestActiveMarkerFormat(t *testing.T) {
	ids := []string{"/a:b/.git", "/c%d/.git", "/plain/.git"}
	s := FormatActive(ids)
	if s != "/a%3Ab/.git:/c%25d/.git:/plain/.git" {
		t.Fatalf("format %q", s)
	}
	if got, err := ParseActive(s); err != nil || !slices.Equal(got, ids) {
		t.Fatalf("round trip %q %v", got, err)
	}
	if got, err := ParseActive("/x%3a"); err != nil || !slices.Equal(got, []string{"/x:"}) {
		t.Fatalf("lower-case escape %q %v", got, err)
	}
	if got, err := ParseActive(""); err != nil || got != nil {
		t.Fatalf("empty %q %v", got, err)
	}
	for _, bad := range []string{"relative", "/a::/b", ":/a", "/a%zz", "/a%2", "/a%"} {
		if _, err := ParseActive(bad); err == nil {
			t.Errorf("ParseActive(%q) accepted", bad)
		}
	}
}

// fakeProc is one process of a fake view.
type fakeProc struct {
	ppid  int
	start string
	state procState
	err   error
}

type fakeView map[int]fakeProc

func (v fakeView) lookup(pid int) (procFact, procState, error) {
	p, ok := v[pid]
	if !ok {
		return procFact{}, procGone, nil
	}
	return procFact{Ppid: p.ppid, Start: p.start}, p.state, p.err
}

// viewSeq makes each walk take the next view; the last one repeats.
func viewSeq(views ...fakeView) func() (procView, error) {
	i := 0
	return func() (procView, error) {
		v := views[min(i, len(views)-1)]
		i++
		return v, nil
	}
}

// The ancestry walk is restarted when the chain changes under it, accepted
// only when two complete walks agree, and fails closed otherwise.
func TestAncestryWalk(t *testing.T) {
	holder := []holder{{namePid: 10, valid: true, rec: holderRecord{Pid: 10, Start: "s10"}}}
	reparented := fakeView{100: {ppid: 10, start: "s100"}, 10: {ppid: 1, start: "s10"}, 1: {ppid: 0, start: "s1"}}
	launcherGone := fakeView{100: {ppid: 50, start: "s100"}, 10: {ppid: 1, start: "s10"}, 1: {ppid: 0, start: "s1"}}
	wrongFirst := fakeView{100: {ppid: 7, start: "s100"}, 7: {ppid: 1, start: "s7"}, 1: {ppid: 0, start: "s1"}}
	for _, c := range []struct {
		name    string
		views   []fakeView
		refused bool
		err     string
	}{
		// The launcher vanished for two walks: a truncated walk [100] would
		// have been "stable" and admitted the nested entry.
		{name: "vanished launcher", views: []fakeView{launcherGone, launcherGone, reparented}, refused: true},
		// A first walk that the next one contradicts is never accepted.
		{name: "first walk contradicted", views: []fakeView{wrongFirst, reparented}, refused: true},
		{name: "foreign ancestor ends the walk", views: []fakeView{{100: {ppid: 20, start: "s100"}, 20: {state: procForeign}, 10: {ppid: 1, start: "s10"}}}},
		{name: "unstable", views: []fakeView{wrongFirst, reparented, wrongFirst, reparented, wrongFirst, reparented}, err: "ancestry unstable"},
		{name: "always changing", views: []fakeView{launcherGone}, err: "ancestry unstable"},
		{name: "cycle", views: []fakeView{{100: {ppid: 30, start: "s100"}, 30: {ppid: 100, start: "s30"}}}, err: "ancestry cycle"},
		{name: "lookup error", views: []fakeView{{100: {ppid: 30, start: "s100"}, 30: {err: errors.New("boom")}}}, err: "boom"},
		{name: "own process invisible", views: []fakeView{{}}, err: "own process"},
	} {
		t.Run(c.name, func(t *testing.T) {
			links, err := stableWalk(100, viewSeq(c.views...))
			if c.err != "" {
				if err == nil || !strings.Contains(err.Error(), c.err) {
					t.Fatalf("err %v, want %q", err, c.err)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			_, refused := matchAncestor(links, holder)
			if refused != c.refused {
				t.Fatalf("links %v: refused %v, want %v", links, refused, c.refused)
			}
		})
	}
}

func TestParsePsAncestry(t *testing.T) {
	out := "    1     0 Thu Oct  1 08:00:00 2026\n\n  412     1 Thu Oct 22 16:37:28 2026\n"
	m, err := parsePsAncestry(out)
	if err != nil {
		t.Fatal(err)
	}
	if m[1] != (procFact{Ppid: 0, Start: "Thu Oct 1 08:00:00 2026"}) || m[412] != (procFact{Ppid: 1, Start: "Thu Oct 22 16:37:28 2026"}) || len(m) != 2 {
		t.Fatalf("parsed %v", m)
	}
	for _, bad := range []string{
		"412 1 Thu Oct 22 16:37:28",                                      // short
		"412 1 Thu Oct 22 16:37:28 2026 x",                               // long
		"x 1 Thu Oct 22 16:37:28 2026",                                   // pid
		"412 y Thu Oct 22 16:37:28 2026",                                 // ppid
		"412 1 Thu Oct 22 16:37:28 2026\n412 1 Thu Oct 22 16:37:29 2026", // duplicate
	} {
		if _, err := parsePsAncestry(bad); err == nil {
			t.Errorf("accepted %q", bad)
		}
	}
}
