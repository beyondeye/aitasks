package annot

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"syscall"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

var testStamp = Stamp{Date: "2026-10-12", Blob: "aaaaaaaaaa"}

func writeFile(t *testing.T, root, rel, content string, mode os.FileMode) {
	t.Helper()
	p := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p, []byte(content), mode); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(p, mode); err != nil {
		t.Fatal(err)
	}
}

func readFile(t *testing.T, root, rel string) string {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(rel)))
	if err != nil {
		t.Fatal(err)
	}
	return string(data)
}

// planOne parses rel under root and plans covering source in member's block.
func planOne(t *testing.T, root, rel, member, source string) (*File, Edit) {
	t.Helper()
	f, err := ParseFile(rel, []byte(readFile(t, root, rel)))
	if err != nil {
		t.Fatal(err)
	}
	e, err := PlanCovers(f, member, source, testStamp)
	if err != nil {
		t.Fatal(err)
	}
	return f, e
}

var placementMember = map[string]string{
	"kotlin_member.kt": "Welcome", "kotlin_member_existing.kt": "Welcome",
}

// Each placement fixture gains one covers line through the real Apply; the
// result is pinned per language (bash after the shebang and the header
// block; Python after the docstring; Go after the package clause; Kotlin
// after the imports or inside the member block).
func TestPlacementGoldens(t *testing.T) {
	ins, _ := filepath.Glob("testdata/placement/*.in")
	if len(ins) == 0 {
		t.Fatal("no fixtures")
	}
	for _, in := range ins {
		name := strings.TrimSuffix(filepath.Base(in), ".in")
		root := t.TempDir()
		data, _ := os.ReadFile(in)
		writeFile(t, root, "tests/"+name, string(data), 0o644)
		f, e := planOne(t, root, "tests/"+name, placementMember[name], "src/new")
		if _, err := Apply(root, EditSet{Path: "tests/" + name, Snapshot: f.Snapshot(), Edits: []Edit{e}}); err != nil {
			t.Errorf("%s: %v", name, err)
			continue
		}
		golden(t, "placement/"+name+".golden", []byte(readFile(t, root, "tests/"+name)))
	}
}

var annotationDiffLine = regexp.MustCompile(`^[+-][ \t]*(#|//)[ \t]*testmap:`)

// Every placement, applied in a real repository, changes comment lines only:
// `git diff -w --ignore-blank-lines` shows nothing but testmap: comments.
func TestPlacementDiffIsCommentsOnly(t *testing.T) {
	r := fixture.New(t)
	ins, _ := filepath.Glob("testdata/placement/*.in")
	for _, in := range ins {
		data, _ := os.ReadFile(in)
		r.Write(t, "tests/"+strings.TrimSuffix(filepath.Base(in), ".in"), string(data))
	}
	r.Commit(t, "1", "test", "fixtures")
	for _, in := range ins {
		rel := "tests/" + strings.TrimSuffix(filepath.Base(in), ".in")
		f, e := planOne(t, r.Dir, rel, placementMember[filepath.Base(rel)], "src/new")
		if _, err := Apply(r.Dir, EditSet{Path: rel, Snapshot: f.Snapshot(), Edits: []Edit{e}}); err != nil {
			t.Fatal(err)
		}
	}
	diff := r.Run(t, "diff", "-w", "--ignore-blank-lines", "-U0")
	n := 0
	for _, l := range strings.Split(diff, "\n") {
		if strings.HasPrefix(l, "+++") || strings.HasPrefix(l, "---") || (!strings.HasPrefix(l, "+") && !strings.HasPrefix(l, "-")) {
			continue
		}
		n++
		if !annotationDiffLine.MatchString(l) {
			t.Errorf("non-annotation diff line: %q", l)
		}
	}
	if n != len(ins) {
		t.Errorf("%d changed lines, want %d", n, len(ins))
	}
}

