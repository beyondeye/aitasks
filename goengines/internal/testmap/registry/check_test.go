package registry

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// The negative control every rule fixture below is compared against.
func TestCheckCleanRepo(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	for _, strict := range []bool{false, true} {
		res := runCheck(t, root, in, strict)
		if res.Status != "pass" || len(res.Findings) != 0 || res.Failing != 0 {
			t.Fatalf("strict=%v: %+v", strict, res)
		}
	}
}

func TestStalePath(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{RegistryDir + "/x.yaml": "owns: [\"src/**\"]\nedges: [{test: tests/test_a.sh, covers: src/gone.sh}]\n"})
	if err := os.Remove(filepath.Join(root, "src/a.sh")); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, "src/dir.sh"), 0o755); err != nil {
		t.Fatal(err)
	}
	in.Annotations = fakeAnns{{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: []Cover{cover("src/a.sh", 2), cover("src/dir.sh", 3)}}}}}
	applyScan(t, root, in)
	res := runCheck(t, root, in, false)
	want := []string{"STALE_PATH:tests/test_a.sh|src/a.sh", "STALE_PATH:tests/test_a.sh|src/dir.sh", "STALE_PATH:tests/test_a.sh|src/gone.sh"}
	if got := only(t, res, RuleStalePath); !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v", got)
	}
	if res.Status != "fail" || res.Failing != 3 {
		t.Fatalf("STALE_PATH must always fail: %+v", res)
	}
}

func TestUnstampedOnlyUnderRequireStampPastBootstrap(t *testing.T) {
	root, in := cleanRepo(t)
	in.Annotations = fakeAnns{{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: []Cover{{Source: "src/a.sh", Line: 2}}}}}}
	applyScan(t, root, in)
	for _, tc := range []struct {
		config, day string
		want        []string
	}{
		{"bootstrap_until: 2026-12-31\nrequire_stamp: true\n", "2026-10-12", nil},  // in bootstrap
		{"bootstrap_until: 2026-01-01\nrequire_stamp: false\n", "2026-10-12", nil}, // no require_stamp
		{"bootstrap_until: 2026-01-01\nrequire_stamp: true\n", "2026-10-12", []string{"UNSTAMPED:tests/test_a.sh|src/a.sh"}},
		{"require_stamp: true\n", "2026-10-12", []string{"UNSTAMPED:tests/test_a.sh|src/a.sh"}}, // no window at all
	} {
		writeTree(t, root, map[string]string{ConfigPath: tc.config})
		atDay(t, tc.day)
		res := runCheck(t, root, in, false)
		if got := only(t, res, RuleUnstamped); !reflect.DeepEqual(got, tc.want) {
			t.Errorf("%q: %v", tc.config, got)
		}
		if (res.Failing > 0) != (tc.want != nil) {
			t.Errorf("%q: failing %d", tc.config, res.Failing)
		}
	}
}

func TestMemberDriftRules(t *testing.T) {
	atDay(t, "2026-10-12")
	root, _ := cleanRepo(t)
	in := Inputs{
		Annotations: fakeAnns{{Path: "app/F.kt", Units: []UnitAnnotation{{Member: "A"}, {Member: "Dead"}}}},
		Lister:      fakeLister{listed("r", "app/F.kt#A", "app/F.kt#New")},
	}
	res := runCheck(t, root, in, false)
	if got := only(t, res, RuleUnannotatedMember); !reflect.DeepEqual(got, []string{"UNANNOTATED_MEMBER:app/F.kt#New"}) {
		t.Errorf("unannotated %v", got)
	}
	if got := only(t, res, RuleDeadMember); !reflect.DeepEqual(got, []string{"DEAD_MEMBER:app/F.kt#Dead"}) {
		t.Errorf("dead %v", got)
	}
	if res.Status != "fail" {
		t.Error("member drift is fail-closed")
	}
}

