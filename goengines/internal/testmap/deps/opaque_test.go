package deps

import (
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// opaqueCase is testdata/opaque/<reason>/case.json: the construct file that
// must be opaque for <reason>, and a test file whose subject the construct
// binds without the graph seeing it (the narrow answer the opaque flag
// guards against). files/ holds the repository, every file with a ".in"
// suffix (stripped when written).
type opaqueCase struct {
	Construct  string `json:"construct"`
	Test       string `json:"test"`
	AndroidRes bool   `json:"android_res"`
	Chmod000   bool   `json:"chmod000"`
	Go         bool   `json:"go"`
	NoGo       bool   `json:"no_go"`
}

func loadOpaqueCase(t *testing.T, reason string) (opaqueCase, *fixture.Repo) {
	t.Helper()
	dir := filepath.Join("testdata", "opaque", reason)
	var c opaqueCase
	data, err := os.ReadFile(filepath.Join(dir, "case.json"))
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(data, &c); err != nil {
		t.Fatal(err)
	}
	r := fixture.New(t)
	root := filepath.Join(dir, "files")
	err = filepath.WalkDir(root, func(p string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		rel, _ := filepath.Rel(root, p)
		content, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		r.Write(t, strings.TrimSuffix(filepath.ToSlash(rel), ".in"), string(content))
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return c, r
}

func scanCase(t *testing.T, c opaqueCase, r *fixture.Repo) *Graph {
	t.Helper()
	return scanRepo(t, r, func(o *Options) {
		if c.AndroidRes {
			o.Config.SymbolScanners = []string{AndroidRes}
		}
	})
}

// Every opaque branch is red-proved: its fixture's construct file is opaque
// with exactly that reason; the test the construct binds does not reach it
// through the graph (so without the flag a change to it would select
// narrowly); and with the branch disabled the file is no longer opaque — the
// flag, and only the flag, stands between that change and the narrow answer.
func TestOpaqueBranchesRedProved(t *testing.T) {
	for _, reason := range opaqueReasons {
		t.Run(reason, func(t *testing.T) {
			c, r := loadOpaqueCase(t, reason)
			if c.Go {
				goEnvFixture(t)
			}
			if c.NoGo {
				old := lookPath
				lookPath = func(string) (string, error) { return "", os.ErrNotExist }
				t.Cleanup(func() { lookPath = old })
			}
			if c.Chmod000 {
				if os.Geteuid() == 0 {
					t.Skip("root reads any file")
				}
				full := filepath.Join(r.Dir, filepath.FromSlash(c.Construct))
				if err := os.Chmod(full, 0); err != nil {
					t.Fatal(err)
				}
				t.Cleanup(func() { os.Chmod(full, 0o644) })
			}
			g := scanCase(t, c, r)
			if got := g.Opaque(c.Construct); got != reason {
				t.Fatalf("opaque(%s) = %q, want %q", c.Construct, got, reason)
			}
			if reached(g, c.Test, c.Construct) || slices.Contains(g.Reverse(c.Construct), c.Test) {
				t.Fatalf("%s reaches %s: the fixture does not model a hidden binding", c.Test, c.Construct)
			}
			disabledOpaque[reason] = true
			t.Cleanup(func() { delete(disabledOpaque, reason) })
			if got := scanCase(t, c, r).Opaque(c.Construct); got != "" {
				t.Fatalf("with %s disabled, opaque(%s) = %q, want transparent", reason, c.Construct, got)
			}
		})
	}
}

// The fixture set and the reason list match exactly: a new reason without a
// fixture, or a fixture naming no reason, fails.
func TestOpaqueFixturesCoverEveryReason(t *testing.T) {
	ents, err := os.ReadDir(filepath.Join("testdata", "opaque"))
	if err != nil {
		t.Fatal(err)
	}
	var dirs []string
	for _, e := range ents {
		if e.IsDir() {
			dirs = append(dirs, e.Name())
		}
	}
	want := slices.Sorted(slices.Values(opaqueReasons))
	if !slices.Equal(dirs, want) {
		t.Fatalf("fixtures %v\nreasons  %v", dirs, want)
	}
}
