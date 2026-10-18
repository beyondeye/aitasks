package registry

import (
	"context"
	"errors"
	"flag"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

var update = flag.Bool("update", false, "rewrite the testdata goldens")

// golden compares got with testdata/<name>, rewriting it under -update.
func golden(t *testing.T, name string, got []byte) {
	t.Helper()
	p := filepath.Join("testdata", name)
	if *update {
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, got, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	want, err := os.ReadFile(p)
	if err != nil {
		t.Fatalf("%v (run with -update to create it)", err)
	}
	if string(got) != string(want) {
		t.Fatalf("%s differs:\n--- got\n%s--- want\n%s", name, got, want)
	}
}

func TestKindVocabulary(t *testing.T) {
	if !reflect.DeepEqual(Kinds, []string{"unit", "integration", "e2e", "device"}) {
		t.Fatalf("Kinds %v", Kinds)
	}
	for i, k := range Kinds {
		if KindRank(k) != i || !ValidKind(k) || IsBroad(k) != (i > 0) {
			t.Fatalf("%s: rank %d broad %v", k, KindRank(k), IsBroad(k))
		}
	}
	if ValidKind("suite") || KindRank("suite") != -1 || IsBroad("") {
		t.Fatal("suite is a runner granularity, not a kind")
	}
}

// scopedAnns is an annotation set exercising every row shape: a file-level
// broad file with members (one inheriting, one restating, one with its own
// scopes), a member-only broad test in a unit file, and a reads helper.
func scopedAnns() fakeAnns {
	return fakeAnns{
		{Path: "tests/test_board_live.py", Units: []UnitAnnotation{
			{Kind: "integration", Areas: []string{"board"}, Needs: []string{"tmux"}, Runner: "pytest", Reviewed: "2026-09-01", ScopedLine: 2},
			{Member: "TestInherits", Line: 10},
			{Member: "TestRestates", Line: 20, Kind: "integration", ScopedLine: 21},
			{Member: "TestOwn", Line: 30, Scopes: []string{"src/b/**"}, Triggers: []string{"lib/x.py"}, Needs: []string{"git"}, ScopedLine: 31},
		}},
		{Path: "tests/test_mixed.sh", Units: []UnitAnnotation{
			{Covers: []Cover{cover("src/a.sh", 2)}},
			{Member: "e2e_flow", Line: 5, Kind: "e2e", Scopes: []string{"src/**", "src/a.sh"}, ScopedLine: 6},
		}},
		{Path: "tests/lib/fixture.py", Units: []UnitAnnotation{{Reads: []string{"tests/*.sh", "tests/*.py"}, ReadsLine: 3}}},
	}
}

func scopedLists() fakeLister {
	return fakeLister{listed("pytest", "tests/test_board_live.py#TestInherits", "tests/test_board_live.py#TestRestates", "tests/test_board_live.py#TestOwn"),
		listed("bash-file", "tests/test_mixed.sh#e2e_flow", "tests/test_a.sh")}
}

func TestBuildScopedGolden(t *testing.T) {
	doc, err := BuildScoped(Defaults(), scopedAnns(), scopedLists())
	if err != nil {
		t.Fatal(err)
	}
	data, err := RenderScoped(doc)
	if err != nil {
		t.Fatal(err)
	}
	golden(t, "scoped/_scoped.yaml", data)
	again, _ := BuildScoped(Defaults(), scopedAnns(), scopedLists())
	if !reflect.DeepEqual(doc, again) {
		t.Fatal("BuildScoped is not deterministic")
	}
}

func refusal(t *testing.T, anns fakeAnns, lists fakeLister, want string) {
	t.Helper()
	_, err := BuildScoped(Defaults(), anns, lists)
	var ie *InputError
	if !errors.As(err, &ie) || ie.Input != InputAnnotations || !strings.Contains(ie.Err.Error(), want) {
		t.Fatalf("err %v, want INPUT_ERROR:annotations containing %q", err, want)
	}
}

func TestBuildScopedRefusals(t *testing.T) {
	f := func(units ...UnitAnnotation) fakeAnns { return fakeAnns{{Path: "tests/t.py", Units: units}} }
	none := fakeLister{}
	refusal(t, f(UnitAnnotation{Kind: "suite", Areas: []string{"a"}, ScopedLine: 3}), none, `tests/t.py:3: unknown kind "suite"`)
	refusal(t, f(UnitAnnotation{Kind: "integration", Areas: []string{"a"}, ScopedLine: 1},
		UnitAnnotation{Member: "M", Line: 4, Kind: "unit", ScopedLine: 5}), none, "tests/t.py:5: member M declares kind unit but the file is integration")
	refusal(t, f(UnitAnnotation{Kind: "integration", Areas: []string{"a"}, ScopedLine: 1},
		UnitAnnotation{Member: "M", Line: 4, Kind: "e2e", Areas: []string{"b"}, ScopedLine: 5}), none, "tests/t.py:5: member M declares kind e2e")
	refusal(t, f(UnitAnnotation{Areas: []string{"a"}, ScopedLine: 2}), none, "tests/t.py:2: testmap:area, scope and trigger belong to a broad test")
	refusal(t, f(UnitAnnotation{Kind: "unit", Scopes: []string{"src/**"}, ScopedLine: 2}), none, "tests/t.py:2: testmap:area, scope and trigger")
	refusal(t, f(UnitAnnotation{Kind: "e2e", ScopedLine: 7}), none, "tests/t.py:7: testmap:kind e2e needs at least one")
	refusal(t, f(UnitAnnotation{}, UnitAnnotation{Member: "M", Line: 3, Kind: "device", ScopedLine: 4}), none, "tests/t.py:4: testmap:kind device needs")
	refusal(t, f(UnitAnnotation{Reads: []string{"x/*"}, ReadsLine: 9}), fakeLister{listed("pytest", "tests/t.py")}, "tests/t.py:9: testmap:reads is legal only in a helper")
	refusal(t, f(UnitAnnotation{Kind: "unit", Reads: []string{"x/*"}, ReadsLine: 2, ScopedLine: 1}), none, "tests/t.py:2: testmap:reads marks a helper")
	// Variant-bearing units are unit kind: through the member's own row and
	// through the file-level row.
	refusal(t, f(UnitAnnotation{}, UnitAnnotation{Member: "M", Line: 3, Kind: "integration", Areas: []string{"a"}, ScopedLine: 4}),
		fakeLister{listed("r", "tests/t.py#M@ltr")}, "tests/t.py:4: tests/t.py#M is listed with variants and cannot be integration")
	refusal(t, f(UnitAnnotation{Kind: "integration", Areas: []string{"a"}, ScopedLine: 1}),
		fakeLister{listed("r", "tests/t.py#M@ltr")}, "tests/t.py:1: tests/t.py#M is listed with variants")
	// The generated file must load: the loader's own validation runs on
	// every generated row (the grammar admits any word).
	refusal(t, f(UnitAnnotation{Kind: "integration", Areas: []string{"invalid/name"}, ScopedLine: 2}), none, "tests/t.py:2: area contains '/'")
	refusal(t, f(UnitAnnotation{Kind: "integration", Areas: []string{"board*"}, ScopedLine: 2}), none, "tests/t.py:2: area \"board*\" contains a glob metacharacter")
	refusal(t, f(UnitAnnotation{Kind: "e2e", Triggers: []string{"x"}, Needs: []string{"a#b"}, ScopedLine: 3}), none, "tests/t.py:3: needs contains")
	refusal(t, f(UnitAnnotation{Kind: "e2e", Triggers: []string{"x"}, Runner: "a@b", ScopedLine: 3}), none, "tests/t.py:3: runner contains")
	// Accepted: a member restating its file's kind; a unit file's variants.
	if _, err := BuildScoped(Defaults(), f(UnitAnnotation{Kind: "integration", Areas: []string{"a"}, ScopedLine: 1},
		UnitAnnotation{Member: "M", Line: 3, Kind: "integration", ScopedLine: 4}), fakeLister{listed("r", "tests/u.py#M@ltr")}); err != nil {
		t.Fatal(err)
	}
	// Excluded files are never judged.
	cfg := Defaults()
	cfg.Exclude = []string{"tests/**"}
	if doc, err := BuildScoped(cfg, f(UnitAnnotation{Kind: "bogus", ScopedLine: 1}), none); err != nil || !doc.empty() {
		t.Fatalf("%+v %v", doc, err)
	}
}

// The round trip the kind data must survive: BuildScoped → scan --apply →
// Load → KindOf answers, for every unit, the kind computed from the
// annotations before persistence.
func TestScopedKindRoundTrip(t *testing.T) {
	root, in := cleanRepo(t)
	in.Annotations = append(fakeAnns{{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: []Cover{cover("src/a.sh", 2)}}}}}, scopedAnns()...)
	in.Lister = scopedLists()
	res := applyScan(t, root, in)
	if !reflect.DeepEqual(res.Wrote, []string{ScannedPath, ScopedPath}) || res.Scoped != 3 || res.Reads != 1 {
		t.Fatalf("%+v", res)
	}
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	s := ScopedOf(reg)
	for id, want := range map[string]string{
		"tests/test_board_live.py":              "integration", // the file-level row
		"tests/test_board_live.py#TestInherits": "integration", // inherits the file row
		"tests/test_board_live.py#TestRestates": "integration", // restates it (no own row)
		"tests/test_board_live.py#TestOwn":      "integration", // its own row, inherited kind
		"tests/test_mixed.sh":                   "unit",        // a unit file ...
		"tests/test_mixed.sh#e2e_flow":          "e2e",         // ... with a broad member
		"tests/test_mixed.sh#other":             "unit",        // an unannotated member of a unit file
		"tests/test_a.sh":                       "unit",
	} {
		if got := s.KindOf(MustParseID(id)); got != want {
			t.Errorf("KindOf(%s) = %s, want %s", id, got, want)
		}
		if s.DigestExempt(MustParseID(id)) != IsBroad(want) {
			t.Errorf("DigestExempt(%s) != %v", id, IsBroad(want))
		}
	}
	if r, ok := s.Row(MustParseID("tests/test_board_live.py#TestOwn")); !ok || r.Runner != "pytest" ||
		!reflect.DeepEqual(r.Needs, []string{"git", "tmux"}) || r.ReviewedAt != "2026-09-01" || r.Line != 31 {
		t.Fatalf("member row inherits runner / needs / reviewed: %+v", r)
	}
	if !reflect.DeepEqual(s.Reads, []ReadsRow{{Helper: "tests/lib/fixture.py", Globs: []string{"tests/*.py", "tests/*.sh"}, Line: 3, File: ScopedPath}}) {
		t.Fatalf("reads %+v", s.Reads)
	}
}

