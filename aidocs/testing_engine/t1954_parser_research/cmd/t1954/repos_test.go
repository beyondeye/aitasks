package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"testing"
)

func TestParseRepoEntry(t *testing.T) {
	for _, c := range []struct {
		in, name, path string
		explicit       bool
	}{
		{"thinking_app", "thinking_app", "", false},
		{" aitasks_go ", "aitasks_go", "", false},
		{"aitasks=/tmp/snap/aitasks", "aitasks", "/tmp/snap/aitasks", true},
		{"x=", "x", "", true},
	} {
		n, p, e := parseRepoEntry(c.in)
		if n != c.name || p != c.path || e != c.explicit {
			t.Errorf("parseRepoEntry(%q) = %q %q %v, want %q %q %v", c.in, n, p, e, c.name, c.path, c.explicit)
		}
	}
	if _, err := resolveRepo("/nonexistent", "x="); err == nil {
		t.Error("an explicit entry with an empty path must be an error")
	}
}

// An explicit checkout is labelled with its commit, and a dirty one says so:
// the label must never claim a commit the walked bytes do not match.
func TestDescribeCheckout(t *testing.T) {
	dir := t.TempDir()
	git := func(args ...string) {
		t.Helper()
		cmd := exec.Command("git", append([]string{"-C", dir, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"}, args...)...)
		if out, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("git %v: %v\n%s", args, err, out)
		}
	}
	git("init", "-q")
	if err := os.WriteFile(filepath.Join(dir, "a.sh"), []byte("# a\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	git("add", "a.sh")
	git("commit", "-q", "-m", "c")
	in, err := resolveRepo("/nonexistent", "r="+dir)
	if err != nil {
		t.Fatal(err)
	}
	if !regexp.MustCompile(`^r@[0-9a-f]{12}$`).MatchString(in.Label) {
		t.Fatalf("clean label %q", in.Label)
	}
	if err := os.WriteFile(filepath.Join(dir, "b.sh"), []byte("# b\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if got := describeCheckout(dir); !regexp.MustCompile(`^@[0-9a-f]{12} \(dirty: 1 paths\)$`).MatchString(got) {
		t.Fatalf("dirty label %q", got)
	}
	if got := describeCheckout(t.TempDir()); got != " (not a git checkout)" {
		t.Fatalf("non-git label %q", got)
	}
}
