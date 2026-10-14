package runner

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"slices"
	"strings"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// batchRepo is a repository with one batch-mode runner over two units whose
// run body is given.
func batchRepo(t *testing.T, run string) *fixture.Repo {
	t.Helper()
	r := newRepo(t, map[string]string{"tests/a.sh": "#!/bin/sh\n", "tests/b.sh": "#!/bin/sh\n"})
	put(t, r, "shell", spec{describe: "unit: file\ntimeouts: batch", list: "tests/a.sh|file|a\ntests/b.sh|file|b\n", run: run})
	runners(t, r, "runners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 30\n    batch_timeout_s: 60\n")
	commitAll(t, r)
	return r
}

func TestRunPassFail(t *testing.T) {
	r := batchRepo(t, "row tests/a.sh pass 5; row tests/b.sh fail 7; exit 1")
	rep := runAll(t, r)
	if got := statuses(rep); !reflect.DeepEqual(got, map[string]string{"tests/a.sh": StatusPass, "tests/b.sh": StatusFail}) {
		t.Fatalf("statuses %v", got)
	}
	if rep.Exit() != 1 || len(rep.Invocations) != 1 || rep.Invocations[0].Cause != "" || rep.Invocations[0].UnitsReported != 2 {
		t.Fatalf("exit %d records %+v", rep.Exit(), rep.Invocations)
	}
	// The record and the manifest are on disk.
	dir := filepath.Join(r.Dir, filepath.FromSlash(rep.Dir), "inv-001")
	var rec Record
	b, err := os.ReadFile(filepath.Join(dir, "record.json"))
	if err != nil || json.Unmarshal(b, &rec) != nil || rec.Runner != "shell" || rec.Timeouts != TimeoutsBatch || rec.DeadlineS != 60 {
		t.Fatalf("record.json: %v %+v", err, rec)
	}
	var m Manifest
	b, err = os.ReadFile(filepath.Join(dir, "manifest.json"))
	if err != nil || json.Unmarshal(b, &m) != nil || len(m.Units) != 2 || m.Units[0].TimeoutS != 30 || m.Handle != "" {
		t.Fatalf("manifest.json: %v %+v", err, m)
	}
}

// Reconciliation failures are causes (no anchor) and fail the run.
func TestRunReconciliation(t *testing.T) {
	for run, want := range map[string]struct {
		cause, detail string
		status        map[string]string
	}{
		"exit 0":                      {CauseReconciliation, "zero_reported", map[string]string{"tests/a.sh": StatusMissing, "tests/b.sh": StatusMissing}},
		"row tests/a.sh pass; exit 0": {CauseReconciliation, "missing", map[string]string{"tests/a.sh": StatusPass, "tests/b.sh": StatusMissing}},
		"row tests/a.sh pass; row tests/b.sh pass; row zzz pass; exit 0": {CauseReconciliation, "unregistered_id:zzz", map[string]string{"tests/a.sh": StatusPass, "tests/b.sh": StatusPass}},
		"row tests/a.sh fail; row tests/b.sh pass; exit 0":               {CauseReconciliation, "exit_mismatch", map[string]string{"tests/a.sh": StatusFail, "tests/b.sh": StatusPass}},
	} {
		rep := runAll(t, batchRepo(t, run))
		rec := rep.Invocations[0]
		if rec.Cause != want.cause || rec.CauseDetail != want.detail || !reflect.DeepEqual(statuses(rep), want.status) || rep.Exit() != 1 {
			t.Errorf("%q: %s/%s %v exit %d", run, rec.Cause, rec.CauseDetail, statuses(rep), rep.Exit())
		}
	}
}

