package fixture

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestMessageGrammar(t *testing.T) {
	for _, tc := range []struct{ task, typ, desc, want string }{
		{"12", "feature", "add a", "feature: add a (t12)"},
		{"12_3", "bug", "fix b", "bug: fix b (t12_3)"},
	} {
		if got := Message(tc.task, tc.typ, tc.desc); got != tc.want {
			t.Errorf("got %q want %q", got, tc.want)
		}
	}
}

func build(t *testing.T, opts ...Option) (*Repo, []string) {
	r := New(t, opts...)
	ids := r.History(t, []Commit{
		{Task: "12", Desc: "add a", Files: map[string]string{"src/a.go": "package a\n", "README": "r\n"}},
		{Task: "12_3", Type: "bug", Desc: "fix a", Files: map[string]string{"src/a.go": "package a // fixed\n"}},
		{Task: "13", Type: "refactor", Desc: "drop readme", Files: map[string]string{"README": ""}},
	})
	return r, ids
}

func TestHistory(t *testing.T) {
	r, ids := build(t)
	if len(ids) != 3 || ids[2] != r.Head(t) {
		t.Fatalf("ids %v head %s", ids, r.Head(t))
	}
	log := r.Run(t, "log", "--format=%s", "--reverse")
	want := "feature: add a (t12)\nbug: fix a (t12_3)\nrefactor: drop readme (t13)\n"
	if log != want {
		t.Fatalf("log %q want %q", log, want)
	}
	files := r.Run(t, "ls-files")
	if files != "src/a.go\n" {
		t.Fatalf("tracked %q, want the README deleted", files)
	}
	if _, err := os.Stat(filepath.Join(r.Dir, "README")); !os.IsNotExist(err) {
		t.Fatalf("README still in the work tree: %v", err)
	}
	dates := r.Run(t, "log", "--format=%cI", "--reverse")
	if !strings.HasPrefix(dates, "2026-01-01T00:00:00Z\n2026-01-01T00:01:00Z\n") {
		t.Fatalf("dates %q", dates)
	}
}

func TestDeterministic(t *testing.T) {
	_, a := build(t)
	_, b := build(t)
	if strings.Join(a, ",") != strings.Join(b, ",") {
		t.Fatalf("two identical histories produced different ids:\n%v\n%v", a, b)
	}
}

func TestSHA256(t *testing.T) {
	r, ids := build(t, SHA256())
	if r.ObjectFormat() != "sha256" || len(ids[0]) != 64 {
		t.Fatalf("format %s id %s", r.ObjectFormat(), ids[0])
	}
}

func TestCommitMessageVerbatim(t *testing.T) {
	r := New(t)
	r.CommitMessage(t, "Merge branch 'x'")
	if got := strings.TrimSpace(r.Run(t, "log", "-1", "--format=%s")); got != "Merge branch 'x'" {
		t.Fatalf("got %q", got)
	}
}

// The same history must produce the same ids whatever the caller's
// environment says: an inherited identity must not leak into the commits,
// and a user's global ignore rules must not drop fixture files.
func TestIsolatedFromCallerGitConfig(t *testing.T) {
	_, clean := build(t)

	home := t.TempDir()
	xdg := filepath.Join(home, "xdg")
	for path, content := range map[string]string{
		filepath.Join(home, ".gitconfig"):       "[core]\n\texcludesFile = " + filepath.Join(home, "ignore") + "\n[user]\n\tname = Global User\n",
		filepath.Join(home, "ignore"):           "*.go\n",
		filepath.Join(xdg, "git", "ignore"):     "README\n",
		filepath.Join(xdg, "git", "attributes"): "* -text\n",
	} {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", xdg)
	t.Setenv("GIT_AUTHOR_NAME", "Intruder")
	t.Setenv("GIT_AUTHOR_EMAIL", "intruder@example.invalid")
	t.Setenv("GIT_COMMITTER_NAME", "Intruder")
	t.Setenv("GIT_COMMITTER_EMAIL", "intruder@example.invalid")
	t.Setenv("GIT_AUTHOR_DATE", "2001-01-01T00:00:00Z")

	r, polluted := build(t)
	if strings.Join(clean, ",") != strings.Join(polluted, ",") {
		t.Fatalf("inherited git environment changed fixture ids:\n%v\n%v", clean, polluted)
	}
	if got := r.Run(t, "ls-tree", "-r", "--name-only", polluted[0]); got != "README\nsrc/a.go\n" {
		t.Fatalf("first commit tracked %q, want README and src/a.go", got)
	}
	if got := r.Run(t, "log", "-1", "--format=%an <%ae> / %cn <%ce>"); got != "Fixture <fixture@example.invalid> / Fixture <fixture@example.invalid>\n" {
		t.Fatalf("identity %q", got)
	}
}