func TestRestampLine(t *testing.T) {
	cases := map[string]string{
		"# testmap:covers a.sh":                               "# testmap:covers a.sh @2026-10-12/aaaaaaaaaa",
		"    // testmap:covers a.kt   @2026-01-01/0123456789": "    // testmap:covers a.kt   @2026-10-12/aaaaaaaaaa",
		"#testmap:covers\ta.sh\t@2026-01-01/0123456789  ":     "#testmap:covers\ta.sh\t@2026-10-12/aaaaaaaaaa  ",
	}
	for in, want := range cases {
		if got, err := RestampLine(in, testStamp); err != nil || got != want {
			t.Errorf("%q: got %q %v, want %q", in, got, err, want)
		}
	}
}

func TestApplyKeepsModeLineEndingsAndFinalNewline(t *testing.T) {
	root := t.TempDir()
	writeFile(t, root, "tests/exec.sh", "#!/bin/sh\n# header\necho\n", 0o755)
	writeFile(t, root, "tests/crlf.sh", "#!/bin/sh\r\n# testmap:covers src/a @2026-01-01/0123456789\r\necho\r\n", 0o644)
	writeFile(t, root, "tests/nonl.sh", "#!/bin/sh\n# header", 0o644)
	for rel, want := range map[string]string{
		"tests/exec.sh": "#!/bin/sh\n# header\n# testmap:covers src/new @2026-10-12/aaaaaaaaaa\necho\n",
		"tests/crlf.sh": "#!/bin/sh\r\n# testmap:covers src/a @2026-01-01/0123456789\r\n# testmap:covers src/new @2026-10-12/aaaaaaaaaa\r\necho\r\n",
		"tests/nonl.sh": "#!/bin/sh\n# header\n# testmap:covers src/new @2026-10-12/aaaaaaaaaa",
	} {
		f, e := planOne(t, root, rel, "", "src/new")
		if _, err := Apply(root, EditSet{Path: rel, Snapshot: f.Snapshot(), Edits: []Edit{e}}); err != nil {
			t.Fatalf("%s: %v", rel, err)
		}
		if got := readFile(t, root, rel); got != want {
			t.Errorf("%s: got %q want %q", rel, got, want)
		}
	}
	if fi, _ := os.Stat(filepath.Join(root, "tests/exec.sh")); fi.Mode().Perm() != 0o755 {
		t.Errorf("mode %v", fi.Mode().Perm())
	}
	if left, _ := filepath.Glob(filepath.Join(root, "tests", ".*")); len(left) != 0 {
		t.Errorf("temporary files left: %v", left)
	}
}

func TestApplyConflicts(t *testing.T) {
	root := t.TempDir()
	src := "#!/bin/sh\n# testmap:covers src/a @2026-01-01/0123456789\n"
	writeFile(t, root, "tests/t.sh", src, 0o644)
	f, e := planOne(t, root, "tests/t.sh", "", "src/a")
	stale := e
	stale.Want = "# testmap:covers src/b"
	var ce *ConflictError
	if _, err := Apply(root, EditSet{Path: "tests/t.sh", Edits: []Edit{stale}}); !errors.As(err, &ce) || ce.Reason != "text" || ce.At != 2 {
		t.Errorf("changed line: %v", err)
	}
	if l, _ := ce.Line(); l != "REWRITE_CONFLICT:tests/t.sh|2" || ce.ExitCode() != 75 {
		t.Errorf("line %q exit %d", l, ce.ExitCode())
	}
	writeFile(t, root, "tests/t.sh", src+"echo\n", 0o644)
	if _, err := Apply(root, EditSet{Path: "tests/t.sh", Snapshot: f.Snapshot(), Edits: []Edit{e}}); !errors.As(err, &ce) || ce.Reason != "snapshot" {
		t.Errorf("snapshot: %v", err)
	}
	// A concurrent write between the temporary file and the rename.
	beforeRename = func(string) { writeFile(t, root, "tests/t.sh", src+"echo changed\n", 0o644) }
	t.Cleanup(func() { beforeRename = func(string) {} })
	if _, err := Apply(root, EditSet{Path: "tests/t.sh", Edits: []Edit{e}}); !errors.As(err, &ce) || ce.Reason != "concurrent" {
		t.Errorf("concurrent: %v", err)
	}
	if got := readFile(t, root, "tests/t.sh"); got != src+"echo changed\n" {
		t.Errorf("concurrent writer lost: %q", got)
	}
	if left, _ := filepath.Glob(filepath.Join(root, "tests", ".*")); len(left) != 0 {
		t.Errorf("temporary files left: %v", left)
	}
}

