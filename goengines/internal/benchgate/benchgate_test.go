package benchgate

import (
	"fmt"
	"math"
	"strings"
	"testing"
	"time"
)

const out = `goos: linux
goarch: amd64
pkg: example.com/m/internal/a
cpu: Some CPU
BenchmarkX-24          	   10000	    100000 ns/op	  12 B/op	   1 allocs/op
BenchmarkX/sub-case-8  	   10000	       500 ns/op
BenchmarkNoProcs       	   10000	      7.5 ns/op
PASS
ok  	example.com/m/internal/a	1.2s
pkg: example.com/m/internal/b
BenchmarkX-24          	   10000	    200000 ns/op
BenchmarkX-24          	   10000	    190000 ns/op
PASS
`

func TestParseBench(t *testing.T) {
	got, err := ParseBench(strings.NewReader(out), "example.com/m/")
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]float64{
		"internal/a.BenchmarkX":          100000,
		"internal/a.BenchmarkX/sub-case": 500,
		"internal/a.BenchmarkNoProcs":    7.5,
		"internal/b.BenchmarkX":          190000, // -count > 1 keeps the minimum
	}
	if len(got) != len(want) {
		t.Fatalf("got %v", got)
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("%s = %v, want %v", k, got[k], v)
		}
	}
}

