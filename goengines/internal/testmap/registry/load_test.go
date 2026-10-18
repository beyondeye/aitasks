package registry

import (
	"errors"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap"
)

// The core merge golden: two hand files and _scanned.yaml contribute their
// rows to the same tables, in file-name order; a duplicate edge is a union.
func TestLoadMergeGolden(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{
		ConfigPath: "contract: 1\n",
		RegistryDir + "/gates.yaml": `contract: 1
owns: [".aitask-scripts/aitask_gate*.sh", "aitasks/metadata/gates.yaml"]
edges:
  - {test: tests/test_gate.sh, covers: .aitask-scripts/aitask_gate.sh}
  - {test: tests/test_gate.sh#Run, covers: [.aitask-scripts/aitask_gate_run.sh, .aitask-scripts/aitask_gate.sh], extra_future_field: ignored}
rules:
  - name: gates-area
    when: [".aitask-scripts/aitask_gate*.sh"]
    select: ["tests/test_gate_*.sh", "tests/x.kt#*"]
    distance: 2
waivers:
  - {path: .aitask-scripts/aitask_gate_log.sh, reason: display-only, until: 2027-03-01}
`,
		RegistryDir + "/board.yaml": `contract: 1
owns: [".aitask-scripts/board/**"]
edges:
  - {test: tests/test_gate.sh, covers: .aitask-scripts/aitask_gate.sh}
rules:
  - {name: board-escalate, when: [".aitask-scripts/board/*.py"], escalate: true}
`,
		ScannedPath: `contract: 1
units:
  - test: tests/test_a.sh
    covers:
      - {source: src/a.sh, line: 3, stamped_at: "2026-10-01", stamped_blob: "0123456789"}
  - test: app/F.kt#Welcome
    line: 12
    variants: [ltr, rtl]
`,
		RegistryDir + "/README.txt": "not yaml, ignored\n",
	})
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	board, gates := RegistryDir+"/board.yaml", RegistryDir+"/gates.yaml"
	wantEdges := []Edge{
		{Test: MustParseID("tests/test_a.sh"), Source: "src/a.sh", Line: 3, StampedAt: "2026-10-01", StampedBlob: "0123456789", From: FromAnnotation, File: ScannedPath},
		{Test: MustParseID("tests/test_gate.sh"), Source: ".aitask-scripts/aitask_gate.sh", From: FromDeclared, File: board},
		{Test: MustParseID("tests/test_gate.sh"), Source: ".aitask-scripts/aitask_gate.sh", From: FromDeclared, File: gates},
		{Test: MustParseID("tests/test_gate.sh#Run"), Source: ".aitask-scripts/aitask_gate_run.sh", From: FromDeclared, File: gates},
		{Test: MustParseID("tests/test_gate.sh#Run"), Source: ".aitask-scripts/aitask_gate.sh", From: FromDeclared, File: gates},
	}
	if !reflect.DeepEqual(reg.Edges, wantEdges) {
		t.Errorf("edges\n got %+v\nwant %+v", reg.Edges, wantEdges)
	}
	wantRules := []Rule{
		{Name: "board-escalate", When: []string{".aitask-scripts/board/*.py"}, Escalate: true, Distance: 1, File: board},
		{Name: "gates-area", When: []string{".aitask-scripts/aitask_gate*.sh"}, Select: []string{"tests/test_gate_*.sh", "tests/x.kt#*"}, Distance: 2, File: gates},
	}
	if !reflect.DeepEqual(reg.Rules, wantRules) {
		t.Errorf("rules\n got %+v\nwant %+v", reg.Rules, wantRules)
	}
	wantWaivers := []Waiver{{Path: ".aitask-scripts/aitask_gate_log.sh", Reason: "display-only", Until: "2027-03-01", File: gates}}
	if !reflect.DeepEqual(reg.Waivers, wantWaivers) {
		t.Errorf("waivers %+v", reg.Waivers)
	}
	wantFiles := []HandFile{
		{Path: board, Owns: []string{".aitask-scripts/board/**"}},
		{Path: gates, Owns: []string{".aitask-scripts/aitask_gate*.sh", "aitasks/metadata/gates.yaml"}},
	}
	if !reflect.DeepEqual(reg.HandFiles, wantFiles) {
		t.Errorf("hand files %+v", reg.HandFiles)
	}
	if len(reg.Units) != 2 || !reflect.DeepEqual(reg.Units[1].Variants, []string{"ltr", "rtl"}) || reg.Units[1].Line != 12 {
		t.Errorf("units %+v", reg.Units)
	}
}

func TestLoadAbsentAndEmpty(t *testing.T) {
	if _, err := Load(t.TempDir()); !errors.Is(err, ErrAbsent) {
		t.Fatalf("no aitestmap/: %v", err)
	}
	root := t.TempDir()
	writeTree(t, root, map[string]string{Dir + "/.keep": ""})
	reg, err := Load(root)
	if err != nil || len(reg.Edges)+len(reg.Rules)+len(reg.Waivers)+len(reg.HandFiles) != 0 {
		t.Fatalf("empty aitestmap/: %+v %v", reg, err)
	}
}