// D17: a line's text does not pin its block. Renaming an earlier opener
// moves an unchanged covers line to another member; the edit must conflict,
// with or without a snapshot.
func TestApplyStaleOwnership(t *testing.T) {
	root := t.TempDir()
	src := "#!/bin/sh\n# testmap:unit A\n# testmap:covers src/a @2026-01-01/0123456789\n"
	writeFile(t, root, "tests/t.sh", src, 0o644)
	f, restamp := planOne(t, root, "tests/t.sh", "A", "src/a")
	_, insert := planOne(t, root, "tests/t.sh", "A", "src/b")
	renamed := strings.Replace(src, "unit A", "unit B", 1)
	writeFile(t, root, "tests/t.sh", renamed, 0o644)
	for _, e := range []Edit{restamp, insert} {
		var ce *ConflictError
		if _, err := Apply(root, EditSet{Path: "tests/t.sh", Snapshot: f.Snapshot(), Edits: []Edit{e}}); !errors.As(err, &ce) || ce.Reason != "snapshot" {
			t.Errorf("with snapshot: %v", err)
		}
		if _, err := Apply(root, EditSet{Path: "tests/t.sh", Edits: []Edit{e}}); !errors.As(err, &ce) || ce.Reason != "ownership" || ce.At != e.Line {
			t.Errorf("without snapshot: %v", err)
		}
		if got := readFile(t, root, "tests/t.sh"); got != renamed {
			t.Errorf("written: %q", got)
		}
	}
}

