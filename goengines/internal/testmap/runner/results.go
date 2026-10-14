package runner

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"strings"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// maxDurationMS bounds a reported duration (about 35 years). With
// results.jsonl capped at resultsMax, the sum of every row's duration stays
// far inside int64.
const maxDurationMS int64 = 1 << 40

// Row is one valid `results.jsonl` result row.
type Row struct {
	ID         registry.ID
	Status     string
	DurationMS int64
	Parent     registry.ID // zero for a top-level row
	Child      bool
	Message    string
}

// rawRow is the wire form: a start row `{"id","event":"start"}` or a result
// row `{"id","status","duration_ms","parent"?,"message"?}`.
type rawRow struct {
	ID         string `json:"id"`
	Event      string `json:"event,omitempty"`
	Status     string `json:"status,omitempty"`
	DurationMS *int64 `json:"duration_ms,omitempty"`
	Parent     string `json:"parent,omitempty"`
	Message    string `json:"message,omitempty"`
}

// rowContext is what validating an invocation's rows needs.
type rowContext struct {
	Expected   []registry.ID // the manifest's ids, in order
	expected   map[registry.ID]bool
	TimeoutS   map[registry.ID]float64
	Registered func(registry.ID) bool // an owned unit of some runner
	Full       bool                   // child rows allowed
	Mode       string                 // timeouts mode
}

// Validation is what row validation keeps.
type Validation struct {
	Rows     []Row                  // valid result rows (top-level and child), file order
	Started  map[registry.ID]bool   // expected ids with a valid start row
	Reported map[registry.ID]bool   // expected ids with a valid top-level result
	PerID    map[registry.ID]string // expected ids whose own rows broke the protocol → error
	Errors   []string               // every protocol error, `<detail>:<id or line N>`, in line order
	Emitted  bool                   // results.jsonl held any non-whitespace byte
}

// ValidateRows validates every complete line of results.jsonl — on a normal
// exit and after an engine kill alike. The one exception is narrow: after
// an engine kill (killed), a final line with no trailing newline is ignored
// as truncated. A malformed newline-terminated line is a protocol error on
// either path, and so is an unterminated final line after a normal exit that
// does not parse.
//
// An expected id whose own rows break the protocol (a duplicate result or
// start, a start after its result, a result without its start in per_unit
// mode, `timeout` from a non-per_unit runner, a bound not enforced) lands in
// PerID and is never treated as reported. Rows naming ids outside the
// manifest and invalid child rows are discarded and recorded.
func ValidateRows(data []byte, killed bool, c rowContext) Validation {
	v := Validation{Started: map[registry.ID]bool{}, Reported: map[registry.ID]bool{}, PerID: map[registry.ID]string{}}
	v.Emitted = len(bytes.TrimSpace(data)) > 0
	c.expected = map[registry.ID]bool{}
	for _, id := range c.Expected {
		c.expected[id] = true
	}
	text := string(data)
	lines := strings.Split(text, "\n")
	if strings.HasSuffix(text, "\n") || text == "" {
		lines = lines[:len(lines)-1]
	} else if killed {
		lines = lines[:len(lines)-1] // truncated by the kill
	}
	children := map[[2]registry.ID]bool{}
	perID := func(id registry.ID, detail string) {
		if _, ok := v.PerID[id]; !ok {
			v.PerID[id] = detail
		}
		v.Errors = append(v.Errors, detail+":"+id.String())
	}
	for i, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		at := fmt.Sprintf("line %d", i+1)
		r, err := decodeRow(line)
		if err != nil {
			// A malformed row that still names an expected id as its own
			// (top-level, no parent) is that unit's protocol error: it
			// invalidates any earlier result for it. Only text that names
			// no expected id stays an invocation-level error.
			if id, ok := ownID(line, c); ok {
				perID(id, "malformed")
				continue
			}
			v.Errors = append(v.Errors, "malformed:"+at)
			continue
		}
		id, err := registry.ParseID(r.ID)
		if err != nil {
			v.Errors = append(v.Errors, "malformed:"+at)
			continue
		}
		if r.Event == "start" {
			switch {
			case !c.expected[id]:
				v.Errors = append(v.Errors, foreign(c, id)+":"+id.String())
			case v.Reported[id] || v.PerID[id] != "":
				perID(id, "start_after_result")
			case v.Started[id]:
				perID(id, "duplicate_start")
			default:
				v.Started[id] = true
			}
			continue
		}
		if r.Status == StatusTimeout && c.Mode != TimeoutsPerUnit {
			if r.Parent == "" && c.expected[id] {
				perID(id, "timeout_not_per_unit")
			} else {
				v.Errors = append(v.Errors, "timeout_not_per_unit:"+id.String())
			}
			continue
		}
		if r.Parent != "" {
			parent, err := registry.ParseID(r.Parent)
			switch {
			case err != nil:
				v.Errors = append(v.Errors, "malformed:"+at)
			case !c.Full || !c.expected[parent]:
				v.Errors = append(v.Errors, "invalid_child:"+id.String())
			case !c.Registered(id):
				v.Errors = append(v.Errors, "unregistered_id:"+id.String())
			case children[[2]registry.ID{parent, id}]:
				v.Errors = append(v.Errors, "duplicate:"+id.String())
			default:
				children[[2]registry.ID{parent, id}] = true
				v.Rows = append(v.Rows, Row{ID: id, Status: r.Status, DurationMS: *r.DurationMS, Parent: parent, Child: true, Message: r.Message})
			}
			continue
		}
		switch {
		case !c.expected[id]:
			v.Errors = append(v.Errors, foreign(c, id)+":"+id.String())
		case v.Reported[id] || v.PerID[id] != "":
			perID(id, "duplicate")
		case c.Mode == TimeoutsPerUnit && !v.Started[id]:
			perID(id, "missing_start")
		default:
			if err := CheckEnforced(c.Mode, c.TimeoutS[id], r.Status, *r.DurationMS); err != nil {
				perID(id, "timeout_not_enforced")
				continue
			}
			v.Reported[id] = true
			v.Rows = append(v.Rows, Row{ID: id, Status: r.Status, DurationMS: *r.DurationMS, Message: r.Message})
		}
	}
	// An id whose rows broke the protocol is not reported, whatever came
	// before the break.
	kept := v.Rows[:0]
	for _, r := range v.Rows {
		if !r.Child && v.PerID[r.ID] != "" {
			delete(v.Reported, r.ID)
			continue
		}
		kept = append(kept, r)
	}
	v.Rows = kept
	return v
}