// The exit / status table through the real run: rows, cause, refused flag
// and the final exit together.
func TestRunExitOutcomes(t *testing.T) {
	for run, want := range map[string]struct {
		status  map[string]string
		cause   string
		refused bool
		exit    int
	}{
		"exit 75":                                          {map[string]string{"tests/a.sh": StatusRefused, "tests/b.sh": StatusRefused}, "", true, 75},
		"row tests/a.sh pass; exit 75":                     {map[string]string{"tests/a.sh": StatusPass, "tests/b.sh": StatusMissing}, CauseReconciliation, false, 1},
		"row tests/zzz.sh pass; exit 75":                   {map[string]string{"tests/a.sh": StatusMissing, "tests/b.sh": StatusMissing}, CauseReconciliation, false, 1},
		"echo garbage >> \"$R\"; exit 75":                  {map[string]string{"tests/a.sh": StatusMissing, "tests/b.sh": StatusMissing}, CauseReconciliation, false, 1},
		"printf garbage >> \"$R\"; exit 75":                {map[string]string{"tests/a.sh": StatusMissing, "tests/b.sh": StatusMissing}, CauseReconciliation, false, 1},
		"row tests/a.sh pass; row tests/b.sh skip; exit 0": {map[string]string{"tests/a.sh": StatusPass, "tests/b.sh": StatusSkip}, "", false, 0},
		"row tests/a.sh skip; row tests/b.sh skip; exit 0": {map[string]string{"tests/a.sh": StatusSkip, "tests/b.sh": StatusSkip}, "", false, 2},
		"exit 2": {map[string]string{"tests/a.sh": StatusMissing, "tests/b.sh": StatusMissing}, CauseReconciliation, false, 1},
		"row tests/a.sh pass; row tests/b.sh pass; exit 1": {map[string]string{"tests/a.sh": StatusPass, "tests/b.sh": StatusPass}, CauseReconciliation, false, 1},
		"exit 5": {map[string]string{"tests/a.sh": StatusMissing, "tests/b.sh": StatusMissing}, CauseMechanism, false, 3},
	} {
		rep := runAll(t, batchRepo(t, run))
		rec := rep.Invocations[0]
		if !reflect.DeepEqual(statuses(rep), want.status) || rec.Cause != want.cause || rec.Refused != want.refused || rep.Exit() != want.exit {
			t.Errorf("%q: %v cause=%q refused=%v exit=%d errors=%v", run, statuses(rep), rec.Cause, rec.Refused, rep.Exit(), rec.ProtocolErrors)
		}
		if rec.Refused && rec.Cause != "" {
			t.Errorf("%q: refused with a cause", run)
		}
	}
}

// A runner that writes a duplicate and a foreign row, then hangs: the kill
// path still validates every complete row, keeps the protocol errors and the
// timeout together, and the primary cause is reconciliation.
func TestKilledRunValidatesRows(t *testing.T) {
	r := newRepo(t, map[string]string{"tests/a.sh": "", "tests/b.sh": "", "tests/c.sh": ""})
	put(t, r, "shell", spec{describe: "unit: file\ntimeouts: per_unit",
		list: "tests/a.sh|file|a\ntests/b.sh|file|b\ntests/c.sh|file|c\n",
		run: "start tests/a.sh; row tests/a.sh pass; row tests/a.sh pass; row tests/zzz.sh pass\n" +
			"start tests/b.sh; row tests/b.sh pass; printf '{\"id\":\"tests/c.sh\",\"ev' >> \"$R\"; exec sleep 30"})
	runners(t, r, "max_invocation_s: 1\nrunners:\n  - name: shell\n    timeout_s: 1\n")
	commitAll(t, r)
	rep := runAll(t, r)
	rec := rep.Invocations[0]
	want := map[string]string{"tests/a.sh": StatusError, "tests/b.sh": StatusPass, "tests/c.sh": StatusNotStarted}
	if !reflect.DeepEqual(statuses(rep), want) {
		t.Fatalf("statuses %v", statuses(rep))
	}
	if !rec.Killed || rec.TimedOut != BoundInvocationMax || rec.Cause != CauseReconciliation ||
		!slices.Equal(rec.ProtocolErrors, []string{"duplicate:tests/a.sh", "unregistered_id:tests/zzz.sh"}) || rep.Exit() != 1 {
		t.Fatalf("record %+v exit %d", rec, rep.Exit())
	}
}

