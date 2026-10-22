package runner

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"slices"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// The evidence contract through Run: accounting: cases runners whose unit
// results the engine derives from cases.jsonl through the shared reconciler.

const casesDescribe = "unit: file\naccounting: cases\ndiscovery: native"

// scen is one fixture runner: its describe, list (with case rows), run body
// and extra runners.yaml entry lines.
type scen struct {
	name, describe, list, run, entry string
}

// unitPaths are the unit ids a list declares (case rows skipped).
func unitPaths(list string) []string {
	var out []string
	for _, l := range strings.Split(strings.TrimSpace(list), "\n") {
		if f := strings.Split(l, "|"); len(f) > 1 && f[1] != caseKind {
			out = append(out, f[0])
		}
	}
	return out
}

// scenRepo is one repository holding every scenario's runner, each bound to
// its own unit paths.
func scenRepo(t *testing.T, ss []scen) *fixture.Repo {
	t.Helper()
	files := map[string]string{}
	var yaml strings.Builder
	yaml.WriteString("runners:\n")
	for _, s := range ss {
		var b []string
		for _, p := range unitPaths(s.list) {
			files[p] = "x\n"
			b = append(b, "'"+p+"'")
		}
		entry := s.entry
		if !strings.Contains(entry, "timeout_s:") {
			entry += "    timeout_s: 10\n"
		}
		fmt.Fprintf(&yaml, "  - name: %s\n    bind: [%s]\n%s", s.name, strings.Join(b, ", "), entry)
	}
	r := newRepo(t, files)
	for _, s := range ss {
		put(t, r, s.name, spec{describe: s.describe, list: s.list, run: s.run})
	}
	runners(t, r, yaml.String())
	commitAll(t, r)
	return r
}

// runIDs runs explicit ids under a run id of its own.
func runIDs(t *testing.T, r *fixture.Repo, runID string, ids ...string) *RunReport {
	t.Helper()
	rep, err := Run(bg, r.Dir, Options{IDs: ids, RunID: runID})
	if err != nil {
		t.Fatalf("%s: %v", runID, err)
	}
	return rep
}

// resultOf is id's top-level result.
func resultOf(t *testing.T, rep *RunReport, id string) Result {
	t.Helper()
	for _, x := range rep.Results {
		if !x.Child && x.ID.String() == id {
			return x
		}
	}
	t.Fatalf("no result for %s in %+v", id, rep.Results)
	return Result{}
}

