package main

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

// runnerRepo is a git repository with a registry, an annotated test, and a
// project runner script that lists and runs it.
func runnerRepo(t *testing.T, run string) *fixture.Repo {
	t.Helper()
	r := fixture.New(t)
	r.Write(t, registry.ConfigPath, "contract: 1\nbootstrap_until: 2099-01-01\n")
	r.Write(t, ".gitignore", ".aitask-testmap/\n")
	r.Write(t, "src/a.sh", "echo a\n")
	r.Write(t, "tests/test_a.sh", "#!/bin/sh\n# testmap:covers src/a.sh\n")
	r.Write(t, "tests/test_b.sh", "#!/bin/sh\n")
	r.Write(t, runner.RunnersPath, "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 5\n    batch_timeout_s: 10\n")
	script := "#!/usr/bin/env bash\ncase \"$1\" in\n" +
		"describe) printf 'unit: file\\ntimeouts: batch\\n';;\n" +
		"list) printf 'tests/test_a.sh\\tfile\\ta\\ntests/test_b.sh\\tfile\\tb\\n';;\n" +
		"run) R=$(sed -n 's/^  \"results\": \"\\(.*\\)\",$/\\1/p' \"$3\")\n" + run + "\n;;\nesac\n"
	r.Write(t, runner.RunnersDir+"/shell.sh", script)
	if err := os.Chmod(filepath.Join(r.Dir, runner.RunnersDir, "shell.sh"), 0o755); err != nil {
		t.Fatal(err)
	}
	r.Commit(t, "1", "test", "fixture")
	t.Chdir(r.Dir)
	return r
}

const twoRows = `printf '{"id":"tests/test_a.sh","status":"pass","duration_ms":3}\n{"id":"tests/test_b.sh","status":"fail","duration_ms":4}\n' >> "$R"; exit 1`

// The run verb end to end through the dispatcher: the line shapes, the
// exit, and the record on disk.
func TestRunThroughBinary(t *testing.T) {
	r := runnerRepo(t, twoRows)
	code, out, errs := call("run", "--all", "--run-id", "r1")
	want := "RUN:r1\n" +
		"DISCOVERY:shell|candidates\n" +
		`INVOCATION:1|shell|2|["shell","",[],"unit",""]` + "\n" +
		"UNIT:tests/test_a.sh|pass|3|top|\n" +
		"UNIT:tests/test_b.sh|fail|4|top|\n" +
		"RUN_ACCOUNTING:2|0|2|0|0\n" +
		"RUN_RESULT:fail|1|1|0|0|0\n"
	if code != 1 || errs != "" || out != want {
		t.Fatalf("run: %d %q %q\nwant %q", code, out, errs, want)
	}
	if _, err := os.Stat(filepath.Join(r.Dir, ".aitask-testmap/runs/r1/inv-001/record.json")); err != nil {
		t.Fatal(err)
	}
	code, out, _ = call("run", "--json", "--run-id", "r2", "tests/test_a.sh")
	var rep struct {
		RunID   string `json:"run_id"`
		Results []struct {
			ID, Status string
		} `json:"results"`
		Accounting          runner.RunAccounting `json:"accounting"`
		DiscoveryCandidates []string             `json:"discovery_candidates"`
	}
	if code != 1 || json.Unmarshal([]byte(out), &rep) != nil || rep.RunID != "r2" || len(rep.Results) != 1 || rep.Results[0].ID != "tests/test_a.sh" ||
		rep.Accounting != (runner.RunAccounting{Selected: 1, Unit: 1}) || len(rep.DiscoveryCandidates) != 1 {
		// test_a passes, but the runner (reporting both) adds an unexpected row.
		t.Fatalf("--json: %d %s", code, out)
	}
}

func TestRunVerbErrors(t *testing.T) {
	runnerRepo(t, twoRows)
	for _, args := range [][]string{{"run"}, {"run", "--all", "tests/test_a.sh"}, {"run", "--bogus"}} {
		if code, out, errs := call(args...); code != 64 || out != "" || !strings.HasPrefix(errs, "USAGE:") {
			t.Errorf("%v: %d %q %q", args, code, out, errs)
		}
	}
	if code, _, errs := call("run", "--run-id", "x", "tests/none.sh"); code != 3 || errs != "RUN_ERROR:unknown-id|tests/none.sh\n" {
		t.Errorf("unknown id: %d %q", code, errs)
	}
	if err := os.Remove(runner.RunnersPath); err != nil {
		t.Fatal(err)
	}
	if code, _, errs := call("run", "--all"); code != 3 || errs != "RUN_ERROR:no-runners|aitestmap/runners.yaml is absent\n" {
		t.Errorf("no runners: %d %q", code, errs)
	}
	t.Chdir(t.TempDir())
	if code, _, errs := call("run", "--all"); code != 2 || errs != "TESTMAP_ABSENT:aitestmap/\n" {
		t.Errorf("no registry: %d %q", code, errs)
	}
}

