package runner

import (
	"fmt"
	"slices"
	"strings"
	"testing"
)

// [characterize_default_accounting_unchanged] The outcome of a `unit`
// accounting runner (the default), pinned as M3.1 shipped it, before the
// evidence contract (M3.2a) added `cases` accounting beside it. Every scenario
// runs through Run on its own, so each exit is observed unmasked. The
// expectations are literal: a change here is a change to M3.1's outcome table.
func TestCharacterizeUnitAccountingOutcomes(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	files := map[string]string{}
	scenarios := []struct {
		name, describe, list, run, entry string
	}{
		{"pass", "unit: file", "tests/pass.sh|file|p\n", "row tests/pass.sh pass 5", ""},
		{"fail", "unit: file", "tests/fail.sh|file|f\n", "row tests/fail.sh fail 6; exit 1", ""},
		{"missing", "unit: file\ntimeouts: batch", "tests/m1.sh|file|m1\ntests/m2.sh|file|m2\n", "row tests/m1.sh pass 3", "    batch_timeout_s: 20\n"},
		{"dup", "unit: file", "tests/dup.sh|file|d\n", "row tests/dup.sh pass 1; row tests/dup.sh pass 2", ""},
		{"malformed", "unit: file", "tests/mal.sh|file|m\n", `row tests/mal.sh pass 1; printf '{"id":"tests/mal.sh","status":"bogus","duration_ms":1}\n' >> "$R"`, ""},
		{"refuse", "unit: file", "tests/ref.sh|file|r\n", "exit 75", ""},
		{"refuserow", "unit: file", "tests/rr.sh|file|rr\n", "row tests/rr.sh pass 1; exit 75", ""},
		{"nothing", "unit: file", "tests/two.sh|file|t\n", "exit 2", ""},
		{"kill", "unit: file", "tests/kill.sh|file|k\n", "sleep 30", "    timeout_s: 1\n"},
	}
	var yaml strings.Builder
	yaml.WriteString("runners:\n")
	for _, s := range scenarios {
		for _, l := range strings.Split(strings.TrimSpace(s.list), "\n") {
			files[strings.Split(l, "|")[0]] = "#!/bin/sh\n"
		}
		fmt.Fprintf(&yaml, "  - name: %s\n    bind: [%s]\n    timeout_s: 10\n%s", s.name, binds(s.list), s.entry)
	}
	r := newRepo(t, files)
	for _, s := range scenarios {
		put(t, r, s.name, spec{describe: s.describe, list: s.list, run: s.run})
	}
	runners(t, r, strings.Replace(yaml.String(), "    timeout_s: 10\n    timeout_s: 1\n", "    timeout_s: 1\n", 1))
	commitAll(t, r)

	want := map[string]struct {
		results []string // id|status|message
		records []string // cause|detail|reported|started|refused|timed_out|protocol errors
		exit    int
	}{
		"pass":      {[]string{"tests/pass.sh|pass|"}, []string{"||1|0|false||"}, 0},
		"fail":      {[]string{"tests/fail.sh|fail|"}, []string{"||1|0|false||"}, 1},
		"missing":   {[]string{"tests/m1.sh|pass|", "tests/m2.sh|missing|"}, []string{"reconciliation|missing|1|0|false||"}, 1},
		"dup":       {[]string{"tests/dup.sh|error|protocol:duplicate"}, []string{"reconciliation|zero_reported|0|0|false||duplicate:tests/dup.sh"}, 1},
		"malformed": {[]string{"tests/mal.sh|error|protocol:malformed"}, []string{"reconciliation|zero_reported|0|0|false||malformed:tests/mal.sh"}, 1},
		"refuse":    {[]string{"tests/ref.sh|refused|"}, []string{"||0|0|true||"}, 75},
		"refuserow": {[]string{"tests/rr.sh|pass|"}, []string{"reconciliation|exit_mismatch|1|0|false||"}, 1},
		"nothing":   {[]string{"tests/two.sh|missing|"}, []string{"reconciliation|zero_reported|0|0|false||"}, 1},
		"kill":      {[]string{"tests/kill.sh|timeout|"}, []string{"timeout|unit|0|0|false|unit|"}, 1},
	}
	for _, s := range scenarios {
		var ids []string
		for _, l := range strings.Split(strings.TrimSpace(s.list), "\n") {
			ids = append(ids, strings.Split(l, "|")[0])
		}
		rep, err := Run(bg, r.Dir, Options{IDs: ids, RunID: "char-" + s.name})
		if err != nil {
			t.Fatalf("%s: %v", s.name, err)
		}
		var res, recs []string
		for _, x := range rep.Results {
			res = append(res, x.ID.String()+"|"+x.Status+"|"+x.Message)
		}
		for _, x := range rep.Invocations {
			recs = append(recs, fmt.Sprintf("%s|%s|%d|%d|%t|%s|%s", x.Cause, x.CauseDetail, x.UnitsReported, x.UnitsStarted, x.Refused, x.TimedOut, strings.Join(x.ProtocolErrors, ",")))
		}
		w := want[s.name]
		if !slices.Equal(res, w.results) || !slices.Equal(recs, w.records) || rep.Exit() != w.exit {
			t.Errorf("%s:\n results %q\n records %q\n exit %d\nwant %q %q %d", s.name, res, recs, rep.Exit(), w.results, w.records, w.exit)
		}
	}
}

// binds renders a scenario's listed paths as a YAML flow list.
func binds(list string) string {
	var out []string
	for _, l := range strings.Split(strings.TrimSpace(list), "\n") {
		out = append(out, "'"+strings.Split(l, "|")[0]+"'")
	}
	return strings.Join(out, ", ")
}