// G1a / G1b end to end: the engine reconciles each unit's expected identities
// (from this run's list) against cases.jsonl and derives the result and the
// counters; equal-count substitutions are errors; the manifest carries what
// the adapter needs.
func TestCasesRunReconciled(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	st := stateOfRepoless(t)
	list := "tests/u.py|file|u\ntests/u.py|case|a\ntests/u.py|case|b\n" +
		"tests/v.py|file|v\ntests/v.py|case|a\ntests/v.py|case|b\n" +
		"tests/w.py|file|w\ntests/w.py|case|a\ntests/w.py|case|b\n"
	r := scenRepo(t, []scen{{name: "py", describe: casesDescribe + "\ntimeouts: batch", list: list, entry: "    batch_timeout_s: 30\n",
		run: "cp \"$M\" " + st + "/manifest.json; echo \"$AIT_TESTMAP_ACCOUNTING\" > " + st + "/acct\n" +
			"crow tests/u.py a pass 3; crow tests/u.py b skip 1; crow tests/v.py a pass; crow tests/v.py a pass; crow tests/w.py a pass; crow tests/w.py c pass"}})
	rep := runIDs(t, r, "cases", "tests/u.py", "tests/v.py", "tests/w.py")
	u := resultOf(t, rep, "tests/u.py")
	if u.Status != StatusPass || u.Reason != "" || !reflect.DeepEqual(*u.Cases, CaseCounts{2, 1, 0, 0, 1}) || !slices.Equal(u.SkippedCases, []string{"b"}) || u.DurationMS != 4 {
		t.Fatalf("u: %+v %+v", u, u.Cases)
	}
	if v := resultOf(t, rep, "tests/v.py"); v.Status != StatusError || v.Reason != "duplicate_case,incomplete" || v.Cases.Passed != 0 {
		t.Fatalf("v ({a,a}): %+v", v)
	}
	if w := resultOf(t, rep, "tests/w.py"); w.Status != StatusError || w.Reason != "unexpected_case,incomplete" || w.Cases.Passed != 1 {
		t.Fatalf("w ({a,c}): %+v", w)
	}
	rec := rep.Invocations[0]
	if rec.Cause != CauseReconciliation || rec.Accounting != AccountingCases || rec.Discovery != DiscoveryNative ||
		!reflect.DeepEqual(*rec.Cases, CaseCounts{6, 2, 0, 0, 1}) || rep.Exit() != 1 ||
		!slices.Equal(rec.ProtocolErrors, []string{"duplicate_case:tests/v.py", "incomplete:tests/v.py", "unexpected_case:tests/w.py", "incomplete:tests/w.py"}) {
		t.Fatalf("record %+v exit %d", rec, rep.Exit())
	}
	var m Manifest
	b, err := os.ReadFile(st + "/manifest.json")
	if err != nil || json.Unmarshal(b, &m) != nil || m.Accounting != AccountingCases || m.ReportDir != rec.ReportDir || !slices.Equal(m.Units[0].Cases, []string{"a", "b"}) {
		t.Fatalf("manifest %v %+v", err, m)
	}
	if a, _ := os.ReadFile(st + "/acct"); string(a) != "cases\n" {
		t.Fatalf("AIT_TESTMAP_ACCOUNTING %q", a)
	}
	// No cases.jsonl at all: every expected identity is missing.
	put(t, r, "py", spec{describe: casesDescribe + "\ntimeouts: batch", list: list, run: "exit 0"})
	rep = runIDs(t, r, "cases-none", "tests/u.py")
	if u := resultOf(t, rep, "tests/u.py"); u.Status != StatusError || u.Reason != "incomplete" || rep.Invocations[0].CauseDetail != "incomplete:tests/u.py" {
		t.Fatalf("no evidence: %+v %+v", u, rep.Invocations[0])
	}
}

// Under cases a top-level result row from the adapter is refused: the unit's
// result is the engine's alone.
func TestCasesTopLevelRowRefused(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := scenRepo(t, []scen{{name: "py", describe: casesDescribe, list: "tests/u.py|file|u\ntests/u.py|case|a\n",
		run: "crow tests/u.py a pass; row tests/u.py pass"}})
	rep := runIDs(t, r, "top", "tests/u.py")
	if u := resultOf(t, rep, "tests/u.py"); u.Status != StatusError || u.Message != "protocol:result_under_cases" || rep.Invocations[0].CauseDetail != "result_under_cases:tests/u.py" {
		t.Fatalf("%+v %+v", u, rep.Invocations[0])
	}
}

// Under unit (and aggregate) accounting a case row is refused, and so are
// case rows in list and a zero-test policy.
func TestCaseRowsRefusedUnderUnit(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := scenRepo(t, []scen{{name: "sh", describe: "unit: file", list: "tests/a.sh|file|a\n", run: "row tests/a.sh pass; crow tests/a.sh a pass"}})
	rep := runIDs(t, r, "unit", "tests/a.sh")
	if rec := rep.Invocations[0]; rec.Cause != CauseReconciliation || rec.CauseDetail != "cases:refused:cases.jsonl from accounting: unit" || resultOf(t, rep, "tests/a.sh").Status != StatusPass {
		t.Fatalf("%+v", rec)
	}
	put(t, r, "sh", spec{describe: "unit: file", list: "tests/a.sh|file|a\ntests/a.sh|case|x\n"})
	if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "RUNNER_PROTOCOL:sh|list|list line 1: case rows from a runner with accounting: unit") {
		t.Fatalf("list case rows: %v", err)
	}
	put(t, r, "sh", spec{describe: "unit: file", list: "tests/a.sh|file|a\n"})
	runners(t, r, "runners:\n  - name: sh\n    zero_tests: skip\n")
	if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "zero_tests is only valid with accounting: cases") {
		t.Fatalf("zero_tests: %v", err)
	}
}

