package deps

import (
	"slices"
	"testing"
)

// The bash scanner's literal invocation facts, including the directory
// variable forms this repository's tests use, rebinding, embedded Python,
// and the closure-only fallbacks.
func TestBashInvocationForms(t *testing.T) {
	r := repo(t, map[string]string{
		"tests/t.sh": lines(
			`#!/bin/bash`,
			`SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`,
			`PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"`,
			`. "$PROJECT_DIR/tests/lib/asserts.sh"`,
			`source "$SCRIPT_DIR/lib/helper.sh"`,
			`bash "$PROJECT_DIR/.aitask-scripts/aitask_a.sh" x`,
			`out=$("$PROJECT_DIR/.aitask-scripts/aitask_b.sh" --flag)`,
			`./.aitask-scripts/aitask_c.sh`,
			`LIB="$PROJECT_DIR/.aitask-scripts/lib/agent.sh"`,
			`source "$LIB"`,
			`run_it() { "$SCRIPT_DIR/../.aitask-scripts/aitask_d.sh"; }`,
			`SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"`,
			`"$SCRIPT_DIR/aitask_e.sh"`,
			`# ./.aitask-scripts/aitask_f.sh only in a comment`,
			`cat <<EOF`,
			`./.aitask-scripts/aitask_g.sh`,
			`EOF`,
			`python3 -c "import sys; import pymod"`,
			`python3 - <<'PY'`,
			`from pkgmod import thing`,
			`PY`,
			`for f in "$A$B/lib/x.sh"; do :; done`,
			`check "./ait board"`,
		),
		"tests/lib/asserts.sh":                   "#!/bin/sh\n",
		"tests/lib/helper.sh":                    "#!/bin/sh\n",
		"tests/lib/x.sh":                         "#!/bin/sh\n",
		".aitask-scripts/aitask_a.sh":            "#!/bin/sh\n",
		".aitask-scripts/aitask_b.sh":            "#!/bin/sh\n",
		".aitask-scripts/aitask_c.sh":            "#!/bin/sh\n",
		".aitask-scripts/aitask_d.sh":            "#!/bin/sh\n",
		".aitask-scripts/aitask_e.sh":            "#!/bin/sh\n",
		".aitask-scripts/aitask_f.sh":            "#!/bin/sh\n",
		".aitask-scripts/aitask_g.sh":            "#!/bin/sh\n",
		".aitask-scripts/lib/agent.sh":           "#!/bin/sh\n",
		".aitask-scripts/lib/pymod.py":           "",
		".aitask-scripts/lib/pkgmod/__init__.py": "",
		".aitask-scripts/lib/pkgmod/thing.py":    "",
		"ait":                                    "#!/bin/bash\n",
		// A Python test whose bootstrap makes .aitask-scripts/lib a source root.
		"tests/test_boot.py": lines(
			`import sys`,
			`from pathlib import Path`,
			`sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".aitask-scripts" / "lib"))`,
		),
	})
	g := scanRepo(t, r)
	const p = "tests/t.sh"
	requireEdge(t, g, p, "tests/lib/asserts.sh", Invocation, "source")
	requireEdge(t, g, p, "tests/lib/helper.sh", Invocation, "source")
	requireEdge(t, g, p, ".aitask-scripts/aitask_a.sh", Invocation, "exec")
	requireEdge(t, g, p, ".aitask-scripts/aitask_b.sh", Invocation, "exec")
	requireEdge(t, g, p, ".aitask-scripts/aitask_c.sh", Invocation, "exec")
	requireEdge(t, g, p, ".aitask-scripts/lib/agent.sh", Invocation, "")
	// A function runs after the later rebinding: every binding is tried.
	requireEdge(t, g, p, ".aitask-scripts/aitask_d.sh", Invocation, "exec")
	requireEdge(t, g, p, ".aitask-scripts/aitask_e.sh", Invocation, "exec")
	requireNoEdge(t, g, p, ".aitask-scripts/aitask_f.sh")
	// Heredoc and embedded-Python content: closure-only.
	requireEdge(t, g, p, ".aitask-scripts/aitask_g.sh", "", "embedded")
	requireEdge(t, g, p, ".aitask-scripts/lib/pymod.py", "", "embedded-python")
	requireEdge(t, g, p, ".aitask-scripts/lib/pkgmod/thing.py", "", "embedded-python")
	// A non-literal word: its literal tail as a suffix.
	requireEdge(t, g, p, "tests/lib/x.sh", "", "suffix")
	// A quoted command line: its path-shaped runs, closure-only.
	requireEdge(t, g, p, "ait", "", "string")
	f, _ := g.Facts(p)
	if !slices.ContainsFunc(f.Symbols, func(s Symbol) bool { return s.Name == "run_it" && s.Kind == "func" }) {
		t.Errorf("symbols: %+v", f.Symbols)
	}
}

