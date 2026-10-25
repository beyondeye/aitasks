package modules

import (
	"context"
	"errors"
	"slices"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// repo is a git repository with a registry and files; scans use a private cache.
func repo(t *testing.T, files map[string]string) *fixture.Repo {
	t.Helper()
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	r := fixture.New(t)
	r.Write(t, registry.ConfigPath, "contract: 1\n")
	for p, c := range files {
		r.Write(t, p, c)
	}
	return r
}

// infer loads r's registry and infers its modules table.
func infer(t *testing.T, r *fixture.Repo) (*registry.Registry, *Result) {
	t.Helper()
	reg, err := registry.Load(r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	res, err := Scan(context.Background(), r.Dir, reg)
	if err != nil {
		t.Fatal(err)
	}
	return reg, res
}

func names(res *Result) []string {
	var out []string
	for _, m := range res.Doc.Modules {
		out = append(out, m.Name)
	}
	return out
}

func row(t *testing.T, res *Result, name string) registry.ModuleRow {
	t.Helper()
	for _, m := range res.Doc.Modules {
		if m.Name == name {
			return m
		}
	}
	t.Fatalf("no module %s in %v", name, names(res))
	return registry.ModuleRow{}
}

func refused(res *Result) []string {
	var out []string
	for _, x := range res.Refused {
		out = append(out, strings.Join(x.Fields(), "|"))
	}
	return out
}

// resolve resolves the live table (hand modules included) over the universe.
func resolve(t *testing.T, reg *registry.Registry, res *Result) *registry.Resolution {
	t.Helper()
	rs, err := registry.ModulesOf(reg).WithGenerated(res.Doc).Resolve(res.Files)
	if err != nil {
		t.Fatal(err)
	}
	return rs
}

const codemapHead = "version: 1\nareas:\n"

// Every codemap entry at any depth is a module named from its path, so two
// entries named alike under different parents are two modules; a root entry
// and an unnameable path are refused; entries sharing a path are one module.
func TestCodemapProvider(t *testing.T) {
	r := repo(t, map[string]string{
		registry.CodemapPath: codemapHead +
			"  - name: a\n    path: a/\n    children:\n      - {name: tests, path: a/tests/}\n" +
			"  - name: b\n    path: b/\n    children:\n      - {name: tests, path: b/tests/}\n" +
			"  - {name: everything, path: /}\n" +
			"  - {name: dotted, path: a.b/}\n" +
			"  - {name: nested, path: x/y/}\n" +
			"  - {name: colon, path: a:b/}\n" +
			"  - {name: again, path: x/y/}\n",
		"a/tests/t.sh": "#!/bin/sh\n", "b/tests/t.sh": "#!/bin/sh\n", "a/x.sh": "", "a.b/f.txt": "", "x/y/z.md": "",
	})
	_, res := infer(t, r)
	if got, want := names(res), []string{"codemap:a", "codemap:a.b", "codemap:a:tests", "codemap:b", "codemap:b:tests", "codemap:x:y"}; !slices.Equal(got, want) {
		t.Fatalf("modules %v, want %v", got, want)
	}
	if got, want := refused(res), []string{"codemap|.|repository_root", "codemap|a:b|unnameable"}; !slices.Equal(got, want) {
		t.Fatalf("refused %v, want %v", got, want)
	}
	if m := row(t, res, "codemap:x:y"); m.Root != "x/y" || !slices.Equal(m.Evidence, []string{"entry:again", "entry:nested"}) {
		t.Fatalf("merged entry %+v", m)
	}
	if m := row(t, res, "codemap:a:tests"); m.Root != "a/tests" || !slices.Equal(m.Evidence, []string{"entry:tests"}) {
		t.Fatalf("child entry %+v", m)
	}
}

func TestCodemapMalformedIsInputError(t *testing.T) {
	for name, body := range map[string]string{
		"yaml":     "version: 1\nareas: [\n",
		"version":  "version: 2\nareas: []\n",
		"dotdot":   codemapHead + "  - {name: up, path: ../x/}\n",
		"absolute": codemapHead + "  - {name: abs, path: /etc/x/}\n",
		"name":     codemapHead + "  - {name: \"a|b\", path: a/}\n",
	} {
		t.Run(name, func(t *testing.T) {
			r := repo(t, map[string]string{registry.CodemapPath: body})
			reg, err := registry.Load(r.Dir)
			if err != nil {
				t.Fatal(err)
			}
			_, err = Scan(context.Background(), r.Dir, reg)
			var ie *registry.InputError
			if !errors.As(err, &ie) || ie.Input != registry.InputCodemap {
				t.Fatalf("err %v, want INPUT_ERROR:code_areas", err)
			}
		})
	}
}

// Only projects a settings file declares are modules, rooted at their
// projectDir; the root project is refused; a project directory the name rule
// cannot name is refused even when its Gradle path is fine; a dynamic build is
// flagged.
func TestGradleProvider(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle.kts": "include(\":app\", \":lib\", \":api\", \":odd\")\n" +
			"project(\":api\").projectDir = file(\"services/api\")\n" +
			"project(\":odd\").projectDir = file(\"odd:dir\")\n",
		"build.gradle.kts":                  "",
		"app/build.gradle.kts":              "val a = $$\"\"\"${/*}\"\"\"\n",
		"lib/build.gradle.kts":              "",
		"services/api/build.gradle.kts":     "",
		"odd:dir/build.gradle.kts":          "",
		"examples/demo/build.gradle.kts":    "",
		"examples/demo/src/Demo.kt":         "class Demo\n",
		"services/api/src/main/kotlin/A.kt": "package a\nclass A\n",
	})
	reg, res := infer(t, r)
	if got, want := names(res), []string{"gradle:api", "gradle:app", "gradle:lib"}; !slices.Equal(got, want) {
		t.Fatalf("modules %v, want %v", got, want)
	}
	if got, want := refused(res), []string{"gradle|.|repository_root", "gradle|odd:dir|unnameable"}; !slices.Equal(got, want) {
		t.Fatalf("refused %v, want %v", got, want)
	}
	api := row(t, res, "gradle:api")
	if api.Root != "services/api" || api.Gradle != ":api" || !slices.Equal(api.Evidence, []string{"settings:settings.gradle.kts", "build:services/api/build.gradle.kts"}) {
		t.Fatalf("projectDir override %+v", api)
	}
	if app := row(t, res, "gradle:app"); !slices.Contains(app.Evidence, "gradle-dynamic") {
		t.Fatalf("dynamic build not flagged: %+v", app)
	}
	if lib := row(t, res, "gradle:lib"); slices.Contains(lib.Evidence, "gradle-dynamic") {
		t.Fatalf("static build flagged: %+v", lib)
	}
	rs := resolve(t, reg, res)
	for _, p := range []string{"examples/demo/src/Demo.kt", "examples/demo/build.gradle.kts", "build.gradle.kts", "odd:dir/build.gradle.kts"} {
		if o := rs.Owner[p]; o != "" {
			t.Errorf("%s owned by %s, want unmapped", p, o)
		}
	}
	if o := rs.Owner["services/api/src/main/kotlin/A.kt"]; o != "gradle:api" {
		t.Errorf("A.kt owned by %q", o)
	}
}

// Worked example 4: a deeply nested project owns its subtree; the enclosing
// project never gets it by nesting; the root project is no module, so the
// root-only build file is unmapped.
func TestWorkedExampleDeepGradleProject(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle.kts":                    "include(\":services\", \":services:payments:api\")\n",
		"build.gradle.kts":                       "",
		"services/build.gradle.kts":              "",
		"services/payments/api/build.gradle.kts": "",
		"services/payments/api/src/A.kt":         "package p\nclass A\n",
		"services/payments/README.md":            "# p\n",
	})
	reg, res := infer(t, r)
	if got, want := names(res), []string{"gradle:services", "gradle:services:payments:api"}; !slices.Equal(got, want) {
		t.Fatalf("modules %v", got)
	}
	if got := refused(res); !slices.Equal(got, []string{"gradle|.|repository_root"}) {
		t.Fatalf("refused %v", got)
	}
	rs := resolve(t, reg, res)
	want := map[string]string{
		"services/payments/api/src/A.kt": "gradle:services:payments:api",
		"services/payments/README.md":    "gradle:services",
		"services/build.gradle.kts":      "gradle:services",
		"build.gradle.kts":               "",
	}
	for p, w := range want {
		if o := rs.Owner[p]; o != w {
			t.Errorf("%s owned by %q, want %q", p, o, w)
		}
	}
	for _, c := range rs.Conflicts {
		t.Errorf("nesting within one provider is no conflict: %+v", c)
	}
}