// G3: zero expected cases is the runner's policy — skip (reason zero_tests,
// never a cause, never a pass) or error — whatever the adapter's own exit.
func TestCasesZeroTestsPolicy(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := scenRepo(t, []scen{
		{name: "zskip", describe: casesDescribe, list: "tests/z.py|file|z\n", run: "exit 0", entry: "    zero_tests: skip\n"},
		{name: "zskip2", describe: casesDescribe, list: "tests/z2.py|file|z\n", run: "exit 2", entry: "    zero_tests: skip\n"},
		{name: "zerr", describe: casesDescribe, list: "tests/e.py|file|e\n", run: "exit 0"},
		{name: "ok", describe: casesDescribe, list: "tests/p.py|file|p\ntests/p.py|case|a\n", run: "crow tests/p.py a pass"},
	})
	for i, c := range []struct {
		ids    []string
		status string
		exit   int
	}{
		{[]string{"tests/z.py"}, StatusSkip, 2},
		{[]string{"tests/z2.py"}, StatusSkip, 2},
		{[]string{"tests/z.py", "tests/p.py"}, StatusSkip, 0},
		{[]string{"tests/e.py"}, StatusError, 1},
	} {
		rep := runIDs(t, r, fmt.Sprintf("zero-%d", i), c.ids...)
		z := resultOf(t, rep, c.ids[0])
		for _, rec := range rep.Invocations {
			if rec.Cause != "" {
				t.Errorf("%v: cause %+v", c.ids, rec)
			}
		}
		if z.Status != c.status || z.Reason != PolicyZeroTests || z.Cases == nil || z.Cases.Expected != 0 || rep.Exit() != c.exit {
			t.Errorf("%v: %+v exit %d", c.ids, z, rep.Exit())
		}
	}
}

// G2 for malformed evidence: a line that still names a unit invalidates its
// evidence whatever else it reported; a line naming no unit invalidates every
// unit of the invocation; a row naming a foreign unit is the invocation's
// protocol error and leaves the unit's own evidence alone.
func TestCasesMalformedEvidence(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	two := "tests/u.py|file|u\ntests/u.py|case|a\ntests/u.py|case|b\ntests/v.py|file|v\ntests/v.py|case|a\n"
	r := scenRepo(t, []scen{{name: "py", describe: casesDescribe + "\ntimeouts: batch", list: two, entry: "    batch_timeout_s: 30\n",
		run: `crow tests/u.py a pass; crow tests/u.py b pass; crow tests/v.py a pass; printf '{"unit":"tests/u.py","case":"a","status":"bogus","duration_ms":1}\n' >> "$C"`}})
	rep := runIDs(t, r, "mal-named", "tests/u.py", "tests/v.py")
	if u := resultOf(t, rep, "tests/u.py"); u.Status != StatusError || u.Reason != "malformed_case" || u.Cases.Passed != 2 {
		t.Fatalf("named: %+v", u)
	}
	if v := resultOf(t, rep, "tests/v.py"); v.Status != StatusPass {
		t.Fatalf("the other unit: %+v", v)
	}
	if rec := rep.Invocations[0]; rec.Cause != CauseReconciliation || rec.CauseDetail != "cases:malformed:line 4" || rep.Exit() != 1 {
		t.Fatalf("named record: %+v", rec)
	}
	put(t, r, "py", spec{describe: casesDescribe + "\ntimeouts: batch", list: two,
		run: `crow tests/u.py a pass; crow tests/u.py b pass; crow tests/v.py a pass; printf '{"case":' >> "$C"`})
	rep = runIDs(t, r, "mal-anon", "tests/u.py", "tests/v.py")
	for _, id := range []string{"tests/u.py", "tests/v.py"} {
		if x := resultOf(t, rep, id); x.Status != StatusError || x.Reason != "malformed_case" {
			t.Fatalf("unattributable %s: %+v", id, x)
		}
	}
	put(t, r, "py", spec{describe: casesDescribe + "\ntimeouts: batch", list: two,
		run: `crow tests/u.py a pass; crow tests/u.py b pass; crow tests/v.py a pass; crow tests/zz.py a pass`})
	rep = runIDs(t, r, "mal-foreign", "tests/u.py", "tests/v.py")
	if u := resultOf(t, rep, "tests/u.py"); u.Status != StatusPass || rep.Invocations[0].CauseDetail != "cases:unregistered_id:tests/zz.py" {
		t.Fatalf("foreign: %+v %+v", u, rep.Invocations[0])
	}
}

