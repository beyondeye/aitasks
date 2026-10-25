package modules

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

type benchAnns []registry.FileAnnotations

func (a benchAnns) Annotations(context.Context, string) ([]registry.FileAnnotations, error) {
	return a, nil
}

type benchLister []registry.Listing

func (l benchLister) List(context.Context, string) ([]registry.Listing, error) { return l, nil }

// benchInputs are `check`'s two inputs over the shape, sized like the real
// registry: every test file (310 bash, 350 Python) annotated with one to three
// covers of the sources it invokes or imports; every 20th file with three
// members of four variants each, listed with golden artifacts under docs/;
// one bash-file runner listing them all, its artifact glob over docs/.
func benchInputs() registry.Inputs {
	var anns benchAnns
	lister := registry.Listing{Runner: "bash-file", ArtifactGlobs: []string{"docs/**/*.md"}}
	add := func(i int, path string, covers []registry.Cover) {
		fa := registry.FileAnnotations{Path: path, Units: []registry.UnitAnnotation{{Covers: covers}}}
		if i%20 == 0 {
			for m := range 3 {
				member := fmt.Sprintf("M%d", m)
				fa.Units = append(fa.Units, registry.UnitAnnotation{Member: member, Line: 10 + m,
					Covers: []registry.Cover{{Source: fmt.Sprintf(".aitask-scripts/lib/mod%d.py", (i+m)%290), Line: 11 + m}}})
				for v := range 4 {
					idx := (i*12 + m*4 + v) % 900
					lister.Units = append(lister.Units, registry.ListedUnit{
						ID: registry.ID{Path: path, Member: member, Variant: fmt.Sprintf("v%d", v)}, Kind: "unit",
						Artifact: fmt.Sprintf("docs/d%d/page%d.md", idx%30, idx)})
				}
			}
		} else {
			lister.Units = append(lister.Units, registry.ListedUnit{ID: registry.ID{Path: path}, Kind: "unit"})
		}
		lister.Bound = append(lister.Bound, path)
		anns = append(anns, fa)
	}
	for i := range 310 {
		var covers []registry.Cover
		for k := range 1 + i%3 {
			covers = append(covers, registry.Cover{Source: fmt.Sprintf(".aitask-scripts/aitask_s%d.sh", (i*3+k)%300), Line: 5 + k})
		}
		add(i, fmt.Sprintf("tests/test_t%d.sh", i), covers)
	}
	for i := range 350 {
		add(i, fmt.Sprintf("tests/test_p%d.py", i), []registry.Cover{{Source: fmt.Sprintf(".aitask-scripts/lib/mod%d.py", i%290), Line: 7}})
	}
	return registry.Inputs{Annotations: anns, Lister: benchLister{lister}}
}