func TestUnregistered(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		ConfigPath:              "bootstrap_until: 2026-01-01\nexclude: [\"tests/data/**\"]\n",
		RegistryDir + "/x.yaml": "owns: [\"src/**\"]\nedges: [{test: tests/test_declared.sh, covers: src/a.sh}]\n",
	})
	in.Annotations = append(fakeAnns{}, append(in.Annotations.(fakeAnns),
		FileAnnotations{Path: "tests/test_annotated.sh"},
		FileAnnotations{Path: "tests/data/helper.sh"})...) // excluded: never UNREGISTERED
	l := listed("bash-file", "tests/test_a.sh")
	l.Bound = []string{"tests/test_a.sh", "tests/test_bound.sh", "tests/data/x.sh"}
	in.Lister = fakeLister{l}
	applyScan(t, root, in)
	want := []string{"UNREGISTERED:tests/test_annotated.sh", "UNREGISTERED:tests/test_bound.sh", "UNREGISTERED:tests/test_declared.sh"}
	res := runCheck(t, root, in, false)
	if got := only(t, res, RuleUnregistered); !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v", got)
	}
	if res.Failing != 0 {
		t.Fatalf("not strict: must not fail: %+v", res)
	}
	if res := runCheck(t, root, in, true); res.Failing != 3 {
		t.Fatalf("strict past bootstrap: %+v", res)
	}
}

func TestUnmappedArtifact(t *testing.T) {
	atDay(t, "2026-10-12")
	r := fixture.New(t)
	root := r.Dir
	writeTree(t, root, map[string]string{
		ConfigPath:    "exclude: [\"shots/skip/**\"]\n",
		"shots/a.png": "", "shots/b.png": "", "shots/skip/s.png": "",
		"shots/tracked_gone.png": "",
		".gitignore":             "shots/ignored.png\n",
		"shots/ignored.png":      "",
	})
	r.Commit(t, "1", "feature", "shots")
	r.Remove(t, "shots/tracked_gone.png")
	l := listed("screens", "app/F.kt#A@x")
	l.Units[0].Artifact = "shots/a.png"
	l.ArtifactGlobs = []string{"shots/**/*.png"}
	in := Inputs{Annotations: fakeAnns{{Path: "app/F.kt", Units: []UnitAnnotation{{Member: "A"}}}}, Lister: fakeLister{l}}
	applyScan(t, root, in)
	res := runCheck(t, root, in, false)
	want := []string{"UNMAPPED_ARTIFACT:shots/b.png|screens", "UNMAPPED_ARTIFACT:shots/ignored.png|screens"}
	if got := only(t, res, RuleUnmappedArtifact); !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v (deleted tracked file never, ignored existing file yes, excluded never)", got, want)
	}
}

func TestScanDrift(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	in.Lister = fakeLister{listed("bash-file", "tests/test_a.sh@v1")} // a new variant scan has not persisted
	res := runCheck(t, root, in, false)
	if got := only(t, res, RuleScanDrift); !reflect.DeepEqual(got, []string{"SCAN_DRIFT:" + ScannedPath}) {
		t.Fatalf("got %v", got)
	}
	applyScan(t, root, in)
	if got := only(t, runCheck(t, root, in, false), RuleScanDrift); got != nil {
		t.Fatalf("after scan --apply: %v", got)
	}
	// An absent _scanned.yaml equals an empty document.
	root2 := t.TempDir()
	writeTree(t, root2, map[string]string{ConfigPath: ""})
	empty := Inputs{Annotations: fakeAnns{}, Lister: fakeLister{}}
	if res := runCheck(t, root2, empty, true); len(res.Findings) != 0 {
		t.Fatalf("empty: %+v", res)
	}
}

// Ownership is judged over concrete matched paths, never pattern against
// pattern (the two review counterexamples).
func TestOwnsViolation(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		"src/x.go": "", "src/deep/x.go": "", "src/a.go": "", "lib/l.sh": "",
		RegistryDir + "/x.yaml": `owns: ["src/*", "src/[ab].go"]
edges:
  - {test: tests/test_a.sh, covers: [src/a.sh, lib/l.sh]}
rules:
  - {name: escapes, when: ["src/**"], select: [tests/test_a.sh]}
  - {name: bracket-self, when: ["src/[ab].go"], select: [tests/test_a.sh]}
  - {name: matches-nothing, when: ["nowhere/**"], select: [tests/test_a.sh]}
waivers:
  - {path: "src/**", reason: escapes}
  - {path: "src/[ab].go", reason: bracket-self}
`,
		RegistryDir + "/y.yaml": "edges: [{test: tests/test_a.sh, covers: src/a.sh}]\n", // no owns: every row violates
	})
	res := runCheck(t, root, in, false)
	x, y := RegistryDir+"/x.yaml", RegistryDir+"/y.yaml"
	want := []string{
		"OWNS_VIOLATION:" + x + "|edges|lib/l.sh",
		"OWNS_VIOLATION:" + x + "|rules|src/deep/x.go",
		"OWNS_VIOLATION:" + x + "|waivers|src/deep/x.go",
		"OWNS_VIOLATION:" + y + "|edges|src/a.sh",
	}
	got := only(t, res, RuleOwnsViolation)
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got\n%v\nwant\n%v", strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
}

