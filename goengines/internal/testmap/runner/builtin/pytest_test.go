//go:build unix

package builtin

import (
	"os"
	"path/filepath"
	"slices"
	"strings"
	"syscall"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

// The pytest builtin's pure tests: no process starts, so none is guarded and
// none references the adapter's verbs.

// evidenceLines joins records into an evidence file.
func evidenceLines(recs ...string) []byte { return []byte(strings.Join(recs, "\n") + "\n") }

const (
	evSession = `{"k":"session","v":1,"rootdir":"/r","pytest":"8.4.2","python":"3.12.1","impl":"CPython"}`
	evItems   = `{"k":"items","nodeids":["tests/test_a.py::t"]}`
	evEnd0    = `{"k":"end","exitstatus":0}`
)

// The evidence parse is strict, and mode-specific about the items record.
func TestPytestParseEvidence(t *testing.T) {
	test := `{"k":"test","nodeid":"tests/test_a.py::t","when":"call","outcome":"passed","xfail":null,"message":"","duration":0.25}`
	for _, tc := range []struct {
		name string
		data []byte
		mode int
		exit int
		want string // "" = accepted; else a substring of the error
	}{
		{"discovery ok", evidenceLines(evSession, evItems, evEnd0), pytestDiscovery, 0, ""},
		{"discovery empty items", evidenceLines(evSession, `{"k":"items","nodeids":[]}`, `{"k":"end","exitstatus":5}`), pytestDiscovery, 5, ""},
		{"discovery without items", evidenceLines(evSession, evEnd0), pytestDiscovery, 0, "no items record"},
		{"execution without items", evidenceLines(evSession, test, evEnd0), pytestExecution, 0, ""},
		{"items twice", evidenceLines(evSession, evItems, evItems, evEnd0), pytestDiscovery, 0, "a second items record"},
		{"items null", evidenceLines(evSession, `{"k":"items","nodeids":null}`, evEnd0), pytestDiscovery, 0, `"nodeids" is null`},
		{"exit status null", evidenceLines(evSession, evItems, `{"k":"end","exitstatus":null}`), pytestDiscovery, 0, `"exitstatus" is null`},
		{"message null", evidenceLines(evSession, `{"k":"test","nodeid":"x","when":"call","outcome":"skipped","xfail":null,"message":null,"duration":0}`, evEnd0), pytestExecution, 0, `"message" is null`},
		{"nodeid null", evidenceLines(evSession, `{"k":"test","nodeid":null,"when":"call","outcome":"passed","xfail":null,"message":"","duration":0}`, evEnd0), pytestExecution, 0, `"nodeid" is null`},
		{"duration null", evidenceLines(evSession, `{"k":"test","nodeid":"x","when":"call","outcome":"passed","xfail":null,"message":"","duration":null}`, evEnd0), pytestExecution, 0, `"duration" is null`},
		{"rootdir null", evidenceLines(strings.Replace(evSession, `"rootdir":"/r"`, `"rootdir":null`, 1), evItems, evEnd0), pytestDiscovery, 0, `"rootdir" is null`},
		{"version null", evidenceLines(strings.Replace(evSession, `"v":1`, `"v":null`, 1), evItems, evEnd0), pytestDiscovery, 0, `"v" is null`},
		{"collect message null", evidenceLines(evSession, `{"k":"collect","nodeid":"x","outcome":"skipped","message":null}`, evItems, evEnd0), pytestDiscovery, 0, `"message" is null`},
		{"xfail null is allowed", evidenceLines(evSession, `{"k":"test","nodeid":"x","when":"call","outcome":"skipped","xfail":null,"message":"why","duration":0}`, evEnd0), pytestExecution, 0, ""},
		{"xfail empty reason is allowed", evidenceLines(evSession, `{"k":"test","nodeid":"x","when":"call","outcome":"skipped","xfail":"","message":"","duration":0}`, evEnd0), pytestExecution, 0, ""},
		{"no session", evidenceLines(evItems, evEnd0), pytestDiscovery, 0, "out of place"},
		{"no end", evidenceLines(evSession, evItems), pytestDiscovery, 0, "out of place"},
		{"two ends", evidenceLines(evSession, evItems, evEnd0, evEnd0), pytestDiscovery, 0, "out of place"},
		{"two sessions", evidenceLines(evSession, evSession, evItems, evEnd0), pytestDiscovery, 0, "out of place"},
		{"exit mismatch", evidenceLines(evSession, evItems, evEnd0), pytestDiscovery, 1, "exited 1 but recorded exit status 0"},
		{"truncated last line", []byte(evSession + "\n" + evItems + "\n{\"k\":\"end\""), pytestDiscovery, 0, "incomplete"},
		{"empty", nil, pytestDiscovery, 0, "empty"},
		{"invalid json", evidenceLines(evSession, `{"k":"items",`, evEnd0), pytestDiscovery, 0, "line 2"},
		{"unknown kind", evidenceLines(evSession, `{"k":"warning"}`, evItems, evEnd0), pytestDiscovery, 0, "unknown record"},
		{"unknown member", evidenceLines(evSession, `{"k":"items","nodeids":[],"extra":1}`, evEnd0), pytestDiscovery, 0, "extra"},
		{"foreign member on a kind", evidenceLines(evSession, `{"k":"items","nodeids":[],"when":"call"}`, evEnd0), pytestDiscovery, 0, "members"},
		{"missing member", evidenceLines(evSession, `{"k":"test","nodeid":"x","when":"call","outcome":"passed","message":"","duration":0}`, evEnd0), pytestExecution, 0, "xfail"},
		{"repeated member", evidenceLines(evSession, `{"k":"items","nodeids":[],"nodeids":["x"]}`, evEnd0), pytestDiscovery, 0, "repeated"},
		{"unpaired surrogate", evidenceLines(evSession, `{"k":"items","nodeids":["tests/x.py::t\ud800"]}`, evEnd0), pytestDiscovery, 0, "surrogate"},
		{"bad version", evidenceLines(strings.Replace(evSession, `"v":1`, `"v":2`, 1), evItems, evEnd0), pytestDiscovery, 0, "version 2"},
		{"bad collect outcome", evidenceLines(evSession, `{"k":"collect","nodeid":"x","outcome":"passed","message":""}`, evItems, evEnd0), pytestDiscovery, 0, "collect outcome"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			ev, err := pytestParseEvidence(tc.data, tc.mode, tc.exit)
			switch {
			case tc.want == "" && err != nil:
				t.Fatalf("refused: %v", err)
			case tc.want != "" && err == nil:
				t.Fatalf("accepted %+v, want an error containing %q", ev, tc.want)
			case tc.want != "" && !strings.Contains(err.Error(), tc.want):
				t.Fatalf("error %q, want it to contain %q", err, tc.want)
			}
		})
	}
	ev, err := pytestParseEvidence(evidenceLines(evSession, `{"k":"collect","nodeid":"tests/test_s.py","outcome":"skipped","message":"why"}`, test, `{"k":"end","exitstatus":1}`), pytestExecution, 1)
	if err != nil {
		t.Fatal(err)
	}
	if ev.Rootdir != "/r" || ev.Pytest != "8.4.2" || len(ev.Collect) != 1 || ev.Collect[0].Message != "why" || len(ev.Tests) != 1 || ev.Tests[0].DurationMS != 250 || ev.Tests[0].XFail != nil {
		t.Fatalf("parsed %+v", ev)
	}
}

