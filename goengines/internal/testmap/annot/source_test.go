package annot

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

func TestSource(t *testing.T) {
	r := repo(t, map[string]string{
		".gitignore":        "build/\n",
		"tests/b.sh":        "#!/bin/sh\n# testmap:covers src/b.sh @2026-01-01/0123456789\n# testmap:unit M\n# testmap:covers src/m.sh\n",
		"tests/a_test.go":   "package a\n\n// testmap:covers src/a.go\nvar s = `\n// testmap:covers src/raw.go\n`\n",
		"tests/plain.sh":    "#!/bin/sh\necho\n",
		"tests/kind.py":     "# testmap:kind unit\n",
		"tests/look.sh":     "cat <<EOF\n# testmap:covers src/look.sh\nEOF\n",
		"tests/notes.md":    "# testmap:covers src/md\n",
		"tests/golden/g.sh": "# testmap:covers src/excluded.sh\n",
		"build/gen.sh":      "# testmap:covers src/ignored.sh\n",
		"moved/t.sh":        "# testmap:covers src/moved.sh\n",
		"gone/t.sh":         "# testmap:covers src/gone.sh\n",
		"tests/split.py":    "\"test\" \"map:covers src/split.sh\"\n",    // the token only in the docstring's value
		"tests/call.py":     "\"testmap:covers src/call.sh\"(\"arg\")\n", // a call: no docstring
	})
	r.Commit(t, "1", "test", "fixtures")
	// A tracked directory replaced by a link to an annotated copy, and a
	// tracked file deleted since the index: neither is read.
	other := t.TempDir()
	writeFile(t, other, "t.sh", "# testmap:covers src/via-link.sh\n", 0o644)
	if err := os.RemoveAll(filepath.Join(r.Dir, "moved")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(other, filepath.Join(r.Dir, "moved")); err != nil {
		t.Fatal(err)
	}
	r.Remove(t, "gone/t.sh")
	r.Write(t, "tests/untracked.sh", "# testmap:covers src/new.sh\n")
	if err := os.Symlink("b.sh", filepath.Join(r.Dir, "tests/link.sh")); err != nil {
		t.Fatal(err)
	}
	got, err := Source{}.Annotations(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	out, _ := json.Marshal(got)
	want := `[{"Path":"tests/a_test.go","Units":[{"Member":"","Line":0,"Covers":[{"Source":"src/a.go","Line":3,"StampedAt":"","StampedBlob":""}]}]},` +
		`{"Path":"tests/b.sh","Units":[{"Member":"","Line":0,"Covers":[{"Source":"src/b.sh","Line":2,"StampedAt":"2026-01-01","StampedBlob":"0123456789"}]},` +
		`{"Member":"M","Line":3,"Covers":[{"Source":"src/m.sh","Line":4,"StampedAt":"","StampedBlob":""}]}]},` +
		`{"Path":"tests/kind.py","Units":[{"Member":"","Line":0,"Covers":null}]},` +
		`{"Path":"tests/split.py","Units":[{"Member":"","Line":0,"Covers":[{"Source":"src/split.sh","Line":1,"StampedAt":"","StampedBlob":""}]}]},` +
		`{"Path":"tests/untracked.sh","Units":[{"Member":"","Line":0,"Covers":[{"Source":"src/new.sh","Line":1,"StampedAt":"","StampedBlob":""}]}]}]`
	if string(out) != want {
		t.Errorf("got  %s\nwant %s", out, want)
	}
}

func TestSourceErrors(t *testing.T) {
	r := repo(t, map[string]string{"tests/bad.sh": "#!/bin/sh\n\n# testmap:covres src/a.sh\n"})
	_, err := Source{}.Annotations(bg, r.Dir)
	if err == nil || !strings.Contains(err.Error(), "tests/bad.sh:3: unknown key") {
		t.Errorf("syntax error: %v", err)
	}
	r = repo(t, map[string]string{"tests/open.sh": "cat <<EOF\n# testmap:covers a\n"})
	if _, err := (Source{}).Annotations(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "tests/open.sh:1: cannot determine comment context") {
		t.Errorf("uncertain: %v", err)
	}
	if os.Geteuid() != 0 {
		r = repo(t, map[string]string{"locked/t.sh": "# testmap:covers a\n"})
		dir := filepath.Join(r.Dir, "locked")
		os.Chmod(dir, 0o000)
		t.Cleanup(func() { os.Chmod(dir, 0o755) })
		if _, err := (Source{}).Annotations(bg, r.Dir); err == nil {
			t.Error("unreadable directory read as empty")
		}
	}
	// An undecodable escape that could decide an annotation fails the scan
	// (review round 4), never a silent omission or a wrong source.
	for _, doc := range []string{"\"prose \\N{LINE FEED} testmap:covers src/a.sh\"\n", "\"\u00a0testmap:covers src/\\N{BULLET}.sh\"\n"} {
		r = repo(t, map[string]string{"tests/t.py": doc})
		if _, err := (Source{}).Annotations(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "tests/t.py:1: cannot decode") {
			t.Errorf("%q: %v", doc, err)
		}
	}
	// Through registry.Scan: the error becomes INPUT_ERROR:annotations.
	r = repo(t, map[string]string{"tests/bad.sh": "# testmap:covers ../up.sh\n"})
	_, err = registry.Scan(bg, r.Dir, registry.Inputs{Annotations: Source{}, Lister: emptyLister{}}, false)
	if ie, ok := err.(*registry.InputError); !ok || ie.Input != registry.InputAnnotations {
		t.Errorf("scan: %v", err)
	}
}

type emptyLister struct{}

func (emptyLister) List(context.Context, string) ([]registry.Listing, error) { return nil, nil }

// The runner keys reach the registry (M3.1's named extension of toRegistry):
// a file-level override, batch flag and needs, a member's own values, and a
// member that sets none of them.
func TestSourceCarriesRunnerBatchNeeds(t *testing.T) {
	r := repo(t, map[string]string{
		"tests/r.sh": "#!/bin/sh\n# testmap:runner shell\n# testmap:batch no\n# testmap:needs repo-git-index emulator\n# testmap:needs heavy-run\n" +
			"# testmap:unit A\n# testmap:runner other\n# testmap:batch yes\n# testmap:needs gpu\n# testmap:unit B\n# testmap:covers src/b.sh\n",
	})
	got, err := Source{}.Annotations(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	out, _ := json.Marshal(got)
	want := `[{"Path":"tests/r.sh","Units":[` +
		`{"Member":"","Line":0,"Covers":null,"Runner":"shell","Batch":"no","Needs":["repo-git-index","emulator","heavy-run"]},` +
		`{"Member":"A","Line":6,"Covers":null,"Runner":"other","Batch":"yes","Needs":["gpu"]},` +
		`{"Member":"B","Line":10,"Covers":[{"Source":"src/b.sh","Line":11,"StampedAt":"","StampedBlob":""}]}]}]`
	if string(out) != want {
		t.Errorf("got  %s\nwant %s", out, want)
	}
}
