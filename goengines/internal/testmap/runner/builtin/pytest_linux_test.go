//go:build linux

package builtin

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

// The pytest builtin's real-tool tests (G10): pytest 8.x on CPython >= 3.10,
// the supported configuration — python3 on PATH, else ~/.aitask/venv. Without
// it a test is skipped (the adapter is pending there) unless
// AIT_TESTMAP_REQUIRE_REAL_TOOLS=1, where the skip is a failure. pytest-xdist
// is required the same way by the tests that use it.
//
// Test-only environment the fixture tests read (besides bash-file's):
//
//	AIT_TEST_DUP        conftest: duplicate the first item at run | both
//	AIT_TEST_NEST_AT    conftest: under --collect-only, run a nested check there
//	AIT_TEST_FAKE       the fake pytest's mode

// pytestHangLimit bounds one isolated pytest test: each chains engine loads
// and runs, each starting pytest (and, for some, nested engines).
const pytestHangLimit = 120 * time.Second

// pythonProbe is what an interpreter offers the real-tool tests.
type pythonProbe struct {
	path, why string
	xdist     bool
}

var (
	probeMu    sync.Mutex
	probeCache = map[string]pythonProbe{}
)

// probePython asks candidate (a command name or path) whether it is CPython
// >= 3.10 with pytest 8.x, and whether pytest-xdist is importable.
func probePython(candidate string) pythonProbe {
	probeMu.Lock()
	defer probeMu.Unlock()
	if p, ok := probeCache[candidate]; ok {
		return p
	}
	p := pythonProbe{}
	path, err := exec.LookPath(candidate)
	if err != nil {
		p.why = candidate + ": " + err.Error()
	} else {
		out, err := exec.Command(path, "-c", `import importlib.util, platform, sys, pytest
print(platform.python_implementation(), sys.version_info[0], sys.version_info[1], pytest.__version__, importlib.util.find_spec("xdist") is not None)`).Output()
		f := strings.Fields(string(out))
		switch {
		case err != nil:
			p.why = fmt.Sprintf("%s: %v", path, err)
		case len(f) != 5 || f[0] != "CPython" || f[1] != "3" || !strings.HasPrefix(f[3], "8."):
			p.why = fmt.Sprintf("%s: %q is not CPython 3 with pytest 8.x", path, out)
		default:
			if minor, err := strconv.Atoi(f[2]); err != nil || minor < 10 {
				p.why = fmt.Sprintf("%s: python 3.%s is older than 3.10", path, f[2])
			} else {
				p.path, p.xdist = path, f[4] == "True"
			}
		}
	}
	probeCache[candidate] = p
	return p
}

// realTool skips, or fails when real tools are required.
func realTool(t *testing.T, why string) {
	t.Helper()
	if os.Getenv("AIT_TESTMAP_REQUIRE_REAL_TOOLS") == "1" {
		t.Fatal("pytest real-tool test: " + why)
	}
	t.Skip("pytest pending here: " + why)
}

// requirePytest is the interpreter the tests run pytest with.
func requirePytest(t *testing.T) string {
	t.Helper()
	var whys []string
	for _, c := range []string{"python3", filepath.Join(os.Getenv("HOME"), ".aitask", "venv", "bin", "python")} {
		p := probePython(c)
		if p.path != "" {
			return p.path
		}
		whys = append(whys, p.why)
	}
	realTool(t, strings.Join(whys, "; "))
	return ""
}

// requireXdist is requirePytest's interpreter, which must have pytest-xdist.
func requireXdist(t *testing.T) string {
	t.Helper()
	py := requirePytest(t)
	if !probePython(py).xdist {
		realTool(t, py+": pytest-xdist is not importable")
	}
	return py
}

// pyEntry is a runners.yaml entry for a pytest runner run by py; bind ""
// leaves the adapter's default. extra lines are appended verbatim.
func pyEntry(name, py, bind string, extra ...string) string {
	s := "  - name: " + name + "\n    builtin: pytest\n"
	has := func(k string) bool {
		return slices.ContainsFunc(extra, func(x string) bool { return strings.HasPrefix(x, k) })
	}
	if !has("command:") {
		s += "    command: " + py + " -m pytest\n"
	}
	if !has("batch_timeout_s:") {
		s += "    batch_timeout_s: 100\n"
	}
	if bind != "" {
		s += "    bind: ['" + bind + "']\n"
	}
	for _, x := range extra {
		s += "    " + x + "\n"
	}
	return s
}

// pyRepo is newRepo with a Python project's .gitignore: pytest writes
// __pycache__ and .pytest_cache into the fixture, as into any repository.
func pyRepo(t *testing.T, files map[string]string, runners string) (*fixture.Repo, string) {
	t.Helper()
	all := map[string]string{".gitignore": runner.StateDir + "/\n__pycache__/\n.pytest_cache/\n"}
	for k, v := range files {
		all[k] = v
	}
	return newRepo(t, all, runners)
}

// load is runner.Load of r.
func load(t *testing.T, r *fixture.Repo) *runner.Repository {
	t.Helper()
	repo, err := runner.Load(context.Background(), r.Dir)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	return repo
}

