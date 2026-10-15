package runner

// The hang guard's tripwire.
//
// A test that starts a process must begin with the isolated guard
// (watchdog_unix_test.go), or a regression that makes it hang waits for go
// test's own timeout. Nothing in the language enforces that convention, so
// TestIsolationTripwire does: it parses every source file of this package —
// test and non-test, whatever its build constraint — and fails a top-level
// test that reaches a process start, transitively through package-level
// functions and variables, unless the guard is its first statement or the
// test is one of the watchdog's own controls (isolationAllow). ci/preflight.sh
// runs it alone before the suite: inside `go test ./...` it would run in file
// order, after tests that could already hang, and its failure would not stop
// them.
//
// Like the Invariant 5 tripwire (goengines/guards_test.go) it is lexical: it
// resolves names, not types. A reference counts wherever an identifier could
// name a package-level declaration — a call, a function value in a table, a
// closure — and another package's name counts by its import path, whatever
// the import is called. Calls through methods, interfaces and func-typed
// fields are not followed, which is why Run (through the Executor) and Load
// (through Runner.call and gitx) are starters themselves; a test that starts
// a process only through such a call is not seen. A guarded test the tripwire
// sees no process start in fails too, so the starter list cannot rot under
// the tests that are guarded.

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"maps"
	"os"
	"slices"
	"strconv"
	"strings"
	"testing"
	"unicode"
	"unicode/utf8"
)

const modPath = "github.com/beyondeye/aitasks/goengines"

// localStarters are this package's entry points to a process — or to a
// session sweep, which can hang without starting one — that name resolution
// cannot see through.
var localStarters = []string{"Run", "Load", "sweepSession"}

// importStarters are other packages' starters as <import path>.<name>;
// <import path>.* is every name of that package.
var importStarters = []string{
	"os/exec.Command",
	"os/exec.CommandContext",
	"os.StartProcess",
	"syscall.ForkExec",
	"syscall.StartProcess",
	modPath + "/internal/testmap/registry.Scan",
	modPath + "/internal/testmap/registry.Check",
	modPath + "/internal/testmap/fixture.New",
	modPath + "/internal/gitx.*", // gitx exists to run git
}

// isolationAllow are the process-starting tests that must not isolate
// themselves, each with its reason.
var isolationAllow = map[string]string{
	"TestIsolationControls":     "the watchdog's own negative controls: they launch runChild themselves and must see the HANG and LEAK reports it produces",
	"TestReapMarkedUncertainty": "drives reapMarked against processes it starts; isolated, it would run under the cleanup it tests",
}

// guardName is the hang guard. It starts a process itself (runChild), so no
// reference to it counts: counting one would make every guarded test look
// process-starting for carrying the guard.
const guardName = "isolated"

// The kinds of finding.
const (
	findUnguarded  = "unguarded"   // starts a process without the guard
	findUnseen     = "unseen"      // guarded, but no process start is seen
	findStaleAllow = "stale-allow" // an isolationAllow entry with nothing to allow
)

// tripTest is one top-level test as the tripwire sees it.
type tripTest struct {
	name, param string
	pos         token.Position
	decl        *ast.FuncDecl
	guarded     bool     // its first statement is the hang guard
	via         []string // the reference chain to a starter; nil when it reaches none
}

type tripFinding struct{ test, kind, msg string }

// refs is what one declaration references: the names that may mean a
// package-level declaration, and the other packages' starters it names.
type refs struct{ local, ext []string }

// parseRunnerPkg parses one package's sources, keyed by file name. A file of
// another package is refused — an external test package would escape the
// tripwire unseen — and so is a dot import: its names arrive unqualified, so
// a starter (Command) could not be told from a name of this package.
func parseRunnerPkg(fset *token.FileSet, srcs map[string][]byte) ([]*ast.File, error) {
	var files []*ast.File
	for _, name := range slices.Sorted(maps.Keys(srcs)) {
		f, err := parser.ParseFile(fset, name, srcs[name], parser.SkipObjectResolution)
		if err != nil {
			return nil, err
		}
		if f.Name.Name != "runner" {
			return nil, fmt.Errorf("%s: package %s, which the tripwire does not cover", name, f.Name.Name)
		}
		for _, is := range f.Imports {
			if is.Name != nil && is.Name.Name == "." {
				return nil, fmt.Errorf("%s: dot import of %s, which the tripwire cannot resolve: import it by name", fset.Position(is.Pos()), is.Path.Value)
			}
		}
		files = append(files, f)
	}
	return files, nil
}

