package registry

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// Fixture implementations of the two injected inputs: in-memory stand-ins for
// M2.2's annotation scanner and M3.1's runner repository.

type fakeAnns []FileAnnotations

func (f fakeAnns) Annotations(context.Context, string) ([]FileAnnotations, error) { return f, nil }

type fakeLister []Listing

func (f fakeLister) List(context.Context, string) ([]Listing, error) { return f, nil }

type failingAnns struct{ err error }

func (f failingAnns) Annotations(context.Context, string) ([]FileAnnotations, error) {
	return nil, f.err
}

type failingLister struct{ err error }

func (f failingLister) List(context.Context, string) ([]Listing, error) { return nil, f.err }

// writeTree writes repository-relative files under root.
func writeTree(t testing.TB, root string, files map[string]string) {
	t.Helper()
	for p, content := range files {
		full := filepath.Join(root, filepath.FromSlash(p))
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
}

func readFile(t testing.TB, root, p string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(p)))
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

// cover is a stamped Cover.
func cover(src string, line int) Cover {
	return Cover{Source: src, Line: line, StampedAt: "2026-10-01", StampedBlob: "0123456789"}
}

func listed(runner string, ids ...string) Listing {
	l := Listing{Runner: runner}
	for _, s := range ids {
		l.Units = append(l.Units, ListedUnit{ID: MustParseID(s), Kind: "unit", Lowering: s})
	}
	return l
}

// cleanRepo is a registry that checks clean: one annotated, stamped, listed
// bash test; config with a future bootstrap window; `_scanned.yaml` applied.
func cleanRepo(t testing.TB) (root string, in Inputs) {
	t.Helper()
	root = t.TempDir()
	writeTree(t, root, map[string]string{
		ConfigPath:              "contract: 1\nbootstrap_until: 2099-01-01\n",
		"tests/test_a.sh":       "#!/usr/bin/env bash\n# testmap:covers src/a.sh @2026-10-01/0123456789\n",
		"src/a.sh":              "echo a\n",
		"src/b.sh":              "echo b\n",
		RegistryDir + "/x.yaml": "contract: 1\nowns: [\"src/**\"]\n",
	})
	in = Inputs{
		Annotations: fakeAnns{{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: []Cover{cover("src/a.sh", 2)}}}}},
		Lister:      fakeLister{listed("bash-file", "tests/test_a.sh")},
	}
	applyScan(t, root, in)
	return root, in
}

func applyScan(t testing.TB, root string, in Inputs) *ScanResult {
	t.Helper()
	res, err := Scan(context.Background(), root, in, true)
	if err != nil {
		t.Fatal(err)
	}
	return res
}

// atDay pins the check clock.
func atDay(t testing.TB, day string) {
	t.Helper()
	d, err := time.Parse(time.DateOnly, day)
	if err != nil {
		t.Fatal(err)
	}
	old := now
	now = func() time.Time { return d }
	t.Cleanup(func() { now = old })
}

func runCheck(t testing.TB, root string, in Inputs, strict bool) *CheckResult {
	t.Helper()
	res, err := Check(context.Background(), root, in, CheckOptions{Strict: strict})
	if err != nil {
		t.Fatal(err)
	}
	return res
}

// lines renders findings as protocol lines.
func lines(t testing.TB, fs []Finding) []string {
	t.Helper()
	var out []string
	for _, f := range fs {
		l, err := f.Line()
		if err != nil {
			t.Fatal(err)
		}
		out = append(out, l)
	}
	return out
}

// only returns the lines of one rule.
func only(t testing.TB, res *CheckResult, rule string) []string {
	t.Helper()
	var fs []Finding
	for _, f := range res.Findings {
		if f.Rule == rule {
			fs = append(fs, f)
		}
	}
	return lines(t, fs)
}
