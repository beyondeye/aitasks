//go:build t1954cgo && cgo

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

func init() { extraVerbs["tsdiff"] = cmdTSDiff }

// tsdiff compares tree-sitter runtimes on the same input, through the same
// mapping (provider.MapTree): gotreesitter vs the C reference (tscgo), and —
// when built with t1954wasm — tswasm vs tscgo. Two levels: the mapped Result
// (what the seam consumes) and the flattened tree. A divergence never
// establishes a cause by itself: the indicator column is HEURISTIC (see the
// report's method section).

type tsPair struct{ a, b string }

type diffAgg struct {
	files, failA, failB                         int
	treeSame, treeDiffLeavesSame, treeDiffOther int
	resSame, resDiff                            int
	uncAOnly, uncBOnly, spansDiff, anchorsDiff  int
	docDiff                                     int
	indicators                                  map[string]int
	paths                                       map[string][]string
}

func (d *diffAgg) add(kind, entry string, max int) {
	if len(d.paths[kind]) < max {
		d.paths[kind] = append(d.paths[kind], entry)
	}
}

// externals reads a grammar's external token names from its pinned
// grammar.json (.tsref/), for the scanner indicator.
func externals(lang string) map[string]bool {
	dirs := map[string]string{
		"bash": "tree-sitter-bash/src", "python": "tree-sitter-python/src", "go": "tree-sitter-go/src",
		"kotlin": "tree-sitter-kotlin/src", "typescript": "tree-sitter-typescript/typescript/src",
		"tsx": "tree-sitter-typescript/tsx/src", "javascript": "tree-sitter-javascript/src",
		"java": "tree-sitter-java/src", "rust": "tree-sitter-rust/src", "swift": "tree-sitter-swift/src",
	}
	out := map[string]bool{}
	b, err := os.ReadFile(filepath.Join(".tsref", dirs[lang], "grammar.json"))
	if err != nil {
		return out
	}
	var g struct {
		Externals []struct{ Type, Name, Value string } `json:"externals"`
	}
	if json.Unmarshal(b, &g) == nil {
		for _, e := range g.Externals {
			if e.Name != "" {
				out[e.Name] = true
			}
			if e.Value != "" {
				out[e.Value] = true
			}
		}
	}
	return out
}

type leaf struct {
	start, end int
	kind       string
	bad        bool
}

func leavesOf(ns []provider.TSNode) []leaf {
	var out []leaf
	for _, n := range ns {
		if n.Leaf {
			out = append(out, leaf{n.Start, n.End, n.Kind, n.Error || n.Missing})
		}
	}
	return out
}

func sameLeafRanges(a, b []leaf) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i].start != b[i].start || a[i].end != b[i].end || a[i].bad != b[i].bad {
			return false
		}
	}
	return true
}

func sameTree(a, b []provider.TSNode) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		x, y := a[i], b[i]
		if x.Kind != y.Kind || x.Start != y.Start || x.End != y.End || x.Parent != y.Parent || x.Error != y.Error || x.Missing != y.Missing {
			return false
		}
	}
	return true
}

// firstDivergence describes the first differing node, kinds and offsets
// only (no file contents).
func firstDivergence(a, b []provider.TSNode) (string, provider.TSNode, provider.TSNode) {
	for i := 0; i < len(a) && i < len(b); i++ {
		x, y := a[i], b[i]
		if x.Kind != y.Kind || x.Start != y.Start || x.End != y.End || x.Error != y.Error || x.Missing != y.Missing {
			return fmt.Sprintf("node %d: %s[%d,%d) vs %s[%d,%d)", i, nodeLabel(x), x.Start, x.End, nodeLabel(y), y.Start, y.End), x, y
		}
	}
	return fmt.Sprintf("node counts %d vs %d", len(a), len(b)), provider.TSNode{}, provider.TSNode{}
}

func nodeLabel(n provider.TSNode) string {
	switch {
	case n.Error:
		return "ERROR"
	case n.Missing:
		return "MISSING " + n.Kind
	}
	return n.Kind
}

