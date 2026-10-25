//go:build unix

package builtin

import (
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"testing"
)

// The adapter-file tripwire: an adapter runs every tool through
// Env.Supervise (contained, bounded, under the recursion marker) and never
// starts a process itself. It is lexical, like the hang-guard and
// Invariant 5 tripwires: it resolves import names, not types.

// scaffoldFiles are the scaffold's own non-test files: env.go is where
// Supervise calls procsup.Run. Every other non-test file of the package is
// an adapter file and is checked — a new adapter is covered without an edit
// here.
var scaffoldFiles = []string{"builtin.go", "env.go", "results.go", "split.go"}

// forbiddenStarters are the selectors an adapter file may not use, as
// <import path>.<name>; <import path>.* is every name of that package but
// the allowed ones.
var (
	forbiddenImports   = []string{"os/exec"}
	forbiddenSelectors = []string{
		"os.StartProcess",
		"syscall.ForkExec", "syscall.StartProcess", "syscall.Exec",
		modPath + "/internal/procsup.Start", modPath + "/internal/procsup.Run",
		modPath + "/internal/testmap/runner.Run", modPath + "/internal/testmap/runner.Load",
		modPath + "/internal/gitx.*", // gitx exists to run git
	}
	allowedSelectors = []string{modPath + "/internal/gitx.Env"} // a pure environment builder
)

const modPath = "github.com/beyondeye/aitasks/goengines"

// directExecFindings returns the direct process starts in one Go source.
func directExecFindings(name string, src []byte) ([]string, error) {
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, name, src, parser.SkipObjectResolution)
	if err != nil {
		return nil, err
	}
	var out []string
	local := map[string]string{} // import name -> path
	for _, im := range f.Imports {
		p, _ := strconv.Unquote(im.Path.Value)
		if slices.Contains(forbiddenImports, p) {
			out = append(out, fset.Position(im.Pos()).String()+": imports "+p)
		}
		n := p[strings.LastIndex(p, "/")+1:]
		if im.Name != nil {
			n = im.Name.Name
		}
		// A dot import's names arrive unqualified, where no selector check
		// can see them (`. "syscall"` then `ForkExec(…)`): refused, whatever
		// the package, as the hang-guard tripwire refuses it.
		if n == "." {
			out = append(out, fset.Position(im.Pos()).String()+": dot import of "+p+", which the tripwire cannot resolve: import it by name")
		}
		local[n] = p
	}
	ast.Inspect(f, func(n ast.Node) bool {
		sel, ok := n.(*ast.SelectorExpr)
		if !ok {
			return true
		}
		x, ok := sel.X.(*ast.Ident)
		if !ok || local[x.Name] == "" {
			return true
		}
		full := local[x.Name] + "." + sel.Sel.Name
		if slices.Contains(allowedSelectors, full) {
			return true
		}
		if slices.Contains(forbiddenSelectors, full) || slices.Contains(forbiddenSelectors, local[x.Name]+".*") {
			out = append(out, fset.Position(sel.Pos()).String()+": "+full)
		}
		return true
	})
	return out, nil
}

// No adapter file starts a process other than through Env.Supervise.
func TestAdapterFilesNoDirectExec(t *testing.T) {
	files, err := filepath.Glob("*.go")
	if err != nil {
		t.Fatal(err)
	}
	checked := 0
	for _, f := range files {
		if strings.HasSuffix(f, "_test.go") || slices.Contains(scaffoldFiles, f) {
			continue
		}
		src, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		found, err := directExecFindings(f, src)
		if err != nil {
			t.Fatal(err)
		}
		for _, x := range found {
			t.Errorf("%s (an adapter runs tools only through Env.Supervise)", x)
		}
		checked++
	}
	if !slices.Contains(files, "bashfile.go") || checked == 0 {
		t.Fatalf("the tripwire checked %d files of %v; bashfile.go must be among them", checked, files)
	}
	for _, s := range scaffoldFiles {
		if !slices.Contains(files, s) {
			t.Errorf("scaffold file %s no longer exists: update scaffoldFiles", s)
		}
	}
}

// The tripwire catches every forbidden form and passes the sanctioned ones.
func TestAdapterTripwireCatches(t *testing.T) {
	for name, src := range map[string]string{
		"exec import":     "package builtin\nimport \"os/exec\"\nvar _ = exec.Command\n",
		"renamed exec":    "package builtin\nimport x \"os/exec\"\nvar _ = x.Command\n",
		"os.StartProcess": "package builtin\nimport \"os\"\nvar _ = os.StartProcess\n",
		"syscall":         "package builtin\nimport \"syscall\"\nfunc f() { syscall.ForkExec(\"\", nil, nil) }\n",
		"syscall.Exec":    "package builtin\nimport \"syscall\"\nvar _ = syscall.Exec\n",
		"procsup.Run":     "package builtin\nimport \"" + modPath + "/internal/procsup\"\nvar _ = procsup.Run\n",
		"procsup.Start":   "package builtin\nimport p \"" + modPath + "/internal/procsup\"\nvar _ = p.Start\n",
		"gitx":            "package builtin\nimport \"" + modPath + "/internal/gitx\"\nvar _ = gitx.Repo{}\n",
		"runner.Run":      "package builtin\nimport \"" + modPath + "/internal/testmap/runner\"\nvar _ = runner.Run\n",
		"dot syscall":     "package builtin\nimport . \"syscall\"\nfunc f() { ForkExec(\"\", nil, nil) }\n",
		"dot os":          "package builtin\nimport . \"os\"\nvar _ = StartProcess\n",
		"dot innocuous":   "package builtin\nimport . \"strings\"\nvar _ = Fields\n",
	} {
		found, err := directExecFindings(name+".go", []byte(src))
		if err != nil || len(found) == 0 {
			t.Errorf("%s: not caught (%v)", name, err)
		}
	}
	clean := "package builtin\nimport (\n\"os\"\n\"" + modPath + "/internal/gitx\"\n\"" + modPath + "/internal/procsup\"\n)\n" +
		"func f(e *Env) { _ = e.Supervise(nil, procsup.RunSpec{Env: gitx.Env()}); _ = procsup.DefaultOutputMax; os.Remove(\"\") }\n"
	if found, err := directExecFindings("clean.go", []byte(clean)); err != nil || len(found) != 0 {
		t.Errorf("clean source flagged: %v %v", found, err)
	}
}
