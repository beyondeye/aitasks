package registry

import (
	"context"
	"fmt"
	"testing"
)

// benchRepo builds the aitasks shape: ~420 test files (1–3 covers each) over
// ~600 sources, ~5 % member files whose members carry variants, two hand files
// with rules and waivers, and one runner artifact glob over ~300 files.
func benchRepo(b *testing.B) (string, Inputs) {
	b.Helper()
	root := b.TempDir()
	files := map[string]string{
		ConfigPath: "contract: 1\nbootstrap_until: 2099-01-01\nexclude: [\"tests/data/**\"]\n",
		RegistryDir + "/scripts.yaml": `contract: 1
owns: [".aitask-scripts/*.sh"]
rules:
  - {name: scripts-all, when: [".aitask-scripts/aitask_1*.sh"], select: ["tests/test_1*.sh"], distance: 2}
  - {name: scripts-esc, when: [".aitask-scripts/aitask_99.sh"], escalate: true}
waivers:
  - {path: ".aitask-scripts/aitask_5*.sh", reason: display-only, until: 2099-01-01}
`,
		RegistryDir + "/lib.yaml": `contract: 1
owns: [".aitask-scripts/lib/**"]
edges:
  - {test: tests/test_0.sh, covers: [.aitask-scripts/lib/m_1.py, .aitask-scripts/lib/m_2.py]}
rules:
  - {name: lib-all, when: [".aitask-scripts/lib/**"], select: ["tests/test_*.py"]}
`,
	}
	for i := 0; i < 400; i++ {
		files[fmt.Sprintf(".aitask-scripts/aitask_%d.sh", i)] = "echo\n"
	}
	for i := 0; i < 200; i++ {
		files[fmt.Sprintf(".aitask-scripts/lib/m_%d.py", i)] = "pass\n"
	}
	for i := 0; i < 300; i++ {
		files[fmt.Sprintf("tests/golden/%d/out_%d.md", i%12, i)] = "g\n"
	}
	var anns fakeAnns
	lister := Listing{Runner: "bash-file", ArtifactGlobs: []string{"tests/golden/**/*.md"}}
	for i := 0; i < 420; i++ {
		path := fmt.Sprintf("tests/test_%d.sh", i)
		if i%3 == 0 {
			path = fmt.Sprintf("tests/test_%d.py", i)
		}
		files[path] = "#\n"
		var covers []Cover
		for k := 0; k <= i%3; k++ {
			covers = append(covers, cover(fmt.Sprintf(".aitask-scripts/aitask_%d.sh", (i*7+k)%400), 2+k))
		}
		fa := FileAnnotations{Path: path, Units: []UnitAnnotation{{Covers: covers}}}
		if i%20 == 0 { // ~5 % member files with variants
			for m := 0; m < 3; m++ {
				member := fmt.Sprintf("M%d", m)
				fa.Units = append(fa.Units, UnitAnnotation{Member: member, Line: 10 + m, Covers: []Cover{cover(fmt.Sprintf(".aitask-scripts/lib/m_%d.py", (i+m)%200), 11+m)}})
				for v := 0; v < 4; v++ {
					id := ID{Path: path, Member: member, Variant: fmt.Sprintf("v%d", v)}
					lister.Units = append(lister.Units, ListedUnit{ID: id, Kind: "unit", Artifact: fmt.Sprintf("tests/golden/%d/out_%d.md", i%12, (i*4+m*4+v)%300)})
				}
			}
		} else {
			lister.Units = append(lister.Units, ListedUnit{ID: ID{Path: path}, Kind: "unit"})
		}
		lister.Bound = append(lister.Bound, path)
		anns = append(anns, fa)
	}
	writeTree(b, root, files)
	in := Inputs{Annotations: anns, Lister: fakeLister{lister}}
	if _, err := Scan(context.Background(), root, in, true); err != nil {
		b.Fatal(err)
	}
	return root, in
}

// BenchmarkScan is `scan` (the dry run: load, build, render, compare) on the
// aitasks shape. Budget: < 300 ms (proposal: Engine binary identity and budget).
func BenchmarkScan(b *testing.B) {
	root, in := benchRepo(b)
	ctx := context.Background()
	b.ResetTimer()
	for b.Loop() {
		res, err := Scan(ctx, root, in, false)
		if err != nil || res.Changed {
			b.Fatalf("%+v %v", res, err)
		}
	}
}

// BenchmarkCheck is `check --strict` on the aitasks shape, including the
// pattern-scoped walk. Budget: < 300 ms.
func BenchmarkCheck(b *testing.B) {
	root, in := benchRepo(b)
	ctx := context.Background()
	b.ResetTimer()
	for b.Loop() {
		res, err := Check(ctx, root, in, CheckOptions{Strict: true})
		if err != nil {
			b.Fatal(err)
		}
		_ = res
	}
}