// A clean refusal stays a refusal (nothing is derived before the end is
// classified); exit 75 with case evidence is an exit_mismatch whose units are
// missing, never derived.
func TestCasesRefusal(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := scenRepo(t, []scen{
		{name: "ref", describe: casesDescribe, list: "tests/r.py|file|r\ntests/r.py|case|a\n", run: "exit 75"},
		{name: "refrow", describe: casesDescribe, list: "tests/q.py|file|q\ntests/q.py|case|a\n", run: "crow tests/q.py a pass; exit 75"},
	})
	rep := runIDs(t, r, "refused", "tests/r.py")
	if rec := rep.Invocations[0]; !rec.Refused || rec.Cause != "" || resultOf(t, rep, "tests/r.py").Status != StatusRefused || rep.Exit() != 75 {
		t.Fatalf("clean refusal: %+v exit %d", rec, rep.Exit())
	}
	rep = runIDs(t, r, "refused-row", "tests/q.py")
	if rec := rep.Invocations[0]; rec.Refused || rec.CauseDetail != "exit_mismatch" || resultOf(t, rep, "tests/q.py").Status != StatusMissing || rep.Exit() != 1 {
		t.Fatalf("refusal with evidence: %+v %+v exit %d", rec, rep.Results, rep.Exit())
	}
}

// A row repeating a member is ambiguous — JSON decoding would keep the last
// value — so it is malformed evidence, never the value that happened to win.
// The same holds for a member spelled in another case (`Status`).
func TestCasesRepeatedMember(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := scenRepo(t, []scen{
		{name: "dup", describe: casesDescribe, list: "tests/d.py|file|d\ntests/d.py|case|a\n",
			run: `printf '{"unit":"tests/d.py","case":"a","status":"fail","status":"pass","duration_ms":1}\n' > "$C"`},
		{name: "fold", describe: casesDescribe, list: "tests/f.py|file|f\ntests/f.py|case|a\n",
			run: `printf '{"unit":"tests/f.py","case":"a","status":"fail","Status":"pass","duration_ms":1}\n' > "$C"`},
		{name: "twounits", describe: casesDescribe + "\ntimeouts: batch", list: "tests/u.py|file|u\ntests/u.py|case|a\ntests/v.py|file|v\ntests/v.py|case|a\n", entry: "    batch_timeout_s: 30\n",
			run: `crow tests/u.py a pass; crow tests/v.py a pass; printf '{"unit":"tests/u.py","unit":"tests/v.py","case":"a","status":"fail","duration_ms":1}\n' >> "$C"`},
		{name: "rows", describe: "unit: file", list: "tests/r.sh|file|r\n",
			run: `printf '{"id":"tests/r.sh","status":"fail","status":"pass","duration_ms":1}\n' > "$R"`},
	})
	for _, id := range []string{"tests/d.py", "tests/f.py"} {
		rep := runIDs(t, r, "dupmember-"+id[6:7], id)
		if x := resultOf(t, rep, id); x.Status != StatusError || x.Reason != "malformed_case,incomplete" || rep.Invocations[0].CauseDetail != "cases:malformed:line 1" {
			t.Errorf("%s: %+v %+v", id, x, rep.Invocations[0])
		}
	}
	// A row naming two units is attributable to neither: every unit is tainted.
	rep := runIDs(t, r, "dupmember-units", "tests/u.py", "tests/v.py")
	for _, id := range []string{"tests/u.py", "tests/v.py"} {
		if x := resultOf(t, rep, id); x.Status != StatusError || x.Reason != "malformed_case" {
			t.Errorf("%s: %+v", id, x)
		}
	}
	// results.jsonl (any accounting): the repeated status is that unit's
	// malformed row, never a pass.
	rep = runIDs(t, r, "dupmember-rows", "tests/r.sh")
	if x := resultOf(t, rep, "tests/r.sh"); x.Status != StatusError || x.Message != "protocol:malformed" {
		t.Errorf("results.jsonl: %+v %+v", x, rep.Invocations[0])
	}
}

