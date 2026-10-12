package registry

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// unreadable makes a directory unreadable for the rest of the test. It skips
// when permissions are not enforced (running as root).
func unreadable(t *testing.T, dir string) {
	t.Helper()
	if os.Geteuid() == 0 {
		t.Skip("permissions are not enforced for root")
	}
	if err := os.Chmod(dir, 0o000); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.Chmod(dir, 0o755) })
}

func TestMatchFilesExistingFilesOnly(t *testing.T) {
	r := fixture.New(t)
	r.Write(t, "artifacts/kept.json", "{}")
	r.Write(t, "artifacts/deleted.json", "{}")
	r.Commit(t, "1", "feature", "artifacts")
	r.Remove(t, "artifacts/deleted.json")                // tracked, gone from disk: never a candidate
	r.Write(t, ".gitignore", "artifacts/ignored.json\n") // existing but ignored: a candidate
	r.Write(t, "artifacts/ignored.json", "{}")
	r.Write(t, "artifacts/untracked.json", "{}")
	got, err := MatchFiles(r.Dir, []string{"artifacts/*.json"}, nil)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"artifacts/ignored.json", "artifacts/kept.json", "artifacts/untracked.json"}
	if !reflect.DeepEqual(got["artifacts/*.json"], want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestMatchFilesExcludeAndGit(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{
		"a/x.json": "", "a/drop.json": "", "a/cache/y.json": "",
		"a/.git/HEAD": "", ".git/config.json": "",
	})
	got, err := MatchFiles(root, []string{"**/*.json", "a/**"}, []string{"a/drop.json", "a/cache/**"})
	if err != nil {
		t.Fatal(err)
	}
	if want := []string{"a/x.json"}; !reflect.DeepEqual(got["**/*.json"], want) {
		t.Fatalf("**/*.json: %v", got["**/*.json"])
	}
	if want := []string{"a/x.json"}; !reflect.DeepEqual(got["a/**"], want) {
		t.Fatalf("a/**: %v (.git metadata is never a work-tree file)", got["a/**"])
	}
}

// No nested-repository pruning: broad and narrow patterns agree, and only
// exclude: removes the nested checkout's files.
func TestMatchFilesNestedRepositoryIsMonotonic(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{
		"artifacts/a.json": "", "artifacts/vendor/b.json": "", "artifacts/vendor/.git/HEAD": "",
	})
	broad, narrow := "artifacts/**/*.json", "artifacts/vendor/**/*.json"
	got, err := MatchFiles(root, []string{broad, narrow}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !contains(got[broad], "artifacts/vendor/b.json") || !contains(got[narrow], "artifacts/vendor/b.json") {
		t.Fatalf("nested checkout not found by both: %v", got)
	}
	got, err = MatchFiles(root, []string{broad, narrow}, []string{"artifacts/vendor/**"})
	if err != nil {
		t.Fatal(err)
	}
	if contains(got[broad], "artifacts/vendor/b.json") || len(got[narrow]) != 0 {
		t.Fatalf("exclude did not remove it from both: %v", got)
	}
}

// A shallow pattern never opens an unreadable directory it cannot match into;
// a pattern that does reach it fails rather than reporting a partial list.
func TestMatchFilesUnreadableDirectory(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{"artifacts/a.json": "", "artifacts/cache/c.json": ""})
	unreadable(t, filepath.Join(root, "artifacts", "cache"))

	got, err := MatchFiles(root, []string{"artifacts/*.json"}, nil)
	if err != nil {
		t.Fatalf("shallow pattern opened the irrelevant directory: %v", err)
	}
	if !reflect.DeepEqual(got["artifacts/*.json"], []string{"artifacts/a.json"}) {
		t.Fatalf("got %v", got)
	}
	if _, err := MatchFiles(root, []string{"artifacts/**/*.json"}, nil); err == nil || !strings.Contains(err.Error(), "cache") {
		t.Fatalf("a relevant unreadable directory must fail, naming it: %v", err)
	}
	if _, err := MatchFiles(root, []string{"artifacts/**/*.json"}, []string{"artifacts/cache/**"}); err != nil {
		t.Fatalf("an excluded unreadable directory must not be read: %v", err)
	}
}

// Symbolic links to directories are never followed, whatever the pattern's
// spelling: a literal prefix through the link matches nothing, exactly like a
// broad pattern that meets the link during the walk.
func TestMatchFilesNeverFollowsDirectorySymlinks(t *testing.T) {
	root, outside := t.TempDir(), t.TempDir()
	writeTree(t, outside, map[string]string{"x.json": "", "deep/y.json": ""})
	writeTree(t, root, map[string]string{"artifacts/a.json": ""})
	if err := os.Symlink(outside, filepath.Join(root, "artifacts", "linked")); err != nil {
		t.Fatal(err)
	}
	patterns := []string{"artifacts/**/*.json", "artifacts/linked/*.json", "artifacts/linked/**/*.json", "artifacts/linked/x.json"}
	got, err := MatchFiles(root, patterns, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got["artifacts/**/*.json"], []string{"artifacts/a.json"}) {
		t.Errorf("broad: %v", got["artifacts/**/*.json"])
	}
	for _, p := range patterns[1:] {
		if len(got[p]) != 0 {
			t.Errorf("%s followed the symlink: %v", p, got[p])
		}
	}
}
