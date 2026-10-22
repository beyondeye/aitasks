package cost

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

var bg = context.Background()

// A test-only reporting contract (G7): the suite fixtures' child rows load
// only through a registered one.
func init() { runner.RegisterReportingContract("test-children") }

// The eligibility fixture: tests/test_a.sh sources tests/lib/helper.sh (which
// declares `testmap:reads tests/data/*.txt`), covers src/a.sh and src/[id].ts
// by annotation and src/b.sh by a hand-file edge, and a scanner plugin
// declares the reads glob fixtures/*.json on the test itself. Nothing is ever
// `scan --apply`d, so the annotation side of the covers union is the only
// source of the annotated edges.
const (
	testA = `#!/usr/bin/env bash
# testmap:covers src/a.sh
# testmap:covers src/[id].ts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/helper.sh"
`
	helperSh = "#!/usr/bin/env bash\n# testmap:reads tests/data/*.txt\nhelper() { :; }\n"
	// shellRunner lists tests/test_a.sh and reports it passing; $COST_MODE
	// selects a misbehaviour.
	shellRunner = `#!/usr/bin/env bash
case "$1" in
describe) printf 'unit: file\ntimeouts: batch\n';;
list) printf 'tests/test_a.sh\tfile\ta\n';;
run) R=$(sed -n 's/^  "results": "\(.*\)",$/\1/p' "$3")
  case "${COST_MODE:-}" in
  ghost) printf '{"id":"tests/test_a.sh","status":"pass","duration_ms":3}\n{"id":"tests/ghost.sh","status":"pass","duration_ms":1}\n' >> "$R";;
  commit) git -c user.name=t -c user.email=t@example.com commit -q --allow-empty -m moved
    printf '{"id":"tests/test_a.sh","status":"pass","duration_ms":3}\n' >> "$R";;
  *) printf '{"id":"tests/test_a.sh","status":"pass","duration_ms":3}\n' >> "$R";;
  esac;;
*) exit 64;;
esac
`
	shellRunners = "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 30\n    batch_timeout_s: 30\n"
)

// eligRepo writes the fixture under prefix ("" or "sub/") and commits it.
func eligRepo(t *testing.T, prefix string, extra map[string]string) *fixture.Repo {
	t.Helper()
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	r := fixture.New(t)
	files := map[string]string{
		"aitestmap/config.yaml":         "contract: 1\nhost_class: ci\nexclude: ['vendor/**']\n",
		".gitignore":                    ".aitask-testmap/\n",
		"src/a.sh":                      "echo a\n",
		"src/b.sh":                      "echo b\n",
		"src/[id].ts":                   "x\n",
		"tests/test_a.sh":               testA,
		"tests/lib/helper.sh":           helperSh,
		"tests/data/x.txt":              "1\n",
		"fixtures/y.json":               "{}\n",
		"docs/readme.md":                "r\n",
		"vendor/lib.sh":                 "#!/bin/sh\n",
		"aitestmap/registry/hand.yaml":  "contract: 1\nowns: ['src/b.sh']\nedges:\n  - {test: tests/test_a.sh, covers: src/b.sh}\n",
		"aitestmap/scanners/fx":         "#!/bin/sh\ncat >/dev/null\necho '{\"file\":\"tests/test_a.sh\",\"reads\":[\"fixtures/*.json\"]}'\n",
		runner.RunnersPath:              shellRunners,
		runner.RunnersDir + "/shell.sh": shellRunner,
	}
	for k, v := range extra {
		files[k] = v
	}
	for p, c := range files {
		r.Write(t, prefix+p, c)
	}
	for p := range files {
		if strings.HasPrefix(p, "aitestmap/scanners/") || strings.HasPrefix(p, runner.RunnersDir+"/") || p == "tools/run.sh" {
			if err := os.Chmod(filepath.Join(r.Dir, filepath.FromSlash(prefix+p)), 0o755); err != nil {
				t.Fatal(err)
			}
		}
	}
	r.Commit(t, "1", "test", "fixture")
	return r
}

// judged runs every unit (all) or tests/test_a.sh through the real runner
// and returns the ledger result rows the hook would append.
func judged(t *testing.T, root string, all bool) []ResultRow {
	t.Helper()
	return judgedIDs(t, root, all, idsIf(!all))
}

// judgedIDs is judged over explicit unit ids.
func judgedIDs(t *testing.T, root string, all bool, ids []string) []ResultRow {
	t.Helper()
	runSeq++
	rep, err := runner.Run(bg, root, runner.Options{All: all, IDs: ids, RunID: fmt.Sprintf("test-%d", runSeq)})
	if err != nil {
		t.Fatal(err)
	}
	batch, err := Rows(bg, rep)
	if err != nil {
		t.Fatal(err)
	}
	var out []ResultRow
	for _, line := range bytes.Split(bytes.TrimSpace(batch), []byte{'\n'}) {
		if bytes.Contains(line, []byte(`"row":"result"`)) {
			var r ResultRow
			if err := json.Unmarshal(line, &r); err != nil {
				t.Fatal(err)
			}
			out = append(out, r)
		}
	}
	return out
}