// importNames maps a file's import names to their paths.
func importNames(f *ast.File) map[string]string {
	m := map[string]string{}
	for _, is := range f.Imports {
		path, err := strconv.Unquote(is.Path.Value)
		if err != nil {
			continue
		}
		name := path[strings.LastIndex(path, "/")+1:]
		if is.Name != nil {
			name = is.Name.Name
		}
		if name != "_" {
			m[name] = path
		}
	}
	return m
}

func isImportStarter(path, name string) bool {
	return slices.Contains(importStarters, path+"."+name) || slices.Contains(importStarters, path+".*")
}

// refsOf collects the references in n. An identifier counts unless it is a
// selector's name (t.Run is not Run), a struct literal's key, a field or
// parameter name, or a label; a selector on an import counts by its path.
func refsOf(n ast.Node, imports map[string]string) refs {
	var r refs
	skip := map[*ast.Ident]bool{}
	ast.Inspect(n, func(x ast.Node) bool {
		switch x := x.(type) {
		case *ast.SelectorExpr:
			skip[x.Sel] = true
			if id, ok := x.X.(*ast.Ident); ok {
				if path, ok := imports[id.Name]; ok {
					skip[id] = true
					if isImportStarter(path, x.Sel.Name) {
						r.ext = append(r.ext, path+"."+x.Sel.Name)
					}
				}
			}
		case *ast.CompositeLit:
			for _, e := range x.Elts {
				if kv, ok := e.(*ast.KeyValueExpr); ok {
					if id, ok := kv.Key.(*ast.Ident); ok {
						skip[id] = true
					}
				}
			}
		case *ast.Field:
			for _, id := range x.Names {
				skip[id] = true
			}
		case *ast.LabeledStmt:
			skip[x.Label] = true
		case *ast.BranchStmt:
			if x.Label != nil {
				skip[x.Label] = true
			}
		case *ast.Ident:
			if !skip[x] {
				r.local = append(r.local, x.Name)
			}
		}
		return true
	})
	return r
}

// isTestFunc reports whether fd is a top-level test, and its *testing.T
// parameter's name. It is go test's own rule (cmd/go/internal/load,
// isTestFunc): a Test name and one parameter of type *T or *<anything>.T. In
// a package that compiles that parameter is testing.T however it is spelled —
// a renamed import (*tt.T) or a type alias (type T = testing.T; *T) — so
// nothing go test runs is left unclassified.
func isTestFunc(fd *ast.FuncDecl) (string, bool) {
	name := fd.Name.Name
	if fd.Recv != nil || fd.Body == nil || !strings.HasPrefix(name, "Test") {
		return "", false
	}
	if r, _ := utf8.DecodeRuneInString(name[len("Test"):]); unicode.IsLower(r) {
		return "", false
	}
	p := fd.Type.Params.List
	if len(p) != 1 || len(p[0].Names) > 1 {
		return "", false
	}
	star, ok := p[0].Type.(*ast.StarExpr)
	if !ok {
		return "", false
	}
	switch x := star.X.(type) {
	case *ast.Ident:
		ok = x.Name == "T"
	case *ast.SelectorExpr:
		ok = x.Sel.Name == "T"
	default:
		ok = false
	}
	if !ok {
		return "", false
	}
	if len(p[0].Names) == 0 {
		return "_", true
	}
	return p[0].Names[0].Name, true
}

// isGuard reports whether s is exactly the hang guard for the test parameter
// param:
//
//	if !isolated(param, <limit>) {
//		return
//	}
func isGuard(s ast.Stmt, param string) bool {
	is, ok := s.(*ast.IfStmt)
	if !ok || is.Init != nil || is.Else != nil || len(is.Body.List) != 1 {
		return false
	}
	if ret, ok := is.Body.List[0].(*ast.ReturnStmt); !ok || len(ret.Results) != 0 {
		return false
	}
	not, ok := is.Cond.(*ast.UnaryExpr)
	if !ok || not.Op != token.NOT {
		return false
	}
	call, ok := not.X.(*ast.CallExpr)
	if !ok || len(call.Args) != 2 {
		return false
	}
	if fn, ok := call.Fun.(*ast.Ident); !ok || fn.Name != guardName {
		return false
	}
	arg, ok := call.Args[0].(*ast.Ident)
	return ok && arg.Name == param
}

