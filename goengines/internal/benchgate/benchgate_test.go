package benchgate

import (
	"fmt"
	"math"
	"slices"
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

// calLine records a calibration of 100 ns/op; with calibrated() on the
// current side the scale is exactly 1.
const calLine = Calibration + " 100\n"

// calibrated returns cur plus a calibration measurement of calNs.
func calibrated(calNs float64, cur map[string]float64) map[string]float64 {
	out := map[string]float64{Calibration: calNs}
	for k, v := range cur {
		out[k] = v
	}
	return out
}

func TestParseBaselineErrors(t *testing.T) {
	for _, s := range []string{
		"a\n", "a x\n", "a 0\n", "a -1\n", "a NaN\n", "a nan\n", "a +Inf\n", "a Inf\n", "a -Inf\n",
		"a 1 2\n", "a 1 budget=nope\n", "a 1\na 2\n",
		"a 1 cal=gpu\n", "a 1 cal=\n", "a 1 cal=spawn cal=cpu\n", "a 1 budget=1ms budget=2ms\n",
		"a 1 budget=1ms cal=spawn x\n", Calibration + " 1 cal=spawn\n",
	} {
		if _, err := ParseBaseline(strings.NewReader(s)); err == nil {
			t.Errorf("%q accepted", s)
		}
	}
}

func TestCompareThreshold(t *testing.T) {
	if !(Threshold > 1 && Threshold < Factor) {
		t.Fatalf("Threshold %v must sit between 1 and Factor %v", Threshold, Factor)
	}
	b := baseline(t, "# c\n"+calLine+"p.BenchmarkA 1000\n")
	if r := Compare(calibrated(100, map[string]float64{"p.BenchmarkA": 1590}), b, Full); r.Fail {
		t.Fatalf("1.59x failed: %v", r.Lines)
	}
	r := Compare(calibrated(100, map[string]float64{"p.BenchmarkA": 1610}), b, Full)
	if !r.Fail || r.Lines[0] != "BENCH_SCALE:cpu|1.000|100|100" || r.Lines[1] != "BENCH_REGRESSION:p.BenchmarkA|1610|1000|1.61" {
		t.Fatalf("1.61x: %v", r.Lines)
	}
	// Every Factor-times regression fails.
	if r := Compare(calibrated(100, map[string]float64{"p.BenchmarkA": 1000 * Factor}), b, Full); !r.Fail {
		t.Fatalf("%vx passed: %v", Factor, r.Lines)
	}
}

func TestCompareBudget(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000000 budget=1.5ms\n")
	r := Compare(calibrated(100, map[string]float64{"p.BenchmarkA": 1600000}), b, Full)
	if !r.Fail || r.Lines[1] != "BENCH_OVER_BUDGET:p.BenchmarkA|1600000|1.5ms" {
		t.Fatalf("%v", r.Lines)
	}
}

func TestCompareMissingNewEmpty(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000\np.BenchmarkGone 1000\n")
	cur := calibrated(100, map[string]float64{"p.BenchmarkA": 1000, "p.BenchmarkNew": 5})
	full := Compare(cur, b, Full)
	if !full.Fail || strings.Join(full.Lines, ",") != "BENCH_SCALE:cpu|1.000|100|100,BENCH_OK:p.BenchmarkA|1000|1000,BENCH_MISSING:p.BenchmarkGone,BENCH_NEW:p.BenchmarkNew|5" {
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
	b := baseline(t, "# header\n\np.BenchmarkA 1000 budget=2ms\np.BenchmarkS 9 cal=spawn budget=1s\np.BenchmarkGone 5\n")
	got := b.Rewrite(map[string]float64{"p.BenchmarkA": 1234.6, "p.BenchmarkS": 8, "p.BenchmarkNew": 7})
	want := "# header\n\np.BenchmarkA 1234.6 budget=2ms\np.BenchmarkS 8 budget=1s cal=spawn\np.BenchmarkNew 7\n"
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
	// Same host on both sides: the calibration is held at scale 1 so the
	// sleep ratios alone decide.
	base := baseline(t, calLine+fmt.Sprintf("p.BenchmarkFixture %.0f\n", measure(time.Millisecond)))
	if r := Compare(calibrated(100, map[string]float64{"p.BenchmarkFixture": measure(time.Millisecond)}), base, Full); r.Fail {
		t.Fatalf("unchanged fixture failed: %v", r.Lines)
	}
	r := Compare(calibrated(100, map[string]float64{"p.BenchmarkFixture": measure(3 * time.Millisecond)}), base, Full)
	if !r.Fail || !strings.HasPrefix(r.Lines[1], "BENCH_REGRESSION:p.BenchmarkFixture|") {
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

// The host-normalization acceptance: a uniformly slower host passes, a
// genuine regression still fails on any host, and a faster host no longer
// masks one.
func TestCalibrationScalesSlowHost(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000\np.BenchmarkB 5000\n")
	r := Compare(calibrated(200, map[string]float64{"p.BenchmarkA": 2000, "p.BenchmarkB": 10000}), b, Full)
	if r.Fail || strings.Join(r.Lines, ",") != "BENCH_SCALE:cpu|2.000|200|100,BENCH_OK:p.BenchmarkA|2000|1000,BENCH_OK:p.BenchmarkB|10000|5000" {
		t.Fatalf("%+v", r)
	}
	// Control: at scale 1 a 3.9x slowdown fails, so the pass above is the
	// scale's doing.
	r = Compare(calibrated(100, map[string]float64{"p.BenchmarkA": 3900, "p.BenchmarkB": 10000}), b, Full)
	if !r.Fail {
		t.Fatalf("unscaled 3.9x passed: %+v", r)
	}
}

func TestCalibrationCatchesRegression(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000\n")
	for _, c := range []struct{ cal, ns float64 }{
		{100, 2500}, // same host, 2.5x
		{200, 5000}, // 2x slower host, 5x slower bench = 2.5x scaled
	} {
		r := Compare(calibrated(c.cal, map[string]float64{"p.BenchmarkA": c.ns}), b, Full)
		if !r.Fail || !strings.HasPrefix(r.Lines[1], "BENCH_REGRESSION:p.BenchmarkA|") || !strings.HasSuffix(r.Lines[1], "|2.50") {
			t.Errorf("cal %v ns %v: %+v", c.cal, c.ns, r)
		}
	}
}

func TestCalibrationFastHostUnmasks(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000\n")
	// 1.2x raw would pass; on a 2x faster host it is a 2.4x regression.
	r := Compare(calibrated(50, map[string]float64{"p.BenchmarkA": 1200}), b, Full)
	if !r.Fail || r.Lines[0] != "BENCH_SCALE:cpu|0.500|50|100" || r.Lines[1] != "BENCH_REGRESSION:p.BenchmarkA|1200|1000|2.40" {
		t.Fatalf("%+v", r)
	}
}

func TestCalibrationMissing(t *testing.T) {
	withCal := baseline(t, calLine+"p.BenchmarkA 1000\n")
	noCal := baseline(t, "p.BenchmarkA 1000\n")
	for _, c := range []struct {
		side string
		base *Baseline
		cur  map[string]float64
	}{
		{"baseline", noCal, calibrated(100, map[string]float64{"p.BenchmarkA": 1000})},
		{"current", withCal, map[string]float64{"p.BenchmarkA": 1000}},
	} {
		full := Compare(c.cur, c.base, Full)
		if !full.Fail || full.Lines[0] != "BENCH_CALIBRATION_MISSING:cpu|"+c.side {
			t.Errorf("full %s: %+v", c.side, full)
		}
		part := Compare(c.cur, c.base, Partial)
		if part.Fail || part.Lines[0] != "BENCH_UNSCALED:cpu|"+c.side {
			t.Errorf("partial %s: %+v", c.side, part)
		}
		// The calibration is never judged as a benchmark of its own.
		for _, l := range append(full.Lines, part.Lines...) {
			if strings.Contains(l, "BenchmarkCalibrate") {
				t.Errorf("%s: calibration judged as a benchmark: %q", c.side, l)
			}
		}
	}
}

func TestCalibrationImplausible(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000\n")
	for _, c := range []struct {
		cal  float64
		line string
	}{
		{500, "BENCH_SCALE_IMPLAUSIBLE:cpu|5.000|500|100"},
		{20, "BENCH_SCALE_IMPLAUSIBLE:cpu|0.200|20|100"},
	} {
		for _, m := range []Mode{Full, Partial} {
			r := Compare(calibrated(c.cal, map[string]float64{"p.BenchmarkA": 1000}), b, m)
			if !r.Fail || r.Lines[0] != c.line {
				t.Errorf("%s cal %v: %+v", m, c.cal, r)
			}
		}
	}
	// The bounds themselves are plausible.
	for _, cal := range []float64{100 * MinScale, 100 * MaxScale} {
		if r := Compare(calibrated(cal, map[string]float64{"p.BenchmarkA": cal * 10}), b, Full); r.Fail {
			t.Errorf("bound %v: %+v", cal, r)
		}
	}
}

func TestBudgetNotScaled(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000000 budget=1.5ms\n")
	for _, c := range []struct{ cal, ns float64 }{
		{50, 1600000},  // fast host: 3.2x scaled regression aside, over budget
		{200, 1600000}, // slow host: fine scaled (0.8x), still over budget
	} {
		r := Compare(calibrated(c.cal, map[string]float64{"p.BenchmarkA": c.ns}), b, Full)
		if !r.Fail || !slices.Contains(r.Lines, "BENCH_OVER_BUDGET:p.BenchmarkA|1600000|1.5ms") {
			t.Errorf("cal %v: %+v", c.cal, r)
		}
	}
}

func TestEmptyExceptCalibration(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000\n")
	for _, m := range []Mode{Full, Partial} {
		if r := Compare(map[string]float64{Calibration: 100}, b, m); !r.Fail || strings.Join(r.Lines, ",") != "BENCH_EMPTY:" {
			t.Errorf("%s: %+v", m, r)
		}
	}
}

func TestCalibrateIsCPUBound(t *testing.T) {
	if testing.Short() {
		t.Skip("measures a real benchmark")
	}
	r := testing.Benchmark(BenchmarkCalibrate)
	if r.AllocsPerOp() != 0 || !validNs(float64(r.NsPerOp())) {
		t.Fatalf("allocs/op %d ns/op %d", r.AllocsPerOp(), r.NsPerOp())
	}
}

// Workload-matched normalization: a process-bound benchmark (cal=spawn) is
// scaled by the spawn calibration, not the CPU one. On a host whose CPU work
// slowed 3x but whose process spawns slowed only 1.5x, CPU scaling would hide
// a 2.1x regression of the spawn-bound benchmark (3150 / (1000 × 3) = 1.05).
func TestSpawnClassScalesSeparately(t *testing.T) {
	b := baseline(t, calLine+CalibrationSpawn+" 100\np.BenchmarkA 1000\np.BenchmarkL 1000 cal=spawn\n")
	host := func(a, l float64) map[string]float64 {
		return map[string]float64{Calibration: 300, CalibrationSpawn: 150, "p.BenchmarkA": a, "p.BenchmarkL": l}
	}
	r := Compare(host(3000, 1500), b, Full)
	if r.Fail || strings.Join(r.Lines, ",") != "BENCH_SCALE:cpu|3.000|300|100,BENCH_SCALE:spawn|1.500|150|100,BENCH_OK:p.BenchmarkA|3000|1000,BENCH_OK:p.BenchmarkL|1500|1000" {
		t.Fatalf("healthy: %+v", r)
	}
	r = Compare(host(3000, 3150), b, Full)
	if !r.Fail || !slices.Contains(r.Lines, "BENCH_REGRESSION:p.BenchmarkL|3150|1000|2.10") {
		t.Fatalf("2.1x spawn-bound regression masked: %+v", r)
	}
}

func TestSpawnCalibrationRequiredOnlyWhenUsed(t *testing.T) {
	uses := baseline(t, calLine+"p.BenchmarkL 1000 cal=spawn\n")
	cur := calibrated(100, map[string]float64{"p.BenchmarkL": 1000})
	if r := Compare(cur, uses, Full); !r.Fail || !slices.Contains(r.Lines, "BENCH_CALIBRATION_MISSING:spawn|baseline") {
		t.Errorf("used class without its calibration passed: %+v", r)
	}
	if r := Compare(cur, uses, Partial); r.Fail || !slices.Contains(r.Lines, "BENCH_UNSCALED:spawn|baseline") {
		t.Errorf("partial: %+v", r)
	}
	unused := baseline(t, calLine+"p.BenchmarkA 1000\n")
	if r := Compare(calibrated(100, map[string]float64{"p.BenchmarkA": 1000}), unused, Full); r.Fail || len(r.Lines) != 2 {
		t.Errorf("unused class resolved: %+v", r)
	}
	// A measured spawn calibration no line uses is neither judged nor new.
	r := Compare(calibrated(100, map[string]float64{CalibrationSpawn: 7, "p.BenchmarkA": 1000}), unused, Full)
	if r.Fail || strings.Contains(strings.Join(r.Lines, ","), "Spawn") {
		t.Errorf("unused spawn calibration judged: %+v", r)
	}
}

// Every class names a distinct calibration benchmark, and every calibration
// is recognized as one (never judged by the 2× rule, never BENCH_NEW).
func TestCalibrationsTable(t *testing.T) {
	seen := map[string]bool{}
	for class, name := range Calibrations {
		if seen[name] || !isCalibration(name) || !strings.HasPrefix(name, "internal/benchgate.BenchmarkCalibrate") {
			t.Errorf("class %s: bad calibration %q", class, name)
		}
		seen[name] = true
	}
	if Calibrations[DefaultClass] != Calibration || Calibrations["spawn"] != CalibrationSpawn || Calibrations["sha1"] != CalibrationHash {
		t.Errorf("table %v", Calibrations)
	}
	b := baseline(t, calLine+CalibrationHash+" 100\np.BenchmarkD 1000 cal=sha1\n")
	r := Compare(map[string]float64{Calibration: 100, CalibrationHash: 50, "p.BenchmarkD": 1100}, b, Full)
	if !r.Fail || !slices.Contains(r.Lines, "BENCH_SCALE:sha1|0.500|50|100") || !slices.Contains(r.Lines, "BENCH_REGRESSION:p.BenchmarkD|1100|1000|2.20") {
		t.Errorf("sha1 class: %+v", r)
	}
}

func TestRequiredClasses(t *testing.T) {
	b := baseline(t, calLine+"p.BenchmarkA 1000\np.BenchmarkL 1000 cal=spawn\n")
	if got := b.RequiredClasses(map[string]float64{"p.BenchmarkA": 1}); !slices.Equal(got, []string{"cpu"}) {
		t.Errorf("A only: %v", got)
	}
	if got := b.RequiredClasses(map[string]float64{"p.BenchmarkL": 1}); !slices.Equal(got, []string{"cpu", "spawn"}) {
		t.Errorf("L measured: %v", got)
	}
}