// loadErr is runner.Load's error, which must contain each of want.
func loadErr(t *testing.T, r *fixture.Repo, want ...string) {
	t.Helper()
	_, err := runner.Load(context.Background(), r.Dir)
	if err == nil {
		t.Fatalf("Load succeeded, want an error containing %q", want)
	}
	for _, w := range want {
		if !strings.Contains(err.Error(), w) {
			t.Fatalf("Load error %q does not contain %q", err, w)
		}
	}
}

// unitCases is each loaded unit's lowering and expected case identities.
func unitCases(repo *runner.Repository) map[string]string {
	out := map[string]string{}
	for _, u := range repo.Units {
		out[u.ID.String()] = u.Lowering + "=" + strings.Join(u.Cases, ",")
	}
	return out
}

// plainCollect is pytest's own `--collect-only -q` of files in dir, without
// the evidence plugin: the node ids discovery must reproduce.
func plainCollect(t *testing.T, py, dir string, files ...string) []string {
	t.Helper()
	args := []string{"-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"}
	for _, f := range files {
		args = append(args, "./"+f)
	}
	c := exec.Command(py, args...)
	c.Dir = dir
	out, err := c.Output()
	if err != nil {
		t.Fatalf("plain collect: %v\n%s", err, out)
	}
	var ids []string
	for _, l := range strings.Split(string(out), "\n") {
		if l == "" {
			break
		}
		ids = append(ids, l)
	}
	return ids
}

// caseRow is one row of an invocation's cases.jsonl.
type caseRow struct {
	Unit, Case, Status, Message string
}

// caseRows are the rows every invocation of runner name wrote.
func caseRows(t *testing.T, rep *runner.RunReport, name string) []caseRow {
	t.Helper()
	var rows []caseRow
	for _, rec := range rep.Invocations {
		if rec.Runner != name {
			continue
		}
		b, err := os.ReadFile(filepath.Join(rec.ReportDir, runner.CasesFile))
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			t.Fatal(err)
		}
		sc := bufio.NewScanner(bytes.NewReader(b))
		sc.Buffer(nil, 1<<20)
		for sc.Scan() {
			var r caseRow
			if err := json.Unmarshal(sc.Bytes(), &r); err != nil {
				t.Fatalf("cases.jsonl: %v", err)
			}
			rows = append(rows, r)
		}
	}
	return rows
}

// rowsOf are the rows for unit, as `<case>|<status>|<message>`.
func rowsOf(rows []caseRow, unit string) []string {
	var out []string
	for _, r := range rows {
		if r.Unit == unit {
			out = append(out, r.Case+"|"+r.Status+"|"+r.Message)
		}
	}
	return out
}

// unitIs asserts a cases unit's engine-derived status and reason.
func unitIs(t *testing.T, rep *runner.RunReport, id, want, reason string) runner.Result {
	t.Helper()
	r := result(t, rep, id)
	if r.Status != want || r.Reason != reason {
		t.Errorf("%s: status %q reason %q (message %q), want %q %q", id, r.Status, r.Reason, r.Message, want, reason)
	}
	return r
}