func TestDuplicateRuleAndExpiredWaiver(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		RegistryDir + "/x.yaml": "owns: [\"src/**\"]\nrules: [{name: r, when: [src/a.sh], escalate: true}]\nwaivers: [{path: src/b.sh, reason: old, until: 2026-01-01}, {path: src/a.sh, reason: live}]\n",
		RegistryDir + "/y.yaml": "owns: [\"src/**\"]\nrules: [{name: r, when: [src/b.sh], escalate: true}]\n",
	})
	res := runCheck(t, root, in, true)
	if got := only(t, res, RuleDuplicateRule); !reflect.DeepEqual(got, []string{"DUPLICATE_RULE:r|" + RegistryDir + "/x.yaml|" + RegistryDir + "/y.yaml"}) {
		t.Errorf("dup %v", got)
	}
	if got := only(t, res, RuleWaiverExpired); !reflect.DeepEqual(got, []string{"WAIVER_EXPIRED:src/b.sh|2026-01-01|" + RegistryDir + "/x.yaml"}) {
		t.Errorf("expired %v", got)
	}
	if res.Failing != 1 {
		t.Errorf("only the duplicate fails (WAIVER_EXPIRED is info): %+v", res)
	}
}

// The severity matrix: (strict on/off) × (before/past bootstrap).
func TestSeverityMatrix(t *testing.T) {
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		RegistryDir + "/x.yaml": "owns: [\"src/**\"]\nedges: [{test: tests/test_reg.sh, covers: src/a.sh}]\nwaivers: [{path: src/b.sh, reason: r, until: 2026-01-01}]\n",
	})
	for _, tc := range []struct {
		config string
		strict bool
		fail   int
	}{
		{"bootstrap_until: 2026-12-31\n", false, 0},
		{"bootstrap_until: 2026-12-31\n", true, 0}, // strict before bootstrap ends: reported, not failing
		{"bootstrap_until: 2026-01-01\n", false, 0},
		{"bootstrap_until: 2026-01-01\n", true, 1}, // UNREGISTERED fails; WAIVER_EXPIRED never does
	} {
		writeTree(t, root, map[string]string{ConfigPath: tc.config})
		atDay(t, "2026-10-12")
		res := runCheck(t, root, in, tc.strict)
		if res.Failing != tc.fail || len(res.Findings) != 2 {
			t.Errorf("%q strict=%v: %+v", tc.config, tc.strict, res)
		}
	}
}

