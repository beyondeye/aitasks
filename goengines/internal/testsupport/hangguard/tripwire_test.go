package hangguard

// The hang guard's tripwire.
//
// A test that starts a process must begin with the hang guard (Isolated), or
// a regression that makes it hang waits for go test's own timeout. Nothing in
// the language enforces that convention, so TestIsolationTripwire does, over
// every package tripwirePackages lists: it parses every source file of each —
// test and non-test, whatever its build constraint — and fails a top-level
// test that reaches a process start, transitively through package-level
// functions and variables, unless the guard is its first statement or the
// test is on its entry's allow list. ci/preflight.sh runs it alone before the
// suite: inside `go test ./...` it would run in package order, after tests
// that could already hang, and its failure would not stop them. A package
// opts in with one tripwirePackages entry; TestIsolationTripwireImports fails
// a package that imports the guard without one, and a non-test file that
// imports it at all.
//
// Like the Invariant 5 tripwire (goengines/guards_test.go) it is lexical: it
// resolves names, not types. A reference counts wherever an identifier could
// name a package-level declaration — a call, a function value in a table, a
// closure — and another package's name counts by its import path, whatever
// the import is called. Calls through methods, interfaces and func-typed
// fields are not followed, which is why an entry declares localStarters: the
// package's own entry points to a process that resolution cannot see through
// (runner's Run goes through the Executor, Load through Runner.call and gitx).
// Every other entry's localStarters count as that package's starters, so a
// listed package calling runner.Run is seen. A test that starts a process only
// through an undeclared such call is not seen; a guarded test the tripwire
// sees no process start in fails too, so the starter lists cannot rot under
// the tests that are guarded.

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"testing"
	"unicode"
	"unicode/utf8"
)

const modPath = "github.com/beyondeye/aitasks/goengines"

// guardPath is this package: <guardPath>.Isolated is the hang guard.
const guardPath = modPath + "/" + guardDir

const guardDir = "internal/testsupport/hangguard"

// tripPackage is one package the tripwire covers.
type tripPackage struct {
	dir  string // module-relative
	name string // its package clause; a file of any other package is refused
	// localStarters are the package's entry points to a process — or to a
	// session sweep, which can hang without starting one — that name
	// resolution cannot see through.
	localStarters []string
	// allow are the process-starting tests that must not isolate
	// themselves, each with its reason.
	allow map[string]string
}

// tripwirePackages are the packages whose tests the tripwire covers. A
// package whose tests start processes opts in with one entry.
var tripwirePackages = []tripPackage{
	{dir: "internal/testmap/runner", name: "runner", localStarters: []string{"Run", "Load", "sweepSession"}},
	{dir: guardDir, name: "hangguard", allow: map[string]string{
		"TestIsolationControls":     "the watchdog's own negative controls: they launch runChild themselves and must see the HANG and LEAK reports it produces",
		"TestReapMarkedUncertainty": "drives reapMarked against processes it starts; isolated, it would run under the cleanup it tests",
	}},
	{dir: guardDir + "/tripfixture", name: "tripfixture", localStarters: []string{"startAll"}},
}

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

// startersFor is p's import starters: importStarters plus every other entry
// of pkgs' localStarters, qualified by that entry's import path.
func startersFor(p tripPackage, pkgs []tripPackage) []string {
	s := slices.Clone(importStarters)
	for _, o := range pkgs {
		if o.dir == p.dir {
			continue
		}
		for _, n := range o.localStarters {
			s = append(s, modPath+"/"+o.dir+"."+n)
		}
	}
	return s
}

// guardName is a package-local wrapper of the hang guard, guardFunc the guard
// itself. Both start a process (runChild), so no reference to either counts:
// counting one would make every guarded test look process-starting for
// carrying the guard.
const (
	guardName = "isolated"
	guardFunc = "Isolated"
)