// Discovery reproduces pytest's own collection exactly; the run turns every
// terminal phase verdict into a case result, which the engine reconciles.
func TestPytestDiscoveryAndRun(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"tests/test_main.py": `import unittest
import pytest

def test_pass(): pass
def test_fail(): assert 1 == 2, "nope"

@pytest.mark.parametrize("x", ["a/b", "c::d", "e.f"])
def test_param(x): pass

class TestKlass:
    def test_m(self): pass

class TestUnit(unittest.TestCase):
    def test_u(self): self.assertTrue(True)

@pytest.mark.xfail(reason="known bug")
def test_xfail(): assert False

@pytest.mark.xfail(reason="xp")
def test_xpass(): pass

def test_skip(): pytest.skip("because reasons")

@pytest.mark.skip(reason="marked skip")
def test_mskip(): pass
`,
		"tests/test_ok.py":     "import pytest\ndef test_ok(): pass\n@pytest.mark.xfail(reason=\"later\")\ndef test_x(): assert 0\n",
		"tests/test_strict.py": "import pytest\n@pytest.mark.xfail(reason=\"xps\", strict=True)\ndef test_s(): pass\n",
		"tests/test_setup.py":  "import pytest\n@pytest.fixture\ndef bad(): raise RuntimeError(\"setup boom\")\ndef test_e(bad): pass\n",
		"tests/test_ftd.py":    "import pytest\n@pytest.fixture\ndef td():\n    yield\n    raise RuntimeError(\"teardown boom\")\ndef test_f(td): assert False\n",
		"tests/test_tds.py":    "import pytest\n@pytest.fixture\ndef f():\n    yield\n    pytest.skip(\"cleanup cannot finish\")\ndef test_t(f): pass\n",
		"tests/helper.py":      "def help(): pass\n",
	}, pyEntry("py", py, ""))
	repo := load(t, r)
	files := []string{"tests/test_ftd.py", "tests/test_main.py", "tests/test_ok.py", "tests/test_setup.py", "tests/test_strict.py", "tests/test_tds.py"}
	var listed []string
	for _, u := range repo.Units {
		if u.Runner != "py" || u.Lowering != u.ID.String() {
			t.Fatalf("unit %+v", u)
		}
		listed = append(listed, u.Cases...)
	}
	if len(repo.Units) != len(files) {
		t.Fatalf("units %v, want the six test files", unitCases(repo))
	}
	if plain := plainCollect(t, py, r.Dir, files...); !slices.Equal(listed, plain) {
		t.Fatalf("discovery lists\n%s\npytest collects\n%s", strings.Join(listed, "\n"), strings.Join(plain, "\n"))
	}
	rep := run(t, r, "discovery-and-run")
	main := unitIs(t, rep, "tests/test_main.py", runner.StatusFail, "")
	if c := main.Cases; c == nil || *c != (runner.CaseCounts{Expected: 11, Passed: 7, Failed: 1, Skipped: 3}) {
		t.Errorf("test_main counters %+v", c)
	}
	ok := unitIs(t, rep, "tests/test_ok.py", runner.StatusPass, "")
	if !slices.Equal(ok.SkippedCases, []string{"tests/test_ok.py::test_x"}) {
		t.Errorf("test_ok skipped %v", ok.SkippedCases)
	}
	unitIs(t, rep, "tests/test_strict.py", runner.StatusFail, "")
	unitIs(t, rep, "tests/test_setup.py", runner.StatusError, "")
	unitIs(t, rep, "tests/test_ftd.py", runner.StatusError, runner.ReasonDuplicateCase)
	unitIs(t, rep, "tests/test_tds.py", runner.StatusError, runner.ReasonDuplicateCase)
	rows := caseRows(t, rep, "py")
	for unit, want := range map[string][]string{
		"tests/test_tds.py":    {"tests/test_tds.py::test_t|pass|", "tests/test_tds.py::test_t|skip|teardown: cleanup cannot finish"},
		"tests/test_ftd.py":    {"tests/test_ftd.py::test_f|fail|assert False", "tests/test_ftd.py::test_f|error|teardown: RuntimeError: teardown boom"},
		"tests/test_setup.py":  {"tests/test_setup.py::test_e|error|setup: RuntimeError: setup boom"},
		"tests/test_strict.py": {"tests/test_strict.py::test_s|fail|[XPASS(strict)] xps"},
	} {
		if got := rowsOf(rows, unit); !slices.Equal(got, want) {
			t.Errorf("%s rows %q, want %q", unit, got, want)
		}
	}
	for _, want := range []string{"tests/test_main.py::test_xfail|skip|xfail: known bug", "tests/test_main.py::test_skip|skip|because reasons",
		"tests/test_main.py::test_mskip|skip|marked skip", "tests/test_main.py::test_xpass|pass|xpass: xp", "tests/test_main.py::test_fail|fail|AssertionError: nope"} {
		if !slices.Contains(rowsOf(rows, "tests/test_main.py"), want) {
			t.Errorf("test_main rows lack %q: %q", want, rowsOf(rows, "tests/test_main.py"))
		}
	}
	rec := record(t, rep, "py")
	if rec.Cause != runner.CauseReconciliation || rec.ExitCode != 1 || rec.Containment != procsup.Supervisor || rec.Accounting != runner.AccountingCases ||
		rec.Discovery != runner.DiscoveryNative || rec.UnitsStarted != 0 || rec.UnitsExpected != len(files) {
		t.Fatalf("record %+v", rec)
	}
	for _, f := range []string{"pytest.stdout", "pytest.stderr", "pytest-evidence.jsonl", "pytest-plugin/" + pytestPluginModule + ".py"} {
		if _, err := os.Stat(filepath.Join(rec.ReportDir, f)); err != nil {
			t.Errorf("report directory: %v", err)
		}
	}
}

// A file that cannot be collected refuses the whole list: never a silently
// dropped unit.
func TestPytestCollectionError(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"tests/test_ok.py":     "def test_ok(): pass\n",
		"tests/test_broken.py": "import nosuchmodule_xyz\ndef test_x(): pass\n",
	}, pyEntry("py", py, ""))
	loadErr(t, r, "collection error: tests/test_broken.py", "ImportError")
}

// A rootdir above the cwd (an ini at the root, the runner in sub/): node ids
// and lowerings are rootdir-relative, and execution agrees with discovery.
func TestPytestRootdirAboveCwd(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"pytest.ini":          "[pytest]\n",
		"sub/tests/test_x.py": "def test_a(): pass\n",
	}, pyEntry("py", py, "", "cwd: sub"))
	if got := unitCases(load(t, r)); got["sub/tests/test_x.py"] != "sub/tests/test_x.py=sub/tests/test_x.py::test_a" || len(got) != 1 {
		t.Fatalf("units %v", got)
	}
	unitIs(t, run(t, r, "above"), "sub/tests/test_x.py", runner.StatusPass, "")
}

// A nested ini below the cwd makes the rootdir tests/: lowerings are relative
// to it. A bound file outside that rootdir has no file in its node id and
// refuses the list.
func TestPytestNestedIniBelowCwd(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"tests/pytest.ini":    "[pytest]\n",
		"tests/x/test_a.py":   "def test_a(): pass\n",
		"other/notbound_o.py": "def test_o(): pass\n",
	}, pyEntry("py", py, "tests/**/test_*.py"))
	if got := unitCases(load(t, r)); got["tests/x/test_a.py"] != "x/test_a.py=x/test_a.py::test_a" || len(got) != 1 {
		t.Fatalf("units %v", got)
	}
	unitIs(t, run(t, r, "nested"), "tests/x/test_a.py", runner.StatusPass, "")
	r2, _ := pyRepo(t, map[string]string{
		"tests/pytest.ini":  "[pytest]\n",
		"tests/x/test_a.py": "def test_a(): pass\n",
		"other/test_o.py":   "def test_o(): pass\n",
	}, pyEntry("py", py, ""))
	loadErr(t, r2, `"::test_o"`, "rootdir")
}