var runSeq int

func idsIf(on bool) []string {
	if on {
		return []string{"tests/test_a.sh"}
	}
	return nil
}

func dirty(t *testing.T, r *fixture.Repo, paths ...string) {
	t.Helper()
	for _, p := range paths {
		old, _ := os.ReadFile(filepath.Join(r.Dir, filepath.FromSlash(p)))
		r.Write(t, p, string(old)+"# dirty\n")
	}
}

// reasonOf is the single result's verdict for tests/test_a.sh.
func reasonOf(t *testing.T, rows []ResultRow, id string) ResultRow {
	t.Helper()
	for _, r := range rows {
		if r.ID == id {
			return r
		}
	}
	t.Fatalf("no row for %s in %+v", id, rows)
	return ResultRow{}
}

// Every rejection names its own reason; the positive control (unrelated
// dirty files) stays eligible.
func TestEligibilityRejections(t *testing.T) {
	for _, c := range []struct {
		name, dirty, want string
	}{
		{"clean-tree", "", ""},
		{"unrelated", "docs/readme.md", ""},
		{"weakened-test", "tests/test_a.sh", "test-file"},
		{"dirty-helper", "tests/lib/helper.sh", "closure:tests/lib/helper.sh"},
		{"covers-annotation", "src/a.sh", "covers:src/a.sh"},
		{"covers-literal-brackets", "src/[id].ts", "covers:src/[id].ts"},
		{"covers-hand-edge", "src/b.sh", "covers:src/b.sh"},
		{"helper-reads-only", "tests/data/x.txt", "reads:tests/data/*.txt"},
		{"plugin-reads-on-test", "fixtures/y.json", "plugin-reads:fixtures/*.json"},
		{"runner-script", runner.RunnersDir + "/shell.sh", "runner-config:" + runner.RunnersDir + "/shell.sh"},
		{"runners-table", runner.RunnersPath, "runner-config:" + runner.RunnersPath},
	} {
		t.Run(c.name, func(t *testing.T) {
			r := eligRepo(t, "", nil)
			if c.dirty != "" {
				dirty(t, r, c.dirty, "docs/readme.md")
			}
			row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh")
			eligible := c.want == ""
			if row.Clean != eligible || row.Anchor != eligible || row.AnchorReason != c.want {
				t.Fatalf("clean %v anchor %v reason %q, want reason %q", row.Clean, row.Anchor, row.AnchorReason, c.want)
			}
		})
	}
}

func TestEligibilityCauseAndHead(t *testing.T) {
	r := eligRepo(t, "", nil)
	t.Setenv("COST_MODE", "ghost")
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || !strings.HasPrefix(row.AnchorReason, "cause:") {
		t.Fatalf("cause: %+v", row)
	}
	t.Setenv("COST_MODE", "commit")
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || row.AnchorReason != "head-moved" {
		t.Fatalf("head moved: %+v", row)
	}
}

// A test that sources an excluded vendor script: the eligibility scan lifts
// `exclude:`, so the script is an ordinary closure file and its edit is named.
func TestEligibilityExcludedSourceIsFollowed(t *testing.T) {
	r := eligRepo(t, "", map[string]string{"tests/test_a.sh": testA + "source \"$SCRIPT_DIR/../vendor/lib.sh\"\n"})
	dirty(t, r, "vendor/lib.sh")
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || row.AnchorReason != "closure:vendor/lib.sh" {
		t.Fatalf("%+v", row)
	}
}

// A project script runner outside aitestmap/runners/ is judged with its own
// closure: its dirty sourced library blocks the anchor.
func TestEligibilityScriptRunnerClosure(t *testing.T) {
	r := eligRepo(t, "", map[string]string{
		runner.RunnersPath: "contract: 1\nrunners:\n  - name: tool\n    script: tools/run.sh\n    bind: ['tests/*.sh']\n    timeout_s: 30\n    batch_timeout_s: 30\n",
		"tools/run.sh":     "#!/usr/bin/env bash\nSCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nsource \"$SCRIPT_DIR/lib.sh\"\n" + strings.SplitN(shellRunner, "\n", 2)[1],
		"tools/lib.sh":     "#!/usr/bin/env bash\n:\n",
	})
	if err := os.Remove(filepath.Join(r.Dir, runner.RunnersDir, "shell.sh")); err != nil {
		t.Fatal(err)
	}
	r.Commit(t, "2", "test", "script runner")
	dirty(t, r, "docs/readme.md")
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); !row.Anchor {
		t.Fatalf("control: %+v", row)
	}
	dirty(t, r, "tools/lib.sh")
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || row.AnchorReason != "runner-config:tools/lib.sh" {
		t.Fatalf("%+v", row)
	}
}