// The combined fixture: precedence hand > codemap > Gradle over one tree,
// MODULE_CONFLICT once per pair whose sets overlap but differ, every file kind
// counted (JSON, Markdown, unsupported sources), and module deps evidence.
func TestCombinedPrecedenceAndConflicts(t *testing.T) {
	r := repo(t, map[string]string{
		registry.CodemapPath:                codemapHead + "  - {name: api, path: services/api/}\n  - {name: docs, path: docs/}\n  - {name: ledger, path: ledger/}\n",
		"settings.gradle.kts":               "include(\":services:api\", \":docs:site\")\n",
		"docs/site/build.gradle.kts":        "",
		"docs/site/index.md":                "# s\n",
		"services/api/build.gradle.kts":     "",
		"services/api/public/Api.kt":        "package api\nclass Api\n",
		"services/api/internal/Impl.kt":     "package api\nclass Impl\n",
		"services/api/config.json":          "{}\n",
		"docs/README.md":                    "# d\n",
		"docs/guide.rst":                    "g\n",
		"ledger/entry.sh":                   "#!/bin/sh\n",
		"ledger/report.sh":                  "#!/bin/sh\n. ./docs/run.sh\n",
		"docs/run.sh":                       "#!/bin/sh\n",
		registry.RegistryDir + "/hand.yaml": "contract: 1\nmodules:\n  api: {paths: [\"services/api/public/**\"]}\n",
	})
	reg, res := infer(t, r)
	rs := resolve(t, reg, res)
	owner := map[string]string{
		"services/api/public/Api.kt":    "api",
		"services/api/internal/Impl.kt": "codemap:services:api",
		"services/api/config.json":      "codemap:services:api",
		"docs/README.md":                "codemap:docs",
		"docs/guide.rst":                "codemap:docs",
		"settings.gradle.kts":           "",
	}
	for p, w := range owner {
		if o := rs.Owner[p]; o != w {
			t.Errorf("%s owned by %q, want %q", p, o, w)
		}
	}
	var got []string
	for _, c := range rs.Conflicts {
		got = append(got, strings.Join(c.Fields(), "|"))
	}
	want := []string{
		"api@hand|codemap:services:api@codemap|1|services/api/public/Api.kt",
		"api@hand|gradle:services:api@gradle|1|services/api/public/Api.kt",
		// codemap:services:api and gradle:services:api share a root: identical
		// claims refine nothing, so the pair is not reported.
		// A Gradle project under a codemap entry: the codemap wins its paths,
		// and the sets differ, so the pair is reported once.
		"codemap:docs@codemap|gradle:docs:site@gradle|2|docs/site/build.gradle.kts",
	}
	if !slices.Equal(got, want) {
		t.Fatalf("conflicts\n got %v\nwant %v", got, want)
	}
	members := map[string]int{}
	for _, m := range rs.Modules {
		members[m.Name] = len(m.Members)
	}
	if members["codemap:docs"] != 5 || members["api"] != 1 || members["codemap:services:api"] != 3 {
		t.Fatalf("members %v", members)
	}
	if _, ok := members["gradle:services:api"]; ok || members["gradle:docs:site"] != 0 {
		t.Fatal("a module left with no paths must be absent from the effective table")
	}
	if l := row(t, res, "codemap:ledger"); len(l.Deps) != 1 || l.Deps[0].Module != "codemap:docs" ||
		l.Deps[0].Evidence != (registry.DepEvidence{From: "ledger/report.sh", To: "docs/run.sh"}) {
		t.Fatalf("ledger deps %+v", l.Deps)
	}
}