// Overlapping paths (t/t.py beside t/t/t.py, importlib mode): each node id
// maps to its own file by exact path, so both units run and pass.
func TestPytestOverlappingPaths(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"pytest.ini": "[pytest]\naddopts = --import-mode=importlib\n",
		"t/t.py":     "def test_1(): pass\n",
		"t/t/t.py":   "def test_2(): pass\n",
	}, pyEntry("py", py, "t/**/*.py"))
	if got := unitCases(load(t, r)); got["t/t.py"] != "t/t.py=t/t.py::test_1" || got["t/t/t.py"] != "t/t/t.py=t/t/t.py::test_2" {
		t.Fatalf("units %v", got)
	}
	rep := run(t, r, "overlap")
	unitIs(t, rep, "t/t.py", runner.StatusPass, "")
	unitIs(t, rep, "t/t/t.py", runner.StatusPass, "")
}

// The equal-key substitution: discovery collects tests/test_a.py::TestC::test_m,
// execution runs tests/test_a/TestC.py::test_m instead — the same JUnit
// (classname, name). Exact runtime identities make the original incomplete
// and the replacement unexpected; zero_tests: skip cannot hide it.
func TestPytestSubstitutionKeyCollision(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"pytest.ini":            "[pytest]\naddopts = --import-mode=importlib\n",
		"tests/test_a.py":       "import sys\nif \"--collect-only\" in sys.argv:\n    class TestC:\n        def test_m(self): pass\n",
		"tests/test_a/TestC.py": "import sys\nif \"--collect-only\" not in sys.argv:\n    def test_m(): pass\n",
	}, pyEntry("py", py, "tests/**/*.py", "zero_tests: skip"))
	if got := unitCases(load(t, r)); got["tests/test_a.py"] != "tests/test_a.py=tests/test_a.py::TestC::test_m" || got["tests/test_a/TestC.py"] != "tests/test_a/TestC.py=" {
		t.Fatalf("units %v", got)
	}
	rep := run(t, r, "collision")
	unitIs(t, rep, "tests/test_a.py", runner.StatusError, runner.ReasonIncomplete)
	unitIs(t, rep, "tests/test_a/TestC.py", runner.StatusError, runner.ReasonUnexpectedCase)
}

// A test renamed between discovery and execution: an equal-count
// substitution, never a pass.
func TestPytestSubstitutionRename(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"tests/test_r.py": "import sys\ndef test_a(): pass\nif \"--collect-only\" in sys.argv:\n    def test_b(): pass\nelse:\n    def test_c(): pass\n",
	}, pyEntry("py", py, ""))
	unitIs(t, run(t, r, "rename"), "tests/test_r.py", runner.StatusError, runner.ReasonUnexpectedCase+","+runner.ReasonIncomplete)
}

// A module skipped at collection is one expected identity, its collector
// node id, whose result is the tool's skip with its reason — alone, in a
// mixed batch, under either zero_tests policy. A skip that appears or
// disappears between discovery and execution is an error.
func TestPytestModuleLevelSkip(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	skipped := "import pytest\npytest.skip(\"mod reason\", allow_module_level=True)\ndef test_x(): pass\n"
	r, _ := pyRepo(t, map[string]string{
		"iso/test_s.py":    skipped,
		"iso2/test_s.py":   skipped,
		"mixed/test_s.py":  skipped,
		"mixed/test_ok.py": "def test_ok(): pass\n",
		"flip/test_c.py":   "import sys, pytest\nif \"--collect-only\" in sys.argv:\n    pytest.skip(\"only at collection\", allow_module_level=True)\ndef test_x(): pass\n",
		"flip/test_d.py":   "import sys, pytest\nif \"--collect-only\" not in sys.argv:\n    pytest.skip(\"only at run\", allow_module_level=True)\ndef test_x(): pass\n",
	}, pyEntry("iso", py, "iso/**/*.py")+pyEntry("iso2", py, "iso2/**/*.py", "zero_tests: skip")+pyEntry("mixed", py, "mixed/**/*.py")+pyEntry("flip", py, "flip/**/*.py"))
	if got := unitCases(load(t, r)); got["iso/test_s.py"] != "iso/test_s.py=iso/test_s.py" || got["flip/test_d.py"] != "flip/test_d.py=flip/test_d.py::test_x" {
		t.Fatalf("units %v", got)
	}
	rep := run(t, r, "module-skip")
	for _, id := range []string{"iso/test_s.py", "iso2/test_s.py", "mixed/test_s.py"} {
		res := unitIs(t, rep, id, runner.StatusSkip, "")
		if !slices.Equal(res.SkippedCases, []string{id}) {
			t.Errorf("%s skipped %v", id, res.SkippedCases)
		}
	}
	unitIs(t, rep, "mixed/test_ok.py", runner.StatusPass, "")
	if got := rowsOf(caseRows(t, rep, "iso"), "iso/test_s.py"); !slices.Equal(got, []string{"iso/test_s.py|skip|mod reason"}) {
		t.Errorf("iso rows %q", got)
	}
	unitIs(t, rep, "flip/test_c.py", runner.StatusError, runner.ReasonUnexpectedCase+","+runner.ReasonIncomplete)
	unitIs(t, rep, "flip/test_d.py", runner.StatusError, runner.ReasonUnexpectedCase+","+runner.ReasonIncomplete)
}