// indicator is the HEURISTIC cause hint for a Result difference.
func indicator(lang string, ext map[string]bool, a, b []provider.TSNode) string {
	la, lb := leavesOf(a), leavesOf(b)
	if sameLeafRanges(la, lb) {
		return "heuristic:table-or-runtime (identical leaves)"
	}
	for i := 0; i < len(la) && i < len(lb); i++ {
		if la[i].start != lb[i].start || la[i].end != lb[i].end || la[i].bad != lb[i].bad {
			if ext[la[i].kind] || ext[lb[i].kind] {
				return "heuristic:scanner (external token at the first divergent leaf)"
			}
			if la[i].bad || lb[i].bad {
				return "heuristic:recovery (ERROR/MISSING at the first divergent leaf)"
			}
			return "unknown"
		}
	}
	return "unknown"
}

func resultKey(r provider.Result) (unc bool, spans, anchors, doc string) {
	ss := append([]provider.Span(nil), r.Spans...)
	sort.Slice(ss, func(i, j int) bool {
		if ss[i].Start != ss[j].Start {
			return ss[i].Start < ss[j].Start
		}
		return ss[i].End < ss[j].End
	})
	return len(r.Diags) > 0, fmt.Sprint(ss), fmt.Sprintf("%+v", r.Anchors), fmt.Sprintf("%+v", r.Doc)
}

