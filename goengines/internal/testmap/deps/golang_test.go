package deps

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

const goMod = "module m\n\ngo 1.21\n"

// goEnvFixture isolates the go invocations: no toolchain download, no user
// flags, no workspace.
func goEnvFixture(t *testing.T) {
	t.Helper()
	t.Setenv("GOTOOLCHAIN", "local")
	t.Setenv("GOFLAGS", "")
	t.Setenv("GOWORK", "off")
	t.Setenv("GOPROXY", "off")
	if _, err := lookPath("go"); err != nil {
		t.Skip("no go toolchain")
	}
}

func countGoExecs(t *testing.T) *int {
	t.Helper()
	n := 0
	old := goExecHook
	goExecHook = func(string) { n++ }
	t.Cleanup(func() { goExecHook = old })
	return &n
}

func scanCached(t *testing.T, r *fixture.Repo, cache string) *Graph {
	t.Helper()
	return scanRepo(t, r, func(o *Options) { o.Uncached, o.CacheDir = false, cache })
}

func TestGoPackageFacts(t *testing.T) {
	goEnvFixture(t)
	r := repo(t, map[string]string{
		"go.mod":            goMod,
		"a/a.go":            "package a\n\nimport \"m/b\"\n\nvar X = b.Y\n",
		"a/embed.go":        "package a\n\nimport _ \"embed\"\n\n//go:embed assets\nvar assets string\n",
		"a/assets":          "data\n",
		"a/zz_tag.go":       "//go:build ignore\n\npackage a\n\nimport _ \"m/c\"\n",
		"a/a_test.go":       "package a\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n",
		"a/export_test.go":  "package a\n\nvar Exported = X\n",
		"a/ax_test.go":      "package a_test\n\nimport (\n\t\"testing\"\n\n\t\"m/a\"\n)\n\nfunc TestX(t *testing.T) { _ = a.X }\n",
		"a/testdata/in.txt": "x\n",
		"b/b.go":            "package b\n\nvar Y = 1\n",
		"c/c.go":            "package c\n",
		"d/d.go":            "package d\n",
	})
	g := scanRepo(t, r)
	for _, test := range []string{"a/a_test.go", "a/ax_test.go"} {
		for _, subj := range []string{"a/a.go", "a/embed.go", "a/zz_tag.go"} {
			requireEdge(t, g, test, subj, Package, "package")
		}
		requireEdge(t, g, test, "a/testdata/in.txt", "", "testdata")
	}
	requireEdge(t, g, "a/ax_test.go", "a/export_test.go", "", "xtest")
	requireEdge(t, g, "a/a.go", "b/b.go", "", "import")
	requireEdge(t, g, "a/embed.go", "a/assets", "", "embed")
	// A tag-excluded file's own imports count (go list reports none for it).
	requireEdge(t, g, "a/zz_tag.go", "c/c.go", "", "import")
	if !reached(g, "a/a_test.go", "b/b.go") {
		t.Error("a_test.go does not reach b/b.go")
	}
	if reached(g, "a/a_test.go", "d/d.go") {
		t.Error("a_test.go reaches an unrelated package")
	}
	if g.Static("a/a.go") != nil {
		t.Errorf("a non-test file got static facts: %+v", g.Static("a/a.go"))
	}
}

// A warm re-scan with unchanged Go inputs runs no `go`.
func TestGoWarmRunsNoGo(t *testing.T) {
	goEnvFixture(t)
	r := repo(t, map[string]string{"go.mod": goMod, "a/a.go": "package a\n"})
	n := countGoExecs(t)
	cache := t.TempDir()
	scanCached(t, r, cache)
	scanCached(t, r, cache)
	if *n != 1 {
		t.Fatalf("go list ran %d times, want 1", *n)
	}
}

// keyVariant swaps goKeyFunc for one test.
func keyVariant(t *testing.T, f func(goKeyInput) string) {
	t.Helper()
	old := goKeyFunc
	goKeyFunc = f
	t.Cleanup(func() { goKeyFunc = old })
}