// Invariant 6 is the rewriter's own guarantee: whatever the caller asks, a
// line that is not a comment annotation is never written, and nothing is
// ever written into a docstring, a heredoc body, a string or an uncertain
// file.
func TestApplyRefusesNonComments(t *testing.T) {
	root := t.TempDir()
	files := map[string]string{
		"tests/doc.py":   "\"\"\"Doc.\ntestmap:covers src/a.py @2026-01-01/0123456789\n\"\"\"\nimport os\n",
		"tests/here.sh":  "cat <<EOF\n# testmap:covers src/a.sh @2026-01-01/0123456789\nEOF\n",
		"tests/delay.sh": "consume <<END \\\nEND arg\n# testmap:covers src/a.sh @2026-01-01/0123456789\nEND\n",
		"tests/quote.sh": "consume <<END \"a\nEND\nb\"\n# testmap:covers src/a.sh @2026-01-01/0123456789\nEND\n",
		"tests/raw.kt":   "val s = \"\"\"\n// testmap:covers src/A.kt @2026-01-01/0123456789\n\"\"\"\n",
		"tests/raw.go":   "package a\nvar s = `\n// testmap:covers src/a.go @2026-01-01/0123456789\n`\n",
		"tests/cont.sh":  "#!/bin/sh\necho a \\\n  b\n",
		"tests/open.sh":  "cat <<EOF\nnever closed\n",
		"tests/code.sh":  "#!/bin/sh\n# testmap:covers src/a.sh\n",
		"tests/join.sh":  "cat <<EOF\nprefix\\\nEOF\n# testmap:covers src/a.sh @2026-01-01/0123456789\nEOF\n",
		"tests/param.sh": "printf '%s\\n' ${x:-\n# testmap:covers src/a.sh @2026-01-01/0123456789\n}\n",
	}
	for rel, c := range files {
		writeFile(t, root, rel, c, 0o644)
	}
	repl := func(line int, want string) Edit {
		return Edit{Kind: Replace, Line: line, Want: want, New: "# testmap:covers src/a.sh @2026-10-12/aaaaaaaaaa", Source: "src/a.sh"}
	}
	cases := []struct {
		rel  string
		edit Edit
		want error
	}{
		{"tests/doc.py", Edit{Kind: Replace, Line: 2, Want: "testmap:covers src/a.py @2026-01-01/0123456789",
			New: "testmap:covers src/a.py @2026-10-12/aaaaaaaaaa", Source: "src/a.py"}, ErrNotComment},
		{"tests/doc.py", Edit{Kind: InsertAfter, Line: 1, Want: "\"\"\"Doc.", New: "# testmap:covers src/b.py", Source: "src/b.py"}, ErrNotComment},
		{"tests/here.sh", repl(2, "# testmap:covers src/a.sh @2026-01-01/0123456789"), ErrNotComment},
		{"tests/delay.sh", repl(3, "# testmap:covers src/a.sh @2026-01-01/0123456789"), ErrNotComment},
		{"tests/quote.sh", repl(4, "# testmap:covers src/a.sh @2026-01-01/0123456789"), ErrNotComment},
		{"tests/join.sh", repl(4, "# testmap:covers src/a.sh @2026-01-01/0123456789"), ErrNotComment},
		{"tests/param.sh", repl(2, "# testmap:covers src/a.sh @2026-01-01/0123456789"), ErrNotComment},
		{"tests/raw.kt", Edit{Kind: Replace, Line: 2, Want: "// testmap:covers src/A.kt @2026-01-01/0123456789",
			New: "// testmap:covers src/A.kt @2026-10-12/aaaaaaaaaa", Source: "src/A.kt"}, ErrNotComment},
		{"tests/raw.go", Edit{Kind: Replace, Line: 3, Want: "// testmap:covers src/a.go @2026-01-01/0123456789",
			New: "// testmap:covers src/a.go @2026-10-12/aaaaaaaaaa", Source: "src/a.go"}, ErrNotComment},
		{"tests/cont.sh", Edit{Kind: InsertAfter, Line: 2, Want: "echo a \\", New: "# testmap:covers src/a.sh", Source: "src/a.sh"}, ErrNotComment},
		{"tests/open.sh", Edit{Kind: InsertAfter, Line: 0, New: "# testmap:covers src/a.sh", Source: "src/a.sh"}, ErrUncertainContext},
		{"tests/code.sh", Edit{Kind: Replace, Line: 2, Want: "# testmap:covers src/a.sh", New: "echo pwned", Source: "src/a.sh"}, ErrNotComment},
		// Replacing a code line with an annotation would delete code: refused
		// before the edit, though the result alone would look clean.
		{"tests/cont.sh", Edit{Kind: Replace, Line: 3, Want: "  b", New: "# testmap:covers src/a.sh", Source: "src/a.sh"}, ErrNotComment},
		{"tests/code.sh", Edit{Kind: Replace, Line: 1, Want: "#!/bin/sh", New: "# testmap:covers src/a.sh", Source: "src/a.sh"}, ErrNotComment},
	}
	for _, tc := range cases {
		before := readFile(t, root, tc.rel)
		_, err := Apply(root, EditSet{Path: tc.rel, Edits: []Edit{tc.edit}})
		if !errors.Is(err, tc.want) {
			t.Errorf("%s line %d: got %v, want %v", tc.rel, tc.edit.Line, err, tc.want)
		}
		if after := readFile(t, root, tc.rel); after != before {
			t.Errorf("%s written", tc.rel)
		}
	}
}

