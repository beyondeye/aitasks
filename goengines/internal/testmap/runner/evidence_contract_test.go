package runner

import (
	"os"
	"path/filepath"
	"reflect"
	"slices"
	"strings"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// The evidence contract (M3.2a) in package runner: the describe classes, the
// zero-test policy key, case rows in `list`, the shared reconciler and the
// freshness rule. The process-level tests are in cases_run_test.go.

// accounting / discovery decode, default, and take the runners.yaml override
// (D6) like every other describe key.
func TestDescribeEvidenceKeys(t *testing.T) {
	d, err := ParseDescribe([]byte("unit: file\naccounting: cases\ndiscovery: native\ntimeouts: batch\n"))
	if err != nil || d.Accounting != AccountingCases || d.Discovery != DiscoveryNative || d.Validate() != nil {
		t.Fatalf("%v %+v", err, d)
	}
	min, _ := ParseDescribe([]byte("unit: file\n"))
	if min.Accounting != AccountingUnit || min.Discovery != DiscoveryCandidates {
		t.Fatalf("defaults %+v", min)
	}
	cfg, err := ParseConfig([]byte("contract: 1\nrunners:\n  - name: s\n    accounting: aggregate\n    discovery: inventory\n"))
	if err != nil {
		t.Fatal(err)
	}
	e := cfg.Runners[0]
	if m := min.Merge(e.Overrides, e.OverrideKeys); m.Accounting != AccountingAggregate || m.Discovery != DiscoveryInventory {
		t.Fatalf("override %+v", m)
	}
}

// An unknown class is refused, and cases cannot pair with per_unit timeouts
// (a per_unit runner reports a unit's timeout as its top-level row).
func TestDescribeRefusesUnknownClasses(t *testing.T) {
	for in, want := range map[string]string{
		"unit: file\naccounting: tests\n":                     "accounting \"tests\" is not cases|unit|aggregate",
		"unit: file\ndiscovery: complete\n":                   "discovery \"complete\" is not native|inventory|candidates",
		"unit: file\naccounting: cases\ntimeouts: per_unit\n": "accounting: cases cannot use timeouts: per_unit",
	} {
		d, err := ParseDescribe([]byte(in))
		if err != nil {
			t.Fatalf("%q: %v", in, err)
		}
		if err := d.Validate(); err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("%q: %v", in, err)
		}
	}
	for _, in := range []string{"unit: file\naccounting: [cases]\n", "unit: file\ndiscovery:\n"} {
		if _, err := ParseDescribe([]byte(in)); err == nil {
			t.Errorf("%q parsed", in)
		}
	}
}

// G7: `children:` names a registered reporting contract or is refused; the
// registry refuses a name twice and an invalid name.
func TestChildrenNeedRegisteredContract(t *testing.T) {
	d, _ := ParseDescribe([]byte("unit: suite\nfull: true\nchildren: junit-x\n"))
	if err := d.Validate(); err == nil || !strings.Contains(err.Error(), "junit-x is not a registered reporting contract") {
		t.Fatalf("unregistered: %v", err)
	}
	withReportingContract(t, "junit-x")
	if err := d.Validate(); err != nil {
		t.Fatalf("registered: %v", err)
	}
	for _, name := range []string{"junit-x", "bad name"} {
		func() {
			defer func() {
				if recover() == nil {
					t.Errorf("%q: no panic", name)
				}
			}()
			RegisterReportingContract(name)
		}()
	}
}

// `zero_tests:` is error|skip; anything else is refused at parse.
func TestZeroTestsEntryKey(t *testing.T) {
	cfg, err := ParseConfig([]byte("contract: 1\nrunners:\n  - name: a\n    zero_tests: skip\n  - name: b\n"))
	if err != nil || cfg.Runners[0].ZeroTests != ZeroTestsSkip || cfg.Runners[1].ZeroTests != "" {
		t.Fatalf("%v %+v", err, cfg.Runners)
	}
	for _, bad := range []string{"pass", "", "[skip]"} {
		if _, err := ParseConfig([]byte("contract: 1\nrunners:\n  - name: a\n    zero_tests: " + bad + "\n")); err == nil {
			t.Errorf("zero_tests %q accepted", bad)
		}
	}
}

// Case rows attach to the unit the same output lists, in list order, before
// or after the unit's own row.
func TestListCaseRows(t *testing.T) {
	rows, err := ParseList([]byte("tests/t.py\tcase\ttests/t.py::a\ntests/t.py\tfile\tt\ntests/t.py\tcase\ttests/t.py::b[x|y z]\ntests/u.py\tfile\tu\n"))
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 2 || !slices.Equal(rows[0].Cases, []string{"tests/t.py::a", "tests/t.py::b[x|y z]"}) || rows[1].Cases != nil {
		t.Fatalf("%+v", rows)
	}
}