// deps are computed against the persisted rows only: a hand module taking a
// file never changes the generated table.
func TestDepsIgnoreHandModules(t *testing.T) {
	files := map[string]string{
		registry.CodemapPath: codemapHead + "  - {name: a, path: a/}\n  - {name: b, path: b/}\n",
		"a/x.sh":             "#!/bin/sh\n. ./b/y.sh\n",
		"b/y.sh":             "#!/bin/sh\n",
	}
	_, plain := infer(t, repo(t, files))
	files[registry.RegistryDir+"/hand.yaml"] = "contract: 1\nmodules:\n  core: {paths: [\"b/**\"]}\n"
	_, withHand := infer(t, repo(t, files))
	a, b := registry.RenderModules(plain.Doc)
	c, d := registry.RenderModules(withHand.Doc)
	if b != nil || d != nil || string(a) != string(c) {
		t.Fatalf("a hand module changed the generated table:\n%s\n---\n%s", a, c)
	}
	if dep := row(t, plain, "codemap:a").Deps; len(dep) != 1 || dep[0].Module != "codemap:b" {
		t.Fatalf("deps %+v", dep)
	}
}

// Agent rows are carried over — paths, by and evidence never re-inferred —
// while their deps are recomputed, so a dependency on a module that was since
// removed or renamed never blocks regeneration.
func TestAgentRowsCarriedOver(t *testing.T) {
	committed := "contract: 1\nmodules:\n" +
		"  - {name: billing, provider: agent, by: \"agent:claudecode/opus5_5\", paths: [\"billing/**\"], evidence: [\"review:run-1\"], " +
		"deps: [{module: codemap:lib, evidence: {from: billing/x.sh, to: lib/l.sh}}]}\n" +
		"  - {name: codemap:lib, provider: codemap, root: lib, evidence: [\"entry:lib\"]}\n"
	for name, tc := range map[string]struct {
		codemap, target string
		deps            []string
	}{
		"kept":    {"  - {name: lib, path: lib/}\n", "lib/l.sh", []string{"codemap:lib"}},
		"removed": {"  - {name: other, path: other/}\n", "lib/l.sh", nil},
		"renamed": {"  - {name: library, path: library/}\n", "library/l.sh", []string{"codemap:library"}},
	} {
		t.Run(name, func(t *testing.T) {
			r := repo(t, map[string]string{
				registry.ModulesPath: committed,
				registry.CodemapPath: codemapHead + tc.codemap,
				"billing/x.sh":       "#!/bin/sh\n. ./" + tc.target + "\n",
				tc.target:            "#!/bin/sh\n",
			})
			_, res := infer(t, r)
			got := row(t, res, "billing")
			if got.By != "agent:claudecode/opus5_5" || !slices.Equal(got.Paths, []string{"billing/**"}) || !slices.Equal(got.Evidence, []string{"review:run-1"}) {
				t.Fatalf("agent row boundaries changed: %+v", got)
			}
			var deps []string
			for _, d := range got.Deps {
				deps = append(deps, d.Module)
			}
			if !slices.Equal(deps, tc.deps) {
				t.Fatalf("agent deps %v, want %v", deps, tc.deps)
			}
			if _, err := registry.RenderModules(res.Doc); err != nil {
				t.Fatal(err)
			}
		})
	}
}

// Evidence names the settings file that declared a project, never a nearer
// unrelated one: root settings redirect :api into vendor/, whose own dynamic
// settings file declares nothing about it.
func TestGradleEvidenceNamesTheDeclaringSettings(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle.kts":         "include(\":api\")\nproject(\":api\").projectDir = file(\"vendor/api\")\n",
		"vendor/settings.gradle.kts":  "include(\"${extra}\")\n",
		"vendor/api/build.gradle.kts": "",
		"vendor/api/src/A.kt":         "package a\nclass A\n",
	})
	_, res := infer(t, r)
	api := row(t, res, "gradle:api")
	if !slices.Equal(api.Evidence, []string{"settings:settings.gradle.kts", "build:vendor/api/build.gradle.kts"}) {
		t.Fatalf("gradle:api evidence %v", api.Evidence)
	}
	if v := row(t, res, "gradle:vendor"); !slices.Contains(v.Evidence, "settings:vendor/settings.gradle.kts") || !slices.Contains(v.Evidence, "gradle-dynamic") {
		t.Fatalf("gradle:vendor evidence %v", v.Evidence)
	}
}