// benchRepo is the aitasks shape plus what the providers read: a codemap
// with nested entries over the whole tree, a Gradle build of six projects
// with Kotlin sources, and a committed `_modules.yaml` equal to the live
// inference (so `check` compares and finds no drift — the steady state).
func benchRepo(b *testing.B) (string, *Result) {
	b.Helper()
	b.Setenv("XDG_CACHE_HOME", b.TempDir())
	b.Setenv("GOTOOLCHAIN", "local")
	b.Setenv("GOFLAGS", "")
	b.Setenv("GOWORK", "off")
	r := fixture.New(b)
	fixture.AitasksShape(b, r)
	var cm strings.Builder
	cm.WriteString("version: 1\nareas:\n")
	cm.WriteString("  - name: scripts\n    path: .aitask-scripts/\n    children:\n      - {name: lib, path: .aitask-scripts/lib/}\n")
	cm.WriteString("  - name: tests\n    path: tests/\n  - name: goengines\n    path: goengines/\n    children:\n")
	for i := range 12 {
		fmt.Fprintf(&cm, "      - {name: p%d, path: goengines/p%d/}\n", i, i)
	}
	cm.WriteString("  - name: docs\n    path: docs/\n    children:\n")
	for i := range 30 {
		fmt.Fprintf(&cm, "      - {name: d%d, path: docs/d%d/}\n", i, i)
	}
	r.Write(b, registry.CodemapPath, cm.String())
	var settings strings.Builder
	projects := []string{"core", "data", "ui", "feature:auth", "feature:pay", "app"}
	for _, p := range projects {
		fmt.Fprintf(&settings, "include(\":android:%s\")\n", p)
		dir := "android/" + strings.ReplaceAll(p, ":", "/")
		r.Write(b, dir+"/build.gradle.kts", "dependencies { implementation(project(\":android:core\")) }\n")
		for k := range 8 {
			r.Write(b, fmt.Sprintf("%s/src/main/kotlin/x/F%d.kt", dir, k), fmt.Sprintf("package x\n\nimport x.F%d\n\nclass F%d\n", (k+1)%8, k))
		}
	}
	r.Write(b, "settings.gradle.kts", settings.String())
	r.Write(b, registry.ConfigPath, "contract: 1\nbootstrap_until: 2099-01-01\n")
	r.Write(b, registry.RegistryDir+"/scripts.yaml", `contract: 1
owns: [".aitask-scripts/*.sh"]
rules:
  - {name: scripts-all, when: [".aitask-scripts/aitask_s1*.sh"], select: ["tests/test_t1*.sh"], distance: 2}
  - {name: scripts-esc, when: [".aitask-scripts/aitask_s99.sh"], escalate: true}
waivers:
  - {path: ".aitask-scripts/aitask_s5*.sh", reason: display-only, until: 2099-01-01}
`)
	r.Write(b, registry.RegistryDir+"/lib.yaml", `contract: 1
owns: [".aitask-scripts/lib/**"]
edges:
  - {test: tests/test_t1.sh, covers: [.aitask-scripts/lib/mod1.py, .aitask-scripts/lib/mod2.py]}
rules:
  - {name: lib-all, when: [".aitask-scripts/lib/**"], select: ["tests/test_p*.py"]}
`)
	root := r.Dir
	if _, err := registry.Scan(context.Background(), root, benchInputs(), true); err != nil {
		b.Fatal(err)
	}
	reg, err := registry.Load(root)
	if err != nil {
		b.Fatal(err)
	}
	res, err := Scan(context.Background(), root, reg)
	if err != nil {
		b.Fatal(err)
	}
	data, err := registry.RenderModules(res.Doc)
	if err != nil {
		b.Fatal(err)
	}
	r.Write(b, registry.ModulesPath, string(data))
	if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(registry.ModulesPath))); err != nil {
		b.Fatal(err)
	}
	return root, res
}

// BenchmarkCheckModulesDrift is `check --strict` on the aitasks shape with a
// populated registry (≈660 annotated tests, their covers, member variants
// with artifacts, two hand files with owns / rules / edges / waivers, the
// persisted `_scanned.yaml`) and a declared modules table: every core, scoped
// and adoption rule plus the warm dependency scan, the providers, the
// resolution over the whole universe and the drift comparison. Budget:
// < 300 ms (proposal: `check` including MODULES_DRIFT).
func BenchmarkCheckModulesDrift(b *testing.B) {
	root, res := benchRepo(b)
	reg, err := registry.Load(root)
	if err != nil {
		b.Fatal(err)
	}
	rs, err := registry.ModulesOf(reg).Resolve(res.Files)
	if err != nil {
		b.Fatal(err)
	}
	in := benchInputs()
	if len(reg.Units) < 600 || len(reg.Edges) < 600 || len(reg.Rules) != 3 || len(reg.Waivers) != 1 {
		b.Fatalf("the check workload is not representative: %d units, %d edges, %d rules, %d waivers", len(reg.Units), len(reg.Edges), len(reg.Rules), len(reg.Waivers))
	}
	b.Logf("universe %d files, %d modules, %d unmapped, %d conflicts; %d scanned units, %d edges", len(res.Files), len(rs.Modules), len(rs.Unmapped), len(rs.Conflicts), len(reg.Units), len(reg.Edges))
	ctx := context.Background()
	b.ResetTimer()
	for b.Loop() {
		out, err := registry.Check(ctx, root, in, registry.CheckOptions{Strict: true})
		if err != nil {
			b.Fatal(err)
		}
		for _, f := range out.Findings {
			if f.Rule == registry.RuleModulesDrift || f.Rule == registry.RuleScanDrift {
				b.Fatalf("a committed generated file drifted: %v", f.Fields)
			}
		}
	}
}