// Invalid UTF-8 is malformed, never repaired into a match: JSON decoding
// would turn the raw byte 0xff into U+FFFD, the very identity this unit
// expects. The same holds for results.jsonl.
func TestCasesInvalidUTF8(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := scenRepo(t, []scen{
		{name: "raw", describe: casesDescribe, list: "tests/x.py|file|x\ntests/x.py|case|a\uFFFD\n",
			run: `printf '{"unit":"tests/x.py","case":"a\xff","status":"pass","duration_ms":1}\n' > "$C"`},
		{name: "rawrow", describe: "unit: file", list: "tests/r.sh|file|r\n",
			run: `printf '{"id":"tests/r.sh","status":"pass","duration_ms":1,"message":"\xff"}\n' > "$R"`},
		// Unpaired surrogate escapes are valid UTF-8 bytes that decoding
		// repairs into U+FFFD all the same.
		{name: "surr", describe: casesDescribe, list: "tests/s.py|file|s\ntests/s.py|case|a\uFFFD\n",
			run: `printf '%s\n' '{"unit":"tests/s.py","case":"a\ud800","status":"pass","duration_ms":1}' > "$C"`},
		{name: "surrrow", describe: "unit: file", list: "tests/q.sh|file|q\n",
			run: `printf '%s\n' '{"id":"tests/q.sh","status":"pass","duration_ms":1,"message":"\udfff"}' > "$R"`},
	})
	rep := runIDs(t, r, "utf8-cases", "tests/x.py")
	if x := resultOf(t, rep, "tests/x.py"); x.Status != StatusError || x.Reason != "malformed_case,incomplete" || rep.Invocations[0].CauseDetail != "cases:malformed:line 1" {
		t.Errorf("cases.jsonl: %+v %+v", x, rep.Invocations[0])
	}
	rep = runIDs(t, r, "utf8-rows", "tests/r.sh")
	if x := resultOf(t, rep, "tests/r.sh"); x.Status != StatusError || x.Message != "protocol:malformed" {
		t.Errorf("results.jsonl: %+v %+v", x, rep.Invocations[0])
	}
	rep = runIDs(t, r, "surrogate-cases", "tests/s.py")
	if x := resultOf(t, rep, "tests/s.py"); x.Status != StatusError || x.Reason != "malformed_case,incomplete" || rep.Invocations[0].CauseDetail != "cases:malformed:line 1" {
		t.Errorf("cases.jsonl surrogate: %+v %+v", x, rep.Invocations[0])
	}
	rep = runIDs(t, r, "surrogate-rows", "tests/q.sh")
	if x := resultOf(t, rep, "tests/q.sh"); x.Status != StatusError || x.Message != "protocol:malformed" {
		t.Errorf("results.jsonl surrogate: %+v %+v", x, rep.Invocations[0])
	}
}