func TestScopedLoaders(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{
		AreasPath: "contract: 1\nareas:\n  board: {paths: [\".aitask-scripts/board/**\"]}\n  cli: {paths: \"ait\"}\n",
		RegistryDir + "/b.yaml": "contract: 1\nowns: [\".aitask-scripts/**\", board]\n" +
			"areas:\n  board: {paths: [\"tests/test_board*.py\", \".aitask-scripts/board/**\"]}\n" +
			"scopes:\n  - {test: tests/test_x_live.py, kind: integration, areas: [board], reviewed_at: \"2026-10-01\", runner: ignored, needs: [ignored]}\n",
		RegistryDir + "/c.yaml": "contract: 1\nowns: [board]\nscopes:\n  - {test: tests/test_y.sh, kind: e2e, globs: [\"src/**\"], triggers: lib/t.py}\n",
	})
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	s := ScopedOf(reg)
	if a := s.Areas["board"]; a == nil || !reflect.DeepEqual(a.Globs, []string{".aitask-scripts/board/**", "tests/test_board*.py"}) ||
		a.From[".aitask-scripts/board/**"] != AreasPath || a.From["tests/test_board*.py"] != RegistryDir+"/b.yaml" {
		t.Fatalf("board %+v", s.Areas["board"])
	}
	if a := s.Areas["cli"]; a == nil || !reflect.DeepEqual(a.Globs, []string{"ait"}) {
		t.Fatalf("cli %+v", s.Areas["cli"])
	}
	got := s.Effective()
	want := []EffectiveRow{
		{Test: MustParseID("tests/test_x_live.py"), Kind: "integration", Areas: []string{"board"}, ReviewedAt: "2026-10-01", Sources: []string{RegistryDir + "/b.yaml"}},
		{Test: MustParseID("tests/test_y.sh"), Kind: "e2e", Globs: []string{"src/**"}, Triggers: []string{"lib/t.py"}, Sources: []string{RegistryDir + "/c.yaml"}},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got  %+v\nwant %+v", got, want)
	}
	if f, err := reg.AreaOwner("cli"); !errors.Is(err, ErrNoOwner) {
		t.Fatalf("no owner: %q %v", f, err)
	}
	if _, err := reg.AreaOwner("board"); !errors.Is(err, ErrAmbiguousOwner) {
		t.Fatalf("two owners: %v", err)
	}
	reg.HandFiles = reg.HandFiles[:1]
	if f, err := reg.AreaOwner("board"); err != nil || f != RegistryDir+"/b.yaml" {
		t.Fatalf("one owner: %q %v", f, err)
	}
}

