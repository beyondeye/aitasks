package deps

import (
	"fmt"
	"maps"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// Each supported bootstrap form makes its import a static:import fact.
func TestPythonBootstrapForms(t *testing.T) {
	cases := map[string]string{
		"tests/test_pathlib.py": lines(
			`import sys`,
			`from pathlib import Path`,
			`REPO_ROOT = Path(__file__).resolve().parent.parent`,
			`sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))`,
			`import subject`,
		),
		"tests/test_parents.py": lines(
			`import sys`,
			`from pathlib import Path`,
			`sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"))`,
			`import subject`,
		),
		"tests/test_ospath.py": lines(
			`import os, sys`,
			`sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))`,
			`import subject`,
		),
		"tests/test_loop.py": lines(
			`import sys`,
			`from pathlib import Path`,
			`ROOT = Path(__file__).resolve().parent.parent`,
			`for path in (ROOT / ".aitask-scripts" / "board", ROOT / ".aitask-scripts" / "lib"):`,
			`    sys.path.insert(0, str(path))`,
			`import subject`,
		),
		"tests/test_cwd.py": lines(
			`import sys`,
			`sys.path.insert(0, ".aitask-scripts/lib")`,
			`from subject import thing`,
		),
	}
	files := map[string]string{".aitask-scripts/lib/subject.py": "thing = 1\n"}
	for p, c := range cases {
		files[p] = c
	}
	g := scanRepo(t, repo(t, files))
	for p := range cases {
		requireEdge(t, g, p, ".aitask-scripts/lib/subject.py", Import, "import")
	}
}

// sys.path is modelled in statement order: insert(0) precedes the script's
// own directory, repeated insert(0) calls reverse, imports resolve at their
// own line with a module cache keyed by the exact fully qualified name.
func TestPythonPrecedence(t *testing.T) {
	shadow := lines(
		`import sys, os`,
		`sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))`,
		`import subject`,
		`print(subject.__file__)`,
	)
	twice := lines(
		`import sys, os`,
		`HERE = os.path.dirname(os.path.abspath(__file__))`,
		`sys.path.insert(0, os.path.join(HERE, "..", "src"))`,
		`sys.path.insert(0, os.path.join(HERE, "..", "alt"))`,
		`import subject`,
		`print(subject.__file__)`,
	)
	before := lines(
		`import sys, os`,
		`import subject`,
		`sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))`,
		`import subject`,
		`print(subject.__file__)`,
	)
	submod := lines(
		`import sys, os`,
		`sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))`,
		`import pkg`,
		`sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "alt"))`,
		`from pkg import child`,
		`import pkg.child`,
		`print(child.__file__)`,
	)
	uncertain := lines(
		`import sys, os`,
		`try:`,
		`    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))`,
		`except Exception:`,
		`    pass`,
		`import subject`,
	)
	r := repo(t, map[string]string{
		"tests/test_shadow.py":    shadow,
		"tests/test_twice.py":     twice,
		"tests/test_before.py":    before,
		"tests/test_submod.py":    submod,
		"tests/test_uncertain.py": uncertain,
		"tests/subject.py":        "",
		"src/subject.py":          "",
		"alt/subject.py":          "",
		"src/pkg/__init__.py":     "",
		"src/pkg/child.py":        "",
		"alt/pkg/__init__.py":     "",
		"alt/pkg/child.py":        "",
	})
	g := scanRepo(t, r)
	requireEdge(t, g, "tests/test_shadow.py", "src/subject.py", Import, "")
	requireEdge(t, g, "tests/test_shadow.py", "tests/subject.py", "", "")
	requireEdge(t, g, "tests/test_twice.py", "alt/subject.py", Import, "")
	requireEdge(t, g, "tests/test_twice.py", "src/subject.py", "", "")
	requireEdge(t, g, "tests/test_before.py", "tests/subject.py", Import, "")
	for _, d := range g.Static("tests/test_before.py") {
		if d.Target == "src/subject.py" {
			t.Errorf("import-before-insert claimed src/subject.py: %+v", d)
		}
	}
	requireEdge(t, g, "tests/test_submod.py", "src/pkg/__init__.py", Import, "")
	requireEdge(t, g, "tests/test_submod.py", "src/pkg/child.py", Import, "")
	for _, d := range g.Static("tests/test_submod.py") {
		if strings.HasPrefix(d.Target, "alt/") {
			t.Errorf("the loaded pkg's child was resolved elsewhere: %+v", d)
		}
	}
	// Uncertain precedence: every candidate is an edge, none is claimed.
	for _, c := range []string{"tests/subject.py", "src/subject.py"} {
		requireEdge(t, g, "tests/test_uncertain.py", c, "", "")
	}
	// Cross-check the certain cases with a real interpreter.
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Log("python3 not found: interpreter cross-check skipped")
		return
	}
	for p, want := range map[string]string{
		"tests/test_shadow.py": "src/subject.py",
		"tests/test_twice.py":  "alt/subject.py",
		"tests/test_before.py": "tests/subject.py",
		"tests/test_submod.py": "src/pkg/child.py",
	} {
		got := runPython(t, r, python, nil, p)
		if got != want {
			t.Errorf("%s: python loads %q, want %q (the model's claim)", p, got, want)
		}
	}
}