// An unknown variable's path is retried against every source root, and the
// hit is closure-only (never seeded).
func TestBashFallbackIsClosureOnly(t *testing.T) {
	r := repo(t, map[string]string{
		"tests/t.sh": lines(`#!/bin/bash`, `source "$SOMEWHERE/lib/util.sh"`),
		// a.sh binds a directory: lib's parent becomes a source root.
		"tools/a.sh":           lines(`#!/bin/bash`, `X="$(cd "$(dirname "${BASH_SOURCE[0]}")/../pkg" && pwd)"`),
		"pkg/lib/util.sh":      "#!/bin/sh\n",
		"pkg/lib/unrelated.sh": "#!/bin/sh\n",
	})
	g := scanRepo(t, r)
	requireEdge(t, g, "tests/t.sh", "pkg/lib/util.sh", "", "fallback")
	if s := g.Static("tests/t.sh"); len(s) != 0 {
		t.Fatalf("a fallback hit was seeded: %+v", s)
	}
}

func TestBashSymbols(t *testing.T) {
	r := repo(t, map[string]string{
		"tool.sh": lines(
			`#!/bin/bash`,
			`function helper { :; }`,
			`case "$1" in`,
			`  list|ls) echo "LISTED:$2" ;;`,
			`  show) printf 'SHOWN:%s\n' x ;;`,
			`esac`,
		),
	})
	g := scanRepo(t, r)
	f, _ := g.Facts("tool.sh")
	want := map[string]string{"helper": "func", "list": "verb", "ls": "verb", "show": "verb", "LISTED": "token", "SHOWN": "token"}
	for name, kind := range want {
		if !slices.ContainsFunc(f.Symbols, func(s Symbol) bool { return s.Name == name && s.Kind == kind }) {
			t.Errorf("missing %s %s in %+v", kind, name, f.Symbols)
		}
	}
}

// A source / exec whose target is not statically known is unresolved
// (`<dynamic>[/<tail>]`); a suffix hit stays resolved, and a plain argument
// never counts.
func TestBashDynamicRefIsUnresolved(t *testing.T) {
	r := repo(t, map[string]string{
		"tests/t.sh": lines(
			`#!/bin/bash`,
			`source "$X"`,
			`"$CMD" --flag`,
			`bash "${A}${B}/gen.sh"`,
			`source "${A}${B}/lib/x.sh"`,
			`cat "${A}${B}/f.txt"`,
		),
		"tests/lib/x.sh": "#!/bin/sh\n",
	})
	g := scanRepo(t, r)
	requireEdge(t, g, "tests/t.sh", "tests/lib/x.sh", "", "suffix")
	f, _ := g.Facts("tests/t.sh")
	if want := []string{"<dynamic>", "<dynamic>/gen.sh"}; !slices.Equal(f.Unresolved, want) {
		t.Errorf("unresolved: %q, want %q", f.Unresolved, want)
	}
}