// A case row for an unlisted unit, a duplicate identity, an empty or
// control-character identity, or a case row with an extra field is refused
// with its line.
func TestListCaseRowsMalformed(t *testing.T) {
	for in, want := range map[string]string{
		"a.py\tfile\ta\nb.py\tcase\tx\n":                "list line 2: case row for b.py, which this output does not list",
		"a.py\tfile\ta\na.py\tcase\tx\na.py\tcase\tx\n": "list line 3: case \"x\" of a.py already listed on line 2",
		"a.py\tfile\ta\na.py\tcase\t\n":                 "list line 2: case row: invalid case identity",
		"a.py\tfile\ta\na.py\tcase\tx\x01y\n":           "list line 2: case row: invalid case identity",
		"a.py\tfile\ta\na.py\tcase\tx\textra\n":         "list line 2: kind \"case\" is not one of",
		"a.py\tfile\ta\n#bad\tcase\tx\n":                "list line 2: case row",
	} {
		if _, err := ParseList([]byte(in)); err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("%q: %v\nwant %s", in, err, want)
		}
	}
}

// rc is one reconciler outcome, flattened for the matrix.
type rc struct {
	status, policy string
	reasons        []string
	counts         CaseCounts
	skipped        []string
	complete, term bool
}

func flatten(r Reconciled) rc {
	return rc{r.Status, r.Policy, r.Reasons, r.Counts, r.Skipped, r.Complete, r.Terminal}
}

// The reconciliation matrix (G1a / G1b / G3), driven once with top-level keys
// and once with child keys, so suite child evidence (t1854_14) is judged by
// the same rule. Equal-count substitutions are caught by identity, and the
// counters come from the identities, never from the row count.
func TestReconcileMatrix(t *testing.T) {
	type res struct{ c, s string }
	ab := []string{"a", "b"}
	cases := []struct {
		name   string
		expect []string
		zero   string
		taints []string
		got    []res
		want   rc
	}{
		{"a,a", ab, "", nil, []res{{"a", "pass"}, {"a", "pass"}}, rc{"error", "", []string{"duplicate_case", "incomplete"}, CaseCounts{Expected: 2}, nil, false, false}},
		{"a,c", ab, "", nil, []res{{"a", "pass"}, {"c", "pass"}}, rc{"error", "", []string{"unexpected_case", "incomplete"}, CaseCounts{Expected: 2, Passed: 1}, nil, false, false}},
		{"a", ab, "", nil, []res{{"a", "pass"}}, rc{"error", "", []string{"incomplete"}, CaseCounts{Expected: 2, Passed: 1}, nil, false, false}},
		{"a,b,b", ab, "", nil, []res{{"a", "pass"}, {"b", "pass"}, {"b", "pass"}}, rc{"error", "", []string{"duplicate_case"}, CaseCounts{Expected: 2, Passed: 1}, nil, false, false}},
		{"pass+skip", ab, "", nil, []res{{"a", "pass"}, {"b", "skip"}}, rc{"pass", "", nil, CaseCounts{2, 1, 0, 0, 1}, []string{"b"}, true, true}},
		{"fail+error", ab, "", nil, []res{{"a", "error"}, {"b", "fail"}}, rc{"fail", "", nil, CaseCounts{2, 0, 1, 1, 0}, nil, true, true}},
		{"error+pass", ab, "", nil, []res{{"a", "pass"}, {"b", "error"}}, rc{"error", "", nil, CaseCounts{2, 1, 0, 1, 0}, nil, true, true}},
		{"all skip", ab, "", nil, []res{{"a", "skip"}, {"b", "skip"}}, rc{"skip", "", nil, CaseCounts{2, 0, 0, 0, 2}, []string{"a", "b"}, true, true}},
		{"zero/error", nil, "", nil, nil, rc{"error", "zero_tests", nil, CaseCounts{}, nil, true, false}},
		{"zero/skip", nil, ZeroTestsSkip, nil, nil, rc{"skip", "zero_tests", nil, CaseCounts{}, nil, true, false}},
		{"zero+stray", nil, ZeroTestsSkip, nil, []res{{"a", "pass"}}, rc{"error", "", []string{"unexpected_case"}, CaseCounts{}, nil, false, false}},
		{"bad status", ab, "", nil, []res{{"a", "pass"}, {"b", "timeout"}}, rc{"error", "", []string{"unexpected_case", "incomplete"}, CaseCounts{Expected: 2, Passed: 1}, nil, false, false}},
		{"malformed taint", ab, "", []string{ReasonMalformedCase}, []res{{"a", "pass"}, {"b", "pass"}}, rc{"error", "", []string{"malformed_case"}, CaseCounts{Expected: 2, Passed: 2}, nil, false, false}},
		{"rejected zero/skip", nil, ZeroTestsSkip, []string{ReasonRejectedReport}, nil, rc{"error", "", []string{"rejected_report"}, CaseCounts{}, nil, false, false}},
	}
	parents := []registry.ID{{}, {Path: "suite.cfg"}}
	for _, parent := range parents {
		for _, c := range cases {
			key := EvidenceKey{Parent: parent, Unit: registry.ID{Path: "u.py"}}
			// A second unit with the same id under another parent (or none)
			// reports everything passing: evidence never crosses keys.
			other := EvidenceKey{Parent: registry.ID{Path: "other.cfg"}, Unit: key.Unit}
			var reported []CaseResult
			for _, g := range c.got {
				reported = append(reported, CaseResult{Key: key, Case: g.c, Status: g.s, DurationMS: 2})
			}
			reported = append(reported, CaseResult{Key: other, Case: "a", Status: StatusPass}, CaseResult{Key: other, Case: "b", Status: StatusPass})
			out, stray := Reconcile([]Expectation{{Key: key, Cases: c.expect, ZeroTests: c.zero, Taints: c.taints}, {Key: other, Cases: ab}}, reported)
			if got := flatten(out[0]); !reflect.DeepEqual(got, c.want) {
				t.Errorf("%s parent %q:\n got  %+v\n want %+v", c.name, parent, got, c.want)
			}
			if out[1].Status != StatusPass || out[1].Counts.Passed != 2 || len(stray) != 0 {
				t.Errorf("%s parent %q: the other key %+v stray %v", c.name, parent, out[1], stray)
			}
		}
	}
	// A result whose key matches no expectation is handed back as stray.
	_, stray := Reconcile(nil, []CaseResult{{Key: EvidenceKey{Unit: registry.ID{Path: "x"}}, Case: "a", Status: StatusPass}})
	if len(stray) != 1 {
		t.Fatalf("stray %v", stray)
	}
	if r := (Reconciled{Reasons: []string{"duplicate_case", "incomplete"}, Policy: "x"}); r.Reason() != "duplicate_case,incomplete" {
		t.Fatalf("reason %q", r.Reason())
	}
}

