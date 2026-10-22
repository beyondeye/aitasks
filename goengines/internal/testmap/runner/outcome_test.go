package runner

import (
	"errors"
	"reflect"
	"slices"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

func ids(ss ...string) []registry.ID {
	var out []registry.ID
	for _, s := range ss {
		out = append(out, registry.MustParseID(s))
	}
	return out
}

func set(ss ...string) map[registry.ID]bool {
	m := map[registry.ID]bool{}
	for _, id := range ids(ss...) {
		m[id] = true
	}
	return m
}

func TestTimeoutDeadline(t *testing.T) {
	one := []Unit{{TimeoutS: 2}}
	for name, tc := range map[string]struct {
		mode        string
		units       []Unit
		batch, maxS float64
		want        time.Duration
		bound       string
	}{
		"per_unit":        {TimeoutsPerUnit, one, 0, 60, 60 * time.Second, BoundInvocationMax},
		"batch":           {TimeoutsBatch, one, 10, 60, 10 * time.Second, BoundBatch},
		"batch capped":    {TimeoutsBatch, one, 90, 60, 60 * time.Second, BoundInvocationMax},
		"none":            {TimeoutsNone, one, 0, 60, 2 * time.Second, BoundUnit},
		"none capped":     {TimeoutsNone, []Unit{{TimeoutS: 90}}, 0, 60, 60 * time.Second, BoundInvocationMax},
		"none fractional": {TimeoutsNone, []Unit{{TimeoutS: 0.25}}, 0, 60, 250 * time.Millisecond, BoundUnit},
	} {
		d, b, err := Deadline(tc.mode, tc.units, tc.batch, tc.maxS)
		if err != nil || d != tc.want || b != tc.bound {
			t.Errorf("%s: %v %q %v", name, d, b, err)
		}
	}
	if _, _, err := Deadline(TimeoutsNone, []Unit{{}, {}}, 0, 60); err == nil {
		t.Error("a two-unit none invocation got a deadline")
	}
}

func TestAttributeKill(t *testing.T) {
	exp := ids("a", "b", "c")
	for name, tc := range map[string]struct {
		mode              string
		started, reported map[registry.ID]bool
		want              map[string]string
	}{
		"per_unit":             {TimeoutsPerUnit, set("a", "b"), set("a"), map[string]string{"b": StatusTimeout, "c": StatusNotStarted}},
		"batch with starts":    {TimeoutsBatch, set("a"), set(), map[string]string{"a": StatusTimeout, "b": StatusNotStarted, "c": StatusNotStarted}},
		"batch without starts": {TimeoutsBatch, set(), set("a"), map[string]string{"b": StatusBatchTimeout, "c": StatusBatchTimeout}},
		"none (singleton)":     {TimeoutsNone, set(), set(), map[string]string{"a": StatusTimeout, "b": StatusTimeout, "c": StatusTimeout}},
	} {
		got := map[string]string{}
		for id, s := range AttributeKill(tc.mode, exp, tc.started, tc.reported) {
			got[id.String()] = s
		}
		if !reflect.DeepEqual(got, tc.want) {
			t.Errorf("%s: %v want %v", name, got, tc.want)
		}
	}
}

func TestCheckEnforced(t *testing.T) {
	if err := CheckEnforced(TimeoutsPerUnit, 1, StatusPass, 3000); err != nil { // 1 s + 2 s slack
		t.Error(err)
	}
	if err := CheckEnforced(TimeoutsPerUnit, 1, StatusPass, 3001); err == nil {
		t.Error("over the bound passed")
	}
	if err := CheckEnforced(TimeoutsPerUnit, 1, StatusTimeout, 99999); err != nil {
		t.Error("a reported timeout is the bound enforced")
	}
	if err := CheckEnforced(TimeoutsBatch, 1, StatusPass, 99999); err != nil {
		t.Error("batch mode makes no per-unit claim")
	}
	// A duration that would overflow time.Duration never wraps into a pass.
	if err := CheckEnforced(TimeoutsPerUnit, 1, StatusPass, 9223372036855); err == nil {
		t.Error("an overflowing duration passed the bound")
	}
}

// A malformed row that names an expected id as its own is that unit's
// error — it invalidates an earlier valid result — while text naming no
// expected id stays an invocation-level error. Out-of-range durations are
// malformed.
func TestValidateRowsMalformedAttribution(t *testing.T) {
	for name, bad := range map[string]string{
		"bad status":      `{"id":"a","status":"bogus","duration_ms":1}`,
		"negative ms":     `{"id":"a","status":"pass","duration_ms":-1}`,
		"overflowing ms":  `{"id":"a","status":"pass","duration_ms":9223372036855}`,
		"unknown field":   `{"id":"a","status":"pass","duration_ms":1,"retries":2}`,
		"bad start shape": `{"id":"a","event":"start","duration_ms":1}`,
		// "" and null parents are top-level for decodeRow, so for ownID too.
		"empty parent": `{"id":"a","status":"bogus","duration_ms":1,"parent":""}`,
		"null parent":  `{"id":"a","status":"bogus","duration_ms":1,"parent":null}`,
	} {
		v := ValidateRows([]byte(`{"id":"a","status":"pass","duration_ms":1}`+"\n"+bad+"\n"), false, ctxFor(TimeoutsBatch, false, "a", "b"))
		a := registry.MustParseID("a")
		if v.PerID[a] != "malformed" || v.Reported[a] || !slices.Equal(v.Errors, []string{"malformed:a"}) {
			t.Errorf("%s: perID %v reported %v errors %v", name, v.PerID, v.Reported, v.Errors)
		}
		vd := decide(EndState{Exit: 0}, v, ids("a", "b"), TimeoutsBatch)
		if vd.Results[0].Status != StatusError {
			t.Errorf("%s: a is %s, want error", name, vd.Results[0].Status)
		}
	}
	for name, bad := range map[string]string{
		"foreign id":     `{"id":"zzz","status":"bogus","duration_ms":1}`,
		"child of a":     `{"id":"a","status":"bogus","duration_ms":1,"parent":"b"}`,
		"not json":       `{"id":"a",`,
		"numeric id":     `{"id":7,"status":"pass","duration_ms":1}`,
		"numeric parent": `{"id":"a","status":"bogus","duration_ms":1,"parent":5}`,
	} {
		v := ValidateRows([]byte(`{"id":"a","status":"pass","duration_ms":1}`+"\n"+bad+"\n"), false, ctxFor(TimeoutsBatch, false, "a", "b"))
		if !v.Reported[registry.MustParseID("a")] || !slices.Equal(v.Errors, []string{"malformed:line 2"}) {
			t.Errorf("%s: reported %v errors %v", name, v.Reported, v.Errors)
		}
	}
}

func ctxFor(mode string, full bool, expected ...string) rowContext {
	return rowContext{
		Expected: ids(expected...), TimeoutS: map[registry.ID]float64{},
		Registered: func(id registry.ID) bool { return id.Path != "foreign" && id.Path != "zzz" }, Children: full, Mode: mode,
	}
}

// Row validation runs the same on a normal exit and after a kill; the only
// kill-path exception is an unterminated final line.
func TestValidateRows(t *testing.T) {
	data := `{"id":"a","status":"pass","duration_ms":3}
{"id":"a","status":"pass","duration_ms":3}
{"id":"b","status":"pass","duration_ms":1}
{"id":"zzz","status":"pass","duration_ms":1}
{"id":"other","status":"pass","duration_ms":1}
garbage
{"id":"c","status":"fail","duration_ms":1,"bogus":1}
{"id":"kid","status":"pass","duration_ms":1,"parent":"b"}
{"id":"c","status":"timeout","duration_ms":1}
{"id":"c","event":"start","status":"pass"}
{"id":"c","status":"pa`
	for _, killed := range []bool{false, true} {
		v := ValidateRows([]byte(data), killed, ctxFor(TimeoutsBatch, false, "a", "b", "c"))
		// Lines 7 and 10 are malformed rows that still name expected id c:
		// they are c's protocol errors (TestValidateRowsMalformedAttribution).
		want := []string{"duplicate:a", "unregistered_id:zzz", "unexpected_id:other", "malformed:line 6", "malformed:c", "invalid_child:kid", "timeout_not_per_unit:c", "malformed:c"}
		if !killed {
			want = append(want, "malformed:line 11")
		}
		if !slices.Equal(v.Errors, want) {
			t.Errorf("killed=%v errors\n%v\nwant\n%v", killed, v.Errors, want)
		}
		if v.PerID[registry.MustParseID("a")] != "duplicate" || v.PerID[registry.MustParseID("c")] != "malformed" {
			t.Errorf("perID %v", v.PerID)
		}
		if !reflect.DeepEqual(v.Reported, set("b")) || len(v.Rows) != 1 {
			t.Errorf("reported %v rows %v", v.Reported, v.Rows)
		}
	}
	// per_unit: a result without its start, a start after the result, and a
	// bound not enforced.
	c := ctxFor(TimeoutsPerUnit, false, "a", "b", "c")
	c.TimeoutS = map[registry.ID]float64{registry.MustParseID("c"): 1}
	v := ValidateRows([]byte(`{"id":"a","status":"pass","duration_ms":1}
{"id":"b","event":"start"}
{"id":"b","status":"pass","duration_ms":1}
{"id":"b","event":"start"}
{"id":"c","event":"start"}
{"id":"c","status":"pass","duration_ms":5000}
`), false, c)
	if !slices.Equal(v.Errors, []string{"missing_start:a", "start_after_result:b", "timeout_not_enforced:c"}) || len(v.Reported) != 0 {
		t.Errorf("per_unit errors %v reported %v", v.Errors, v.Reported)
	}
	// Child rows: valid under a full runner, refused when unregistered.
	v = ValidateRows([]byte(`{"id":"s","status":"pass","duration_ms":9}
{"id":"kid","status":"fail","duration_ms":4,"parent":"s"}
{"id":"foreign","status":"pass","duration_ms":4,"parent":"s"}
`), false, ctxFor(TimeoutsNone, true, "s"))
	if !slices.Equal(v.Errors, []string{"unregistered_id:foreign"}) || len(v.Rows) != 2 || !v.Rows[1].Child {
		t.Errorf("children: %v %+v", v.Errors, v.Rows)
	}
	if e := ValidateRows([]byte("  \n"), false, ctxFor(TimeoutsNone, false, "a")); e.Emitted || len(e.Errors) != 0 {
		t.Errorf("whitespace only: %+v", e)
	}
}

// One case per row of the invocation outcome table: unit statuses, cause,
// timed_out, refused and protocol errors together.
func TestOutcomeTable(t *testing.T) {
	type want struct {
		status        map[string]string
		cause, detail string
		refused       bool
		timedOut      string
	}
	pass := `{"id":"a","status":"pass","duration_ms":1}` + "\n"
	fail := `{"id":"a","status":"fail","duration_ms":1}` + "\n"
	skip := `{"id":"b","status":"skip","duration_ms":1}` + "\n"
	for name, tc := range map[string]struct {
		end  EndState
		data string
		mode string
		want want
	}{
		"75 nothing emitted": {EndState{Exit: 75}, "", TimeoutsBatch, want{map[string]string{"a": StatusRefused, "b": StatusRefused}, "", "", true, ""}},
		"75 with valid rows": {EndState{Exit: 75}, pass, TimeoutsBatch, want{map[string]string{"a": StatusPass, "b": StatusMissing}, CauseReconciliation, "exit_mismatch", false, ""}},
		"75 only foreign id": {EndState{Exit: 75}, `{"id":"zzz","status":"pass","duration_ms":1}` + "\n", TimeoutsBatch,
			want{map[string]string{"a": StatusMissing, "b": StatusMissing}, CauseReconciliation, "exit_mismatch", false, ""}},
		"75 only malformed":        {EndState{Exit: 75}, "garbage\n", TimeoutsBatch, want{map[string]string{"a": StatusMissing, "b": StatusMissing}, CauseReconciliation, "exit_mismatch", false, ""}},
		"75 only unterminated":     {EndState{Exit: 75}, "garbage", TimeoutsBatch, want{map[string]string{"a": StatusMissing, "b": StatusMissing}, CauseReconciliation, "exit_mismatch", false, ""}},
		"0 pass + skip":            {EndState{Exit: 0}, pass + skip, TimeoutsBatch, want{map[string]string{"a": StatusPass, "b": StatusSkip}, "", "", false, ""}},
		"0 with a fail row":        {EndState{Exit: 0}, fail + skip, TimeoutsBatch, want{map[string]string{"a": StatusFail, "b": StatusSkip}, CauseReconciliation, "exit_mismatch", false, ""}},
		"0 with a gap":             {EndState{Exit: 0}, pass, TimeoutsBatch, want{map[string]string{"a": StatusPass, "b": StatusMissing}, CauseReconciliation, "missing", false, ""}},
		"1 with a fail row":        {EndState{Exit: 1}, fail + skip, TimeoutsBatch, want{map[string]string{"a": StatusFail, "b": StatusSkip}, "", "", false, ""}},
		"1 with a fail and a gap":  {EndState{Exit: 1}, fail, TimeoutsBatch, want{map[string]string{"a": StatusFail, "b": StatusMissing}, CauseReconciliation, "missing", false, ""}},
		"1 all pass":               {EndState{Exit: 1}, pass + skip, TimeoutsBatch, want{map[string]string{"a": StatusPass, "b": StatusSkip}, CauseReconciliation, "exit_mismatch", false, ""}},
		"0 no top-level rows":      {EndState{Exit: 0}, "", TimeoutsBatch, want{map[string]string{"a": StatusMissing, "b": StatusMissing}, CauseReconciliation, "zero_reported", false, ""}},
		"2 nothing":                {EndState{Exit: 2}, "", TimeoutsBatch, want{map[string]string{"a": StatusMissing, "b": StatusMissing}, CauseReconciliation, "zero_reported", false, ""}},
		"2 with rows":              {EndState{Exit: 2}, pass, TimeoutsBatch, want{map[string]string{"a": StatusPass, "b": StatusMissing}, CauseReconciliation, "exit_mismatch", false, ""}},
		"64":                       {EndState{Exit: 64}, "", TimeoutsBatch, want{map[string]string{"a": StatusMissing, "b": StatusMissing}, CauseMechanism, "runner_exit:64", false, ""}},
		"out of contract":          {EndState{Exit: 5}, pass, TimeoutsBatch, want{map[string]string{"a": StatusPass, "b": StatusMissing}, CauseMechanism, "runner_exit:5", false, ""}},
		"killed, batch, no starts": {EndState{Exit: -1, Killed: true, Bound: BoundBatch}, pass, TimeoutsBatch, want{map[string]string{"a": StatusPass, "b": StatusBatchTimeout}, CauseTimeout, BoundBatch, false, BoundBatch}},
		"killed + protocol error": {EndState{Exit: -1, Killed: true, Bound: BoundBatch}, pass + pass, TimeoutsBatch,
			want{map[string]string{"a": StatusError, "b": StatusBatchTimeout}, CauseReconciliation, "duplicate:a", false, BoundBatch}},
		"start failure":       {EndState{Exit: -1, StartErr: errors.New("enoent")}, "", TimeoutsBatch, want{map[string]string{"a": StatusNotStarted, "b": StatusNotStarted}, CauseMechanism, "runner_start:enoent", false, ""}},
		"overflow":            {EndState{Exit: -1, Overflow: true}, "", TimeoutsBatch, want{map[string]string{"a": StatusMissing, "b": StatusMissing}, CauseMechanism, "runner_output_overflow", false, ""}},
		"sweep failed on 75":  {EndState{Exit: 75, Sweep: &cleanupError{Detail: "cleanup_incomplete:42"}}, "", TimeoutsBatch, want{map[string]string{"a": StatusMissing, "b": StatusMissing}, CauseMechanism, "cleanup_incomplete:42", false, ""}},
		"sweep failed + kill": {EndState{Exit: -1, Killed: true, Bound: BoundBatch, Sweep: &cleanupError{Detail: "cleanup_unverified:x"}}, "", TimeoutsBatch, want{map[string]string{"a": StatusBatchTimeout, "b": StatusBatchTimeout}, CauseMechanism, "cleanup_unverified:x", false, BoundBatch}},
	} {
		exp := ids("a", "b")
		v := ValidateRows([]byte(tc.data), tc.end.Killed, ctxFor(tc.mode, false, "a", "b"))
		vd := decide(tc.end, v, exp, tc.mode)
		got := map[string]string{}
		for _, r := range vd.Results {
			got[r.ID.String()] = r.Status
		}
		if !reflect.DeepEqual(got, tc.want.status) || vd.Cause != tc.want.cause || vd.CauseDetail != tc.want.detail || vd.Refused != tc.want.refused || vd.TimedOut != tc.want.timedOut {
			t.Errorf("%s:\n got  %v cause=%q/%q refused=%v timed_out=%q errors=%v\n want %v cause=%q/%q refused=%v timed_out=%q",
				name, got, vd.Cause, vd.CauseDetail, vd.Refused, vd.TimedOut, vd.ProtocolErrors, tc.want.status, tc.want.cause, tc.want.detail, tc.want.refused, tc.want.timedOut)
		}
		if vd.Refused && vd.Cause != "" {
			t.Errorf("%s: refused with a cause", name)
		}
	}
}
