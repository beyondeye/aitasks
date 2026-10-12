package registry

import (
	"context"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestScanPersistsVariantsAndCovers(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{ConfigPath: "exclude: [\"tests/golden/**\"]\n"})
	in := Inputs{
		Annotations: fakeAnns{
			{Path: "app/F.kt", Units: []UnitAnnotation{
				{Covers: []Cover{cover("app/Shared.kt", 3)}},
				{Member: "Welcome", Line: 10, Covers: []Cover{cover("app/W.kt", 12), {Source: "app/A.kt", Line: 11}}},
				{Member: "Login", Line: 20},
			}},
			{Path: "tests/golden/g.md", Units: []UnitAnnotation{{Covers: []Cover{cover("x", 1)}}}}, // excluded
			{Path: "tests/test_noedges.sh", Units: []UnitAnnotation{{}}},                           // no covers, no row
		},
		Lister: fakeLister{
			listed("screen-matrix", "app/F.kt#Welcome@rtl", "app/F.kt#Welcome@ltr", "app/F.kt#Login@ltr", "app/F.kt#Welcome@ltr"),
			listed("golden", "tests/golden/g.md@a", "docs/m.md@b"), // excluded path dropped; unannotated base kept for its variants
			listed("bash-file", "tests/test_noedges.sh"),
		},
	}
	res := applyScan(t, root, in)
	if !res.Changed || !reflect.DeepEqual(res.Wrote, []string{ScannedPath}) || len(res.Findings) != 0 {
		t.Fatalf("result %+v", res)
	}
	if res.Units != 4 || res.Edges != 3 || res.Variants != 4 {
		t.Fatalf("counts %d/%d/%d", res.Units, res.Edges, res.Variants)
	}
	want := GeneratedHeader + `contract: 1
units:
  - test: app/F.kt
    covers:
      - source: app/Shared.kt
        line: 3
        stamped_at: "2026-10-01"
        stamped_blob: "0123456789"
  - test: app/F.kt#Login
    line: 20
    variants: [ltr]
  - test: app/F.kt#Welcome
    line: 10
    variants: [ltr, rtl]
    covers:
      - source: app/A.kt
        line: 11
      - source: app/W.kt
        line: 12
        stamped_at: "2026-10-01"
        stamped_blob: "0123456789"
  - test: docs/m.md
    variants: [b]
`
	if got := readFile(t, root, ScannedPath); got != want {
		t.Fatalf("_scanned.yaml:\n%s\nwant:\n%s", got, want)
	}
	// The written file loads back into the same units.
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(reg.Units) != 4 || len(reg.Edges) != 3 {
		t.Fatalf("reloaded %d units %d edges", len(reg.Units), len(reg.Edges))
	}
}

func TestScanReapplyIsByteIdentical(t *testing.T) {
	root, in := cleanRepo(t)
	path := filepath.Join(root, filepath.FromSlash(ScannedPath))
	before, _ := os.ReadFile(path)
	fi1, _ := os.Stat(path)
	res := applyScan(t, root, in)
	if res.Changed || len(res.Wrote) != 0 {
		t.Fatalf("re-apply with no change wrote: %+v", res)
	}
	after, _ := os.ReadFile(path)
	fi2, _ := os.Stat(path)
	if string(before) != string(after) || !fi1.ModTime().Equal(fi2.ModTime()) {
		t.Fatal("re-apply changed the file")
	}
}

func TestScanDryRunReportsWithoutWriting(t *testing.T) {
	root, in := cleanRepo(t)
	in.Annotations = fakeAnns{{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: []Cover{cover("src/a.sh", 2), cover("src/b.sh", 3)}}}}}
	before := readFile(t, root, ScannedPath)
	res, err := Scan(context.Background(), root, in, false)
	if err != nil || !res.Changed || len(res.Wrote) != 0 {
		t.Fatalf("%+v %v", res, err)
	}
	if readFile(t, root, ScannedPath) != before {
		t.Fatal("a dry run wrote")
	}
}

// Member drift refuses the write: scan never guesses across a rename.
func TestScanRefusesOnMemberDrift(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{ConfigPath: ""})
	in := Inputs{
		Annotations: fakeAnns{{Path: "app/F.kt", Units: []UnitAnnotation{{Member: "Welcome", Line: 3}, {Member: "Gone", Line: 9}}}},
		Lister:      fakeLister{listed("r", "app/F.kt#Welcome", "app/F.kt#Renamed@v")},
	}
	res := applyScan(t, root, in)
	if len(res.Wrote) != 0 {
		t.Fatalf("wrote despite drift: %+v", res)
	}
	got := lines(t, res.Findings)
	want := []string{"DEAD_MEMBER:app/F.kt#Gone", "UNANNOTATED_MEMBER:app/F.kt#Renamed"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("findings %v, want %v", got, want)
	}
	for _, f := range res.Findings {
		if !f.Fail {
			t.Fatalf("member drift must fail: %+v", f)
		}
	}
	if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(ScannedPath))); !os.IsNotExist(err) {
		t.Fatal("_scanned.yaml exists")
	}
}

// A file with no testmap:unit block is a plain file unit, whatever granularity
// its runner lists at: no UNANNOTATED_MEMBER for each listed method.
func TestNoMemberDriftForFileWithoutBlocks(t *testing.T) {
	_, drift := BuildScanned(Defaults(),
		fakeAnns{{Path: "tests/test_x.py", Units: []UnitAnnotation{{Covers: []Cover{cover("x.py", 1)}}}}},
		fakeLister{listed("pytest", "tests/test_x.py#test_one", "tests/test_x.py#test_two")})
	if len(drift) != 0 {
		t.Fatalf("drift %+v", drift)
	}
	// and a block in a file no runner lists is UNREGISTERED's business, not dead
	_, drift = BuildScanned(Defaults(),
		fakeAnns{{Path: "app/G.kt", Units: []UnitAnnotation{{Member: "M"}}}}, fakeLister{})
	if len(drift) != 0 {
		t.Fatalf("drift %+v", drift)
	}
}