// classifyTests resolves every top-level test of files against the
// package-level graph, and returns the names the package declares.
func classifyTests(fset *token.FileSet, files []*ast.File) ([]tripTest, map[string]bool) {
	declared := map[string]bool{}
	nodes := map[string]refs{} // build-tagged variants of one name are unioned
	add := func(name string, r refs) {
		declared[name] = true
		n := nodes[name]
		n.local = append(n.local, r.local...)
		n.ext = append(n.ext, r.ext...)
		nodes[name] = n
	}
	type testDecl struct {
		fd      *ast.FuncDecl
		param   string
		imports map[string]string
	}
	var decls []testDecl
	for _, f := range files {
		imports := importNames(f)
		for _, d := range f.Decls {
			switch d := d.(type) {
			case *ast.FuncDecl:
				if d.Recv != nil || d.Body == nil {
					continue
				}
				if param, ok := isTestFunc(d); ok {
					decls = append(decls, testDecl{d, param, imports})
				}
				add(d.Name.Name, refsOf(d.Body, imports))
			case *ast.GenDecl:
				for _, s := range d.Specs {
					switch s := s.(type) {
					case *ast.ValueSpec:
						var r refs
						for _, v := range s.Values {
							vr := refsOf(v, imports)
							r.local, r.ext = append(r.local, vr.local...), append(r.ext, vr.ext...)
						}
						for _, id := range s.Names {
							add(id.Name, r)
						}
					case *ast.TypeSpec:
						declared[s.Name.Name] = true
					}
				}
			}
		}
	}

	starter := map[string]bool{}
	for _, s := range localStarters {
		starter[s] = true
	}
	// next[n] is the reference node n reaches a starter through. It is only
	// ever set to a reference that already reaches one, so a chain ends.
	next := map[string]string{}
	reaches := func(name string) bool { return starter[name] || next[name] != "" }
	firstReach := func(r refs) string {
		if len(r.ext) > 0 {
			return r.ext[0]
		}
		for _, l := range r.local {
			if l != guardName && reaches(l) {
				return l
			}
		}
		return ""
	}
	names := slices.Sorted(maps.Keys(nodes))
	for changed := true; changed; {
		changed = false
		for _, n := range names {
			if reaches(n) {
				continue
			}
			if w := firstReach(nodes[n]); w != "" {
				next[n], changed = w, true
			}
		}
	}

	var tests []tripTest
	for _, d := range decls {
		tt := tripTest{
			name:    d.fd.Name.Name,
			param:   d.param,
			pos:     fset.Position(d.fd.Pos()),
			decl:    d.fd,
			guarded: len(d.fd.Body.List) > 0 && isGuard(d.fd.Body.List[0], d.param),
		}
		for w := firstReach(refsOf(d.fd.Body, d.imports)); w != ""; w = next[w] {
			tt.via = append(tt.via, w)
			if starter[w] {
				break
			}
		}
		tests = append(tests, tt)
	}
	return tests, declared
}

// isolationFindings is every violation among tests, sorted by test.
func isolationFindings(tests []tripTest, allow map[string]string) []tripFinding {
	var out []tripFinding
	byName := map[string][]tripTest{}
	for _, tt := range tests {
		byName[tt.name] = append(byName[tt.name], tt)
		_, allowed := allow[tt.name]
		switch {
		case tt.via != nil && !tt.guarded && !allowed:
			out = append(out, tripFinding{tt.name, findUnguarded, fmt.Sprintf(
				"%s: %s starts a process (%s) but does not begin with the hang guard\n"+
					"\tif !isolated(%s, hangLimit) {\n\t\treturn\n\t}\n"+
					"(or, for one of the watchdog's own controls, an isolationAllow entry with its reason)",
				tt.pos, tt.name, strings.Join(append([]string{tt.name}, tt.via...), " → "), tt.param)})
		case tt.via == nil && tt.guarded:
			out = append(out, tripFinding{tt.name, findUnseen, fmt.Sprintf(
				"%s: %s is guarded, but the tripwire sees no process start in it: add the call it starts "+
					"processes through to localStarters or importStarters, or drop the guard", tt.pos, tt.name)})
		}
	}
	for _, name := range slices.Sorted(maps.Keys(allow)) {
		switch ts := byName[name]; {
		case len(ts) == 0:
			out = append(out, tripFinding{name, findStaleAllow,
				fmt.Sprintf("isolationAllow names %s, which is not a test of this package", name)})
		case !slices.ContainsFunc(ts, func(tt tripTest) bool { return tt.via != nil }):
			out = append(out, tripFinding{name, findStaleAllow,
				fmt.Sprintf("isolationAllow names %s, which starts no process the tripwire can see", name)})
		}
	}
	slices.SortStableFunc(out, func(a, b tripFinding) int { return strings.Compare(a.test, b.test) })
	return out
}