// run --all executes a subsumed runner's units only through its full suite;
// the suite's child rows land under their parent.
func TestRunAllSubsumedAndChildren(t *testing.T) {
	r := newRepo(t, map[string]string{"tests/a.sh": "", "tests/b.sh": "", "suite.cfg": ""})
	st := stateOfRepoless(t)
	put(t, r, "shell", spec{describe: "unit: file", list: "tests/a.sh|file|a\ntests/b.sh|file|b\n",
		run: "echo x >> " + st + "/shell.count; for i in $IDS; do row $i pass; done"})
	put(t, r, "full", spec{describe: "unit: suite\nfull: true\nchildren: bash-file-exit", list: "suite.cfg|suite|all\n",
		run: "echo x >> " + st + "/full.count; row suite.cfg pass 30; row tests/a.sh pass 10 suite.cfg; row tests/b.sh pass 20 suite.cfg; exit 0"})
	runners(t, r, "runners:\n  - name: shell\n    bind: ['tests/*.sh']\n    subsumed_by: full\n  - name: full\n")
	commitAll(t, r)
	rep := runAll(t, r)
	if c, _ := os.ReadFile(st + "/full.count"); string(c) != "x\n" {
		t.Fatalf("suite ran %q", c)
	}
	if _, err := os.Stat(st + "/shell.count"); !os.IsNotExist(err) {
		t.Fatal("the subsumed runner ran")
	}
	var kids []string
	for _, res := range rep.Results {
		if res.Child {
			kids = append(kids, res.ID.String()+"<"+res.Parent.String()+":"+res.Status)
		}
	}
	if !slices.Equal(kids, []string{"tests/a.sh<suite.cfg:pass", "tests/b.sh<suite.cfg:pass"}) || rep.Exit() != 0 || rep.Invocations[0].Cause != "" {
		t.Fatalf("children %v exit %d %+v", kids, rep.Exit(), rep.Invocations[0])
	}
	// A suite that exits 0 while one of its child rows fails contradicts
	// itself: exit_mismatch, never a pass.
	put(t, r, "full", spec{describe: "unit: suite\nfull: true", list: "suite.cfg|suite|all\n",
		run: "row suite.cfg pass 30; row tests/a.sh pass 10 suite.cfg; row tests/b.sh fail 20 suite.cfg; exit 0"})
	rep, err := Run(bg, r.Dir, Options{All: true, RunID: "contradiction"})
	if err != nil || rep.Invocations[0].CauseDetail != "exit_mismatch" || rep.Exit() != 1 {
		t.Fatalf("passing suite with a failing child: %v %+v", err, rep)
	}
	// Exit 1 with a passing suite parent and a failing registered child is
	// consistent (no cause) — and the failing child fails the run.
	put(t, r, "full", spec{describe: "unit: suite\nfull: true", list: "suite.cfg|suite|all\n",
		run: "row suite.cfg pass 30; row tests/a.sh pass 10 suite.cfg; row tests/b.sh fail 20 suite.cfg; exit 1"})
	rep, err = Run(bg, r.Dir, Options{All: true, RunID: "child-fails"})
	if err != nil || rep.Invocations[0].Cause != "" || statuses(rep)["suite.cfg"] != StatusPass || rep.Exit() != 1 {
		t.Fatalf("failing child under a passing parent, exit 1: %v %+v exit %d", err, rep.Invocations, rep.Exit())
	}
	// Explicit ids still run the subsumed runner itself.
	rep2, err := Run(bg, r.Dir, Options{IDs: []string{"tests/a.sh"}, RunID: "explicit"})
	if err != nil || statuses(rep2)["tests/a.sh"] != StatusPass {
		t.Fatalf("explicit: %v %v", err, rep2)
	}
}

// Child rows are refused without full: true.
func TestChildRowsNeedFull(t *testing.T) {
	r := batchRepo(t, "row tests/a.sh pass; row tests/b.sh pass; row tests/a.sh pass 1 tests/b.sh; exit 0")
	rep := runAll(t, r)
	if rec := rep.Invocations[0]; rec.Cause != CauseReconciliation || !slices.Equal(rec.ProtocolErrors, []string{"invalid_child:tests/a.sh"}) {
		t.Fatalf("%+v", rec)
	}
}

// A cyclic subsumption plus an unrelated passing runner never yields a
// passing run: Load refuses, so run and check exit 3.
func TestSubsumptionCycleWithPassingRunner(t *testing.T) {
	r := newRepo(t, map[string]string{"tests/a.sh": "", "x.cfg": "", "y.cfg": ""})
	put(t, r, "ok", spec{describe: "unit: file", list: "tests/a.sh|file|a\n", run: "row tests/a.sh pass"})
	put(t, r, "x", spec{describe: "unit: suite\nfull: true", list: "x.cfg|suite|x\n", run: "row x.cfg fail"})
	put(t, r, "y", spec{describe: "unit: suite\nfull: true", list: "y.cfg|suite|y\n", run: "row y.cfg fail"})
	runners(t, r, "runners:\n  - name: ok\n  - name: x\n    subsumed_by: y\n  - name: y\n    subsumed_by: x\n")
	commitAll(t, r)
	_, err := Run(bg, r.Dir, Options{All: true, RunID: "cycle"})
	if err == nil || !strings.Contains(err.Error(), "subsumption cycle x→y→x") {
		t.Fatalf("run: %v", err)
	}
	var le *LineError
	if !errors.As(err, &le) || le.ExitCode() != 3 {
		t.Fatalf("not a framework error: %v", err)
	}
	if _, err := registry.Check(bg, r.Dir, registry.Inputs{Annotations: noAnns{}, Lister: Lister{}}, registry.CheckOptions{}); err == nil {
		t.Fatal("check passed over a subsumption cycle")
	}
}

