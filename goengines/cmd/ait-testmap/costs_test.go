package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/cost"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

const passRows = `printf '{"id":"tests/test_a.sh","status":"pass","duration_ms":3}\n{"id":"tests/test_b.sh","status":"pass","duration_ms":4}\n' >> "$R"; exit 0`

// costsRepo is runnerRepo with a fixed host class.
func costsRepo(t *testing.T, run string) *fixture.Repo {
	t.Helper()
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	r := runnerRepo(t, run)
	r.Write(t, registry.ConfigPath, "contract: 1\nbootstrap_until: 2099-01-01\nhost_class: ci\n")
	r.Commit(t, "1", "test", "host class")
	return r
}

func ledgerLines(t *testing.T, r *fixture.Repo) []string {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(r.Dir, cost.LedgerPath))
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		t.Fatal(err)
	}
	if strings.TrimSpace(string(data)) == "" {
		return nil
	}
	return strings.Split(strings.TrimSpace(string(data)), "\n")
}

// The production wiring end to end: the real `run` appends one row per
// result and one per invocation (plus the run_end frame) through the
// registered hook; `costs --update` folds and truncates; a second update
// writes nothing; a review- run appends nothing.
func TestCostsLedgerThroughRun(t *testing.T) {
	r := costsRepo(t, twoRows)
	if code, _, errs := call("run", "--all", "--run-id", "test-1"); code != 1 || errs != "" {
		t.Fatalf("run: %d %q", code, errs)
	}
	lines := ledgerLines(t, r)
	var kinds []string
	for _, l := range lines {
		for _, k := range []string{"invocation", "result", "run_end"} {
			if strings.Contains(l, `"row":"`+k+`"`) {
				kinds = append(kinds, k)
			}
		}
	}
	if strings.Join(kinds, ",") != "invocation,result,result,run_end" {
		t.Fatalf("ledger rows %v:\n%s", kinds, strings.Join(lines, "\n"))
	}
	code, out, errs := call("costs", "--update")
	want := "COSTS_FOLDED:ci|1\nWROTE:aitestmap/costs/ci.yaml\nLEDGER_TRUNCATED:4\n"
	if code != 0 || errs != "" || out != want {
		t.Fatalf("update: %d %q %q", code, out, errs)
	}
	table, _ := os.ReadFile(filepath.Join(r.Dir, "aitestmap/costs/ci.yaml"))
	if code, out, _ := call("costs", "--update"); code != 0 || out != "" {
		t.Fatalf("second update: %d %q", code, out)
	}
	if again, _ := os.ReadFile(filepath.Join(r.Dir, "aitestmap/costs/ci.yaml")); string(again) != string(table) {
		t.Fatal("second update changed the table")
	}
	if code, _, _ := call("run", "--all", "--run-id", "review-1"); code != 1 || ledgerLines(t, r) != nil {
		t.Fatalf("review run: %d %v", code, ledgerLines(t, r))
	}
	code, out, _ = call("costs")
	if code != 0 || !strings.Contains(out, "COST:tests/test_a.sh|1|3.0|3|3|0.000|0|") || !strings.HasSuffix(out, "COSTS:ci|2|1|0\n") {
		t.Fatalf("costs: %d %q", code, out)
	}
}

func TestCostsGateTimeoutAndErrors(t *testing.T) {
	r := costsRepo(t, passRows)
	if code, out, errs := call("costs", "--gate-timeout", "tests_pass"); code != 2 || out != "" || errs != "COSTS_NO_FULL_RUN:ci\n" {
		t.Fatalf("no full run: %d %q %q", code, out, errs)
	}
	if code, _, errs := call("run", "--all", "--run-id", "full-1"); code != 0 || errs != "" {
		t.Fatalf("full run: %d %q", code, errs)
	}
	if code, out, errs := call("costs", "--gate-timeout", "tests_pass"); code != 0 || out != "GATE_TIMEOUT_SUGGESTED:tests_pass|600\n" || errs != "" {
		t.Fatalf("gate timeout: %d %q %q", code, out, errs)
	}
	if code, out, _ := call("costs"); code != 0 || !strings.Contains(out, "FULL_SUITE:ci|full-1|") {
		t.Fatalf("full suite line: %q", out)
	}
	// A clone without the state directory reads the committed table alone.
	if code, _, _ := call("costs", "--update"); code != 0 {
		t.Fatal("update")
	}
	if err := os.RemoveAll(filepath.Join(r.Dir, ".aitask-testmap")); err != nil {
		t.Fatal(err)
	}
	if code, out, _ := call("costs"); code != 0 || !strings.HasSuffix(out, "COSTS:ci|2|1|0\n") {
		t.Fatalf("fresh clone: %d %q", code, out)
	}
	for _, args := range [][]string{{"costs", "--update", "x"}, {"costs", "--gate-timeout", "g", "--json"}, {"costs", "--bogus"}} {
		if code, _, errs := call(args...); code != 64 || !strings.HasPrefix(errs, "USAGE:") {
			t.Errorf("%v: %d %q", args, code, errs)
		}
	}
	if code, _, errs := call("costs", "--host-class", "Policy"); code != 3 || errs != "COSTS_ERROR:host-class|reserved Policy\n" {
		t.Errorf("reserved host class: %d %q", code, errs)
	}
	t.Chdir(t.TempDir())
	if code, _, errs := call("costs"); code != 2 || errs != "TESTMAP_ABSENT:aitestmap/\n" {
		t.Errorf("no registry: %d %q", code, errs)
	}
}