// D18: no file is read, hashed or written through a symbolic link — a link
// to another directory (outside the root) or one inside the root alike.
func TestNoFollowSymlinks(t *testing.T) {
	root, outside := t.TempDir(), t.TempDir()
	ext := "#!/bin/sh\n# testmap:covers src/a.sh @2026-01-01/0123456789\n"
	writeFile(t, outside, "t.sh", ext, 0o644)
	writeFile(t, outside, "src.sh", "external\n", 0o644)
	writeFile(t, root, "tests/t.sh", ext, 0o644)
	if err := os.Symlink(outside, filepath.Join(root, "link")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("tests", filepath.Join(root, "inlink")); err != nil {
		t.Fatal(err)
	}
	e := Edit{Kind: Replace, Line: 2, Want: "# testmap:covers src/a.sh @2026-01-01/0123456789",
		New: "# testmap:covers src/a.sh @2026-10-12/aaaaaaaaaa", Source: "src/a.sh"}
	for _, rel := range []string{"link/t.sh", "inlink/t.sh"} {
		if _, err := Apply(root, EditSet{Path: rel, Edits: []Edit{e}}); !errors.Is(err, ErrNotAFile) {
			t.Errorf("%s: %v", rel, err)
		}
	}
	r, _ := openRoot(root)
	defer r.Close()
	if _, err := SourceStamp(r, "link/src.sh", "sha1"); !errors.Is(err, ErrNotAFile) {
		t.Errorf("hash through a link: %v", err)
	}
	if got := readFile(t, outside, "t.sh"); got != ext {
		t.Errorf("outside file changed: %q", got)
	}
	if got := readFile(t, root, "tests/t.sh"); got != ext {
		t.Errorf("file changed through an in-root link: %q", got)
	}
}

// D9 end to end, through bash itself: `verify` over a script whose data
// carries annotation-shaped lines — heredoc bodies delayed past a
// continuation or a spanning quote, a body line joined by a backslash-newline,
// a ${…} expansion spanning lines — re-stamps the one real annotation and
// leaves the data the commands read unchanged.
func TestVerifyKeepsBashDataUnchanged(t *testing.T) {
	bash, err := exec.LookPath("bash")
	if err != nil {
		t.Skip("bash not on PATH")
	}
	const look = "# testmap:covers src/a.sh @2026-01-01/0123456789"
	script := "#!/usr/bin/env bash\n" + look + "\n" +
		"consume() { echo \"args:[$*]\"; cat; }\n" +
		"consume <<EOF \\\nEOF arg\n" + look + "\nEOF\n" +
		"consume <<EOF \"a\nEOF\nb\"\n" + look + "\nEOF\n" +
		"consume <<EOF\nprefix\\\nEOF\n" + look + "\nEOF\n" +
		"unset x\nprintf '%s\\n' ${x:-\n" + look + "\n}\n" +
		"cat <<$'EOF'\n$EOF\n" + look + "\nEOF\n" +
		"printf '%s\\n' ${x:-{}\n" +
		"# testmap:covers src/b.sh @2026-01-01/0123456789\n" // a real annotation after the literal brace
	r := repo(t, map[string]string{"src/a.sh": "a\n", "src/b.sh": "b\n", "tests/t.sh": script})
	run := func() string {
		out, err := exec.Command(bash, filepath.Join(r.Dir, "tests/t.sh")).CombinedOutput()
		if err != nil {
			t.Fatalf("%v: %s", err, out)
		}
		return string(out)
	}
	before := run()
	if strings.Count(before, "testmap:covers") != 5 || !strings.Contains(before, "testmap:covers\nsrc/a.sh") || !strings.Contains(before, "$EOF\n") {
		t.Fatalf("the fixture no longer exercises bash's data paths:\n%s", before)
	}
	res, err := Verify(bg, r.Dir, []registry.ID{{Path: "tests/t.sh"}}, Actor{})
	if err != nil || len(res.Stamps) != 2 || res.Stamps[0].State != Restamped || res.Stamps[1].Source != "src/b.sh" {
		t.Fatalf("verify read data as annotations: %+v %v", res, err)
	}
	if after := run(); after != before {
		t.Errorf("the data the commands read changed:\n%s\nvs\n%s", before, after)
	}
	got := strings.Split(readFile(t, r.Dir, "tests/t.sh"), "\n")
	want := strings.Split(script, "\n")
	last := len(want) - 2 // the second real annotation
	for i := range want {
		if i != 1 && i != last && got[i] != want[i] {
			t.Errorf("line %d changed: %q", i+1, got[i])
		}
	}
	if got[1] == want[1] || got[last] == want[last] {
		t.Errorf("a real annotation was not re-stamped: %q / %q", got[1], got[last])
	}
}

// A component swapped for a link between the check and the open is refused,
// never followed: the leaf, a parent directory, and a parent during a write.
func TestNoFollowUnderConcurrentReplacement(t *testing.T) {
	setup := func(t *testing.T) string {
		root := t.TempDir()
		writeFile(t, root, "tests/t.sh", "#!/bin/sh\n# testmap:covers src/a.sh\n", 0o644)
		writeFile(t, root, "tests/sentinel.sh", "#!/bin/sh\n# testmap:covers src/SENTINEL.sh\n", 0o644)
		writeFile(t, root, "decoy/t.sh", "#!/bin/sh\n# testmap:covers src/DECOY.sh\n", 0o644)
		return root
	}
	restore := func() {
		beforeOpenLeaf, beforeEnterDir, beforeRename = func(string) {}, func(string) {}, func(string) {}
	}
	t.Cleanup(restore)
	must := func(err error) {
		if err != nil {
			t.Fatal(err)
		}
	}
	read := func(root string) ([]byte, error) {
		r, _ := openRoot(root)
		defer r.Close()
		data, _, err := readNoFollow(r, "tests/t.sh")
		return data, err
	}
	t.Run("leaf", func(t *testing.T) {
		root := setup(t)
		beforeOpenLeaf = func(string) {
			must(os.Remove(filepath.Join(root, "tests/t.sh")))
			must(os.Symlink("sentinel.sh", filepath.Join(root, "tests/t.sh")))
		}
		defer restore()
		if data, err := read(root); !errors.Is(err, ErrNotAFile) || strings.Contains(string(data), "SENTINEL") {
			t.Errorf("read through a swapped leaf: %q %v", data, err)
		}
	})
	t.Run("parent", func(t *testing.T) {
		root := setup(t)
		beforeEnterDir = func(name string) {
			if name == "tests" {
				must(os.Rename(filepath.Join(root, "tests"), filepath.Join(root, "tests.real")))
				must(os.Symlink("decoy", filepath.Join(root, "tests")))
			}
		}
		defer restore()
		if data, err := read(root); !errors.Is(err, ErrNotAFile) || strings.Contains(string(data), "DECOY") {
			t.Errorf("read through a swapped parent: %q %v", data, err)
		}
	})
	// A FIFO swapped in after the check must not block the read: it is
	// refused within a bounded time (review round 2).
	for _, where := range []string{"leaf", "parent"} {
		t.Run("fifo "+where, func(t *testing.T) {
			root := setup(t)
			fifo := filepath.Join(root, "tests/t.sh")
			swap := func() {
				if where == "parent" {
					fifo = filepath.Join(root, "tests")
					must(os.Rename(fifo, filepath.Join(root, "tests.real")))
				} else {
					must(os.Remove(fifo))
				}
				must(syscall.Mkfifo(fifo, 0o644))
			}
			if where == "leaf" {
				beforeOpenLeaf = func(string) { swap() }
			} else {
				beforeEnterDir = func(name string) {
					if name == "tests" {
						swap()
					}
				}
			}
			defer restore()
			t.Cleanup(func() { // never leave a reader blocked: open a writer
				if w, err := os.OpenFile(fifo, os.O_WRONLY|syscall.O_NONBLOCK, 0); err == nil {
					w.Close()
				}
			})
			done := make(chan error, 1)
			go func() { _, err := read(root); done <- err }()
			select {
			case err := <-done:
				if !errors.Is(err, ErrNotAFile) {
					t.Errorf("got %v, want ErrNotAFile", err)
				}
			case <-time.After(3 * time.Second):
				t.Fatal("the read blocked on a swapped-in FIFO")
			}
		})
	}
	t.Run("parent during write", func(t *testing.T) {
		root := setup(t)
		f, e := planOne(t, root, "tests/t.sh", "", "src/a.sh")
		beforeRename = func(string) {
			must(os.Rename(filepath.Join(root, "tests"), filepath.Join(root, "tests.real")))
			must(os.Symlink("decoy", filepath.Join(root, "tests")))
		}
		defer restore()
		if _, err := Apply(root, EditSet{Path: "tests/t.sh", Snapshot: f.Snapshot(), Edits: []Edit{e}}); err != nil {
			t.Fatal(err)
		}
		if got := readFile(t, root, "decoy/t.sh"); got != "#!/bin/sh\n# testmap:covers src/DECOY.sh\n" {
			t.Errorf("the write followed the swapped parent: %q", got)
		}
		if got := readFile(t, root, "tests.real/t.sh"); !strings.Contains(got, "src/a.sh @2026-10-12/") {
			t.Errorf("the verified directory was not written: %q", got)
		}
	})
}