// A valid chain whose terminal suite selects no unit refuses before
// anything runs.
func TestSubsumptionTerminalSelectsNothing(t *testing.T) {
	st := stateOfRepoless(t)
	for name, files := range map[string]map[string]string{
		"lists nothing": {"tests/a.sh": ""},
		"excluded":      {"tests/a.sh": "", "suite.cfg": "", registry.ConfigPath: "contract: 1\nexclude: ['suite.cfg']\n"},
	} {
		r := newRepo(t, files)
		list := ""
		if name == "excluded" {
			list = "suite.cfg|suite|all\n"
		}
		put(t, r, "shell", spec{describe: "unit: file", list: "tests/a.sh|file|a\n", run: "echo x >> " + st + "/ran"})
		put(t, r, "full", spec{describe: "unit: suite\nfull: true", list: list, run: "echo x >> " + st + "/ran"})
		runners(t, r, "runners:\n  - name: shell\n    subsumed_by: full\n  - name: full\n")
		commitAll(t, r)
		_, err := Run(bg, r.Dir, Options{All: true, RunID: "term"})
		if err == nil || !strings.Contains(err.Error(), "RUN_ERROR:subsumption|shell|terminal full selects no unit") {
			t.Errorf("%s: %v", name, err)
		}
	}
	if _, err := os.Stat(st + "/ran"); !os.IsNotExist(err) {
		t.Fatal("a runner executed")
	}
}

// The built-in serial plan refuses any invocation holding resources, before
// anything runs.
func TestSerialPlanRefusesResources(t *testing.T) {
	st := stateOfRepoless(t)
	r := newRepo(t, map[string]string{"tests/a.sh": "", "tests/b.sh": "#!/bin/sh\n# testmap:needs repo-git-index\n"})
	put(t, r, "shell", spec{describe: "unit: file\ntimeouts: batch", list: "tests/a.sh|file|a\ntests/b.sh|file|b\n", run: "echo x >> " + st + "/ran"})
	runners(t, r, "runners:\n  - name: shell\n    timeout_s: 5\n    batch_timeout_s: 9\n")
	commitAll(t, r)
	_, err := Run(bg, r.Dir, Options{All: true, RunID: "res"})
	if err == nil || !strings.HasPrefix(err.Error(), `RUN_ERROR:scheduler-unavailable|["shell","",["repo-git-index"]`) {
		t.Fatalf("%v", err)
	}
	if _, err := os.Stat(st + "/ran"); !os.IsNotExist(err) {
		t.Fatal("a runner executed")
	}
}

type handleExecutor struct{ seen []string }

func (h *handleExecutor) Execute(ctx context.Context, invs []*Invocation, invoke InvokeFunc) ([]Outcome, error) {
	var out []Outcome
	for _, inv := range invs {
		h.seen = append(h.seen, inv.Key.String())
		inv.Handle = "emulator-5554"
		out = append(out, invoke(ctx, inv))
	}
	return out, nil
}

// A registered executor replaces the serial plan, receives exactly the
// grouping function's invocations, and its allocator handle reaches the
// runner through the manifest.
func TestExecutorSeamAndHandle(t *testing.T) {
	h := &handleExecutor{}
	withExecutor(t, h)
	r := newRepo(t, map[string]string{"tests/a.sh": "#!/bin/sh\n# testmap:needs emulator\n"})
	put(t, r, "dev", spec{describe: "unit: file", list: "tests/a.sh|file|a\n",
		run: "grep -q '\"handle\": \"emulator-5554\"' \"$M\" && row tests/a.sh pass || row tests/a.sh fail"})
	runners(t, r, "runners:\n  - name: dev\n")
	commitAll(t, r)
	rep := runAll(t, r)
	if statuses(rep)["tests/a.sh"] != StatusPass || !slices.Equal(h.seen, []string{`["dev","",["emulator"],"unit","tests/a.sh"]`}) {
		t.Fatalf("%v %v", statuses(rep), h.seen)
	}
}