// G3: a bound file with no tests is error:zero_tests, or skip under
// zero_tests: skip — never a pass; its batch neighbour is unaffected.
func TestPytestZeroTests(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"a/test_empty.py": "def helper(): pass\n",
		"a/test_ok.py":    "def test_ok(): pass\n",
		"b/test_empty.py": "def helper(): pass\n",
	}, pyEntry("a", py, "a/**/*.py")+pyEntry("b", py, "b/**/*.py", "zero_tests: skip"))
	rep := run(t, r, "zero")
	unitIs(t, rep, "a/test_empty.py", runner.StatusError, runner.PolicyZeroTests)
	unitIs(t, rep, "a/test_ok.py", runner.StatusPass, "")
	unitIs(t, rep, "b/test_empty.py", runner.StatusSkip, runner.PolicyZeroTests)
}

// testmap:batch no makes each such unit a singleton invocation, beside a
// batch of the others.
func TestPytestBatchNo(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"tests/test_b1.py": "# testmap:batch no\ndef test_x(): pass\n",
		"tests/test_b2.py": "# testmap:batch no\ndef test_x(): pass\n",
		"tests/test_p1.py": "def test_x(): pass\n",
		"tests/test_p2.py": "def test_x(): pass\n",
	}, pyEntry("py", py, ""))
	rep := run(t, r, "batchno")
	size, inv := map[int]int{}, map[string]int{}
	for _, rec := range rep.Invocations {
		size[rec.Invocation] = rec.UnitsExpected
	}
	for _, res := range rep.Results {
		inv[res.ID.String()] = res.Invocation
		if res.Status != runner.StatusPass {
			t.Errorf("%s: %s %s", res.ID, res.Status, res.Reason)
		}
	}
	if len(rep.Invocations) != 3 || size[inv["tests/test_b1.py"]] != 1 || size[inv["tests/test_b2.py"]] != 1 ||
		inv["tests/test_b1.py"] == inv["tests/test_b2.py"] || inv["tests/test_p1.py"] != inv["tests/test_p2.py"] || size[inv["tests/test_p1.py"]] != 2 {
		t.Fatalf("invocations %v sizes %v", inv, size)
	}
}

// Duplicates are never collapsed: an item run twice is duplicate_case, and an
// item collected twice refuses the list (the engine's list rule).
func TestPytestDuplicates(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{
		"conftest.py": `import os, sys
def pytest_collection_modifyitems(session, config, items):
    mode = os.environ.get("AIT_TEST_DUP", "")
    if items and (mode == "both" or (mode == "run" and "--collect-only" not in sys.argv)):
        items.append(items[0])
`,
		"tests/test_d.py": "def test_x(): pass\n",
	}, pyEntry("py", py, ""))
	t.Setenv("AIT_TEST_DUP", "run")
	rep := run(t, r, "dup-run")
	unitIs(t, rep, "tests/test_d.py", runner.StatusError, runner.ReasonDuplicateCase)
	if got := rowsOf(caseRows(t, rep, "py"), "tests/test_d.py"); !slices.Equal(got, []string{"tests/test_d.py::test_x|pass|", "tests/test_d.py::test_x|pass|"}) {
		t.Fatalf("rows %q", got)
	}
	t.Setenv("AIT_TEST_DUP", "both")
	loadErr(t, r, "already listed")
}