// Under cases the adapter's exit is checked against its own case verdicts.
func TestCasesExitConsistency(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := scenRepo(t, []scen{
		{name: "f0", describe: casesDescribe, list: "tests/a.py|file|a\ntests/a.py|case|x\n", run: "crow tests/a.py x fail; exit 0"},
		{name: "p1", describe: casesDescribe, list: "tests/b.py|file|b\ntests/b.py|case|x\n", run: "crow tests/b.py x pass; exit 1"},
		{name: "f1", describe: casesDescribe, list: "tests/c.py|file|c\ntests/c.py|case|x\n", run: "crow tests/c.py x fail; exit 1"},
	})
	for id, want := range map[string][2]string{
		"tests/a.py": {StatusFail, "exit_mismatch"},
		"tests/b.py": {StatusPass, "exit_mismatch"},
		"tests/c.py": {StatusFail, ""},
	} {
		rep := runIDs(t, r, "exit-"+id[6:7], id)
		if x := resultOf(t, rep, id); x.Status != want[0] || rep.Invocations[0].CauseDetail != want[1] {
			t.Errorf("%s: %+v %+v", id, x, rep.Invocations[0])
		}
	}
}

// G6 through Run: a report the invocation did not produce taints every unit
// rejected_report, which outranks the zero-test policy; with no report at all
// that policy stands.
func TestCasesStaleReport(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	st := stateOfRepoless(t)
	r := scenRepo(t, []scen{
		{name: "old", describe: casesDescribe, list: "tests/o.py|file|o\ntests/o.py|case|a\n", run: "crow tests/o.py a pass; touch -d '2001-01-01T12:00:00Z' \"$C\""},
		{name: "link", describe: casesDescribe, list: "tests/l.py|file|l\ntests/l.py|case|a\n",
			run: "printf '{\"unit\":\"tests/l.py\",\"case\":\"a\",\"status\":\"pass\",\"duration_ms\":1}\\n' > " + st + "/real.jsonl; ln -s " + st + "/real.jsonl \"$C\""},
		{name: "zold", describe: casesDescribe, list: "tests/z.py|file|z\n", run: ": > \"$C\"; touch -d '2001-01-01T12:00:00Z' \"$C\"", entry: "    zero_tests: skip\n"},
		{name: "znone", describe: casesDescribe, list: "tests/n.py|file|n\n", run: "exit 0", entry: "    zero_tests: skip\n"},
		{name: "swap", describe: casesDescribe, list: "tests/s.py|file|s\ntests/s.py|case|a\n",
			run: "mkdir -p " + st + "/elsewhere; printf '{\"unit\":\"tests/s.py\",\"case\":\"a\",\"status\":\"pass\",\"duration_ms\":1}\\n' > " + st + "/elsewhere/cases.jsonl; rmdir \"$AIT_TESTMAP_REPORT_DIR\"; ln -s " + st + "/elsewhere \"$AIT_TESTMAP_REPORT_DIR\""},
	})
	// The refused file's rows were never read, so an expected identity is
	// also missing (incomplete); a zero-expected unit has only the rejection.
	for id, want := range map[string][2]string{
		"tests/o.py": {"rejected_report,incomplete", "report:cases.jsonl:stale: modified 2001-01-01T12:00:00Z"},
		"tests/l.py": {"rejected_report,incomplete", "report:cases.jsonl:a symbolic link"},
		"tests/z.py": {"rejected_report", "report:cases.jsonl:stale: modified 2001-01-01T12:00:00Z"},
		// The engine's report directory replaced by a link to fresh evidence
		// elsewhere: refused, however fresh that evidence is.
		"tests/s.py": {"rejected_report,incomplete", "report:cases.jsonl:the report directory was replaced"},
	} {
		rep := runIDs(t, r, "stale-"+id[6:7], id)
		x, rec := resultOf(t, rep, id), rep.Invocations[0]
		if x.Status != StatusError || x.Reason != want[0] || rec.Cause != CauseReconciliation || !strings.HasPrefix(rec.CauseDetail, want[1]) || rep.Exit() != 1 {
			t.Errorf("%s: %+v %+v exit %d", id, x, rec, rep.Exit())
		}
	}
	rep := runIDs(t, r, "stale-none", "tests/n.py")
	if x := resultOf(t, rep, "tests/n.py"); x.Status != StatusSkip || x.Reason != PolicyZeroTests || rep.Invocations[0].Cause != "" || rep.Exit() != 2 {
		t.Fatalf("no report: %+v %+v", x, rep.Invocations[0])
	}
}