// The kinds of finding.
const (
	findUnguarded  = "unguarded"   // starts a process without the guard
	findUnseen     = "unseen"      // guarded, but no process start is seen
	findStaleAllow = "stale-allow" // an allow entry with nothing to allow
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

// parsePkg parses one package's sources, keyed by file name. A file of
// another package than name is refused — an external test package would
// escape the tripwire unseen — and so is a dot import: its names arrive
// unqualified, so a starter (Command) could not be told from a name of this
// package.
func parsePkg(fset *token.FileSet, name string, srcs map[string][]byte) ([]*ast.File, error) {
	var files []*ast.File
	for _, fn := range slices.Sorted(maps.Keys(srcs)) {
		f, err := parser.ParseFile(fset, fn, srcs[fn], parser.SkipObjectResolution)
		if err != nil {
			return nil, err
		}
		if f.Name.Name != name {
			return nil, fmt.Errorf("%s: package %s, which the tripwire does not cover", fn, f.Name.Name)
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

func isImportStarter(starters []string, path, name string) bool {
	return slices.Contains(starters, path+"."+name) || slices.Contains(starters, path+".*")
}

// refsOf collects the references in n. An identifier counts unless it is a
// selector's name (t.Run is not Run), a struct literal's key, a field or
// parameter name, or a label; a selector on an import counts by its path.
func refsOf(n ast.Node, imports map[string]string, starters []string) refs {
	var r refs
	skip := map[*ast.Ident]bool{}
	ast.Inspect(n, func(x ast.Node) bool {
		switch x := x.(type) {
		case *ast.SelectorExpr:
			skip[x.Sel] = true
			if id, ok := x.X.(*ast.Ident); ok {
				if path, ok := imports[id.Name]; ok {
					skip[id] = true
					if isImportStarter(starters, path, x.Sel.Name) {
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
// param, called either through a package-local wrapper or through this
// package by its import path (whatever the import is called):
//
//	if !isolated(param, <limit>) {        if !hangguard.Isolated(param, <limit>) {
//		return                                return
//	}                                     }
func isGuard(s ast.Stmt, param string, imports map[string]string) bool {
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
	switch fn := call.Fun.(type) {
	case *ast.Ident:
		if fn.Name != guardName {
			return false
		}
	case *ast.SelectorExpr:
		id, ok := fn.X.(*ast.Ident)
		if !ok || imports[id.Name] != guardPath || fn.Sel.Name != guardFunc {
			return false
		}
	default:
		return false
	}
	arg, ok := call.Args[0].(*ast.Ident)
	return ok && arg.Name == param
}

// classifyTests resolves every top-level test of files against the
// package-level graph, with the package's localStarters and its import
// starters, and returns the names the package declares.
func classifyTests(fset *token.FileSet, files []*ast.File, localStarters, starters []string) ([]tripTest, map[string]bool) {
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
				add(d.Name.Name, refsOf(d.Body, imports, starters))
			case *ast.GenDecl:
				for _, s := range d.Specs {
					switch s := s.(type) {
					case *ast.ValueSpec:
						var r refs
						for _, v := range s.Values {
							vr := refsOf(v, imports, starters)
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
			guarded: len(d.fd.Body.List) > 0 && isGuard(d.fd.Body.List[0], d.param, d.imports),
		}
		for w := firstReach(refsOf(d.fd.Body, d.imports, starters)); w != ""; w = next[w] {
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
					"(or hangguard.Isolated(%s, <limit>); for one of the watchdog's own controls, "+
					"an allow entry in its tripwirePackages entry, with its reason)",
				tt.pos, tt.name, strings.Join(append([]string{tt.name}, tt.via...), " → "), tt.param, tt.param)})
		case tt.via == nil && tt.guarded:
			out = append(out, tripFinding{tt.name, findUnseen, fmt.Sprintf(
				"%s: %s is guarded, but the tripwire sees no process start in it: add the call it starts "+
					"processes through to its entry's localStarters or to importStarters, or drop the guard", tt.pos, tt.name)})
		}
	}
	for _, name := range slices.Sorted(maps.Keys(allow)) {
		switch ts := byName[name]; {
		case len(ts) == 0:
			out = append(out, tripFinding{name, findStaleAllow,
				fmt.Sprintf("the allow list names %s, which is not a test of this package", name)})
		case !slices.ContainsFunc(ts, func(tt tripTest) bool { return tt.via != nil }):
			out = append(out, tripFinding{name, findStaleAllow,
				fmt.Sprintf("the allow list names %s, which starts no process the tripwire can see", name)})
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

// moduleRoot is the goengines module's directory: the nearest ancestor of the
// test's directory holding a go.mod that declares modPath.
func moduleRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	for {
		if b, err := os.ReadFile(filepath.Join(dir, "go.mod")); err == nil {
			for _, line := range strings.Split(string(b), "\n") {
				if f := strings.Fields(line); len(f) == 2 && f[0] == "module" {
					if f[1] != modPath {
						t.Fatalf("%s/go.mod declares module %s, not %s", dir, f[1], modPath)
					}
					return dir
				}
			}
			t.Fatalf("%s/go.mod declares no module", dir)
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			t.Fatal("no go.mod above the test's directory")
		}
		dir = parent
	}
}

// packageSources reads every Go source file of the module-relative directory
// dir, keyed by its module-relative path.
func packageSources(t *testing.T, root, dir string) map[string][]byte {
	t.Helper()
	ents, err := os.ReadDir(filepath.Join(root, dir))
	if err != nil {
		t.Fatal(err)
	}
	srcs := map[string][]byte{}
	for _, e := range ents {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") {
			continue
		}
		b, err := os.ReadFile(filepath.Join(root, dir, e.Name()))
		if err != nil {
			t.Fatal(err)
		}
		srcs[dir+"/"+e.Name()] = b
	}
	if len(srcs) == 0 {
		t.Fatalf("%s holds no Go source: its tripwirePackages entry is stale", dir)
	}
	return srcs
}

// classifyEntry parses and classifies p's package in the module at root.
func classifyEntry(t *testing.T, root string, p tripPackage) ([]tripTest, map[string]bool, *token.FileSet, []*ast.File) {
	t.Helper()
	fset := token.NewFileSet()
	files, err := parsePkg(fset, p.name, packageSources(t, root, p.dir))
	if err != nil {
		t.Fatal(err)
	}
	tests, declared := classifyTests(fset, files, p.localStarters, startersFor(p, tripwirePackages))
	return tests, declared, fset, files
}

func TestIsolationTripwire(t *testing.T) {
	root := moduleRoot(t)
	self := false
	dirs := map[string]bool{}
	for _, p := range tripwirePackages {
		if dirs[p.dir] {
			t.Errorf("tripwirePackages lists %s twice", p.dir)
		}
		dirs[p.dir] = true
		tests, declared, _, _ := classifyEntry(t, root, p)
		for _, f := range isolationFindings(tests, p.allow) {
			t.Error(f.msg)
		}
		for _, s := range p.localStarters {
			if !declared[s] {
				t.Errorf("%s: localStarters names %s, which the package does not declare", p.dir, s)
			}
		}
		var guarded, pure, allowed int
		for _, tt := range tests {
			_, a := p.allow[tt.name]
			switch {
			case tt.guarded:
				guarded++
			case a:
				allowed++
			case tt.via == nil:
				pure++
			}
			self = self || (p.dir == guardDir && tt.name == "TestIsolationTripwire")
		}
		if guarded+allowed == 0 {
			t.Errorf("%s: vacuous: no guarded or allowlisted test — the entry covers nothing", p.dir)
		}
		t.Logf("%s: %d guarded, %d pure, %d allowlisted tests", p.dir, guarded, pure, allowed)
	}
	if !self {
		t.Fatal("vacuous: the tripwire did not find itself in " + guardDir + " — the sources were not read")
	}
}

// Negative controls: a tripwire that flags nothing proves nothing. Every
// shape of an unguarded process start must be caught and every benign
// look-alike must not; and on the real tree, every guarded test of every
// entry must be caught once its guard is gone, and once only its guard is
// left.
func TestIsolationTripwireCatches(t *testing.T) {
	runner := tripwirePackages[0]
	if runner.name != "runner" {
		t.Fatalf("tripwirePackages[0] is %s, want runner", runner.name)
	}
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
		// The guard called through this package, by any import name; a
		// look-alike from another package or under another name is not it.
		"selector_test.go": []byte(`package runner

import (
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
	hg "github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

func TestSelectorGuarded(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
	runAll(t)
}

func TestRenamedSelectorGuarded(t *testing.T) {
	if !hg.Isolated(t, hangLimit) {
		return
	}
	runAll(t)
}

func TestSelectorGuardedPure(t *testing.T) {
	if !hangguard.Isolated(t, hangLimit) {
		return
	}
}

func TestWrongPackageGuard(t *testing.T) {
	if !fixture.Isolated(t, hangLimit) {
		return
	}
	runAll(t)
}

func TestWrongNameGuard(t *testing.T) {
	if !hangguard.Isolate(t, hangLimit) {
		return
	}
	runAll(t)
}
`),
	}
	fset := token.NewFileSet()
	files, err := parsePkg(fset, "runner", srcs)
	if err != nil {
		t.Fatal(err)
	}
	tests, _ := classifyTests(fset, files, runner.localStarters, startersFor(runner, tripwirePackages))
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
		"TestSelectorGuardedPure:" + findUnseen,
		"TestTypeAlias:" + findUnguarded,
		"TestViaHelpers:" + findUnguarded,
		"TestWrongNameGuard:" + findUnguarded,
		"TestWrongPackageGuard:" + findUnguarded,
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
	// unqualified. A file of another package is refused too.
	for _, path := range []string{"os/exec", "testing"} {
		src := "package runner\n\nimport . \"" + path + "\"\n\nfunc TestDot(t *T) { _ = Command(\"true\").Run() }\n"
		if _, err := parsePkg(token.NewFileSet(), "runner", map[string][]byte{"dot_test.go": []byte(src)}); err == nil || !strings.Contains(err.Error(), "dot import") {
			t.Errorf("dot import of %s: err %v, want a dot-import refusal", path, err)
		}
	}
	if _, err := parsePkg(token.NewFileSet(), "runner", map[string][]byte{"ext_test.go": []byte("package runner_test\n")}); err == nil || !strings.Contains(err.Error(), "does not cover") {
		t.Errorf("external test package: err %v, want a refusal", err)
	}

	// Another listed package's localStarters count by its import path: a
	// package calling runner.Run starts a process once runner is listed, and
	// is not seen to without the entry.
	other := tripPackage{dir: "internal/other", name: "other"}
	osrcs := map[string][]byte{"o_test.go": []byte(`package other

import (
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

func TestCrossRun(t *testing.T) { _ = runner.Run(nil) }

func TestCrossPure(t *testing.T) { _ = runner.Config{} }
`)}
	ofset := token.NewFileSet()
	ofiles, err := parsePkg(ofset, "other", osrcs)
	if err != nil {
		t.Fatal(err)
	}
	listed, _ := classifyTests(ofset, ofiles, nil, startersFor(other, tripwirePackages))
	if got, want := findingKeys(isolationFindings(listed, nil)), []string{"TestCrossRun:" + findUnguarded}; !slices.Equal(got, want) {
		t.Errorf("with runner listed: flagged %q, want %q", got, want)
	}
	unlisted, _ := classifyTests(ofset, ofiles, nil, startersFor(other, tripwirePackages[1:]))
	if got := findingKeys(isolationFindings(unlisted, nil)); len(got) != 0 {
		t.Errorf("without runner's entry: flagged %q, want nothing", got)
	}

	// The red proofs on the real tree: removing a guard leaves the tree's
	// own findings plus exactly that test as unguarded, and leaving only the
	// guard leaves them plus exactly that test as unseen.
	root := moduleRoot(t)
	n := 0
	for _, p := range tripwirePackages {
		tests, _, fset, files := classifyEntry(t, root, p)
		starters := startersFor(p, tripwirePackages)
		base := findingKeys(isolationFindings(tests, p.allow))
		mutant := func(name, kind string) {
			t.Helper()
			m, _ := classifyTests(fset, files, p.localStarters, starters)
			got := findingKeys(isolationFindings(m, p.allow))
			want := append(slices.Clone(base), name+":"+kind)
			slices.Sort(want)
			if !slices.Equal(got, want) {
				t.Errorf("%s: %s %s mutant: flagged %q, want %q", p.dir, name, kind, got, want)
			}
		}
		for _, tt := range tests {
			if !tt.guarded {
				continue
			}
			n++
			body := tt.decl.Body.List
			tt.decl.Body.List = body[1:]
			mutant(tt.name, findUnguarded)
			tt.decl.Body.List = body[:1]
			mutant(tt.name, findUnseen)
			tt.decl.Body.List = body
		}
		// An entry's own localStarters are what make a start through them
		// seen: without startAll, the fixture's test through it is unseen.
		if p.name == "tripfixture" {
			fewer := slices.DeleteFunc(slices.Clone(p.localStarters), func(s string) bool { return s == "startAll" })
			m, _ := classifyTests(fset, files, fewer, starters)
			got := findingKeys(isolationFindings(m, p.allow))
			want := append(slices.Clone(base), "TestGuardedLocalStarter:"+findUnseen)
			slices.Sort(want)
			if !slices.Equal(got, want) {
				t.Errorf("%s without startAll: flagged %q, want %q", p.dir, got, want)
			}
		}
	}
	if n == 0 {
		t.Fatal("no guarded test in the real tree: the red proof is vacuous")
	}
}

// The kinds of import finding.
const (
	findNonTestImport  = "non-test-import" // a non-test file imports the guard
	findUnlistedImport = "unlisted-import" // a test file imports it from an unlisted package
)

// importFindings flags, among files (module-relative path → source), a
// non-test file that imports the guard — it is test support, never shipped —
// and a test file that imports it from a directory listed does not hold: that
// package's tests would escape the tripwire. It returns how many listed test
// files import the guard.
func importFindings(files map[string][]byte, listed map[string]bool) ([]tripFinding, int, error) {
	var out []tripFinding
	used := 0
	for _, path := range slices.Sorted(maps.Keys(files)) {
		f, err := parser.ParseFile(token.NewFileSet(), path, files[path], parser.ImportsOnly)
		if err != nil {
			return nil, 0, err
		}
		if !slices.ContainsFunc(f.Imports, func(is *ast.ImportSpec) bool {
			p, err := strconv.Unquote(is.Path.Value)
			return err == nil && p == guardPath
		}) {
			continue
		}
		dir := filepath.ToSlash(filepath.Dir(path))
		switch {
		case !strings.HasSuffix(path, "_test.go"):
			out = append(out, tripFinding{path, findNonTestImport, fmt.Sprintf(
				"%s imports %s, which is test support: only _test.go files may import it", path, guardPath)})
		case !listed[dir]:
			out = append(out, tripFinding{path, findUnlistedImport, fmt.Sprintf(
				"%s imports the hang guard, but %s has no tripwirePackages entry: its tests would escape the tripwire", path, dir)})
		default:
			used++
		}
	}
	return out, used, nil
}

// moduleFiles reads every Go file of the module at root, keyed by its
// module-relative path, skipping what the go tool skips: testdata, vendor,
// directories starting with . or _, and nested modules.
func moduleFiles(t *testing.T, root string) map[string][]byte {
	t.Helper()
	files := map[string][]byte{}
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			if path == root {
				return nil
			}
			n := d.Name()
			if n == "testdata" || n == "vendor" || strings.HasPrefix(n, ".") || strings.HasPrefix(n, "_") {
				return filepath.SkipDir
			}
			if _, err := os.Stat(filepath.Join(path, "go.mod")); err == nil {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") {
			return nil
		}
		b, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		files[filepath.ToSlash(rel)] = b
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return files
}

func TestIsolationTripwireImports(t *testing.T) {
	listed := map[string]bool{}
	for _, p := range tripwirePackages {
		listed[p.dir] = true
	}

	// The control first: a finding that cannot fire proves nothing.
	imp := func(pkg, name string) []byte {
		return []byte("package " + pkg + "\n\nimport " + name + " \"" + guardPath + "\"\n")
	}
	got, used, err := importFindings(map[string][]byte{
		"internal/a/a.go":      imp("a", ""),
		"internal/b/b.go":      imp("b", "hg"),
		"internal/c/c_test.go": imp("c", ""),
		"internal/d/d_test.go": imp("d", ""),
		"internal/e/e.go":      []byte("package e\n\nimport \"os\"\n"),
	}, map[string]bool{"internal/d": true})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"internal/a/a.go:" + findNonTestImport,
		"internal/b/b.go:" + findNonTestImport,
		"internal/c/c_test.go:" + findUnlistedImport,
	}
	if keys := findingKeys(got); !slices.Equal(keys, want) || used != 1 {
		t.Fatalf("control: flagged %q (%d listed uses), want %q (1)", keys, used, want)
	}

	got, used, err = importFindings(moduleFiles(t, moduleRoot(t)), listed)
	if err != nil {
		t.Fatal(err)
	}
	for _, f := range got {
		t.Error(f.msg)
	}
	if used == 0 {
		t.Fatal("vacuous: no listed test file imports the hang guard — the module was not read")
	}
	t.Logf("%d listed test files import the hang guard", used)
}
