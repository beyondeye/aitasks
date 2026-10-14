package runner

import (
	"strconv"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// Invocation causes. A cause on an invocation means none of its results may
// anchor evidence (M3.4).
const (
	CauseMechanism      = "mechanism"
	CauseReconciliation = "reconciliation"
	CauseTimeout        = "timeout"
)

// causeRank orders causes for the primary one: mechanism > reconciliation >
// timeout.
var causeRank = map[string]int{"": 0, CauseTimeout: 1, CauseReconciliation: 2, CauseMechanism: 3}

// EndState is how a runner's `run` ended, as the engine observed it.
type EndState struct {
	Exit     int    // the runner's exit status (-1: signalled or never started)
	Killed   bool   // the engine's deadline fired and the engine killed it
	Bound    string // the bound the deadline represented (unit | batch | invocation_max)
	StartErr error  // the runner could not be started
	Overflow bool   // stdout exceeded its cap
	Sweep    error  // the session could not be proven empty
}

// Result is one unit result: a top-level row per manifest id (reported or
// synthesized), then the valid child rows.
type Result struct {
	ID         registry.ID `json:"id"`
	Status     string      `json:"status"`
	DurationMS int64       `json:"duration_ms"`
	Parent     registry.ID `json:"parent,omitzero"`
	Child      bool        `json:"child,omitempty"`
	Started    bool        `json:"started,omitempty"` // a valid start row was seen
	Message    string      `json:"message,omitempty"`
	Invocation int         `json:"invocation"`
}

// failing reports whether a status fails a run.
func failing(status string) bool { return status != StatusPass && status != StatusSkip }

// verdict is the outcome of one invocation.
type verdict struct {
	Results        []Result
	Cause          string
	CauseDetail    string
	Refused        bool
	TimedOut       string
	ProtocolErrors []string
}

// decide applies the invocation outcome table, in a fixed order:
//
//  1. protocol-invalid expected ids → error (never pass, never re-synthesized);
//  2. classify how the invocation ended — a sweep failure, a start failure or
//     an output overflow is mechanism; an engine kill is timeout; exit 75 is
//     a clean refusal only with nothing emitted and no protocol error; exits
//     0 / 1 / 2 are checked against the rows;
//  3. only then, synthesize the still-unreported valid expected ids
//     (AttributeKill after a kill, `refused` after a clean refusal,
//     `not_started` when the runner never started, else `missing`);
//  4. pick the primary cause by precedence, keeping every protocol error and
//     the timeout bound.
func decide(end EndState, v Validation, expected []registry.ID, mode string) verdict {
	var out verdict
	out.ProtocolErrors = v.Errors
	status := map[registry.ID]Result{}
	for _, r := range v.Rows {
		if !r.Child {
			status[r.ID] = Result{ID: r.ID, Status: r.Status, DurationMS: r.DurationMS, Message: r.Message}
		}
	}
	for id, detail := range v.PerID {
		status[id] = Result{ID: id, Status: StatusError, Message: "protocol:" + detail}
	}

	var cause, detail string
	set := func(c, d string) {
		if causeRank[c] > causeRank[cause] {
			cause, detail = c, d
		}
	}
	topRows, failRows := 0, false
	for _, r := range v.Rows {
		if !r.Child {
			topRows++
		}
		if failing(r.Status) {
			failRows = true
		}
	}
	unreported := func() bool {
		for _, id := range expected {
			if _, ok := status[id]; !ok {
				return true
			}
		}
		return false
	}()
	synth := StatusMissing
	switch {
	case end.StartErr != nil:
		set(CauseMechanism, "runner_start:"+oneLine(end.StartErr.Error()))
		synth = StatusNotStarted
	case end.Overflow:
		set(CauseMechanism, "runner_output_overflow")
	case end.Killed:
		set(CauseTimeout, end.Bound)
		out.TimedOut = end.Bound
		synth = ""
	case end.Exit == lineproto.ExitRefused:
		if !v.Emitted && len(v.Errors) == 0 {
			out.Refused = true
			synth = StatusRefused
		} else {
			set(CauseReconciliation, "exit_mismatch")
		}
	case end.Exit == lineproto.ExitOK || end.Exit == lineproto.ExitFail:
		switch {
		case topRows == 0:
			set(CauseReconciliation, "zero_reported")
		case end.Exit == lineproto.ExitOK && failRows, end.Exit == lineproto.ExitFail && !failRows:
			set(CauseReconciliation, "exit_mismatch")
		case unreported:
			set(CauseReconciliation, "missing")
		}
	case end.Exit == lineproto.ExitNothingRan:
		if len(v.Rows) == 0 {
			set(CauseReconciliation, "zero_reported")
		} else {
			set(CauseReconciliation, "exit_mismatch")
		}
	default:
		set(CauseMechanism, "runner_exit:"+strconv.Itoa(end.Exit))
	}
	if len(v.Errors) > 0 {
		set(CauseReconciliation, v.Errors[0])
	}
	if end.Sweep != nil {
		set(CauseMechanism, end.Sweep.Error())
		out.Refused = false
		if synth == StatusRefused {
			synth = StatusMissing
		}
	}

	var killStatus map[registry.ID]string
	if synth == "" {
		killStatus = AttributeKill(mode, expected, v.Started, v.Reported)
	}
	for _, id := range expected {
		r, ok := status[id]
		if !ok {
			s := synth
			if s == "" {
				s = killStatus[id]
			}
			r = Result{ID: id, Status: s}
		}
		r.Started = v.Started[id]
		out.Results = append(out.Results, r)
	}
	for _, r := range v.Rows {
		if r.Child {
			out.Results = append(out.Results, Result{ID: r.ID, Status: r.Status, DurationMS: r.DurationMS, Parent: r.Parent, Child: true, Message: r.Message})
		}
	}
	if out.Refused && cause != "" {
		out.Refused = false // a refusal never coexists with a cause
	}
	out.Cause, out.CauseDetail = cause, detail
	return out
}
