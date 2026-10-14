package gitx_test

import (
	"os"
	"path/filepath"
	"slices"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// Every dirty shape a run's provenance must see: a staged deletion, an
// unstaged deletion, a staged and an unstaged modification, an untracked
// file in a new directory, a staged addition and both sides of a staged
// rename. Ignored files and clean tracked files stay out.
func TestModifiedPaths(t *testing.T) {
	r := fixture.New(t)
	r.History(t, []fixture.Commit{{Task: "1", Desc: "base", Files: map[string]string{
		".gitignore":   "ignored.log\n",
		"staged_del":   "a\n",
		"unstaged_del": "b\n",
		"staged_mod":   "c\n",
		"unstaged_mod": "d\n",
		"rename_from":  "e\n",
		"clean":        "f\n",
	}}})
	r.Run(t, "rm", "-q", "staged_del")
	r.Remove(t, "unstaged_del")
	r.Write(t, "staged_mod", "c2\n")
	r.Run(t, "add", "staged_mod")
	r.Write(t, "unstaged_mod", "d2\n")
	r.Run(t, "mv", "rename_from", "rename_to")
	r.Write(t, "new/dir/untracked", "g\n")
	r.Write(t, "staged_new", "h\n")
	r.Run(t, "add", "staged_new")
	r.Write(t, "ignored.log", "i\n")

	got, err := r.Git.ModifiedPaths(ctx)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"new/dir/untracked", "rename_from", "rename_to", "staged_del", "staged_mod", "staged_new", "unstaged_del", "unstaged_mod"}
	if !slices.Equal(got, want) {
		t.Fatalf("ModifiedPaths = %v\nwant %v", got, want)
	}
	if _, err := os.Stat(filepath.Join(r.Dir, ".git", "index.lock")); !os.IsNotExist(err) {
		t.Fatalf("index.lock left behind: %v", err)
	}
}

// Negative control: a clean tree reports nothing.
func TestModifiedPathsClean(t *testing.T) {
	r := fixture.New(t)
	r.History(t, []fixture.Commit{{Task: "1", Desc: "base", Files: map[string]string{"a": "1\n"}}})
	got, err := r.Git.ModifiedPaths(ctx)
	if err != nil || len(got) != 0 {
		t.Fatalf("clean tree: %v %v", got, err)
	}
}

// Paths with spaces and non-ASCII bytes come back verbatim (-z: no quoting).
func TestModifiedPathsVerbatimNames(t *testing.T) {
	r := fixture.New(t)
	r.History(t, []fixture.Commit{{Task: "1", Desc: "base", Files: map[string]string{"a": "1\n"}}})
	r.Write(t, "dir with space/é.txt", "x\n")
	got, err := r.Git.ModifiedPaths(ctx)
	if err != nil || !slices.Equal(got, []string{"dir with space/é.txt"}) {
		t.Fatalf("got %q %v", got, err)
	}
}

func TestHeadUnbornAndBorn(t *testing.T) {
	r := fixture.New(t)
	head, err := r.Git.Head(ctx)
	if err != nil || head != "" {
		t.Fatalf("unborn: %q %v", head, err)
	}
	r.Write(t, "u", "1\n")
	got, err := r.Git.ModifiedPaths(ctx)
	if err != nil || !slices.Equal(got, []string{"u"}) {
		t.Fatalf("unborn ModifiedPaths: %v %v", got, err)
	}
	id := r.Commit(t, "1", "feature", "first")
	head, err = r.Git.Head(ctx)
	if err != nil || head != id {
		t.Fatalf("born: %q %v want %q", head, err, id)
	}
}

func TestHeadOutsideRepositoryIsAnError(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("GIT_CEILING_DIRECTORIES", filepath.Dir(dir))
	r := fixture.New(t)
	r.Git.Dir = dir
	if head, err := r.Git.Head(ctx); err == nil {
		t.Fatalf("Head outside a repository = %q, nil", head)
	}
}
