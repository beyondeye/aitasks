package main

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

// producer returns argv for a fake `go test -bench` that prints out and exits
// with code.
func producer(out string, code int) []string {
	return []string{"sh", "-c", `printf '%s' "$1"; exit "$2"`, "sh", out, strconv.Itoa(code)}
}

const benchOut = "pkg: " + modulePrefix + "internal/p\nBenchmarkA-8 100 1000 ns/op\nBenchmarkB-8 100 2000 ns/op\nPASS\n"

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

const fullBaseline = "internal/p.BenchmarkA 1000\ninternal/p.BenchmarkB 2000\n"

func TestGatePasses(t *testing.T) {
	b := writeBaseline(t, fullBaseline)
	code, out := gate(t, append([]string{"-baseline", b, "--"}, producer(benchOut, 0)...)...)
	if code != 0 || !strings.HasPrefix(out, "BENCH_MODE:full\n") || strings.Count(out, "BENCH_OK:") != 2 {
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
	orig := "# keep\ninternal/p.BenchmarkA 1 budget=1s\n"
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
	if string(got) != "# keep\ninternal/p.BenchmarkA 1000 budget=1s\ninternal/p.BenchmarkB 2000\n" {
		t.Fatalf("rewritten %q", got)
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