// After an engine kill: written evidence that is invalid stays an error, a
// unit that provably finished keeps its status, and unfinished work — a
// zero-expected unit included — is attributed by AttributeKill.
func TestCasesKilledAttribution(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	kill := "    timeout_s: 1\n"
	r := scenRepo(t, []scen{
		{name: "done", describe: casesDescribe, list: "tests/d.py|file|d\ntests/d.py|case|a\ntests/d.py|case|b\n", run: "crow tests/d.py a pass; crow tests/d.py b pass; sleep 30", entry: kill},
		{name: "half", describe: casesDescribe, list: "tests/h.py|file|h\ntests/h.py|case|a\ntests/h.py|case|b\n", run: "crow tests/h.py a pass; sleep 30", entry: kill},
		{name: "zero", describe: casesDescribe, list: "tests/z.py|file|z\n", run: "sleep 30", entry: kill + "    zero_tests: skip\n"},
		{name: "mal", describe: casesDescribe, list: "tests/m.py|file|m\ntests/m.py|case|a\ntests/m.py|case|b\n",
			run: `crow tests/m.py a pass; crow tests/m.py b pass; printf '{"unit":"tests/m.py","status":"bogus"}\n' >> "$C"; sleep 30`, entry: kill},
		{name: "batch", describe: casesDescribe + "\ntimeouts: batch", list: "tests/b1.py|file|1\ntests/b1.py|case|a\ntests/b2.py|file|2\ntests/b2.py|case|a\n",
			run: "start tests/b1.py; sleep 30", entry: "    batch_timeout_s: 1\n"},
	})
	for id, want := range map[string][2]string{
		"tests/d.py": {StatusPass, ""},
		"tests/h.py": {StatusTimeout, ""},
		"tests/z.py": {StatusTimeout, ""},
		"tests/m.py": {StatusError, ReasonMalformedCase},
	} {
		rep := runIDs(t, r, "kill-"+id[6:7], id)
		x, rec := resultOf(t, rep, id), rep.Invocations[0]
		if x.Status != want[0] || x.Reason != want[1] || !rec.Killed || rec.TimedOut != BoundUnit {
			t.Errorf("%s: %+v %+v", id, x, rec)
		}
		if wantCause := map[bool]string{true: CauseReconciliation, false: CauseTimeout}[want[1] != ""]; rec.Cause != wantCause {
			t.Errorf("%s: cause %q, want %q", id, rec.Cause, wantCause)
		}
	}
	rep := runIDs(t, r, "kill-batch", "tests/b1.py", "tests/b2.py")
	if got := statuses(rep); got["tests/b1.py"] != StatusTimeout || got["tests/b2.py"] != StatusNotStarted || rep.Invocations[0].TimedOut != BoundBatch {
		t.Fatalf("batch: %v %+v", got, rep.Invocations[0])
	}
}