// findingKeys is each finding as test:kind.
func findingKeys(fs []tripFinding) []string {
	keys := []string{}
	for _, f := range fs {
		keys = append(keys, f.test+":"+f.kind)
	}
	slices.Sort(keys)
	return keys
}

// runnerSources reads every Go source file of this package's directory.
func runnerSources(t *testing.T) map[string][]byte {
	t.Helper()
	ents, err := os.ReadDir(".")
	if err != nil {
		t.Fatal(err)
	}
	srcs := map[string][]byte{}
	for _, e := range ents {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") {
			continue
		}
		b, err := os.ReadFile(e.Name())
		if err != nil {
			t.Fatal(err)
		}
		srcs[e.Name()] = b
	}
	return srcs
}

func TestIsolationTripwire(t *testing.T) {
	fset := token.NewFileSet()
	files, err := parseRunnerPkg(fset, runnerSources(t))
	if err != nil {
		t.Fatal(err)
	}
	tests, declared := classifyTests(fset, files)
	for _, f := range isolationFindings(tests, isolationAllow) {
		t.Error(f.msg)
	}
	for _, s := range localStarters {
		if !declared[s] {
			t.Errorf("localStarters names %s, which this package does not declare", s)
		}
	}
	var guarded, pure, allowed int
	self := false
	for _, tt := range tests {
		_, a := isolationAllow[tt.name]
		switch {
		case tt.guarded:
			guarded++
		case a:
			allowed++
		case tt.via == nil:
			pure++
		}
		self = self || tt.name == "TestIsolationTripwire"
	}
	if guarded == 0 || !self {
		t.Fatalf("vacuous: %d guarded tests, this test found: %v — the package's sources were not read", guarded, self)
	}
	t.Logf("%d guarded, %d pure, %d allowlisted tests", guarded, pure, allowed)
}

