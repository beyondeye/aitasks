package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"syscall"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/runner"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/seam"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// The bench follows amendment A3 of the t1954_1 plan:
//   - the ONLY budget-comparable operation is what annot.BenchmarkScan times:
//     registry.Scan with the annotation source over the regenerated M2.2
//     bench shape; a provider enters through ClassifyHook;
//   - lexical-only timings (Analyze+ToContext / Classify over preloaded bytes)
//     are a separate table, never compared with the scan budget;
//   - cold = ONE timed first operation in a fresh process, the timer started
//     before provider construction (no benchmark calibration); warm = a
//     separate process, an untimed warm-up, then testing.Benchmark; both
//     pinned with taskset -c 0, fastest of 3 processes; peak RSS from the
//     child's rusage (and its own children's, for subprocess providers).

const budget = 300 * time.Millisecond

type emptyLister struct{}

func (emptyLister) List(context.Context, string) ([]registry.Listing, error) { return nil, nil }

// benchSubjects are the end-to-end configurations: each provider for its
// languages with the landed lexer for the rest, and the native composite.
var benchSubjects = []string{"baseline", "pytokenize", "shfmt", "native"}

// lexSubjects are the lexical-only subjects.
var lexSubjects = []string{"baseline", "goscanner", "pytokenize", "shfmt"}

func benchSubject(name string) (runner.Subject, error) {
	switch name {
	case "baseline":
		return runner.Baseline, nil
	case "native":
		c, err := provider.NewComposite()
		if err != nil {
			return runner.Subject{}, err
		}
		return runner.Subject{Name: name, P: c, Delegate: true}, nil
	}
	p, err := provider.New(name)
	if err != nil {
		return runner.Subject{}, err
	}
	return runner.Subject{Name: name, P: p, Delegate: true}, nil
}

// writeM22Shape regenerates annot/bench_test.go's workload: ≈420 annotated
// test files (¼ Python), 600 sources, 1,000 docs, untracked in a fresh repo.
func writeM22Shape(dir string) error {
	w := func(rel, body string) error {
		p := filepath.Join(dir, rel)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			return err
		}
		return os.WriteFile(p, []byte(body), 0o644)
	}
	if out, err := exec.Command("git", "init", "-q", dir).CombinedOutput(); err != nil {
		return fmt.Errorf("git init: %v %s", err, out)
	}
	if err := w(registry.ConfigPath, "contract: 1\n"); err != nil {
		return err
	}
	for i := range 600 {
		if err := w(fmt.Sprintf("src/lib%d/s%d.sh", i%20, i), "echo source\n"); err != nil {
			return err
		}
	}
	for i := range 420 {
		var body strings.Builder
		body.WriteString("#!/usr/bin/env bash\n# A test header.\n#\n")
		for k := range 1 + i%3 {
			fmt.Fprintf(&body, "# testmap:covers src/lib%d/s%d.sh @2026-01-01/0123456789\n", (i+k)%20, (i*7+k)%600)
		}
		body.WriteString("set -euo pipefail\nsource \"$(dirname \"$0\")/lib/asserts.sh\"\n")
		if i%20 == 0 {
			body.WriteString("# testmap:unit Alpha\n# testmap:covers src/lib0/s0.sh\nalpha() { :; }\n")
		}
		for range 40 {
			body.WriteString("assert_eq \"x\" \"$(echo x)\" \"$(cat <<EOF\nx\nEOF\n)\"\n")
		}
		ext := ".sh"
		if i%4 == 0 {
			ext = ".py"
			body.Reset()
			fmt.Fprintf(&body, "\"\"\"Test %d.\"\"\"\n# testmap:covers src/lib1/s%d.sh\nimport unittest\n", i, i%600)
			for range 40 {
				body.WriteString("x = f\"{1}\" + '#' + \"\"\"a\"\"\"\n")
			}
		}
		if err := w(fmt.Sprintf("tests/test_%d%s", i, ext), body.String()); err != nil {
			return err
		}
	}
	for i := range 1000 {
		if err := w(fmt.Sprintf("docs/d%d/page%d.md", i%30, i), "# Title\n\nText.\n"); err != nil {
			return err
		}
	}
	return nil
}

// lexSet is a named list of files for the lexical-only table.
type lexSet struct {
	Name  string
	Files []string
}