// The production wiring: scan and check over the real runner repository on
// a fixture repo — no INPUT_UNAVAILABLE, and the listed units reach
// _scanned.yaml.
func TestScanCheckRealLister(t *testing.T) {
	r := runnerRepo(t, twoRows)
	code, out, errs := call("scan", "--apply")
	if code != 0 || errs != "" || out != "DISCOVERY:shell|candidates\nSCAN:1|1|0\nWROTE:"+registry.ScannedPath+"\n" {
		t.Fatalf("scan: %d %q %q", code, out, errs)
	}
	data, _ := os.ReadFile(filepath.Join(r.Dir, registry.ScannedPath))
	if !strings.Contains(string(data), "test: tests/test_a.sh") || !strings.Contains(string(data), "source: src/a.sh") {
		t.Fatalf("_scanned.yaml:\n%s", data)
	}
	code, out, errs = call("check")
	if code != 0 || errs != "" || out != "DISCOVERY:shell|candidates\n"+emptyAdoption+"CHECK:pass|0|0\n" {
		t.Fatalf("check: %d %q %q", code, out, errs)
	}
	// An unlisted bound file is UNREGISTERED through the real lister.
	r.Write(t, "tests/test_c.sh", "#!/bin/sh\n")
	if _, out, _ := call("check"); !strings.Contains(out, "UNREGISTERED:tests/test_c.sh") {
		t.Fatalf("check after adding an unlisted test: %q", out)
	}
	// A runner declaring its discovery is not a candidates source: no line.
	r.Write(t, runner.RunnersPath, "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 5\n    batch_timeout_s: 10\n    discovery: inventory\n")
	if _, out, _ := call("check"); strings.Contains(out, "DISCOVERY:") {
		t.Fatalf("inventory runner: %q", out)
	}
}

// A cases runner end to end through the dispatcher: the CASES line, the
// RUN_ACCOUNTING class counts, and a duplicate case identity at discovery
// refused as the lister's input error by scan and as a protocol error by run.
func TestRunCasesThroughBinary(t *testing.T) {
	r := runnerRepo(t, "")
	r.Write(t, runner.RunnersPath, "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 5\n    batch_timeout_s: 10\n    zero_tests: skip\n")
	script := "#!/usr/bin/env bash\ncase \"$1\" in\n" +
		"describe) printf 'unit: file\\ntimeouts: batch\\naccounting: cases\\ndiscovery: native\\n';;\n" +
		"list) printf \"tests/test_a.sh\\tfile\\ta\\ntests/test_a.sh\\tcase\\tone\\ntests/test_a.sh\\tcase\\t${DUP:-two}\\ntests/test_b.sh\\tfile\\tb\\n\";;\n" +
		"run) C=\"$AIT_TESTMAP_REPORT_DIR/cases.jsonl\"\n" +
		"printf '{\"unit\":\"tests/test_a.sh\",\"case\":\"one\",\"status\":\"pass\",\"duration_ms\":2}\\n{\"unit\":\"tests/test_a.sh\",\"case\":\"two\",\"status\":\"skip\",\"duration_ms\":1}\\n' > \"$C\";;\nesac\n"
	r.Write(t, runner.RunnersDir+"/shell.sh", script)
	code, out, errs := call("run", "--all", "--run-id", "c1")
	want := "RUN:c1\n" +
		`INVOCATION:1|shell|2|["shell","",[],"unit",""]` + "\n" +
		"UNIT:tests/test_a.sh|pass|3|top|\n" +
		"CASES:tests/test_a.sh|2|1|0|0|1|\n" +
		"UNIT:tests/test_b.sh|skip|0|top|\n" +
		"CASES:tests/test_b.sh|0|0|0|0|0|zero_tests\n" +
		"RUN_ACCOUNTING:2|2|0|0|0\n" +
		"RUN_RESULT:pass|1|0|1|0|0\n"
	if code != 0 || errs != "" || out != want {
		t.Fatalf("run: %d %q %q\nwant %q", code, out, errs, want)
	}
	t.Setenv("DUP", "one")
	if code, out, errs := call("scan"); code != 3 || out != "" || !strings.HasPrefix(errs, "INPUT_ERROR:lister|RUNNER_PROTOCOL:shell/list/list line 3: case \"one\" of tests/test_a.sh already listed on line 2") {
		t.Fatalf("duplicate case through scan: %d %q %q", code, out, errs)
	}
	if code, _, errs := call("run", "--all", "--run-id", "c2"); code != 3 || !strings.HasPrefix(errs, "RUNNER_PROTOCOL:shell|list|list line 3: case") {
		t.Fatalf("duplicate case through run: %d %q", code, errs)
	}
}

// A nested entry for a repository already active prints exactly
// RUN_ERROR:recursion|<root> on every verb that reaches the runners — run
// directly, scan and check through the lister — with nothing on stdout,
// exit 3 (G9).
func TestRunAndCheckRecursionLine(t *testing.T) {
	r := runnerRepo(t, twoRows)
	id, err := runner.Identity(context.Background(), r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	root, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv(runner.ActiveEnv, runner.FormatActive([]string{id}))
	for _, args := range [][]string{{"run", "--all", "--run-id", "x"}, {"check"}, {"scan"}} {
		if code, out, errs := call(args...); code != 3 || out != "" || errs != "RUN_ERROR:recursion|"+root+"\n" {
			t.Errorf("%v: %d %q %q", args, code, out, errs)
		}
	}
}
