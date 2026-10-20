package runner

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/gitx"
	"github.com/beyondeye/aitasks/goengines/internal/testmap"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// StateDir is the engine's gitignored state directory; its own writes are
// never part of a run's modified-path set.
const StateDir = ".aitask-testmap"

// Manifest is what `run --manifest <path>` reads.
type Manifest struct {
	Contract   int            `json:"contract"`
	RunID      string         `json:"run_id"`
	Invocation int            `json:"invocation"`
	Group      string         `json:"group"`
	Handle     string         `json:"handle"` // the allocator handle (M3.3); "" when none is held
	Timeouts   string         `json:"timeouts"`
	DeadlineS  float64        `json:"deadline_s"` // the engine's deadline for this invocation
	Results    string         `json:"results"`
	RunnerJSON string         `json:"runner_json"`
	Units      []ManifestUnit `json:"units"`
}

// ManifestUnit is one unit to run.
type ManifestUnit struct {
	ID       string  `json:"id"`
	Lowering string  `json:"lowering"`
	TimeoutS float64 `json:"timeout_s"`
}

// Record is the engine's own per-invocation record (`record.json`) — never
// the runner's: a runner cannot judge its own reconciliation. It carries the
// worktree provenance M3.4's anchor eligibility reads.
type Record struct {
	Contract       int      `json:"contract"`
	RunID          string   `json:"run_id"`
	Invocation     int      `json:"invocation"`
	Group          string   `json:"group"`
	Runner         string   `json:"runner"`
	UnitsExpected  int      `json:"units_expected"`
	UnitsReported  int      `json:"units_reported"`
	UnitsStarted   int      `json:"units_started"`
	ExitCode       int      `json:"exit_code"`
	ElapsedMS      int64    `json:"elapsed_ms"`
	Timeouts       string   `json:"timeouts"`
	DeadlineS      float64  `json:"deadline_s"`
	Killed         bool     `json:"killed"`
	Refused        bool     `json:"refused"`
	TimedOut       string   `json:"timed_out"`
	ProtocolErrors []string `json:"protocol_errors"`
	OverheadMS     int64    `json:"overhead_ms"`
	Cause          string   `json:"cause"`
	CauseDetail    string   `json:"cause_detail"`
	HeadStart      string   `json:"head_start"`
	HeadEnd        string   `json:"head_end"`
	Modified       []string `json:"modified"` // start ∪ end, root-relative (../ outside the root), sorted
}

// invoker runs invocations for one run.
type invoker struct {
	repo  *Repository
	runID string
	dir   string // absolute run directory
}

func (iv *invoker) invoke(ctx context.Context, inv *Invocation) Outcome {
	r := iv.repo.Runner(inv.Runner)
	mode := r.Describe.Timeouts
	rec := Record{
		Contract: testmap.Contract, RunID: iv.runID, Invocation: inv.Index, Group: inv.Key.String(),
		Runner: inv.Runner, UnitsExpected: len(inv.Units), Timeouts: mode, ProtocolErrors: []string{}, Modified: []string{},
	}
	expected := make([]registry.ID, len(inv.Units))
	timeouts := map[registry.ID]float64{}
	for i, u := range inv.Units {
		expected[i] = u.ID
		timeouts[u.ID] = u.TimeoutS
	}
	fail := func(detail string) Outcome {
		v := verdict{Cause: CauseMechanism, CauseDetail: detail}
		for _, id := range expected {
			v.Results = append(v.Results, Result{ID: id, Status: StatusNotStarted})
		}
		return iv.finish(inv, rec, v, nil)
	}
	deadline, bound, err := Deadline(mode, inv.Units, r.Entry.BatchTimeoutS, r.MaxInvocationS)
	if err != nil {
		return fail("plan:" + err.Error())
	}
	rec.DeadlineS = deadline.Seconds()
	idir := filepath.Join(iv.dir, fmt.Sprintf("inv-%03d", inv.Index))
	if err := os.MkdirAll(idir, 0o755); err != nil {
		return fail("state:" + err.Error())
	}
	m := Manifest{
		Contract: testmap.Contract, RunID: iv.runID, Invocation: inv.Index, Group: rec.Group, Handle: inv.Handle,
		Timeouts: mode, DeadlineS: rec.DeadlineS,
		Results: filepath.Join(idir, "results.jsonl"), RunnerJSON: filepath.Join(idir, "runner.json"),
	}
	for _, u := range inv.Units {
		m.Units = append(m.Units, ManifestUnit{ID: u.ID.String(), Lowering: u.Lowering, TimeoutS: u.TimeoutS})
	}
	mpath := filepath.Join(idir, "manifest.json")
	if err := writeJSON(mpath, m); err != nil {
		return fail("state:" + err.Error())
	}
	git := gitx.Repo{Dir: iv.repo.Root}
	headStart, modStart, perr := provenance(ctx, git)
	if perr != nil {
		return fail("provenance:" + perr.Error())
	}
	c, err := r.command(iv.repo.Root, append(os.Environ(), "AIT_TESTMAP_RUN_ID="+iv.runID), "run", "--manifest", mpath)
	if err != nil {
		return fail("runner_start:" + err.Error())
	}
	start := time.Now()
	res := execRunner(ctx, c, deadline)
	rec.ElapsedMS = time.Since(start).Milliseconds()
	rec.ExitCode, rec.Killed = res.Exit, res.Killed
	headEnd, modEnd, perr := provenance(ctx, git)
	// The report files are read only through readReport: a FIFO, a link, a
	// device or an oversized file left at a report path is a protocol error,
	// never a read that blocks or grows past the bounds the deadline set.
	data, _, rerr := readReport(m.Results, resultsMax)
	v := ValidateRows(data, res.Killed, rowContext{
		Expected: expected, TimeoutS: timeouts, Registered: iv.repo.Registered,
		Full: r.Describe.Full, Mode: mode,
	})
	if rerr != nil {
		v.Errors = append(v.Errors, "report:results.jsonl:"+oneLine(rerr.Error()))
	}
	rj, _, jerr := readReport(m.RunnerJSON, runnerJSONMax)
	if jerr == nil {
		_, jerr = parseRunnerJSON(rj)
	}
	if jerr != nil {
		v.Errors = append(v.Errors, "report:runner.json:"+oneLine(jerr.Error()))
	}
	vd := decide(EndState{Exit: res.Exit, Killed: res.Killed, Bound: bound, StartErr: res.StartErr, Overflow: res.Overflow, Sweep: res.Sweep}, v, expected, mode)
	if perr != nil && causeRank[CauseMechanism] > causeRank[vd.Cause] {
		vd.Cause, vd.CauseDetail = CauseMechanism, "provenance:"+oneLine(perr.Error())
	}
	rec.HeadStart, rec.HeadEnd = headStart, headEnd
	rec.Modified = union(modStart, modEnd)
	rec.UnitsReported = len(v.Reported)
	rec.UnitsStarted = len(v.Started)
	var top int64 // durations are bounded by maxDurationMS, so the sum cannot overflow
	for _, row := range v.Rows {
		if !row.Child {
			top += row.DurationMS
		}
	}
	rec.OverheadMS = max(rec.ElapsedMS-top, 0)
	return iv.finish(inv, rec, vd, &idir)
}