// Under pytest-xdist every phase is recorded once (the controller), and the
// verdicts are those of a plain run; discovery under -n records its items,
// populated or entirely module-skipped.
func TestPytestXdist(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requireXdist(t)
	r, _ := pyRepo(t, map[string]string{
		"x/test_ok.py":   "def test_1(): pass\ndef test_2(): pass\n",
		"x/test_fail.py": "def test_f(): assert False\n",
		"x/test_s.py":    "import pytest\npytest.skip(\"mod reason\", allow_module_level=True)\n",
		"x/test_tds.py":  "import pytest\n@pytest.fixture\ndef f():\n    yield\n    pytest.skip(\"cleanup cannot finish\")\ndef test_t(f): pass\n",
		"x/test_late.py": "import sys\nif \"--collect-only\" not in sys.argv:\n    import nosuchmodule_xyz\ndef test_l(): pass\n",
		"xs/test_s.py":   "import pytest\npytest.skip(\"all skipped\", allow_module_level=True)\n",
	}, pyEntry("x", py, "x/**/*.py", "command: "+py+" -m pytest -n 2")+pyEntry("xs", py, "xs/**/*.py", "command: "+py+" -m pytest -n 2"))
	if got := unitCases(load(t, r)); got["x/test_ok.py"] != "x/test_ok.py=x/test_ok.py::test_1,x/test_ok.py::test_2" || got["xs/test_s.py"] != "xs/test_s.py=xs/test_s.py" {
		t.Fatalf("units %v", got)
	}
	rep := run(t, r, "xdist")
	ok := unitIs(t, rep, "x/test_ok.py", runner.StatusPass, "")
	if ok.Cases == nil || ok.Cases.Passed != 2 {
		t.Errorf("x/test_ok counters %+v", ok.Cases)
	}
	unitIs(t, rep, "x/test_fail.py", runner.StatusFail, "")
	unitIs(t, rep, "x/test_s.py", runner.StatusSkip, "")
	unitIs(t, rep, "x/test_tds.py", runner.StatusError, runner.ReasonDuplicateCase)
	unitIs(t, rep, "x/test_late.py", runner.StatusError, runner.ReasonUnexpectedCase+","+runner.ReasonIncomplete)
	unitIs(t, rep, "xs/test_s.py", runner.StatusSkip, "")
	rows := caseRows(t, rep, "x")
	if got := rowsOf(rows, "x/test_ok.py"); len(got) != 2 {
		t.Errorf("x/test_ok rows %q: every phase must be recorded once", got)
	}
	if got := rowsOf(rows, "x/test_tds.py"); !slices.Equal(got, []string{"x/test_tds.py::test_t|pass|", "x/test_tds.py::test_t|skip|teardown: cleanup cannot finish"}) {
		t.Errorf("x/test_tds rows %q", got)
	}
}

// The bounded batch timeout: with no start rows every unit is batch_timeout,
// and pytest and the background child of the running test are gone.
func TestPytestBatchTimeoutKillsTree(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, st := pyRepo(t, map[string]string{
		"tests/test_a_slow.py": `import os, subprocess, time
def test_slow():
    st = os.environ["AIT_TEST_STATE"]
    p = subprocess.Popen(["sleep", "300"])
    for name, pid in (("bg", p.pid), ("py", os.getpid())):
        with open(os.path.join(st, name + ".tmp"), "w") as f:
            f.write("%d\n" % pid)
        os.rename(os.path.join(st, name + ".tmp"), os.path.join(st, name + ".pid"))
    time.sleep(300)
`,
		"tests/test_b_other.py": "def test_o(): pass\n",
	}, pyEntry("py", py, "", "batch_timeout_s: 6"))
	rep := run(t, r, "batch-timeout")
	unitIs(t, rep, "tests/test_a_slow.py", runner.StatusBatchTimeout, "")
	unitIs(t, rep, "tests/test_b_other.py", runner.StatusBatchTimeout, "")
	for _, f := range []string{"bg.pid", "py.pid"} {
		b, err := os.ReadFile(filepath.Join(st, f))
		if err != nil {
			t.Fatalf("pytest did not reach the slow test within the batch timeout: %v", err)
		}
		pid, err := strconv.Atoi(strings.TrimSpace(string(b)))
		if err != nil {
			t.Fatal(err)
		}
		if !waitDead(pid, 5*time.Second) {
			t.Fatalf("%s %d survived the batch timeout", f, pid)
		}
	}
}

// pyNest is a test module that runs the engine nested on its own repository
// (refused) and on another (allowed), recording each nested stderr.
const pyNest = `import os, subprocess
def _nest(root, name):
    p = subprocess.run([os.environ["AIT_TEST_ENGINE"], "` + nestedEngineArg + `", "run"], cwd=root, capture_output=True, text=True)
    with open(os.path.join(os.environ["AIT_TEST_STATE"], name), "w") as f:
        f.write(p.stderr)
    return p.returncode
def test_self(): assert _nest(os.environ["AIT_TESTMAP_ROOT"], "self.err") != 0
def test_other(): assert _nest(os.environ["AIT_TEST_OTHER"], "other.err") == 0
`

// The execution recursion test: a test that runs the engine on its own
// repository is refused through the inherited marker (VIA:marker — the
// ancestry backstop would refuse too); the same nested run on another
// repository succeeds.
func TestPytestRecursionThroughExecution(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	other, _ := pyRepo(t, map[string]string{"tests/test_ok.py": "def test_ok(): pass\n"}, pyEntry("o", py, ""))
	r, st := pyRepo(t, map[string]string{"tests/test_nest.py": pyNest}, pyEntry("py", py, ""))
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("AIT_TEST_ENGINE", exe)
	t.Setenv("AIT_TEST_OTHER", other.Dir)
	rep := run(t, r, "nest-exec")
	unitIs(t, rep, "tests/test_nest.py", runner.StatusPass, "")
	self := readState(t, st, "self.err")
	if !strings.Contains(self, "RUN_ERROR:recursion|") || !slices.Contains(strings.Split(self, "\n"), "VIA:marker") {
		t.Fatalf("the nested run on the same repository: %q", self)
	}
	if o := readState(t, st, "other.err"); !strings.Contains(o, "NESTED_OK:0") {
		t.Fatalf("the nested run on another repository: %q", o)
	}
}

