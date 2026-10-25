package deps

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"reflect"
	"slices"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// The universe: git-visible files minus exclude:, ignored files, symbolic
// links, and tracked files deleted from the working tree.
func TestUniverse(t *testing.T) {
	r := repo(t, map[string]string{
		".gitignore":    "ignored.sh\n",
		"kept.sh":       "#!/bin/sh\n",
		"ignored.sh":    "#!/bin/sh\n",
		"golden/x.sh":   "#!/bin/sh\n",
		"deleted.sh":    "#!/bin/sh\n",
		"real/inner.sh": "#!/bin/sh\n",
	})
	r.Commit(t, "1", "feature", "init")
	r.Remove(t, "deleted.sh")
	if err := os.Symlink("real", filepath.Join(r.Dir, "link")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("kept.sh", filepath.Join(r.Dir, "alias.sh")); err != nil {
		t.Fatal(err)
	}
	g := scanRepo(t, r, func(o *Options) { o.Config.Exclude = []string{"golden/**"} })
	if got, want := g.Files(), []string{"kept.sh", "real/inner.sh"}; !slices.Equal(got, want) {
		t.Fatalf("files %v, want %v", got, want)
	}
}

// Universe is the whole filtered file set the scan starts from: files no
// scanner reads are in it (and absent from Files); excluded, deleted and
// symlink-reached files are in neither.
func TestUniverseIncludesUnscannedFiles(t *testing.T) {
	r := repo(t, map[string]string{
		"kept.sh":        "#!/bin/sh\n",
		"conf/app.json":  "{}\n",
		"README.md":      "# r\n",
		"src/x.rs":       "fn main() {}\n",
		"golden/x.json":  "{}\n",
		"deleted.json":   "{}\n",
		"real/inner.txt": "t\n",
	})
	r.Commit(t, "1", "feature", "init")
	r.Remove(t, "deleted.json")
	if err := os.Symlink("real", filepath.Join(r.Dir, "link")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("README.md", filepath.Join(r.Dir, "alias.md")); err != nil {
		t.Fatal(err)
	}
	g := scanRepo(t, r, func(o *Options) { o.Config.Exclude = []string{"golden/**"} })
	if got, want := g.Universe(), []string{"README.md", "conf/app.json", "kept.sh", "real/inner.txt", "src/x.rs"}; !slices.Equal(got, want) {
		t.Fatalf("universe %v, want %v", got, want)
	}
	if got, want := g.Files(), []string{"kept.sh"}; !slices.Equal(got, want) {
		t.Fatalf("files %v, want %v", got, want)
	}
	u, err := Universe(bg, r.Dir, registry.Config{Exclude: []string{"golden/**"}})
	if err != nil || !slices.Equal(u, g.Universe()) {
		t.Fatalf("Universe() = %v %v, want the scan's %v", u, err, g.Universe())
	}
}

func TestClosureAndReverse(t *testing.T) {
	r := repo(t, map[string]string{
		"t.sh":     "#!/bin/sh\n. ./lib/a.sh\n",
		"lib/a.sh": "#!/bin/sh\n. ./lib/b.sh\n",
		"lib/b.sh": "#!/bin/sh\n. ./lib/c.sh\n",
		"lib/c.sh": "#!/bin/sh\n",
	})
	g := scanRepo(t, r)
	var got []string
	for _, x := range g.Closure("t.sh", 0) {
		got = append(got, x.Path+"@"+string(rune('0'+x.Distance)))
	}
	if want := []string{"lib/a.sh@1", "lib/b.sh@2", "lib/c.sh@3"}; !slices.Equal(got, want) {
		t.Fatalf("closure %v (unbounded: chains run deeper than two hops)", got)
	}
	if len(g.Closure("t.sh", 2)) != 2 {
		t.Fatal("max distance")
	}
	if !slices.Equal(g.Reverse("lib/b.sh"), []string{"lib/a.sh"}) {
		t.Fatalf("reverse %v", g.Reverse("lib/b.sh"))
	}
	if s := g.Static("t.sh"); len(s) != 1 || s[0].Origin != Invocation || s[0].Line != 2 {
		t.Fatalf("static %+v", s)
	}
}

// The blob cache: a second scan extracts nothing; the same blob at two
// paths resolves against each path; an edit misses.
func TestCacheHitByBlob(t *testing.T) {
	same := "#!/bin/bash\nsource \"$(dirname \"$0\")/lib.sh\"\n"
	r := repo(t, map[string]string{
		"a/t.sh":   same,
		"b/t.sh":   same,
		"a/lib.sh": "#!/bin/sh\n",
		"b/lib.sh": "#!/bin/sh\n",
	})
	var n atomic.Int32
	misses := func() int { return int(n.Swap(0)) }
	old := scanRawHook
	scanRawHook = func(string) { n.Add(1) }
	t.Cleanup(func() { scanRawHook = old })
	cache := t.TempDir()
	first := scanCached(t, r, cache)
	if m := misses(); m != 2 { // one per distinct blob: the scripts share one, the libs another
		t.Fatalf("cold misses %d, want 2", m)
	}
	second := scanCached(t, r, cache)
	if m := misses(); m != 0 {
		t.Fatalf("warm scan extracted %d files", m)
	}
	if !reflect.DeepEqual(first.files, second.files) {
		t.Fatal("warm and cold scans differ")
	}
	requireEdge(t, second, "a/t.sh", "a/lib.sh", Invocation, "")
	requireEdge(t, second, "b/t.sh", "b/lib.sh", Invocation, "")
	r.Write(t, "a/t.sh", same+"# edited\n")
	scanCached(t, r, cache)
	if m := misses(); m != 1 {
		t.Fatalf("an edit: %d misses, want 1", m)
	}
}

func TestCacheEntriesAreValidated(t *testing.T) {
	dir := t.TempDir()
	c := &cache{dir: dir}
	raw := rawFile{Symbols: []Symbol{{Name: "x", Kind: "func", Line: 1}}}
	c.put("abc", kindBash, raw)
	if got, ok := c.get("abc", kindBash); !ok || !reflect.DeepEqual(got, raw) {
		t.Fatalf("round trip: %+v %v", got, ok)
	}
	if _, ok := c.get("abc", kindPython); ok {
		t.Fatal("another kind hit")
	}
	if err := os.WriteFile(filepath.Join(dir, "abc.json"), []byte(`{"v":0,"kind":"bash","raw":{}}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, ok := c.get("abc", kindBash); ok {
		t.Fatal("an older schema hit")
	}
	if err := os.WriteFile(filepath.Join(dir, "abc.json"), []byte(`{not json`), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, ok := c.get("abc", kindBash); ok {
		t.Fatal("a corrupt entry hit")
	}
	var nilCache *cache
	nilCache.put("abc", kindBash, raw)
	if _, ok := nilCache.get("abc", kindBash); ok {
		t.Fatal("uncached hit")
	}
}

// An unwritable cache only costs speed: the scan succeeds and says so.
func TestCacheUnwritable(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root writes anywhere")
	}
	r := repo(t, map[string]string{"t.sh": "#!/bin/sh\n"})
	dir := filepath.Join(t.TempDir(), "ro")
	if err := os.MkdirAll(dir, 0o555); err != nil {
		t.Fatal(err)
	}
	g := scanCached(t, r, dir)
	if !slices.ContainsFunc(g.Problems(), func(p Problem) bool { return strings.HasPrefix(p.Reason, "cache-unwritable") }) {
		t.Fatalf("problems %v", g.Problems())
	}
	if _, ok := g.Facts("t.sh"); !ok {
		t.Fatal("scan lost the file")
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 0 {
		t.Fatal("wrote into a read-only dir")
	}
}

func TestUncachedWritesNothing(t *testing.T) {
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	r := repo(t, map[string]string{"t.sh": "#!/bin/sh\n"})
	scanRepo(t, r)
	if entries, _ := os.ReadDir(os.Getenv("XDG_CACHE_HOME")); len(entries) != 0 {
		t.Fatalf("an uncached scan wrote %v", entries)
	}
	// The default location is the per-user testmap cache.
	if _, err := Scan(bg, r.Dir, Options{Config: registry.Defaults()}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(os.Getenv("XDG_CACHE_HOME"), "aitasks", "testmap", "deps")); err != nil {
		t.Fatalf("default cache dir: %v", err)
	}
}

// The cached bash facts depend on annot.Classify (M2.2's lexer). This
// fingerprint pins Classify's output over a corpus of the constructs the
// scanner relies on; when M2.2 changes its lexers this fails, and the fix is
// to bump schemaVersion (so stale cache entries are rescanned) and then
// update the fingerprint.
func TestClassifyFingerprint(t *testing.T) {
	corpus := strings.Join([]string{
		"#!/bin/bash",
		"# comment ./x.sh",
		"cat <<EOF",
		"./in/heredoc.sh",
		"EOF",
		`x="multi`,
		`line ./y.sh"`,
		"echo $(( 1 << 2 )) ${a#b} # tail",
		"run 'single",
		"quoted' ./z.sh",
		"cat <<-'Q' | sed 's/a/b/'",
		"\tbody",
		"\tQ",
		"",
	}, "\n")
	c := annot.Classify(annot.Bash, []byte(corpus))
	var b strings.Builder
	for _, cl := range c.Class {
		b.WriteByte('0' + byte(cl))
	}
	if c.Uncertain != nil {
		b.WriteString("U")
	}
	h := sha256.Sum256([]byte(b.String()))
	got := hex.EncodeToString(h[:8])
	const want = "8cbc81cc75f27630"
	if got != want {
		t.Fatalf("annot.Classify fingerprint %s (classes %s), want %s: M2.2's bash lexer changed — bump schemaVersion in cache.go, then update the fingerprint", got, b.String(), want)
	}
}