// Discovery's evidence is read capped, refused past the cap before any
// decoding, never through a link; an absent file is empty.
func TestPytestReadOwn(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "evidence.jsonl")
	if b, err := pytestReadOwn(p, 16); err != nil || b != nil {
		t.Fatalf("absent: %q, %v", b, err)
	}
	if err := os.WriteFile(p, []byte("0123456789abcdef"), 0o644); err != nil {
		t.Fatal(err)
	}
	if b, err := pytestReadOwn(p, 16); err != nil || string(b) != "0123456789abcdef" {
		t.Fatalf("at the cap: %q, %v", b, err)
	}
	if b, err := pytestReadOwn(p, 15); err == nil || !strings.Contains(err.Error(), "larger than 15 bytes") {
		t.Fatalf("past the cap: %d bytes, %v", len(b), err)
	}
	link := filepath.Join(dir, "link.jsonl")
	if err := os.Symlink(p, link); err != nil {
		t.Fatal(err)
	}
	if _, err := pytestReadOwn(link, 16); err == nil {
		t.Fatal("a symbolic link was read")
	}
	if _, err := pytestReadOwn(dir, 16); err == nil {
		t.Fatal("a directory was read")
	}
	// A FIFO with no writer is refused at once: opening it must not block
	// (the bound is the test's, so a regression fails here, not by hanging).
	fifo := filepath.Join(dir, "fifo.jsonl")
	if err := syscall.Mkfifo(fifo, 0o644); err != nil {
		t.Fatal(err)
	}
	done := make(chan error, 1)
	go func() { _, err := pytestReadOwn(fifo, 16); done <- err }()
	select {
	case err := <-done:
		if err == nil || !strings.Contains(err.Error(), "not a regular file") {
			t.Fatalf("a FIFO: %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("reading a writer-less FIFO blocked")
	}
}

// fakeFiles is a pytestFiles over a real temporary rootdir: R = C, and the
// given cwd-relative argument files.
func fakeFiles(t *testing.T, args ...string) (*pytestFiles, string) {
	t.Helper()
	dir := t.TempDir()
	pf, err := newPytestFiles(dir, dir, args)
	if err != nil {
		t.Fatal(err)
	}
	return pf, dir
}

func strp(s string) *string { return &s }

// Every phase that did not pass is its own verdict, the call phase always
// is one, and nothing is merged.
func TestPytestRows(t *testing.T) {
	pf, _ := fakeFiles(t, "tests/test_a.py", "tests/test_s.py", "tests/test_b.py")
	tr := func(id, when, outcome string, xfail *string, msg string) pytestTestRec {
		return pytestTestRec{NodeID: "tests/test_a.py::" + id, When: when, Outcome: outcome, XFail: xfail, Message: msg, DurationMS: 7}
	}
	ev := &pytestEvidence{
		Collect: []pytestCollectRec{
			{NodeID: "tests/test_s.py", Outcome: "skipped", Message: "mod reason"},
			{NodeID: "tests/test_b.py", Outcome: "failed", Message: "ImportError while importing"},
		},
		Tests: []pytestTestRec{
			tr("pass", "setup", "passed", nil, ""), tr("pass", "call", "passed", nil, ""), tr("pass", "teardown", "passed", nil, ""),
			tr("fail", "call", "failed", nil, "AssertionError: nope"),
			tr("xfail", "call", "skipped", strp("known"), ""),
			tr("xpass", "call", "passed", strp("xp"), ""),
			tr("strict", "call", "failed", nil, "[XPASS(strict)] xps"),
			tr("skip", "call", "skipped", nil, "because"),
			tr("setupskip", "setup", "skipped", nil, "marked"),
			tr("setuperr", "setup", "failed", nil, "RuntimeError: setup boom"), tr("setuperr", "teardown", "passed", nil, ""),
			tr("ftd", "call", "failed", nil, "assert False"), tr("ftd", "teardown", "failed", nil, "RuntimeError: td"),
			tr("tds", "call", "passed", nil, ""), tr("tds", "teardown", "skipped", nil, "cleanup cannot finish"),
		},
	}
	rows, err := pytestRows(ev, pf)
	if err != nil {
		t.Fatal(err)
	}
	var got []string
	for _, r := range rows {
		got = append(got, r.File+"|"+strings.TrimPrefix(r.Case, "tests/test_a.py::")+"|"+r.Status+"|"+r.Message)
	}
	want := []string{
		"tests/test_s.py|tests/test_s.py|skip|mod reason",
		"tests/test_b.py|tests/test_b.py|error|ImportError while importing",
		"tests/test_a.py|pass|pass|",
		"tests/test_a.py|fail|fail|AssertionError: nope",
		"tests/test_a.py|xfail|skip|xfail: known",
		"tests/test_a.py|xpass|pass|xpass: xp",
		"tests/test_a.py|strict|fail|[XPASS(strict)] xps",
		"tests/test_a.py|skip|skip|because",
		"tests/test_a.py|setupskip|skip|marked",
		"tests/test_a.py|setuperr|error|setup: RuntimeError: setup boom",
		"tests/test_a.py|ftd|fail|assert False",
		"tests/test_a.py|ftd|error|teardown: RuntimeError: td",
		"tests/test_a.py|tds|pass|",
		"tests/test_a.py|tds|skip|teardown: cleanup cannot finish",
	}
	if !slices.Equal(got, want) {
		t.Fatalf("rows\n%s\nwant\n%s", strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
	for _, bad := range []pytestTestRec{tr("x", "call", "error", nil, ""), tr("x", "collect", "passed", nil, "")} {
		if _, err := pytestRows(&pytestEvidence{Tests: []pytestTestRec{bad}}, pf); err == nil {
			t.Errorf("%+v accepted", bad)
		}
	}
	if _, err := pytestRows(&pytestEvidence{Tests: []pytestTestRec{{NodeID: "tests/test_z.py::t", When: "call", Outcome: "passed"}}}, pf); err == nil || !strings.Contains(err.Error(), "names no listed file") {
		t.Errorf("an unattributable node id: %v", err)
	}
}

// Node ids map to their files by exact path equality under the reported
// rootdir, wherever that rootdir lies relative to the cwd.
func TestPytestUnitOf(t *testing.T) {
	base := t.TempDir()
	for _, d := range []string{"repo/sub/tests", "repo/t/t", "repo/tests/x", "link"} {
		if err := os.MkdirAll(filepath.Join(base, d), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.Remove(filepath.Join(base, "link")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(filepath.Join(base, "repo"), filepath.Join(base, "link")); err != nil {
		t.Fatal(err)
	}
	repo := filepath.Join(base, "repo")
	for _, tc := range []struct {
		name, root, cwd string
		args            []string
		nodeid, want    string // want "" = refused
		lowering        string // of args[0]
	}{
		{"rootdir is the cwd", repo, repo, []string{"tests/test_a.py"}, "tests/test_a.py::TestC::test_m[a/b]", "tests/test_a.py", "tests/test_a.py"},
		{"rootdir above the cwd", repo, filepath.Join(repo, "sub"), []string{"tests/test_x.py"}, "sub/tests/test_x.py::t", "tests/test_x.py", "sub/tests/test_x.py"},
		{"rootdir below the cwd", filepath.Join(repo, "tests"), repo, []string{"tests/x/test_a.py"}, "x/test_a.py::t", "tests/x/test_a.py", "x/test_a.py"},
		{"overlapping paths, outer", repo, repo, []string{"t/t.py", "t/t/t.py"}, "t/t.py::test_1", "t/t.py", "t/t.py"},
		{"overlapping paths, inner", repo, repo, []string{"t/t.py", "t/t/t.py"}, "t/t/t.py::test_2", "t/t/t.py", "t/t.py"},
		{"module collector", repo, repo, []string{"tests/test_s.py"}, "tests/test_s.py", "tests/test_s.py", "tests/test_s.py"},
		{"a symlinked cwd", repo, filepath.Join(base, "link"), []string{"tests/test_a.py"}, "tests/test_a.py::t", "tests/test_a.py", "tests/test_a.py"},
		{"empty file part", repo, repo, []string{"tests/test_a.py"}, "::test_o", "", "tests/test_a.py"},
		{"parent segment", repo, repo, []string{"tests/test_a.py"}, "../repo/tests/test_a.py::t", "", "tests/test_a.py"},
		{"absolute", repo, repo, []string{"tests/test_a.py"}, repo + "/tests/test_a.py::t", "", "tests/test_a.py"},
		{"not listed", repo, repo, []string{"tests/test_a.py"}, "tests/test_b.py::t", "", "tests/test_a.py"},
		{"a suffix is not a match", repo, repo, []string{"x/tests/test_a.py"}, "tests/test_a.py::t", "", "x/tests/test_a.py"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			pf, err := newPytestFiles(tc.root, tc.cwd, tc.args)
			if err != nil {
				t.Fatal(err)
			}
			got, err := pf.unitOf(tc.nodeid)
			if tc.want == "" {
				if err == nil {
					t.Fatalf("mapped to %q, want a refusal", got)
				}
			} else if err != nil || got != tc.want {
				t.Fatalf("unitOf %q = %q, %v; want %q", tc.nodeid, got, err, tc.want)
			}
			if low, err := pf.lowering(tc.args[0]); err != nil || low != tc.lowering {
				t.Fatalf("lowering %q, %v; want %q", low, err, tc.lowering)
			}
		})
	}
	pf, err := newPytestFiles(filepath.Join(repo, "tests"), repo, []string{"other/test_o.py"})
	if err != nil {
		t.Fatal(err)
	}
	if low, err := pf.lowering("other/test_o.py"); err == nil {
		t.Fatalf("a file outside the rootdir has lowering %q", low)
	}
	if _, err := newPytestFiles("relative", repo, nil); err == nil {
		t.Fatal("a relative rootdir accepted")
	}
}

// Discovery and execution share one argument set: they differ exactly by
// discovery's flags, and the files come last as ./<path>.
func TestPytestArgvShared(t *testing.T) {
	cmd := []string{"python3", "-m", "pytest", "-n", "2"}
	files := []string{"-tests/test_o.py", "tests/test_a.py"}
	listArgv, runArgv := pytestArgv(cmd, pytestDiscoveryFlags, files), pytestArgv(cmd, nil, files)
	want := []string{"python3", "-m", "pytest", "-n", "2", "-p", pytestPluginModule, "./-tests/test_o.py", "./tests/test_a.py"}
	if !slices.Equal(runArgv, want) {
		t.Fatalf("run argv %q, want %q", runArgv, want)
	}
	if stripped := slices.DeleteFunc(slices.Clone(listArgv), func(s string) bool { return slices.Contains(pytestDiscoveryFlags, s) }); !slices.Equal(stripped, runArgv) {
		t.Fatalf("list argv %q minus %q is %q, not the run argv %q", listArgv, pytestDiscoveryFlags, stripped, runArgv)
	}
	if !slices.Equal(pytestDiscoveryFlags, []string{"--collect-only", "-q"}) {
		t.Fatalf("discovery flags %q", pytestDiscoveryFlags)
	}
	for _, f := range listArgv {
		if f == "-c" || f == "--rootdir" || f == "-o" || strings.HasPrefix(f, "--junitxml") || strings.HasPrefix(f, "--rootdir=") {
			t.Fatalf("argv passes %q", f)
		}
	}
}

// pytest's environment: the plugin directory first on PYTHONPATH, the
// evidence file named, everything else (the recursion marker included) kept.
func TestPytestEnv(t *testing.T) {
	got := pytestEnv([]string{"A=1", "PYTHONPATH=/x:/y", "AIT_TESTMAP_ACTIVE=m", pytestEvidenceEnv + "=/stale"}, "/plug", "/ev")
	if want := []string{"A=1", "AIT_TESTMAP_ACTIVE=m", "PYTHONPATH=/plug:/x:/y", pytestEvidenceEnv + "=/ev"}; !slices.Equal(got, want) {
		t.Fatalf("env %q, want %q", got, want)
	}
	for _, environ := range [][]string{{"A=1"}, {"A=1", "PYTHONPATH="}} {
		if got := pytestEnv(environ, "/plug", "/ev"); !slices.Contains(got, "PYTHONPATH=/plug") {
			t.Fatalf("env %q has no PYTHONPATH=/plug", got)
		}
	}
}

// Only pytest 8.x on CPython >= 3.10 is supported (G10).
func TestPytestSupported(t *testing.T) {
	for _, tc := range []struct {
		pytest, python, impl string
		ok                   bool
	}{
		{"8.4.2", "3.14.8", "CPython", true},
		{"8.0.0", "3.10.0", "CPython", true},
		{"9.0.0", "3.12.1", "CPython", false},
		{"7.4.4", "3.12.1", "CPython", false},
		{"8.4.2", "3.9.18", "CPython", false},
		{"8.4.2", "3.10.13", "PyPy", false},
		{"8.4.2", "garbage", "CPython", false},
	} {
		err := pytestSupported(&pytestEvidence{Pytest: tc.pytest, Python: tc.python, Impl: tc.impl})
		if (err == nil) != tc.ok || (err != nil && !strings.HasPrefix(err.Error(), "PYTEST_UNSUPPORTED:")) {
			t.Errorf("%+v: %v", tc, err)
		}
	}
}

// A manifest unit must be a file under the cwd whose cases all name its
// lowering.
func TestPytestUnitCheck(t *testing.T) {
	for _, tc := range []struct {
		cwd  string
		u    runner.ManifestUnit
		want string // the argument; "" = refused
	}{
		{"", runner.ManifestUnit{ID: "tests/test_a.py", Lowering: "tests/test_a.py", Cases: []string{"tests/test_a.py::t"}}, "tests/test_a.py"},
		{"sub", runner.ManifestUnit{ID: "sub/tests/test_a.py", Lowering: "sub/tests/test_a.py", Cases: []string{"sub/tests/test_a.py"}}, "tests/test_a.py"},
		{"sub", runner.ManifestUnit{ID: "tests/test_a.py", Lowering: "tests/test_a.py"}, ""},
		{"", runner.ManifestUnit{ID: "tests/test_a.py", Lowering: "tests/test_a.py", Cases: []string{"tests/test_b.py::t"}}, ""},
		{"", runner.ManifestUnit{ID: "tests/test_a.py", Lowering: "../test_a.py"}, ""},
		{"", runner.ManifestUnit{ID: "tests/test_a.py", Lowering: "/abs/test_a.py"}, ""},
		{"", runner.ManifestUnit{ID: "tests/test_a.py", Lowering: ""}, ""},
		{"", runner.ManifestUnit{ID: "tests/a::b.py", Lowering: "tests/a::b.py"}, ""},
	} {
		got, err := pytestUnitCheck(tc.cwd, tc.u)
		if (tc.want == "") != (err != nil) || got != tc.want {
			t.Errorf("%q %+v: %q, %v; want %q", tc.cwd, tc.u, got, err, tc.want)
		}
	}
}

// describe is a valid file / cases / native / batch document whose comments
// carry the contract and the support claim.
func TestPytestDescribe(t *testing.T) {
	b, err := pytestDescribe(nil)
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
	if d.Unit != "file" || d.Accounting != runner.AccountingCases || d.Discovery != runner.DiscoveryNative || d.Timeouts != runner.TimeoutsBatch || !d.Batch {
		t.Fatalf("describe %+v", d)
	}
	for _, s := range []string{"-p " + pytestPluginModule, "PYTHONPATH", "observe-only", "default **/test_*.py, **/*_test.py", "--collect-only -q",
		"collector node id", "duplicate_case", "no start rows", "pytest 8.x on CPython >= 3.10, linux", "python -I / -E", "No -c, --rootdir, -o or --junitxml"} {
		if !strings.Contains(string(b), s) {
			t.Errorf("describe docs do not state %q", s)
		}
	}
}

// The embedded plugin is the source file, and records only on the
// controller.
func TestPytestPluginSource(t *testing.T) {
	src, err := os.ReadFile("pytest_evidence_plugin.py")
	if err != nil {
		t.Fatal(err)
	}
	if string(src) != string(pytestPluginSource) {
		t.Fatal("the embedded plugin differs from pytest_evidence_plugin.py")
	}
	for _, s := range []string{`hasattr(config, "workerinput")`, pytestEvidenceEnv, `"k": "items"`, `"k": "end"`, "trylast=True"} {
		if !strings.Contains(string(src), s) {
			t.Errorf("the plugin does not contain %q", s)
		}
	}
	if strings.Contains(string(src), "hookwrapper") || strings.Contains(string(src), "wrapper=True") {
		t.Error("the plugin must be observe-only: no hook wrappers")
	}
}
