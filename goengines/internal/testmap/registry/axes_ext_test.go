package registry

import (
	"context"
	"errors"
	"strings"
	"testing"
)

// M2.4's named extensions of this package: a listing's axis and the units'
// `testmap:axis` claims persist on `_scanned.yaml` rows; the lister and the
// annotation source are validated for them; `check` can run a named subset
// of its rules.

func TestScanPersistsAxisAndClaims(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{ConfigPath: "contract: 1\n"})
	matrix := listed("screen-matrix", "app/F.kt#Welcome@ru-ltr", "app/F.kt#Welcome@en-ltr")
	matrix.Axis = "matrix"
	in := Inputs{
		Annotations: fakeAnns{
			{Path: "app/F.kt", Units: []UnitAnnotation{{}, {Member: "Welcome", Line: 4}}},
			// a file-level block carrying only claims gets a row, its claims sorted and deduplicated
			{Path: "tests/test_ru.sh", Units: []UnitAnnotation{{Axes: []string{"matrix.locale=ru", "matrix.direction=ltr", "matrix.locale=ru"}}}},
			{Path: "app/G.kt", Units: []UnitAnnotation{{}, {Member: "Plain", Line: 2, Axes: []string{"matrix.locale=ar"}}}},
		},
		Lister: fakeLister{
			matrix,
			listed("bash-file", "tests/test_ru.sh", "app/G.kt#Plain"),
			listed("noaxis", "docs/m.md@b"), // a runner naming no axis persists no axis
		},
	}
	res := applyScan(t, root, in)
	if res.Units != 4 || res.Variants != 3 {
		t.Fatalf("counts %+v", res)
	}
	want := GeneratedHeader + `contract: 1
units:
  - test: app/F.kt#Welcome
    line: 4
    axis: matrix
    variants: [en-ltr, ru-ltr]
  - test: app/G.kt#Plain
    line: 2
    facets: [matrix.locale=ar]
  - test: docs/m.md
    variants: [b]
  - test: tests/test_ru.sh
    facets: [matrix.direction=ltr, matrix.locale=ru]
`
	if got := readFile(t, root, ScannedPath); got != want {
		t.Fatalf("_scanned.yaml:\n%s\nwant:\n%s", got, want)
	}
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	if reg.Units[0].Axis != "matrix" || len(reg.Units[3].Facets) != 2 {
		t.Fatalf("reloaded %+v", reg.Units)
	}
}

func TestReadInputsRefusesBadAxisInputs(t *testing.T) {
	root := t.TempDir()
	a := listed("a", "x.kt#M@v1")
	a.Axis = "matrix"
	b := listed("b", "x.kt#M@v2")
	b.Axis = "other"
	bad := listed("c", "y.kt@v")
	bad.Axis = "m.x"
	plain := fakeAnns{{Path: "x.kt", Units: []UnitAnnotation{{}}}}
	for name, c := range map[string]struct {
		in   Inputs
		want string
	}{
		"axis conflict": {Inputs{Annotations: plain, Lister: fakeLister{a, b}}, `variants of x.kt#M listed on axes "matrix" and "other"`},
		"bad axis":      {Inputs{Annotations: plain, Lister: fakeLister{bad}}, `invalid axis "m.x"`},
		"bad claim":     {Inputs{Annotations: fakeAnns{{Path: "x.kt", Units: []UnitAnnotation{{Axes: []string{"m.l=a b"}}}}}, Lister: fakeLister{}}, `axis claim "m.l=a b" is invalid`},
		"empty claim":   {Inputs{Annotations: fakeAnns{{Path: "x.kt", Units: []UnitAnnotation{{Axes: []string{""}}}}}, Lister: fakeLister{}}, `axis claim "" is invalid`},
	} {
		_, _, err := ReadInputs(context.Background(), root, c.in)
		var ie *InputError
		if !errors.As(err, &ie) || !strings.Contains(err.Error(), c.want) {
			t.Errorf("%s: %v (want %q)", name, err, c.want)
		}
	}
	// One runner listing its own variants on its one axis is fine.
	a2 := listed("a", "x.kt#M@v1", "x.kt#M@v2")
	a2.Axis = "matrix"
	if _, _, err := ReadInputs(context.Background(), root, Inputs{Annotations: plain, Lister: fakeLister{a2}}); err != nil {
		t.Fatal(err)
	}
}

func TestCheckRulesFilter(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{"tests/test_b.sh": "#!/usr/bin/env bash\n# testmap:covers src/gone.sh\n"})
	in.Annotations = append(in.Annotations.(fakeAnns), FileAnnotations{Path: "tests/test_b.sh", Units: []UnitAnnotation{{Covers: []Cover{{Source: "src/gone.sh", Line: 2}}}}})
	all := runCheck(t, root, in, false)
	only, err := Check(context.Background(), root, in, CheckOptions{Rules: []string{RuleStalePath}})
	if err != nil {
		t.Fatal(err)
	}
	if len(only.Findings) == 0 || len(only.Summary) != 0 {
		t.Fatalf("filtered: %+v", only)
	}
	for _, f := range only.Findings {
		if f.Rule != RuleStalePath {
			t.Fatalf("filtered check ran %s", f.Rule)
		}
	}
	other := false
	for _, f := range all.Findings {
		other = other || f.Rule != RuleStalePath
	}
	if !other || len(all.Summary) == 0 {
		t.Fatalf("fixture: the unfiltered check must see other rules too: %+v", all)
	}
	// Two rules share a name: both run when it is named.
	if rs, err := selectRules([]string{RuleOwnsViolation}); err != nil || len(rs) < 2 {
		t.Fatalf("OWNS_VIOLATION rules %d %v", len(rs), err)
	}
	_, err = Check(context.Background(), root, in, CheckOptions{Rules: []string{"NO_SUCH_RULE"}})
	var ce *CheckError
	if !errors.As(err, &ce) || !strings.Contains(err.Error(), "unknown rule NO_SUCH_RULE") {
		t.Fatalf("%v", err)
	}
}