// pyNestConftest, under --collect-only and armed by AIT_TEST_NEST_AT, runs a
// nested engine check there during discovery and refuses on its refusal.
const pyNestConftest = `import os, subprocess, sys
import pytest
def pytest_configure(config):
    at = os.environ.get("AIT_TEST_NEST_AT")
    if not at or "--collect-only" not in sys.argv:
        return
    p = subprocess.run([os.environ["AIT_TEST_ENGINE"], "` + nestedEngineArg + `", "check"], cwd=at, capture_output=True, text=True)
    with open(os.path.join(os.environ["AIT_TEST_STATE"], "discovery.err"), "w") as f:
        f.write(p.stderr)
    if p.returncode != 0:
        raise pytest.UsageError(p.stderr.splitlines()[0] if p.stderr else "nested check failed")
`

// The discovery recursion test: native discovery runs project code, and a
// conftest running the engine on its own repository is refused through the
// marker; the same nested check of another repository succeeds.
func TestPytestRecursionThroughDiscovery(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	other, _ := pyRepo(t, map[string]string{"tests/test_ok.py": "def test_ok(): pass\n"}, pyEntry("o", py, ""))
	r, st := pyRepo(t, map[string]string{"conftest.py": pyNestConftest, "tests/test_ok.py": "def test_ok(): pass\n"}, pyEntry("py", py, ""))
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("AIT_TEST_ENGINE", exe)
	t.Setenv("AIT_TEST_NEST_AT", r.Dir)
	loadErr(t, r, "RUNNER_PROTOCOL:py|list|", "RUN_ERROR:recursion")
	if d := readState(t, st, "discovery.err"); !slices.Contains(strings.Split(d, "\n"), "VIA:marker") {
		t.Fatalf("the nested check during discovery: %q", d)
	}
	t.Setenv("AIT_TEST_NEST_AT", other.Dir)
	load(t, r)
	if d := readState(t, st, "discovery.err"); !strings.Contains(d, "NESTED_OK:0") {
		t.Fatalf("the nested check of another repository: %q", d)
	}
}

// command: overrides — refused shell syntax, an interpreter that ignores
// PYTHONPATH (the plugin cannot load: refused, never run unrecorded), and
// the default python3 -m pytest where python3 qualifies.
func TestPytestCommandOverride(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	files := map[string]string{"tests/test_ok.py": "def test_ok(): pass\n"}
	r, _ := pyRepo(t, files, pyEntry("py", py, "", "command: python3;x"))
	loadErr(t, r, "not allowed")
	r, _ = pyRepo(t, files, pyEntry("py", py, "", "command: "+py+" -I -m pytest"))
	loadErr(t, r, "evidence plugin", "PYTHONPATH")
	if probePython("python3").path == "" {
		t.Log("python3 on PATH does not qualify: the default command is not exercised here")
		return
	}
	r, _ = pyRepo(t, files, "  - name: py\n    builtin: pytest\n    batch_timeout_s: 100\n")
	unitIs(t, run(t, r, "default-command"), "tests/test_ok.py", runner.StatusPass, "")
}

// Where containment is unavailable the adapter refuses before anything runs.
func TestPytestContainmentUnavailable(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	defer procsup.SetUnavailableForTesting()()
	for _, verb := range []string{"describe", "list"} {
		var out, errb bytes.Buffer
		if code := Main([]string{pytestName, verb}, &out, &errb); code != 3 || errb.String() != "CONTAINMENT_UNAVAILABLE:linux\n" || out.Len() != 0 {
			t.Fatalf("%s: code %d stdout %q stderr %q", verb, code, out.String(), errb.String())
		}
	}
}

// fakePytest stands in for pytest only where the real tool cannot produce
// the case: crafted evidence (stale, linked, malformed, contradicting the
// exit, outside every unit, a moved rootdir, an unsupported version, a lost
// items record, a null where a value is required, a FIFO as discovery's
// evidence). Discovery evidence is
// valid unless the mode says otherwise.
// Each run mode trips exactly one check: exitmismatch's rows agree with the
// exit and only the recorded status does not; drift's node id still maps to
// the file under the moved rootdir, and only its lowering differs.
const fakePytest = `#!/bin/bash
ev=$AIT_TESTMAP_PYTEST_EVIDENCE
root=$PWD
session='{"k":"session","v":1,"rootdir":"'$root'","pytest":"8.4.2","python":"3.12.1","impl":"CPython"}'
pass='{"k":"test","nodeid":"tests/test_f.py::t","when":"call","outcome":"passed","xfail":null,"message":"","duration":0.0}'
failed='{"k":"test","nodeid":"tests/test_f.py::t","when":"call","outcome":"failed","xfail":null,"message":"boom","duration":0.0}'
case " $* " in
*" --collect-only "*)
  case $AIT_TEST_FAKE in
  v9) session=${session/8.4.2/9.0.0} ;;
  fifo) rm -f "$ev"; mkfifo "$ev"; exit 0 ;;
  esac
  {
    echo "$session"
    [ "$AIT_TEST_FAKE" = noitems ] || echo '{"k":"items","nodeids":["tests/test_f.py::t"]}'
    echo '{"k":"end","exitstatus":0}'
  } > "$ev"
  exit 0 ;;
esac
code=0
case $AIT_TEST_FAKE in
stale) printf '%s\n%s\n%s\n' "$session" "$pass" '{"k":"end","exitstatus":0}' > "$ev"; touch -d 2000-01-01 "$ev" ;;
symlink) printf '%s\n%s\n%s\n' "$session" "$pass" '{"k":"end","exitstatus":0}' > "$AIT_TEST_STATE/real.jsonl"; ln -s "$AIT_TEST_STATE/real.jsonl" "$ev" ;;
malformed) echo 'not json' > "$ev" ;;
absent) ;;
noend) printf '%s\n%s\n' "$session" "$pass" > "$ev" ;;
exitmismatch) printf '%s\n%s\n%s\n' "$session" "$pass" '{"k":"end","exitstatus":1}' > "$ev" ;;
zerowithfail) printf '%s\n%s\n%s\n' "$session" "$failed" '{"k":"end","exitstatus":0}' > "$ev" ;;
onewithoutfail) printf '%s\n%s\n%s\n' "$session" "$pass" '{"k":"end","exitstatus":1}' > "$ev"; code=1 ;;
unattributable) printf '%s\n%s\n%s\n' "$session" "${pass/test_f.py/test_other.py}" '{"k":"end","exitstatus":0}' > "$ev" ;;
drift) printf '%s\n%s\n%s\n' '{"k":"session","v":1,"rootdir":"'$root'/tests","pytest":"8.4.2","python":"3.12.1","impl":"CPython"}' "${pass/tests\/test_f.py/test_f.py}" '{"k":"end","exitstatus":0}' > "$ev" ;;
nullexit) printf '%s\n%s\n%s\n' "$session" "$pass" '{"k":"end","exitstatus":null}' > "$ev" ;;
nullmessage) printf '%s\n%s\n%s\n' "$session" '{"k":"test","nodeid":"tests/test_f.py::t","when":"call","outcome":"skipped","xfail":null,"message":null,"duration":0.0}' '{"k":"end","exitstatus":0}' > "$ev" ;;
*) printf '%s\n%s\n%s\n' "$session" "$pass" '{"k":"end","exitstatus":0}' > "$ev" ;;
esac
exit $code
`