// Suite units and full: true child rows are opaque: eligible only on an
// unmodified tree.
func TestEligibilitySuiteAndChildRows(t *testing.T) {
	full := `#!/usr/bin/env bash
case "$1" in
describe) printf 'unit: suite\nfull: true\nchildren: test-children\ntimeouts: batch\n';;
list) printf 'suite.cfg\tsuite\tall\n';;
run) R=$(sed -n 's/^  "results": "\(.*\)",$/\1/p' "$3")
  printf '{"id":"suite.cfg","status":"pass","duration_ms":9}\n{"id":"tests/test_a.sh","status":"pass","duration_ms":3,"parent":"suite.cfg"}\n' >> "$R";;
*) exit 64;;
esac
`
	r := eligRepo(t, "", map[string]string{
		"suite.cfg":                    "x\n",
		runner.RunnersDir + "/full.sh": full,
		runner.RunnersPath:             shellRunners + "    subsumed_by: full\n  - name: full\n    bind: ['suite.cfg']\n    timeout_s: 30\n    batch_timeout_s: 30\n",
	})
	rows := judged(t, r.Dir, true)
	if s, c := reasonOf(t, rows, "suite.cfg"), reasonOf(t, rows, "tests/test_a.sh"); !s.Anchor || !c.Anchor || c.Parent != "suite.cfg" {
		t.Fatalf("clean tree: %+v %+v", s, c)
	}
	dirty(t, r, "docs/readme.md")
	rows = judged(t, r.Dir, true)
	if s := reasonOf(t, rows, "suite.cfg"); s.Anchor || s.AnchorReason != "opaque:suite" {
		t.Fatalf("suite: %+v", s)
	}
	if c := reasonOf(t, rows, "tests/test_a.sh"); c.Anchor || c.AnchorReason != "opaque:child" {
		t.Fatalf("child: %+v", c)
	}
}

// G1: an aggregate result proves one command's exit, never which tests ran,
// so it never anchors — on a clean tree as on a dirty one — while the same
// runner declared unit keeps every existing decision.
func TestEligibilityAggregateNeverAnchors(t *testing.T) {
	r := eligRepo(t, "", map[string]string{runner.RunnersPath: shellRunners + "    accounting: aggregate\n"})
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || row.AnchorReason != "opaque:aggregate" || row.Accounting != runner.AccountingAggregate {
		t.Fatalf("clean tree: %+v", row)
	}
	dirty(t, r, "docs/readme.md")
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || row.AnchorReason != "opaque:aggregate" {
		t.Fatalf("dirty tree: %+v", row)
	}
	u := eligRepo(t, "", nil)
	if row := reasonOf(t, judged(t, u.Dir, false), "tests/test_a.sh"); !row.Anchor || row.AnchorReason != "" {
		t.Fatalf("unit accounting, clean tree: %+v", row)
	}
}

// Ledger result rows carry the result's runner's accounting and discovery
// classes (a child row: the subsumed runner's) and the engine-derived reason.
func TestLedgerRecordsAccountingDiscovery(t *testing.T) {
	full := `#!/usr/bin/env bash
case "$1" in
describe) printf 'unit: suite\nfull: true\nchildren: test-children\naccounting: aggregate\ndiscovery: inventory\ntimeouts: batch\n';;
list) printf 'suite.cfg\tsuite\tall\n';;
run) R=$(sed -n 's/^  "results": "\(.*\)",$/\1/p' "$3")
  printf '{"id":"suite.cfg","status":"pass","duration_ms":9}\n{"id":"tests/test_a.sh","status":"pass","duration_ms":3,"parent":"suite.cfg"}\n' >> "$R";;
*) exit 64;;
esac
`
	r := eligRepo(t, "", map[string]string{
		"suite.cfg":                    "x\n",
		runner.RunnersDir + "/full.sh": full,
		runner.RunnersPath:             shellRunners + "    discovery: native\n    subsumed_by: full\n  - name: full\n    bind: ['suite.cfg']\n    timeout_s: 30\n    batch_timeout_s: 30\n",
	})
	rows := judged(t, r.Dir, true)
	if s := reasonOf(t, rows, "suite.cfg"); s.Accounting != runner.AccountingAggregate || s.Discovery != runner.DiscoveryInventory || s.AnchorReason != "opaque:aggregate" {
		t.Fatalf("suite: %+v", s)
	}
	if c := reasonOf(t, rows, "tests/test_a.sh"); c.Parent != "suite.cfg" || c.Accounting != runner.AccountingUnit || c.Discovery != runner.DiscoveryNative || !c.Anchor {
		t.Fatalf("child: %+v", c)
	}
}