func baseline(t *testing.T, s string) *Baseline {
	t.Helper()
	b, err := ParseBaseline(strings.NewReader(s))
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestParseBaselineErrors(t *testing.T) {
	for _, s := range []string{
		"a\n", "a x\n", "a 0\n", "a -1\n", "a NaN\n", "a nan\n", "a +Inf\n", "a Inf\n", "a -Inf\n",
		"a 1 2\n", "a 1 budget=nope\n", "a 1\na 2\n",
	} {
		if _, err := ParseBaseline(strings.NewReader(s)); err == nil {
			t.Errorf("%q accepted", s)
		}
	}
}

func TestCompareFactor(t *testing.T) {
	b := baseline(t, "# c\np.BenchmarkA 1000\n")
	if r := Compare(map[string]float64{"p.BenchmarkA": 1900}, b, Full); r.Fail {
		t.Fatalf("1.9x failed: %v", r.Lines)
	}
	r := Compare(map[string]float64{"p.BenchmarkA": 2100}, b, Full)
	if !r.Fail || !strings.HasPrefix(r.Lines[0], "BENCH_REGRESSION:p.BenchmarkA|2100|1000|2.10") {
		t.Fatalf("2.1x: %v", r.Lines)
	}
}

func TestCompareBudget(t *testing.T) {
	b := baseline(t, "p.BenchmarkA 1000000 budget=1.5ms\n")
	r := Compare(map[string]float64{"p.BenchmarkA": 1600000}, b, Full)
	if !r.Fail || r.Lines[0] != "BENCH_OVER_BUDGET:p.BenchmarkA|1600000|1.5ms" {
		t.Fatalf("%v", r.Lines)
	}
}

func TestCompareMissingNewEmpty(t *testing.T) {
	b := baseline(t, "p.BenchmarkA 1000\np.BenchmarkGone 1000\n")
	cur := map[string]float64{"p.BenchmarkA": 1000, "p.BenchmarkNew": 5}
	full := Compare(cur, b, Full)
	if !full.Fail || strings.Join(full.Lines, ",") != "BENCH_OK:p.BenchmarkA|1000|1000,BENCH_MISSING:p.BenchmarkGone,BENCH_NEW:p.BenchmarkNew|5" {
		t.Fatalf("full: %+v", full)
	}
	if part := Compare(cur, b, Partial); part.Fail {
		t.Fatalf("partial must not fail on missing: %+v", part)
	}
	for _, m := range []Mode{Full, Partial} {
		if e := Compare(map[string]float64{}, b, m); !e.Fail || e.Lines[0] != "BENCH_EMPTY:" {
			t.Fatalf("%s empty: %+v", m, e)
		}
	}
}

func TestRewrite(t *testing.T) {
	b := baseline(t, "# header\n\np.BenchmarkA 1000 budget=2ms\np.BenchmarkGone 5\n")
	got := b.Rewrite(map[string]float64{"p.BenchmarkA": 1234.6, "p.BenchmarkNew": 7})
	want := "# header\n\np.BenchmarkA 1234.6 budget=2ms\np.BenchmarkNew 7\n"
	if got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}

// The acceptance for the 2× rule on real measurements: a sleep-based fixture
// sets the baseline, the same fixture re-measured passes, and a slowed copy
// (3× the sleep) fails. Sleeps dominate the measurement, so the ratios (~1
// and ~3) sit far from the 2.0 line on any machine.
func TestSlowedFixtureFailsTwoX(t *testing.T) {
	if testing.Short() {
		t.Skip("measures real benchmarks")
	}
	fixture := func(d time.Duration) func(*testing.B) {
		return func(b *testing.B) {
			for b.Loop() {
				time.Sleep(d)
			}
		}
	}
	measure := func(d time.Duration) float64 {
		return float64(testing.Benchmark(fixture(d)).NsPerOp())
	}
	base := baseline(t, fmt.Sprintf("p.BenchmarkFixture %.0f\n", measure(time.Millisecond)))
	if r := Compare(map[string]float64{"p.BenchmarkFixture": measure(time.Millisecond)}, base, Full); r.Fail {
		t.Fatalf("unchanged fixture failed: %v", r.Lines)
	}
	r := Compare(map[string]float64{"p.BenchmarkFixture": measure(3 * time.Millisecond)}, base, Full)
	if !r.Fail || !strings.HasPrefix(r.Lines[0], "BENCH_REGRESSION:p.BenchmarkFixture|") {
		t.Fatalf("slowed fixture passed: %v", r.Lines)
	}
}

func TestParseBenchRejectsNonFinite(t *testing.T) {
	for _, v := range []string{"NaN", "+Inf", "Inf", "0", "-5"} {
		in := "pkg: m/p\nBenchmarkA-8 10 " + v + " ns/op\n"
		if got, err := ParseBench(strings.NewReader(in), "m/"); err == nil {
			t.Errorf("%s accepted: %v", v, got)
		}
	}
}

// A non-finite value must never reach the ratio test: NaN compares false and
// x/Inf is 0, so either would read as BENCH_OK.
func TestCompareRejectsNonFinite(t *testing.T) {
	b := baseline(t, "p.BenchmarkA 1000\n")
	for _, v := range []float64{math.NaN(), math.Inf(1), 0, -1} {
		r := Compare(map[string]float64{"p.BenchmarkA": v}, b, Full)
		if !r.Fail || !strings.HasPrefix(r.Lines[0], "BENCH_INVALID:p.BenchmarkA|") {
			t.Errorf("%v: %+v", v, r)
		}
	}
	// And the baseline side, if one were constructed by hand.
	hand := &Baseline{Entries: map[string]Entry{"p.BenchmarkA": {Name: "p.BenchmarkA", NsOp: math.Inf(1)}}}
	if r := Compare(map[string]float64{"p.BenchmarkA": 1e6}, hand, Full); !r.Fail {
		t.Errorf("Inf baseline passed: %+v", r)
	}
}

// Sub-nanosecond and fractional timings survive a rewrite and read back.
func TestRewriteKeepsPrecision(t *testing.T) {
	b := baseline(t, "p.BenchmarkA 1\n")
	out := b.Rewrite(map[string]float64{"p.BenchmarkA": 0.4, "p.BenchmarkB": 1234.56})
	if out != "p.BenchmarkA 0.4\np.BenchmarkB 1234.56\n" {
		t.Fatalf("rewrite %q", out)
	}
	back := baseline(t, out)
	if back.Entries["p.BenchmarkA"].NsOp != 0.4 || back.Entries["p.BenchmarkB"].NsOp != 1234.56 {
		t.Fatalf("read back %+v", back.Entries)
	}
}
