package runner

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// Options select what Run executes.
type Options struct {
	All   bool     // every owned unit, minus the runners subsumed by a full suite
	IDs   []string // explicit ids (each an owned unit)
	RunID string   // "" = $AIT_GATE_RUN_ID, else generated
}

// RunReport is a finished run, as the post-run hook receives it.
type RunReport struct {
	RunID       string   `json:"run_id"`
	Root        string   `json:"-"`
	Dir         string   `json:"dir"` // repo-relative run directory
	Selected    int      `json:"selected"`
	Invocations []Record `json:"invocations"`
	Results     []Result `json:"results"` // invocation order; per invocation, manifest order then child rows
	// HookErrors are the subscribers that failed (each ran once regardless).
	HookErrors []HookError `json:"-"`
}

var runIDRe = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]*$`)

// newRunID is run-<UTC timestamp>-<pid>, unless the caller named one.
func newRunID(explicit string, now time.Time) (string, error) {
	id := explicit
	if id == "" {
		id = os.Getenv("AIT_GATE_RUN_ID")
	}
	if id == "" {
		id = fmt.Sprintf("run-%s-%d", now.UTC().Format("20060102T150405Z"), os.Getpid())
	}
	if !runIDRe.MatchString(id) {
		return "", lineErr(ClassRun, "run-id", "invalid run id "+id)
	}
	return id, nil
}

// Run executes a selection: it loads the repository, selects units, forms
// invocations with the canonical grouping function, executes them through
// the registered plan executor (or the built-in serial plan), writes the
// per-invocation records under .aitask-testmap/runs/<run-id>/, and calls the
// post-run hooks. A framework error is returned before anything runs; once
// execution starts, failures are causes in the records.
func Run(ctx context.Context, root string, opts Options) (*RunReport, error) {
	if fi, err := os.Stat(filepath.Join(root, registry.Dir)); err != nil || !fi.IsDir() {
		return nil, registry.ErrAbsent
	}
	runID, err := newRunID(opts.RunID, time.Now())
	if err != nil {
		return nil, err
	}
	repo, err := Load(ctx, root)
	if err != nil {
		return nil, err
	}
	units, err := selectUnits(repo, opts)
	if err != nil {
		return nil, err
	}
	rel := StateDir + "/runs/" + runID
	report := &RunReport{RunID: runID, Root: root, Dir: rel, Selected: len(units), Invocations: []Record{}, Results: []Result{}}
	if len(units) == 0 {
		report.HookErrors = runHooks(ctx, report)
		return report, nil
	}
	dir := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(dir), 0o755); err != nil {
		return nil, lineErr(ClassRun, "state", err.Error())
	}
	if err := os.Mkdir(dir, 0o755); err != nil {
		if errors.Is(err, fs.ErrExist) {
			return nil, lineErr(ClassRun, "run-exists", runID)
		}
		return nil, lineErr(ClassRun, "state", err.Error())
	}
	exec, wave := seams()
	invs := Group(units, wave)
	iv := &invoker{repo: repo, runID: runID, dir: dir}
	outs, err := exec.Execute(ctx, invs, iv.invoke)
	if err != nil {
		return nil, err
	}
	if len(outs) != len(invs) {
		return nil, lineErr(ClassRun, "executor", fmt.Sprintf("%d outcomes for %d invocations", len(outs), len(invs)))
	}
	for _, o := range outs {
		report.Invocations = append(report.Invocations, o.Record)
		report.Results = append(report.Results, o.Results...)
	}
	report.HookErrors = runHooks(ctx, report)
	return report, nil
}

// selectUnits applies Options. --all omits every runner carrying
// subsumed_by — its units are the child rows of the full suite at the end of
// its chain — but only when that terminal suite itself contributes a
// selected unit: an omitted runner's tests are never silently dropped behind
// a suite that does not run.
func selectUnits(repo *Repository, opts Options) ([]Unit, error) {
	switch {
	case opts.All && len(opts.IDs) > 0:
		return nil, lineErr(ClassRun, "usage", "--all and ids are exclusive")
	case opts.All:
		var out []Unit
		for _, u := range repo.Units {
			if repo.Runner(u.Runner).Entry.SubsumedBy == "" {
				out = append(out, u)
			}
		}
		for _, r := range repo.Runners {
			if r.Entry.SubsumedBy == "" {
				continue
			}
			term := repo.Config.Terminal(r.Name())
			if !slices.ContainsFunc(out, func(u Unit) bool { return u.Runner == term }) {
				return nil, lineErr(ClassRun, "subsumption", r.Name(), "terminal "+term+" selects no unit")
			}
		}
		return out, nil
	default:
		var out []Unit
		seen := map[registry.ID]bool{}
		for _, s := range opts.IDs {
			id, err := registry.ParseID(s)
			if err != nil {
				return nil, lineErr(ClassRun, "unknown-id", s)
			}
			i := slices.IndexFunc(repo.Units, func(u Unit) bool { return u.ID == id })
			if i < 0 {
				return nil, lineErr(ClassRun, "unknown-id", s)
			}
			if !seen[id] {
				seen[id] = true
				out = append(out, repo.Units[i])
			}
		}
		return out, nil
	}
}

// Exit is the run's exit code, before hook errors (which the verb maps to 3):
// 3 for a mechanism failure; else 75 if an invocation was refused; else 1
// for a failing result — top-level or child — or any invocation cause; else
// 2 when no top-level unit passed (nothing selected, or every unit skipped —
// no pass evidence); else 0.
func (r *RunReport) Exit() int {
	refused, causes, passed, failed := false, false, 0, false
	for _, rec := range r.Invocations {
		if rec.Cause == CauseMechanism {
			return lineproto.ExitFramework
		}
		refused = refused || rec.Refused
		causes = causes || rec.Cause != ""
	}
	if refused {
		return lineproto.ExitRefused
	}
	for _, res := range r.Results {
		// A failing child row fails the run even under a passing suite
		// parent; only top-level rows count as passes (disjoint accounting:
		// a child never stands in for a unit that ran).
		failed = failed || failing(res.Status)
		if !res.Child && res.Status == StatusPass {
			passed++
		}
	}
	switch {
	case failed || causes:
		return lineproto.ExitFail
	case passed == 0:
		return lineproto.ExitNothingRan
	}
	return lineproto.ExitOK
}
