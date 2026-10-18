package registry

import (
	"context"
	"errors"
	"reflect"
	"testing"
)

// The M2.5 rules on fixtures derived from cleanRepo, whose clean check
// (TestCheckCleanRepo) is the negative control for every rule here.

func withAnns(in Inputs, more ...FileAnnotations) Inputs {
	in.Annotations = append(append(fakeAnns(nil), in.Annotations.(fakeAnns)...), more...)
	return in
}

func TestDeadScope(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{AreasPath: "contract: 1\nareas:\n  src: {paths: [\"src/**\", \"gone/**\"]}\n"})
	in = withAnns(in, FileAnnotations{Path: "tests/t_live.py", Units: []UnitAnnotation{
		{Kind: "integration", Areas: []string{"src", "nope"}, Scopes: []string{"nothing/**", "src/a.sh"}, Triggers: []string{"future/x.py"}, ScopedLine: 1},
	}})
	applyScan(t, root, in)
	res := runCheck(t, root, in, false)
	want := []string{
		"DEAD_SCOPE:aitestmap/registry/areas.yaml|areas|src|gone/**",
		"DEAD_SCOPE:tests/t_live.py|area|nope|undeclared",
		"DEAD_SCOPE:tests/t_live.py|scope|nothing/**|empty",
	}
	if got := only(t, res, RuleDeadScope); !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v", got)
	}
	if res.Status != "fail" || res.Failing != 3 {
		t.Fatalf("DEAD_SCOPE always fails: %+v", res)
	}
}

func TestKindMismatch(t *testing.T) {
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		ConfigPath:              "contract: 1\nbootstrap_until: 2026-01-01\nunit_covers_max: 2\n",
		RegistryDir + "/x.yaml": "contract: 1\nowns: [\"src/**\"]\nedges: [{test: tests/test_a.sh, covers: src/c.sh}]\n",
		"src/c.sh":              "",
	})
	atDay(t, "2026-10-12")
	at := func(n int) Inputs {
		covers := []Cover{cover("src/a.sh", 2), cover("src/b.sh", 3)}[:n]
		live := FileAnnotations{Path: "tests/t_live.py", Units: []UnitAnnotation{{Kind: "e2e", Areas: []string{"x"},
			Covers: []Cover{cover("src/a.sh", 2), cover("src/b.sh", 3), cover("src/c.sh", 4)}, ScopedLine: 1}}}
		return Inputs{Annotations: fakeAnns{{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: covers}}}, live}, Lister: in.Lister}
	}
	// 1 annotation + 1 declared = 2 = unit_covers_max: no finding; the e2e
	// test's 3 fixture pins never count.
	applyScan(t, root, at(1))
	if got := only(t, runCheck(t, root, at(1), true), RuleKindMismatch); len(got) != 0 {
		t.Fatalf("at the limit: %v", got)
	}
	applyScan(t, root, at(2))
	want := []string{"KIND_MISMATCH:tests/test_a.sh|3|CONVERT_TO_SUITE"}
	res := runCheck(t, root, at(2), false)
	if got := only(t, res, RuleKindMismatch); !reflect.DeepEqual(got, want) || res.Findings[indexOf(res, RuleKindMismatch)].Fail {
		t.Fatalf("a warning without --strict: %v %+v", got, res)
	}
	res = runCheck(t, root, at(2), true)
	if got := only(t, res, RuleKindMismatch); !reflect.DeepEqual(got, want) || !res.Findings[indexOf(res, RuleKindMismatch)].Fail {
		t.Fatalf("fails under --strict past bootstrap: %v %+v", got, res)
	}
}

func indexOf(res *CheckResult, rule string) int {
	for i, f := range res.Findings {
		if f.Rule == rule {
			return i
		}
	}
	return -1
}

func TestScopesOwnsViolation(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		AreasPath: "contract: 1\nareas:\n  board: {paths: [\"src/**\"]}\n  cli: {paths: [\"src/a.sh\"]}\n",
		RegistryDir + "/x.yaml": "contract: 1\nowns: [\"src/**\", board]\n" +
			"scopes: [{test: tests/test_a.sh, kind: e2e, areas: [board, cli], globs: [\"src/**\", \"lib/*.sh\"], triggers: [lib/t.sh]}]\n",
		"lib/x.sh": "", "lib/t.sh": "",
	})
	res := runCheck(t, root, in, false)
	want := []string{
		"OWNS_VIOLATION:aitestmap/registry/x.yaml|scopes|cli",
		"OWNS_VIOLATION:aitestmap/registry/x.yaml|scopes|lib/t.sh",
		"OWNS_VIOLATION:aitestmap/registry/x.yaml|scopes|lib/x.sh",
	}
	if got := only(t, res, RuleOwnsViolation); !reflect.DeepEqual(got, want) || res.Failing != 3 {
		t.Fatalf("got %v %+v", got, res)
	}
}

func TestScopeConflict(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		AreasPath:               "contract: 1\nareas:\n  board: {paths: [\"src/**\"]}\n",
		RegistryDir + "/x.yaml": "contract: 1\nowns: [\"src/**\", board]\nscopes: [{test: tests/t.py, kind: e2e, areas: [board]}]\n",
	})
	in = withAnns(in, FileAnnotations{Path: "tests/t.py", Units: []UnitAnnotation{{Kind: "integration", Areas: []string{"board"}, ScopedLine: 1}}})
	applyScan(t, root, in)
	res := runCheck(t, root, in, false)
	want := []string{"SCOPE_CONFLICT:tests/t.py|kind|integration@aitestmap/registry/_scoped.yaml,e2e@aitestmap/registry/x.yaml"}
	if got := only(t, res, RuleScopeConflict); !reflect.DeepEqual(got, want) || res.Failing != 1 {
		t.Fatalf("got %v %+v", got, res)
	}
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	if k := ScopedOf(reg).KindOf(MustParseID("tests/t.py")); k != KindIntegration {
		t.Fatalf("a conflict reads as the lowest-ranked kind, got %s", k)
	}
}

