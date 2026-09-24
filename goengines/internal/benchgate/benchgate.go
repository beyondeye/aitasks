// Package benchgate enforces the engine's latency budgets: `go test -bench`
// results are compared against committed baselines, and a benchmark more than
// Factor times slower than its baseline — or over its absolute budget —
// fails. The tool that runs it is internal/tools/benchgate.
//
// Baseline file format (bench/baseline.txt), one benchmark per line:
//
//	# comment
//	internal/gitx.BenchmarkBlobDigest 14250 budget=1ms
//
// The name is the package path relative to the module plus the benchmark name
// without its -<GOMAXPROCS> suffix; the number is ns/op; budget= is optional.
package benchgate

import (
	"bufio"
	"fmt"
	"io"
	"maps"
	"math"
	"slices"
	"strconv"
	"strings"
	"time"
)

// Factor is the regression rule: slower than Factor × baseline fails.
const Factor = 2.0

// Mode selects how a baseline benchmark with no measurement is judged.
type Mode int

const (
	// Full is the gate: every baseline benchmark must be measured, so a
	// deleted or renamed benchmark cannot silently drop its baseline.
	Full Mode = iota
	// Partial is a developer run over a subset (-bench pattern, one
	// package): unmeasured baselines are listed but do not fail. Never the
	// gate.
	Partial
)

func (m Mode) String() string {
	if m == Partial {
		return "partial"
	}
	return "full"
}

// ParseBench reads `go test -bench` output and returns ns/op per benchmark,
// keyed `<pkg>.<Benchmark>` with modulePrefix trimmed from the package path
// and the -<procs> suffix removed. A benchmark reported twice (-count > 1)
// keeps its minimum.
func ParseBench(r io.Reader, modulePrefix string) (map[string]float64, error) {
	res := map[string]float64{}
	pkg := ""
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64<<10), 1<<20)
	for sc.Scan() {
		line := sc.Text()
		if p, ok := strings.CutPrefix(line, "pkg: "); ok {
			pkg = strings.TrimPrefix(strings.TrimSpace(p), modulePrefix)
			continue
		}
		if !strings.HasPrefix(line, "Benchmark") {
			continue
		}
		f := strings.Fields(line)
		// Benchmark<Name>-N  <iterations>  <value> ns/op  [more pairs…]
		if len(f) < 4 || f[3] != "ns/op" {
			continue
		}
		ns, err := strconv.ParseFloat(f[2], 64)
		if err != nil || !validNs(ns) {
			return nil, fmt.Errorf("benchgate: %q: ns/op must be a finite positive number", line)
		}
		key := pkg + "." + stripProcs(f[0])
		if old, ok := res[key]; !ok || ns < old {
			res[key] = ns
		}
	}
	return res, sc.Err()
}

// validNs rejects zero, negative, NaN and ±Inf timings: any of them would
// turn the ratio test into a silent pass (NaN compares false, x/Inf is 0).
func validNs(ns float64) bool {
	return ns > 0 && !math.IsInf(ns, 0) && !math.IsNaN(ns)
}

func stripProcs(name string) string {
	i := strings.LastIndexByte(name, '-')
	if i < 0 {
		return name
	}
	if _, err := strconv.Atoi(name[i+1:]); err != nil {
		return name
	}
	return name[:i]
}

// Entry is one baseline line.
type Entry struct {
	Name   string
	NsOp   float64
	Budget time.Duration // 0 = no absolute budget
}

// Baseline is a parsed baseline file; Lines keeps comments and blank lines so
// Rewrite can preserve them.
type Baseline struct {
	Entries map[string]Entry
	lines   []string // raw lines; a benchmark line is replaced on rewrite
}

// ParseBaseline reads a baseline file.
func ParseBaseline(r io.Reader) (*Baseline, error) {
	b := &Baseline{Entries: map[string]Entry{}}
	sc := bufio.NewScanner(r)
	n := 0
	for sc.Scan() {
		n++
		line := sc.Text()
		b.lines = append(b.lines, line)
		t := strings.TrimSpace(line)
		if t == "" || strings.HasPrefix(t, "#") {
			continue
		}
		f := strings.Fields(t)
		if len(f) < 2 || len(f) > 3 {
			return nil, fmt.Errorf("benchgate: baseline line %d: want `<name> <ns/op> [budget=<d>]`", n)
		}
		e := Entry{Name: f[0]}
		var err error
		if e.NsOp, err = strconv.ParseFloat(f[1], 64); err != nil || !validNs(e.NsOp) {
			return nil, fmt.Errorf("benchgate: baseline line %d: bad ns/op %q", n, f[1])
		}
		if len(f) == 3 {
			d, ok := strings.CutPrefix(f[2], "budget=")
			if !ok {
				return nil, fmt.Errorf("benchgate: baseline line %d: unknown field %q", n, f[2])
			}
			if e.Budget, err = time.ParseDuration(d); err != nil || e.Budget <= 0 {
				return nil, fmt.Errorf("benchgate: baseline line %d: bad budget %q", n, d)
			}
		}
		if _, dup := b.Entries[e.Name]; dup {
			return nil, fmt.Errorf("benchgate: baseline line %d: duplicate %s", n, e.Name)
		}
		b.Entries[e.Name] = e
	}
	return b, sc.Err()
}