// A JSON line is judged on the text it holds, never on what lossy decoding
// would make of it: an unpaired surrogate escape is refused, while a literal
// U+FFFD, its escape, a valid surrogate pair and an escaped backslash
// followed by "u" are not.
func TestExactMembersUnicode(t *testing.T) {
	for line, ok := range map[string]bool{
		`{"unit":"a\uFFFD"}`:       true,
		"{\"unit\":\"a\uFFFD\"}":   true,
		`{"unit":"a\ud83d\ude00"}`: true,
		`{"unit":"a\\ud800"}`:      true,
		`{"unit":"a\\\\"}`:         true,
		`{"unit":"a\ud800"}`:       false,
		`{"unit":"a\udfff"}`:       false,
		`{"unit":"a\ud800x"}`:      false,
		`{"unit":"a\ud800\u0041"}`: false,
		`{"unit":"a\udc00\ud800"}`: false,
		`{"u\ud800nit":"a"}`:       false,
		"{\"unit\":\"a\xff\"}":     false,
	} {
		if err := exactMembers(line, "unit"); (err == nil) != ok {
			t.Errorf("%q: %v, want ok=%v", line, err, ok)
		}
		if m, err := members(line); err == nil {
			if _, got := soleString(m, "unit"); ok && !got {
				t.Errorf("%q: soleString refused a valid value", line)
			} else if !ok && got && !strings.Contains(line, "u\\ud800nit") {
				t.Errorf("%q: soleString accepted an unrepresentable value", line)
			}
		}
	}
}