func TestScopedLoadRefusals(t *testing.T) {
	for _, tc := range []struct{ file, body, want string }{
		{"areas.yaml", "areas: {\"a/b\": {paths: [x]}}\n", "contains '/'"},
		{"areas.yaml", "areas: {\"a*\": {paths: [x]}}\n", "glob metacharacter"},
		{"areas.yaml", "areas: {a: {paths: []}}\n", "paths is required"},
		{"areas.yaml", "areas: {a: {paths: [\"x y\"]}}\n", "whitespace"},
		{"areas.yaml", "areas: {a: {paths: [\"a/[\"]}}\n", "invalid glob"},
		{"areas.yaml", "edges: []\n", "unknown key edges"},
		{"x.yaml", "areas: [a]\n", "areas:"},
		{"x.yaml", "scopes: [{test: t.py, kind: unit, areas: [a]}]\n", "not one of integration, e2e, device"},
		{"x.yaml", "scopes: [{test: t.py, kind: e2e}]\n", "at least one of areas, globs, triggers"},
		{"x.yaml", "scopes: [{test: 't.py#M@ltr', kind: e2e, areas: [a]}]\n", "never names a variant"},
		{"x.yaml", "scopes: [{test: t.py, kind: e2e, areas: [a], reviewed_at: soon}]\n", "reviewed_at"},
		{"x.yaml", "scopes: [{test: /t.py, kind: e2e, areas: [a]}]\n", "scopes[0]: test"},
		{"_scoped.yaml", "scopes: [{test: t.py, kind: e2e, areas: [a], extra: 1}]\n", "extra"},
		{"_scoped.yaml", "reads: [{helper: h.py, globs: []}]\n", "globs is required"},
		{"_scoped.yaml", "reads: [{helper: ../h.py, globs: [x]}]\n", "helper"},
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

// One effective row per test, whatever mix of sources names it.
func TestEffectiveRows(t *testing.T) {
	id := MustParseID("tests/t.py")
	gen := ScopedRow{Test: id, Kind: "integration", Runner: "pytest", Areas: []string{"b", "a"}, Needs: []string{"tmux"}, ReviewedAt: "2026-01-01", Line: 4, File: ScopedPath}
	hand := func(file, kind string, reviewed string) ScopedRow {
		return ScopedRow{Test: id, Kind: kind, Areas: []string{"a", "c"}, Globs: []string{"src/**"}, ReviewedAt: reviewed, File: file}
	}
	for _, tc := range []struct {
		name     string
		rows     []ScopedRow
		kind     string
		areas    []string
		conflict []KindDecl
	}{
		{"generated+hand agree", []ScopedRow{gen, hand("r/h.yaml", "integration", "2026-05-01")}, "integration", []string{"a", "b", "c"}, nil},
		{"generated+hand disagree", []ScopedRow{gen, hand("r/h.yaml", "e2e", "")}, "integration", []string{"a", "b", "c"},
			[]KindDecl{{"integration", ScopedPath}, {"e2e", "r/h.yaml"}}},
		{"hand+hand disagree", []ScopedRow{hand("r/a.yaml", "device", ""), hand("r/b.yaml", "e2e", "")}, "e2e", []string{"a", "c"},
			[]KindDecl{{"device", "r/a.yaml"}, {"e2e", "r/b.yaml"}}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s := &Scoped{Areas: map[string]*Area{}}
			for _, r := range tc.rows {
				s.addRow(r)
			}
			eff := s.Effective()
			if len(eff) != 1 {
				t.Fatalf("%d rows", len(eff))
			}
			e := eff[0]
			if e.Kind != tc.kind || !reflect.DeepEqual(e.Conflict, tc.conflict) || s.KindOf(id) != tc.kind {
				t.Fatalf("kind %s conflict %+v KindOf %s", e.Kind, e.Conflict, s.KindOf(id))
			}
			if !reflect.DeepEqual(e.Areas, tc.areas) {
				t.Fatalf("areas %v", e.Areas)
			}
			hits, err := s.Join([]string{"src/x.go"}, nil, nil)
			if err != nil {
				t.Fatal(err)
			}
			for _, h := range hits {
				if h.Kind != s.KindOf(h.Test) {
					t.Fatalf("join hit kind %s != KindOf %s", h.Kind, s.KindOf(h.Test))
				}
			}
			if len(hits) != 1 {
				t.Fatalf("hits %+v", hits)
			}
		})
	}
	s := &Scoped{Areas: map[string]*Area{}}
	s.addRow(gen)
	s.addRow(hand("r/h.yaml", "integration", "2026-05-01"))
	e := s.Effective()[0]
	if e.Runner != "pytest" || !reflect.DeepEqual(e.Needs, []string{"tmux"}) || e.Line != 4 || e.ReviewedAt != "2026-05-01" ||
		!reflect.DeepEqual(e.Areas, []string{"a", "b", "c"}) || !reflect.DeepEqual(e.Globs, []string{"src/**"}) ||
		!reflect.DeepEqual(e.Sources, []string{ScopedPath, "r/h.yaml"}) {
		t.Fatalf("merge %+v", e)
	}
}

// A scoped annotation refusal writes neither generated file.
func TestScanScopedRefusalWritesNothing(t *testing.T) {
	root, in := cleanRepo(t)
	before := readFile(t, root, ScannedPath)
	in.Annotations = fakeAnns{
		{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: []Cover{cover("src/a.sh", 2), cover("src/b.sh", 3)}}}},
		{Path: "tests/t.py", Units: []UnitAnnotation{{Kind: "bogus", ScopedLine: 1}}},
	}
	_, err := Scan(context.Background(), root, in, true)
	var ie *InputError
	if !errors.As(err, &ie) {
		t.Fatalf("err %v", err)
	}
	if readFile(t, root, ScannedPath) != before {
		t.Fatal("_scanned.yaml was rewritten")
	}
	if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(ScopedPath))); !os.IsNotExist(err) {
		t.Fatalf("_scoped.yaml: %v", err)
	}
}