// runPython runs python with args in r (plus env) and returns the
// repository path the program prints.
func runPython(t *testing.T, r *fixture.Repo, python string, env []string, args ...string) string {
	t.Helper()
	cmd := exec.Command(python, append([]string{"-B"}, args...)...)
	cmd.Dir = r.Dir
	for _, kv := range os.Environ() {
		if !strings.HasPrefix(kv, "PYTHON") {
			cmd.Env = append(cmd.Env, kv)
		}
	}
	cmd.Env = append(cmd.Env, "PYTHONDONTWRITEBYTECODE=1")
	cmd.Env = append(cmd.Env, env...)
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("%v: %v", args, err)
	}
	abs := strings.TrimSpace(string(out))
	rel, err := filepath.Rel(r.Dir, abs)
	if err != nil {
		t.Fatal(err)
	}
	return filepath.ToSlash(rel)
}

// Imports anywhere in the module are found (functions, try blocks); a string
// or a docstring is never an import; __init__, conftest, path strings and
// spec_from_file_location targets are closure-only edges; a miss is retried
// against the source roots.
func TestPythonOtherEdges(t *testing.T) {
	r := repo(t, map[string]string{
		"tests/conftest.py": "",
		"tests/unit/test_x.py": lines(
			`"""import notamodule"""`,
			`import importlib.util`,
			`X = "import alsonot"`,
			`def f():`,
			`    import infunc`,
			`try:`,
			`    from pkg.mod import name`,
			`except ImportError:`,
			`    pass`,
			`subprocess.run(["bash", "scripts/run.sh", "--x"])`,
			`spec = importlib.util.spec_from_file_location("m", "tools/loader.py")`,
			`import rooted`,
		),
		"tests/unit/infunc.py":       "",
		"tests/unit/pkg/__init__.py": "",
		"tests/unit/pkg/mod.py":      "",
		"scripts/run.sh":             "#!/bin/sh\n",
		"tools/loader.py":            "",
		"tests/unit/notamodule.py":   "",
		"tests/unit/alsonot.py":      "",
		// lib is a source root through another file's bootstrap.
		"tests/test_boot.py": lines(`import sys`, `sys.path.insert(0, "lib")`),
		"lib/rooted.py":      "",
	})
	g := scanRepo(t, r)
	const p = "tests/unit/test_x.py"
	requireEdge(t, g, p, "tests/unit/infunc.py", Import, "")
	requireEdge(t, g, p, "tests/unit/pkg/mod.py", Import, "")
	requireEdge(t, g, p, "tests/unit/pkg/__init__.py", "", "init")
	requireEdge(t, g, p, "tests/conftest.py", "", "conftest")
	requireEdge(t, g, p, "scripts/run.sh", "", "path")
	requireEdge(t, g, p, "tools/loader.py", "", "path")
	requireEdge(t, g, p, "lib/rooted.py", "", "fallback")
	requireNoEdge(t, g, p, "tests/unit/notamodule.py")
	requireNoEdge(t, g, p, "tests/unit/alsonot.py")
}