// The tree edited between the run and the hook: the closure read at hook
// time may not be the one the run saw.
func TestEligibilityTreeChanged(t *testing.T) {
	r := eligRepo(t, "", nil)
	dirty(t, r, "docs/readme.md")
	testBeforeInputs = func() { r.Write(t, "docs/late.md", "late\n") }
	t.Cleanup(func() { testBeforeInputs = nil })
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || row.AnchorReason != "tree-changed" {
		t.Fatalf("%+v", row)
	}
}

// aitestmap/ below the git top level: the modified set is root-relative, so
// in-root dirt is judged like a top-level one. Unrelated dirt anchors; the
// test file and a closure file, dirtied by their top-level-relative paths,
// are each caught under their root-relative ids; any dirt outside the root
// fails closed.
func TestEligibilitySubdirectoryRoot(t *testing.T) {
	for _, c := range []struct {
		name, dirty, want string
	}{
		{"unrelated", "", ""},
		{"weakened-test", "sub/tests/test_a.sh", "test-file"},
		{"dirty-helper", "sub/tests/lib/helper.sh", "closure:tests/lib/helper.sh"},
		{"outside-root", "outside.txt", "outside-root:../outside.txt"},
	} {
		t.Run(c.name, func(t *testing.T) {
			r := eligRepo(t, "sub/", nil)
			dirty(t, r, "sub/docs/readme.md")
			if c.dirty != "" {
				dirty(t, r, c.dirty)
			}
			row := reasonOf(t, judged(t, filepath.Join(r.Dir, "sub"), false), "tests/test_a.sh")
			eligible := c.want == ""
			if row.Clean != eligible || row.Anchor != eligible || row.AnchorReason != c.want {
				t.Fatalf("clean %v anchor %v reason %q, want reason %q", row.Clean, row.Anchor, row.AnchorReason, c.want)
			}
		})
	}
}

// A reference that leaves a subdirectory root resolves to an unchanged
// in-root namesake (tests/../outside.sh), so the closure is clean while the
// file the test really sources (the top-level outside.sh) is modified. The
// outside-root rule, not the closure, is what refuses the anchor.
func TestEligibilityOutsideRootNamesake(t *testing.T) {
	r := eligRepo(t, "sub/", map[string]string{
		"tests/test_a.sh": testA + "source ../outside.sh\n",
		"outside.sh":      "#!/bin/sh\n",
	})
	r.Write(t, "outside.sh", "#!/bin/sh\n")
	r.Commit(t, "2", "test", "outside input")
	dirty(t, r, "outside.sh")
	if row := reasonOf(t, judged(t, filepath.Join(r.Dir, "sub"), false), "tests/test_a.sh"); row.Anchor || row.AnchorReason != "outside-root:../outside.sh" {
		t.Fatalf("%+v", row)
	}
}

// An unreadable input fails closed into the rows; the run still writes them.
func TestEligibilityInputErrorFailsClosed(t *testing.T) {
	r := eligRepo(t, "", map[string]string{"aitestmap/scanners/fx": "#!/bin/sh\ncat >/dev/null\necho 'not json'\n"})
	dirty(t, r, "docs/readme.md")
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || !strings.HasPrefix(row.AnchorReason, "eligibility-error:deps:") {
		t.Fatalf("%+v", row)
	}
}

// No path of the modified set reaches a committed table: only ids.
func TestNoPathListInTable(t *testing.T) {
	r := eligRepo(t, "", nil)
	dirty(t, r, "docs/readme.md", "tests/data/x.txt", "src/a.sh")
	rep, err := runner.Run(bg, r.Dir, runner.Options{IDs: []string{"tests/test_a.sh"}, RunID: "test-np"})
	if err != nil {
		t.Fatal(err)
	}
	if err := Hook(bg, rep); err != nil {
		t.Fatal(err)
	}
	if _, err := Update(r.Dir); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(r.Dir, TablePath("ci")))
	if err != nil {
		t.Fatal(err)
	}
	for _, p := range []string{"docs/readme.md", "tests/data", "src/a.sh"} {
		if strings.Contains(string(data), p) {
			t.Fatalf("table carries %s:\n%s", p, data)
		}
	}
	if !strings.Contains(string(data), "id: tests/test_a.sh") {
		t.Fatalf("table:\n%s", data)
	}
}

// A review- run writes nothing; any other run writes its batch.
func TestHookReviewWritesNothing(t *testing.T) {
	r := eligRepo(t, "", nil)
	rep, err := runner.Run(bg, r.Dir, runner.Options{All: true, RunID: "review-1"})
	if err != nil {
		t.Fatal(err)
	}
	if err := Hook(bg, rep); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(r.Dir, LedgerPath)); !os.IsNotExist(err) {
		t.Fatalf("review run wrote the ledger: %v", err)
	}
}
