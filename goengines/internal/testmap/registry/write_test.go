package registry

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestWriteFileOnlyOnChange(t *testing.T) {
	path := filepath.Join(t.TempDir(), "sub", "f.yaml")
	changed, err := WriteFile(path, []byte("a: 1\n"))
	if err != nil || !changed {
		t.Fatalf("first write: %v %v", changed, err)
	}
	old := time.Now().Add(-time.Hour).Truncate(time.Second)
	if err := os.Chtimes(path, old, old); err != nil {
		t.Fatal(err)
	}
	changed, err = WriteFile(path, []byte("a: 1\n"))
	if err != nil || changed {
		t.Fatalf("identical write: %v %v", changed, err)
	}
	fi, _ := os.Stat(path)
	if !fi.ModTime().Equal(old) {
		t.Fatal("an identical write touched the file")
	}
	if fi.Mode().Perm() != 0o644 {
		t.Fatalf("mode %v", fi.Mode().Perm())
	}
	if changed, err = WriteFile(path, []byte("a: 2\n")); err != nil || !changed {
		t.Fatalf("changed write: %v %v", changed, err)
	}
	entries, _ := os.ReadDir(filepath.Dir(path))
	if len(entries) != 1 {
		t.Fatalf("temporary files left behind: %v", entries)
	}
}

func TestRenderDeterministic(t *testing.T) {
	doc := ScannedDoc{Contract: 1, Units: []ScannedRow{
		{Test: "a.kt#M", Line: 4, Variants: []string{"x", "y"}, Covers: []ScannedCover{{Source: "s.kt", Line: 5, StampedAt: "2026-10-01", StampedBlob: "0123456789"}}},
	}}
	a, err := RenderScanned(doc)
	if err != nil {
		t.Fatal(err)
	}
	b, _ := RenderScanned(doc)
	if string(a) != string(b) {
		t.Fatal("render is not deterministic")
	}
	want := GeneratedHeader + `contract: 1
units:
  - test: a.kt#M
    line: 4
    variants: [x, "y"]
    covers:
      - source: s.kt
        line: 5
        stamped_at: "2026-10-01"
        stamped_blob: "0123456789"
`
	if string(a) != want {
		t.Fatalf("render:\n%s\nwant:\n%s", a, want)
	}
}
