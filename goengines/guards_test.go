// Module-wide guards: the dependency allowlist and an Invariant 5 tripwire.
package goengines_test

import (
	"go/scanner"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"testing"
)

// allowedDeps is the proposal's complete dependency list (component Go
// engine and CLI). It is an allowlist: a module is added when its first
// importer lands, never ahead of it.
var allowedDeps = []string{
	"gopkg.in/yaml.v3",
	"github.com/bmatcuk/doublestar/v4",
	"golang.org/x/sync",
}

func TestDependencyAllowlist(t *testing.T) {
	data, err := os.ReadFile("go.mod")
	if err != nil {
		t.Fatal(err)
	}
	inBlock := false
	for _, line := range strings.Split(string(data), "\n") {
		f := strings.Fields(strings.SplitN(line, "//", 2)[0])
		switch {
		case len(f) >= 2 && f[0] == "require" && f[1] == "(":
			inBlock = true
			continue
		case inBlock && len(f) == 1 && f[0] == ")":
			inBlock = false
			continue
		case len(f) >= 3 && f[0] == "require":
			f = f[1:]
		case !inBlock || len(f) < 2:
			continue
		}
		if !slices.Contains(allowedDeps, f[0]) {
			t.Errorf("go.mod requires %s, which is not on the proposal's allowlist %v", f[0], allowedDeps)
		}
	}
}

// Invariant 5: the engine never writes aitasks/, aiplans/, .aitask-data/, a
// gate ledger, project_config.yaml, gates.yaml, a profile or CLAUDE.md,
// never invokes an aitask_*.sh script and never commits; Invariant 4: it
// never launches a code agent. This is a lexical tripwire over string
// literals — it catches the obvious regression, it does not prove the
// invariant, which review enforces.
var (
	forbiddenPath   = regexp.MustCompile(`(^|[^A-Za-z0-9_.-])(aitasks|aiplans)(/|$)|\.aitask-data|CLAUDE\.md|gates\.yaml|project_config\.yaml|aitask_[A-Za-z0-9_]*\.sh`)
	gitWriteVerbs   = []string{"commit", "push", "add", "rm", "mv", "reset", "checkout", "switch", "merge", "rebase", "cherry-pick", "revert", "tag", "stash", "update-ref", "update-index", "notes"}
	agentExecutable = []string{"claude", "codex", "opencode", "gemini", "agy"}
)

// exemptMarker exempts the literals on its own line, and only those — never a
// whole file. The reason is mandatory: `// invariant5-ok: <why>`.
var exemptMarker = regexp.MustCompile(`//\s*invariant5-ok:\s*\S`)

// violations returns the forbidden string literals in one Go source file.
// Git verbs and agent names only count in files that import os/exec (the
// only way to run them); the module's own import path and literals on a line
// carrying the exemption marker are exempt.
func violations(src []byte) []string {
	var lits []string
	execs := false
	lines := strings.Split(string(src), "\n")
	fset := token.NewFileSet()
	file := fset.AddFile("", fset.Base(), len(src))
	var s scanner.Scanner
	s.Init(file, src, nil, scanner.ScanComments)
	for {
		pos, tok, lit := s.Scan()
		if tok == token.EOF {
			break
		}
		if tok != token.STRING {
			continue
		}
		v, err := strconv.Unquote(lit)
		if err != nil {
			continue
		}
		if v == "os/exec" || strings.HasSuffix(v, "/internal/gitx") {
			execs = true
		}
		if exemptMarker.MatchString(lines[file.Line(pos)-1]) {
			continue
		}
		lits = append(lits, v)
	}
	var bad []string
	for _, v := range lits {
		if strings.HasPrefix(v, "github.com/beyondeye/aitasks/") {
			continue
		}
		if forbiddenPath.MatchString(v) {
			bad = append(bad, v)
			continue
		}
		if execs && (slices.Contains(gitWriteVerbs, v) || slices.Contains(agentExecutable, v)) {
			bad = append(bad, v)
		}
	}
	return bad
}

func TestInvariant5Tripwire(t *testing.T) {
	err := filepath.WalkDir(".", func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		// The fixture harness writes throwaway repositories in t.TempDir();
		// it is test infrastructure, not engine code.
		if d.IsDir() && filepath.ToSlash(path) == "internal/testmap/fixture" {
			return filepath.SkipDir
		}
		if d.IsDir() || !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
			return nil
		}
		src, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		for _, v := range violations(src) {
			t.Errorf("%s: forbidden literal %q (Invariants 4-5)", path, v)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}

// Negative control: a guard that flags nothing proves nothing. Every
// forbidden form must be caught, and the benign look-alikes must not be.
func TestInvariant5TripwireCatches(t *testing.T) {
	bad := `package x
import "os/exec"
var _ = exec.Command("git", "commit", "-m", "x")
var _ = exec.Command("git", "push")
var _ = exec.Command("claude", "-p")
var _ = "aitasks/t1.md"
var _ = "./aiplans/p1.md"
var _ = ".aitask-data/x"
var _ = "CLAUDE.md"
var _ = "aitasks/metadata/project_config.yaml"
var _ = "gates.yaml"
var _ = "./.aitask-scripts/aitask_create.sh"
var _ = "aitasks" // invariant5-ok:
var _ = "aitasks" // an unmarked comment exempts nothing
`
	got := violations([]byte(bad))
	want := []string{"commit", "push", "claude", "aitasks/t1.md", "./aiplans/p1.md", ".aitask-data/x",
		"CLAUDE.md", "aitasks/metadata/project_config.yaml", "gates.yaml", "./.aitask-scripts/aitask_create.sh",
		"aitasks", "aitasks"}
	if !slices.Equal(got, want) {
		t.Fatalf("flagged %q\nwant    %q", got, want)
	}
	benign := "package x\n" +
		"import \"github.com/beyondeye/aitasks/goengines/internal/lineproto\"\n" +
		"// the engine never commits to aitasks/ and never runs claude\n" +
		"type v struct{ Commit string `json:\"commit\"` }\n" +
		"var _ = \"commit\" // no os/exec import: a plain word\n" +
		"var _ = \"myaitasks/x\"\n" +
		"var _ = \"aitasks\" // invariant5-ok: the per-user cache namespace\n"
	if got := violations([]byte(benign)); len(got) != 0 {
		t.Fatalf("benign source flagged: %q", got)
	}
}
