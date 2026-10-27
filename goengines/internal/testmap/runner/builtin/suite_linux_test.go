//go:build linux

package builtin

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/cost"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

// The suite builtin's tests (G10): its command runs under GNU bash >= 4.4 on
// linux, the supported configuration, so the real-tool tests require bash
// (requireBash: a skip, or a failure under AIT_TESTMAP_REQUIRE_REAL_TOOLS=1).
// They reuse the bash-file tests' environment (AIT_TEST_STATE, AIT_TEST_ENGINE,
// AIT_TEST_OTHER) and their __nested_engine.

// suiteEntry is a runners.yaml entry for a suite runner; command "" leaves
// command: out. extra lines are appended verbatim.
func suiteEntry(name, command string, extra ...string) string {
	s := "  - name: " + name + "\n    builtin: suite\n"
	if command != "" {
		s += "    command: '" + strings.ReplaceAll(command, "'", "''") + "'\n"
	}
	if !slices.ContainsFunc(extra, func(x string) bool { return strings.HasPrefix(x, "timeout_s:") }) {
		s += "    timeout_s: 30\n"
	}
	for _, x := range extra {
		s += "    " + x + "\n"
	}
	return s
}

// suiteRepo is newRepo with the given runners, and requires bash.
func suiteRepo(t *testing.T, files map[string]string, runners string) (*fixture.Repo, string) {
	t.Helper()
	requireBash(t)
	return newRepo(t, files, runners)
}

func suiteID(name string) string { return runner.RunnersPath + "#" + name }

// The describe document: the fixed classes, the rules as comments, and a
// required command.
func TestSuiteDescribe(t *testing.T) {
	b, err := suiteDescribe(&Env{Command: "make test"})
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
	if d.Unit != "suite" || d.Accounting != runner.AccountingAggregate || d.Discovery != runner.DiscoveryInventory || d.Timeouts != runner.TimeoutsNone || d.Full || d.Children != "" {
		t.Fatalf("describe %+v", d)
	}
	for _, s := range []string{"bash -c <command:>", "exited 0", "ever inferred from it", "never anchors", "aitestmap/runners.yaml#<name>", "takes no bind:", "may not be overridden", "never run here", "GNU bash >= 4.4 on linux", "darwin is pending", "unit-<n>.stdout"} {
		if !strings.Contains(string(b), s) {
			t.Errorf("describe docs do not state %q", s)
		}
	}
	for _, c := range []string{"", "  \t"} {
		if _, err := suiteDescribe(&Env{Command: c}); err == nil || !strings.Contains(err.Error(), "command: is required") {
			t.Errorf("command %q: %v", c, err)
		}
	}
}

// The early recursion diagnostic: the words that name the test front, on
// their basename, through shell operators and quotes.
func TestSuiteRecursionWord(t *testing.T) {
	for cmd, want := range map[string]string{
		"./ait test":                          "./ait",
		"ait test --all":                      "ait",
		"/x/ait testmap run":                  "/x/ait",
		"ait testmap test":                    "ait",
		"ait-testmap test":                    "ait-testmap",
		"../bin/ait-testmap run --all":        "../bin/ait-testmap",
		"bash .aitask-scripts/aitask_test.sh": ".aitask-scripts/aitask_test.sh",
		"make && ./ait test":                  "./ait",
		"cd x;ait test":                       "ait",
		"(ait test)":                          "ait",
		`"./ait" test`:                        "./ait",
		"echo $(./ait test)":                  "./ait",
		"x=`ait-testmap run`":                 "ait-testmap",
		"true | 'ait' 'test'":                 "ait",
		"go test ./... || ./ait testmap test": "./ait",
	} {
		if got, ok := suiteRecursionWord(cmd); !ok || got != want {
			t.Errorf("%q: %q %v, want %q", cmd, got, ok, want)
		}
	}
	for _, cmd := range []string{"go test ./...", "pytest -q", "./gradlew test", "ait testmap check", "ait-testmap scan", "./ait board", "bash tests/aitask_test.sh.bak", "waittest", "ait", "ait testmap"} {
		if got, ok := suiteRecursionWord(cmd); ok {
			t.Errorf("%q refused as %q", cmd, got)
		}
	}
}