// No scoped data writes no _scoped.yaml; scoped data writes it, a dry run
// reports its drift, and removing the data rewrites it to an empty document.
func TestScanScopedFile(t *testing.T) {
	root, in := cleanRepo(t)
	if res := applyScan(t, root, in); len(res.Wrote) != 0 || len(res.Drift) != 0 {
		t.Fatalf("%+v", res)
	}
	in.Annotations = append(in.Annotations.(fakeAnns), FileAnnotations{Path: "tests/t_live.py", Units: []UnitAnnotation{{Kind: "e2e", Areas: []string{"a"}, ScopedLine: 1}}})
	res, err := Scan(context.Background(), root, in, false)
	if err != nil || !res.Changed || !reflect.DeepEqual(res.Drift, []string{ScopedPath}) || len(res.Wrote) != 0 {
		t.Fatalf("%+v %v", res, err)
	}
	if res := applyScan(t, root, in); !reflect.DeepEqual(res.Wrote, []string{ScopedPath}) {
		t.Fatalf("%+v", res)
	}
	in.Annotations = in.Annotations.(fakeAnns)[:1]
	applyScan(t, root, in)
	if got := readFile(t, root, ScopedPath); got != GeneratedHeader+"contract: 1\n" {
		t.Fatalf("%q", got)
	}
}