// G6: FreshReport reads only what this invocation wrote into its report
// directory.
func TestFreshReportRefusals(t *testing.T) {
	base := t.TempDir()
	d, err := NewReportDir(filepath.Join(base, "report"))
	if err != nil {
		t.Fatal(err)
	}
	dir, start := d.Path, d.Start
	if _, err := NewReportDir(dir); err == nil {
		t.Fatal("a report directory that already exists was accepted")
	}
	write := func(p, s string) string {
		t.Helper()
		full := filepath.Join(dir, p)
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, []byte(s), 0o644); err != nil {
			t.Fatal(err)
		}
		return full
	}
	fresh := write("cases.jsonl", "x\n")
	if data, absent, err := FreshReport(d, fresh); err != nil || absent || string(data) != "x\n" {
		t.Fatalf("fresh: %q %v %v", data, absent, err)
	}
	if _, absent, err := FreshReport(d, filepath.Join(dir, "none.jsonl")); err != nil || !absent {
		t.Fatalf("absent: %v %v", absent, err)
	}
	if _, absent, err := FreshReport(d, filepath.Join(dir, "sub", "none.jsonl")); err != nil || !absent {
		t.Fatalf("absent below a missing dir: %v %v", absent, err)
	}
	old := write("old.jsonl", "y\n")
	if err := os.Chtimes(old, start.Add(-time.Hour), start.Add(-time.Hour)); err != nil {
		t.Fatal(err)
	}
	outside := filepath.Join(base, "outside.jsonl")
	if err := os.WriteFile(outside, []byte("z\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Join(dir, "link.jsonl")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(base, filepath.Join(dir, "linkdir")); err != nil {
		t.Fatal(err)
	}
	// A link to a fresh file inside the directory is a link all the same.
	if err := os.Symlink("cases.jsonl", filepath.Join(dir, "inlink.jsonl")); err != nil {
		t.Fatal(err)
	}
	for path, want := range map[string]string{
		old:                                "stale: modified",
		filepath.Join(dir, "link.jsonl"):   "a symbolic link",
		filepath.Join(dir, "inlink.jsonl"): "a symbolic link",
		filepath.Join(dir, "linkdir", "outside.jsonl"): "linkdir is not a directory",
		filepath.Join(dir, "..", "outside.jsonl"):      "outside the report directory",
		outside: "outside the report directory",
		dir:     "outside the report directory",
	} {
		if _, absent, err := FreshReport(d, path); err == nil || absent || !strings.Contains(err.Error(), want) {
			t.Errorf("%s: absent %v err %v, want %q", path, absent, err, want)
		}
	}
	if _, _, err := FreshReport(ReportDir{Path: dir}, fresh); err == nil {
		t.Error("a report directory the engine did not create was read")
	}
	// The report directory itself replaced — by a link to a directory of
	// fresh evidence elsewhere, or by a new directory at the same path —
	// is refused: only the directory the engine created is read.
	elsewhere := filepath.Join(base, "elsewhere")
	if err := os.Mkdir(elsewhere, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(elsewhere, "cases.jsonl"), []byte("fresh\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Rename(dir, filepath.Join(base, "moved")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(elsewhere, dir); err != nil {
		t.Fatal(err)
	}
	if _, absent, err := FreshReport(d, fresh); err == nil || absent || !strings.Contains(err.Error(), "the report directory was replaced") {
		t.Errorf("symlinked report directory: absent %v err %v", absent, err)
	}
	if err := os.Remove(dir); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(fresh, []byte("new\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, absent, err := FreshReport(d, fresh); err == nil || absent || !strings.Contains(err.Error(), "the report directory was replaced") {
		t.Errorf("recreated report directory: absent %v err %v", absent, err)
	}
	if err := os.Remove(fresh); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(dir); err != nil {
		t.Fatal(err)
	}
	if _, absent, err := FreshReport(d, fresh); err == nil || absent {
		t.Errorf("removed report directory: absent %v err %v", absent, err)
	}
}

// OpenReportDir takes the engine's report directory in another process (a
// builtin at startup): only a real, empty directory, and FreshReport then
// judges freshness against the moment it was opened.
func TestOpenReportDir(t *testing.T) {
	base := t.TempDir()
	dir := filepath.Join(base, "report")
	if _, err := NewReportDir(dir); err != nil {
		t.Fatal(err)
	}
	d, err := OpenReportDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	fresh := filepath.Join(dir, "cases.jsonl")
	if err := os.WriteFile(fresh, []byte("x\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if data, _, err := FreshReport(d, fresh); err != nil || string(data) != "x\n" {
		t.Fatalf("fresh: %q %v", data, err)
	}
	old := filepath.Join(dir, "old.jsonl")
	if err := os.WriteFile(old, []byte("y\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Chtimes(old, d.Start.Add(-time.Hour), d.Start.Add(-time.Hour)); err != nil {
		t.Fatal(err)
	}
	if _, _, err := FreshReport(d, old); err == nil || !strings.Contains(err.Error(), "stale") {
		t.Fatalf("back-dated: %v", err)
	}
	if _, err := OpenReportDir(dir); err == nil || !strings.Contains(err.Error(), "not empty") {
		t.Fatalf("non-empty: %v", err)
	}
	file := filepath.Join(base, "file")
	if err := os.WriteFile(file, nil, 0o644); err != nil {
		t.Fatal(err)
	}
	empty := filepath.Join(base, "empty")
	if err := os.Mkdir(empty, 0o755); err != nil {
		t.Fatal(err)
	}
	link := filepath.Join(base, "link")
	if err := os.Symlink(empty, link); err != nil {
		t.Fatal(err)
	}
	for _, p := range []string{file, link, filepath.Join(base, "missing")} {
		if _, err := OpenReportDir(p); err == nil {
			t.Errorf("%s accepted", p)
		}
	}
}