func TestLoadRefusals(t *testing.T) {
	for _, tc := range []struct{ file, body, want string }{
		{"x.yaml", "contract: 1\nwaiver: []\n", "unknown key waiver"},
		// scopes / areas (hand tables) and _scoped.yaml / areas.yaml are M2.5's,
		// registered from scoped.go; their refusals are pinned in scoped_test.go.
		{"_other.yaml", "contract: 1\n", "reserved file"},
		{"seeded.yaml", "contract: 1\n", "reserved file"},
		{"adopted.yaml", "contract: 1\n", "reserved file"},
		{"observed.yaml", "contract: 1\n", "reserved file"},
		{"x.yaml", "edges: [{covers: a}]\n", "edges[0]: test"},
		{"x.yaml", "edges: [{test: t.sh}]\n", "covers is required"},
		{"x.yaml", "edges: [{test: t.sh, covers: ../a}]\n", "covers"},
		{"x.yaml", "rules: [{when: [a]}]\n", "name is required"},
		{"x.yaml", "rules: [{name: r, select: [a]}]\n", "when is required"},
		{"x.yaml", "rules: [{name: r, when: [a]}]\n", "one of select, implies, escalate"},
		{"x.yaml", "rules: [{name: r, when: ['a/['], select: [b]}]\n", "invalid glob"},
		{"x.yaml", "rules: [{name: r, when: [a], select: [b], distance: -1}]\n", "negative"},
		{"x.yaml", "rules: [{name: r, when: [a], implies: [../b]}]\n", "implies"},
		{"x.yaml", "waivers: [{path: a}]\n", "reason is required"},
		{"x.yaml", "waivers: [{path: a, reason: r, until: soon}]\n", "until"},
		{"x.yaml", "owns: ['a/[']\n", "owns: invalid glob"},
		{"x.yaml", "- a list\n", "mapping"},
		{"x.yaml", "contract: 1\ncontract: 1\n", "contract"},
		{"_scanned.yaml", "units: [{test: 'a@v'}]\n", "no variant fragment"},
		{"_scanned.yaml", "units: [{test: a, unknown: 1}]\n", "unknown"},
		{"_scanned.yaml", "units: [{test: a, covers: [{source: /abs}]}]\n", "covers"},
	} {
		root := t.TempDir()
		writeTree(t, root, map[string]string{RegistryDir + "/" + tc.file: tc.body})
		_, err := Load(root)
		var ie *InvalidError
		if !errors.As(err, &ie) || ie.Path != RegistryDir+"/"+tc.file || !strings.Contains(ie.Reason, tc.want) {
			t.Errorf("%s %q: err %v, want *InvalidError containing %q", tc.file, tc.body, err, tc.want)
		}
	}
}

// A newer contract in any registry file is CONTRACT_MISMATCH, exit 3.
func TestLoadNewerContract(t *testing.T) {
	for _, f := range []string{ConfigPath, ScannedPath, RegistryDir + "/hand.yaml"} {
		root := t.TempDir()
		writeTree(t, root, map[string]string{f: "contract: 2\n", Dir + "/.keep": ""})
		_, err := Load(root)
		var cm *testmap.ContractMismatchError
		if !errors.As(err, &cm) || cm.Path != f || cm.ExitCode() != 3 {
			t.Errorf("%s: %v", f, err)
		}
	}
}

func TestOwnerOf(t *testing.T) {
	reg := &Registry{HandFiles: []HandFile{
		{Path: "a.yaml", Owns: []string{"src/a/**"}},
		{Path: "b.yaml", Owns: []string{"src/b/**", "src/shared.sh"}},
		{Path: "c.yaml", Owns: []string{"src/shared.sh"}},
	}}
	if f, err := reg.OwnerOf("src/b/x.go"); err != nil || f != "b.yaml" {
		t.Fatalf("one owner: %q %v", f, err)
	}
	if _, err := reg.OwnerOf("lib/x.go"); !errors.Is(err, ErrNoOwner) {
		t.Fatalf("no owner: %v", err)
	}
	if _, err := reg.OwnerOf("src/shared.sh"); !errors.Is(err, ErrAmbiguousOwner) {
		t.Fatalf("two owners: %v", err)
	}
}

func TestWaived(t *testing.T) {
	day := func(s string) time.Time { d, _ := time.Parse(time.DateOnly, s); return d }
	reg := &Registry{Waivers: []Waiver{
		{Path: "src/legacy/**", Reason: "r", Until: "2026-12-31"},
		{Path: "src/forever.sh", Reason: "r"},
	}}
	for _, tc := range []struct {
		path, day string
		want      bool
	}{
		{"src/legacy/x.sh", "2026-12-31", true},
		{"src/legacy/x.sh", "2027-01-01", false}, // expired waivers stop waiving
		{"src/forever.sh", "2099-01-01", true},
		{"src/other.sh", "2026-01-01", false},
	} {
		if got := reg.Waived(tc.path, day(tc.day)); got != tc.want {
			t.Errorf("%s on %s: %v", tc.path, tc.day, got)
		}
	}
}

// A rule's select pattern is `<path glob>[#<member glob>]`; both halves are
// validated.
func TestRuleSelectPatterns(t *testing.T) {
	for _, sel := range []string{"tests/x.kt#*", "tests/x.kt#Welcome", "tests/*_test.py#test_[ab]*", "tests/**/*.sh", "tests/{a,b}.kt#{M,N}"} {
		root := t.TempDir()
		writeTree(t, root, map[string]string{RegistryDir + "/x.yaml": "rules: [{name: r, when: [a], select: ['" + sel + "']}]\n"})
		if _, err := Load(root); err != nil {
			t.Errorf("%q refused: %v", sel, err)
		}
	}
	for _, sel := range []string{"tests/a.py#[", "tests/a.py#", "tests/a.py#a#b", "tests/a.py#a/b", "#M", "tests/a.py#M@v", "tests/[.py", "tests/a b.py"} {
		root := t.TempDir()
		writeTree(t, root, map[string]string{RegistryDir + "/x.yaml": "rules: [{name: r, when: [a], select: ['" + sel + "']}]\n"})
		var ie *InvalidError
		if _, err := Load(root); !errors.As(err, &ie) || !strings.Contains(ie.Reason, "select") {
			t.Errorf("%q: %v, want REGISTRY_INVALID on select", sel, err)
		}
	}
}
