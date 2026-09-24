package gitx_test

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/gitx"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

var ctx = context.Background()

func hashObject(t *testing.T, dir string, data []byte) string {
	t.Helper()
	cmd := exec.Command("git", "-C", dir, "hash-object", "--stdin")
	cmd.Env = gitx.Env()
	cmd.Stdin = strings.NewReader(string(data))
	out, err := cmd.Output()
	if err != nil {
		t.Fatal(err)
	}
	return strings.TrimSpace(string(out))
}

func TestBlobDigestMatchesGit(t *testing.T) {
	inputs := [][]byte{[]byte("hello\n"), {}, {0, 1, 2, 0xff, '\n', 0}}
	for _, opt := range []fixture.Option{nil, fixture.SHA256()} {
		var r *fixture.Repo
		if opt == nil {
			r = fixture.New(t)
		} else {
			r = fixture.New(t, opt)
		}
		format, err := r.Git.ObjectFormat(ctx)
		if err != nil || format != r.ObjectFormat() {
			t.Fatalf("ObjectFormat %q, %v", format, err)
		}
		for _, in := range inputs {
			got, err := gitx.BlobDigest(in, format)
			if err != nil {
				t.Fatal(err)
			}
			if want := hashObject(t, r.Dir, in); got != want {
				t.Errorf("%s %q: got %s want %s", format, in, got, want)
			}
		}
	}
	if _, err := gitx.BlobDigest(nil, "md5"); err == nil {
		t.Fatal("unknown format accepted")
	}
}

func TestIsAncestor(t *testing.T) {
	r := fixture.New(t)
	ids := r.History(t, []fixture.Commit{
		{Task: "1", Desc: "one", Files: map[string]string{"a": "1"}},
		{Task: "2", Desc: "two", Files: map[string]string{"a": "2"}},
	})
	if ok, err := r.Git.IsAncestor(ctx, ids[0], ids[1]); !ok || err != nil {
		t.Fatalf("first→second: %v %v", ok, err)
	}
	if ok, err := r.Git.IsAncestor(ctx, ids[1], ids[0]); ok || err != nil {
		t.Fatalf("second→first: %v %v", ok, err)
	}
	ok, err := r.Git.IsAncestor(ctx, "no-such-rev", ids[0])
	var ge *gitx.Error
	if ok || !errors.As(err, &ge) || ge.ExitCode == 1 {
		t.Fatalf("bad rev must be an error, not a no: %v %v", ok, err)
	}
}

func TestLsTree(t *testing.T) {
	r := fixture.New(t)
	r.History(t, []fixture.Commit{{Task: "1", Desc: "tree", Files: map[string]string{
		"top.txt":               "t",
		"dir/sub/with space.sh": "#!/bin/sh\n",
	}}})
	if err := os.Chmod(filepath.Join(r.Dir, "dir/sub/with space.sh"), 0o755); err != nil {
		t.Fatal(err)
	}
	r.Commit(t, "2", "chore", "exec bit")
	entries, err := r.Git.LsTree(ctx, "HEAD")
	if err != nil {
		t.Fatal(err)
	}
	got := map[string]gitx.TreeEntry{}
	for _, e := range entries {
		got[e.Path] = e
	}
	sh, ok := got["dir/sub/with space.sh"]
	if len(entries) != 2 || !ok || sh.Mode != "100755" || sh.Type != "blob" || len(sh.OID) != 40 {
		t.Fatalf("entries %+v", entries)
	}
	if want := hashObject(t, r.Dir, []byte("#!/bin/sh\n")); sh.OID != want {
		t.Fatalf("oid %s want %s", sh.OID, want)
	}
	only, err := r.Git.LsTree(ctx, "HEAD", "top.txt")
	if err != nil || len(only) != 1 || only[0].Path != "top.txt" {
		t.Fatalf("path filter: %+v %v", only, err)
	}
}

func TestRevParse(t *testing.T) {
	r := fixture.New(t)
	id := r.Commit(t, "1", "chore", "empty")
	if got, err := r.Git.RevParse(ctx, "HEAD"); err != nil || got != id {
		t.Fatalf("got %q %v", got, err)
	}
	if _, err := r.Git.RevParse(ctx, "nope"); err == nil {
		t.Fatal("unknown rev resolved")
	}
}

// A GIT_DIR inherited from a hook environment must not redirect gitx away
// from the repository it was pointed at.
func TestEnvScrub(t *testing.T) {
	r := fixture.New(t)
	id := r.Commit(t, "1", "chore", "c")
	t.Setenv("GIT_DIR", "/nonexistent")
	t.Setenv("GIT_WORK_TREE", "/nonexistent")
	t.Setenv("LC_ALL", "de_DE.UTF-8")
	if got, err := r.Git.RevParse(ctx, "HEAD"); err != nil || got != id {
		t.Fatalf("got %q %v", got, err)
	}
	for _, kv := range gitx.Env() {
		if strings.HasPrefix(kv, "GIT_DIR=") || kv == "LC_ALL=de_DE.UTF-8" {
			t.Fatalf("leaked %s", kv)
		}
	}
}

func BenchmarkBlobDigest(b *testing.B) {
	data := make([]byte, 64<<10)
	for i := range data {
		data[i] = byte(i)
	}
	b.SetBytes(int64(len(data)))
	for b.Loop() {
		if _, err := gitx.BlobDigest(data, "sha1"); err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkLsTree(b *testing.B) {
	r := fixture.New(b)
	for i := range 200 {
		r.Write(b, fmt.Sprintf("d%d/f%d.txt", i%10, i), fmt.Sprint(i))
	}
	r.Commit(b, "1", "chore", "200 files")
	for b.Loop() {
		if _, err := r.Git.LsTree(ctx, "HEAD"); err != nil {
			b.Fatal(err)
		}
	}
}

func TestMain(m *testing.M) {
	if _, err := exec.LookPath("git"); err != nil {
		fmt.Fprintln(os.Stderr, "git not on PATH")
		os.Exit(1)
	}
	os.Exit(m.Run())
}