// Subscribers fire once each, in registration order, after the records are
// written; a failing one does not stop the next.
func TestPostRunHookOrder(t *testing.T) {
	withHooks(t)
	var calls []string
	RegisterPostRunHook("first", func(_ context.Context, rep *RunReport) error {
		calls = append(calls, "first:"+rep.RunID)
		if _, err := os.Stat(filepath.Join(rep.Root, rep.Dir, "inv-001", "record.json")); err != nil {
			t.Errorf("record not written before the hook: %v", err)
		}
		return errors.New("ledger unwritable")
	})
	RegisterPostRunHook("second", func(_ context.Context, rep *RunReport) error {
		calls = append(calls, "second:"+rep.RunID)
		return nil
	})
	rep := runAll(t, batchRepo(t, "row tests/a.sh pass; row tests/b.sh pass"))
	if !slices.Equal(calls, []string{"first:" + rep.RunID, "second:" + rep.RunID}) {
		t.Fatalf("calls %v", calls)
	}
	if len(rep.HookErrors) != 1 || rep.HookErrors[0].Hook != "first" {
		t.Fatalf("hook errors %v", rep.HookErrors)
	}
	defer func() {
		if recover() == nil {
			t.Error("a duplicate hook name did not panic")
		}
	}()
	RegisterPostRunHook("first", nil)
}

func TestRunErrors(t *testing.T) {
	if _, err := Run(bg, t.TempDir(), Options{All: true}); !errors.Is(err, registry.ErrAbsent) {
		t.Errorf("no registry: %v", err)
	}
	r := batchRepo(t, "row tests/a.sh pass; row tests/b.sh pass")
	if _, err := Run(bg, r.Dir, Options{IDs: []string{"tests/nope.sh"}, RunID: "u"}); err == nil || !strings.Contains(err.Error(), "unknown-id|tests/nope.sh") {
		t.Errorf("unknown id: %v", err)
	}
	if _, err := Run(bg, r.Dir, Options{All: true, RunID: "bad/id"}); err == nil {
		t.Error("bad run id accepted")
	}
	if _, err := Run(bg, r.Dir, Options{All: true, RunID: "same"}); err != nil {
		t.Fatal(err)
	}
	if _, err := Run(bg, r.Dir, Options{All: true, RunID: "same"}); err == nil || !strings.Contains(err.Error(), "run-exists|same") {
		t.Errorf("reused run id: %v", err)
	}
	t.Setenv("AIT_GATE_RUN_ID", "gate-42")
	rep, err := Run(bg, r.Dir, Options{All: true})
	if err != nil || rep.RunID != "gate-42" {
		t.Errorf("AIT_GATE_RUN_ID: %v %v", rep, err)
	}
	empty := newRepo(t, nil)
	runners(t, empty, "runners: []\n")
	if rep, err := Run(bg, empty.Dir, Options{All: true, RunID: "e"}); err != nil || rep.Exit() != 2 {
		t.Errorf("nothing selected: %v %v", rep, err)
	}
}

// stateOfRepoless is a scratch directory for counters and pid files.
func stateOfRepoless(t *testing.T) string { return t.TempDir() }

// A report path holding anything but a bounded regular file — a FIFO, a
// symbolic link, a directory, an oversized file — is a protocol error read
// without blocking or growing, for results.jsonl and runner.json alike; the
// run returns promptly instead of hanging past its deadline.
func TestRunReportFilesAreSafe(t *testing.T) {
	old := resultsMax
	resultsMax = 4096
	t.Cleanup(func() { resultsMax = old })
	rows := "row tests/a.sh pass; row tests/b.sh pass; "
	runnerJSON := `RJ=$(sed -n 's/^  "runner_json": "\(.*\)",$/\1/p' "$M"); [ -n "$RJ" ] || exit 9; `
	for name, tc := range map[string]struct{ run, err string }{
		"results fifo":      {`rm -f "$R"; mkfifo "$R"; exit 0`, "report:results.jsonl:not a regular file (p---------)"},
		"results symlink":   {`ln -s /etc/hostname "$R"; exit 0`, "report:results.jsonl:a symbolic link"},
		"results directory": {`mkdir "$R"; exit 0`, "report:results.jsonl:not a regular file (d---------)"},
		"results oversized": {rows + `head -c 5000 /dev/zero | tr '\0' ' ' >> "$R"; exit 0`, "report:results.jsonl:exceeds 4096 bytes"},
		"runner.json fifo":  {rows + runnerJSON + `mkfifo "$RJ"; exit 0`, "report:runner.json:not a regular file (p---------)"},
		"runner.json bad":   {rows + runnerJSON + `echo '{"overhead":[],"x":1}' > "$RJ"; exit 0`, "report:runner.json:json: unknown field \"x\""},
	} {
		start := time.Now()
		rep := runAll(t, batchRepo(t, tc.run))
		if d := time.Since(start); d > 10*time.Second {
			t.Fatalf("%s: run took %v", name, d)
		}
		rec := rep.Invocations[0]
		if rec.Cause != CauseReconciliation || !slices.Contains(rec.ProtocolErrors, tc.err) || rep.Exit() != 1 {
			t.Errorf("%s: %+v", name, rec)
		}
	}
}