func hashOf(parts ...string) string {
	h := sha256.Sum256([]byte(strings.Join(parts, "\x00")))
	return hex.EncodeToString(h[:])
}

// Reduced keys, each one input class short of fullGoKey: the red proofs.
var (
	goSumOnlyKey = func(in goKeyInput) string {
		var parts []string
		for _, m := range in.Mods {
			parts = append(parts, m.GoSum)
		}
		return hashOf(parts...)
	}
	universeOnlyKey = func(in goKeyInput) string { // the pre-review design
		var parts []string
		for _, f := range in.Files {
			parts = append(parts, f.Path)
			if f.InUniverse {
				parts = append(parts, f.Header)
			}
		}
		return hashOf(parts...)
	}
	dotAllWalkKey = func(in goKeyInput) string { // what `./...` discovers
		var parts []string
		for _, f := range in.Files {
			if !f.SkippedByAll {
				parts = append(parts, f.Path, f.Header)
			}
		}
		return hashOf(parts...)
	}
	nonRecursiveEmbedKey = func(in goKeyInput) string {
		c := in
		c.Embed = map[string][]string{}
		for d, list := range in.Embed {
			for _, e := range list {
				if !strings.Contains(strings.TrimSuffix(e, "/"), "/") {
					c.Embed[d] = append(c.Embed[d], e)
				}
			}
		}
		return fullGoKey(c)
	}
)

// redGreen runs prime → mutate → re-scan twice: under the reduced key the
// re-scan must MISS want (the red: that key would have served a stale go list
// result), under the real key it must reach it.
func redGreen(t *testing.T, files map[string]string, reduced func(goKeyInput) string,
	mutate func(r *fixture.Repo), from, want string) {
	t.Helper()
	goEnvFixture(t)
	for _, real := range []bool{false, true} {
		r := repo(t, files)
		if !real {
			keyVariant(t, reduced)
		} else {
			keyVariant(t, fullGoKey)
		}
		cache := t.TempDir()
		if g := scanCached(t, r, cache); reached(g, from, want) {
			t.Fatalf("setup: %s already reaches %s", from, want)
		}
		mutate(r)
		g := scanCached(t, r, cache)
		if got := reached(g, from, want); got != real {
			t.Errorf("real key=%v: %s reaches %s = %v (closure %+v)", real, from, want, got, g.Closure(from, 0))
		}
	}
}

func baseModule() map[string]string {
	return map[string]string{
		"go.mod":      goMod,
		"go.sum":      "",
		"a/a.go":      "package a\n\nimport _ \"m/b\"\n",
		"a/a_test.go": "package a\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n",
		"b/b.go":      "package b\n",
		"c/c.go":      "package c\n",
	}
}

// The proposal's case: a new import of another local package, go.mod and
// go.sum byte-identical. A go.sum-only key serves the stale graph.
func TestGoKeyRedNewLocalImport(t *testing.T) {
	redGreen(t, baseModule(), goSumOnlyKey, func(r *fixture.Repo) {
		r.Write(t, "a/a.go", "package a\n\nimport (\n\t_ \"m/b\"\n\t_ \"m/c\"\n)\n")
	}, "a/a_test.go", "c/c.go")
}

// A new file in an existing package changes its membership.
func TestGoKeyRedNewFile(t *testing.T) {
	redGreen(t, baseModule(), goSumOnlyKey, func(r *fixture.Repo) {
		r.Write(t, "b/b2.go", "package b\n")
	}, "a/a_test.go", "b/b2.go")
}

// A gitignored generated file is a package input: its import change re-runs
// go list although every universe file and every name is unchanged.
func TestGoKeyRedIgnoredGeneratedFile(t *testing.T) {
	files := baseModule()
	files[".gitignore"] = "a/zz_gen.go\n"
	files["a/a.go"] = "package a\n"
	files["a/zz_gen.go"] = "package a\n\nimport _ \"m/b\"\n"
	redGreen(t, files, universeOnlyKey, func(r *fixture.Repo) {
		r.Write(t, "a/zz_gen.go", "package a\n\nimport _ \"m/c\"\n")
	}, "a/a_test.go", "c/c.go")
}