// Negative controls: a tripwire that flags nothing proves nothing. Every
// shape of an unguarded process start must be caught and every benign
// look-alike must not; and on the real tree, every guarded test must be
// caught once its guard is gone.
func TestIsolationTripwireCatches(t *testing.T) {
	srcs := map[string][]byte{
		"helpers.go": []byte(`package runner

import (
	osexec "os/exec"
	"testing"
	"time"
)

const hangLimit = time.Second

func Run() error { return nil }

func runAll(t *testing.T) { _ = Run() }
func helper(t *testing.T) { runAll(t) }
func deeper(t *testing.T) { helper(t) }

// isolated starts a process itself; the tripwire must not count it.
func isolated(t *testing.T, limit time.Duration) bool { return osexec.Command("true").Run() == nil }

var starter = osexec.Command

type spec struct{ Run string }
`),
		"x_test.go": []byte(`package runner

import (
	sh "os/exec"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/gitx"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

func TestDirect(t *testing.T) { runAll(t) }

func TestViaHelpers(t *testing.T) { deeper(t) }

func TestGuardNotFirst(t *testing.T) {
	t.Log("first")
	if !isolated(t, hangLimit) {
		return
	}
	runAll(t)
}

func TestInSubtest(t *testing.T) {
	t.Run("a", func(t *testing.T) { runAll(t) })
}

func TestFuncValue(t *testing.T) {
	for _, f := range []func(*testing.T){runAll} {
		f(t)
	}
}

func TestRenamedImport(t *testing.T) { _ = sh.Command("true").Run() }

func TestPkgVar(t *testing.T) { _ = starter("true").Run() }

func TestFixture(t *testing.T) { _ = fixture.New(t) }

func TestGitx(t *testing.T) { _, _ = gitx.Repo{Dir: "."}.Run(nil, "status") }

func TestPositiveGuard(t *testing.T) {
	if isolated(t, hangLimit) {
		runAll(t)
	}
}

func TestGuardWrongT(tt *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	runAll(tt)
}

func TestGuardedPure(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	if 1+1 != 2 {
		t.Fatal("arithmetic")
	}
}

func TestGuarded(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	runAll(t)
}

func TestAllowed(t *testing.T) { runAll(t) }

func TestPure(t *testing.T) {
	t.Run("Run", func(t *testing.T) {})
	_ = spec{Run: "x"}
Run:
	for range 1 {
		continue Run
	}
}

func TestPureListed(t *testing.T) {}
`),
		"alias_test.go": []byte(`package runner

import tt "testing"

func TestAlias(t *tt.T) { runAll(t) }

func TestAliasGuarded(t *tt.T) {
	if !isolated(t, hangLimit) {
		return
	}
	runAll(t)
}
`),
		"typealias_test.go": []byte(`package runner

import "testing"

type T = testing.T

func TestTypeAlias(t *T) { Run() }

// Not a test for go test either: one parameter, but no *T.
func TestNotATest(m *testing.M) { runAll(nil) }
`),
	}
	fset := token.NewFileSet()
	files, err := parseRunnerPkg(fset, srcs)
	if err != nil {
		t.Fatal(err)
	}
	tests, _ := classifyTests(fset, files)
	allow := map[string]string{"TestAllowed": "a control", "TestPureListed": "stale", "TestNoSuchTest": "stale"}
	got := findingKeys(isolationFindings(tests, allow))
	want := []string{
		"TestAlias:" + findUnguarded,
		"TestDirect:" + findUnguarded,
		"TestFixture:" + findUnguarded,
		"TestFuncValue:" + findUnguarded,
		"TestGitx:" + findUnguarded,
		"TestGuardNotFirst:" + findUnguarded,
		"TestGuardWrongT:" + findUnguarded,
		"TestGuardedPure:" + findUnseen,
		"TestInSubtest:" + findUnguarded,
		"TestNoSuchTest:" + findStaleAllow,
		"TestPkgVar:" + findUnguarded,
		"TestPositiveGuard:" + findUnguarded,
		"TestPureListed:" + findStaleAllow,
		"TestRenamedImport:" + findUnguarded,
		"TestTypeAlias:" + findUnguarded,
		"TestViaHelpers:" + findUnguarded,
	}
	if !slices.Equal(got, want) {
		t.Fatalf("flagged %q\nwant    %q", got, want)
	}
	for _, tt := range tests {
		if tt.name == "TestViaHelpers" {
			if want := []string{"deeper", "helper", "runAll", "Run"}; !slices.Equal(tt.via, want) {
				t.Errorf("TestViaHelpers reaches through %q, want %q", tt.via, want)
			}
		}
	}

	// A dot import is refused, not skipped: its starters would arrive
	// unqualified.
	for _, path := range []string{"os/exec", "testing"} {
		src := "package runner\n\nimport . \"" + path + "\"\n\nfunc TestDot(t *T) { _ = Command(\"true\").Run() }\n"
		if _, err := parseRunnerPkg(token.NewFileSet(), map[string][]byte{"dot_test.go": []byte(src)}); err == nil || !strings.Contains(err.Error(), "dot import") {
			t.Errorf("dot import of %s: err %v, want a dot-import refusal", path, err)
		}
	}

	// The red proof on the real tree: removing a guard leaves the tree's own
	// findings plus exactly that test.
	fset = token.NewFileSet()
	files, err = parseRunnerPkg(fset, runnerSources(t))
	if err != nil {
		t.Fatal(err)
	}
	tests, _ = classifyTests(fset, files)
	base := findingKeys(isolationFindings(tests, isolationAllow))
	n := 0
	for _, tt := range tests {
		if !tt.guarded {
			continue
		}
		n++
		body := tt.decl.Body.List
		tt.decl.Body.List = body[1:]
		mutant, _ := classifyTests(fset, files)
		tt.decl.Body.List = body
		got := findingKeys(isolationFindings(mutant, isolationAllow))
		want := append(slices.Clone(base), tt.name+":"+findUnguarded)
		slices.Sort(want)
		if !slices.Equal(got, want) {
			t.Errorf("%s without its guard: flagged %q, want %q", tt.name, got, want)
		}
	}
	if n == 0 {
		t.Fatal("no guarded test in the real tree: the red proof is vacuous")
	}
}