// An unterminated string makes the lexical context untrustworthy: opaque.
func TestPythonUncertainIsOpaque(t *testing.T) {
	g := scanRepo(t, repo(t, map[string]string{"t.py": "x = '''never closed\nimport a\n"}))
	if got := g.Opaque("t.py"); got != "uncertain" {
		t.Fatalf("opaque = %q", got)
	}
}

// Assignments keep Python's lexical scope: a function's or a class body's
// local never becomes the module's value, and a binding that may not happen
// (a conditional block, a function's `global` assignment, a module name a
// function reads after it is rebound) keeps every alternative, so no
// candidate is claimed static. Checked against what a real interpreter loads
// under each alternative.
func TestPythonAssignmentScopes(t *testing.T) {
	cases := map[string]struct {
		src    string
		envs   [][]string // the interpreter runs (one per alternative)
		static string     // the claimed static:import of subject ("" = none may be claimed)
	}{
		"tests/test_local.py": {lines(
			`import os, sys`,
			`ROOT = 'a'`,
			`def unused():`,
			`    ROOT = 'b'`,
			`    return ROOT`,
			`sys.path.insert(0, ROOT)`,
			`import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{nil}, "a/subject.py"},
		"tests/test_class.py": {lines(
			`import os, sys`,
			`ROOT = 'a'`,
			`class Config:`,
			`    ROOT = 'b'`,
			`sys.path.insert(0, ROOT)`,
			`import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{nil}, "a/subject.py"},
		"tests/test_cond.py": {lines(
			`import os, sys`,
			`ROOT = 'a'`,
			`if os.environ.get('PICK_B'):`,
			`    ROOT = 'b'`,
			`sys.path.insert(0, ROOT)`,
			`import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{nil, {"PICK_B=1"}}, ""},
		"tests/test_global.py": {lines(
			`import os, sys`,
			`ROOT = 'a'`,
			`def pick_b():`,
			`    global ROOT`,
			`    ROOT = 'b'`,
			`pick_b()`,
			`sys.path.insert(0, ROOT)`,
			`import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{nil}, ""},
		"tests/test_later.py": {lines(
			`import os, sys`,
			`ROOT = 'a'`,
			`def boot():`,
			`    sys.path.insert(0, ROOT)`,
			`ROOT = 'b'`,
			`boot()`,
			`import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{nil}, ""},
		// A nested function reads its enclosing function's local when it
		// runs, after the enclosing function rebound it.
		"tests/test_nested.py": {lines(
			`import os, sys`,
			`def outer():`,
			`    ROOT = 'a'`,
			`    def inner():`,
			`        sys.path.insert(0, ROOT)`,
			`        import subject`,
			`        print(os.path.abspath(subject.__file__))`,
			`    ROOT = 'b'`,
			`    inner()`,
			`outer()`,
		), [][]string{nil}, ""},
		// More alternatives than the model keeps per name.
		"tests/test_many.py": {manyAlternatives(), [][]string{{"PICK=0"}, {"PICK=9"}, {"PICK=17"}}, ""},
		// More combinations than a statement is evaluated under.
		"tests/test_combos.py": {combinations(), [][]string{{"PA=0", "PB=0"}, {"PA=5", "PB=5"}}, ""},
		// A sys.path call inside a lambda runs later, or never.
		"tests/test_lambda.py": {lines(
			`import os, sys`,
			`sys.path.insert(0, 'a')`,
			`later = lambda: sys.path.insert(0, 'b')`,
			`import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{nil}, ""},
		// An entry the scanner cannot evaluate may hold a competing module:
		// the lone candidate it found is not claimed.
		"tests/test_extra.py": {lines(
			`import os, sys`,
			`sys.path.insert(0, os.environ['EXTRA'])`,
			`import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{{"EXTRA=x"}, {"EXTRA=nowhere"}}, ""},
		// The same for an imported member of a namespace package: the
		// member under another directory competes.
		"tests/test_nsmember.py": {lines(
			`import os, sys`,
			`sys.path.insert(0, os.environ['EXTRA'])`,
			`from nspkg import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{{"EXTRA=x"}, {"EXTRA=nowhere"}}, ""},
		// A conditional expression may not run its sys.path call.
		"tests/test_ternary.py": {lines(
			`import os, sys`,
			`sys.path.insert(0, 'a')`,
			`sys.path.insert(0, 'b') if os.environ.get('PICK_B') else None`,
			`import subject`,
			`print(os.path.abspath(subject.__file__))`,
		), [][]string{nil, {"PICK_B=1"}}, ""},
	}
	files := map[string]string{"a/subject.py": "", "b/subject.py": "", "x/subject.py": "", "tests/subject.py": "",
		"tests/nspkg/subject.py": "", "x/nspkg/subject.py": ""}
	for i := range 18 {
		files[fmt.Sprintf("p%d/subject.py", i)] = ""
	}
	for i := range 6 {
		files[fmt.Sprintf("q%d/r%d/subject.py", i, i)] = ""
	}
	for p, c := range cases {
		files[p] = c.src
	}
	r := repo(t, files)
	g := scanRepo(t, r)
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Log("python3 not found: interpreter cross-check skipped")
	}
	for p, c := range cases {
		var claimed []string
		for _, d := range g.Static(p) {
			if strings.HasSuffix(d.Target, "/subject.py") {
				claimed = append(claimed, d.Target)
			}
		}
		if c.static == "" && len(claimed) > 0 || c.static != "" && !slices.Equal(claimed, []string{c.static}) {
			t.Errorf("%s: claimed %v, want %q", p, claimed, c.static)
		}
		if c.static != "" {
			requireNoEdge(t, g, p, "b/subject.py")
		}
		if python == "" {
			continue
		}
		for _, env := range c.envs {
			loaded := runPython(t, r, python, env, p)
			if c.static != "" && loaded != c.static {
				t.Errorf("%s %v: python loads %s, the model claims %s", p, env, loaded, c.static)
			}
			if !slices.ContainsFunc(edges(g, p), func(e string) bool { return strings.HasPrefix(e, loaded+" ") }) {
				t.Errorf("%s %v: python loads %s, not an edge: %v", p, env, loaded, edges(g, p))
			}
		}
	}
}

// A relative import is cached under the importing package's name: after
// `from . import helper` in pkg, a later absolute `import helper` resolves on
// its own (pkg.helper and helper are distinct modules).
func TestPythonRelativeImportIdentity(t *testing.T) {
	r := repo(t, map[string]string{
		"pkg/__init__.py": "",
		"pkg/helper.py":   "",
		"a/helper.py":     "",
		"pkg/t_rel.py": lines(
			`import os, sys`,
			`from . import helper`,
			`sys.path.insert(0, 'a')`,
			`import helper`,
			`print(os.path.abspath(helper.__file__))`,
		),
		"pkg/sub/__init__.py": "",
		"pkg/sub/t_up.py": lines(
			`import os, sys`,
			`from .. import helper`,
			`sys.path.insert(0, 'a')`,
			`import helper`,
			`print(os.path.abspath(helper.__file__))`,
		),
	})
	g := scanRepo(t, r)
	for p, want := range map[string]map[int]string{
		"pkg/t_rel.py":    {2: "pkg/helper.py", 4: "a/helper.py"},
		"pkg/sub/t_up.py": {2: "pkg/helper.py", 4: "a/helper.py"},
	} {
		got := map[int]string{}
		for _, d := range g.Static(p) {
			if strings.HasSuffix(d.Target, "helper.py") {
				got[d.Line] = d.Target
			}
		}
		if !maps.Equal(got, want) {
			t.Errorf("%s: static %v, want %v", p, got, want)
		}
	}
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Log("python3 not found: interpreter cross-check skipped")
		return
	}
	for mod, want := range map[string]string{"pkg.t_rel": "a/helper.py", "pkg.sub.t_up": "a/helper.py"} {
		if got := runPython(t, r, python, nil, "-m", mod); got != want {
			t.Errorf("%s: python loads %s, want %s (the model's claim)", mod, got, want)
		}
	}
}

// manyAlternatives binds ROOT to one of p0 … p17 by the PICK variable.
func manyAlternatives() string {
	src := []string{`import os, sys`, `PICK = os.environ.get('PICK', '0')`, `ROOT = 'p0'`}
	for i := 1; i < 18; i++ {
		src = append(src, fmt.Sprintf(`if PICK == '%d': ROOT = 'p%d'`, i, i))
	}
	return lines(append(src, `sys.path.insert(0, ROOT)`, `import subject`, `print(os.path.abspath(subject.__file__))`)...)
}

// combinations joins two names of six alternatives each (36 combinations).
func combinations() string {
	src := []string{`import os, sys`, `A = 'q0'`, `B = 'r0'`}
	for i := 1; i < 6; i++ {
		src = append(src, fmt.Sprintf(`if os.environ.get('PA') == '%d': A = 'q%d'`, i, i),
			fmt.Sprintf(`if os.environ.get('PB') == '%d': B = 'r%d'`, i, i))
	}
	return lines(append(src, `sys.path.insert(0, os.path.join(A, B))`, `import subject`, `print(os.path.abspath(subject.__file__))`)...)
}

// A path the scanner cannot evaluate keeps its candidates: an import after
// an unevaluable sys.path entry may load the module from any directory, and
// a path built on an unknown base keeps its literal tail.
func TestPythonUnknownBases(t *testing.T) {
	r := repo(t, map[string]string{
		"tests/test_env.py": lines(
			`import os, sys`,
			`from pathlib import Path`,
			`BASE = Path(os.environ["SOMEWHERE"])`,
			`TOOL = BASE / "tools" / "run.sh"`,
			`sys.path.insert(0, os.environ["EXTRA"])`,
			`import helper_mod`,
		),
		"deep/tools/run.sh":        "#!/bin/sh\n",
		"x/helper_mod.py":          "",
		"y/helper_mod/__init__.py": "",
		"tests/test_plain.py":      lines(`import helper_mod`),
		// An import before the unevaluable entry is resolved exactly.
		"tests/test_early.py": lines(
			`import os, sys`,
			`import early`,
			`sys.path.insert(0, os.environ["EXTRA"])`,
			`import late`,
		),
		"tests/early.py":         "",
		"x/early.py":             "",
		"tests/late.py":          "",
		"x/late.py":              "",
		"tests/unrelated/run.sh": "#!/bin/sh\n",
	})
	g := scanRepo(t, r)
	requireEdge(t, g, "tests/test_env.py", "deep/tools/run.sh", "", "suffix")
	requireNoEdge(t, g, "tests/test_env.py", "tests/unrelated/run.sh")
	requireEdge(t, g, "tests/test_env.py", "x/helper_mod.py", "", "anywhere")
	requireEdge(t, g, "tests/test_env.py", "y/helper_mod/__init__.py", "", "anywhere")
	requireEdge(t, g, "tests/test_early.py", "tests/early.py", Import, "import")
	requireEdge(t, g, "tests/test_early.py", "tests/late.py", "", "")
	requireEdge(t, g, "tests/test_early.py", "x/late.py", "", "anywhere")
	for _, d := range g.Static("tests/test_early.py") {
		if strings.HasSuffix(d.Target, "late.py") {
			t.Errorf("a lone candidate after an unevaluable entry was claimed: %+v", d)
		}
	}
	// A module whose sys.path is fully evaluated is not widened.
	for _, e := range edges(g, "tests/test_plain.py") {
		if strings.HasSuffix(e, " anywhere") {
			t.Errorf("test_plain.py widened: %v", edges(g, "tests/test_plain.py"))
		}
	}
}