// Every invocation gets its own report directory, created empty, named in
// the manifest and the record.
func TestReportDirFreshPerInvocation(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	st := stateOfRepoless(t)
	r := scenRepo(t, []scen{{name: "py", describe: casesDescribe, list: "tests/a.py|file|a\ntests/a.py|case|x\ntests/b.py|file|b\ntests/b.py|case|x\n",
		run: "ls -A \"$AIT_TESTMAP_REPORT_DIR\" >> " + st + "/ls; echo \"$AIT_TESTMAP_REPORT_DIR\" >> " + st + "/dirs; for i in $IDS; do crow $i x pass; done"}})
	rep := runIDs(t, r, "dirs", "tests/a.py", "tests/b.py")
	if len(rep.Invocations) != 2 || rep.Invocations[0].ReportDir == rep.Invocations[1].ReportDir || rep.Exit() != 0 {
		t.Fatalf("%+v", rep.Invocations)
	}
	ls, _ := os.ReadFile(st + "/ls")
	dirs, _ := os.ReadFile(st + "/dirs")
	if string(ls) != "" || string(dirs) != rep.Invocations[0].ReportDir+"\n"+rep.Invocations[1].ReportDir+"\n" {
		t.Fatalf("ls %q dirs %q", ls, dirs)
	}
	for _, rec := range rep.Invocations {
		if filepath.Base(rec.ReportDir) != "report" {
			t.Fatalf("report dir %s", rec.ReportDir)
		}
	}
}

// RUN_ACCOUNTING's numbers: the selected units by class, and the subsumed
// units the selected suite was to cover that no child row accounts for.
func TestRunAccounting(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	withReportingContract(t, "test-children")
	r := scenRepo(t, []scen{
		{name: "py", describe: casesDescribe, list: "tests/p.py|file|p\ntests/p.py|case|a\n", run: "crow tests/p.py a pass"},
		{name: "agg", describe: "unit: suite\naccounting: aggregate", list: "agg.cfg|suite|g\n", run: "row agg.cfg pass"},
		{name: "sh", describe: "unit: file", list: "tests/a.sh|file|a\ntests/b.sh|file|b\n", run: "row tests/a.sh pass", entry: "    subsumed_by: full\n"},
		{name: "full", describe: "unit: suite\nfull: true\nchildren: test-children", list: "suite.cfg|suite|s\n", run: "row suite.cfg pass; row tests/a.sh pass 1 suite.cfg"},
	})
	rep := runAll(t, r)
	if want := (RunAccounting{Selected: 3, Cases: 1, Unit: 1, Aggregate: 1, Unaccounted: 1}); rep.Accounting != want || !slices.Equal(rep.DiscoveryCandidates, []string{"agg", "sh", "full"}) {
		t.Fatalf("accounting %+v candidates %v", rep.Accounting, rep.DiscoveryCandidates)
	}
	// Explicit ids: no suite selected, nothing to account for beyond them.
	rep = runIDs(t, r, "acct-ids", "tests/a.sh")
	if want := (RunAccounting{Selected: 1, Unit: 1}); rep.Accounting != want {
		t.Fatalf("explicit %+v", rep.Accounting)
	}
}

// G7 through Run: child rows from a full suite without a reporting contract
// are refused, never read as test results.
func TestChildRowsNeedContract(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := scenRepo(t, []scen{
		{name: "sh", describe: "unit: file", list: "tests/a.sh|file|a\n", run: "row tests/a.sh pass", entry: "    subsumed_by: full\n"},
		{name: "full", describe: "unit: suite\nfull: true", list: "suite.cfg|suite|s\n", run: "row suite.cfg pass; row tests/a.sh pass 1 suite.cfg"},
	})
	rep := runAll(t, r)
	if rec := rep.Invocations[0]; rec.Cause != CauseReconciliation || !slices.Equal(rec.ProtocolErrors, []string{"invalid_child:tests/a.sh"}) || rep.Accounting.Unaccounted != 1 {
		t.Fatalf("%+v %+v", rec, rep.Accounting)
	}
}