// The diagnostic's line reaches the engine intact: written first on the
// builtin's stderr, ahead of BUILTIN_ERROR (whose detail loses its '|').
func TestSuiteRecursionDiagnostic(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	c := exec.Command(exe, "runner", suiteName, "describe")
	c.Env = append(os.Environ(), "AIT_TESTMAP_COMMAND=./ait test", "AIT_TESTMAP_RUNNER=full")
	var out, errb bytes.Buffer
	c.Stdout, c.Stderr = &out, &errb
	err = c.Run()
	var ee *exec.ExitError
	if !errors.As(err, &ee) || ee.ExitCode() != 3 || out.Len() != 0 {
		t.Fatalf("describe: %v stdout %q stderr %q", err, out.String(), errb.String())
	}
	if first, _, _ := strings.Cut(errb.String(), "\n"); first != "SUITE_RECURSION:full|./ait" {
		t.Fatalf("first stderr line %q (stderr %q)", first, errb.String())
	}
	r, _ := suiteRepo(t, nil, suiteEntry("full", "make check && ./ait test"))
	loadErr(t, r, "RUNNER_PROTOCOL:full|describe|exit 3: SUITE_RECURSION:full|./ait")
}

// One unit per entry, kind suite, with no member drift; loading runs
// neither the command nor the fallback_command.
func TestSuiteInventory(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, st := suiteRepo(t, map[string]string{"sub/README": "x\n"},
		suiteEntry("full", `touch "$AIT_TEST_STATE/full.ran"`, `fallback_command: touch "$AIT_TEST_STATE/fb.ran"`)+
			suiteEntry("sub", `touch "$AIT_TEST_STATE/sub.ran"`, "cwd: sub"))
	ctx := context.Background()
	repo, err := runner.Load(ctx, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	var units []string
	for _, u := range repo.Units {
		units = append(units, u.ID.String()+"="+u.Kind+":"+u.Lowering+":"+strconv.FormatBool(u.BatchNo))
	}
	if want := []string{suiteID("full") + "=suite:full:true", suiteID("sub") + "=suite:sub:true"}; !slices.Equal(units, want) {
		t.Fatalf("units %v, want %v", units, want)
	}
	rcfg, err := registry.LoadConfig(r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	anns, err := annot.Source{}.Annotations(ctx, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	if _, findings := registry.BuildScanned(rcfg, anns, repo.Listings()); len(findings) != 0 {
		t.Fatalf("member drift: %+v", findings)
	}
	for _, f := range []string{"full.ran", "sub.ran", "fb.ran"} {
		if _, err := os.Stat(filepath.Join(st, f)); err == nil {
			t.Errorf("%s exists: loading ran a command", f)
		}
	}
}

// The list refuses, never silently loses, a suite unit the engine would not
// run: a bind: on the suite, another runner's binding of runners.yaml, an
// exclude: of it; and a suite without a command.
func TestSuiteInventoryRefusals(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	for _, tc := range []struct {
		name, runners, config, want string
	}{
		{"own bind", suiteEntry("s", "true", "bind: ['tests/**']"), "", "a suite runner takes no bind:"},
		{"foreign bind", bashEntry("b", "aitestmap/**") + suiteEntry("s", "true"), "", "runner b's bind: aitestmap/** matches aitestmap/runners.yaml"},
		{"exclude", suiteEntry("s", "true"), "contract: 1\nexclude: ['aitestmap/**']\n", "exclude: drops aitestmap/runners.yaml"},
		{"no command", suiteEntry("s", ""), "", "command: is required"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			files := map[string]string{}
			if tc.config != "" {
				files[registry.ConfigPath] = tc.config
			}
			r, _ := suiteRepo(t, files, tc.runners)
			loadErr(t, r, "RUNNER_PROTOCOL:s|", tc.want)
		})
	}
}

// The fixed contract: unit, accounting, discovery and timeouts cannot be
// overridden to another value (the refusal names the key, whichever layer
// gives it); every other key, and a redundant override, loads as an
// aggregate. On a clean tree the aggregate result is still no anchor.
func TestSuiteFixedContractOverrides(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	for _, tc := range []struct{ extra, key string }{
		{"accounting: unit", "accounting"},
		{"accounting: cases", "accounting"},
		{"timeouts: per_unit", "timeouts"},
		{"timeouts: batch\n    batch_timeout_s: 5", "timeouts"},
		{"unit: file", "unit"},
		{"discovery: native", "discovery"},
		{"discovery: candidates", "discovery"},
	} {
		t.Run("refused "+tc.extra, func(t *testing.T) {
			r, _ := suiteRepo(t, nil, suiteEntry("s", "true", tc.extra))
			loadErr(t, r, "RUNNER_PROTOCOL:s|list|", tc.key, "fixed at")
		})
	}
	for _, extra := range []string{"accounting: aggregate\n    timeouts: none\n    unit: suite\n    discovery: inventory", "full: true", "needs: [gpu]", "batch: false", "group_by: dir", "filter_scope: whole_run"} {
		t.Run("accepted "+extra, func(t *testing.T) {
			r, _ := suiteRepo(t, nil, suiteEntry("s", "true", extra))
			repo, err := runner.Load(context.Background(), r.Dir)
			if err != nil {
				t.Fatal(err)
			}
			d := repo.Runner("s").Describe
			if len(repo.Units) != 1 || repo.Units[0].Kind != "suite" || d.Accounting != runner.AccountingAggregate || d.Discovery != runner.DiscoveryInventory || d.Timeouts != runner.TimeoutsNone || d.Unit != "suite" {
				t.Fatalf("units %+v describe %+v", repo.Units, d)
			}
		})
	}
	t.Run("effective accounting", func(t *testing.T) {
		r, _ := suiteRepo(t, nil, suiteEntry("s", "true"))
		var buf bytes.Buffer
		err := suiteList(context.Background(), &Env{Root: r.Dir, Runner: "s", Command: "true", Accounting: runner.AccountingUnit}, &buf)
		if err == nil || !strings.Contains(err.Error(), `effective accounting is "unit"`) || buf.Len() != 0 {
			t.Fatalf("list: %v rows %q", err, buf.String())
		}
	})
	t.Run("never an anchor", func(t *testing.T) {
		r, _ := suiteRepo(t, nil, suiteEntry("s", "true", "full: true"))
		rep := run(t, r, "anchor")
		status(t, rep, suiteID("s"), runner.StatusPass, "")
		if rec := record(t, rep, "s"); len(rec.Modified) != 0 || rec.HeadStart == "" {
			t.Fatalf("not a clean tree: %+v", rec)
		}
		batch, err := cost.Rows(context.Background(), rep)
		if err != nil {
			t.Fatal(err)
		}
		var rows []cost.ResultRow
		for line := range bytes.SplitSeq(bytes.TrimSpace(batch), []byte{'\n'}) {
			var row cost.ResultRow
			if err := json.Unmarshal(line, &row); err != nil {
				t.Fatal(err)
			}
			if row.Row == "result" {
				rows = append(rows, row)
			}
		}
		if len(rows) != 1 || rows[0].ID != suiteID("s") || rows[0].Anchor || rows[0].AnchorReason != "opaque:aggregate" || rows[0].Accounting != runner.AccountingAggregate {
			t.Fatalf("result rows %+v", rows)
		}
	})
}

// The command's exit is the unit's result; the run is contained and
// aggregate-accounted, and its output is in the unit's logs.
func TestSuitePassFail(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := suiteRepo(t, nil, suiteEntry("ok", "echo out; echo err >&2; exit 0")+suiteEntry("bad", "exit 3")+suiteEntry("sig", "kill -USR1 $$"))
	rep := run(t, r, "passfail")
	status(t, rep, suiteID("ok"), runner.StatusPass, "")
	status(t, rep, suiteID("bad"), runner.StatusFail, "exit 3")
	status(t, rep, suiteID("sig"), runner.StatusFail, "signal ")
	for _, name := range []string{"ok", "bad", "sig"} {
		rec := record(t, rep, name)
		if rec.Cause != "" || rec.Containment != procsup.Supervisor || rec.Accounting != runner.AccountingAggregate || rec.Discovery != runner.DiscoveryInventory || rec.UnitsStarted != 1 || rec.Timeouts != runner.TimeoutsNone {
			t.Fatalf("record %+v", rec)
		}
	}
	if a := rep.Accounting; a.Selected != 3 || a.Aggregate != 3 || a.Cases != 0 || a.Unit != 0 || a.Unaccounted != 0 {
		t.Fatalf("accounting %+v", a)
	}
	if out, errs := unitLog(t, rep, suiteID("ok"), "stdout"), unitLog(t, rep, suiteID("ok"), "stderr"); out != "out\n" || errs != "err\n" {
		t.Fatalf("logs %q %q", out, errs)
	}
}

// The command runs under bash, not POSIX sh: bash invoked as sh (this host's
// /bin/sh) sets posix mode, and dash has neither [[ ]] nor pipefail.
func TestSuiteBashSemantics(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := suiteRepo(t, nil, suiteEntry("b", `[[ 1 == 1 ]] && [ -n "$BASH_VERSION" ] && ! shopt -qo posix`)+suiteEntry("p", "set -o pipefail; false | true"))
	rep := run(t, r, "bash")
	status(t, rep, suiteID("b"), runner.StatusPass, "")
	status(t, rep, suiteID("p"), runner.StatusFail, "exit 1")
}

// The command runs in the entry's cwd.
func TestSuiteRunsInCwd(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, st := suiteRepo(t, map[string]string{"sub/README": "x\n"}, suiteEntry("s", `pwd -P > "$AIT_TEST_STATE/pwd"`, "cwd: sub"))
	rep := run(t, r, "cwd")
	status(t, rep, suiteID("s"), runner.StatusPass, "")
	want, err := filepath.EvalSymlinks(filepath.Join(r.Dir, "sub"))
	if err != nil {
		t.Fatal(err)
	}
	if got := readState(t, st, "pwd"); got != want {
		t.Fatalf("cwd %q, want %q", got, want)
	}
}

// Over timeout_s the engine kills the invocation and attributes `timeout`;
// a setsid daemon the command left is gone when the run returns.
func TestSuiteTimeoutKillsSetsidDescendant(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, st := suiteRepo(t, nil, suiteEntry("slow", `setsid sh -c 'echo $$ > "$AIT_TEST_STATE/sid.tmp"; mv "$AIT_TEST_STATE/sid.tmp" "$AIT_TEST_STATE/sid.pid"; exec sleep 300' & `+
		`for i in $(seq 1 1000); do [ -s "$AIT_TEST_STATE/sid.pid" ] && break; sleep 0.01; done; sleep 300`, "timeout_s: 3"))
	rep := run(t, r, "timeout")
	res := result(t, rep, suiteID("slow"))
	if res.Status != runner.StatusTimeout || !res.Started {
		t.Fatalf("result %+v", res)
	}
	if rec := record(t, rep, "slow"); !rec.Killed || rec.TimedOut != runner.BoundUnit {
		t.Fatalf("record %+v", rec)
	}
	p, err := strconv.Atoi(readState(t, st, "sid.pid"))
	if err != nil {
		t.Fatal(err)
	}
	if alive(p) {
		t.Fatalf("the setsid daemon %d survived the timeout", p)
	}
}

// Output goes to the unit's log, never to the builtin's capped stdout: past
// the log cap the unit still passes, the log is truncated and said so, and
// the invocation is not a mechanism failure.
func TestSuiteOutputPastCap(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := suiteRepo(t, nil, suiteEntry("big", "head -c "+strconv.FormatInt(procsup.DefaultOutputMax+4096, 10)+" /dev/zero; echo tail >&2; exit 0"))
	rep := run(t, r, "big")
	status(t, rep, suiteID("big"), runner.StatusPass, "log truncated")
	rec := record(t, rep, "big")
	if rec.Cause != "" || len(rec.ProtocolErrors) != 0 {
		t.Fatalf("record %+v", rec)
	}
	fi, err := os.Stat(filepath.Join(rec.ReportDir, "unit-0000.stdout"))
	if err != nil || fi.Size() != procsup.DefaultOutputMax {
		t.Fatalf("stdout log: %v %v", fi, err)
	}
	if e := unitLog(t, rep, suiteID("big"), "stderr"); e != "tail\n" {
		t.Fatalf("stderr log %q", e)
	}
}

// A nested run of the same repository, reached through a script the
// diagnostic cannot see, is refused at runtime through the recursion marker;
// the same nested run of another repository succeeds.
func TestSuiteRecursionThroughExecution(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	other, _ := suiteRepo(t, nil, suiteEntry("o", "exit 0"))
	nest := "cd \"$1\" && exec \"$AIT_TEST_ENGINE\" " + nestedEngineArg + " run\n"
	r, _ := suiteRepo(t, map[string]string{"tests/hidden.sh": nest},
		suiteEntry("self", `bash tests/hidden.sh "$AIT_TESTMAP_ROOT"`)+suiteEntry("other", `bash tests/hidden.sh "$AIT_TEST_OTHER"`))
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("AIT_TEST_ENGINE", exe)
	t.Setenv("AIT_TEST_OTHER", other.Dir)
	rep := run(t, r, "nest")
	status(t, rep, suiteID("self"), runner.StatusFail, "exit 3")
	self := unitLog(t, rep, suiteID("self"), "stderr")
	if !strings.Contains(self, "RUN_ERROR:recursion|") || !slices.Contains(strings.Split(self, "\n"), "VIA:marker") {
		t.Fatalf("self-nested run: %q", self)
	}
	status(t, rep, suiteID("other"), runner.StatusPass, "")
	if o := unitLog(t, rep, suiteID("other"), "stderr"); !strings.Contains(o, "NESTED_OK:0") {
		t.Fatalf("nested run on another repository: %q", o)
	}
}

// A full: true suite runs without child rows: the subsumed runner's units
// are unaccounted, never implicitly covered. children: needs a registered
// reporting contract.
func TestSuiteFullWithoutChildren(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := suiteRepo(t, map[string]string{"tests/test_a.sh": "exit 0\n", "tests/test_b.sh": "exit 0\n"},
		suiteEntry("full", "exit 0", "full: true")+bashEntry("b", "tests/test_*.sh", "subsumed_by: full"))
	rep := run(t, r, "full")
	status(t, rep, suiteID("full"), runner.StatusPass, "")
	for _, res := range rep.Results {
		if res.Child {
			t.Fatalf("child row %+v", res)
		}
	}
	if a := rep.Accounting; a.Selected != 1 || a.Aggregate != 1 || a.Unaccounted != 2 {
		t.Fatalf("accounting %+v", a)
	}
	c, _ := suiteRepo(t, nil, suiteEntry("full", "exit 0", "full: true", "children: junit"))
	loadErr(t, c, "RUNNER_INVALID:full|", "not a registered reporting contract")
}

// A command that writes case evidence into the report directory cannot turn
// the aggregate into case accounting: the cases file is refused, and the
// refusal fails the run.
func TestSuiteCasesFileRefused(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	r, _ := suiteRepo(t, nil, suiteEntry("s", `printf '{"unit":"x","case":"c","status":"pass","duration_ms":1}\n' > "$AIT_TESTMAP_REPORT_DIR/cases.jsonl"`))
	rep := run(t, r, "cases")
	// The unit row is the command's; the refusal is the invocation's cause
	// (t1854_2), which fails the run and, being a cause, rules out an anchor.
	if res := result(t, rep, suiteID("s")); res.Cases != nil || rep.Exit() != 1 {
		t.Fatalf("result %+v exit %d", res, rep.Exit())
	}
	if rec := record(t, rep, "s"); rec.Cause != "reconciliation" || !strings.HasPrefix(rec.CauseDetail, "cases:refused:") || !slices.ContainsFunc(rec.ProtocolErrors, func(e string) bool { return strings.HasPrefix(e, "cases:refused") }) {
		t.Fatalf("record %+v", rec)
	}
}

// Where containment is unavailable the production suite refuses before
// doing anything.
func TestSuiteContainmentUnavailable(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	t.Setenv("AIT_TESTMAP_COMMAND", "true")
	defer procsup.SetUnavailableForTesting()()
	for _, verb := range []string{"describe", "list"} {
		var out, errb bytes.Buffer
		if code := Main([]string{suiteName, verb}, &out, &errb); code != 3 || errb.String() != "CONTAINMENT_UNAVAILABLE:linux\n" || out.Len() != 0 {
			t.Fatalf("%s: code %d stdout %q stderr %q", verb, code, out.String(), errb.String())
		}
	}
}

// A manifest the suite's contract cannot have produced is refused unit by
// unit, and nothing runs; a valid one runs the command (the control).
func TestSuiteRunRefusesForgedUnit(t *testing.T) {
	if !hangguard.Isolated(t, bashHangLimit) {
		return
	}
	requireBash(t)
	good := runner.ManifestUnit{ID: suiteID("s"), Lowering: "s", TimeoutS: 30}
	for _, tc := range []struct {
		name                 string
		timeouts, accounting string
		units                []runner.ManifestUnit
		want                 string
	}{
		{"two units", runner.TimeoutsNone, runner.AccountingAggregate, []runner.ManifestUnit{good, {ID: suiteID("t"), Lowering: "t", TimeoutS: 30}}, "2 units"},
		{"wrong id", runner.TimeoutsNone, runner.AccountingAggregate, []runner.ManifestUnit{{ID: suiteID("other"), Lowering: "s", TimeoutS: 30}}, "is not this runner's"},
		{"wrong lowering", runner.TimeoutsNone, runner.AccountingAggregate, []runner.ManifestUnit{{ID: suiteID("s"), Lowering: "x", TimeoutS: 30}}, "is not this runner's"},
		{"per_unit", runner.TimeoutsPerUnit, runner.AccountingAggregate, []runner.ManifestUnit{good}, "timeouts is fixed at none"},
		{"unit accounting", runner.TimeoutsNone, runner.AccountingUnit, []runner.ManifestUnit{good}, "accounting is fixed at aggregate"},
		{"valid", runner.TimeoutsNone, runner.AccountingAggregate, []runner.ManifestUnit{good}, ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			d := t.TempDir()
			if err := os.MkdirAll(filepath.Join(d, filepath.Dir(runner.RunnersPath)), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(d, runner.RunnersPath), []byte("contract: 1\nrunners:\n"+suiteEntry("s", "true")), 0o644); err != nil {
				t.Fatal(err)
			}
			marker := filepath.Join(d, "ran")
			m := &runner.Manifest{Results: filepath.Join(d, "results.jsonl"), ReportDir: d, Timeouts: tc.timeouts, Accounting: tc.accounting, Units: tc.units}
			res, err := OpenResults(m)
			if err != nil {
				t.Fatal(err)
			}
			code := suiteRun(context.Background(), &Env{Root: d, Runner: "s", Command: "touch '" + marker + "'"}, m, res)
			if err := res.Close(); err != nil {
				t.Fatal(err)
			}
			b, err := os.ReadFile(m.Results)
			if err != nil {
				t.Fatal(err)
			}
			_, statErr := os.Stat(marker)
			if tc.want == "" {
				if code != 0 || statErr != nil || !strings.Contains(string(b), `"status":"pass"`) {
					t.Fatalf("control: code %d marker %v rows %s", code, statErr, b)
				}
				return
			}
			if code != 1 || statErr == nil || strings.Contains(string(b), `"event":"start"`) || strings.Count(string(b), `"status":"error"`) != len(tc.units) || !strings.Contains(string(b), "protocol:") || !strings.Contains(string(b), tc.want) {
				t.Fatalf("code %d marker %v rows %s", code, statErr, b)
			}
		})
	}
}