func cmdTSDiff(args []string) int {
	fs := flag.NewFlagSet("tsdiff", flag.ExitOnError)
	repos := fs.String("repos", "aitasks,aitasks_go,aitasks_mobile,thinking_app,thinking_backend,timexchange", "registered repositories walked read-only")
	out := fs.String("out", "results/ts_differential.md", "output file")
	maxPaths := fs.Int("max-paths", 25, "paths listed per kind")
	_ = fs.Parse(args)
	defer provider.CloseAll()
	treers := map[string]provider.TSTreer{}
	for _, n := range []string{"gotreesitter", "tscgo", "tswasm"} {
		p, err := provider.New(n)
		if err != nil {
			continue // tswasm is absent without -tags t1954wasm; reported below
		}
		treers[n] = p.(provider.TSTreer)
	}
	if treers["gotreesitter"] == nil || treers["tscgo"] == nil {
		fail(1, fmt.Errorf("tsdiff needs gotreesitter and tscgo"))
	}
	pairs := []tsPair{{"gotreesitter", "tscgo"}}
	if treers["tswasm"] != nil {
		pairs = append(pairs, tsPair{"tswasm", "tscgo"})
	}
	// Input sets: the corpus, then each repository's git-visible files.
	type input struct{ set, lang, path string }
	var inputs []input
	cases, err := corpus.Load("corpus")
	if err != nil {
		fail(1, err)
	}
	for _, c := range cases {
		l, ok := provider.LangOfPath(c.Name, c.Data)
		if ok {
			inputs = append(inputs, input{"corpus", l.Name, c.Path})
		}
	}
	top, _ := exec.Command("git", "-C", id.Root, "rev-parse", "--show-toplevel").Output()
	setOrder := []string{"corpus"}
	unresolved := map[string]string{}
	for _, n := range strings.Split(*repos, ",") {
		if n == "" {
			continue
		}
		res, err := exec.Command(filepath.Join(strings.TrimSpace(string(top)), "ait"), "projects", "resolve", n).Output()
		path := strings.TrimPrefix(strings.TrimSpace(string(res)), "RESOLVED:")
		if err != nil || path == "" {
			unresolved[n] = "not resolved"
			continue
		}
		ls, err := exec.Command("git", "-C", path, "ls-files", "-z", "--cached", "--others", "--exclude-standard").Output()
		if err != nil {
			unresolved[n] = "git ls-files failed"
			continue
		}
		setOrder = append(setOrder, n)
		for _, f := range strings.Split(strings.TrimRight(string(ls), "\x00"), "\x00") {
			if f == "" || strings.Contains(f, "/.baseline") || strings.Contains(f, "/.tsref") {
				continue
			}
			p := filepath.Join(path, f)
			st, err := os.Lstat(p)
			if err != nil || !st.Mode().IsRegular() || st.Size() > maxFileBytes {
				continue
			}
			head := []byte{}
			if filepath.Ext(f) == "" {
				if b, err := readHead(p, 128); err == nil {
					head = b
				}
			}
			if l, ok := provider.LangOfPath(f, head); ok {
				inputs = append(inputs, input{n, l.Name, p})
			}
		}
	}
	ext := map[string]map[string]bool{}
	for _, l := range provider.TSLangs {
		ext[l] = externals(l)
	}
	// aggs[pair][set][lang]
	aggs := map[tsPair]map[string]map[string]*diffAgg{}
	for _, pr := range pairs {
		aggs[pr] = map[string]map[string]*diffAgg{}
	}
	for _, in := range inputs {
		src, err := os.ReadFile(in.path)
		if err != nil {
			continue
		}
		rel := in.path
		if r, err := filepath.Rel(id.Root, in.path); err == nil && !strings.HasPrefix(r, "..") {
			rel = r
		}
		if in.set != "corpus" {
			rel = in.set + ":" + filepath.Base(filepath.Dir(in.path)) + "/" + filepath.Base(in.path)
		}
		flat := map[string][]provider.TSNode{}
		stop := map[string]string{}
		errs := map[string]error{}
		for n, t := range treers {
			flat[n], stop[n], errs[n] = t.Flat(in.lang, src)
		}
		for _, pr := range pairs {
			bySet := aggs[pr][in.set]
			if bySet == nil {
				bySet = map[string]*diffAgg{}
				aggs[pr][in.set] = bySet
			}
			d := bySet[in.lang]
			if d == nil {
				d = &diffAgg{indicators: map[string]int{}, paths: map[string][]string{}}
				bySet[in.lang] = d
			}
			d.files++
			if errs[pr.a] != nil || errs[pr.b] != nil {
				if errs[pr.a] != nil {
					d.failA++
					d.add("runtime failure: "+pr.a, rel+" — "+oneLineErr(errs[pr.a]), *maxPaths)
				}
				if errs[pr.b] != nil {
					d.failB++
					d.add("runtime failure: "+pr.b, rel+" — "+oneLineErr(errs[pr.b]), *maxPaths)
				}
				continue
			}
			a, b := flat[pr.a], flat[pr.b]
			switch {
			case sameTree(a, b):
				d.treeSame++
			case sameLeafRanges(leavesOf(a), leavesOf(b)):
				d.treeDiffLeavesSame++
			default:
				d.treeDiffOther++
			}
			ra := provider.MapTree(in.lang, a, stop[pr.a], src)
			rb := provider.MapTree(in.lang, b, stop[pr.b], src)
			ua, sa, aa, da := resultKey(ra)
			ub, sb, ab, db := resultKey(rb)
			if ua == ub && sa == sb && aa == ab && da == db {
				d.resSame++
				continue
			}
			d.resDiff++
			var what []string
			if ua && !ub {
				d.uncAOnly++
				what = append(what, "uncertain: "+pr.a+" only")
			}
			if ub && !ua {
				d.uncBOnly++
				what = append(what, "uncertain: "+pr.b+" only")
			}
			if sa != sb {
				d.spansDiff++
				what = append(what, "spans")
			}
			if aa != ab {
				d.anchorsDiff++
				what = append(what, "anchors")
			}
			if da != db {
				d.docDiff++
				what = append(what, "doc")
			}
			ind := indicator(in.lang, ext[in.lang], a, b)
			d.indicators[ind]++
			fd, _, _ := firstDivergence(a, b)
			d.add("result differs", fmt.Sprintf("%s — %s — %s — first divergence %s", rel, strings.Join(what, ", "), ind, fd), *maxPaths)
		}
	}
	// Report.
	var w strings.Builder
	fmt.Fprintf(&w, "# Tree-sitter runtime differential (t1954_2)\n\n%s\n\n", id.Header())
	w.WriteString("Each input is parsed by two runtimes and both trees go through the **same** mapping (`provider.MapTree`), so a difference is a runtime/table/scanner difference, never a mapping difference — except where the mapping is sensitive to a tree SHAPE one runtime produces (recorded in the findings). Grammars: the commits in `tsref/LOCK` (gotreesitter v0.55.1's `languages.lock`). Rerun: `tsref/fetch.sh && go run -tags 't1954cgo t1954wasm' ./cmd/t1954 tsdiff` (tswasm needs `tswasm/build.sh` first).\n\n")
	w.WriteString("**Levels.** *Tree*: identical flattened trees (kind, range, parent, ERROR/MISSING); otherwise whether the leaf ranges still agree. *Result*: the mapped `Result` the seam consumes — certainty, sorted spans, anchors, Python `DocInfo`.\n\n")
	w.WriteString("**Cause indicators are HEURISTIC, never an attribution.** `table-or-runtime (identical leaves)`: same token ranges, different tree — consistent with a table difference OR a runtime defect, it does not choose. `scanner`: an external token at the first divergent leaf. `recovery`: ERROR/MISSING at the first divergent leaf. `unknown` otherwise. Table provenance (gotreesitter `go` and `swift` are grammargen-owned, the rest mirror upstream `parser.c`) says where the tables came from, not what caused a difference. Repository files are listed as `<repo>:<dir>/<file>`; nothing was executed or written there.\n\n")
	if len(unresolved) > 0 {
		w.WriteString("Unresolved repositories (not walked): ")
		for _, k := range sortedKeys(unresolved) {
			fmt.Fprintf(&w, "`%s` (%s) ", k, unresolved[k])
		}
		w.WriteString("\n\n")
	}
	if treers["tswasm"] == nil {
		w.WriteString("tswasm: not in this build (needs `-tags t1954wasm` and `.tswasm/ts.wasm`) — not measured.\n\n")
	}
	for _, pr := range pairs {
		fmt.Fprintf(&w, "## %s vs %s\n\n", pr.a, pr.b)
		w.WriteString("| set | lang | files | runtime failures (A / B) | tree identical | tree differs: leaves identical / leaves differ | Result identical | Result differs | uncertain: A only / B only | spans differ | anchors differ | doc differs | indicators |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
		for _, set := range setOrder {
			for _, lang := range provider.TSLangs {
				d := aggs[pr][set][lang]
				if d == nil {
					continue
				}
				var inds []string
				for _, k := range sortedIntKeys(d.indicators) {
					inds = append(inds, fmt.Sprintf("%s: %d", k, d.indicators[k]))
				}
				fmt.Fprintf(&w, "| %s | %s | %d | %d / %d | %d | %d / %d | %d | %d | %d / %d | %d | %d | %d | %s |\n", set, lang, d.files, d.failA, d.failB,
					d.treeSame, d.treeDiffLeavesSame, d.treeDiffOther, d.resSame, d.resDiff, d.uncAOnly, d.uncBOnly, d.spansDiff, d.anchorsDiff, d.docDiff, strings.Join(inds, "; "))
			}
		}
		w.WriteString("\n### Paths\n\n")
		any := false
		for _, set := range setOrder {
			for _, lang := range provider.TSLangs {
				d := aggs[pr][set][lang]
				if d == nil {
					continue
				}
				for _, k := range sortedPathKeys(d.paths) {
					for _, p := range d.paths[k] {
						fmt.Fprintf(&w, "- %s/%s — %s: %s\n", set, lang, k, p)
						any = true
					}
				}
			}
		}
		if !any {
			w.WriteString("None.\n")
		}
		w.WriteString("\n")
	}
	if err := os.WriteFile(*out, []byte(w.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", *out)
	return 0
}

func oneLineErr(err error) string { return strings.ReplaceAll(err.Error(), "\n", " ") }

func sortedIntKeys(m map[string]int) []string {
	var out []string
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func sortedPathKeys(m map[string][]string) []string {
	var out []string
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