// A `_`-prefixed package imported directly: `./...` skips the directory, go
// list -deps loads it.
func TestGoKeyRedUnderscorePackage(t *testing.T) {
	files := baseModule()
	files["a/a.go"] = "package a\n\nimport _ \"m/_bridge\"\n"
	files["_bridge/bridge.go"] = "package bridge\n\nimport _ \"m/b\"\n"
	redGreen(t, files, dotAllWalkKey, func(r *fixture.Repo) {
		r.Write(t, "_bridge/bridge.go", "package bridge\n\nimport _ \"m/c\"\n")
	}, "a/a_test.go", "c/c.go")
}

// A file added under an embedded directory changes EmbedFiles.
func TestGoKeyRedRecursiveEmbed(t *testing.T) {
	files := baseModule()
	files["a/embed.go"] = "package a\n\nimport \"embed\"\n\n//go:embed assets\nvar fs embed.FS\n"
	files["a/assets/first.txt"] = "1\n"
	redGreen(t, files, nonRecursiveEmbedKey, func(r *fixture.Repo) {
		r.Write(t, "a/assets/second.txt", "2\n")
	}, "a/a_test.go", "a/assets/second.txt")
}

// A build-constraint flip is in the key (the edges here are the same either
// way: a tag-excluded file still belongs, as an over-approximation).
func TestGoKeyCoversDirectives(t *testing.T) {
	goEnvFixture(t)
	var keys []string
	keyVariant(t, func(in goKeyInput) string {
		k := fullGoKey(in)
		keys = append(keys, k)
		return k
	})
	r := repo(t, map[string]string{"go.mod": goMod, "a/a.go": "//go:build linux\n\npackage a\n"})
	scanRepo(t, r)
	r.Write(t, "a/a.go", "//go:build ignore\n\npackage a\n")
	scanRepo(t, r)
	if len(keys) != 2 || keys[0] == keys[1] {
		t.Fatalf("keys %v: a directive change must change the key", keys)
	}
}

// A package directory reached through a symbolic link is outside the keyed
// walk: the result is used but never cached.
func TestGoUntrackedInputIsNotCached(t *testing.T) {
	goEnvFixture(t)
	r := repo(t, map[string]string{"go.mod": goMod, "real/r.go": "package real\n", "a/a.go": "package a\n\nimport _ \"m/link\"\n"})
	if err := os.Symlink("real", filepath.Join(r.Dir, "link")); err != nil {
		t.Skip(err)
	}
	n := countGoExecs(t)
	cache := t.TempDir()
	g := scanCached(t, r, cache)
	scanCached(t, r, cache)
	if *n != 2 {
		t.Errorf("go list ran %d times, want 2 (never cached)", *n)
	}
	if !slices.ContainsFunc(g.Problems(), func(p Problem) bool { return strings.Contains(p.Reason, "go-input-untracked") }) {
		t.Errorf("problems: %+v", g.Problems())
	}
}

// Failure branches: fail closed, never cached.
func TestGoFailuresAreOpaque(t *testing.T) {
	goEnvFixture(t)
	t.Run("go-list-failed", func(t *testing.T) {
		r := repo(t, map[string]string{"go.mod": "this is not a go.mod\n", "a/a.go": "package a\n"})
		n := countGoExecs(t)
		cache := t.TempDir()
		g := scanCached(t, r, cache)
		scanCached(t, r, cache)
		if g.Opaque("a/a.go") != "go-list-failed" || *n != 2 {
			t.Fatalf("opaque %q, go list runs %d", g.Opaque("a/a.go"), *n)
		}
	})
	t.Run("local-package-error", func(t *testing.T) {
		r := repo(t, map[string]string{"go.mod": goMod, "a/a.go": "package a\n\nimport (\n\t\"m/b\"\n", "b/b.go": "package b\n"})
		g := scanRepo(t, r)
		if g.Opaque("a/a.go") != "go-list-failed" || g.Opaque("b/b.go") != "" {
			t.Fatalf("a %q b %q", g.Opaque("a/a.go"), g.Opaque("b/b.go"))
		}
	})
	t.Run("missing-third-party", func(t *testing.T) {
		r := repo(t, map[string]string{"go.mod": goMod + "\nrequire example.com/nope v1.0.0\n",
			"a/a.go": "package a\n\nimport _ \"example.com/nope\"\n"})
		if got := scanRepo(t, r).Opaque("a/a.go"); got != "" {
			t.Fatalf("a missing third-party module made a local file opaque: %q", got)
		}
	})
	t.Run("go-unavailable", func(t *testing.T) {
		old := lookPath
		lookPath = func(string) (string, error) { return "", errors.New("no go") }
		t.Cleanup(func() { lookPath = old })
		r := repo(t, map[string]string{"go.mod": goMod, "a/a.go": "package a\n"})
		if got := scanRepo(t, r).Opaque("a/a.go"); got != "go-unavailable" {
			t.Fatalf("opaque %q", got)
		}
	})
}