func testFiles(repo string) ([]string, error) {
	out, err := exec.Command("git", "-C", repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard").Output()
	if err != nil {
		return nil, err
	}
	var files []string
	for _, f := range strings.Split(strings.TrimRight(string(out), "\x00"), "\x00") {
		b := filepath.Base(f)
		isTest := strings.HasPrefix(b, "test_") || strings.HasSuffix(b, "_test.go") || strings.HasSuffix(strings.TrimSuffix(b, filepath.Ext(b)), "_test") ||
			strings.HasSuffix(b, "Test.kt")
		if !isTest || strings.Contains(f, "/.baseline") {
			continue
		}
		switch filepath.Ext(b) {
		case ".sh", ".py", ".go", ".kt":
			files = append(files, filepath.Join(repo, f))
		}
	}
	sort.Strings(files)
	return files, nil
}

type childResult struct {
	NS       int64  `json:"ns"`
	Files    int    `json:"files"`
	Err      string `json:"err,omitempty"`
	SelfRSS  int64  `json:"self_rss_kib"`  // RUSAGE_SELF of the bench child: the harness process itself
	ChildRSS int64  `json:"child_rss_kib"` // RUSAGE_CHILDREN of the bench child: git ls-files (scan), python (pytokenize)
}

type sample struct {
	ns            int64
	rss, childRSS int64
	err           string
}

func runChild(args []string) sample {
	self, _ := os.Executable()
	cmd := exec.Command("taskset", append([]string{"-c", "0", self, "bench-child"}, args...)...)
	if _, err := exec.LookPath("taskset"); err != nil {
		cmd = exec.Command(self, append([]string{"bench-child"}, args...)...)
	}
	cmd.Stderr = os.Stderr
	out, err := cmd.Output()
	s := sample{}
	if err != nil {
		s.err = err.Error()
		return s
	}
	var r childResult
	if jerr := json.Unmarshal(out, &r); jerr != nil {
		s.err = jerr.Error() + ": " + string(out)
		return s
	}
	s.ns, s.rss, s.childRSS, s.err = r.NS, r.SelfRSS, r.ChildRSS, r.Err
	return s
}

// best is the fastest sample's time with the peak RSS over ALL samples
// (the RSS maxima are tracked independently of which sample was fastest).
func best(ss []sample) (sample, []int64) {
	var all []int64
	ns, rss, childRSS := int64(-1), int64(0), int64(0)
	for _, s := range ss {
		if s.err != "" {
			return s, nil
		}
		all = append(all, s.ns)
		if ns < 0 || s.ns < ns {
			ns = s.ns
		}
		rss, childRSS = max(rss, s.rss), max(childRSS, s.childRSS)
	}
	return sample{ns: ns, rss: rss, childRSS: childRSS}, all
}

func ms(ns int64) string { return fmt.Sprintf("%.1f ms", float64(ns)/1e6) }

func cmdBench(args []string) int {
	fs := flag.NewFlagSet("bench", flag.ExitOnError)
	out := fs.String("out", "results/bench.md", "output file")
	runs := fs.Int("runs", 3, "fresh processes per measurement")
	siblings := fs.String("siblings", "aitasks_go,aitasks_mobile,thinking_app,thinking_backend,timexchange", "registered sibling projects for the lexical-only sets (read-only)")
	_ = fs.Parse(args)
	tmp, err := os.MkdirTemp("", "t1954-bench-")
	if err != nil {
		fail(1, err)
	}
	defer os.RemoveAll(tmp)
	shape := filepath.Join(tmp, "m22")
	if err := writeM22Shape(shape); err != nil {
		fail(1, err)
	}
	// Lexical sets: the M2.2 shape's test files, aitasks' test files, each sibling's.
	var sets []lexSet
	m22Files, _ := filepath.Glob(filepath.Join(shape, "tests", "*"))
	sort.Strings(m22Files)
	sets = append(sets, lexSet{"M2.2 shape tests (420)", m22Files})
	top, _ := exec.Command("git", "-C", id.Root, "rev-parse", "--show-toplevel").Output()
	if f, err := testFiles(strings.TrimSpace(string(top))); err == nil {
		sets = append(sets, lexSet{"aitasks test files", f})
	}
	for _, n := range strings.Split(*siblings, ",") {
		if n == "" {
			continue
		}
		p, err := exec.Command(filepath.Join(strings.TrimSpace(string(top)), "ait"), "projects", "resolve", n).Output()
		path := strings.TrimPrefix(strings.TrimSpace(string(p)), "RESOLVED:")
		if err != nil || path == "" {
			sets = append(sets, lexSet{Name: n + " test files (unresolved)"})
			continue
		}
		if f, err := testFiles(path); err == nil {
			sets = append(sets, lexSet{n + " test files", f})
		}
	}
	var b strings.Builder
	fmt.Fprintf(&b, "# Performance (t1954_1)\n\n%s\n\n", id.Header())
	fmt.Fprintf(&b, "Method (plan amendment A3): `taskset -c 0`; fastest of %d fresh processes; **cold** = one timed first operation per fresh process, the timer started before provider construction (grammar/oracle start-up included, no benchmark calibration); **warm** = a separate process, an untimed warm-up, then `testing.Benchmark` (ns/op). \"Cold\" is a cold PROCESS and provider, not a cold page cache (the workload is written once beforehand). Peak RSS (KiB, Linux `ru_maxrss`): the measured process itself (`RUSAGE_SELF`), and separately its subprocesses (`RUSAGE_CHILDREN`: `git ls-files` inside the scan, the Python oracle for pytokenize). The subprocess figure is an UPPER BOUND, not the subprocess's own working set: a forked child's `ru_maxrss` includes the pages it shares with the parent at fork, which is why the scan rows show the same value twice. Rerun: `go run ./cmd/t1954 bench`.\n\n", *runs)
	b.WriteString("## End-to-end scan — budget-comparable\n\n")
	b.WriteString("The operation `annot.BenchmarkScan` times: `registry.Scan(ctx, dir, Inputs{Annotations: annot.Source{}, Lister: emptyLister}, false)` over the regenerated M2.2 bench shape (420 annotated tests, ¼ Python; 600 sources; 1,000 docs; a fresh git repository). A provider enters through `ClassifyHook` for its languages; the landed lexer handles the others (named per row). Budget: 300 ms (proposal *Engine binary identity and budget*); the landed `annot.BenchmarkScan` baseline is ≈21 ms (`goengines/bench/baseline.txt`).\n\n")
	b.WriteString("| subject | languages via the subject | cold (fastest) | cold runs | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) | vs 300 ms budget |\n|---|---|---|---|---|---|---|\n")
	for _, s := range benchSubjects {
		var cold, warm []sample
		for range *runs {
			cold = append(cold, runChild([]string{"--mode", "cold", "--op", "scan", "--subject", s, "--dir", shape}))
		}
		for range *runs {
			warm = append(warm, runChild([]string{"--mode", "warm", "--op", "scan", "--subject", s, "--dir", shape}))
		}
		cb, call := best(cold)
		wb, _ := best(warm)
		langs := composition(s)
		if cb.err != "" || wb.err != "" {
			fmt.Fprintf(&b, "| %s | %s | error: %s | | %s | | not measured |\n", s, langs, esc(cb.err), esc(wb.err))
			continue
		}
		verdict := "within"
		if max(cb.ns, wb.ns) > budget.Nanoseconds() {
			verdict = "OVER"
		}
		var cr []string
		for _, n := range call {
			cr = append(cr, ms(n))
		}
		fmt.Fprintf(&b, "| %s | %s | %s | %s | %s | %d / %d | %s (cold %.1f×, warm %.1f×) |\n", s, langs, ms(cb.ns), strings.Join(cr, ", "), ms(wb.ns),
			max(cb.rss, wb.rss), max(cb.childRSS, wb.childRSS), verdict, float64(cb.ns)/float64(budget.Nanoseconds()), float64(wb.ns)/float64(budget.Nanoseconds()))
	}
	b.WriteString("\n## Lexical only — NOT comparable to the scan budget\n\n")
	b.WriteString("Analyze + ToContext (or the landed `annot.Classify`) over preloaded bytes; files read before the timer starts. A subject is timed only on the files of its own languages.\n\n")
	b.WriteString("| set | subject | files | cold (fastest) | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) |\n|---|---|---|---|---|---|\n")
	for _, set := range sets {
		if len(set.Files) == 0 {
			fmt.Fprintf(&b, "| %s | — | 0 | not measured | not measured | |\n", set.Name)
			continue
		}
		list := filepath.Join(tmp, "files.txt")
		_ = os.WriteFile(list, []byte(strings.Join(set.Files, "\n")), 0o644)
		for _, s := range lexSubjects {
			var cold, warm []sample
			for range *runs {
				cold = append(cold, runChild([]string{"--mode", "cold", "--op", "lex", "--subject", s, "--list", list}))
			}
			for range *runs {
				warm = append(warm, runChild([]string{"--mode", "warm", "--op", "lex", "--subject", s, "--list", list}))
			}
			cb, _ := best(cold)
			wb, _ := best(warm)
			if cb.err != "" || wb.err != "" {
				fmt.Fprintf(&b, "| %s | %s | | error: %s %s | | |\n", set.Name, s, esc(cb.err), esc(wb.err))
				continue
			}
			n := countFor(s, set.Files)
			if n == 0 {
				continue
			}
			fmt.Fprintf(&b, "| %s | %s | %d | %s | %s | %d / %d |\n", set.Name, s, n, ms(cb.ns), ms(wb.ns), max(cb.rss, wb.rss), max(cb.childRSS, wb.childRSS))
		}
	}
	if err := os.WriteFile(*out, []byte(b.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", *out)
	return 0
}

// composition describes, from the subject actually constructed, which
// languages it handles; every other language of the scan goes to the landed
// lexer. A subject that cannot be constructed says so.
func composition(name string) string {
	s, err := benchSubject(name)
	if err != nil {
		return "unavailable: " + err.Error()
	}
	if s.IsBaseline() {
		return "all (landed)"
	}
	var parts []string
	if c, ok := s.P.(*provider.Composite); ok {
		comp := c.Composition()
		var ls []string
		for l := range comp {
			ls = append(ls, l)
		}
		sort.Strings(ls)
		for _, l := range ls {
			parts = append(parts, l+": "+comp[l])
		}
	} else {
		for _, l := range s.P.Langs() {
			parts = append(parts, l+": "+s.P.Name())
		}
	}
	return strings.Join(parts, ", ") + "; others: landed"
}

func countFor(subject string, files []string) int {
	s, err := benchSubject(subject)
	if err != nil {
		return 0
	}
	n := 0
	for _, f := range files {
		l, ok := provider.LangOfPath(f, nil)
		if ok && s.Supports(l.Name) {
			n++
		}
	}
	return n
}

// cmdBenchChild is one measured process.
func cmdBenchChild(args []string) int {
	fs := flag.NewFlagSet("bench-child", flag.ExitOnError)
	mode := fs.String("mode", "cold", "cold|warm")
	op := fs.String("op", "scan", "scan|lex")
	subject := fs.String("subject", "baseline", "subject")
	dir := fs.String("dir", "", "scan: the workload repository")
	list := fs.String("list", "", "lex: file with one path per line")
	_ = fs.Parse(args)
	emit := func(r childResult) int {
		var ru syscall.Rusage
		if syscall.Getrusage(syscall.RUSAGE_SELF, &ru) == nil {
			r.SelfRSS = ru.Maxrss
		}
		if syscall.Getrusage(syscall.RUSAGE_CHILDREN, &ru) == nil {
			r.ChildRSS = ru.Maxrss
		}
		_ = json.NewEncoder(os.Stdout).Encode(r)
		return 0
	}
	// Preload for lex (untimed): only the files of the subject's languages.
	type item struct {
		lang string
		data []byte
	}
	var items []item
	if *op == "lex" {
		raw, err := os.ReadFile(*list)
		if err != nil {
			return emit(childResult{Err: err.Error()})
		}
		probe, _ := benchSubject(*subject)
		for _, f := range strings.Split(strings.TrimSpace(string(raw)), "\n") {
			data, err := os.ReadFile(f)
			if err != nil {
				continue
			}
			l, ok := provider.LangOfPath(f, data)
			if !ok || !probe.Supports(l.Name) {
				continue
			}
			items = append(items, item{l.Name, data})
		}
		provider.CloseAll()
	}
	runtime.GC()
	start := time.Now() // cold: provider construction is inside the timed region
	s, err := benchSubject(*subject)
	if err != nil {
		return emit(childResult{Err: err.Error()})
	}
	defer provider.CloseAll()
	var opErr error
	do := func() {
		switch *op {
		case "scan":
			var fails []string
			c, l := runnerHooks(s, &fails)
			opErr = seam.With(c, l, func() error {
				_, err := registry.Scan(context.Background(), *dir, registry.Inputs{Annotations: annot.Source{}, Lister: emptyLister{}}, false)
				return err
			})
			if opErr == nil && len(fails) > 0 {
				opErr = fmt.Errorf("provider refused %d file(s): %s", len(fails), fails[0])
			}
		case "lex":
			for _, it := range items {
				if _, err := runner.ContextOf(s, it.lang, it.data); err != nil {
					opErr = err
					return
				}
			}
		}
	}
	if *mode == "cold" {
		do()
		ns := time.Since(start).Nanoseconds()
		if opErr != nil {
			return emit(childResult{Err: opErr.Error()})
		}
		return emit(childResult{NS: ns, Files: len(items)})
	}
	do() // untimed warm-up
	if opErr != nil {
		return emit(childResult{Err: opErr.Error()})
	}
	testing.Init()
	res := testing.Benchmark(func(b *testing.B) {
		for b.Loop() {
			do()
		}
	})
	if opErr != nil {
		return emit(childResult{Err: opErr.Error()})
	}
	return emit(childResult{NS: res.NsPerOp(), Files: len(items)})
}
