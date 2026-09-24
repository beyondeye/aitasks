package main

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/benchgate"
)

// producer returns argv for a fake `go test -bench` that prints out and exits
// with code.
func producer(out string, code int) []string {
	return []string{"sh", "-c", `printf '%s' "$1"; exit "$2"`, "sh", out, strconv.Itoa(code)}
}

const calOut = "pkg: " + modulePrefix + "internal/benchgate\nBenchmarkCalibrate-8 100 500 ns/op\nPASS\n"

const benchOut = calOut + "pkg: " + modulePrefix + "internal/p\nBenchmarkA-8 100 1000 ns/op\nBenchmarkB-8 100 2000 ns/op\nPASS\n"

func writeBaseline(t *testing.T, s string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "baseline.txt")
	if err := os.WriteFile(p, []byte(s), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func gate(t *testing.T, args ...string) (int, string) {
	t.Helper()
	var out, errb bytes.Buffer
	code := run(args, &out, &errb)
	return code, out.String()
}

const fullBaseline = benchgate.Calibration + " 500\ninternal/p.BenchmarkA 1000\ninternal/p.BenchmarkB 2000\n"

func TestGatePasses(t *testing.T) {
	b := writeBaseline(t, fullBaseline)
	code, out := gate(t, append([]string{"-baseline", b, "--"}, producer(benchOut, 0)...)...)
	if code != 0 || !strings.HasPrefix(out, "BENCH_MODE:full\nBENCH_SCALE:cpu|1.000|500|500\n") || strings.Count(out, "BENCH_OK:") != 2 {
		t.Fatalf("code %d out %q", code, out)
	}
}

func TestGateMissingBaselineBench(t *testing.T) {
	b := writeBaseline(t, fullBaseline+"internal/p.BenchmarkRenamed 10\n")
	args := append([]string{"-baseline", b, "--"}, producer(benchOut, 0)...)
	code, out := gate(t, args...)
	if code != 1 || !strings.Contains(out, "BENCH_MISSING:internal/p.BenchmarkRenamed\n") {
		t.Fatalf("full: code %d out %q", code, out)
	}
	code, out = gate(t, append([]string{"-partial"}, args...)...)
	if code != 0 || !strings.HasPrefix(out, "BENCH_MODE:partial\n") || !strings.Contains(out, "BENCH_MISSING:") {
		t.Fatalf("partial: code %d out %q", code, out)
	}
}

func TestGateEmpty(t *testing.T) {
	b := writeBaseline(t, fullBaseline)
	for _, mode := range [][]string{nil, {"-partial"}} {
		args := append(append(mode, "-baseline", b, "--"), producer("PASS\n", 0)...)
		if code, out := gate(t, args...); code != 1 || !strings.Contains(out, "BENCH_EMPTY:") {
			t.Fatalf("%v: code %d out %q", mode, code, out)
		}
	}
}

func TestGateProducerFailure(t *testing.T) {
	b := writeBaseline(t, fullBaseline)
	code, out := gate(t, append([]string{"-baseline", b, "--"}, producer(benchOut, 2)...)...)
	if code != 1 || !strings.Contains(out, "BENCH_PRODUCER_FAILED:2\n") || strings.Contains(out, "BENCH_OK") {
		t.Fatalf("code %d out %q", code, out)
	}
}

func TestUpdate(t *testing.T) {
	orig := "# keep\n" + benchgate.Calibration + " 400\ninternal/p.BenchmarkA 1 budget=1s\n"
	b := writeBaseline(t, orig)
	// A failed producer must leave the baseline byte-identical.
	if code, _ := gate(t, append([]string{"-update", "-baseline", b, "--"}, producer(benchOut, 2)...)...); code != 1 {
		t.Fatalf("update after failed producer: code %d", code)
	}
	if got, _ := os.ReadFile(b); string(got) != orig {
		t.Fatalf("baseline changed: %q", got)
	}
	if code, _ := gate(t, "-update", "-partial", "-baseline", b); code != 64 {
		t.Fatalf("-update -partial: code %d", code)
	}
	if code, out := gate(t, append([]string{"-update", "-baseline", b, "--"}, producer(benchOut, 0)...)...); code != 0 || !strings.Contains(out, "BENCH_UPDATED:") {
		t.Fatalf("update: code %d out %q", code, out)
	}
	got, _ := os.ReadFile(b)
	if string(got) != "# keep\n"+benchgate.Calibration+" 500\ninternal/p.BenchmarkA 1000 budget=1s\ninternal/p.BenchmarkB 2000\n" {
		t.Fatalf("rewritten %q", got)
	}
}

// -update refuses a run the gate could not judge afterwards, leaving the
// baseline byte-identical: no calibration (every later full gate would fail)
// or only the calibration (Rewrite would drop every benchmark).
func TestUpdateRefusesUnjudgeableRun(t *testing.T) {
	noCal := "pkg: " + modulePrefix + "internal/p\nBenchmarkA-8 100 1000 ns/op\nPASS\n"
	spawnBaseline := fullBaseline + benchgate.CalibrationSpawn + " 900\ninternal/p.BenchmarkL 1000 cal=spawn\n"
	lNoSpawnCal := benchOut + "pkg: " + modulePrefix + "internal/p\nBenchmarkL-8 100 1000 ns/op\nPASS\n"
	for _, c := range []struct{ name, base, out, line string }{
		{"no calibration", fullBaseline, noCal, "BENCH_CALIBRATION_MISSING:cpu|current\n"},
		{"calibration only", fullBaseline, calOut, "BENCH_EMPTY:\n"},
		{"spawn line without spawn calibration", spawnBaseline, lNoSpawnCal, "BENCH_CALIBRATION_MISSING:spawn|current\n"},
	} {
		b := writeBaseline(t, c.base)
		code, out := gate(t, append([]string{"-update", "-baseline", b, "--"}, producer(c.out, 0)...)...)
		if code != 1 || !strings.HasSuffix(out, c.line) || strings.Contains(out, "BENCH_UPDATED") {
			t.Errorf("%s: code %d out %q", c.name, code, out)
		}
		if got, _ := os.ReadFile(b); string(got) != c.base {
			t.Errorf("%s: baseline changed: %q", c.name, got)
		}
	}
}

// The calibrations and the benchmarks they scale must not run concurrently,
// must run at a GOMAXPROCS independent of the host, and each must be the
// fastest of several samples.
func TestDefaultProducerSerial(t *testing.T) {
	if !slices.Equal(defaultProducer[:6], []string{"go", "test", "-p", "1", "-cpu", "1"}) {
		t.Fatalf("defaultProducer %v does not run packages serially at GOMAXPROCS 1", defaultProducer)
	}
	i := slices.Index(defaultProducer, "-count")
	if i < 0 || i+1 >= len(defaultProducer) {
		t.Fatalf("defaultProducer %v has no -count", defaultProducer)
	}
	if n, err := strconv.Atoi(defaultProducer[i+1]); err != nil || n < 3 {
		t.Fatalf("defaultProducer -count %q: want at least 3 samples", defaultProducer[i+1])
	}
}

func TestUsage(t *testing.T) {
	if code, _ := gate(t); code != 64 {
		t.Fatalf("no -baseline: %d", code)
	}
	if code, _ := gate(t, "-baseline", filepath.Join(t.TempDir(), "absent")); code != 64 {
		t.Fatalf("absent baseline without -update: %d", code)
	}
}

// Covers main()'s wiring: the built binary, not just run().
func TestBuiltBinary(t *testing.T) {
	if testing.Short() {
		t.Skip("builds a binary")
	}
	bin := filepath.Join(t.TempDir(), "benchgate")
	if out, err := exec.Command("go", "build", "-o", bin, ".").CombinedOutput(); err != nil {
		t.Fatalf("build: %v\n%s", err, out)
	}
	b := writeBaseline(t, fullBaseline+"internal/p.BenchmarkRenamed 10\n")
	cmd := exec.Command(bin, append([]string{"-baseline", b, "--"}, producer(benchOut, 0)...)...)
	out, err := cmd.Output()
	ee, ok := err.(*exec.ExitError)
	if !ok || ee.ExitCode() != 1 || !strings.Contains(string(out), "BENCH_MISSING:internal/p.BenchmarkRenamed") {
		t.Fatalf("err %v out %q", err, out)
	}
}