func TestGoSymbols(t *testing.T) {
	r := repo(t, map[string]string{"x.go": "package x\n\ntype T struct{}\n\nfunc (t *T) Do() {}\nfunc F() {}\nfunc g() {}\n\nconst C = 1\n"})
	f, _ := scanRepo(t, r).Facts("x.go")
	var names []string
	for _, s := range f.Symbols {
		names = append(names, s.Kind+":"+s.Name)
	}
	if want := []string{"type:T", "method:T.Do", "func:F", "const:C"}; !slices.Equal(names, want) {
		t.Fatalf("symbols %v, want %v", names, want)
	}
}

// Dependencies only test files import are loaded too: a bridge package that
// only an internal test imports, a helper that only an external test imports
// and that is recompiled for the test (it imports the package under test),
// and a missing local package that only a test imports.
func TestGoTestOnlyImports(t *testing.T) {
	goEnvFixture(t)
	r := repo(t, map[string]string{
		"go.mod":            goMod,
		"a/a.go":            "package a\n",
		"a/a_test.go":       "package a\n\nimport (\n\t\"testing\"\n\n\t_ \"m/_bridge\"\n)\n\nfunc TestA(t *testing.T) {}\n",
		"_bridge/bridge.go": "package bridge\n\nimport _ \"m/b\"\n",
		"b/b.go":            "package b\n",
		"c/c.go":            "package c\n",
		"c/c_in_test.go":    "package c\n\nimport \"testing\"\n\nfunc TestIn(t *testing.T) {}\n",
		"c/cx_test.go":      "package c_test\n\nimport (\n\t\"testing\"\n\n\t_ \"m/_h\"\n)\n\nfunc TestX(t *testing.T) {}\n",
		"_h/h.go":           "package h\n\nimport (\n\t_ \"m/c\"\n\t_ \"m/e\"\n)\n",
		"e/e.go":            "package e\n",
		"f/f.go":            "package f\n",
		"f/f_test.go":       "package f\n\nimport (\n\t\"testing\"\n\n\t_ \"m/nope\"\n)\n\nfunc TestF(t *testing.T) {}\n",
	})
	g := scanRepo(t, r)
	for _, c := range []struct{ from, to string }{
		{"a/a_test.go", "_bridge/bridge.go"},
		{"a/a_test.go", "b/b.go"},
		{"c/cx_test.go", "_h/h.go"},
		{"c/cx_test.go", "e/e.go"},
	} {
		if !reached(g, c.from, c.to) {
			t.Errorf("%s does not reach %s: %v", c.from, c.to, g.Closure(c.from, 0))
		}
	}
	requireEdge(t, g, "_bridge/bridge.go", "b/b.go", "", "import")
	if reached(g, "a/a.go", "b/b.go") {
		t.Error("a non-test file reaches a test-only dependency")
	}
	if got := g.Opaque("f/f_test.go"); got != "go-list-failed" {
		t.Errorf("a test-only missing local import: opaque %q", got)
	}
	if got := g.Opaque("f/f.go"); got != "" {
		t.Errorf("the package's non-test file: opaque %q", got)
	}
}
