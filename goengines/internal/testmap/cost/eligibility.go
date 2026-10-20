package cost

import (
	"context"
	"path"
	"slices"
	"strings"

	"github.com/bmatcuk/doublestar/v4"

	"github.com/beyondeye/aitasks/goengines/internal/gitx"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/deps"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

// Anchor eligibility, decided at run time. A result is *clean* when the tree
// its invocation ran on differs from head_start in nothing the unit can
// read: no cause, HEAD unmoved, and the modified-path set either empty or
// disjoint from the unit's test file, its whole test-side closure, its
// covers sources, the reads globs (helper `testmap:reads` and scanner
// plugin) of every file in that closure, and the runner's own files. A unit
// whose closure is opaque or not computable is clean only on an unmodified
// tree. A clean pass anchors; every rejection carries its reason, which fails
// toward running more (the edge stays STALE). A file edited and reverted
// within one invocation is invisible to the start and end snapshots — the
// residual this rule accepts.

// inputs are what the disjointness checks read, loaded at most once per run
// and only when some result needs them.
type inputs struct {
	err      string // "<input>:<detail>" when an input failed
	head     string
	modified map[string]bool
	graph    *deps.Graph
	covers   map[registry.ID][]string // unit block (file-level: Member "") → covered sources
	reads    map[string][]string      // helper path → testmap:reads globs
}

// judge decides each result of one run.
type judge struct {
	ctx   context.Context
	rep   *runner.RunReport
	units map[registry.ID]runner.Unit
	in    *inputs
	// beforeInputs runs just before the inputs are read (tests edit the tree
	// there to prove tree-changed).
	beforeInputs func()
}

// testBeforeInputs is the test seam behind judge.beforeInputs.
var testBeforeInputs func()

func newJudge(ctx context.Context, rep *runner.RunReport) *judge {
	j := &judge{ctx: ctx, rep: rep, units: map[registry.ID]runner.Unit{}, beforeInputs: testBeforeInputs}
	if rep.Repo != nil {
		for _, u := range rep.Repo.Units {
			j.units[u.ID] = u
		}
	}
	return j
}

func (j *judge) load() *inputs {
	if j.in != nil {
		return j.in
	}
	if j.beforeInputs != nil {
		j.beforeInputs()
	}
	in := &inputs{}
	j.in = in
	root := j.rep.Root
	git := gitx.Repo{Dir: root}
	var err error
	if in.head, err = git.Head(j.ctx); err != nil {
		in.err = "git:" + oneLine(err.Error())
		return in
	}
	mod, err := runner.ModifiedPaths(j.ctx, git)
	if err != nil {
		in.err = "git:" + oneLine(err.Error())
		return in
	}
	in.modified = map[string]bool{}
	for _, p := range mod {
		in.modified[p] = true
	}
	cfg, err := registry.LoadConfig(root)
	if err != nil {
		in.err = "config:" + oneLine(err.Error())
		return in
	}
	if in.graph, err = deps.Scan(j.ctx, root, deps.Options{Config: cfg}); err != nil {
		in.err = "deps:" + oneLine(err.Error())
		return in
	}
	in.covers, in.reads = map[registry.ID][]string{}, map[string][]string{}
	anns, err := annot.Source{}.Annotations(j.ctx, root)
	if err != nil {
		in.err = "annotations:" + oneLine(err.Error())
		return in
	}
	for _, f := range anns {
		for _, u := range f.Units {
			id := registry.ID{Path: f.Path, Member: u.Member}
			for _, c := range u.Covers {
				in.covers[id] = append(in.covers[id], c.Source)
			}
			if len(u.Reads) > 0 {
				in.reads[f.Path] = append(in.reads[f.Path], u.Reads...)
			}
		}
	}
	reg, err := registry.Load(root)
	if err != nil {
		in.err = "registry:" + oneLine(err.Error())
		return in
	}
	for _, e := range reg.Edges {
		in.covers[e.Test] = append(in.covers[e.Test], e.Source)
	}
	for _, r := range registry.ScopedOf(reg).Reads {
		in.reads[r.Helper] = append(in.reads[r.Helper], r.Globs...)
	}
	return in
}

// decide returns whether res is clean and, when it is not, why.
func (j *judge) decide(res runner.Result, rec runner.Record) (bool, string) {
	switch {
	case rec.Cause != "":
		return false, "cause:" + rec.Cause
	case rec.Refused:
		return false, "refused"
	case rec.HeadStart == "":
		return false, "head-unborn"
	case rec.HeadStart != rec.HeadEnd:
		return false, "head-moved"
	case len(rec.Modified) == 0:
		return true, ""
	}
	if res.Child {
		return false, "opaque:child"
	}
	u, ok := j.units[res.ID]
	var r *runner.Runner
	if ok && j.rep.Repo != nil {
		r = j.rep.Repo.Runner(u.Runner)
	}
	if r == nil {
		return false, "eligibility-error:unit:" + res.ID.String()
	}
	switch {
	case u.Kind == "suite" || r.Describe.Full:
		return false, "opaque:suite"
	case r.Describe.FilterScope == runner.FilterWholeRun:
		return false, "opaque:whole-run"
	}
	in := j.load()
	switch {
	case in.err != "":
		return false, "eligibility-error:" + in.err
	case in.head != rec.HeadEnd || !subset(in.modified, rec.Modified):
		return false, "tree-changed"
	}
	mod := map[string]bool{}
	for _, p := range rec.Modified {
		// A root below the git top level sees modifications outside it
		// (../…), which the scan cannot follow: it resolves within the root
		// only, so a reference that leaves it can land on an in-root
		// namesake. No closure proves such a path unread.
		if strings.HasPrefix(p, "../") {
			return false, "outside-root:" + p
		}
		mod[p] = true
	}
	test := res.ID.Path
	if _, ok := in.graph.Facts(test); !ok {
		return false, "opaque:no-facts"
	}
	files := j.closure(test)
	if why := opaqueIn(in.graph, files); why != "" {
		return false, "opaque:" + why
	}
	if mod[test] {
		return false, "test-file"
	}
	for _, f := range files[1:] {
		if mod[f] {
			return false, "closure:" + f
		}
	}
	for _, src := range j.coversOf(res.ID) {
		if mod[src] {
			return false, "covers:" + src
		}
	}
	for _, f := range files {
		if g := globHit(in.reads[f], rec.Modified); g != "" {
			return false, "reads:" + g
		}
	}
	for _, f := range files {
		facts, _ := in.graph.Facts(f)
		if g := globHit(facts.Reads, rec.Modified); g != "" {
			return false, "plugin-reads:" + g
		}
	}
	if why := j.runnerConfig(r, mod); why != "" {
		return false, "runner-config:" + why
	}
	return true, ""
}

// closure is {test} ∪ its test-side closure, the test first.
func (j *judge) closure(test string) []string {
	files := []string{test}
	for _, r := range j.in.graph.Closure(test, 0) {
		files = append(files, r.Path)
	}
	return files
}

// opaqueIn names the first file of files whose closure cannot be trusted: an
// opaque reason, or a literal reference that resolved to no repository file
// (an excluded, linked or deleted target the closure could not follow).
func opaqueIn(g *deps.Graph, files []string) string {
	for _, f := range files {
		if g.Opaque(f) != "" {
			return "closure-opaque:" + f
		}
		if facts, ok := g.Facts(f); ok && len(facts.Unresolved) > 0 {
			return "unresolved:" + f
		}
	}
	return ""
}

// coversOf is every covered source of id: its own block's and the file-level
// block's, from the current annotations and from the registry's edges.
// Covers are literal paths, compared by equality.
func (j *judge) coversOf(id registry.ID) []string {
	var out []string
	for _, k := range []registry.ID{id.Base(), {Path: id.Path}} {
		out = append(out, j.in.covers[k]...)
	}
	slices.Sort(out)
	return slices.Compact(out)
}

// runnerConfig names the first runner file the modified set touches: the
// runners table, anything under aitestmap/runners/, a project script and
// its own closure, or a path the builtin command line names.
func (j *judge) runnerConfig(r *runner.Runner, mod map[string]bool) string {
	if mod[runner.RunnersPath] {
		return runner.RunnersPath
	}
	for p := range sortedKeys(mod) {
		if strings.HasPrefix(p, runner.RunnersDir+"/") {
			return p
		}
	}
	if r.Resolution.Source != runner.SourceBuiltin && r.Resolution.Path != "" {
		script := r.Resolution.Path
		if _, ok := j.in.graph.Facts(script); !ok {
			if mod[script] {
				return script
			}
			return "opaque:" + script
		}
		files := j.closure(script)
		if why := opaqueIn(j.in.graph, files); why != "" {
			return "opaque:" + strings.TrimPrefix(strings.TrimPrefix(why, "closure-opaque:"), "unresolved:")
		}
		for _, f := range files {
			if mod[f] {
				return f
			}
		}
	}
	for _, tok := range strings.Fields(r.Entry.Command) {
		for _, p := range []string{path.Clean(tok), path.Clean(path.Join(r.Entry.Cwd, tok))} {
			if mod[p] {
				return p
			}
		}
	}
	return ""
}

// globHit returns the first glob matching a modified path. A glob that does
// not parse counts as a hit: an unreadable declaration fails closed.
func globHit(globs, modified []string) string {
	for _, g := range globs {
		if !doublestar.ValidatePattern(g) {
			return g
		}
		for _, p := range modified {
			if ok, _ := doublestar.Match(g, p); ok {
				return g
			}
		}
	}
	return ""
}

func subset(a map[string]bool, b []string) bool {
	in := map[string]bool{}
	for _, p := range b {
		in[p] = true
	}
	for p := range a {
		if !in[p] {
			return false
		}
	}
	return true
}

func sortedKeys(m map[string]bool) func(func(string) bool) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	slices.Sort(keys)
	return slices.Values(keys)
}