// ownID decodes just the identity of a malformed line — a JSON object with a
// string "id" that is top-level by the same rule decodeRow applies (a
// "parent" that is absent, null or "" decodes to an empty Parent, so the
// row is top-level) — and returns it when it is an expected id. A parent
// that names an id makes it a child row, never this unit's own; a parent of
// any other JSON type is unclassifiable and stays an invocation-level error.
func ownID(line string, c rowContext) (registry.ID, bool) {
	var probe struct {
		ID     *string         `json:"id"`
		Parent json.RawMessage `json:"parent"`
	}
	if json.Unmarshal([]byte(line), &probe) != nil || probe.ID == nil {
		return registry.ID{}, false
	}
	if len(probe.Parent) > 0 {
		var p any
		if json.Unmarshal(probe.Parent, &p) != nil {
			return registry.ID{}, false
		}
		if s, isStr := p.(string); p != nil && !(isStr && s == "") {
			return registry.ID{}, false
		}
	}
	id, err := registry.ParseID(*probe.ID)
	if err != nil || !c.expected[id] {
		return registry.ID{}, false
	}
	return id, true
}

// foreign classifies a top-level row for an id outside the manifest.
func foreign(c rowContext, id registry.ID) string {
	if c.Registered != nil && c.Registered(id) {
		return "unexpected_id"
	}
	return "unregistered_id"
}

// decodeRow decodes one strict JSON object and checks its form.
func decodeRow(line string) (rawRow, error) {
	var r rawRow
	dec := json.NewDecoder(strings.NewReader(line))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&r); err != nil {
		return r, err
	}
	if err := dec.Decode(&struct{}{}); err != io.EOF {
		return r, fmt.Errorf("trailing data")
	}
	switch r.Event {
	case "start":
		if r.Status != "" || r.DurationMS != nil || r.Parent != "" || r.Message != "" {
			return r, fmt.Errorf("a start row carries only id and event")
		}
	case "":
		switch r.Status {
		case StatusPass, StatusFail, StatusSkip, StatusError, StatusTimeout:
		default:
			return r, fmt.Errorf("status %q", r.Status)
		}
		if r.DurationMS == nil || *r.DurationMS < 0 || *r.DurationMS > maxDurationMS {
			return r, fmt.Errorf("duration_ms missing or outside [0, %d]", maxDurationMS)
		}
	default:
		return r, fmt.Errorf("event %q", r.Event)
	}
	return r, nil
}

// RunnerJSON is the optional `runner.json`.
type RunnerJSON struct {
	Overhead []struct {
		Group      string `json:"group"`
		OverheadMS int64  `json:"overhead_ms"`
	} `json:"overhead"`
}

// parseRunnerJSON decodes runner.json strictly; absent (nil data) is fine.
func parseRunnerJSON(data []byte) (*RunnerJSON, error) {
	if data == nil {
		return nil, nil
	}
	var r RunnerJSON
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&r); err != nil {
		return nil, err
	}
	if err := dec.Decode(&struct{}{}); err != io.EOF {
		return nil, fmt.Errorf("trailing data")
	}
	return &r, nil
}