// Result is the verdict of one comparison.
type Result struct {
	Lines []string // protocol lines, sorted by benchmark name
	Fail  bool
}

// Compare judges cur against base under mode. An empty cur always fails
// (BENCH_EMPTY): a run that measured nothing proves nothing.
func Compare(cur map[string]float64, base *Baseline, mode Mode) Result {
	var r Result
	if len(cur) == 0 {
		return Result{Lines: []string{"BENCH_EMPTY:"}, Fail: true}
	}
	// ParseBench and ParseBaseline never yield a non-finite or non-positive
	// timing; a caller that builds either side by hand gets a failure, not
	// the vacuous pass NaN or Inf would produce in the ratio test.
	for _, n := range slices.Sorted(maps.Keys(cur)) {
		if !validNs(cur[n]) {
			return Result{Lines: []string{"BENCH_INVALID:" + n + "|" + fmtNs(cur[n])}, Fail: true}
		}
	}
	for _, n := range slices.Sorted(maps.Keys(base.Entries)) {
		if e := base.Entries[n]; !validNs(e.NsOp) {
			return Result{Lines: []string{"BENCH_INVALID:" + n + "|" + fmtNs(e.NsOp)}, Fail: true}
		}
	}
	names := slices.Sorted(maps.Keys(cur))
	for _, n := range slices.Sorted(maps.Keys(base.Entries)) {
		if _, ok := cur[n]; !ok {
			names = append(names, n)
		}
	}
	slices.Sort(names)
	for _, n := range names {
		ns, measured := cur[n]
		e, known := base.Entries[n]
		switch {
		case !measured:
			r.Lines = append(r.Lines, "BENCH_MISSING:"+n)
			if mode == Full {
				r.Fail = true
			}
		case !known:
			r.Lines = append(r.Lines, fmt.Sprintf("BENCH_NEW:%s|%s", n, fmtNs(ns)))
		default:
			bad := false
			if ratio := ns / e.NsOp; ratio > Factor {
				r.Lines = append(r.Lines, fmt.Sprintf("BENCH_REGRESSION:%s|%s|%s|%.2f", n, fmtNs(ns), fmtNs(e.NsOp), ratio))
				bad = true
			}
			if e.Budget > 0 && time.Duration(ns) > e.Budget {
				r.Lines = append(r.Lines, fmt.Sprintf("BENCH_OVER_BUDGET:%s|%s|%s", n, fmtNs(ns), e.Budget))
				bad = true
			}
			if bad {
				r.Fail = true
			} else {
				r.Lines = append(r.Lines, fmt.Sprintf("BENCH_OK:%s|%s|%s", n, fmtNs(ns), fmtNs(e.NsOp)))
			}
		}
	}
	return r
}

func fmtNs(ns float64) string { return strconv.FormatFloat(ns, 'f', -1, 64) }

// Rewrite returns the baseline file re-recorded from cur: measured
// benchmarks get their new ns/op (budgets kept), unmeasured ones are
// dropped, new ones are appended, comments and blank lines stay.
func (b *Baseline) Rewrite(cur map[string]float64) string {
	var sb strings.Builder
	seen := map[string]bool{}
	for _, line := range b.lines {
		t := strings.TrimSpace(line)
		if t == "" || strings.HasPrefix(t, "#") {
			sb.WriteString(line + "\n")
			continue
		}
		name := strings.Fields(t)[0]
		ns, ok := cur[name]
		if !ok {
			continue
		}
		seen[name] = true
		sb.WriteString(entryLine(name, ns, b.Entries[name].Budget))
	}
	for _, n := range slices.Sorted(maps.Keys(cur)) {
		if !seen[n] {
			sb.WriteString(entryLine(n, cur[n], 0))
		}
	}
	return sb.String()
}

func entryLine(name string, ns float64, budget time.Duration) string {
	s := name + " " + fmtNs(ns) // full precision: 0.4 must not round to 0
	if budget > 0 {
		s += " budget=" + budget.String()
	}
	return s + "\n"
}