// A check that could not look never passes: real unreadable directories, a
// failing stat and failing inputs all abort with an error and no result.
func TestCheckInspectionFailuresAbort(t *testing.T) {
	atDay(t, "2026-10-12")
	t.Run("unreadable artifact dir", func(t *testing.T) {
		root, in := cleanRepo(t)
		writeTree(t, root, map[string]string{"shots/a.png": "", "shots/cache/c.png": ""})
		l := listed("bash-file", "tests/test_a.sh")
		l.ArtifactGlobs = []string{"shots/**/*.png"}
		in.Lister = fakeLister{l}
		unreadable(t, filepath.Join(root, "shots/cache"))
		assertCheckError(t, root, in, "enumerate")
	})
	t.Run("unreadable rule base", func(t *testing.T) {
		root, in := cleanRepo(t)
		writeTree(t, root, map[string]string{"src/sub/z.sh": "", RegistryDir + "/x.yaml": "owns: [\"src/**\"]\nrules: [{name: r, when: [\"src/**\"], escalate: true}]\n"})
		unreadable(t, filepath.Join(root, "src/sub"))
		assertCheckError(t, root, in, "enumerate")
	})
	t.Run("unreadable waiver base", func(t *testing.T) {
		root, in := cleanRepo(t)
		writeTree(t, root, map[string]string{"legacy/q/z.sh": "", RegistryDir + "/x.yaml": "owns: [\"src/**\"]\nwaivers: [{path: \"legacy/**\", reason: r}]\n"})
		unreadable(t, filepath.Join(root, "legacy/q"))
		assertCheckError(t, root, in, "enumerate")
	})
	t.Run("excluded unreadable dir is hidden", func(t *testing.T) {
		root, in := cleanRepo(t)
		writeTree(t, root, map[string]string{ConfigPath: "bootstrap_until: 2099-01-01\nexclude: [\"shots/cache/**\"]\n", "shots/cache/c.png": ""})
		l := listed("bash-file", "tests/test_a.sh")
		l.ArtifactGlobs = []string{"shots/**/*.png"}
		in.Lister = fakeLister{l}
		unreadable(t, filepath.Join(root, "shots/cache"))
		if res := runCheck(t, root, in, true); res.Status != "pass" {
			t.Fatalf("%+v", res)
		}
	})
	t.Run("stat permission error on a covered source", func(t *testing.T) {
		root, in := cleanRepo(t)
		writeTree(t, root, map[string]string{"locked/s.sh": ""})
		in.Annotations = fakeAnns{{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: []Cover{cover("src/a.sh", 2), cover("locked/s.sh", 3)}}}}}
		applyScan(t, root, in)
		unreadable(t, filepath.Join(root, "locked"))
		assertCheckError(t, root, in, RuleStalePath)
	})
	t.Run("input errors", func(t *testing.T) {
		root, in := cleanRepo(t)
		boom := errors.New("boom")
		for _, bad := range []Inputs{
			{Annotations: failingAnns{boom}, Lister: in.Lister},
			{Annotations: in.Annotations, Lister: failingLister{boom}},
			{Annotations: fakeAnns{{Path: "../escape.sh"}}, Lister: in.Lister},
		} {
			_, err := Check(context.Background(), root, bad, CheckOptions{})
			var ie *InputError
			if !errors.As(err, &ie) {
				t.Errorf("%T: %v", bad, err)
			}
			if _, err := Scan(context.Background(), root, bad, true); !errors.As(err, &ie) {
				t.Errorf("scan %T: %v", bad, err)
			}
		}
	})
	t.Run("unavailable inputs", func(t *testing.T) {
		root, in := cleanRepo(t)
		for _, bad := range []Inputs{{Lister: in.Lister}, {Annotations: in.Annotations}} {
			_, err := Check(context.Background(), root, bad, CheckOptions{})
			var ue *UnavailableError
			if !errors.As(err, &ue) {
				t.Errorf("%+v: %v", bad, err)
			}
		}
	})
}

func assertCheckError(t *testing.T, root string, in Inputs, rule string) {
	t.Helper()
	for _, strict := range []bool{false, true} {
		res, err := Check(context.Background(), root, in, CheckOptions{Strict: strict})
		var ce *CheckError
		if res != nil || !errors.As(err, &ce) || ce.Rule != rule || ce.ExitCode() != 3 {
			t.Fatalf("strict=%v: res %+v err %v, want *CheckError{%s}", strict, res, err, rule)
		}
		if l, lerr := ce.Line(); lerr != nil || !strings.HasPrefix(l, "CHECK_ERROR:"+rule+"|") {
			t.Fatalf("line %q %v", l, lerr)
		}
	}
}

// An excluded test's listed unit must not claim an artifact: BuildScanned
// drops it, so its artifact column cannot hide UNMAPPED_ARTIFACT either.
func TestUnmappedArtifactIgnoresExcludedClaimant(t *testing.T) {
	atDay(t, "2026-10-12")
	root, in := cleanRepo(t)
	writeTree(t, root, map[string]string{
		ConfigPath:    "bootstrap_until: 2026-01-01\nexclude: [\"tests/skip/**\"]\n",
		"shots/a.png": "",
	})
	l := listed("screens", "tests/test_a.sh", "tests/skip/a.kt#A")
	l.Units[1].Artifact = "shots/a.png"
	l.ArtifactGlobs = []string{"shots/*.png"}
	in.Lister = fakeLister{l}
	applyScan(t, root, in)
	res := runCheck(t, root, in, true)
	if got := only(t, res, RuleUnmappedArtifact); !reflect.DeepEqual(got, []string{"UNMAPPED_ARTIFACT:shots/a.png|screens"}) {
		t.Fatalf("got %v (%+v)", got, res)
	}
	if res.Status != "fail" {
		t.Fatalf("strict past bootstrap must fail: %+v", res)
	}
}
