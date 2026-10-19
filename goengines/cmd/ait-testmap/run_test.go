package main

import (
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
		`INVOCATION:1|shell|2|["shell","",[],"unit",""]` + "\n" +
		"UNIT:tests/test_a.sh|pass|3|top|\n" +
		"UNIT:tests/test_b.sh|fail|4|top|\n" +
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
	}
	if code != 1 || json.Unmarshal([]byte(out), &rep) != nil || rep.RunID != "r2" || len(rep.Results) != 1 || rep.Results[0].ID != "tests/test_a.sh" {
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
	if code != 0 || errs != "" || out != "SCAN:1|1|0\nWROTE:"+registry.ScannedPath+"\n" {
		t.Fatalf("scan: %d %q %q", code, out, errs)
	}
	data, _ := os.ReadFile(filepath.Join(r.Dir, registry.ScannedPath))
	if !strings.Contains(string(data), "test: tests/test_a.sh") || !strings.Contains(string(data), "source: src/a.sh") {
		t.Fatalf("_scanned.yaml:\n%s", data)
	}
	code, out, errs = call("check")
	if code != 0 || errs != "" || out != emptyAdoption+"CHECK:pass|0|0\n" {
		t.Fatalf("check: %d %q %q", code, out, errs)
	}
	// An unlisted bound file is UNREGISTERED through the real lister.
	r.Write(t, "tests/test_c.sh", "#!/bin/sh\n")
	if _, out, _ := call("check"); !strings.Contains(out, "UNREGISTERED:tests/test_c.sh") {
		t.Fatalf("check after adding an unlisted test: %q", out)
	}
}