func TestScopeInvalidHandRowOnVariants(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		AreasPath: "contract: 1\nareas:\n  board: {paths: [\"src/**\"]}\n",
		RegistryDir + "/x.yaml": "contract: 1\nowns: [\"src/**\", board]\nscopes:\n" +
			"  - {test: 'tests/f.kt#M', kind: device, areas: [board]}\n" + // a base id whose unit has variants
			"  - {test: tests/g.kt, kind: e2e, areas: [board]}\n" + // a file whose member has variants
			"  - {test: tests/h.kt, kind: e2e, areas: [board]}\n", // no variants: valid
	})
	in.Lister = fakeLister{listed("bash-file", "tests/test_a.sh"), listed("gradle", "tests/f.kt#M@ltr", "tests/f.kt#M@rtl", "tests/g.kt#N@ltr", "tests/h.kt#P")}
	res := runCheck(t, root, in, false)
	want := []string{
		"SCOPE_INVALID:tests/f.kt#M|aitestmap/registry/x.yaml|variant-bearing",
		"SCOPE_INVALID:tests/g.kt|aitestmap/registry/x.yaml|variant-bearing",
	}
	if got := only(t, res, RuleScopeInvalid); !reflect.DeepEqual(got, want) || res.Failing != 2 {
		t.Fatalf("got %v %+v", got, res)
	}
}

func TestScopedScanDrift(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	in = withAnns(in, FileAnnotations{Path: "tests/t.py", Units: []UnitAnnotation{{Kind: "e2e", Triggers: []string{"src/a.sh"}, ScopedLine: 1}}})
	res := runCheck(t, root, in, false)
	if got := only(t, res, RuleScanDrift); !reflect.DeepEqual(got, []string{"SCAN_DRIFT:" + ScopedPath}) {
		t.Fatalf("got %v", got)
	}
	applyScan(t, root, in)
	if got := only(t, runCheck(t, root, in, false), RuleScanDrift); len(got) != 0 {
		t.Fatalf("after apply: %v", got)
	}
}

// An annotation BuildScoped refuses is INPUT_ERROR:annotations in check, as
// in scan — never a CHECK_ERROR naming one of M2.5's rules.
func TestCheckScopedRefusalIsInputError(t *testing.T) {
	root, in := cleanRepo(t)
	in = withAnns(in, FileAnnotations{Path: "tests/t.py", Units: []UnitAnnotation{{Areas: []string{"a"}, ScopedLine: 4}}})
	_, err := Check(context.Background(), root, in, CheckOptions{})
	var ie *InputError
	if !errors.As(err, &ie) || ie.Input != InputAnnotations {
		t.Fatalf("err %T %v", err, err)
	}
	if l, _ := ie.Line(); l != "INPUT_ERROR:annotations|tests/t.py:4: testmap:area, scope and trigger belong to a broad test (declare testmap:kind integration, e2e or device)" {
		t.Fatalf("line %q", l)
	}
}

// A `testmap:reads` helper carries annotations but no runner lists it — by
// definition, not by omission — so it is never UNREGISTERED (negative
// control: an annotated file without reads still is).
func TestReadsHelperIsNotUnregistered(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	in = withAnns(in,
		FileAnnotations{Path: "tests/lib/fixture.py", Units: []UnitAnnotation{{Reads: []string{"tests/*.sh"}, ReadsLine: 1}}},
		FileAnnotations{Path: "tests/lib/stray.py", Units: []UnitAnnotation{{Covers: []Cover{cover("src/a.sh", 1)}}}},
	)
	applyScan(t, root, in)
	if got := only(t, runCheck(t, root, in, true), RuleUnregistered); !reflect.DeepEqual(got, []string{"UNREGISTERED:tests/lib/stray.py"}) {
		t.Fatalf("got %v", got)
	}
}

// A hand `scopes:` row names a test: one no runner lists is UNREGISTERED,
// exactly like a declared edge's test, with the same severity and the same
// `exclude:` handling.
func TestHandScopeTestIsRegistrationChecked(t *testing.T) {
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		ConfigPath: "contract: 1\nbootstrap_until: 2026-01-01\nexclude: [\"tests/skip/**\"]\n",
		RegistryDir + "/x.yaml": "contract: 1\nowns: [\"src/**\"]\nscopes:\n" +
			"  - {test: tests/missing.sh, kind: e2e, globs: [\"src/**\"]}\n" +
			"  - {test: tests/skip/t.sh, kind: e2e, globs: [\"src/**\"]}\n" +
			"  - {test: tests/test_a.sh, kind: e2e, globs: [\"src/**\"]}\n",
	})
	atDay(t, "2026-10-12")
	res := runCheck(t, root, in, true)
	if got := only(t, res, RuleUnregistered); !reflect.DeepEqual(got, []string{"UNREGISTERED:tests/missing.sh"}) || res.Status != "fail" {
		t.Fatalf("got %v %+v", got, res)
	}
	if got := only(t, runCheck(t, root, in, false), RuleUnregistered); len(got) != 1 || runCheck(t, root, in, false).Failing != 0 {
		t.Fatalf("not strict: reported, not failing: %v", got)
	}
}