// finish stamps the verdict into the record, writes record.json (when the
// invocation directory exists) and returns the outcome.
func (iv *invoker) finish(inv *Invocation, rec Record, vd verdict, idir *string) Outcome {
	rec.Cause, rec.CauseDetail, rec.Refused, rec.TimedOut = vd.Cause, vd.CauseDetail, vd.Refused, vd.TimedOut
	if vd.ProtocolErrors != nil {
		rec.ProtocolErrors = vd.ProtocolErrors
	}
	for i := range vd.Results {
		vd.Results[i].Invocation = inv.Index
	}
	if idir != nil {
		if err := writeJSON(filepath.Join(*idir, "record.json"), rec); err != nil && rec.Cause != CauseMechanism {
			rec.Cause, rec.CauseDetail = CauseMechanism, "state:"+oneLine(err.Error())
		}
	}
	return Outcome{Record: rec, Results: vd.Results}
}

// provenance is HEAD and the modified-path set at one moment.
func provenance(ctx context.Context, git gitx.Repo) (string, []string, error) {
	head, err := git.Head(ctx)
	if err != nil {
		return "", nil, err
	}
	mod, err := ModifiedPaths(ctx, git)
	if err != nil {
		return head, nil, err
	}
	return head, mod, nil
}

// ModifiedPaths is the modified-path set of the root git.Dir names, in the
// engine's path space: relative to the root (gitx.DirModifiedPaths — a path
// outside it climbs with ../), minus the engine's own state directory.
func ModifiedPaths(ctx context.Context, git gitx.Repo) ([]string, error) {
	mod, err := git.DirModifiedPaths(ctx)
	if err != nil {
		return nil, err
	}
	kept := mod[:0]
	for _, p := range mod {
		if p != StateDir && !strings.HasPrefix(p, StateDir+"/") {
			kept = append(kept, p)
		}
	}
	return kept, nil
}

func union(a, b []string) []string {
	out := slices.Concat(a, b)
	slices.Sort(out)
	out = slices.Compact(out)
	if out == nil {
		out = []string{}
	}
	return out
}

func writeJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, append(b, '\n'), 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

// MarshalJSON renders ids as their canonical strings.
func (r Result) MarshalJSON() ([]byte, error) {
	type wire struct {
		ID         string `json:"id"`
		Status     string `json:"status"`
		DurationMS int64  `json:"duration_ms"`
		Parent     string `json:"parent,omitempty"`
		Child      bool   `json:"child,omitempty"`
		Started    bool   `json:"started,omitempty"`
		Message    string `json:"message,omitempty"`
		Invocation int    `json:"invocation"`
	}
	w := wire{ID: r.ID.String(), Status: r.Status, DurationMS: r.DurationMS, Child: r.Child, Started: r.Started, Message: r.Message, Invocation: r.Invocation}
	if r.Child {
		w.Parent = r.Parent.String()
	}
	return json.Marshal(w)
}

// MarshalJSON renders the id as its canonical string.
func (u Unit) MarshalJSON() ([]byte, error) {
	type alias Unit
	return json.Marshal(struct {
		ID string `json:"id"`
		alias
	}{u.ID.String(), alias(u)})
}