// Evidence the run cannot prove is a mechanism failure with no case rows,
// and the unit is never a pass or a skip; discovery evidence of an
// unsupported pytest or without its items record refuses the list.
func TestPytestFakeEvidence(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	r, _ := pyRepo(t, map[string]string{
		"tools/fakepytest.sh": fakePytest,
		"tests/test_f.py":     "def t(): pass\n",
	}, pyEntry("py", "", "", "command: bash tools/fakepytest.sh", "zero_tests: skip"))
	t.Setenv("AIT_TEST_FAKE", "good")
	unitIs(t, run(t, r, "fake-good"), "tests/test_f.py", runner.StatusPass, "") // the control: the fake's good evidence passes
	for _, mode := range []string{"stale", "symlink", "malformed", "absent", "noend", "exitmismatch", "zerowithfail", "onewithoutfail", "unattributable", "drift", "nullexit", "nullmessage"} {
		t.Run(mode, func(t *testing.T) {
			t.Setenv("AIT_TEST_FAKE", mode)
			rep := run(t, r, "fake-"+mode)
			res := result(t, rep, "tests/test_f.py")
			rec := record(t, rep, "py")
			if res.Status == runner.StatusPass || res.Status == runner.StatusSkip || rec.Cause != runner.CauseMechanism || len(caseRows(t, rep, "py")) != 0 {
				t.Fatalf("%s: unit %+v record cause %q detail %q", mode, res, rec.Cause, rec.CauseDetail)
			}
		})
	}
	t.Setenv("AIT_TEST_FAKE", "v9")
	loadErr(t, r, "PYTEST_UNSUPPORTED:pytest 9.0.0")
	t.Setenv("AIT_TEST_FAKE", "noitems")
	loadErr(t, r, "no items record")
	// A writer-less FIFO left as discovery's evidence is refused promptly,
	// never waited on until the discovery bound.
	t.Setenv("AIT_TEST_FAKE", "fifo")
	t0 := time.Now()
	loadErr(t, r, "not a regular file")
	if d := time.Since(t0); d > 30*time.Second {
		t.Fatalf("refusing the FIFO took %v", d)
	}
}

// A file name starting with "-" stays an operand (./-tests/...); a path
// containing "::" (pytest's node selector), or one the id grammar reads as a
// member or variant ('#', '@'), is refused.
func TestPytestOptionShapedPath(t *testing.T) {
	if !hangguard.Isolated(t, pytestHangLimit) {
		return
	}
	py := requirePytest(t)
	r, _ := pyRepo(t, map[string]string{"-tests/test_o.py": "def test_o(): pass\n"}, pyEntry("py", py, ""))
	if got := unitCases(load(t, r)); got["-tests/test_o.py"] != "-tests/test_o.py=-tests/test_o.py::test_o" {
		t.Fatalf("units %v", got)
	}
	unitIs(t, run(t, r, "option-shaped"), "-tests/test_o.py", runner.StatusPass, "")
	r, _ = pyRepo(t, map[string]string{"tests/test_a::b.py": "def test_x(): pass\n"}, pyEntry("py", py, ""))
	loadErr(t, r, `"::"`)
	for _, p := range []string{"tests/test_a#b.py", "tests/test_a@v.py"} {
		r, _ = pyRepo(t, map[string]string{p: "def test_x(): pass\n"}, pyEntry("py", py, ""))
		loadErr(t, r, p, "no '#' member")
	}
}
